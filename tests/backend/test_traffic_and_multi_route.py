from datetime import datetime, timezone
import time

import httpx
import pytest

from app.schemas.geo import (
    AlternativeRouteOption,
    CoordinatePoint,
    RouteOption,
    RouteTrafficSummary,
)
from app.schemas.navigation import OptimizationPreferences
from app.services import alternative_route_service, traffic_monitor_service, traffic_service
from app.services.eta_prediction_service import (
    compare_prediction_vs_observed,
    predict_eta_seconds,
)
from app.services.route_optimizer import evaluate_route_switch


class FakeHttpResponse:
    def __init__(self, payload, status_code=200, url="https://example.test"):
        self._payload = payload
        self.status_code = status_code
        self.request = httpx.Request("GET", url)

    def raise_for_status(self):
        if self.status_code >= 400:
            raise httpx.HTTPStatusError(
                f"HTTP {self.status_code}",
                request=self.request,
                response=httpx.Response(self.status_code, request=self.request),
            )

    def json(self):
        return self._payload


def _make_distinct_route_option(idx: int, lat_offset: float, dist_m: float, dur_s: float) -> RouteOption:
    return RouteOption(
        index=idx,
        summary=f"Corridor {idx + 1}",
        distance_meters=dist_m,
        duration_seconds=dur_s,
        geometry_latlng=[
            [37.7749, -122.4194],
            [37.7799 + lat_offset, -122.4144 + lat_offset],
            [37.7849, -122.4094],
        ],
        steps=[],
    )


def _make_alt_option(
    route_id: str,
    route_number: int,
    dist_m: float,
    base_dur_s: float,
    live_dur_s: float | None,
    congestion: str = "low",
    has_closure: bool = False,
    has_tolls: bool = False,
) -> AlternativeRouteOption:
    is_live = live_dur_s is not None
    return AlternativeRouteOption(
        index=route_number - 1,
        route_id=route_id,
        route_number=route_number,
        color="#1a73e8",
        summary=f"Test Route {route_number}",
        distance_meters=dist_m,
        duration_seconds=base_dur_s,
        geometry_latlng=[[37.7749, -122.4194], [37.7800, -122.4150], [37.7849, -122.4094]],
        steps=[],
        is_fastest=False,
        has_tolls=has_tolls,
        traffic=RouteTrafficSummary(
            provider="tomtom" if is_live else "none",
            traffic_status="live" if is_live else "unavailable",
            traffic_label="Live traffic" if is_live else "Live traffic unavailable",
            congestion_level=congestion if is_live else "unknown",
            color=traffic_service.CONGESTION_COLORS.get(congestion if is_live else "unknown", "#64748b"),
            traffic_delay_seconds=(live_dur_s - base_dur_s) if is_live else None,
            traffic_adjusted_duration_seconds=live_dur_s,
            has_road_closure=has_closure,
            predicted_duration_seconds=base_dur_s * 1.1,
        ),
    )


