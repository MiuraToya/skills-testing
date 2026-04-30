from fastapi.testclient import TestClient


class TestCreateRoom:
    def test_returns_201_with_created_room(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/rooms",
            json={"name": "Conference A", "capacity": 10},
        )

        assert response.status_code == 201
        body = response.json()
        assert body["name"] == "Conference A"
        assert body["capacity"] == 10
        assert isinstance(body["id"], int)
        assert body["id"] > 0

    def test_duplicate_name_returns_409(self, client: TestClient) -> None:
        client.post(
            "/api/v1/rooms",
            json={"name": "Conference A", "capacity": 10},
        )

        response = client.post(
            "/api/v1/rooms",
            json={"name": "Conference A", "capacity": 8},
        )

        assert response.status_code == 409
        assert "error" in response.json()

    def test_zero_capacity_returns_422(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/rooms",
            json={"name": "Conference A", "capacity": 0},
        )

        assert response.status_code == 422

    def test_negative_capacity_returns_422(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/rooms",
            json={"name": "Conference A", "capacity": -5},
        )

        assert response.status_code == 422

    def test_capacity_over_limit_returns_422(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/rooms",
            json={"name": "Conference A", "capacity": 201},
        )

        assert response.status_code == 422

    def test_empty_name_returns_422(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/rooms",
            json={"name": "", "capacity": 10},
        )

        assert response.status_code == 422

    def test_missing_name_returns_422(self, client: TestClient) -> None:
        response = client.post(
            "/api/v1/rooms",
            json={"capacity": 10},
        )

        assert response.status_code == 422


class TestListRooms:
    def test_empty_list_when_no_rooms(self, client: TestClient) -> None:
        response = client.get("/api/v1/rooms")

        assert response.status_code == 200
        assert response.json() == []

    def test_returns_created_rooms_in_id_order(self, client: TestClient) -> None:
        client.post("/api/v1/rooms", json={"name": "Room A", "capacity": 4})
        client.post("/api/v1/rooms", json={"name": "Room B", "capacity": 8})
        client.post("/api/v1/rooms", json={"name": "Room C", "capacity": 12})

        response = client.get("/api/v1/rooms")

        assert response.status_code == 200
        rooms = response.json()
        assert len(rooms) == 3
        names = [room["name"] for room in rooms]
        assert names == ["Room A", "Room B", "Room C"]
        ids = [room["id"] for room in rooms]
        assert ids == sorted(ids)
