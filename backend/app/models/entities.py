from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database.session import Base
from app.database.spatial import PointGeography


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    full_name: Mapped[str] = mapped_column(String(120), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    favorites: Mapped[list["FavoritePlace"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    route_history: Mapped[list["RouteHistory"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )
    navigation_sessions: Mapped[list["NavigationSession"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class FavoritePlace(Base):
    __tablename__ = "favorite_places"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    label: Mapped[str] = mapped_column(String(160), nullable=False)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[str] = mapped_column(String(64), default="favorite", nullable=False)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lng: Mapped[float] = mapped_column(Float, nullable=False)
    location: Mapped[Optional[str]] = mapped_column(PointGeography, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    user: Mapped["User"] = relationship(back_populates="favorites")


class RouteHistory(Base):
    __tablename__ = "route_history"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    origin_label: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    destination_label: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    origin_lat: Mapped[float] = mapped_column(Float, nullable=False)
    origin_lng: Mapped[float] = mapped_column(Float, nullable=False)
    dest_lat: Mapped[float] = mapped_column(Float, nullable=False)
    dest_lng: Mapped[float] = mapped_column(Float, nullable=False)
    origin_point: Mapped[Optional[str]] = mapped_column(PointGeography, nullable=True)
    dest_point: Mapped[Optional[str]] = mapped_column(PointGeography, nullable=True)
    profile: Mapped[str] = mapped_column(String(32), default="driving", nullable=False)
    distance_meters: Mapped[float] = mapped_column(Float, nullable=False)
    duration_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    user: Mapped["User"] = relationship(back_populates="route_history")


class NavigationSession(Base):
    __tablename__ = "navigation_sessions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), index=True, nullable=True
    )
    origin_label: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    destination_label: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    origin_lat: Mapped[float] = mapped_column(Float, nullable=False)
    origin_lng: Mapped[float] = mapped_column(Float, nullable=False)
    dest_lat: Mapped[float] = mapped_column(Float, nullable=False)
    dest_lng: Mapped[float] = mapped_column(Float, nullable=False)
    last_lat: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    last_lng: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    last_point: Mapped[Optional[str]] = mapped_column(PointGeography, nullable=True)
    profile: Mapped[str] = mapped_column(String(32), default="driving", nullable=False)
    route_distance_meters: Mapped[float] = mapped_column(Float, nullable=False)
    route_duration_seconds: Mapped[float] = mapped_column(Float, nullable=False)
    remaining_distance_meters: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    reroute_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(32), default="active", nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    ended_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped[Optional["User"]] = relationship(back_populates="navigation_sessions")
    breadcrumbs: Mapped[list["NavigationBreadcrumb"]] = relationship(
        back_populates="session", cascade="all, delete-orphan"
    )


class NavigationBreadcrumb(Base):
    __tablename__ = "navigation_breadcrumbs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    session_id: Mapped[int] = mapped_column(
        ForeignKey("navigation_sessions.id", ondelete="CASCADE"), index=True
    )
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lng: Mapped[float] = mapped_column(Float, nullable=False)
    point: Mapped[Optional[str]] = mapped_column(PointGeography, nullable=True)
    accuracy_meters: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    speed_mps: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    heading_deg: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)

    session: Mapped["NavigationSession"] = relationship(back_populates="breadcrumbs")
