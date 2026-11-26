from datetime import datetime, timezone
from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.security import get_optional_user
from app.database.session import get_db
from app.database.spatial import point_wkt
from app.models.entities import NavigationBreadcrumb, NavigationSession, User
from app.schemas.geo import AlternativeRoutesResponse
from app.schemas.navigation import (
    CompareRoutesRequest,
    CompareRoutesResponse,
    NavigationRerouteRequest,
    NavigationStartRequest,
    NavigationStartResponse,
    NavigationStatusResponse,
    NavigationStopRequest,
    NavigationUpdateRequest,
    OptimizeRouteRequest,
    OptimizeRouteResponse,
    TrafficMonitorUpdateRequest,
    TrafficMonitorUpdateResponse,
    TrafficSummaryResponse,
)
from app.services.alternative_route_service import generate_alternative_routes
from app.services.rerouting_service import perform_reroute
from app.services.route_optimizer import evaluate_route_switch
from app.services.traffic_monitor_service import (
    check_navigation_traffic,
    clear_session_monitor_state,
    get_session_monitor_state,
)

router = APIRouter(prefix="/api/navigation", tags=["Live Navigation & Traffic Optimization"])


def _get_authorized_session(db: Session, session_id: int, current_user: Optional[User]) -> NavigationSession:
    session = db.get(NavigationSession, session_id)
    if not session:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Navigation session not found.")
    if session.user_id is not None:
        if current_user is None or session.user_id != current_user.id:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied to session.")
    return session


