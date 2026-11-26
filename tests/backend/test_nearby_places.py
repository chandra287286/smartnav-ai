import httpx

from app.services import places


class DummyOverpassResponse:
    def __init__(self, payload, status_code=200):
        self._payload = payload
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            req = httpx.Request("POST", "https://overpass-api.de/api/interpreter")
            resp = httpx.Response(self.status_code, request=req)
            raise httpx.HTTPStatusError("Overpass error", request=req, response=resp)

    def json(self):
        return self._payload


def test_nearby_places_sorts_by_distance(client, monkeypatch):
    places._places_cache.clear()

    async def fake_post(self, url, data=None, headers=None):
        return DummyOverpassResponse(
            {
                "elements": [
                    {
                        "type": "node",
                        "id": 2,
                        "lat": 37.7850,
                        "lon": -122.4194,
                        "tags": {"name": "Far Cafe", "amenity": "cafe"},
                    },
                    {
                        "type": "node",
                        "id": 1,
                        "lat": 37.7755,
                        "lon": -122.4194,
                        "tags": {
                            "name": "Corner Bistro",
                            "amenity": "restaurant",
                            "addr:street": "Market St",
                        },
                    },
                ]
            }
        )

    monkeypatch.setattr(httpx.AsyncClient, "post", fake_post)

    res = client.get(
        "/api/places/nearby",
        params={"lat": 37.7749, "lng": -122.4194, "category": "restaurant", "radius": 1500},
    )
    assert res.status_code == 200
    items = res.json()["places"]
    assert len(items) == 2
    assert items[0]["name"] == "Corner Bistro"
    assert items[0]["distance_meters"] < items[1]["distance_meters"]


def test_nearby_places_rejects_unknown_category(client):
    res = client.get(
        "/api/places/nearby",
        params={"lat": 37.7749, "lng": -122.4194, "category": "spaceship_port"},
    )
    assert res.status_code == 400
