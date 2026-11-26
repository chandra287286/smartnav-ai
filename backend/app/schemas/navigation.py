from datetime import datetime
from typing import List, Literal, Optional
from pydantic import BaseModel, Field

from app.schemas.geo import AlternativeRouteOption, CoordinatePoint, RouteTrafficSummary


class NavigationStartRequest(BaseModel):
    origin_lat: float = Field(..., ge=-90.0, le=90.0)
    origin_lng: float = Field(..., ge=-180.0, le=180.0)
    dest_lat: float = Field(..., ge=-90.0, le=90.0)
    dest_lng: float = Field(..., ge=-180.0, le=180.0)
    origin_label: Optional[str] = Field(default=None, max_length=255)
    destination_label: Optional[str] = Field(default=None, max_length=255)
    profile: Literal["driving", "cycling", "walking"] = "driving"
    route_distance_meters: float = Field(..., ge=0.0)
    route_duration_seconds: float = Field(..., ge=0.0)
    selected_route_id: Optional[str] = None


class NavigationStartResponse(BaseModel):
    session_id: int
    status: str
    started_at: datetime


class NavigationUpdateRequest(BaseModel):
    session_id: int
    lat: float = Field(..., ge=-90.0, le=90.0)
    lng: float = Field(..., ge=-180.0, le=180.0)
    accuracy_meters: Optional[float] = Field(default=None, ge=0.0)
    speed_mps: Optional[float] = Field(default=None, ge=0.0)
    heading_deg: Optional[float] = Field(default=None, ge=0.0, le=360.0)
    remaining_distance_meters: Optional[float] = Field(default=None, ge=0.0)


class NavigationRerouteRequest(BaseModel):
    session_id: Optional[int] = None
    current_lat: float = Field(..., ge=-90.0, le=90.0)
    current_lng: float = Field(..., ge=-180.0, le=180.0)
    dest_lat: float = Field(..., ge=-90.0, le=90.0)
    dest_lng: float = Field(..., ge=-180.0, le=180.0)
    profile: Literal["driving", "cycling", "walking"] = "driving"
    avoid_tolls: bool = False
    reason: Literal["deviation", "traffic_optimization", "manual"] = "deviation"


class NavigationStopRequest(BaseModel):
    session_id: int
    status: Literal["completed", "cancelled"] = "completed"


class OptimizationPreferences(BaseModel):
    auto_reroute: bool = False
    manual_confirmation: bool = True
    avoid_tolls: bool = False
    route_preference: Literal["fastest", "shortest"] = "fastest"
    min_time_saving_seconds: int = Field(default=300, ge=30, le=3600)
    min_relative_improvement: float = Field(default=0.10, ge=0.01, le=0.90)
    monitor_interval_seconds: int = Field(default=45, ge=15, le=300)
    reroute_cooldown_seconds: int = Field(default=120, ge=15, le=900)


class TrafficMonitorUpdateRequest(BaseModel):
    session_id: Optional[int] = None
    current_lat: float = Field(..., ge=-90.0, le=90.0)
    current_lng: float = Field(..., ge=-180.0, le=180.0)
    dest_lat: float = Field(..., ge=-90.0, le=90.0)
    dest_lng: float = Field(..., ge=-180.0, le=180.0)
    profile: Literal["driving", "cycling", "walking"] = "driving"
    current_route_id: Optional[str] = None
    current_remaining_duration_seconds: Optional[float] = Field(default=None, ge=0.0)
    avoid_tolls: bool = False
    monitor_interval_seconds: int = Field(default=45, ge=15, le=300)
    force_refresh: bool = False


class TrafficMonitorUpdateResponse(BaseModel):
    session_id: Optional[int] = None
    refreshed: bool
    skipped_reason: Optional[str] = None
    traffic_available: bool
    traffic_provider: str
    checked_at_iso: str
    current_route_eta_seconds: Optional[float] = None
    sudden_congestion_detected: bool = False
    road_closure_detected: bool = False
    routes: List[AlternativeRouteOption] = Field(default_factory=list)


class CompareRoutesRequest(BaseModel):
    origin: CoordinatePoint
    destination: CoordinatePoint
    profile: Literal["driving", "cycling", "walking"] = "driving"
    selected_route_id: Optional[str] = None
    avoid_tolls: bool = False
    preference: Literal["fastest", "shortest"] = "fastest"


