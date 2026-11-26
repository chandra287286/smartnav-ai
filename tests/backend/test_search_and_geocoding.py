import httpx

from app.services import geocoding


class DummyResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            req = httpx.Request("GET", "https://nominatim.openstreetmap.org/search")
            resp = httpx.Response(self.status_code, request=req)
            raise httpx.HTTPStatusError("Upstream error", request=req, response=resp)

    def json(self):
        return self._payload


def test_search_geocoding_returns_validated_places(client, monkeypatch):
    geocoding._cache.clear()
    geocoding._last_request_ts = 0.0

    async def fake_get(self, url, params=None, headers=None):
        assert "User-Agent" in headers
        return DummyResponse(
            [
                {
                    "place_id": 12345,
                    "name": "Golden Gate Bridge",
                    "display_name": "Golden Gate Bridge, San Francisco, CA, USA",
                    "lat": "37.8199286",
                    "lon": "-122.4782551",
                    "type": "bridge",
                }
            ]
        )

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get)

    res = client.get("/api/search", params={"q": "Golden Gate Bridge", "lat": 37.77, "lng": -122.41})
    assert res.status_code == 200
    body = res.json()
    assert body["query"] == "Golden Gate Bridge"
    assert len(body["results"]) == 1
    assert body["results"][0]["lat"] == 37.8199286
    assert body["results"][0]["lng"] == -122.4782551


def test_search_rejects_short_query_and_invalid_coords(client):
    res_short = client.get("/api/search", params={"q": "a"})
    assert res_short.status_code == 422

    res_bad_lat = client.get("/api/search", params={"q": "Paris", "lat": 95.0, "lng": 2.0})
    assert res_bad_lat.status_code == 422


def test_search_handles_upstream_error(client, monkeypatch):
    geocoding._cache.clear()
    geocoding._last_request_ts = 0.0

    async def fake_get_error(self, url, params=None, headers=None):
        return DummyResponse({}, status_code=503)

    monkeypatch.setattr(httpx.AsyncClient, "get", fake_get_error)
    res = client.get("/api/search", params={"q": "Unknown Place Test"})
    assert res.status_code == 502
