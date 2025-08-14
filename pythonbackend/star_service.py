from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from datetime import timedelta
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional

# Skyfield para cálculos astronómicos de alta precisión
from skyfield.api import Star, load, wgs84
from skyfield import almanac
from constellations import get_constellation_definition, list_constellations


@dataclass
class CatalogStar:
    name: str
    ra_hours: float  # Ascensión recta en horas
    dec_deg: float   # Declinación en grados
    magnitude: float
    # Campos opcionales enriquecidos (si existen en el catálogo)
    distance_ly: Optional[float] = None
    color_temp_K: Optional[float] = None
    bv: Optional[float] = None
    rgb_hex: Optional[str] = None
    aliases: Optional[List[str]] = None
    ids: Optional[Dict[str, int]] = None


def _module_dir() -> Path:
    return Path(__file__).resolve().parent


def _catalog_path() -> Path:
    return _module_dir() / "star_catalog.json"


@lru_cache(maxsize=1)
def load_star_catalog() -> List[CatalogStar]:
    path = _catalog_path()
    with path.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    stars: List[CatalogStar] = []
    for item in raw:
        # Aceptar ambos esquemas: nuevo (ra, dec, mag) y anterior (ra_hours, dec_deg, magnitude)
        ra_value = item.get("ra", item.get("ra_hours"))
        dec_value = item.get("dec", item.get("dec_deg"))
        mag_value = item.get("mag", item.get("magnitude"))

        if ra_value is None or dec_value is None or mag_value is None or "name" not in item:
            raise ValueError("Entrada de catálogo inválida: se requieren name, y ra/ra_hours, dec/dec_deg, mag/magnitude")

        stars.append(
            CatalogStar(
                name=str(item["name"]),
                ra_hours=float(ra_value),
                dec_deg=float(dec_value),
                magnitude=float(mag_value),
                distance_ly=(float(item["distance_ly"]) if "distance_ly" in item and item["distance_ly"] is not None else None),
                color_temp_K=(float(item["color_temp_K"]) if "color_temp_K" in item and item["color_temp_K"] is not None else None),
                bv=(float(item["bv"]) if "bv" in item and item["bv"] is not None else None),
                rgb_hex=(str(item["rgb_hex"]) if "rgb_hex" in item and item["rgb_hex"] is not None else None),
                aliases=(list(item["aliases"]) if "aliases" in item and item["aliases"] is not None else None),
                ids=(dict(item["ids"]) if "ids" in item and item["ids"] is not None else None),
            )
        )
    return stars


def _normalize_hours(hours: float) -> float:
    return hours % 24.0


def _normalize_degrees_360(deg: float) -> float:
    return deg % 360.0


def _deg_to_rad(deg: float) -> float:
    return math.radians(deg)


def _rad_to_deg(rad: float) -> float:
    return math.degrees(rad)


