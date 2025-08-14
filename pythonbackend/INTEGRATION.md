## Guía de integración – Visible Stars API

Esta guía resume todo lo necesario para consumir el backend desde Flutter (Android), iOS o web sin contratiempos.

### Base
- **Base URL**: URL pública del servicio (ej.: `https://tu-servicio.onrender.com`).
- **Auth**: no requiere autenticación.
- **CORS**: habilitado para todos los orígenes.
- **Formato de respuesta**: JSON. Enviar `Accept: application/json` (opcional).
- **Salud**: `GET /health` → `{ "status": "ok" }`.

### Convenciones importantes
- **Coordenadas**: `lat` (grados, sur negativo), `lon` (grados, oeste negativo).
- **Tiempo**: usar ISO 8601 en UTC con sufijo `Z` (ej.: `2025-01-10T03:00:00Z`).
- **Unidades**:
  - `altitude_deg` y `azimuth_deg` en grados.
  - `distance_ly`: años luz; `distance_km`/`distance_au`: km / UA.
  - `magnitude`: escala astronómica (menor = más brillante).
- **Orden y filtros**:
  - Por defecto, las estrellas pueden incluir altitudes negativas (debajo del horizonte). Filtra en el cliente si deseas `altitude_deg > 0`.
  - Usa `limit` y `max_mag` para reducir payload y mejorar rendimiento.

### Endpoints

#### 1) GET `/sky`
- **Query**: `lat` (req), `lon` (req), `date` (opt ISO 8601 UTC)
- **Respuesta**: `VisibleStar[]`
  - `name` (string), `magnitude` (number), `altitude_deg` (number), `azimuth_deg` (number)
  - opcionales: `distance_ly`, `color_temp_K`, `bv`, `rgb_hex`, `aliases`, `ids`

#### 2) GET `/visible-stars`
- **Query**: `lat` (req), `lon` (req), `at` (opt ISO), `limit` (opt int), `max_mag` (opt float)
- **Respuesta**: `VisibleStar[]` (ver esquema arriba)

#### 3) GET `/visible-bodies`
- **Query**: `lat` (req), `lon` (req), `at` (opt ISO)
- **Respuesta**: `VisibleBody[]`
  - `name` (string), `type` (string: planet|moon|sun|...), `altitude_deg` (number), `azimuth_deg` (number)
  - opcionales: `magnitude`, `phase`, `distance_km`, `distance_au`

#### 4) GET `/astronomy-events`
- **Query**: `lat` (req), `lon` (req), `start_datetime` (req ISO), `end_datetime` (req ISO)
- **Respuesta**: `AstronomyEvent[]`
  - `type` (string), `time` (ISO 8601 UTC), `description` (string)

#### 5) GET `/visible-stars-batch`
- **Query**: `lat` (req), `lon` (req), `start` (req ISO), `end` (req ISO), `step_hours` (opt float, def 1.0), `max_mag` (opt), `limit` (opt)
- **Respuesta**: `{ "frames": [ { "at": ISO, "stars": VisibleStar[] } ] }`

#### 6) GET `/visible-bodies-batch`
- **Query**: `lat` (req), `lon` (req), `start` (req ISO), `end` (req ISO), `step_hours` (opt float, def 1.0), `limit` (opt)
- **Respuesta**: `{ "frames": [ { "at": ISO, "bodies": VisibleBody[] } ] }`

### Ejemplos rápidos (cURL)
```bash
curl "https://tu-servicio.onrender.com/health"

curl "https://tu-servicio.onrender.com/sky?lat=19.4326&lon=-99.1332&date=2025-01-10T03:00:00Z"

curl "https://tu-servicio.onrender.com/visible-stars?lat=19.4326&lon=-99.1332&at=2025-01-10T03:00:00Z&max_mag=6&limit=20"

curl "https://tu-servicio.onrender.com/astronomy-events?lat=19.4326&lon=-99.1332&start_datetime=2025-01-10T00:00:00Z&end_datetime=2025-01-11T00:00:00Z"
```

### Ejemplo mínimo en Flutter (Android)

1) `AndroidManifest.xml`:
```xml
<uses-permission android:name="android.permission.INTERNET" />
```

2) `pubspec.yaml`:
```yaml
dependencies:
  http: ^1.2.0
```

3) Código (Dart):
```dart
import 'dart:convert';
import 'package:http/http.dart' as http;

const baseUrl = 'https://tu-servicio.onrender.com';

Future<List<Map<String, dynamic>>> fetchVisibleStars({
  required double lat,
  required double lon,
  String? atIsoUtc,
  int? limit,
  double? maxMag,
}) async {
  final uri = Uri.parse('$baseUrl/visible-stars').replace(queryParameters: {
    'lat': '$lat',
    'lon': '$lon',
    if (atIsoUtc != null) 'at': atIsoUtc,
    if (limit != null) 'limit': '$limit',
    if (maxMag != null) 'max_mag': '$maxMag',
  });
  final res = await http.get(uri, headers: {'Accept': 'application/json'});
  if (res.statusCode != 200) {
    throw Exception('HTTP ${res.statusCode}: ${res.body}');
  }
  return (jsonDecode(res.body) as List).cast<Map<String, dynamic>>();
}
```

### Errores y diagnóstico
- **422 (validation)**: parámetros faltantes o con tipo inválido.
- **400/500**: formato de fecha incorrecto. Use ISO 8601 UTC con `Z` (ej.: `2025-01-10T03:00:00Z`).
- **200 con lista vacía**: algunos endpoints retornan `[]` o `{frames: []}` ante errores internos controlados.
- **Android HTTP claro**: use siempre `https://` (evita restricciones de cleartext).

### Buenas prácticas de rendimiento
- Filtra por `max_mag` y usa `limit` para respuestas más pequeñas.
- En batch, evita `step_hours` demasiado pequeño en ventanas largas.
- Filtra client-side `altitude_deg > 0` si solo quieres objetos sobre el horizonte.

### Versionado
- Versión de la API: `1.0.0` (visible en OpenAPI/Swagger en `/docs`).

### Documentación interactiva
- Swagger UI: `{BASE_URL}/docs`
- ReDoc: `{BASE_URL}/redoc`


