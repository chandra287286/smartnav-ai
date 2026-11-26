"""
Dynamic Traffic Monitoring Service.

Continuously monitors traffic along the active navigation session at configurable
intervals (default 45s), detects sudden congestion spikes or road closures, and caches
latest snapshots to avoid excessive provider API calls.
"""

import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.schemas.geo import AlternativeRouteOption, CoordinatePoint
from app.schemas.navigation import TrafficMonitorUpdateResponse
from app.services.alternative_route_service import generate_alternative_routes

logger = logging.getLogger("smartnav.traffic_monitor")

SEVERITY_ORDER = {"unknown": 0, "low": 1, "moderate": 2, "heavy": 3, "severe": 4}


@dataclass
class SessionMonitorState:
    session_id: int
    last_checked_mono: float = 0.0
    last_checked_iso: Optional[str] = None
    active_route_id: Optional[str] = None
    last_eta_seconds: Optional[float] = None
    last_congestion: str = "unknown"
    traffic_available: bool = False
    traffic_provider: str = "none"
    cached_routes: List[AlternativeRouteOption] = field(default_factory=list)


_session_states: Dict[int, SessionMonitorState] = {}


def get_session_monitor_state(session_id: int) -> Optional[SessionMonitorState]:
    return _session_states.get(session_id)


def clear_session_monitor_state(session_id: int) -> None:
    _session_states.pop(session_id, None)


def _route_effective_eta(route: AlternativeRouteOption) -> float:
    if route.traffic.traffic_adjusted_duration_seconds is not None:
        return route.traffic.traffic_adjusted_duration_seconds
    return route.duration_seconds


async def check_navigation_traffic(
    session_id: Optional[int],
    current_lat: float,
    current_lng: float,
    dest_lat: float,
    dest_lng: float,
    profile: str = "driving",
    current_route_id: Optional[str] = None,
    current_remaining_duration_seconds: Optional[float] = None,
    avoid_tolls: bool = False,
    monitor_interval_seconds: int = 45,
    force_refresh: bool = False,
) -> TrafficMonitorUpdateResponse:
    now_mono = time.monotonic()
    now_iso = datetime.now(timezone.utc).isoformat()

    state = _session_states.get(session_id) if session_id is not None else None
    if state is not None and not force_refresh:
        elapsed = now_mono - state.last_checked_mono
        if elapsed < monitor_interval_seconds and state.cached_routes:
            return TrafficMonitorUpdateResponse(
                session_id=session_id,
                refreshed=False,
                skipped_reason=f"Throttled: next refresh in {int(monitor_interval_seconds - elapsed)}s",
                traffic_available=state.traffic_available,
                traffic_provider=state.traffic_provider,
                checked_at_iso=state.last_checked_iso or now_iso,
                current_route_eta_seconds=state.last_eta_seconds,
                sudden_congestion_detected=False,
                road_closure_detected=any(r.traffic.has_road_closure for r in state.cached_routes),
                routes=state.cached_routes,
            )

    alt_response = await generate_alternative_routes(
        origin=CoordinatePoint(lat=current_lat, lng=current_lng),
        destination=CoordinatePoint(lat=dest_lat, lng=dest_lng),
        profile=profile,
        max_routes=5,
        avoid_tolls=avoid_tolls,
        preference="fastest",
    )

    routes = alt_response.routes
    active_route = next((r for r in routes if r.route_id == current_route_id), None)
    if active_route is None and routes:
        active_route = routes[0]

    new_eta = (
        _route_effective_eta(active_route)
        if active_route
        else current_remaining_duration_seconds
    )
    new_congestion = active_route.traffic.congestion_level if active_route else "unknown"
    road_closure_detected = bool(
        active_route and active_route.traffic.has_road_closure
    ) or any(r.traffic.has_road_closure for r in routes)

    sudden_congestion = False
    if state is not None:
        prev_sev = SEVERITY_ORDER.get(state.last_congestion, 0)
        new_sev = SEVERITY_ORDER.get(new_congestion, 0)
        if new_sev >= 3 and new_sev > prev_sev:
            sudden_congestion = True
        elif (
            state.last_eta_seconds
            and new_eta
            and state.last_eta_seconds > 0
            and (new_eta - state.last_eta_seconds) / state.last_eta_seconds >= 0.25
        ):
            sudden_congestion = True
    elif new_congestion in ("heavy", "severe"):
        sudden_congestion = True

    if session_id is not None:
        _session_states[session_id] = SessionMonitorState(
            session_id=session_id,
            last_checked_mono=now_mono,
            last_checked_iso=now_iso,
            active_route_id=current_route_id or (active_route.route_id if active_route else None),
            last_eta_seconds=new_eta,
            last_congestion=new_congestion,
            traffic_available=alt_response.traffic_available,
            traffic_provider=alt_response.traffic_provider,
            cached_routes=routes,
        )

    logger.info(
        "Traffic monitor session=%s refreshed routes=%d traffic_available=%s congestion=%s",
        session_id,
        len(routes),
        alt_response.traffic_available,
        new_congestion,
    )

    return TrafficMonitorUpdateResponse(
        session_id=session_id,
        refreshed=True,
        traffic_available=alt_response.traffic_available,
        traffic_provider=alt_response.traffic_provider,
        checked_at_iso=now_iso,
        current_route_eta_seconds=new_eta,
        sudden_congestion_detected=sudden_congestion,
        road_closure_detected=road_closure_detected,
        routes=routes,
    )
