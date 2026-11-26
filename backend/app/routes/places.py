import httpx
from fastapi import APIRouter, HTTPException, Query, status

from app.schemas.geo import CoordinatePoint, NearbyPlacesResponse
from app.services.places import fetch_nearby_places

router = APIRouter(prefix="/api/places", tags=["Nearby Places"])


@router.get("/nearby", response_model=NearbyPlacesResponse)
async def nearby_places(
    lat: float = Query(..., ge=-90.0, le=90.0),
    lng: float = Query(..., ge=-180.0, le=180.0),
    category: str = Query(default="restaurant"),
    radius: int = Query(default=1500, ge=200, le=5000),
):
    try:
        places = await fetch_nearby_places(lat=lat, lng=lng, category=category, radius=radius)
        return NearbyPlacesResponse(
            category=category,
            center=CoordinatePoint(lat=lat, lng=lng),
            places=places,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except httpx.HTTPStatusError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Places service returned HTTP {exc.response.status_code}.",
        ) from exc
    except httpx.RequestError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Nearby places service (Overpass) is temporarily unreachable.",
        ) from exc
