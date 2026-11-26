# SmartNav AI — Full-Stack GPS Navigation Platform

SmartNav AI is a responsive, production-oriented GPS navigation web application built with **React + Vite + Tailwind CSS + Leaflet**, **FastAPI + Python + Pydantic**, **PostgreSQL + PostGIS + SQLAlchemy + Alembic**, and **OpenStreetMap** services (**Nominatim**, **OSRM**, and **Overpass API**).

## Implemented Features

- **Real Mobile & Desktop GPS Tracking** (`frontend/src/hooks/useGeolocation.js`):
  - Native Browser Geolocation API (`getCurrentPosition`, `watchPosition`, `clearWatch`) with `enableHighAccuracy: true`.
  - Live accuracy circle (meters), speed (km/h), directional heading arrow, start/stop tracking controls, single-watcher guard, and cleanup on unmount.
  - Explicit handling for permission denial, GPS unavailable, timeout, and insecure HTTP context on mobile.
  - Zero IP-based or hardcoded fake GPS coordinates.
- **Interactive Leaflet Map** (`frontend/src/components/MapView.jsx`):
  - Light, Dark, and Standard OpenStreetMap tile themes, smooth `flyTo` / `fitBounds`, clickable alternative route polylines, origin/destination/nearby pins, and zoom controls.
- **Location Search & Geocoding** (`GET /api/search`):
  - Debounced autocomplete powered by Nominatim with polite rate limiting, caching, "Use Current GPS Location", origin/destination swap, and error handling.
- **Multi-Route Alternatives & Live Traffic Prediction** (`POST /api/routes/alternatives`):
  - Generates up to 5 genuinely distinct road routes via TomTom/OSRM + lateral corridor waypoints, filtering out duplicate geometries (never fabricating routes).
  - Integrates TomTom Routing & Traffic APIs on the backend (`TOMTOM_API_KEY` environment variable) for congestion levels (`GREEN`, `ORANGE`, `RED`, `DARK RED`), road-segment colors, delays, incidents, and road closures; explicitly displays `"Live traffic unavailable"` when live data is unavailable and keeps baseline `"Predicted traffic"` ETAs separately labeled.
  - Interactive Route Comparison Dashboard (`RouteComparisonPanel.jsx`) sorted by estimated travel time with `FASTEST` badges, preferences (`Fastest`/`Shortest`, `Avoid Tolls`, `Auto-Reroute`), and configurable thresholds.
- **Dynamic Traffic Monitoring & Automatic Fastest-Route Optimization** (`POST /api/navigation/traffic/update`, `POST /api/navigation/optimize-route`):
  - Background traffic polling during active navigation (default 45s interval), sudden congestion & road closure detection, anti-oscillation cooldowns (default 120s), minimum saving thresholds (default 5 min & 10%), and smart switch/continue notifications (`TrafficNotificationBanner.jsx`).
- **Live Navigation & Automatic Rerouting**:
  - Real-time route progress, remaining distance, dynamic ETA, off-route deviation hysteresis (2 consecutive fixes > 65 m off-route with <= 60 m GPS accuracy and 12s cooldown), throttled backend telemetry sync, and automatic OSRM rerouting.
- **Voice Navigation** (`frontend/src/hooks/useVoiceNavigation.js`):
  - Web Speech API (`SpeechSynthesis`) distance-triggered turn announcements with deduplication, mute/unmute toggle, and graceful fallback when unsupported.
- **Nearby Places Discovery** (`GET /api/places/nearby`):
  - Overpass API integration for **Restaurants, Hospitals, Petrol Stations, ATMs, Hotels, Shopping Centres, and Parking Areas**.
- **Authentication & PostgreSQL/PostGIS Persistence**:
  - `bcrypt` password hashing, JWT authentication, saved favorites, route history, and navigation session tracking with Alembic PostGIS migrations.

## Project Structure

```text
smartnav-ai/
  frontend/
    src/
      components/   # MapView, SearchPanel, NavigationHUD, NearbyPlacesBar, GpsStatusBadge, AuthModal, ProfileDrawer
      hooks/        # useGeolocation, useVoiceNavigation
      services/     # api.js
      context/      # AuthContext.jsx
      utils/        # geo.js
      App.jsx
      main.jsx
    package.json
  backend/
    app/
      routes/       # auth, search, routes_api, places, navigation, user_data
      models/       # SQLAlchemy + PostGIS entities
      schemas/      # Pydantic v2 request/response schemas
      services/     # geocoding (Nominatim), routing (OSRM), places (Overpass)
      algorithms/   # Educational Dijkstra & A*
      database/     # session.py & dialect-aware PostGIS spatial.py
      core/         # config.py, security.py, logging_config.py
      main.py
    alembic/        # PostgreSQL + PostGIS migrations
    requirements.txt
  docs/
    architecture.md
    setup.md
    api_documentation.md
  tests/
    backend/        # Pytest suite (auth, DB, search, routing, deviation, algorithms, nearby)
    frontend/       # Vitest suite (GPS permissions/errors/updates, geo math, voice synthesis)
  docker-compose.yml
  render.yaml
  .env.example
```

## Running Tests

### Backend Tests (Pytest)
```bash
cd smartnav-ai
backend/.venv/Scripts/python -m pytest tests/backend -v
```

### Frontend Tests (Vitest) & Production Build
```bash
cd smartnav-ai/frontend
npm test
npm run build
```

## Documentation
- [Architecture Overview](docs/architecture.md)
- [Setup, Android HTTPS Testing & Deployment](docs/setup.md)
- [REST API Documentation](docs/api_documentation.md)
