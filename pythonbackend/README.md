## Visible Stars API (FastAPI + Skyfield)

Backend con FastAPI para calcular posiciones (altitud y acimut) de estrellas visibles desde una ubicación y fecha/hora dadas. Usa Skyfield para el endpoint `/sky` y un cálculo interno para `/visible-stars`.

### Requisitos
- Python 3.10+

### Instalación de dependencias
Opción A (recomendada, usa `requirements.txt`):
```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
```

Opción B (instalación directa):
```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install fastapi uvicorn[standard] skyfield
```

### Ejecutar el servidor
```bash
uvicorn main:app --reload --host 0.0.0.0 --port 8000
```

Abrir documentación:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

### Probar endpoints
1) Navegador (ejemplos):
- `http://localhost:8000/sky?lat=19.4326&lon=-99.1332&date=2025-01-10T03:00:00Z`
- `http://localhost:8000/visible-stars?lat=19.4326&lon=-99.1332&at=2025-01-10T03:00:00Z&min_alt=10&limit=5`

2) curl (PowerShell/CMD):
```bash
curl "http://localhost:8000/sky?lat=19.4326&lon=-99.1332&date=2025-01-10T03:00:00Z"
```

```bash
curl "http://localhost:8000/visible-stars?lat=19.4326&lon=-99.1332&at=2025-01-10T03:00:00Z&min_alt=10&limit=5"
```

### Parámetros
- `lat` y `lon`: grados decimales; sur/oeste negativos.
- `date`/`at`: ISO 8601 UTC (ej. `2025-01-10T03:00:00Z`). Si se omite, usa la hora actual UTC.
- `/visible-stars` admite además `min_alt`, `limit`, `sort_by_magnitude`.

### Notas
- El catálogo `star_catalog.json` contiene estrellas brillantes con `name`, `ra`, `dec`, `mag` (o claves equivalentes).
- Para mayor precisión, el endpoint `/sky` usa Skyfield.


