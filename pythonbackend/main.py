from typing import List, Optional, Dict
from fastapi import FastAPI, Query, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from star_service import (
    get_visible_stars,
    compute_visible_stars,
    get_visible_bodies,
    get_astronomy_events,
    get_visible_stars_batch,
    get_visible_bodies_batch,
    get_constellation_frame,
    get_circumpolar_constellations,
    get_all_constellations_frames,
    get_visible_constellations_summary,
    project_constellations_to_screen,
    get_labels_for_screen,
    resolve_iau_in_fov,
)
from iau import find_constellation_by_radec


app = FastAPI(
    title="Visible Stars API",
    description="Backend con FastAPI para calcular posiciones (alt-az) de estrellas visibles desde una ubicación y fecha/hora dadas",
    version="1.0.0",
)
def _iso_now_z() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


# Error handling
@app.exception_handler(ValueError)
async def value_error_handler(_: Request, exc: ValueError):
    return JSONResponse(
        status_code=400,
        content={
            "detail": str(exc),
            "hint": "Use ISO 8601 UTC con sufijo Z, ej. 2025-01-10T03:00:00Z",
        },
    )


# CORS (entorno de desarrollo: permitir todo)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)


class VisibleStar(BaseModel):
    name: str
    magnitude: float
    altitude_deg: float
    azimuth_deg: float
    distance_ly: Optional[float] = None
    color_temp_K: Optional[float] = None
    bv: Optional[float] = None
    rgb_hex: Optional[str] = None
    aliases: Optional[List[str]] = None
    ids: Optional[Dict[str, int]] = None


@app.get("/health")
def health() -> dict:
    return {"status": "ok"}


@app.get("/visible-stars", response_model=List[VisibleStar])
def visible_stars(
    lat: float = Query(..., description="Latitud del observador en grados (sur negativo)"),
    lon: float = Query(..., description="Longitud del observador en grados (oeste negativo)"),
    at: Optional[str] = Query(
        None,
        description="Fecha/hora en formato ISO 8601 (UTC). Ej: 2024-01-01T02:30:00Z. Si se omite, se usa la hora actual en UTC.",
    ),
    limit: Optional[int] = Query(
        None, description="Limitar el número de resultados. Si se omite, devuelve todas las visibles."
    ),
    max_mag: Optional[float] = Query(
        None, description="Magnitud visual máxima (menor o igual). Ej: 6.0"
    ),
) -> List[VisibleStar]:
    stars = get_visible_stars(
        latitude_deg=lat,
        longitude_deg=lon,
        when_iso_utc=at,
        minimum_altitude_deg=-90.0,
        limit=limit,
        sort_by_magnitude=True,
        max_magnitude=max_mag,
    )
    # FastAPI/Pydantic realizará la conversión a VisibleStar automáticamente
    return stars


@app.get("/sky", response_model=List[VisibleStar])
def sky(
    lat: float = Query(..., description="Latitud del observador en grados (sur negativo)"),
    lon: float = Query(..., description="Longitud del observador en grados (oeste negativo)"),
    date: Optional[str] = Query(
        None,
        description="Fecha/hora en formato ISO 8601 (UTC). Ej: 2024-01-01T02:30:00Z. Si se omite, se usa la hora actual en UTC.",
    ),
) -> List[VisibleStar]:
    stars = compute_visible_stars(lat=lat, lon=lon, date_iso=date)
    return stars


class VisibleBody(BaseModel):
    name: str
    type: str  # planet | moon | sun | comet | asteroid
    altitude_deg: float
    azimuth_deg: float
    magnitude: Optional[float] = None
    phase: Optional[float] = None
    distance_km: Optional[float] = None
    distance_au: Optional[float] = None


