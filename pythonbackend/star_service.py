from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional


@dataclass
class CatalogStar:
    name: str
    ra_hours: float  # Ascensión recta en horas
    dec_deg: float   # Declinación en grados
    magnitude: float


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


def get_visible_stars(
    *,
    latitude_deg: float,
    longitude_deg: float,
    when_iso_utc: Optional[str] = None,
    minimum_altitude_deg: float = 0.0,
    limit: Optional[int] = None,
    sort_by_magnitude: bool = True,
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
        if horiz["altitude_deg"] >= minimum_altitude_deg:
            results.append(
                {
                    "name": star.name,
                    "magnitude": star.magnitude,
                    "altitude_deg": horiz["altitude_deg"],
                    "azimuth_deg": horiz["azimuth_deg"],
                }
            )

    if sort_by_magnitude:
        results.sort(key=lambda x: x["magnitude"])  # menor magnitud = más brillante
    else:
        results.sort(key=lambda x: x["altitude_deg"], reverse=True)

    if limit is not None and limit > 0:
        results = results[:limit]

    return results


