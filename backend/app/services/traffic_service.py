"""
Modular Live Traffic Service.

Preferred Provider: TomTom Routing & Traffic APIs (backend-only API key).
Strict Honesty Rules:
- Never pretend OSRM provides live traffic.
- Never fabricate random/mock traffic values in production.
- If live traffic data cannot be retrieved, explicitly return
  traffic_status="unavailable" and traffic_label="Live traffic unavailable".
"""

import hashlib
import logging
import time
from abc import ABC, abstractmethod
from datetime import datetime, timedelta, timezone
from typing import Dict, List, Optional, Tuple

import httpx

from app.core.config import get_settings
from app.schemas.geo import (
    CongestionLevel,
    RouteOption,
    RouteTrafficSummary,
    TrafficIncident,
    TrafficSegment,
)
from app.services.eta_prediction_service import predict_eta_seconds
from app.services.routing import distance_to_polyline_meters

logger = logging.getLogger("smartnav.traffic")

CONGESTION_COLORS: Dict[CongestionLevel, str] = {
    "low": "#16a34a",       # GREEN
    "moderate": "#f97316",  # ORANGE
    "heavy": "#dc2626",     # RED
    "severe": "#7f1d1d",    # DARK RED
    "unknown": "#64748b",   # NEUTRAL SLATE
}

# In-memory TTL cache for traffic responses and route lookup registry
_traffic_cache: Dict[str, Tuple[float, RouteTrafficSummary]] = {}
_route_registry: Dict[str, RouteOption] = {}
_rate_limited_until: float = 0.0


def classify_congestion(
    current_speed_kmh: Optional[float] = None,
    normal_speed_kmh: Optional[float] = None,
    delay_seconds: Optional[float] = None,
    base_duration_seconds: Optional[float] = None,
    magnitude_of_delay: Optional[int] = None,
) -> CongestionLevel:
    """Classify congestion strictly from real provider metrics."""
    if magnitude_of_delay is not None:
        # TomTom magnitudeOfDelay: 0=unknown, 1=minor, 2=moderate, 3=major, 4=undefined/closure
        if magnitude_of_delay >= 4:
            return "severe"
        if magnitude_of_delay == 3:
            return "heavy"
        if magnitude_of_delay == 2:
            return "moderate"
        if magnitude_of_delay == 1:
            return "low"

    if current_speed_kmh is not None and normal_speed_kmh and normal_speed_kmh > 0:
        ratio = current_speed_kmh / normal_speed_kmh
        if ratio >= 0.80:
            return "low"
        if ratio >= 0.55:
            return "moderate"
        if ratio >= 0.35:
            return "heavy"
        return "severe"

    if delay_seconds is not None and base_duration_seconds and base_duration_seconds > 0:
        delay_ratio = delay_seconds / base_duration_seconds
        if delay_ratio <= 0.10 and delay_seconds < 120:
            return "low"
        if delay_ratio <= 0.28:
            return "moderate"
        if delay_ratio <= 0.55:
            return "heavy"
        return "severe"

    return "unknown"


def register_route_for_traffic_lookup(route_id: str, route: RouteOption) -> None:
    """Store route geometry briefly in memory so GET /api/routes/{route_id}/traffic can refresh it."""
    if len(_route_registry) > 300:
        # Evict oldest inserted item
        first_key = next(iter(_route_registry))
        _route_registry.pop(first_key, None)
    _route_registry[route_id] = route


def get_registered_route(route_id: str) -> Optional[RouteOption]:
    return _route_registry.get(route_id)


