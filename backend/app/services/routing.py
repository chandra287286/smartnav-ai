import logging
import math
from typing import List, Tuple

import httpx

from app.core.config import get_settings
from app.schemas.geo import CoordinatePoint, RouteOption, RouteStep

logger = logging.getLogger("smartnav.routing")

EARTH_RADIUS_METERS = 6371000.0

PROFILE_MAP = {
    "driving": "driving",
    "cycling": "cycling",
    "walking": "walking",
}


def format_maneuver_instruction(step: dict) -> str:
    """Build clear turn-by-turn text strictly from OSRM maneuver fields without inventing data."""
    maneuver = step.get("maneuver") or {}
    m_type = (maneuver.get("type") or "").lower()
    modifier = (maneuver.get("modifier") or "").lower()
    road_name = (step.get("name") or "").strip()
    road_suffix = f" onto {road_name}" if road_name else ""

    if m_type == "depart":
        return f"Head {modifier or 'forward'}{road_suffix}".strip()
    if m_type == "arrive":
        return "Arrive at your destination"
    if m_type in ("roundabout", "rotary"):
        exit_num = maneuver.get("exit")
        exit_text = f"take exit {exit_num}" if exit_num else "enter the roundabout"
        return f"At the roundabout, {exit_text}{road_suffix}"
    if m_type == "turn":
        direction = modifier.replace("_", " ") if modifier else "ahead"
        return f"Turn {direction}{road_suffix}"
    if m_type == "new name":
        return f"Continue{road_suffix}" if road_name else "Continue straight"
    if m_type == "merge":
        return f"Merge {modifier or ''}{road_suffix}".replace("  ", " ").strip()
    if m_type in ("on ramp", "off ramp"):
        return f"Take the ramp {modifier or ''}{road_suffix}".replace("  ", " ").strip()
    if m_type == "fork":
        return f"Keep {modifier or 'straight'} at the fork{road_suffix}"
    if m_type == "end of road":
        return f"At the end of the road, turn {modifier or 'ahead'}{road_suffix}"

    if modifier:
        return f"Continue {modifier.replace('_', ' ')}{road_suffix}"
    return f"Continue{road_suffix}" if road_name else "Continue along route"


async def fetch_osrm_routes(
    origin: CoordinatePoint,
    destination: CoordinatePoint,
    profile: str = "driving",
    alternatives: bool = True,
) -> List[RouteOption]:
    settings = get_settings()
    osrm_profile = PROFILE_MAP.get(profile, "driving")
    coords = f"{origin.lng},{origin.lat};{destination.lng},{destination.lat}"
    url = f"{settings.OSRM_BASE_URL.rstrip('/')}/route/v1/{osrm_profile}/{coords}"
    params = {
        "overview": "full",
        "geometries": "geojson",
        "steps": "true",
        "alternatives": "true" if alternatives else "false",
    }

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

    if data.get("code") != "Ok":
        message = data.get("message") or "OSRM could not compute a route for these coordinates."
        raise ValueError(message)

    options: List[RouteOption] = []
    for idx, route in enumerate(data.get("routes", [])):
        raw_coords = (route.get("geometry") or {}).get("coordinates") or []
        # OSRM GeoJSON uses [lng, lat]; Leaflet expects [lat, lng]
        geometry_latlng = [[float(pt[1]), float(pt[0])] for pt in raw_coords if len(pt) >= 2]

        steps: List[RouteStep] = []
        leg_summaries: List[str] = []
        for leg in route.get("legs", []):
            if leg.get("summary"):
                leg_summaries.append(leg["summary"])
            for raw_step in leg.get("steps", []):
                maneuver = raw_step.get("maneuver") or {}
                loc = maneuver.get("location") or []
                steps.append(
                    RouteStep(
                        instruction=format_maneuver_instruction(raw_step),
                        road_name=(raw_step.get("name") or "").strip(),
                        distance_meters=float(raw_step.get("distance") or 0.0),
                        duration_seconds=float(raw_step.get("duration") or 0.0),
                        maneuver_type=str(maneuver.get("type") or ""),
                        modifier=str(maneuver.get("modifier") or ""),
                        lat=float(loc[1]) if len(loc) >= 2 else None,
                        lng=float(loc[0]) if len(loc) >= 2 else None,
                    )
                )

        summary = ", ".join(leg_summaries) if leg_summaries else f"Route {idx + 1}"
        options.append(
            RouteOption(
                index=idx,
                summary=summary,
                distance_meters=float(route.get("distance") or 0.0),
                duration_seconds=float(route.get("duration") or 0.0),
                geometry_latlng=geometry_latlng,
                steps=steps,
            )
        )

    logger.info(
        "OSRM routed (%s) (%f,%f)->(%f,%f): %d option(s)",
        osrm_profile,
        origin.lat,
        origin.lng,
        destination.lat,
        destination.lng,
        len(options),
    )
    return options


def haversine_distance_meters(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    rlat1, rlng1 = math.radians(lat1), math.radians(lng1)
    rlat2, rlng2 = math.radians(lat2), math.radians(lng2)
    dlat = rlat2 - rlat1
    dlng = rlng2 - rlng1
    a = math.sin(dlat / 2) ** 2 + math.cos(rlat1) * math.cos(rlat2) * math.sin(dlng / 2) ** 2
    return 2 * EARTH_RADIUS_METERS * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def distance_to_polyline_meters(
    lat: float,
    lng: float,
    polyline_latlng: List[Tuple[float, float]],
) -> float:
    """Compute shortest distance in meters from (lat, lng) to a route polyline."""
    if len(polyline_latlng) < 2:
        return float("inf")

    ref_lat = math.radians(lat)
    m_per_lat = 111132.92
    m_per_lng = 111320.0 * math.cos(ref_lat)

    min_dist = float("inf")
    for i in range(len(polyline_latlng) - 1):
        a_lat, a_lng = polyline_latlng[i]
        b_lat, b_lng = polyline_latlng[i + 1]
        px = (lng - a_lng) * m_per_lng
        py = (lat - a_lat) * m_per_lat
        bx = (b_lng - a_lng) * m_per_lng
        by = (b_lat - a_lat) * m_per_lat
        len_sq = bx * bx + by * by
        if len_sq == 0:
            dist = math.hypot(px, py)
        else:
            t = max(0.0, min(1.0, (px * bx + py * by) / len_sq))
            dist = math.hypot(px - t * bx, py - t * by)
        if dist < min_dist:
            min_dist = dist
    return min_dist
