def test_register_login_profile_and_duplicates(client):
    reg = client.post(
        "/api/auth/register",
        json={
            "full_name": "Maya Lin",
            "email": "maya@example.com",
            "password": "securepassword123",
        },
    )
    assert reg.status_code == 201
    data = reg.json()
    assert "access_token" in data
    assert data["user"]["email"] == "maya@example.com"
    token = data["access_token"]

    # Duplicate email fails with 409
    dup = client.post(
        "/api/auth/register",
        json={
            "full_name": "Maya Duplicate",
            "email": "maya@example.com",
            "password": "anotherpassword",
        },
    )
    assert dup.status_code == 409

    # Wrong password rejected
    bad_login = client.post(
        "/api/auth/login",
        json={"email": "maya@example.com", "password": "wrong"},
    )
    assert bad_login.status_code == 401

    # Valid login
    good_login = client.post(
        "/api/auth/login",
        json={"email": "maya@example.com", "password": "securepassword123"},
    )
    assert good_login.status_code == 200

    # Profile requires valid token
    unauth = client.get("/api/auth/profile")
    assert unauth.status_code == 401

    prof = client.get("/api/auth/profile", headers={"Authorization": f"Bearer {token}"})
    assert prof.status_code == 200
    assert prof.json()["full_name"] == "Maya Lin"


def test_favorites_and_history_persistence(client):
    reg = client.post(
        "/api/auth/register",
        json={"full_name": "Alex", "email": "alex@example.com", "password": "password123"},
    )
    token = reg.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Add favorite
    fav_res = client.post(
        "/api/favorites",
        headers=headers,
        json={
            "label": "Central Library",
            "address": "100 Main St",
            "category": "favorite",
            "lat": 37.7793,
            "lng": -122.4193,
        },
    )
    assert fav_res.status_code == 201
    fav_id = fav_res.json()["id"]

    list_res = client.get("/api/favorites", headers=headers)
    assert list_res.status_code == 200
    assert len(list_res.json()["items"]) == 1
    assert list_res.json()["items"][0]["label"] == "Central Library"

    # Delete favorite
    del_res = client.delete(f"/api/favorites/{fav_id}", headers=headers)
    assert del_res.status_code == 204
    assert client.get("/api/favorites", headers=headers).json()["items"] == []

    # Navigation session history
    start_res = client.post(
        "/api/navigation/start",
        headers=headers,
        json={
            "origin_lat": 37.7749,
            "origin_lng": -122.4194,
            "dest_lat": 37.7849,
            "dest_lng": -122.4094,
            "origin_label": "Start",
            "destination_label": "Dest",
            "profile": "driving",
            "route_distance_meters": 1500,
            "route_duration_seconds": 240,
        },
    )
    assert start_res.status_code == 201
    sess_id = start_res.json()["session_id"]

    stop_res = client.post(
        "/api/navigation/stop",
        headers=headers,
        json={"session_id": sess_id, "status": "completed"},
    )
    assert stop_res.status_code == 200

    hist_res = client.get("/api/history", headers=headers)
    assert hist_res.status_code == 200
    assert len(hist_res.json()["sessions"]) == 1
    assert hist_res.json()["sessions"][0]["status"] == "completed"
