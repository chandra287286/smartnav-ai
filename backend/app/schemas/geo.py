import math
from typing import List, Literal, Optional
from pydantic import BaseModel, Field, field_validator


class CoordinatePoint(BaseModel):
    lat: float = Field(..., ge=-90.0, le=90.0)
    lng: float = Field(..., ge=-180.0, le=180.0)
    label: Optional[str] = Field(default=None, max_length=255)

    @field_validator("lat", "lng")
    @classmethod
    def check_finite(cls, v: float) -> float:
        if not math.isfinite(v):
            raise ValueError("Coordinate must be a finite number.")
        return v


class SearchPlaceResult(BaseModel):
    place_id: str
    name: str
    display_name: str
    lat: float
    lng: float
    type: Optional[str] = None


class SearchResponse(BaseModel):
    query: str
    results: List[SearchPlaceResult]


class RouteRequest(BaseModel):
    origin: CoordinatePoint
    destination: CoordinatePoint
    profile: Literal["driving", "cycling", "walking"] = "driving"
    alternatives: bool = True


class RouteStep(BaseModel):
    instruction: str
    road_name: str = ""
    distance_meters: float
    duration_seconds: float
    maneuver_type: str = ""
    modifier: str = ""
    lat: Optional[float] = None
    lng: Optional[float] = None


class RouteOption(BaseModel):
    index: int
    summary: str
    distance_meters: float
    duration_seconds: float
    geometry_latlng: List[List[float]]
    steps: List[RouteStep]


class RouteResponse(BaseModel):
    provider: str = "OSRM"
    profile: str
    routes: List[RouteOption]


CongestionLevel = Literal["low", "moderate", "heavy", "severe", "unknown"]


class TrafficSegment(BaseModel):
    start_index: int
    end_index: int
    coords_latlng: List[List[float]] = Field(default_factory=list)
    congestion_level: CongestionLevel = "unknown"
    color: str = "#64748b"
    current_speed_kmh: Optional[float] = None
    free_flow_speed_kmh: Optional[float] = None
    delay_seconds: Optional[float] = None
    magnitude_of_delay: Optional[int] = None


class TrafficIncident(BaseModel):
    id: str
    category: str = "incident"
    severity: str = "moderate"
    description: str
    delay_seconds: Optional[float] = None
    is_road_closure: bool = False
    lat: float
    lng: float
    road_name: Optional[str] = None


class RouteTrafficSummary(BaseModel):
    provider: str = "none"
    traffic_status: Literal["live", "unavailable"] = "unavailable"
    traffic_label: str = "Live traffic unavailable"
    congestion_level: CongestionLevel = "unknown"
    color: str = "#64748b"
    current_speed_kmh: Optional[float] = None
    normal_speed_kmh: Optional[float] = None
    traffic_delay_seconds: Optional[float] = None
    traffic_adjusted_duration_seconds: Optional[float] = None
    estimated_arrival_iso: Optional[str] = None
    timestamp_iso: Optional[str] = None
    confidence: Optional[float] = None
    has_road_closure: bool = False
    segments: List[TrafficSegment] = Field(default_factory=list)
    incidents: List[TrafficIncident] = Field(default_factory=list)
    # Separately labeled baseline/ML prediction (never disguised as live traffic)
    predicted_duration_seconds: Optional[float] = None
    prediction_label: str = "Predicted traffic"


class AlternativeRouteOption(RouteOption):
    route_id: str
    route_number: int
    color: str
    is_fastest: bool = False
    time_saved_vs_selected_seconds: Optional[float] = None
    has_tolls: bool = False
    traffic: RouteTrafficSummary


class AlternativeRoutesRequest(BaseModel):
    origin: CoordinatePoint
    destination: CoordinatePoint
    profile: Literal["driving", "cycling", "walking"] = "driving"
    max_routes: int = Field(default=5, ge=1, le=7)
    avoid_tolls: bool = False
    preference: Literal["fastest", "shortest"] = "fastest"


class AlternativeRoutesResponse(BaseModel):
    provider: str
    traffic_provider: str
    traffic_available: bool
    profile: str
    requested_count: int = 5
    returned_count: int
    availability_note: Optional[str] = None
    routes: List[AlternativeRouteOption]


class NearbyPlaceItem(BaseModel):
    id: str
    name: str
    category: str
    lat: float
    lng: float
    distance_meters: Optional[float] = None
    address: Optional[str] = None


class NearbyPlacesResponse(BaseModel):
    category: str
    center: CoordinatePoint
    places: List[NearbyPlaceItem]