@app.get("/constellation-by-direction")
def constellation_by_direction(
    lat: float = Query(..., description="Latitud del observador"),
    lon: float = Query(..., description="Longitud del observador"),
    at: Optional[str] = Query(None, description="Fecha/hora ISO 8601 UTC (Z)"),
    az_deg: float = Query(..., description="Azimut (0..360)"),
    alt_deg: float = Query(..., description="Altitud (-90..+90)"),
):
    """Resuelve a qué constelación (IAU) corresponde una dirección alt-az dada."""
    from skyfield.api import load, wgs84

    # Convert alt-az a RA/Dec usando Skyfield
    ts = load.timescale()
    import math
    from datetime import datetime, timezone
    if at is None:
        t = ts.from_datetime(datetime.now(timezone.utc))
    else:
        # Reusar parser robusto desde star_service si se desea, pero aquí aceptamos ISO directo
        s = at.strip()
        if s.endswith("Z"):
            s = s[:-1] + "+00:00"
        t = ts.from_datetime(datetime.fromisoformat(s))

    observer = wgs84.latlon(latitude_degrees=float(lat), longitude_degrees=float(lon))
    # Skyfield no ofrece inverso alt-az->RA/Dec directo; aproximamos buscando la dirección
    # creamos un vector dirección a partir de alt-az en el sistema local y lo convertimos a RA/Dec con frame local.
    # Para simplificar, sampleamos cercana a esa dirección via astrometric of small angular displacement.
    # Alternativa simple: usar geometría esférica local -> ecuatorial.

    # Transformación aproximada: a partir de LST y lat.
    from star_service import _lst_hours, _deg_to_rad, _rad_to_deg
    from datetime import datetime as _dt
    dt = _dt.utcnow().replace(tzinfo=timezone.utc) if at is None else _dt.fromisoformat(s)
    lst_h = _lst_hours(lon, dt)
    lst_rad = math.radians(lst_h * 15.0)
    lat_rad = math.radians(lat)
    alt_rad = math.radians(alt_deg)
    az_rad = math.radians(az_deg)

    # Inversa de horizontal->ecuatorial
    sin_dec = math.sin(alt_rad) * math.sin(lat_rad) + math.cos(alt_rad) * math.cos(lat_rad) * math.cos(az_rad)
    dec_rad = math.asin(max(-1.0, min(1.0, sin_dec)))
    cos_dec = max(1e-9, math.cos(dec_rad))
    sin_ha = -math.sin(az_rad) * math.cos(alt_rad) / cos_dec
    cos_ha = (math.sin(alt_rad) - math.sin(lat_rad) * math.sin(dec_rad)) / (math.cos(lat_rad) * cos_dec)
    ha_rad = math.atan2(sin_ha, cos_ha)
    ra_rad = (lst_rad - ha_rad) % (2.0 * math.pi)
    ra_deg = math.degrees(ra_rad)
    dec_deg = math.degrees(dec_rad)

    name = find_constellation_by_radec(ra_deg, dec_deg)
    return {
        "at": at or _iso_now_z(),
        "input_alt_az": {"altitude_deg": alt_deg, "azimuth_deg": az_deg},
        "radec_deg": {"ra": ra_deg, "dec": dec_deg},
        "iau_constellation": name,
    }


@app.get("/visible-bodies", response_model=List[VisibleBody])
def visible_bodies(
    lat: float = Query(..., description="Latitud del observador en grados (sur negativo)"),
    lon: float = Query(..., description="Longitud del observador en grados (oeste negativo)"),
    at: Optional[str] = Query(
        None,
        description="Fecha/hora en formato ISO 8601 (UTC). Ej: 2024-01-01T02:30:00Z. Si se omite, se usa la hora actual en UTC.",
    ),
) -> List[VisibleBody]:
    try:
        bodies = get_visible_bodies(
            latitude_deg=lat,
            longitude_deg=lon,
            when_iso_utc=at,
            minimum_altitude_deg=-90.0,
        )
        return bodies
    except Exception:
        # Compatibilidad: si no está disponible o falla, devolver lista vacía con 200
        return []


