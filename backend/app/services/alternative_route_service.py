"""
Multi-Route Alternative Generator & Route Diversity Filter.

Generates up to 5 genuinely distinct, valid road routes from origin to destination:
1. Uses provider native alternatives (TomTom maxAlternatives / OSRM alternatives).
2. When fewer than 5 distinct routes exist, probes perpendicular lateral corridor
   waypoints (via real routing engine queries, never fabricated coordinates).
3. Filters out duplicate or nearly identical routes by comparing sampled polyline
   geometry distance and corridor overlap.
4. Enriches every valid route with live traffic (if configured) and predicted ETA.
"""

import asyncio
import hashlib
import logging
import math
from typing import Dict, List, Optional, Tuple

import httpx

from app.core.config import get_settings
from app.schemas.geo import (
    AlternativeRouteOption,
    AlternativeRoutesResponse,
    CoordinatePoint,
    RouteOption,
)
from app.services.routing import distance_to_polyline_meters, haversine_distance_meters
from app.services.routing_service import (
    fetch_osrm_routes_with_waypoints,
    fetch_tomtom_routes_with_traffic,
)
from app.services.traffic_service import (
    get_route_traffic,
    register_route_for_traffic_lookup,
)

logger = logging.getLogger("smartnav.alternatives")

ROUTE_PALETTE = [
    "#1a73e8",  # Blue (Primary / Route 1)
    "#0f9d58",  # Emerald (Route 2)
    "#9333ea",  # Purple (Route 3)
    "#ea580c",  # Orange (Route 4)
    "#0891b2",  # Cyan (Route 5)
    "#db2777",  # Pink (Fallback 6)
    "#4f46e5",  # Indigo (Fallback 7)
]


