from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import desc, select
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database.session import get_db
from app.database.spatial import point_wkt
from app.models.entities import FavoritePlace, NavigationSession, RouteHistory, User
from app.schemas.navigation import (
    FavoriteCreateRequest,
    FavoriteItemResponse,
    FavoritesListResponse,
    HistoryResponse,
    NavigationSessionItem,
    RouteHistoryItem,
)

router = APIRouter(prefix="/api", tags=["Favorites & History"])


@router.get("/favorites", response_model=FavoritesListResponse)
def list_favorites(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    rows = db.scalars(
        select(FavoritePlace)
        .where(FavoritePlace.user_id == current_user.id)
        .order_by(desc(FavoritePlace.created_at))
    ).all()
    return FavoritesListResponse(items=[FavoriteItemResponse.model_validate(r) for r in rows])


@router.post("/favorites", response_model=FavoriteItemResponse, status_code=status.HTTP_201_CREATED)
def add_favorite(
    payload: FavoriteCreateRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    fav = FavoritePlace(
        user_id=current_user.id,
        label=payload.label.strip(),
        address=payload.address,
        category=payload.category.strip() or "favorite",
        lat=payload.lat,
        lng=payload.lng,
        location=point_wkt(payload.lat, payload.lng),
    )
    db.add(fav)
    db.commit()
    db.refresh(fav)
    return FavoriteItemResponse.model_validate(fav)


@router.delete("/favorites/{favorite_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_favorite(
    favorite_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    fav = db.get(FavoritePlace, favorite_id)
    if not fav or fav.user_id != current_user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Favorite location not found.")
    db.delete(fav)
    db.commit()


@router.get("/history", response_model=HistoryResponse)
def get_history(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    routes = db.scalars(
        select(RouteHistory)
        .where(RouteHistory.user_id == current_user.id)
        .order_by(desc(RouteHistory.created_at))
        .limit(30)
    ).all()

    sessions = db.scalars(
        select(NavigationSession)
        .where(NavigationSession.user_id == current_user.id)
        .order_by(desc(NavigationSession.started_at))
        .limit(30)
    ).all()

    return HistoryResponse(
        routes=[RouteHistoryItem.model_validate(r) for r in routes],
        sessions=[NavigationSessionItem.model_validate(s) for s in sessions],
    )
