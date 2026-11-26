import httpx

from app.services.routing import distance_to_polyline_meters


class DummyOsrmResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            req = httpx.Request("GET", "https://router.project-osrm.org/route/v1/driving/0,0;1,1")
            resp = httpx.Response(self.status_code, request=req)
            raise httpx.HTTPStatusError("OSRM error", request=req, response=resp)

    def json(self):
        return self._payload


SAMPLE_OSRM_PAYLOAD = {
    "code": "Ok",
    "routes": [
        {
            "distance": 2450.5,
            "duration": 310.2,
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [-122.4194, 37.7749],
                    [-122.4140, 37.7790],
                    [-122.4094, 37.7849],
                ],
            },
            "legs": [
                {
                    "summary": "Market St",
                    "steps": [
                        {
                            "name": "Market St",
                            "distance": 1200.0,
                            "duration": 150.0,
                            "maneuver": {
                                "type": "depart",
                                "modifier": "northeast",
                                "location": [-122.4194, 37.7749],
                            },
                        },
                        {
                            "name": "4th St",
                            "distance": 1250.5,
                            "duration": 160.2,
                            "maneuver": {
                                "type": "turn",
                                "modifier": "left",
                                "location": [-122.4140, 37.7790],
                            },
                        },
                    ],
                }
            ],
        },
        {
            "distance": 2900.0,
            "duration": 360.0,
            "geometry": {
                "type": "LineString",
                "coordinates": [
                    [-122.4194, 37.7749],
                    [-122.4100, 37.7749],
                    [-122.4094, 37.7849],
                ],
            },
            "legs": [{"summary": "Mission St", "steps": []}],
        },
    ],
}


def test_route_calculation_with_alternatives(client, monkeypatch):
    async def fake_get(self, url, params=None):
        return DummyOsrmResponse(SAMPLE_OSRM_PAYLOAD)

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    res = client.post(
        "/api/routes",
        json={
            "origin": {"lat": 37.7749, "lng": -122.4194, "label": "Origin"},
            "destination": {"lat": 37.7849, "lng": -122.4094, "label": "Dest"},
            "profile": "driving",
            "alternatives": True,
        },
    )
    assert res.status_code == 200
    body = res.json()
    assert body["provider"] == "OSRM"
    assert len(body["routes"]) == 2
    primary = body["routes"][0]
    assert primary["distance_meters"] == 2450.5
    assert primary["duration_seconds"] == 310.2
    # GeoJSON [lng, lat] converted to Leaflet [lat, lng]
    assert primary["geometry_latlng"][0] == [37.7749, -122.4194]
    assert primary["steps"][1]["instruction"] == "Turn left onto 4th St"


def test_route_rejects_invalid_coordinates(client):
    res = client.post(
        "/api/routes",
        json={
            "origin": {"lat": 120.0, "lng": -122.4194},
            "destination": {"lat": 37.7849, "lng": -200.0},
            "profile": "driving",
        },
    )
    assert res.status_code == 422


def test_route_deviation_and_reroute_lifecycle(client, monkeypatch):
    async def fake_get(self, url, params=None):
        return DummyOsrmResponse(SAMPLE_OSRM_PAYLOAD)

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    # Verify distance_to_polyline_meters accurately flags on-route vs off-route
    polyline = [(37.7749, -122.4194), (37.7790, -122.4140), (37.7849, -122.4094)]
    on_route_dist = distance_to_polyline_meters(37.77695, -122.4167, polyline)
    off_route_dist = distance_to_polyline_meters(37.7749, -122.4000, polyline)
    assert on_route_dist < 25.0
    assert off_route_dist > 500.0

    # Start navigation session -> update -> reroute -> stop
    start = client.post(
        "/api/navigation/start",
        json={
            "origin_lat": 37.7749,
            "origin_lng": -122.4194,
            "dest_lat": 37.7849,
            "dest_lng": -122.4094,
            "profile": "driving",
            "route_distance_meters": 2450.5,
            "route_duration_seconds": 310.2,
        },
    )
    assert start.status_code == 201
    session_id = start.json()["session_id"]

    upd = client.post(
        "/api/navigation/update",
        json={
            "session_id": session_id,
            "lat": 37.7760,
            "lng": -122.4170,
            "accuracy_meters": 8.0,
            "speed_mps": 11.2,
            "heading_deg": 45.0,
            "remaining_distance_meters": 1900.0,
        },
    )
    assert upd.status_code == 200

    reroute = client.post(
        "/api/navigation/reroute",
        json={
            "session_id": session_id,
            "current_lat": 37.7749,
            "current_lng": -122.4000,
            "dest_lat": 37.7849,
            "dest_lng": -122.4094,
            "profile": "driving",
        },
    )
    assert reroute.status_code == 200
    assert len(reroute.json()["routes"]) >= 1

    stop = client.post(
        "/api/navigation/stop",
        json={"session_id": session_id, "status": "completed"},
    )
    assert stop.status_code == 200
    assert stop.json()["status"] == "completed"
