# SmartNav AI — REST API Documentation

Interactive Swagger UI is automatically served at `/docs` and ReDoc at `/redoc` when the FastAPI server is running.

## Health
- `GET /health` — Returns `{"status": "ok", "service": "SmartNav AI"}`.

## Authentication
- `POST /api/auth/register`
  - Body: `{"full_name": "Alex", "email": "alex@example.com", "password": "password123"}`
  - Response (`201`): `{"access_token": "...", "token_type": "bearer", "user": {...}}`
- `POST /api/auth/login`
  - Body: `{"email": "alex@example.com", "password": "password123"}`
  - Response (`200`): `{"access_token": "...", "token_type": "bearer", "user": {...}}`
- `GET /api/auth/profile` *(Bearer JWT required)*
  - Response (`200`): User profile object.

## Geocoding & Search
- `GET /api/search?q=<query>&lat=<optional>&lng=<optional>`
  - Queries Nominatim (rate-limited to 1 req/s, cached 5 minutes).
  - Validates coordinates (`-90 <= lat <= 90`, `-180 <= lng <= 180`).

## Routing & Multi-Route Traffic
- `POST /api/routes` *(Optional Bearer JWT; saves route history when authenticated)*
  - Body:
    ```json
    {
      "origin": {"lat": 37.7749, "lng": -122.4194, "label": "Origin"},
      "destination": {"lat": 37.7849, "lng": -122.4094, "label": "Destination"},
      "profile": "driving",
      "alternatives": true
    }
    ```
  - Profiles: `driving`, `cycling`, `walking`.
  - Response (`200`): OSRM routes with road distance (meters), duration (seconds), `[lat, lng]` polyline geometry, and turn-by-turn steps.
- `POST /api/routes/alternatives` *(Optional Bearer JWT)*
  - Generates up to 5 genuinely distinct valid road routes using native provider alternatives + perpendicular corridor waypoints with geometry deduplication, enriched with TomTom live traffic (when `TOMTOM_API_KEY` is configured on backend) or `"Live traffic unavailable"` + baseline `"Predicted traffic"` ETA.
- `GET /api/routes/{route_id}/traffic?profile=driving&force_refresh=false`
  - Refreshes or returns cached `RouteTrafficSummary` for a registered `route_id`.

## Live Navigation & Dynamic Traffic Optimization
- `POST /api/navigation/start` — Creates a `NavigationSession` record and returns `session_id`.
- `POST /api/navigation/update` — Records GPS breadcrumb (`lat`, `lng`, `accuracy_meters`, `speed_mps`, `heading_deg`, `remaining_distance_meters`).
- `POST /api/navigation/reroute` — Computes fresh distinct routes from current GPS position to destination and increments `reroute_count`.
- `POST /api/navigation/traffic/update` — Throttled periodic traffic monitoring update (default 45s interval), detecting sudden congestion jumps or road closures.
- `POST /api/navigation/compare-routes` — Re-evaluates all candidate routes between origin and destination and identifies the fastest route.
- `POST /api/navigation/optimize-route` — Runs configurable route-switching decision logic (`continue`, `recommend_switch`, or `auto_switch`) respecting cooldowns, minimum time savings (default 5 min & 10%), toll avoidance, and auto-reroute preferences.
- `GET /api/navigation/status?session_id=<id>` — Returns session state and last traffic check status.
- `GET /api/navigation/traffic-summary?session_id=<id>` — Returns current route and alternative route traffic summaries for the session.
- `POST /api/navigation/stop` — Marks session `completed` or `cancelled` with `ended_at` timestamp.

## Nearby Places
- `GET /api/places/nearby?lat=<lat>&lng=<lng>&category=<cat>&radius=<meters>`
  - Supported categories: `restaurant`, `hospital`, `fuel`, `atm`, `hotel`, `shopping`, `parking`.
  - Radius: `200` to `5000` meters.

## Favorites & History *(Bearer JWT required)*
- `GET /api/favorites` — Lists user's saved favorite places.
- `POST /api/favorites` — Saves a favorite place with PostGIS `POINT` geometry.
- `DELETE /api/favorites/{favorite_id}` — Deletes a saved favorite.
- `GET /api/history` — Returns recent `routes` and `navigation_sessions`.
