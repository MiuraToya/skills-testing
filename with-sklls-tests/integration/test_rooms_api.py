class TestCreateRoom:
    def test_valid_payload_creates_room_and_returns_201(self, client):
        response = client.post(
            "/api/v1/rooms",
            json={"name": "Sakura", "capacity": 8},
        )

        assert response.status_code == 201
        body = response.json()
        assert body["name"] == "Sakura"
        assert body["capacity"] == 8
        assert isinstance(body["id"], int) and body["id"] > 0

    def test_duplicate_name_returns_409_conflict(self, client):
        client.post("/api/v1/rooms", json={"name": "Sakura", "capacity": 8})

        response = client.post(
            "/api/v1/rooms", json={"name": "Sakura", "capacity": 4}
        )

        assert response.status_code == 409
        assert "already exists" in response.json()["error"]

    def test_zero_capacity_returns_422_unprocessable(self, client):
        response = client.post(
            "/api/v1/rooms",
            json={"name": "Sakura", "capacity": 0},
        )

        # Pydantic field validation rejects before reaching the service.
        assert response.status_code == 422

    def test_blank_name_returns_422_unprocessable(self, client):
        response = client.post(
            "/api/v1/rooms",
            json={"name": "", "capacity": 4},
        )

        assert response.status_code == 422


class TestListRooms:
    def test_returns_empty_list_when_no_rooms_persisted(self, client):
        response = client.get("/api/v1/rooms")

        assert response.status_code == 200
        assert response.json() == []

    def test_returns_persisted_rooms(self, client):
        client.post("/api/v1/rooms", json={"name": "Sakura", "capacity": 8})
        client.post("/api/v1/rooms", json={"name": "Hinoki", "capacity": 4})

        response = client.get("/api/v1/rooms")

        assert response.status_code == 200
        names = [room["name"] for room in response.json()]
        assert names == ["Sakura", "Hinoki"]
