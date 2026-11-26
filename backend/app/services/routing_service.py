"""
Unified Routing Service wrapping OSRM and TomTom Routing APIs.
Supports multi-waypoint routing, route preferences (fastest/shortest), and toll avoidance.
"""

import logging
from typing import List, Optional, Tuple

import httpx

from app.core.config import get_settings
from app.schemas.geo import CoordinatePoint, RouteOption, RouteStep
from app.services.routing import PROFILE_MAP, format_maneuver_instruction

logger = logging.getLogger("smartnav.routing_service")


async def fetch_osrm_routes_with_waypoints(
    waypoints: List[CoordinatePoint],
    profile: str = "driving",
    alternatives: bool = True,
) -> List[RouteOption]:
    """Query OSRM for a sequence of 2 or more waypoints (origin -> [via...] -> destination)."""
    if len(waypoints) < 2:
        raise ValueError("At least origin and destination waypoints are required.")

    settings = get_settings()
    osrm_profile = PROFILE_MAP.get(profile, "driving")
    coords = ";".join(f"{pt.lng},{pt.lat}" for pt in waypoints)
    url = f"{settings.OSRM_BASE_URL.rstrip('/')}/route/v1/{osrm_profile}/{coords}"
    params = {
        "overview": "full",
        "geometries": "geojson",
        "steps": "true",
        "alternatives": "true" if (alternatives and len(waypoints) == 2) else "false",
    }

    async with httpx.AsyncClient(timeout=12.0) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

    if data.get("code") != "Ok":
        return []

    options: List[RouteOption] = []
    for idx, route in enumerate(data.get("routes", [])):
        raw_coords = (route.get("geometry") or {}).get("coordinates") or []
        geometry_latlng = [[float(pt[1]), float(pt[0])] for pt in raw_coords if len(pt) >= 2]
        if len(geometry_latlng) < 2:
            continue

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

        summary = " via ".join(s for s in leg_summaries if s) or f"Route {idx + 1}"
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

    return options


async def fetch_tomtom_routes_with_traffic(
    waypoints: List[CoordinatePoint],
    profile: str = "driving",
    max_alternatives: int = 4,
    avoid_tolls: bool = False,
    preference: str = "fastest",
) -> List[Tuple[RouteOption, dict]]:
    """
    Query TomTom Routing API with live traffic enabled.
    Returns list of (RouteOption, raw_tomtom_route_dict) tuples.
    """
    settings = get_settings()
    api_key = settings.TOMTOM_API_KEY.strip()
    if not api_key:
        return []

    travel_mode_map = {
        "driving": "car",
        "cycling": "bicycle",
        "walking": "pedestrian",
    }
    locs = ":".join(f"{pt.lat},{pt.lng}" for pt in waypoints)
    url = f"{settings.TOMTOM_BASE_URL.rstrip('/')}/routing/1/calculateRoute/{locs}/json"
    params = {
        "key": api_key,
        "traffic": "true",
        "computeTravelTimeFor": "all",
        "sectionType": "traffic",
        "instructionsType": "text",
        "travelMode": travel_mode_map.get(profile, "car"),
        "routeType": "shortest" if preference == "shortest" else "fastest",
        "maxAlternatives": min(max(max_alternatives, 0), 5) if len(waypoints) == 2 else 0,
    }
    if avoid_tolls and profile == "driving":
        params["avoid"] = "tollRoads"

    async with httpx.AsyncClient(timeout=14.0) as client:
        resp = await client.get(url, params=params)
        resp.raise_for_status()
        data = resp.json()

    results: List[Tuple[RouteOption, dict]] = []
    for idx, raw_route in enumerate(data.get("routes", [])):
        geometry_latlng: List[List[float]] = []
        for leg in raw_route.get("legs", []):
            for pt in leg.get("points", []):
                geometry_latlng.append([float(pt["latitude"]), float(pt["longitude"])])
        if len(geometry_latlng) < 2:
            continue

        steps: List[RouteStep] = []
        road_names: List[str] = []
        guidance = (raw_route.get("guidance") or {}).get("instructions") or []
        for instr in guidance:
            pt = instr.get("point") or {}
            road = (instr.get("street") or "").strip()
            if road and road not in road_names:
                road_names.append(road)
            steps.append(
                RouteStep(
                    instruction=str(instr.get("message") or "Continue"),
                    road_name=road,
                    distance_meters=float(instr.get("routeOffsetInMeters") or 0.0),
                    duration_seconds=float(instr.get("travelTimeInSeconds") or 0.0),
                    maneuver_type=str(instr.get("maneuver") or "").lower(),
                    modifier="",
                    lat=float(pt["latitude"]) if "latitude" in pt else None,
                    lng=float(pt["longitude"]) if "longitude" in pt else None,
                )
            )

        summary_obj = raw_route.get("summary") or {}
        no_traffic_sec = float(
            summary_obj.get("noTrafficTravelTimeInSeconds")
            or summary_obj.get("travelTimeInSeconds")
            or 0.0
        )
        summary_label = ", ".join(road_names[:2]) if road_names else f"TomTom Route {idx + 1}"
        option = RouteOption(
            index=idx,
            summary=summary_label,
            distance_meters=float(summary_obj.get("lengthInMeters") or 0.0),
            duration_seconds=no_traffic_sec,
            geometry_latlng=geometry_latlng,
            steps=steps,
        )
        results.append((option, raw_route))

    return results