class AstronomyEvent(BaseModel):
    type: str  # planet_rise | planet_set | moon_phase | solar_eclipse | lunar_eclipse
    time: str
    description: str


@app.get("/astronomy-events", response_model=List[AstronomyEvent])
def astronomy_events(
    lat: float = Query(..., description="Latitud del observador en grados (sur negativo)"),
    lon: float = Query(..., description="Longitud del observador en grados (oeste negativo)"),
    start_datetime: str = Query(..., description="Inicio (ISO 8601 UTC, ej: 2025-08-12T00:00:00Z)"),
    end_datetime: str = Query(..., description="Fin (ISO 8601 UTC, debe ser posterior al inicio)"),
) -> List[AstronomyEvent]:
    try:
        events = get_astronomy_events(
            latitude_deg=lat,
            longitude_deg=lon,
            start_iso_utc=start_datetime,
            end_iso_utc=end_datetime,
        )
        return events
    except Exception:
        return []


@app.get("/visible-stars-batch")
def visible_stars_batch(
    lat: float = Query(..., description="Latitud del observador en grados (sur negativo)"),
    lon: float = Query(..., description="Longitud del observador en grados (oeste negativo)"),
    start: str = Query(..., description="Inicio (ISO 8601 UTC, ej: 2025-08-11T18:00:00Z)"),
    end: str = Query(..., description="Fin (ISO 8601 UTC, ej: 2025-08-12T06:00:00Z)"),
    step_hours: float = Query(1.0, description="Paso en horas entre frames"),
    max_mag: Optional[float] = Query(None, description="Magnitud visual máxima (menor o igual). Ej: 6.0"),
    limit: Optional[int] = Query(None, description="Límite por frame"),
):
    try:
        frames = get_visible_stars_batch(
            latitude_deg=lat,
            longitude_deg=lon,
            start_iso_utc=start,
            end_iso_utc=end,
            step_hours=step_hours,
            max_magnitude=max_mag,
            limit=limit,
        )
        return {"frames": frames}
    except Exception:
        return {"frames": []}


@app.get("/constellations-visible")
def constellations_visible(
    lat: float = Query(..., description="Latitud del observador"),
    lon: float = Query(..., description="Longitud del observador"),
    at: Optional[str] = Query(None, description="Fecha/hora ISO 8601 UTC (Z)"),
    min_alt: float = Query(0.0, description="Altitud mínima (grados)"),
    names: Optional[str] = Query(None, description="Lista separada por comas de constelaciones"),
    include_below_horizon: bool = Query(False, description="Incluir constelaciones bajo el horizonte"),
    fov_center_az_deg: Optional[float] = Query(None, description="Centro FOV azimut (deg)"),
    fov_center_alt_deg: Optional[float] = Query(None, description="Centro FOV altitud (deg)"),
    fov_h_deg: Optional[float] = Query(None, description="Ancho FOV (deg)"),
    fov_v_deg: Optional[float] = Query(None, description="Alto FOV (deg)"),
):
    frames = get_visible_constellations_summary(
        latitude_deg=lat,
        longitude_deg=lon,
        when_iso_utc=at,
        minimum_altitude_deg=min_alt,
        names=[s.strip() for s in names.split(",") if s.strip()] if names else None,
        include_below_horizon=include_below_horizon,
        fov_center_az_deg=fov_center_az_deg,
        fov_center_alt_deg=fov_center_alt_deg,
        fov_h_deg=fov_h_deg,
        fov_v_deg=fov_v_deg,
    )
    return {"at": at or "now", "constellations": frames}