class CompareRoutesResponse(BaseModel):
    traffic_available: bool
    traffic_provider: str
    selected_route_id: Optional[str] = None
    fastest_route_id: Optional[str] = None
    routes: List[AlternativeRouteOption]


class OptimizeRouteRequest(BaseModel):
    session_id: Optional[int] = None
    current_lat: float = Field(..., ge=-90.0, le=90.0)
    current_lng: float = Field(..., ge=-180.0, le=180.0)
    dest_lat: float = Field(..., ge=-90.0, le=90.0)
    dest_lng: float = Field(..., ge=-180.0, le=180.0)
    profile: Literal["driving", "cycling", "walking"] = "driving"
    current_route_id: Optional[str] = None
    current_route_remaining_seconds: Optional[float] = Field(default=None, ge=0.0)
    current_route_has_closure: bool = False
    last_reroute_timestamp_ms: Optional[int] = None
    preferences: OptimizationPreferences = Field(default_factory=OptimizationPreferences)
    candidate_routes: Optional[List[AlternativeRouteOption]] = None


class RouteSwitchNotification(BaseModel):
    title: str
    message: str
    reason: str
    current_route_eta_seconds: float
    alternative_route_eta_seconds: float
    time_saved_seconds: float
    recommended_route: AlternativeRouteOption


class OptimizeRouteResponse(BaseModel):
    decision: Literal["continue", "recommend_switch", "auto_switch"]
    reason: str
    current_route_eta_seconds: Optional[float] = None
    best_route_eta_seconds: Optional[float] = None
    time_saved_seconds: float = 0.0
    relative_improvement: float = 0.0
    cooldown_active: bool = False
    notification: Optional[RouteSwitchNotification] = None
    evaluated_routes: List[AlternativeRouteOption] = Field(default_factory=list)


class NavigationStatusResponse(BaseModel):
    session_id: int
    status: str
    profile: str
    reroute_count: int
    remaining_distance_meters: Optional[float] = None
    last_lat: Optional[float] = None
    last_lng: Optional[float] = None
    started_at: datetime
    ended_at: Optional[datetime] = None
    last_traffic_check_iso: Optional[str] = None
    traffic_available: bool = False
    active_route_id: Optional[str] = None


class TrafficSummaryResponse(BaseModel):
    session_id: Optional[int] = None
    traffic_available: bool
    traffic_provider: str
    last_updated_iso: Optional[str] = None
    active_route_traffic: Optional[RouteTrafficSummary] = None
    alternatives_count: int = 0
    routes: List[AlternativeRouteOption] = Field(default_factory=list)


class FavoriteCreateRequest(BaseModel):
    label: str = Field(..., min_length=1, max_length=160)
    address: Optional[str] = Field(default=None, max_length=500)
    category: str = Field(default="favorite", max_length=64)
    lat: float = Field(..., ge=-90.0, le=90.0)
    lng: float = Field(..., ge=-180.0, le=180.0)


class FavoriteItemResponse(BaseModel):
    id: int
    label: str
    address: Optional[str]
    category: str
    lat: float
    lng: float
    created_at: datetime

    model_config = {"from_attributes": True}


class FavoritesListResponse(BaseModel):
    items: List[FavoriteItemResponse]


class RouteHistoryItem(BaseModel):
    id: int
    origin_label: Optional[str]
    destination_label: Optional[str]
    origin_lat: float
    origin_lng: float
    dest_lat: float
    dest_lng: float
    profile: str
    distance_meters: float
    duration_seconds: float
    created_at: datetime

    model_config = {"from_attributes": True}


class NavigationSessionItem(BaseModel):
    id: int
    origin_label: Optional[str]
    destination_label: Optional[str]
    origin_lat: float
    origin_lng: float
    dest_lat: float
    dest_lng: float
    profile: str
    route_distance_meters: float
    route_duration_seconds: float
    reroute_count: int
    status: str
    started_at: datetime
    ended_at: Optional[datetime]

    model_config = {"from_attributes": True}


class HistoryResponse(BaseModel):
    routes: List[RouteHistoryItem]
    sessions: List[NavigationSessionItem]