def test_five_distinct_routes_with_traffic_and_deduplication(client, monkeypatch):
    """Covers scenarios 2, 4, and 5: 5 distinct routes, duplicate filtering, and varied traffic."""
    traffic_service._traffic_cache.clear()
    traffic_service._rate_limited_until = 0.0

    # Test fixture: 5 distinct corridors + 1 near-duplicate corridor
    distinct_routes = [
        _make_distinct_route_option(0, 0.000, 3200, 420),
        _make_distinct_route_option(1, 0.012, 3500, 450),
        _make_distinct_route_option(2, -0.012, 3600, 460),
        _make_distinct_route_option(3, 0.024, 3900, 500),
        _make_distinct_route_option(4, -0.024, 4100, 520),
        _make_distinct_route_option(5, 0.0001, 3210, 422),  # Near-duplicate of route 0
    ]

    async def fake_osrm_waypoints(waypoints, profile="driving", alternatives=True):
        if len(waypoints) == 2:
            return distinct_routes
        return []

    # Simulate varied live traffic across the 5 distinct routes via mocked TomTom flow
    speeds = iter([
        (15.0, 50.0, 0.9), (15.0, 50.0, 0.9), (15.0, 50.0, 0.9),  # Route 0: severe congestion
        (48.0, 50.0, 0.95), (48.0, 50.0, 0.95), (48.0, 50.0, 0.95),  # Route 1: low traffic (FASTEST!)
        (32.0, 50.0, 0.9), (32.0, 50.0, 0.9), (32.0, 50.0, 0.9),  # Route 2: moderate
        (22.0, 50.0, 0.88), (22.0, 50.0, 0.88), (22.0, 50.0, 0.88),  # Route 3: heavy
        (45.0, 50.0, 0.92), (45.0, 50.0, 0.92), (45.0, 50.0, 0.92),  # Route 4: low traffic
    ])

    class FakeTomTom(traffic_service.TomTomTrafficProvider):
        async def _fetch_incidents_bbox(self, client, coords):
            return []

        async def _fetch_flow_segment(self, client, lat, lng):
            c, f, conf = next(speeds, (45.0, 50.0, 0.9))
            return {"currentSpeed": c, "freeFlowSpeed": f, "confidence": conf}

    monkeypatch.setattr(
        alternative_route_service, "fetch_osrm_routes_with_waypoints", fake_osrm_waypoints
    )
    monkeypatch.setattr(
        traffic_service, "get_traffic_provider", lambda: FakeTomTom(api_key="test-fixture-key")
    )

    res = client.post(
        "/api/routes/alternatives",
        json={
            "origin": {"lat": 37.7749, "lng": -122.4194},
            "destination": {"lat": 37.7849, "lng": -122.4094},
            "profile": "driving",
            "max_routes": 5,
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["returned_count"] == 5
    assert body["traffic_available"] is True
    assert body["traffic_provider"] == "tomtom"

    # Fastest route must be marked by traffic-adjusted ETA (Route 1 had low traffic despite longer distance)
    assert body["routes"][0]["is_fastest"] is True
    assert body["routes"][0]["traffic"]["congestion_level"] == "low"
    assert body["routes"][0]["distance_meters"] == 3500
    assert body["routes"][-1]["traffic"]["congestion_level"] == "severe"

    # GET /api/routes/{route_id}/traffic works for registered route
    route_id = body["routes"][0]["route_id"]
    tr_res = client.get(f"/api/routes/{route_id}/traffic")
    assert tr_res.status_code == 200
    assert tr_res.json()["traffic_label"] == "Live traffic"


def test_fewer_than_five_routes_and_no_routes_available(client, monkeypatch):
    """Covers scenarios 3 and 18: fewer than 5 routes explanation, and no valid routes found."""
    traffic_service._traffic_cache.clear()

    async def fake_two_routes(waypoints, profile="driving", alternatives=True):
        if len(waypoints) == 2:
            return [
                _make_distinct_route_option(0, 0.0, 2000, 240),
                _make_distinct_route_option(1, 0.015, 2400, 300),
            ]
        # Lateral probes return duplicate of route 0
        return [_make_distinct_route_option(0, 0.0001, 2010, 242)]

    monkeypatch.setattr(
        alternative_route_service, "fetch_osrm_routes_with_waypoints", fake_two_routes
    )

    res = client.post(
        "/api/routes/alternatives",
        json={
            "origin": {"lat": 37.7749, "lng": -122.4194},
            "destination": {"lat": 37.7849, "lng": -122.4094},
            "max_routes": 5,
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["returned_count"] == 2
    assert "Found 2 genuinely distinct" in body["availability_note"]
    # Without TOMTOM_API_KEY, traffic is explicitly unavailable (never fabricated)
    assert body["traffic_available"] is False
    assert body["routes"][0]["traffic"]["traffic_label"] == "Live traffic unavailable"
    assert body["routes"][0]["traffic"]["prediction_label"] == "Predicted traffic"

    # Scenario 18: No valid route exists
    async def fake_no_routes(waypoints, profile="driving", alternatives=True):
        return []

    monkeypatch.setattr(
        alternative_route_service, "fetch_osrm_routes_with_waypoints", fake_no_routes
    )
    res_none = client.post(
        "/api/routes/alternatives",
        json={
            "origin": {"lat": 37.7749, "lng": -122.4194},
            "destination": {"lat": 37.7849, "lng": -122.4094},
        },
    )
    assert res_none.status_code == 404


@pytest.mark.asyncio
async def test_traffic_api_unavailable_and_rate_limit_handling(monkeypatch):
    """Covers scenarios 12 and 17: Traffic API unavailable and HTTP 429 rate-limit handling."""
    traffic_service._traffic_cache.clear()
    traffic_service._rate_limited_until = 0.0
    route = _make_distinct_route_option(0, 0.0, 3000, 360)

    provider = traffic_service.TomTomTrafficProvider(api_key="test-key")

    async def fake_429(self, url, params=None):
        return FakeHttpResponse({}, status_code=429, url=url)

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_429)
    monkeypatch.setattr(traffic_service, "get_traffic_provider", lambda: provider)

    summary = await traffic_service.get_route_traffic(route, force_refresh=True)
    assert summary.traffic_status == "unavailable"
    assert summary.traffic_label == "Live traffic unavailable"
    assert traffic_service._rate_limited_until > time.monotonic()

    # Subsequent call during cooldown skips provider cleanly
    summary2 = await traffic_service.get_route_traffic(route, force_refresh=True)
    assert summary2.traffic_status == "unavailable"


def test_dynamic_route_optimizer_decisions():
    """Covers scenarios 6, 7, 8, 9, 10, 11: manual vs auto switch, marginal rejections, cooldown, closures."""
    # Current route developed heavy traffic (1800s = 30 min), Route 2 is 1080s = 18 min (saves 12 min / 40%)
    cur = _make_alt_option("rt-1", 1, 10000, 900, 1800, congestion="heavy")
    fast_alt = _make_alt_option("rt-2", 2, 11000, 1000, 1080, congestion="low")
    marginal_alt = _make_alt_option("rt-3", 3, 10500, 950, 1680, congestion="moderate")  # saves 2 min (<5 min)

    # Scenario 8 & 11: Auto-reroute disabled -> recommend_switch
    res_manual = evaluate_route_switch(
        candidate_routes=[cur, fast_alt],
        current_route_id="rt-1",
        current_route_remaining_seconds=1800,
        preferences=OptimizationPreferences(auto_reroute=False, manual_confirmation=True),
    )
    assert res_manual.decision == "recommend_switch"
    assert res_manual.time_saved_seconds == 720.0
    assert res_manual.notification.recommended_route.route_id == "rt-2"

    # Scenario 10: Auto-reroute enabled -> auto_switch
    res_auto = evaluate_route_switch(
        candidate_routes=[cur, fast_alt],
        current_route_id="rt-1",
        current_route_remaining_seconds=1800,
        preferences=OptimizationPreferences(auto_reroute=True, manual_confirmation=False),
    )
    assert res_auto.decision == "auto_switch"

    # Marginal improvement (< 5 min) -> continue (prevents unnecessary switching)
    res_marginal = evaluate_route_switch(
        candidate_routes=[cur, marginal_alt],
        current_route_id="rt-1",
        current_route_remaining_seconds=1800,
    )
    assert res_marginal.decision == "continue"

    # Cooldown active -> continue
    now_ms = 1_700_000_000_000
    res_cooldown = evaluate_route_switch(
        candidate_routes=[cur, fast_alt],
        current_route_id="rt-1",
        current_route_remaining_seconds=1800,
        last_reroute_timestamp_ms=now_ms - 30_000,  # 30s ago (< 120s cooldown)
        now_ms=now_ms,
    )
    assert res_cooldown.decision == "continue"
    assert res_cooldown.cooldown_active is True

    # Road closure overrides marginal/cooldown -> immediate switch recommendation
    closed_cur = _make_alt_option("rt-1", 1, 10000, 900, 1200, congestion="severe", has_closure=True)
    res_closure = evaluate_route_switch(
        candidate_routes=[closed_cur, marginal_alt],
        current_route_id="rt-1",
        current_route_remaining_seconds=1200,
        current_route_has_closure=True,
        last_reroute_timestamp_ms=now_ms - 10_000,
        now_ms=now_ms,
    )
    assert res_closure.decision == "recommend_switch"
    assert res_closure.notification.reason == "road_closure"


def test_navigation_traffic_monitoring_endpoints_and_throttling(client, monkeypatch):
    """Covers scenarios 15 and 16: live ETA updates, throttling within interval, status & summary."""
    traffic_monitor_service._session_states.clear()

    async def fake_gen(origin, destination, profile="driving", max_routes=5, avoid_tolls=False, preference="fastest"):
        from app.schemas.geo import AlternativeRoutesResponse

        r1 = _make_alt_option("rt-1", 1, 5000, 400, 900, congestion="heavy")
        r2 = _make_alt_option("rt-2", 2, 5400, 420, 450, congestion="low")
        r2.is_fastest = True
        return AlternativeRoutesResponse(
            provider="OSRM",
            traffic_provider="tomtom",
            traffic_available=True,
            profile=profile,
            requested_count=5,
            returned_count=2,
            routes=[r2, r1],
        )

    monkeypatch.setattr(traffic_monitor_service, "generate_alternative_routes", fake_gen)

    start = client.post(
        "/api/navigation/start",
        json={
            "origin_lat": 37.7749,
            "origin_lng": -122.4194,
            "dest_lat": 37.7849,
            "dest_lng": -122.4094,
            "profile": "driving",
            "route_distance_meters": 5000,
            "route_duration_seconds": 400,
        },
    )
    session_id = start.json()["session_id"]

    # First monitor poll refreshes
    upd1 = client.post(
        "/api/navigation/traffic/update",
        json={
            "session_id": session_id,
            "current_lat": 37.7760,
            "current_lng": -122.4180,
            "dest_lat": 37.7849,
            "dest_lng": -122.4094,
            "current_route_id": "rt-1",
            "monitor_interval_seconds": 45,
        },
    )
    assert upd1.status_code == 200
    assert upd1.json()["refreshed"] is True
    assert upd1.json()["sudden_congestion_detected"] is True

    # Immediate second poll is throttled (Scenario 16)
    upd2 = client.post(
        "/api/navigation/traffic/update",
        json={
            "session_id": session_id,
            "current_lat": 37.7765,
            "current_lng": -122.4175,
            "dest_lat": 37.7849,
            "dest_lng": -122.4094,
            "current_route_id": "rt-1",
            "monitor_interval_seconds": 45,
        },
    )
    assert upd2.status_code == 200
    assert upd2.json()["refreshed"] is False
    assert "Throttled" in upd2.json()["skipped_reason"]

    # Optimize route endpoint recommends switch to rt-2
    opt = client.post(
        "/api/navigation/optimize-route",
        json={
            "session_id": session_id,
            "current_lat": 37.7765,
            "current_lng": -122.4175,
            "dest_lat": 37.7849,
            "dest_lng": -122.4094,
            "current_route_id": "rt-1",
            "current_route_remaining_seconds": 900,
            "candidate_routes": upd1.json()["routes"],
        },
    )
    assert opt.status_code == 200
    assert opt.json()["decision"] == "recommend_switch"

    status_res = client.get("/api/navigation/status", params={"session_id": session_id})
    assert status_res.status_code == 200
    assert status_res.json()["traffic_available"] is True

    summary_res = client.get("/api/navigation/traffic-summary", params={"session_id": session_id})
    assert summary_res.status_code == 200
    assert summary_res.json()["alternatives_count"] == 2


def test_eta_prediction_baseline_and_comparison():
    rush_dt = datetime(2026, 11, 26, 8, 30, tzinfo=timezone.utc)
    night_dt = datetime(2026, 11, 26, 2, 0, tzinfo=timezone.utc)

    rush_eta = predict_eta_seconds(10000, 720, "driving", congestion_level="heavy", reference_time=rush_dt)
    night_eta = predict_eta_seconds(10000, 720, "driving", congestion_level="low", reference_time=night_dt)
    assert rush_eta > night_eta

    err = compare_prediction_vs_observed(predicted_seconds=900, observed_seconds=1000)
    assert err["absolute_error_seconds"] == 100.0
    assert err["relative_error_pct"] == 10.0