@app.get("/constellations-screen")
def constellations_screen(
    lat: float = Query(..., description="Latitud"),
    lon: float = Query(..., description="Longitud"),
    at: Optional[str] = Query(None, description="Fecha/hora ISO 8601 UTC (Z)"),
    min_alt: float = Query(0.0, description="Altitud mínima"),
    names: Optional[str] = Query(None, description="Lista separada por comas"),
    include_below_horizon: bool = Query(False, description="Incluir bajo el horizonte"),
    fov_center_az_deg: Optional[float] = Query(None, description="FOV centro az (deg)"),
    fov_center_alt_deg: Optional[float] = Query(None, description="FOV centro alt (deg)"),
    fov_h_deg: float = Query(..., description="FOV ancho (deg)"),
    fov_v_deg: float = Query(..., description="FOV alto (deg)"),
    width_px: int = Query(..., description="Ancho pantalla px"),
    height_px: int = Query(..., description="Alto pantalla px"),
    include_offscreen: bool = Query(False, description="Incluir estrellas fuera del FOV"),
    clip_edges_to_fov: bool = Query(True, description="Recortar edges al FOV"),
    heading_offset_deg: float = Query(0.0, description="Corrección de brújula (deg)"),
    roll_deg: float = Query(0.0, description="Rotación de pantalla (roll, deg)"),
    cache_bucket_s: Optional[int] = Query(1, description="Cache por bucket de segundos (modo AR: 1, educativo: 2)"),
    yaw_deg: Optional[float] = Query(None, description="Orientación yaw/heading (deg)"),
    pitch_deg: Optional[float] = Query(None, description="Orientación pitch (deg)"),
    pitch_offset_deg: float = Query(0.0, description="Corrección de pitch (deg)"),
):
    # Derivar centro del FOV usando sensores si no vienen centros explícitos
    if yaw_deg is not None:
        az_center = (yaw_deg + heading_offset_deg) % 360.0
    else:
        if fov_center_az_deg is None:
            raise HTTPException(status_code=422, detail="Requiere fov_center_az_deg o yaw_deg")
        az_center = float(fov_center_az_deg)

    if pitch_deg is not None:
        alt_center = pitch_deg + pitch_offset_deg
        if alt_center > 90.0:
            alt_center = 90.0
        if alt_center < -90.0:
            alt_center = -90.0
    else:
        if fov_center_alt_deg is None:
            raise HTTPException(status_code=422, detail="Requiere fov_center_alt_deg o pitch_deg")
        alt_center = float(fov_center_alt_deg)

    frames = project_constellations_to_screen(
        latitude_deg=lat,
        longitude_deg=lon,
        when_iso_utc=at,
        minimum_altitude_deg=min_alt,
        names=[s.strip() for s in names.split(",") if s.strip()] if names else None,
        include_below_horizon=include_below_horizon,
        fov_center_az_deg=az_center,
        fov_center_alt_deg=alt_center,
        fov_h_deg=fov_h_deg,
        fov_v_deg=fov_v_deg,
        width_px=width_px,
        height_px=height_px,
        include_offscreen=include_offscreen,
        clip_edges_to_fov=clip_edges_to_fov,
        heading_offset_deg=heading_offset_deg,
        roll_deg=roll_deg,
        cache_bucket_s=cache_bucket_s,
    )
    return {"at": at or "now", "frames": frames}


