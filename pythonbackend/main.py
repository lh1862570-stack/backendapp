from typing import List, Optional
from fastapi import FastAPI, Query
from pydantic import BaseModel
from star_service import get_visible_stars


app = FastAPI(
    title="Visible Stars API",
    description="Backend con FastAPI para calcular posiciones (alt-az) de estrellas visibles desde una ubicación y fecha/hora dadas",
    version="1.0.0",
)


class VisibleStar(BaseModel):
    name: str
    magnitude: float
    altitude_deg: float
    azimuth_deg: float


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
    min_alt: float = Query(
        0.0, description="Altitud mínima (grados) para considerar una estrella visible (horizonte=0)"
    ),
    limit: Optional[int] = Query(
        None, description="Limitar el número de resultados. Si se omite, devuelve todas las visibles."
    ),
    sort_by_magnitude: bool = Query(
        True, description="Ordenar por magnitud (más brillante primero). Si False, ordena por altitud."
    ),
) -> List[VisibleStar]:
    stars = get_visible_stars(
        latitude_deg=lat,
        longitude_deg=lon,
        when_iso_utc=at,
        minimum_altitude_deg=min_alt,
        limit=limit,
        sort_by_magnitude=sort_by_magnitude,
    )
    # FastAPI/Pydantic realizará la conversión a VisibleStar automáticamente
    return stars


if __name__ == "__main__":
    # Ejecución directa: uvicorn con autoreload para desarrollo
    import uvicorn

    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)


