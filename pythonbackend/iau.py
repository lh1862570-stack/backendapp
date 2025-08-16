from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Tuple, Optional


def _module_dir() -> Path:
    return Path(__file__).resolve().parent


def _iau_boundaries_path() -> Path:
    return _module_dir() / "iau_boundaries.json"


@lru_cache(maxsize=1)
def load_iau_boundaries() -> Dict[str, List[List[Tuple[float, float]]]]:
    """
    Carga límites de constelaciones IAU desde un JSON con formato:
    {
      "Ursa Major": [ [ [ra_deg, dec_deg], ... ], ... ],
      ...
    }
    Cada constelación puede tener múltiples polígonos (lista de listas de puntos).
    """
    path = _iau_boundaries_path()
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        raw = json.load(f)
    boundaries: Dict[str, List[List[Tuple[float, float]]]] = {}
    for name, polys in raw.items():
        fixed_polys: List[List[Tuple[float, float]]] = []
        for poly in polys or []:
            pts: List[Tuple[float, float]] = []
            for p in poly or []:
                try:
                    ra = float(p[0]) % 360.0
                    dec = float(p[1])
                    if dec > 90.0:
                        dec = 90.0
                    if dec < -90.0:
                        dec = -90.0
                    pts.append((ra, dec))
                except Exception:
                    continue
            if len(pts) >= 3:
                fixed_polys.append(pts)
        if fixed_polys:
            boundaries[str(name)] = fixed_polys
    return boundaries


def _circular_mean_deg(values_deg: List[float]) -> float:
    import math
    if not values_deg:
        return 0.0
    xs = 0.0
    ys = 0.0
    for d in values_deg:
        r = math.radians(d % 360.0)
        xs += math.cos(r)
        ys += math.sin(r)
    if xs == 0.0 and ys == 0.0:
        return 0.0
    ang = math.degrees(math.atan2(ys, xs)) % 360.0
    return ang


@lru_cache(maxsize=1)
def get_iau_constellation_centroids() -> Dict[str, Tuple[float, float]]:
    """Devuelve centroides (aprox) RA/Dec deg por constelación a partir de sus polígonos.
    RA usa media circular; Dec media aritmética de todos los vértices.
    """
    boundaries = load_iau_boundaries()
    centroids: Dict[str, Tuple[float, float]] = {}
    for name, polys in boundaries.items():
        ra_all: List[float] = []
        dec_all: List[float] = []
        for poly in polys:
            for ra, dec in poly:
                ra_all.append(ra)
                dec_all.append(dec)
        if ra_all and dec_all:
            ra_c = _circular_mean_deg(ra_all)
            dec_c = sum(dec_all) / float(len(dec_all))
            centroids[name] = (ra_c, dec_c)
    return centroids


def _wrap_ra_to_center(values: List[float], center_ra: float) -> List[float]:
    """Ajusta RAs para que estén cerca de center_ra, manejando wrap 0/360."""
    out: List[float] = []
    for ra in values:
        d = (ra - center_ra + 180.0) % 360.0 - 180.0
        out.append(center_ra + d)
    return out


def _point_in_polygon_2d(x: float, y: float, poly: List[Tuple[float, float]]) -> bool:
    """Algoritmo ray casting en 2D. Poly no debe cruzar el polo ni envolver 360°.
    x ~ RA en grados ajustada a ventana local; y ~ Dec.
    """
    inside = False
    n = len(poly)
    if n < 3:
        return False
    for i in range(n):
        x1, y1 = poly[i]
        x2, y2 = poly[(i + 1) % n]
        # Chequear intersección del segmento con el rayo horizontal a la derecha
        intersect = ((y1 > y) != (y2 > y)) and (
            x < (x2 - x1) * (y - y1) / (y2 - y1 + 1e-12) + x1
        )
        if intersect:
            inside = not inside
    return inside


def find_constellation_by_radec(ra_deg: float, dec_deg: float) -> Optional[str]:
    """Devuelve el nombre IAU si el punto cae dentro de algún polígono.
    RA/Dec en grados. Si no hay archivo o no encuentra, retorna None.
    """
    boundaries = load_iau_boundaries()
    if not boundaries:
        return None

    ra = ra_deg % 360.0
    dec = max(-90.0, min(90.0, float(dec_deg)))

    for name, polys in boundaries.items():
        for poly in polys:
            ra_list = [p[0] for p in poly]
            dec_list = [p[1] for p in poly]
            ra_adj = _wrap_ra_to_center(ra_list, ra)
            poly_adj = list(zip(ra_adj, dec_list))
            if _point_in_polygon_2d(ra, dec, poly_adj):
                return name
    return None