@app.get("/constellations-labels")
def constellations_labels(
    lat: float = Query(..., description="Latitud"),
    lon: float = Query(..., description="Longitud"),
    at: Optional[str] = Query(None, description="Fecha/hora ISO 8601 UTC (Z)"),
    min_alt: float = Query(0.0, description="Altitud mínima"),
    names: Optional[str] = Query(None, description="Lista separada por comas"),
    include_below_horizon: bool = Query(False, description="Incluir bajo el horizonte"),
    fov_center_az_deg: float = Query(..., description="FOV centro az (deg)"),
    fov_center_alt_deg: float = Query(..., description="FOV centro alt (deg)"),
    fov_h_deg: float = Query(..., description="FOV ancho (deg)"),
    fov_v_deg: float = Query(..., description="FOV alto (deg)"),
    width_px: int = Query(..., description="Ancho pantalla px"),
    height_px: int = Query(..., description="Alto pantalla px"),
    heading_offset_deg: float = Query(0.0, description="Corrección de brújula (deg)"),
    roll_deg: float = Query(0.0, description="Rotación de pantalla (roll, deg)"),
    max_labels: int = Query(20, description="Cantidad máxima de labels"),
    max_mag: float = Query(4.0, description="Magnitud máxima para etiquetar"),
    min_separation_px: float = Query(24.0, description="Separación mínima entre labels (px)"),
    cache_bucket_s: Optional[int] = Query(1, description="Cache por bucket de segundos (modo AR: 1, educativo: 2)"),
):
    labels = get_labels_for_screen(
        latitude_deg=lat,
        longitude_deg=lon,
        when_iso_utc=at,
        minimum_altitude_deg=min_alt,
        names=[s.strip() for s in names.split(",") if s.strip()] if names else None,
        include_below_horizon=include_below_horizon,
        fov_center_az_deg=fov_center_az_deg,
        fov_center_alt_deg=fov_center_alt_deg,
        fov_h_deg=fov_h_deg,
        fov_v_deg=fov_v_deg,
        width_px=width_px,
        height_px=height_px,
        heading_offset_deg=heading_offset_deg,
        roll_deg=roll_deg,
        max_labels=max_labels,
        max_mag=max_mag,
        min_separation_px=min_separation_px,
        cache_bucket_s=cache_bucket_s,
    )
    return {"at": at or "now", "labels": labels}


@app.get("/iau-in-fov")
def iau_in_fov(
    lat: float = Query(..., description="Latitud"),
    lon: float = Query(..., description="Longitud"),
    at: Optional[str] = Query(None, description="Fecha/hora ISO 8601 UTC (Z)"),
    fov_center_az_deg: Optional[float] = Query(None, description="Centro FOV az (deg)"),
    fov_center_alt_deg: Optional[float] = Query(None, description="Centro FOV alt (deg)"),
    fov_h_deg: float = Query(..., description="FOV ancho (deg)"),
    fov_v_deg: float = Query(..., description="FOV alto (deg)"),
    yaw_deg: Optional[float] = Query(None, description="Orientación yaw/heading (deg)"),
    pitch_deg: Optional[float] = Query(None, description="Orientación pitch (deg)"),
    heading_offset_deg: float = Query(0.0, description="Corrección de brújula (deg)"),
    pitch_offset_deg: float = Query(0.0, description="Corrección de pitch (deg)"),
):
    # Derivar centro del FOV desde sensores si aplica
    if yaw_deg is not None:
        az_center = (yaw_deg + heading_offset_deg) % 360.0
    else:
        if fov_center_az_deg is None:
            raise HTTPException(status_code=422, detail="Requiere fov_center_az_deg o yaw_deg")
        az_center = float(fov_center_az_deg)
    if pitch_deg is not None:
        alt_center = pitch_deg + pitch_offset_deg
        if alt_center > 90.0:
            alt_center = 90.0
        if alt_center < -90.0:
            alt_center = -90.0
    else:
        if fov_center_alt_deg is None:
            raise HTTPException(status_code=422, detail="Requiere fov_center_alt_deg o pitch_deg")
        alt_center = float(fov_center_alt_deg)

    name = resolve_iau_in_fov(
        latitude_deg=lat,
        longitude_deg=lon,
        when_iso_utc=at,
        fov_center_az_deg=az_center,
        fov_center_alt_deg=alt_center,
        fov_h_deg=fov_h_deg,
        fov_v_deg=fov_v_deg,
    )
    return {"at": at or _iso_now_z(), "iau_constellation": name}