def _sample_polyline(coords: List[List[float]], num_samples: int = 24) -> List[Tuple[float, float]]:
    if len(coords) <= 2:
        return [(pt[0], pt[1]) for pt in coords]
    step = max(1, (len(coords) - 1) // max(1, num_samples - 1))
    sampled = [(coords[i][0], coords[i][1]) for i in range(0, len(coords), step)]
    last = (coords[-1][0], coords[-1][1])
    if sampled[-1] != last:
        sampled.append(last)
    return sampled


def routes_are_similar(route_a: RouteOption, route_b: RouteOption) -> bool:
    """
    Compare two route geometries to avoid displaying duplicate or nearly identical alternatives.
    Checks symmetric sampled distance and corridor overlap ratio.
    """
    pts_a = _sample_polyline(route_a.geometry_latlng)
    pts_b = _sample_polyline(route_b.geometry_latlng)
    if len(pts_a) < 2 or len(pts_b) < 2:
        return True

    # Ignore endpoints when computing overlap so shared start/end streets don't dominate
    core_a = pts_a[1:-1] if len(pts_a) > 4 else pts_a
    core_b = pts_b[1:-1] if len(pts_b) > 4 else pts_b

    full_b = [(pt[0], pt[1]) for pt in route_b.geometry_latlng]
    full_a = [(pt[0], pt[1]) for pt in route_a.geometry_latlng]

    dists_ab = [distance_to_polyline_meters(lat, lng, full_b) for lat, lng in core_a]
    dists_ba = [distance_to_polyline_meters(lat, lng, full_a) for lat, lng in core_b]

    avg_sep = (sum(dists_ab) / len(dists_ab) + sum(dists_ba) / len(dists_ba)) / 2.0
    corridor_tol = max(75.0, min(250.0, 0.02 * min(route_a.distance_meters, route_b.distance_meters)))
    overlap_a = sum(1 for d in dists_ab if d <= corridor_tol) / len(dists_ab)
    overlap_b = sum(1 for d in dists_ba if d <= corridor_tol) / len(dists_ba)
    overlap_ratio = (overlap_a + overlap_b) / 2.0

    # Similar if >85% of the core route follows the same corridor OR average separation is tiny
    min_distinct_sep = max(90.0, 0.025 * min(route_a.distance_meters, route_b.distance_meters))
    return overlap_ratio >= 0.85 or avg_sep < min_distinct_sep


def is_valid_connected_route(
    route: RouteOption,
    origin: CoordinatePoint,
    destination: CoordinatePoint,
) -> bool:
    """Ensure the candidate route has valid geometry and connects near origin and destination."""
    pts = route.geometry_latlng
    if len(pts) < 2 or route.distance_meters <= 0 or route.duration_seconds <= 0:
        return False
    start_dist = haversine_distance_meters(origin.lat, origin.lng, pts[0][0], pts[0][1])
    end_dist = haversine_distance_meters(destination.lat, destination.lng, pts[-1][0], pts[-1][1])
    # Allow up to 3.0 km snap from off-road start/end coordinates to nearest road network node
    return start_dist <= 3000.0 and end_dist <= 3000.0


def _generate_lateral_via_points(
    origin: CoordinatePoint, destination: CoordinatePoint
) -> List[CoordinatePoint]:
    """
    Generate lateral intermediate waypoints perpendicular to the origin-destination axis
    to discover genuinely distinct alternative road corridors.
    """
    d_meters = haversine_distance_meters(origin.lat, origin.lng, destination.lat, destination.lng)
    if d_meters < 400:
        return []

    mid_lat = (origin.lat + destination.lat) / 2.0
    cos_lat = max(0.2, math.cos(math.radians(mid_lat)))
    dx = (destination.lng - origin.lng) * cos_lat
    dy = destination.lat - origin.lat
    axis_len = math.hypot(dx, dy)
    if axis_len == 0:
        return []

    # Unit perpendicular vector in scaled lat/lng space
    perp_lat = -dx / axis_len
    perp_lng = (dy / axis_len) / cos_lat

    # Offsets at (fraction along route, lateral fraction of trip length)
    probes = [
        (0.50, 0.16),
        (0.50, -0.16),
        (0.35, 0.24),
        (0.65, -0.24),
        (0.50, 0.32),
        (0.50, -0.32),
    ]
    waypoints: List[CoordinatePoint] = []
    for along_t, lat_frac in probes:
        base_lat = origin.lat + along_t * (destination.lat - origin.lat)
        base_lng = origin.lng + along_t * (destination.lng - origin.lng)
        w_lat = max(-89.5, min(89.5, base_lat + perp_lat * axis_len * lat_frac))
        w_lng = max(-179.5, min(179.5, base_lng + perp_lng * axis_len * lat_frac))
        waypoints.append(CoordinatePoint(lat=w_lat, lng=w_lng))
    return waypoints


def _make_route_id(route: RouteOption) -> str:
    pts = route.geometry_latlng
    sig = f"{pts[0]}|{pts[len(pts)//2]}|{pts[-1]}|{round(route.distance_meters, 1)}"
    return "rt-" + hashlib.sha1(sig.encode("utf-8")).hexdigest()[:12]


async def generate_alternative_routes(
    origin: CoordinatePoint,
    destination: CoordinatePoint,
    profile: str = "driving",
    max_routes: int = 5,
    avoid_tolls: bool = False,
    preference: str = "fastest",
) -> AlternativeRoutesResponse:
    settings = get_settings()
    candidates: List[Tuple[RouteOption, Optional[dict]]] = []
    routing_provider = "OSRM"

    # 1. Try TomTom Routing API first if API key is configured (supports up to 5 traffic-aware routes)
    if settings.TOMTOM_API_KEY.strip():
        try:
            tt_routes = await fetch_tomtom_routes_with_traffic(
                waypoints=[origin, destination],
                profile=profile,
                max_alternatives=max(4, max_routes - 1),
                avoid_tolls=avoid_tolls,
                preference=preference,
            )
            if tt_routes:
                routing_provider = "TomTom"
                candidates.extend(tt_routes)
        except httpx.HTTPError as exc:
            logger.warning("TomTom routing fallback to OSRM: %s", exc)

    # 2. Query OSRM native alternatives if TomTom is not configured or returned no routes
    if routing_provider != "TomTom" and len(candidates) < max_routes:
        try:
            osrm_primary = await fetch_osrm_routes_with_waypoints(
                waypoints=[origin, destination],
                profile=profile,
                alternatives=True,
            )
            for rt in osrm_primary:
                candidates.append((rt, None))
        except httpx.HTTPError as exc:
            if not candidates:
                raise exc

    # Deduplicate initial candidates
    unique_candidates: List[Tuple[RouteOption, Optional[dict]]] = []
    for cand, tt_raw in candidates:
        if not is_valid_connected_route(cand, origin, destination):
            continue
        if any(routes_are_similar(cand, existing) for existing, _ in unique_candidates):
            continue
        unique_candidates.append((cand, tt_raw))

    # 3. If fewer than max_routes distinct routes exist, probe lateral intermediate waypoints
    if len(unique_candidates) < max_routes:
        via_points = _generate_lateral_via_points(origin, destination)
        if via_points:
            use_tomtom_probes = routing_provider == "TomTom" and bool(settings.TOMTOM_API_KEY.strip())
            if use_tomtom_probes:
                tasks = [
                    fetch_tomtom_routes_with_traffic(
                        waypoints=[origin, via, destination],
                        profile=profile,
                        max_alternatives=0,
                        avoid_tolls=avoid_tolls,
                        preference=preference,
                    )
                    for via in via_points
                ]
            else:
                tasks = [
                    fetch_osrm_routes_with_waypoints(
                        waypoints=[origin, via, destination],
                        profile=profile,
                        alternatives=False,
                    )
                    for via in via_points
                ]
            probe_results = await asyncio.gather(*tasks, return_exceptions=True)
            for res in probe_results:
                if isinstance(res, Exception) or not res:
                    continue
                for item in res:
                    cand, tt_raw = item if use_tomtom_probes else (item, None)
                    if not is_valid_connected_route(cand, origin, destination):
                        continue
                    # Reject extreme detours (> 2.2x shortest known route distance)
                    if unique_candidates:
                        min_dist = min(r.distance_meters for r, _ in unique_candidates)
                        if cand.distance_meters > min_dist * 2.2:
                            continue
                    if any(routes_are_similar(cand, existing) for existing, _ in unique_candidates):
                        continue
                    unique_candidates.append((cand, tt_raw))
                    if len(unique_candidates) >= max_routes:
                        break
                if len(unique_candidates) >= max_routes:
                    break

    unique_candidates = unique_candidates[:max_routes]

    # 4. Enrich every distinct route with live traffic (if configured) and ETA predictions
    traffic_tasks = [
        get_route_traffic(route=rt, profile=profile, precomputed_tomtom_summary=tt_raw)
        for rt, tt_raw in unique_candidates
    ]
    traffic_summaries = await asyncio.gather(*traffic_tasks)

    enriched: List[AlternativeRouteOption] = []
    for idx, ((rt, _), traffic) in enumerate(zip(unique_candidates, traffic_summaries)):
        route_id = _make_route_id(rt)
        register_route_for_traffic_lookup(route_id, rt)
        effective_eta = (
            traffic.traffic_adjusted_duration_seconds
            if traffic.traffic_adjusted_duration_seconds is not None
            else rt.duration_seconds
        )
        enriched.append(
            AlternativeRouteOption(
                index=idx,
                route_id=route_id,
                route_number=idx + 1,
                color=ROUTE_PALETTE[idx % len(ROUTE_PALETTE)],
                summary=rt.summary,
                distance_meters=rt.distance_meters,
                duration_seconds=rt.duration_seconds,
                geometry_latlng=rt.geometry_latlng,
                steps=rt.steps,
                is_fastest=False,
                has_tolls=False,
                traffic=traffic,
            )
        )

    # Sort according to user preference (default: estimated travel time; never mark fastest by distance alone)
    def effective_duration(r: AlternativeRouteOption) -> float:
        if r.traffic.traffic_adjusted_duration_seconds is not None:
            return r.traffic.traffic_adjusted_duration_seconds
        return r.duration_seconds

    if preference == "shortest":
        enriched.sort(key=lambda r: (r.distance_meters, effective_duration(r)))
    else:
        enriched.sort(key=effective_duration)

    # Identify the fastest route strictly by estimated travel time (ignoring closed routes if open ones exist)
    open_routes = [r for r in enriched if not r.traffic.has_road_closure] or enriched
    fastest_route = min(open_routes, key=effective_duration) if open_routes else None
    selected_ref_eta = effective_duration(enriched[0]) if enriched else 0.0

    for idx, r in enumerate(enriched):
        r.index = idx
        r.route_number = idx + 1
        r.color = ROUTE_PALETTE[idx % len(ROUTE_PALETTE)]
        r.is_fastest = bool(fastest_route and r.route_id == fastest_route.route_id)
        r.time_saved_vs_selected_seconds = round(selected_ref_eta - effective_duration(r), 1)

    traffic_available = any(r.traffic.traffic_status == "live" for r in enriched)
    traffic_provider = next(
        (r.traffic.provider for r in enriched if r.traffic.traffic_status == "live"),
        "none",
    )

    availability_note: Optional[str] = None
    if len(enriched) < max_routes:
        availability_note = (
            f"Found {len(enriched)} genuinely distinct valid road route(s) out of {max_routes} requested. "
            "Additional corridor probes produced duplicate or disconnected paths on this road network."
        )

    return AlternativeRoutesResponse(
        provider=routing_provider,
        traffic_provider=traffic_provider,
        traffic_available=traffic_available,
        profile=profile,
        requested_count=max_routes,
        returned_count=len(enriched),
        availability_note=availability_note,
        routes=enriched,
    )
