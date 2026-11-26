"""
Rerouting Service.

Coordinates rerouting triggered by off-route GPS deviation or traffic optimization,
logs session updates, and persists updated metrics in PostgreSQL/PostGIS.
"""

import logging
from typing import Optional

from sqlalchemy.orm import Session

from app.database.spatial import point_wkt
from app.models.entities import NavigationSession
from app.schemas.geo import AlternativeRoutesResponse, CoordinatePoint
from app.services.alternative_route_service import generate_alternative_routes

logger = logging.getLogger("smartnav.rerouting")


async def perform_reroute(
    db: Session,
    session: Optional[NavigationSession],
    current_lat: float,
    current_lng: float,
    dest_lat: float,
    dest_lng: float,
    profile: str = "driving",
    avoid_tolls: bool = False,
    reason: str = "deviation",
) -> AlternativeRoutesResponse:
    alt_response = await generate_alternative_routes(
        origin=CoordinatePoint(lat=current_lat, lng=current_lng),
        destination=CoordinatePoint(lat=dest_lat, lng=dest_lng),
        profile=profile,
        max_routes=5,
        avoid_tolls=avoid_tolls,
        preference="fastest",
    )

    if session is not None and alt_response.routes:
        best = alt_response.routes[0]
        session.reroute_count += 1
        session.last_lat = current_lat
        session.last_lng = current_lng
        session.last_point = point_wkt(current_lat, current_lng)
        session.remaining_distance_meters = best.distance_meters
        db.commit()
        logger.info(
            "Session %d rerouted (reason=%s, count=%d, new_distance=%.1fm)",
            session.id,
            reason,
            session.reroute_count,
            best.distance_meters,
        )

    return alt_response
