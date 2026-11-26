from typing import Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.core.security import get_optional_user
from app.database.session import get_db
from app.database.spatial import point_wkt
from app.models.entities import RouteHistory, User
from app.schemas.geo import (
    AlternativeRoutesRequest,
    AlternativeRoutesResponse,
    RouteRequest,
    RouteResponse,
    RouteTrafficSummary,
)
from app.services.alternative_route_service import generate_alternative_routes
from app.services.routing import fetch_osrm_routes
from app.services.traffic_service import get_registered_route, get_route_traffic

router = APIRouter(prefix="/api", tags=["Routing & Traffic"])


@router.post("/routes", response_model=RouteResponse)
async def calculate_routes(
    payload: RouteRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    try:
        routes = await fetch_osrm_routes(
            origin=payload.origin,
            destination=payload.destination,
            profile=payload.profile,
            alternatives=payload.alternatives,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Routing provider returned HTTP {exc.response.status_code}.",
        ) from exc
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Routing service (OSRM) is temporarily unreachable.",
        ) from exc

    if not routes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No road route found between the specified coordinates.",
        )

    if current_user is not None:
        primary = routes[0]
        record = RouteHistory(
            user_id=current_user.id,
            origin_label=payload.origin.label,
            destination_label=payload.destination.label,
            origin_lat=payload.origin.lat,
            origin_lng=payload.origin.lng,
            dest_lat=payload.destination.lat,
            dest_lng=payload.destination.lng,
            origin_point=point_wkt(payload.origin.lat, payload.origin.lng),
            dest_point=point_wkt(payload.destination.lat, payload.destination.lng),
            profile=payload.profile,
            distance_meters=primary.distance_meters,
            duration_seconds=primary.duration_seconds,
        )
        db.add(record)
        db.commit()

    return RouteResponse(provider="OSRM", profile=payload.profile, routes=routes)


@router.post("/routes/alternatives", response_model=AlternativeRoutesResponse)
async def calculate_alternative_routes(
    payload: AlternativeRoutesRequest,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """Generate up to 5 genuinely distinct road routes enriched with live traffic & ETA predictions."""
    try:
        response = await generate_alternative_routes(
            origin=payload.origin,
            destination=payload.destination,
            profile=payload.profile,
            max_routes=payload.max_routes,
            avoid_tolls=payload.avoid_tolls,
            preference=payload.preference,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Routing provider returned HTTP {exc.response.status_code}.",
        ) from exc
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Routing service is temporarily unreachable.",
        ) from exc

    if not response.routes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No valid road routes found between these coordinates.",
        )

    if current_user is not None:
        primary = response.routes[0]
        effective_dur = (
            primary.traffic.traffic_adjusted_duration_seconds
            if primary.traffic.traffic_adjusted_duration_seconds is not None
            else primary.duration_seconds
        )
        record = RouteHistory(
            user_id=current_user.id,
            origin_label=payload.origin.label,
            destination_label=payload.destination.label,
            origin_lat=payload.origin.lat,
            origin_lng=payload.origin.lng,
            dest_lat=payload.destination.lat,
            dest_lng=payload.destination.lng,
            origin_point=point_wkt(payload.origin.lat, payload.origin.lng),
            dest_point=point_wkt(payload.destination.lat, payload.destination.lng),
            profile=payload.profile,
            distance_meters=primary.distance_meters,
            duration_seconds=effective_dur,
        )
        db.add(record)
        db.commit()

    return response


@router.get("/routes/{route_id}/traffic", response_model=RouteTrafficSummary)
async def get_traffic_for_route(
    route_id: str,
    profile: str = Query(default="driving"),
    force_refresh: bool = Query(default=False),
):
    route = get_registered_route(route_id)
    if not route:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Route ID not found or expired. Recalculate routes first.",
        )
    return await get_route_traffic(route=route, profile=profile, force_refresh=force_refresh)
