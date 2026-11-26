# SmartNav AI — System Architecture

## Overview

SmartNav AI is a full-stack GPS navigation platform inspired by Google Maps Navigator. It pairs a React + Leaflet responsive frontend with a FastAPI + PostgreSQL/PostGIS backend and integrates real OpenStreetMap ecosystem services.

```
[Mobile / Desktop Browser]
  ├── Geolocation API (getCurrentPosition / watchPosition / clearWatch)
  ├── Web Speech API (SpeechSynthesis turn-by-turn announcements)
  └── React + Tailwind + React-Leaflet UI
           │  HTTPS / JSON REST + JWT Bearer
           ▼
[FastAPI Backend (backend/app/main.py)]
  ├── /api/auth/*        ──► bcrypt + PyJWT + Users table
  ├── /api/search        ──► Nominatim (rate-limited + cached)
  ├── /api/routes        ──► OSRM (road geometry, steps, alternatives)
  ├── /api/places/nearby ──► Overpass API (7 OSM categories + distance sort)
  ├── /api/navigation/*  ──► Session lifecycle, GPS breadcrumbs, rerouting
  └── /api/favorites & /api/history ──► PostgreSQL + PostGIS
```

## Key Architectural Decisions

1. **Real Mobile GPS Only**:
   - Implemented in `frontend/src/hooks/useGeolocation.js`.
   - Uses `navigator.geolocation.getCurrentPosition()`, `watchPosition()`, and `clearWatch()` with `enableHighAccuracy: true`.
   - Checks `window.isSecureContext` and `navigator.permissions.query({ name: 'geolocation' })`.
   - No IP geolocation fallback or simulated/hardcoded coordinates are ever used for live GPS.

2. **Road Routing vs. Educational Algorithms**:
   - **Production Routing** (`backend/app/services/routing.py`): Queries OSRM (`/route/v1/{profile}`) for road-network geometry, distance, duration, alternative routes, and turn-by-turn maneuver steps.
   - **Educational Algorithms** (`backend/app/algorithms/dijkstra.py`, `astar.py`): Standalone weighted graph shortest-path implementations using Haversine admissible heuristics for A*, clearly separated from OSRM production routing.

3. **Route Deviation & Rerouting Hysteresis**:
   - Computed continuously in `frontend/src/App.jsx` via `computeRouteProgress` (`frontend/src/utils/geo.js`).
   - Ignores low-accuracy fixes (`accuracy > 60 m`).
   - Requires 2 consecutive fixes > 65 meters off the active polyline and enforces a 12-second cooldown before invoking `POST /api/navigation/reroute`.

4. **PostgreSQL + PostGIS Spatial Persistence**:
   - Defined in `backend/app/models/entities.py` and `backend/app/database/spatial.py`.
   - Uses `PointGeography` (`GEOGRAPHY(POINT, 4326)` with GIST spatial indexing in PostgreSQL/PostGIS) and Alembic migrations in `backend/alembic/versions/`.
   - Supports SQLite WKT storage transparently for zero-dependency local automated testing.
