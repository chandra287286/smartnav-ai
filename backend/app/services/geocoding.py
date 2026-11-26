import asyncio
import logging
import time
from typing import Dict, List, Optional, Tuple

import httpx

from app.core.config import get_settings
from app.schemas.geo import SearchPlaceResult

logger = logging.getLogger("smartnav.geocoding")

# Polite Nominatim rate limiter (1 request/second policy) and short-TTL cache
_rate_lock = asyncio.Lock()
_last_request_ts = 0.0
_cache: Dict[str, Tuple[float, List[SearchPlaceResult]]] = {}
_CACHE_TTL_SECONDS = 300.0


def _cache_key(query: str, lat: Optional[float], lng: Optional[float]) -> str:
    lat_part = f"{lat:.2f}" if lat is not None else "none"
    lng_part = f"{lng:.2f}" if lng is not None else "none"
    return f"{query.strip().lower()}|{lat_part}|{lng_part}"


async def search_locations(
    query: str,
    near_lat: Optional[float] = None,
    near_lng: Optional[float] = None,
    limit: int = 6,
) -> List[SearchPlaceResult]:
    cleaned = query.strip()
    if len(cleaned) < 2:
        return []

    key = _cache_key(cleaned, near_lat, near_lng)
    now = time.monotonic()
    cached = _cache.get(key)
    if cached and (now - cached[0]) < _CACHE_TTL_SECONDS:
        return cached[1]

    settings = get_settings()
    params = {
        "q": cleaned,
        "format": "jsonv2",
        "addressdetails": 1,
        "limit": min(max(limit, 1), 10),
    }
    if near_lat is not None and near_lng is not None:
        # Provide a soft viewbox bias (~0.5 deg around user's position) without restricting global results
        params["viewbox"] = f"{near_lng - 0.5},{near_lat + 0.5},{near_lng + 0.5},{near_lat - 0.5}"

    headers = {
        "User-Agent": settings.NOMINATIM_USER_AGENT,
        "Accept": "application/json",
    }

    async with _rate_lock:
        global _last_request_ts
        elapsed = time.monotonic() - _last_request_ts
        if elapsed < 1.05:
            await asyncio.sleep(1.05 - elapsed)
        _last_request_ts = time.monotonic()

        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.get(
                f"{settings.NOMINATIM_BASE_URL.rstrip('/')}/search",
                params=params,
                headers=headers,
            )
            resp.raise_for_status()
            raw_items = resp.json()

    results: List[SearchPlaceResult] = []
    for item in raw_items:
        try:
            lat = float(item["lat"])
            lng = float(item["lon"])
            if not (-90.0 <= lat <= 90.0 and -180.0 <= lng <= 180.0):
                continue
            display_name = str(item.get("display_name") or "").strip()
            name = str(item.get("name") or (display_name.split(",")[0] if display_name else cleaned)).strip()
            results.append(
                SearchPlaceResult(
                    place_id=str(item.get("place_id") or f"{lat}:{lng}"),
                    name=name,
                    display_name=display_name or name,
                    lat=lat,
                    lng=lng,
                    type=item.get("type"),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue

    _cache[key] = (time.monotonic(), results)
    logger.info("Nominatim search query=%r returned %d results", cleaned, len(results))
    return results
