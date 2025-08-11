## Visible Stars API (FastAPI)

Backend de ejemplo con FastAPI para calcular posiciones (altitud y azimut) de estrellas visibles desde una ubicación y fecha/hora dadas.

### Requisitos
- Python 3.10+

### Instalación
```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

### Ejecución
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Documentación interactiva:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Uso rápido
Endpoint `GET /visible-stars`
- `lat` (float): latitud en grados (sur negativo)
- `lon` (float): longitud en grados (oeste negativo)
- `at` (str, opcional): fecha/hora ISO 8601 (UTC), ej: `2025-01-10T03:00:00Z`
- `min_alt` (float, opcional): altitud mínima en grados (default 0.0)
- `limit` (int, opcional): máximo de resultados
- `sort_by_magnitude` (bool, opcional): true por brillo; false por altitud

Ejemplo:
```
GET http://localhost:8000/visible-stars?lat=19.4326&lon=-99.1332&at=2025-01-10T03:00:00Z&min_alt=10&limit=5
```

### Notas
- El catálogo `star_catalog.json` incluye un conjunto pequeño de estrellas brillantes con RA (horas) y Dec (grados).
- Para mayor precisión científica considere `astropy` o `skyfield`.