@app.get("/visible-bodies-batch")
def visible_bodies_batch(
    lat: float = Query(..., description="Latitud del observador en grados (sur negativo)"),
    lon: float = Query(..., description="Longitud del observador en grados (oeste negativo)"),
    start: str = Query(..., description="Inicio (ISO 8601 UTC, ej: 2025-08-11T18:00:00Z)"),
    end: str = Query(..., description="Fin (ISO 8601 UTC, ej: 2025-08-12T06:00:00Z)"),
    step_hours: float = Query(1.0, description="Paso en horas entre frames"),
    limit: Optional[int] = Query(None, description="Límite por frame"),
):
    try:
        frames = get_visible_bodies_batch(
            latitude_deg=lat,
            longitude_deg=lon,
            start_iso_utc=start,
            end_iso_utc=end,
            step_hours=step_hours,
            limit=limit,
        )
        return {"frames": frames}
    except Exception:
        return {"frames": []}


@app.get("/constellations")
def list_constellations_api():
    return {"constellations": get_circumpolar_constellations()}


@app.get("/constellation-frame")
def constellation_frame(
    name: str = Query(..., description="Nombre de la constelación (ej.: 'Ursa Minor', 'Cassiopeia')"),
    lat: float = Query(..., description="Latitud del observador"),
    lon: float = Query(..., description="Longitud del observador"),
    at: Optional[str] = Query(None, description="Fecha/hora ISO 8601 UTC (Z)"),
    min_alt: float = Query(0.0, description="Altitud mínima (grados). 0 = sobre horizonte"),
):
    try:
        frame = get_constellation_frame(
            constellation_name=name,
            latitude_deg=lat,
            longitude_deg=lon,
            when_iso_utc=at,
            minimum_altitude_deg=min_alt,
        )
        return frame
    except Exception as e:
        return {"name": name, "stars": [], "edges": [], "error": str(e)}


@app.get("/constellations-frames")
def constellations_frames(
    lat: float = Query(..., description="Latitud del observador"),
    lon: float = Query(..., description="Longitud del observador"),
    at: Optional[str] = Query(None, description="Fecha/hora ISO 8601 UTC (Z)"),
    min_alt: float = Query(0.0, description="Altitud mínima (grados)"),
    names: Optional[str] = Query(None, description="Lista separada por comas de constelaciones"),
    include_below_horizon: bool = Query(True, description="Incluir constelaciones bajo el horizonte (modo educativo)"),
    fov_center_az_deg: Optional[float] = Query(None, description="Centro FOV azimut (deg)"),
    fov_center_alt_deg: Optional[float] = Query(None, description="Centro FOV altitud (deg)"),
    fov_h_deg: Optional[float] = Query(None, description="Ancho FOV (deg)"),
    fov_v_deg: Optional[float] = Query(None, description="Alto FOV (deg)"),
    clip_edges_to_fov: bool = Query(False, description="Recortar edges al FOV"),
    cache_bucket_s: Optional[int] = Query(1, description="Cache por bucket de segundos (modo AR: 1, educativo: 2)"),
    dim_below_horizon: bool = Query(True, description="Sugerir estilo tenue para constelaciones bajo el horizonte"),
):
    try:
        frames = get_all_constellations_frames(
            latitude_deg=lat,
            longitude_deg=lon,
            when_iso_utc=at,
            minimum_altitude_deg=min_alt,
            names=[s.strip() for s in names.split(",") if s.strip()] if names else None,
            include_below_horizon=include_below_horizon,
            fov_center_az_deg=fov_center_az_deg,
            fov_center_alt_deg=fov_center_alt_deg,
            fov_h_deg=fov_h_deg,
            fov_v_deg=fov_v_deg,
            clip_edges_to_fov=clip_edges_to_fov,
            cache_bucket_s=cache_bucket_s,
        )
        # Anotar estilo sugerido según visibilidad
        if dim_below_horizon:
            for f in frames:
                if bool(f.get("below_horizon", False)):
                    f["style"] = {"variant": "dim", "opacity": 0.35}
                else:
                    f["style"] = {"variant": "normal", "opacity": 1.0}
        return {"at": at or "now", "frames": frames}
    except Exception:
        return {"frames": []}

if __name__ == "__main__":
    # Ejecución directa: uvicorn con autoreload para desarrollo
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)


