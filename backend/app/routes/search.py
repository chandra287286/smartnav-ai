from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.geo import SearchResponse
from app.services.geocoding import search_locations

router = APIRouter(prefix="/api", tags=["Search & Geocoding"])


@router.get("/search", response_model=SearchResponse)
async def search(
    q: str = Query(..., min_length=2, max_length=200, description="Place name or address"),
    lat: Optional[float] = Query(default=None, ge=-90.0, le=90.0),
    lng: Optional[float] = Query(default=None, ge=-180.0, le=180.0),
):
    try:
        results = await search_locations(q, near_lat=lat, near_lng=lng)
        return SearchResponse(query=q, results=results)
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Geocoding provider returned HTTP {exc.response.status_code}.",
        ) from exc
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Geocoding service is temporarily unreachable.",
        ) from exc