@router.post("/start", response_model=NavigationStartResponse, status_code=status.HTTP_201_CREATED)
def start_navigation(
    payload: NavigationStartRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    session = NavigationSession(
        user_id=current_user.id if current_user else None,
        origin_label=payload.origin_label,
        destination_label=payload.destination_label,
        origin_lat=payload.origin_lat,
        origin_lng=payload.origin_lng,
        dest_lat=payload.dest_lat,
        dest_lng=payload.dest_lng,
        last_lat=payload.origin_lat,
        last_lng=payload.origin_lng,
        last_point=point_wkt(payload.origin_lat, payload.origin_lng),
        profile=payload.profile,
        route_distance_meters=payload.route_distance_meters,
        route_duration_seconds=payload.route_duration_seconds,
        remaining_distance_meters=payload.route_distance_meters,
        status="active",
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    return NavigationStartResponse(
        session_id=session.id,
        status=session.status,
        started_at=session.started_at,
    )


@router.post("/update")
def update_navigation(
    payload: NavigationUpdateRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    session = _get_authorized_session(db, payload.session_id, current_user)
    if session.status != "active":
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Navigation session is not active.")

    session.last_lat = payload.lat
    session.last_lng = payload.lng
    session.last_point = point_wkt(payload.lat, payload.lng)
    if payload.remaining_distance_meters is not None:
        session.remaining_distance_meters = payload.remaining_distance_meters

    breadcrumb = NavigationBreadcrumb(
        session_id=session.id,
        lat=payload.lat,
        lng=payload.lng,
        point=point_wkt(payload.lat, payload.lng),
        accuracy_meters=payload.accuracy_meters,
        speed_mps=payload.speed_mps,
        heading_deg=payload.heading_deg,
    )
    db.add(breadcrumb)
    db.commit()

    return {"status": "updated", "session_id": session.id}


@router.post("/reroute", response_model=AlternativeRoutesResponse)
async def reroute_navigation(
    payload: NavigationRerouteRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    session = None
    if payload.session_id is not None:
        session = _get_authorized_session(db, payload.session_id, current_user)

    try:
        return await perform_reroute(
            db=db,
            session=session,
            current_lat=payload.current_lat,
            current_lng=payload.current_lng,
            dest_lat=payload.dest_lat,
            dest_lng=payload.dest_lng,
            profile=payload.profile,
            avoid_tolls=payload.avoid_tolls,
            reason=payload.reason,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Routing provider unavailable during reroute.",
        ) from exc


@router.post("/traffic/update", response_model=TrafficMonitorUpdateResponse)
async def traffic_monitor_update(
    payload: TrafficMonitorUpdateRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    if payload.session_id is not None:
        _get_authorized_session(db, payload.session_id, current_user)

    try:
        return await check_navigation_traffic(
            session_id=payload.session_id,
            current_lat=payload.current_lat,
            current_lng=payload.current_lng,
            dest_lat=payload.dest_lat,
            dest_lng=payload.dest_lng,
            profile=payload.profile,
            current_route_id=payload.current_route_id,
            current_remaining_duration_seconds=payload.current_remaining_duration_seconds,
            avoid_tolls=payload.avoid_tolls,
            monitor_interval_seconds=payload.monitor_interval_seconds,
            force_refresh=payload.force_refresh,
        )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Traffic monitoring update failed due to upstream routing error.",
        ) from exc


@router.post("/compare-routes", response_model=CompareRoutesResponse)
async def compare_routes(payload: CompareRoutesRequest):
    try:
        alt = await generate_alternative_routes(
            origin=payload.origin,
            destination=payload.destination,
            profile=payload.profile,
            max_routes=5,
            avoid_tolls=payload.avoid_tolls,
            preference=payload.preference,
        )
    except httpx.HTTPError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Unable to compare routes due to upstream provider error.",
        ) from exc

    fastest = next((r.route_id for r in alt.routes if r.is_fastest), alt.routes[0].route_id if alt.routes else None)
    return CompareRoutesResponse(
        traffic_available=alt.traffic_available,
        traffic_provider=alt.traffic_provider,
        selected_route_id=payload.selected_route_id or fastest,
        fastest_route_id=fastest,
        routes=alt.routes,
    )


@router.post("/optimize-route", response_model=OptimizeRouteResponse)
async def optimize_route(
    payload: OptimizeRouteRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    if payload.session_id is not None:
        _get_authorized_session(db, payload.session_id, current_user)

    candidates = payload.candidate_routes
    if not candidates:
        try:
            monitor_res = await check_navigation_traffic(
                session_id=payload.session_id,
                current_lat=payload.current_lat,
                current_lng=payload.current_lng,
                dest_lat=payload.dest_lat,
                dest_lng=payload.dest_lng,
                profile=payload.profile,
                current_route_id=payload.current_route_id,
                current_remaining_duration_seconds=payload.current_route_remaining_seconds,
                avoid_tolls=payload.preferences.avoid_tolls,
                monitor_interval_seconds=payload.preferences.monitor_interval_seconds,
                force_refresh=True,
            )
            candidates = monitor_res.routes
        except httpx.HTTPError as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Route optimization failed because routing provider is unreachable.",
            ) from exc

    return evaluate_route_switch(
        candidate_routes=candidates,
        current_route_id=payload.current_route_id,
        current_route_remaining_seconds=payload.current_route_remaining_seconds,
        current_route_has_closure=payload.current_route_has_closure,
        last_reroute_timestamp_ms=payload.last_reroute_timestamp_ms,
        preferences=payload.preferences,
    )


@router.get("/status", response_model=NavigationStatusResponse)
def navigation_status(
    session_id: int = Query(..., ge=1),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    session = _get_authorized_session(db, session_id, current_user)
    state = get_session_monitor_state(session_id)
    return NavigationStatusResponse(
        session_id=session.id,
        status=session.status,
        profile=session.profile,
        reroute_count=session.reroute_count,
        remaining_distance_meters=session.remaining_distance_meters,
        last_lat=session.last_lat,
        last_lng=session.last_lng,
        started_at=session.started_at,
        ended_at=session.ended_at,
        last_traffic_check_iso=state.last_checked_iso if state else None,
        traffic_available=state.traffic_available if state else False,
        active_route_id=state.active_route_id if state else None,
    )


@router.get("/traffic-summary", response_model=TrafficSummaryResponse)
def navigation_traffic_summary(
    session_id: int = Query(..., ge=1),
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    _get_authorized_session(db, session_id, current_user)
    state = get_session_monitor_state(session_id)
    if not state:
        return TrafficSummaryResponse(
            session_id=session_id,
            traffic_available=False,
            traffic_provider="none",
            alternatives_count=0,
            routes=[],
        )

    active = next((r for r in state.cached_routes if r.route_id == state.active_route_id), None)
    if active is None and state.cached_routes:
        active = state.cached_routes[0]

    return TrafficSummaryResponse(
        session_id=session_id,
        traffic_available=state.traffic_available,
        traffic_provider=state.traffic_provider,
        last_updated_iso=state.last_checked_iso,
        active_route_traffic=active.traffic if active else None,
        alternatives_count=len(state.cached_routes),
        routes=state.cached_routes,
    )


@router.post("/stop")
def stop_navigation(
    payload: NavigationStopRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    session = _get_authorized_session(db, payload.session_id, current_user)
    session.status = payload.status
    session.ended_at = datetime.now(timezone.utc)
    db.commit()
    clear_session_monitor_state(session.id)
    return {"status": session.status, "session_id": session.id, "ended_at": session.ended_at}
