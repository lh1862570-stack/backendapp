from typing import List, Optional, Dict
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from star_service import (
    get_visible_stars,
    compute_visible_stars,
    get_visible_bodies,
    get_astronomy_events,
    get_visible_stars_batch,
    get_visible_bodies_batch,
)


app = FastAPI(
    title="Visible Stars API",
    description="Backend con FastAPI para calcular posiciones (alt-az) de estrellas visibles desde una ubicación y fecha/hora dadas",
    version="1.0.0",
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

if __name__ == "__main__":
    # Ejecución directa: uvicorn con autoreload para desarrollo
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)