def _route_cache_key(route: RouteOption, provider_name: str) -> str:
    pts = route.geometry_latlng or []
    sample = pts[:: max(1, len(pts) // 8)] if pts else []
    digest = hashlib.sha256(str(sample).encode("utf-8")).hexdigest()[:16]
    return f"{provider_name}:{digest}:{round(route.distance_meters, -1)}"


class TrafficProvider(ABC):
    name: str = "none"

    @abstractmethod
    async def evaluate_route_traffic(
        self,
        route: RouteOption,
        profile: str = "driving",
        precomputed_tomtom_summary: Optional[dict] = None,
    ) -> RouteTrafficSummary:
        raise NotImplementedError


class UnavailableTrafficProvider(TrafficProvider):
    name = "none"

    async def evaluate_route_traffic(
        self,
        route: RouteOption,
        profile: str = "driving",
        precomputed_tomtom_summary: Optional[dict] = None,
    ) -> RouteTrafficSummary:
        predicted = predict_eta_seconds(
            distance_meters=route.distance_meters,
            base_duration_seconds=route.duration_seconds,
            profile=profile,
        )
        return RouteTrafficSummary(
            provider="none",
            traffic_status="unavailable",
            traffic_label="Live traffic unavailable",
            congestion_level="unknown",
            color=CONGESTION_COLORS["unknown"],
            predicted_duration_seconds=predicted,
            prediction_label="Predicted traffic",
        )


class TomTomTrafficProvider(TrafficProvider):
    """TomTom Traffic Flow + Incidents + Traffic Routing integration."""

    name = "tomtom"

    def __init__(self, api_key: str, base_url: str = "https://api.tomtom.com"):
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")

    async def _fetch_flow_segment(
        self, client: httpx.AsyncClient, lat: float, lng: float
    ) -> Optional[dict]:
        url = f"{self.base_url}/traffic/services/4/flowSegmentData/absolute/10/json"
        resp = await client.get(
            url,
            params={"key": self.api_key, "point": f"{lat},{lng}", "unit": "KMPH"},
        )
        if resp.status_code == 429:
            raise httpx.HTTPStatusError("Rate limit reached", request=resp.request, response=resp)
        resp.raise_for_status()
        return resp.json().get("flowSegmentData")

    async def _fetch_incidents_bbox(
        self, client: httpx.AsyncClient, coords: List[List[float]]
    ) -> List[TrafficIncident]:
        if len(coords) < 2:
            return []
        lats = [pt[0] for pt in coords]
        lngs = [pt[1] for pt in coords]
        min_lat, max_lat = min(lats) - 0.005, max(lats) + 0.005
        min_lng, max_lng = min(lngs) - 0.005, max(lngs) + 0.005
        bbox = f"{min_lng:.5f},{min_lat:.5f},{max_lng:.5f},{max_lat:.5f}"

        url = f"{self.base_url}/traffic/services/5/incidentDetails"
        resp = await client.get(
            url,
            params={
                "key": self.api_key,
                "bbox": bbox,
                "fields": "{incidents{type,geometry{type,coordinates},properties{id,iconCategory,magnitudeOfDelay,events{description},from,delay,roadNumbers}}}",
                "language": "en-US",
            },
        )
        if resp.status_code == 429:
            raise httpx.HTTPStatusError("Rate limit reached", request=resp.request, response=resp)
        if resp.status_code >= 400:
            return []

        route_tuples = [(pt[0], pt[1]) for pt in coords]
        incidents: List[TrafficIncident] = []
        for raw in resp.json().get("incidents", []):
            props = raw.get("properties") or {}
            geom = raw.get("geometry") or {}
            coords_raw = geom.get("coordinates") or []
            pt = coords_raw[0] if coords_raw and isinstance(coords_raw[0], list) else coords_raw
            if not isinstance(pt, list) or len(pt) < 2:
                continue
            inc_lat, inc_lng = float(pt[1]), float(pt[0])
            if distance_to_polyline_meters(inc_lat, inc_lng, route_tuples) > 75.0:
                continue
            events = props.get("events") or []
            desc = events[0].get("description") if events else "Traffic incident"
            mag = int(props.get("magnitudeOfDelay") or 1)
            icon_cat = int(props.get("iconCategory") or 0)
            is_closure = icon_cat == 8 or "closed" in str(desc).lower()
            sev = classify_congestion(magnitude_of_delay=4 if is_closure else mag)

            incidents.append(
                TrafficIncident(
                    id=str(props.get("id") or f"inc-{len(incidents)}"),
                    category="road_closure" if is_closure else "incident",
                    severity=sev,
                    description=str(desc),
                    delay_seconds=float(props["delay"]) if props.get("delay") is not None else None,
                    is_road_closure=is_closure,
                    lat=inc_lat,
                    lng=inc_lng,
                    road_name=props.get("from"),
                )
            )
            if len(incidents) >= 15:
                break
        return incidents

    def _build_summary_from_tomtom_route(
        self,
        route: RouteOption,
        tomtom_data: dict,
        incidents: List[TrafficIncident],
        profile: str,
    ) -> RouteTrafficSummary:
        summary = tomtom_data.get("summary") or {}
        live_sec = float(summary.get("travelTimeInSeconds") or route.duration_seconds)
        no_traffic_sec = float(summary.get("noTrafficTravelTimeInSeconds") or live_sec)
        delay_sec = float(summary.get("trafficDelayInSeconds") or max(0.0, live_sec - no_traffic_sec))

        dist_km = route.distance_meters / 1000.0
        cur_speed = round(dist_km / (live_sec / 3600.0), 1) if live_sec > 0 else None
        norm_speed = round(dist_km / (no_traffic_sec / 3600.0), 1) if no_traffic_sec > 0 else None

        segments: List[TrafficSegment] = []
        pts = route.geometry_latlng or []
        for sec in tomtom_data.get("sections", []):
            if sec.get("sectionType") != "TRAFFIC":
                continue
            s_idx = int(sec.get("startPointIndex") or 0)
            e_idx = int(sec.get("endPointIndex") or 0)
            if 0 <= s_idx < e_idx < len(pts):
                mag = sec.get("magnitudeOfDelay")
                eff_speed = sec.get("effectiveSpeedInKmh")
                seg_level = classify_congestion(
                    current_speed_kmh=eff_speed,
                    normal_speed_kmh=norm_speed,
                    magnitude_of_delay=mag,
                )
                segments.append(
                    TrafficSegment(
                        start_index=s_idx,
                        end_index=e_idx,
                        coords_latlng=pts[s_idx : e_idx + 1],
                        congestion_level=seg_level,
                        color=CONGESTION_COLORS[seg_level],
                        current_speed_kmh=eff_speed,
                        free_flow_speed_kmh=norm_speed,
                        delay_seconds=sec.get("delayInSeconds"),
                        magnitude_of_delay=mag,
                    )
                )

        overall_level = classify_congestion(
            current_speed_kmh=cur_speed,
            normal_speed_kmh=norm_speed,
            delay_seconds=delay_sec,
            base_duration_seconds=no_traffic_sec,
        )
        now = datetime.now(timezone.utc)
        eta_dt = now + timedelta(seconds=live_sec)
        has_closure = any(inc.is_road_closure for inc in incidents)
        if has_closure:
            overall_level = "severe"

        predicted = predict_eta_seconds(
            distance_meters=route.distance_meters,
            base_duration_seconds=no_traffic_sec,
            profile=profile,
            observed_speed_kmh=cur_speed,
            historical_avg_speed_kmh=norm_speed,
            congestion_level=overall_level,
            reference_time=now,
        )

        return RouteTrafficSummary(
            provider="tomtom",
            traffic_status="live",
            traffic_label="Live traffic",
            congestion_level=overall_level,
            color=CONGESTION_COLORS[overall_level],
            current_speed_kmh=cur_speed,
            normal_speed_kmh=norm_speed,
            traffic_delay_seconds=round(delay_sec, 1),
            traffic_adjusted_duration_seconds=round(live_sec, 1),
            estimated_arrival_iso=eta_dt.isoformat(),
            timestamp_iso=now.isoformat(),
            confidence=0.92,
            has_road_closure=has_closure,
            segments=segments,
            incidents=incidents,
            predicted_duration_seconds=predicted,
            prediction_label="Predicted traffic",
        )

    async def evaluate_route_traffic(
        self,
        route: RouteOption,
        profile: str = "driving",
        precomputed_tomtom_summary: Optional[dict] = None,
    ) -> RouteTrafficSummary:
        global _rate_limited_until
        now_mono = time.monotonic()
        if now_mono < _rate_limited_until:
            logger.warning("TomTom rate-limit cooldown active; returning unavailable.")
            return await UnavailableTrafficProvider().evaluate_route_traffic(route, profile)

        pts = route.geometry_latlng or []
        if len(pts) < 2:
            return await UnavailableTrafficProvider().evaluate_route_traffic(route, profile)

        try:
            async with httpx.AsyncClient(timeout=10.0) as client:
                incidents = await self._fetch_incidents_bbox(client, pts) if profile == "driving" else []
                if precomputed_tomtom_summary:
                    return self._build_summary_from_tomtom_route(
                        route, precomputed_tomtom_summary, incidents, profile
                    )

                # Sample up to 3 equidistant points along the route for TomTom Flow Segment Data
                sample_indices = sorted(
                    set([len(pts) // 4, len(pts) // 2, (3 * len(pts)) // 4])
                )
                flow_samples = []
                for idx in sample_indices:
                    pt = pts[min(idx, len(pts) - 1)]
                    flow = await self._fetch_flow_segment(client, pt[0], pt[1])
                    if flow:
                        flow_samples.append((idx, flow))

            if not flow_samples:
                return await UnavailableTrafficProvider().evaluate_route_traffic(route, profile)

            cur_speeds = [float(f["currentSpeed"]) for _, f in flow_samples if f.get("currentSpeed")]
            free_speeds = [float(f["freeFlowSpeed"]) for _, f in flow_samples if f.get("freeFlowSpeed")]
            confidences = [float(f["confidence"]) for _, f in flow_samples if f.get("confidence") is not None]

            avg_cur = round(sum(cur_speeds) / len(cur_speeds), 1) if cur_speeds else None
            avg_free = round(sum(free_speeds) / len(free_speeds), 1) if free_speeds else None
            avg_conf = round(sum(confidences) / len(confidences), 2) if confidences else None

            if avg_cur and avg_free and avg_cur > 0:
                speed_factor = max(1.0, avg_free / avg_cur)
                adjusted_sec = route.duration_seconds * speed_factor
                delay_sec = max(0.0, adjusted_sec - route.duration_seconds)
            else:
                adjusted_sec = route.duration_seconds
                delay_sec = 0.0

            # Build colored traffic segments across the sampled chunks
            segments: List[TrafficSegment] = []
            chunk_bounds = [0] + [idx for idx, _ in flow_samples] + [len(pts) - 1]
            for i, (_, flow) in enumerate(flow_samples):
                s_idx = chunk_bounds[i]
                e_idx = chunk_bounds[i + 2] if i + 2 < len(chunk_bounds) else len(pts) - 1
                if s_idx < e_idx:
                    c_spd = flow.get("currentSpeed")
                    f_spd = flow.get("freeFlowSpeed")
                    seg_level = classify_congestion(current_speed_kmh=c_spd, normal_speed_kmh=f_spd)
                    segments.append(
                        TrafficSegment(
                            start_index=s_idx,
                            end_index=e_idx,
                            coords_latlng=pts[s_idx : e_idx + 1],
                            congestion_level=seg_level,
                            color=CONGESTION_COLORS[seg_level],
                            current_speed_kmh=c_spd,
                            free_flow_speed_kmh=f_spd,
                        )
                    )

            has_closure = any(inc.is_road_closure for inc in incidents)
            overall = (
                "severe"
                if has_closure
                else classify_congestion(
                    current_speed_kmh=avg_cur,
                    normal_speed_kmh=avg_free,
                    delay_seconds=delay_sec,
                    base_duration_seconds=route.duration_seconds,
                )
            )
            now = datetime.now(timezone.utc)
            eta_dt = now + timedelta(seconds=adjusted_sec)
            predicted = predict_eta_seconds(
                distance_meters=route.distance_meters,
                base_duration_seconds=route.duration_seconds,
                profile=profile,
                observed_speed_kmh=avg_cur,
                historical_avg_speed_kmh=avg_free,
                congestion_level=overall,
                reference_time=now,
            )

            return RouteTrafficSummary(
                provider="tomtom",
                traffic_status="live",
                traffic_label="Live traffic",
                congestion_level=overall,
                color=CONGESTION_COLORS[overall],
                current_speed_kmh=avg_cur,
                normal_speed_kmh=avg_free,
                traffic_delay_seconds=round(delay_sec, 1),
                traffic_adjusted_duration_seconds=round(adjusted_sec, 1),
                estimated_arrival_iso=eta_dt.isoformat(),
                timestamp_iso=now.isoformat(),
                confidence=avg_conf,
                has_road_closure=has_closure,
                segments=segments,
                incidents=incidents,
                predicted_duration_seconds=predicted,
                prediction_label="Predicted traffic",
            )
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 429:
                _rate_limited_until = time.monotonic() + 60.0
                logger.warning("TomTom API rate limit (429) hit; cooling down for 60s.")
            else:
                logger.warning("TomTom API returned HTTP %s", exc.response.status_code)
            return await UnavailableTrafficProvider().evaluate_route_traffic(route, profile)
        except httpx.RequestError as exc:
            logger.warning("TomTom API network error: %s", exc)
            return await UnavailableTrafficProvider().evaluate_route_traffic(route, profile)


def get_traffic_provider() -> TrafficProvider:
    settings = get_settings()
    if settings.TRAFFIC_PROVIDER.lower() == "tomtom" and settings.TOMTOM_API_KEY.strip():
        return TomTomTrafficProvider(
            api_key=settings.TOMTOM_API_KEY.strip(),
            base_url=settings.TOMTOM_BASE_URL,
        )
    return UnavailableTrafficProvider()


async def get_route_traffic(
    route: RouteOption,
    profile: str = "driving",
    precomputed_tomtom_summary: Optional[dict] = None,
    force_refresh: bool = False,
) -> RouteTrafficSummary:
    settings = get_settings()
    provider = get_traffic_provider()
    cache_key = _route_cache_key(route, provider.name)
    now = time.monotonic()

    if not force_refresh and not precomputed_tomtom_summary:
        cached = _traffic_cache.get(cache_key)
        if cached and (now - cached[0]) < settings.TRAFFIC_CACHE_TTL_SECONDS:
            return cached[1]

    summary = await provider.evaluate_route_traffic(
        route=route,
        profile=profile,
        precomputed_tomtom_summary=precomputed_tomtom_summary,
    )
    _traffic_cache[cache_key] = (time.monotonic(), summary)
    return summary
