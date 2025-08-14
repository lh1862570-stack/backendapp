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

#### 7) GET `/constellation-frame`
- **Query**: `name` (req), `lat` (req), `lon` (req), `at` (opt ISO), `min_alt` (opt, def 0)
- **Respuesta**: `{ name, at, below_horizon, center?, stars[], edges[] }`

#### 8) GET `/constellations-frames`
- **Query**: `lat` (req), `lon` (req), `at` (opt ISO),
  `names` (opt lista separada por comas), `min_alt` (opt),
  `include_below_horizon` (opt bool), `fov_center_az_deg`, `fov_center_alt_deg`, `fov_h_deg`, `fov_v_deg` (opcionales para filtrar al FOV), `clip_edges_to_fov` (opt bool)
- **Respuesta**: `{ at, frames: [ { name, below_horizon, center?, stars[], edges[] } ] }`

#### 9) GET `/constellations-visible`
- Igual que `/constellations-frames` pero devuelve solo `{ name, center?, below_horizon }` por constelación.

#### 10) GET `/constellations-screen`
- Proyecta a coordenadas de pantalla usando FOV y resolución.
- **Query**: `lat`, `lon`, `at?`, `min_alt?`, `names?`, `include_below_horizon?`,
  `fov_center_az_deg` (req), `fov_center_alt_deg` (req), `fov_h_deg` (req), `fov_v_deg` (req),
  `width_px` (req), `height_px` (req), `include_offscreen?`, `clip_edges_to_fov?`
- **Respuesta**: `{ at, frames: [ { name, below_horizon, center?, screen_stars: [{ name, magnitude, azimuth_deg, altitude_deg, x_px, y_px }], screen_edges: [[x1,y1,x2,y2]], ... } ] }`

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

#### Ejemplo: consumir `/constellations-screen` y dibujar
```dart
class ScreenStar {
  final String name; final double x, y; final double mag;
  ScreenStar({required this.name, required this.x, required this.y, required this.mag});
  factory ScreenStar.fromJson(Map<String, dynamic> j) => ScreenStar(
    name: j['name'], x: (j['x_px'] as num).toDouble(), y: (j['y_px'] as num).toDouble(), mag: (j['magnitude'] as num).toDouble(),
  );
}

class ScreenFrame {
  final String name; final List<ScreenStar> stars; final List<List<double>> edges;
  ScreenFrame({required this.name, required this.stars, required this.edges});
  factory ScreenFrame.fromJson(Map<String, dynamic> j) => ScreenFrame(
    name: j['name'],
    stars: (j['screen_stars'] as List).map((e) => ScreenStar.fromJson(e)).toList(),
    edges: (j['screen_edges'] as List).map((e) => (e as List).map((n) => (n as num).toDouble()).toList()).toList(),
  );
}

Future<List<ScreenFrame>> fetchConstellationsScreen({
  required double lat, required double lon,
  required double fovAz, required double fovAlt,
  required double fovH, required double fovV,
  required int width, required int height,
  double minAlt = 0.0,
}) async {
  final uri = Uri.parse('$baseUrl/constellations-screen').replace(queryParameters: {
    'lat': '$lat', 'lon': '$lon', 'min_alt': '$minAlt',
    'fov_center_az_deg': '$fovAz', 'fov_center_alt_deg': '$fovAlt',
    'fov_h_deg': '$fovH', 'fov_v_deg': '$fovV',
    'width_px': '$width', 'height_px': '$height',
    'clip_edges_to_fov': 'true',
  });
  final res = await http.get(uri);
  if (res.statusCode != 200) throw Exception('HTTP ${res.statusCode}: ${res.body}');
  final List frames = (jsonDecode(res.body) as Map<String, dynamic>)['frames'];
  return frames.map((e) => ScreenFrame.fromJson(e)).toList();
}

class ScreenPainter extends CustomPainter {
  final List<ScreenFrame> frames;
  ScreenPainter(this.frames);
  @override
  void paint(Canvas c, Size s) {
    for (final f in frames) {
      final line = Paint()..color = Colors.blueAccent..strokeWidth = 2;
      for (final e in f.edges) {
        if (e.length != 4) continue; c.drawLine(Offset(e[0], e[1]), Offset(e[2], e[3]), line);
      }
      final star = Paint()..color = Colors.white;
      for (final st in f.stars) { c.drawCircle(Offset(st.x, st.y), (3 + (2.5 - st.mag).clamp(0, 3)).toDouble(), star); }
    }
  }
  @override bool shouldRepaint(covariant ScreenPainter old) => old.frames != frames;
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