def _julian_date(dt: datetime) -> float:
    # Conversión a UTC consciente de zona horaria
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)

    year = dt.year
    month = dt.month
    day = dt.day
    hour = dt.hour
    minute = dt.minute
    second = dt.second + dt.microsecond / 1_000_000

    if month <= 2:
        year -= 1
        month += 12

    A = year // 100
    B = 2 - A + (A // 4)

    day_fraction = (hour + (minute + second / 60.0) / 60.0) / 24.0
    JD = (
        int(365.25 * (year + 4716))
        + int(30.6001 * (month + 1))
        + day
        + B
        - 1524.5
        + day_fraction
    )
    return JD


def _gmst_hours(dt: datetime) -> float:
    # Aproximación precisa para propósitos de visualización
    JD = _julian_date(dt)
    d = JD - 2451545.0  # días desde J2000.0
    GMST = 18.697374558 + 24.06570982441908 * d  # horas
    return _normalize_hours(GMST)


def _lst_hours(longitude_deg: float, dt: datetime) -> float:
    return _normalize_hours(_gmst_hours(dt) + longitude_deg / 15.0)


def _parse_iso_datetime_utc(when_iso_utc: Optional[str]) -> datetime:
    if not when_iso_utc:
        return datetime.now(timezone.utc)
    s = when_iso_utc.strip()
    if s.endswith("Z"):
        s = s[:-1] + "+00:00"
    try:
        dt = datetime.fromisoformat(s)
    except Exception:
        raise ValueError(
            "Fecha/hora inválida. Use ISO 8601, por ejemplo: 2024-01-01T02:30:00Z"
        )
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt


def _equatorial_to_horizontal(
    ra_hours: float, dec_deg: float, latitude_deg: float, lst_hours: float
) -> Dict[str, float]:
    # Ángulos a radianes
    ra_rad = _deg_to_rad(ra_hours * 15.0)  # 15 deg por hora
    dec_rad = _deg_to_rad(dec_deg)
    lat_rad = _deg_to_rad(latitude_deg)
    lst_rad = _deg_to_rad(lst_hours * 15.0)

    # Ángulo horario HA = LST - RA
    ha_rad = lst_rad - ra_rad

    sin_alt = math.sin(dec_rad) * math.sin(lat_rad) + math.cos(dec_rad) * math.cos(lat_rad) * math.cos(ha_rad)
    alt_rad = math.asin(max(-1.0, min(1.0, sin_alt)))

    cos_alt = max(1e-9, math.cos(alt_rad))  # evitar divisiones por cero en el zenit
    sin_az = -math.cos(dec_rad) * math.sin(ha_rad) / cos_alt
    cos_az = (math.sin(dec_rad) - math.sin(alt_rad) * math.sin(lat_rad)) / (cos_alt * math.cos(lat_rad))
    az_rad = math.atan2(sin_az, cos_az)

    alt_deg = _rad_to_deg(alt_rad)
    az_deg = _normalize_degrees_360(_rad_to_deg(az_rad))
    return {"altitude_deg": alt_deg, "azimuth_deg": az_deg}


# ------------------------- Cuerpos del Sistema Solar -------------------------

@lru_cache(maxsize=1)
def _load_ephemeris():
    # Kernel estándar relativamente liviano
    return load("de421.bsp")


def _planet_magnitude(planet_name: str, r_au: float, delta_au: float, phase_angle_deg: float) -> Optional[float]:
    """Magnitudes visuales aproximadas para planetas principales.

    Fórmulas empíricas simplificadas. r = distancia Sol-planeta (AU),
    Δ = distancia Tierra-planeta (AU), α = ángulo de fase (grados).
    """
    import math as _math

    log_term = 5.0 * _math.log10(max(1e-12, r_au * delta_au))
    a = phase_angle_deg

    name = planet_name.lower()
    if name == "mercury":
        return -0.60 + log_term + 0.0380 * a - 0.000273 * a * a + 0.000002 * a * a * a
    if name == "venus":
        return -4.47 + log_term + 0.036 * a - 0.000000484 * (a ** 3)
    if name == "mars":
        return -1.52 + log_term + 0.016 * a
    if name == "jupiter barycenter" or name == "jupiter":
        return -9.40 + log_term + 0.005 * a
    if name == "saturn barycenter" or name == "saturn":
        # Sin contribuir con anillos (aprox)
        return -8.88 + log_term + 0.044 * a
    if name == "uranus barycenter" or name == "uranus":
        return -7.19 + log_term + 0.002 * a
    if name == "neptune barycenter" or name == "neptune":
        return -6.87 + log_term
    return None


def _moon_magnitude(phase_angle_deg: float, delta_km: float) -> float:
    """Magnitud lunar aproximada basada en fase; muy simplificada.

    No corrige todos los efectos; suficiente para orden de magnitud.
    """
    import math as _math

    a = phase_angle_deg
    # Relación empírica (aprox): Meeus-like
    m = -12.7 + 0.026 * _math.fabs(a) + 4e-9 * (a ** 4)
    # Corrección leve por distancia (referencia ~384400 km):
    if delta_km > 0:
        m += 5.0 * _math.log10(delta_km / 384400.0)
    return m


def get_visible_bodies(
    *,
    latitude_deg: float,
    longitude_deg: float,
    when_iso_utc: Optional[str] = None,
    minimum_altitude_deg: float = -90.0,
) -> List[Dict[str, float]]:
    """
    Calcula posiciones (alt-az) de cuerpos brillantes del Sistema Solar y devuelve
    una lista con dicts: {name, type, magnitude?, altitude_deg, azimuth_deg, phase?, distance_km?, distance_au?}.
    """
    dt_utc = _parse_iso_datetime_utc(when_iso_utc)
    ts = load.timescale()
    t = ts.from_datetime(dt_utc)

    eph = _load_ephemeris()

    observer = wgs84.latlon(latitude_degrees=float(latitude_deg), longitude_degrees=float(longitude_deg))

    results: List[Dict[str, float]] = []

    bodies_planets = [
        ("Mercury", "planet", eph["mercury"]),
        ("Venus", "planet", eph["venus"]),
        ("Mars", "planet", eph["mars"]),
        ("Jupiter", "planet", eph["jupiter barycenter"]),
        ("Saturn", "planet", eph["saturn barycenter"]),
        ("Uranus", "planet", eph["uranus barycenter"]),
        ("Neptune", "planet", eph["neptune barycenter"]),
    ]

    # Sol
    sun_app = observer.at(t).observe(eph["sun"]).apparent()
    sun_alt, sun_az, sun_dist = sun_app.altaz()
    if float(sun_alt.degrees) >= minimum_altitude_deg:
        results.append(
            {
                "name": "Sun",
                "type": "sun",
                "magnitude": -26.74,
                "altitude_deg": float(sun_alt.degrees),
                "azimuth_deg": float(sun_az.degrees) % 360.0,
                "distance_au": float(sun_dist.au),
            }
        )

    # Luna
    moon_app = observer.at(t).observe(eph["moon"]).apparent()
    moon_alt, moon_az, moon_dist = moon_app.altaz()
    if float(moon_alt.degrees) >= minimum_altitude_deg:
        # Fase (fracción iluminada 0..1) y ángulo de fase en grados
        frac = float(almanac.fraction_illuminated(eph, "moon", t))
        phase_angle = float(almanac.phase_angle(eph, "moon", t).degrees)
        mag_moon = _moon_magnitude(phase_angle_deg=phase_angle, delta_km=float(moon_dist.km))
        results.append(
            {
                "name": "Moon",
                "type": "moon",
                "magnitude": mag_moon,
                "altitude_deg": float(moon_alt.degrees),
                "azimuth_deg": float(moon_az.degrees) % 360.0,
                "phase": frac,
                "distance_km": float(moon_dist.km),
            }
        )

    # Planetas
    earth = eph["earth"]
    sun = eph["sun"]
    for name, ptype, body in bodies_planets:
        app = observer.at(t).observe(body).apparent()
        alt, az, dist_topo = app.altaz()
        alt_deg = float(alt.degrees)
        if alt_deg < minimum_altitude_deg:
            continue

        # Distancia geocéntrica y heliocéntrica para magnitud
        geo = earth.at(t).observe(body).apparent().distance().au
        helio = sun.at(t).observe(body).apparent().distance().au
        try:
            phase = float(almanac.phase_angle(eph, body, t).degrees)
        except Exception:
            phase = 0.0

        magnitude = _planet_magnitude(body.target_name.lower() if hasattr(body, "target_name") else name.lower(), helio, geo, phase)

        item: Dict[str, float] = {
            "name": name,
            "type": ptype,
            "altitude_deg": alt_deg,
            "azimuth_deg": float(az.degrees) % 360.0,
            "distance_au": float(dist_topo.au),
        }
        if magnitude is not None:
            item["magnitude"] = magnitude

        results.append(item)

    # Ordenar por altitud descendente
    results.sort(key=lambda x: x.get("altitude_deg", -1e9), reverse=True)
    return results


# --------------------------- Eventos astronómicos ----------------------------

def _format_time_iso_z(t) -> str:
    # t puede ser skyfield Time o datetime
    if hasattr(t, "utc_strftime"):
        return t.utc_strftime("%Y-%m-%dT%H:%M:%SZ")
    if isinstance(t, datetime):
        if t.tzinfo is None:
            t = t.replace(tzinfo=timezone.utc)
        else:
            t = t.astimezone(timezone.utc)
        return t.strftime("%Y-%m-%dT%H:%M:%SZ")
    raise TypeError("Unsupported time type")


def _az_to_cardinal8(azimuth_deg: float) -> str:
    # N, NE, E, SE, S, SW, W, NW
    dirs = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
    ix = int(((azimuth_deg % 360.0) + 22.5) // 45) % 8
    return dirs[ix]


def get_astronomy_events(
    *,
    latitude_deg: float,
    longitude_deg: float,
    start_iso_utc: str,
    end_iso_utc: str,
) -> List[Dict[str, str]]:
    """
    Devuelve eventos astronómicos entre start y end (UTC):
    - planet_rise / planet_set para planetas principales
    - moon_phase para las 4 fases principales
    """
    t_start = _parse_iso_datetime_utc(start_iso_utc)
    t_end = _parse_iso_datetime_utc(end_iso_utc)
    if t_end <= t_start:
        raise ValueError("end_datetime debe ser posterior a start_datetime")

    ts = load.timescale()
    t0 = ts.from_datetime(t_start)
    t1 = ts.from_datetime(t_end)

    eph = _load_ephemeris()
    topos = wgs84.latlon(latitude_degrees=float(latitude_deg), longitude_degrees=float(longitude_deg))

    events: List[Dict[str, str]] = []

    # 1) Fases de la luna (eventos discretos: nueva, cuarto creciente, llena, cuarto menguante)
    try:
        f_moon = almanac.moon_phases(eph)
        times_moon, phases = almanac.find_discrete(t0, t1, f_moon)
        phase_names = {
            0: "Luna nueva",
            1: "Cuarto creciente",
            2: "Luna llena",
            3: "Cuarto menguante",
        }
        for ti, ph in zip(times_moon, phases):
            # Fracción iluminada para enriquecer descripción
            frac = float(almanac.fraction_illuminated(eph, "moon", ti))
            pct = int(round(frac * 100))
            desc = f"{phase_names.get(int(ph), 'Fase lunar')} ({pct}%)"
            events.append(
                {
                    "type": "moon_phase",
                    "time": _format_time_iso_z(ti),
                    "description": desc,
                }
            )
    except Exception:
        # Si falla, no incluimos fases
        pass

    # 2) Salidas y puestas de planetas principales
    planets = [
        ("Mercury", eph["mercury"]),
        ("Venus", eph["venus"]),
        ("Mars", eph["mars"]),
        ("Jupiter", eph["jupiter barycenter"]),
        ("Saturn", eph["saturn barycenter"]),
        ("Uranus", eph["uranus barycenter"]),
        ("Neptune", eph["neptune barycenter"]),
    ]

    for name, body in planets:
        try:
            f_rs = almanac.risings_and_settings(eph, body, topos)
            times, updown = almanac.find_discrete(t0, t1, f_rs)
            # Determinar transición respecto al estado inicial
            state0 = bool(f_rs(t0))  # True si por encima del horizonte al inicio
            prev = state0
            for ti, st in zip(times, updown):
                st_bool = bool(st)
                # Evento de cambio
                if not prev and st_bool:
                    # Rise
                    alt, az, _ = topos.at(ti).observe(body).apparent().altaz()
                    dir_label = _az_to_cardinal8(float(az.degrees))
                    events.append(
                        {
                            "type": "planet_rise",
                            "time": _format_time_iso_z(ti),
                            "description": f"{name} sale por el {dir_label}",
                        }
                    )
                elif prev and not st_bool:
                    # Set
                    alt, az, _ = topos.at(ti).observe(body).apparent().altaz()
                    dir_label = _az_to_cardinal8(float(az.degrees))
                    events.append(
                        {
                            "type": "planet_set",
                            "time": _format_time_iso_z(ti),
                            "description": f"{name} se pone por el {dir_label}",
                        }
                    )
                prev = st_bool
        except Exception:
            continue

    # Orden por tiempo
    events.sort(key=lambda e: e.get("time", ""))
    return events


# ------------------------------- Batch helpers -------------------------------

def _iterate_datetimes_utc(start_dt: datetime, end_dt: datetime, step_hours: float):
    if step_hours <= 0:
        raise ValueError("step_hours debe ser > 0")
    cur = start_dt
    step = timedelta(hours=step_hours)
    while cur <= end_dt:
        yield cur
        cur = cur + step


def get_visible_stars_batch(
    *,
    latitude_deg: float,
    longitude_deg: float,
    start_iso_utc: str,
    end_iso_utc: str,
    step_hours: float = 1.0,
    max_magnitude: Optional[float] = None,
    limit: Optional[int] = None,
) -> List[Dict[str, object]]:
    start_dt = _parse_iso_datetime_utc(start_iso_utc)
    end_dt = _parse_iso_datetime_utc(end_iso_utc)
    if end_dt <= start_dt:
        return []

    frames: List[Dict[str, object]] = []
    for dt in _iterate_datetimes_utc(start_dt, end_dt, step_hours):
        iso = _format_time_iso_z(dt)
        stars = get_visible_stars(
            latitude_deg=latitude_deg,
            longitude_deg=longitude_deg,
            when_iso_utc=iso,
            minimum_altitude_deg=-90.0,
            limit=limit,
            sort_by_magnitude=True,
            max_magnitude=max_magnitude,
        )
        frames.append({"at": iso, "stars": stars})
    return frames


def get_visible_bodies_batch(
    *,
    latitude_deg: float,
    longitude_deg: float,
    start_iso_utc: str,
    end_iso_utc: str,
    step_hours: float = 1.0,
    limit: Optional[int] = None,
) -> List[Dict[str, object]]:
    start_dt = _parse_iso_datetime_utc(start_iso_utc)
    end_dt = _parse_iso_datetime_utc(end_iso_utc)
    if end_dt <= start_dt:
        return []

    frames: List[Dict[str, object]] = []
    for dt in _iterate_datetimes_utc(start_dt, end_dt, step_hours):
        iso = _format_time_iso_z(dt)
        bodies = get_visible_bodies(
            latitude_deg=latitude_deg,
            longitude_deg=longitude_deg,
            when_iso_utc=iso,
            minimum_altitude_deg=-90.0,
        )
        if limit is not None and limit > 0:
            bodies = bodies[:limit]
        frames.append({"at": iso, "bodies": bodies})
    return frames


def get_visible_stars(
    *,
    latitude_deg: float,
    longitude_deg: float,
    when_iso_utc: Optional[str] = None,
    minimum_altitude_deg: float = -90.0,
    limit: Optional[int] = None,
    sort_by_magnitude: bool = True,
    max_magnitude: Optional[float] = None,
) -> List[Dict[str, float]]:
    """
    Calcula estrellas visibles y devuelve una lista de dicts con name, magnitude, altitude_deg, azimuth_deg.

    - latitude_deg: Latitud del observador (sur negativo)
    - longitude_deg: Longitud del observador (oeste negativo)
    - when_iso_utc: Fecha/hora ISO 8601 (UTC). Si None, ahora en UTC
    - minimum_altitude_deg: Umbral de altitud para visibilidad
    - limit: Limitar la cantidad de resultados
    - sort_by_magnitude: True -> más brillantes primero, False -> más altos primero
    """
    dt = _parse_iso_datetime_utc(when_iso_utc)
    lst_h = _lst_hours(longitude_deg, dt)

    results: List[Dict[str, float]] = []
    for star in load_star_catalog():
        horiz = _equatorial_to_horizontal(
            ra_hours=star.ra_hours,
            dec_deg=star.dec_deg,
            latitude_deg=latitude_deg,
            lst_hours=lst_h,
        )
        # No filtrar por altitud por defecto (minimum_altitude_deg=-90)
        if horiz["altitude_deg"] >= minimum_altitude_deg:
            result_item: Dict[str, float] = {
                "name": star.name,
                "magnitude": star.magnitude,
                "altitude_deg": horiz["altitude_deg"],
                "azimuth_deg": horiz["azimuth_deg"],
            }
            # Campos opcionales si existen
            if star.distance_ly is not None:
                result_item["distance_ly"] = star.distance_ly
            if star.color_temp_K is not None:
                result_item["color_temp_K"] = star.color_temp_K
            if star.bv is not None:
                result_item["bv"] = star.bv
            if star.rgb_hex is not None:
                result_item["rgb_hex"] = star.rgb_hex
            if star.aliases is not None:
                result_item["aliases"] = star.aliases
            if star.ids is not None:
                result_item["ids"] = star.ids

            results.append(result_item)

    # Filtrar por magnitud máxima si se solicita
    if max_magnitude is not None:
        results = [r for r in results if r["magnitude"] <= max_magnitude]

    # Ordenar por magnitud (más brillante primero) por defecto
    if sort_by_magnitude:
        results.sort(key=lambda x: x["magnitude"])  # menor magnitud = más brillante
    else:
        results.sort(key=lambda x: x["altitude_deg"], reverse=True)

    if limit is not None and limit > 0:
        results = results[:limit]

    return results



def compute_visible_stars(lat: float, lon: float, date_iso: Optional[str]) -> List[Dict[str, float]]:
    """
    Calcula altitud y acimut usando Skyfield para las estrellas del catálogo.
    Devuelve solo estrellas con altitud > 0°.

    Parámetros:
    - lat: Latitud del observador (grados; sur negativo)
    - lon: Longitud del observador (grados; oeste negativo)
    - date_iso: Fecha/hora en ISO 8601 (UTC). Si None o vacío, usa ahora (UTC)

    Retorna: Lista de dicts {name, magnitude, altitude_deg, azimuth_deg}
    """
    dt_utc = _parse_iso_datetime_utc(date_iso)
    ts = load.timescale()
    t = ts.from_datetime(dt_utc)

    observer = wgs84.latlon(latitude_degrees=float(lat), longitude_degrees=float(lon))

    visible: List[Dict[str, float]] = []
    for star in load_star_catalog():
        sf_star = Star(ra_hours=star.ra_hours, dec_degrees=star.dec_deg)
        astrometric = observer.at(t).observe(sf_star).apparent()
        alt, az, _distance = astrometric.altaz()
        alt_deg = float(alt.degrees)
        # No filtrar por altitud aquí; el cliente decide si mostrar > 0°
        item: Dict[str, float] = {
            "name": star.name,
            "magnitude": star.magnitude,
            "altitude_deg": alt_deg,
            "azimuth_deg": float(az.degrees) % 360.0,
        }
        # Campos opcionales si existen
        if star.distance_ly is not None:
            item["distance_ly"] = star.distance_ly
        if star.color_temp_K is not None:
            item["color_temp_K"] = star.color_temp_K
        if star.bv is not None:
            item["bv"] = star.bv
        if star.rgb_hex is not None:
            item["rgb_hex"] = star.rgb_hex
        if star.aliases is not None:
            item["aliases"] = star.aliases
        if star.ids is not None:
            item["ids"] = star.ids

        visible.append(item)

    return visible


# --------------------------- Constellation helpers ----------------------------

def get_constellation_frame(
    *,
    constellation_name: str,
    latitude_deg: float,
    longitude_deg: float,
    when_iso_utc: Optional[str] = None,
) -> Dict[str, object]:
    """
    Devuelve las posiciones de las estrellas principales de una constelación y
    las aristas para dibujarla.

    Respuesta:
    {
      "name": str,
      "at": ISO_UTC,
      "stars": [{ name, magnitude, altitude_deg, azimuth_deg }],
      "edges": [[fromName, toName], ...]
    }
    """
    dt = _parse_iso_datetime_utc(when_iso_utc)
    ts = load.timescale()
    t = ts.from_datetime(dt)

    definition = get_constellation_definition(constellation_name)
    star_names: List[str] = definition["stars"]  # type: ignore[index]
    edges: List[List[str]] = definition["edges"]  # type: ignore[index]

    observer = wgs84.latlon(latitude_degrees=float(latitude_deg), longitude_degrees=float(longitude_deg))

    # Index catálogo por nombre para acceso rápido
    catalog_index: Dict[str, CatalogStar] = {s.name: s for s in load_star_catalog()}

    positioned: List[Dict[str, float]] = []
    for name in star_names:
        cat_star = catalog_index.get(name)
        if not cat_star:
            # Si una estrella no existe en el catálogo, se omite
            continue
        sf_star = Star(ra_hours=cat_star.ra_hours, dec_degrees=cat_star.dec_deg)
        alt, az, _ = observer.at(t).observe(sf_star).apparent().altaz()
        positioned.append(
            {
                "name": name,
                "magnitude": cat_star.magnitude,
                "altitude_deg": float(alt.degrees),
                "azimuth_deg": float(az.degrees) % 360.0,
            }
        )

    return {
        "name": constellation_name,
        "at": _format_time_iso_z(dt),
        "stars": positioned,
        "edges": edges,
    }


def get_circumpolar_constellations() -> List[str]:
    """Devuelve la lista de constelaciones circumpolares configuradas."""
    return list_constellations()

