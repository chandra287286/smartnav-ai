import logging
import time
from typing import Dict, List, Tuple

import httpx

from app.core.config import get_settings
from app.schemas.geo import NearbyPlaceItem
from app.services.routing import haversine_distance_meters

logger = logging.getLogger("smartnav.places")

CATEGORY_OSM_FILTERS = {
    "restaurant": '["amenity"~"restaurant|cafe|fast_food"]',
    "hospital": '["amenity"~"hospital|clinic|doctors"]',
    "fuel": '["amenity"="fuel"]',
    "atm": '["amenity"~"atm|bank"]',
    "hotel": '["tourism"~"hotel|guest_house|hostel|motel"]',
    "shopping": '["shop"~"mall|supermarket|department_store"]',
    "parking": '["amenity"="parking"]',
}

_places_cache: Dict[str, Tuple[float, List[NearbyPlaceItem]]] = {}
_CACHE_TTL_SECONDS = 180.0


def _build_overpass_query(lat: float, lng: float, category: str, radius: int) -> str:
    osm_filter = CATEGORY_OSM_FILTERS[category]
    return (
        f"[out:json][timeout:12];"
        f"("
        f"node{osm_filter}(around:{radius},{lat},{lng});"
        f"way{osm_filter}(around:{radius},{lat},{lng});"
        f");"
        f"out center 25;"
    )


async def fetch_nearby_places(
    lat: float,
    lng: float,
    category: str,
    radius: int = 1500,
) -> List[NearbyPlaceItem]:
    if category not in CATEGORY_OSM_FILTERS:
        raise ValueError(
            f"Unsupported category '{category}'. Supported: {', '.join(CATEGORY_OSM_FILTERS.keys())}"
        )

    bounded_radius = min(max(radius, 200), 5000)
    key = f"{lat:.3f}|{lng:.3f}|{category}|{bounded_radius}"
    now = time.monotonic()
    cached = _places_cache.get(key)
    if cached and (now - cached[0]) < _CACHE_TTL_SECONDS:
        return cached[1]

    settings = get_settings()
    query = _build_overpass_query(lat, lng, category, bounded_radius)

    async with httpx.AsyncClient(timeout=15.0) as client:
        resp = await client.post(
            settings.OVERPASS_BASE_URL,
            data={"data": query},
            headers={"User-Agent": settings.NOMINATIM_USER_AGENT},
        )
        resp.raise_for_status()
        payload = resp.json()

    items: List[NearbyPlaceItem] = []
    seen = set()
    for el in payload.get("elements", []):
        tags = el.get("tags") or {}
        el_lat = el.get("lat") if el.get("lat") is not None else (el.get("center") or {}).get("lat")
        el_lng = el.get("lon") if el.get("lon") is not None else (el.get("center") or {}).get("lon")
        if el_lat is None or el_lng is None:
            continue

        el_lat = float(el_lat)
        el_lng = float(el_lng)
        name = (tags.get("name") or tags.get("operator") or f"{category.title()}").strip()
        dedup_key = f"{name.lower()}|{el_lat:.4f}|{el_lng:.4f}"
        if dedup_key in seen:
            continue
        seen.add(dedup_key)

        addr_parts = [tags.get("addr:housenumber"), tags.get("addr:street"), tags.get("addr:city")]
        address = ", ".join([p for p in addr_parts if p]) or None
        dist = haversine_distance_meters(lat, lng, el_lat, el_lng)

        items.append(
            NearbyPlaceItem(
                id=f"{el.get('type', 'node')}-{el.get('id')}",
                name=name,
                category=category,
                lat=el_lat,
                lng=el_lng,
                distance_meters=round(dist, 1),
                address=address,
            )
        )

    items.sort(key=lambda x: x.distance_meters if x.distance_meters is not None else float("inf"))
    items = items[:25]
    _places_cache[key] = (time.monotonic(), items)
    logger.info("Overpass nearby category=%s center=(%f,%f) count=%d", category, lat, lng, len(items))
    return items
