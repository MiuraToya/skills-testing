from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

JST = ZoneInfo("Asia/Tokyo")


def _iso(dt: datetime) -> str:
    return dt.isoformat()


def _create_room(client: TestClient, name: str = "Conference A", capacity: int = 10) -> int:
    response = client.post(
        "/api/v1/rooms",
        json={"name": name, "capacity": capacity},
    )
    assert response.status_code == 201
    return response.json()["id"]


def _slot(start_hour: int, end_hour: int, *, day: int = 4) -> tuple[str, str]:
    start = datetime(2030, 6, day, start_hour, 0, tzinfo=JST)
    end = datetime(2030, 6, day, end_hour, 0, tzinfo=JST)
    return _iso(start), _iso(end)


@pytest.fixture
def room_id(client: TestClient) -> int:
    return _create_room(client)


class TestCreateReservation:
    def test_succeeds_with_valid_payload(self, client: TestClient, room_id: int) -> None:
        start_at, end_at = _slot(10, 11)

        response = client.post(
            "/api/v1/reservations",
            json={
                "room_id": room_id,
                "guest_name": "Alice",
                "attendee_count": 4,
                "start_at": start_at,
                "end_at": end_at,
            },
        )

        assert response.status_code == 201
        body = response.json()
        assert body["room_id"] == room_id
        assert body["guest_name"] == "Alice"
        assert body["attendee_count"] == 4
        assert body["status"] == "active"
        assert body["canceled_at"] is None
        assert isinstance(body["id"], str) and body["id"]

    def test_non_existent_room_returns_404(self, client: TestClient) -> None:
        start_at, end_at = _slot(10, 11)

        response = client.post(
            "/api/v1/reservations",
            json={
                "room_id": 9999,
                "guest_name": "Alice",
                "attendee_count": 1,
                "start_at": start_at,
                "end_at": end_at,
            },
        )

        assert response.status_code == 404
        assert "error" in response.json()

    def test_attendees_exceeding_capacity_returns_422(self, client: TestClient) -> None:
        small_room_id = _create_room(client, name="Small", capacity=4)
        start_at, end_at = _slot(10, 11)

        response = client.post(
            "/api/v1/reservations",
            json={
                "room_id": small_room_id,
                "guest_name": "Alice",
                "attendee_count": 5,
                "start_at": start_at,
                "end_at": end_at,
            },
        )

        assert response.status_code == 422

    def test_attendee_count_at_capacity_succeeds(self, client: TestClient) -> None:
        small_room_id = _create_room(client, name="Small", capacity=4)
        start_at, end_at = _slot(10, 11)

        response = client.post(
            "/api/v1/reservations",
            json={
                "room_id": small_room_id,
                "guest_name": "Alice",
                "attendee_count": 4,
                "start_at": start_at,
                "end_at": end_at,
            },
        )

        assert response.status_code == 201

    def test_overlapping_returns_409(self, client: TestClient, room_id: int) -> None:
        start_at, end_at = _slot(10, 12)
        first = client.post(
            "/api/v1/reservations",
            json={
                "room_id": room_id,
                "guest_name": "Alice",
                "attendee_count": 2,
                "start_at": start_at,
                "end_at": end_at,
            },
        )
        assert first.status_code == 201

        overlap_start, overlap_end = _slot(11, 13)
        response = client.post(
            "/api/v1/reservations",
            json={
                "room_id": room_id,
                "guest_name": "Bob",
                "attendee_count": 1,
                "start_at": overlap_start,
                "end_at": overlap_end,
            },
        )

        assert response.status_code == 409

    def test_adjacent_at_boundary_succeeds(self, client: TestClient, room_id: int) -> None:
        start_at, end_at = _slot(10, 11)
        first = client.post(
            "/api/v1/reservations",
            json={
                "room_id": room_id,
                "guest_name": "Alice",
                "attendee_count": 2,
                "start_at": start_at,
                "end_at": end_at,
            },
        )
        assert first.status_code == 201

        next_start, next_end = _slot(11, 12)
        response = client.post(
            "/api/v1/reservations",
            json={
                "room_id": room_id,
                "guest_name": "Bob",
                "attendee_count": 2,
                "start_at": next_start,
                "end_at": next_end,
            },
        )

        assert response.status_code == 201

    def test_different_room_does_not_conflict(self, client: TestClient, room_id: int) -> None:
        other_room_id = _create_room(client, name="Conference B", capacity=10)
        start_at, end_at = _slot(10, 11)

        first = client.post(
            "/api/v1/reservations",
            json={
                "room_id": room_id,
                "guest_name": "Alice",
                "attendee_count": 2,
                "start_at": start_at,
                "end_at": end_at,
            },
        )
        assert first.status_code == 201

        response = client.post(
            "/api/v1/reservations",
            json={
                "room_id": other_room_id,
                "guest_name": "Bob",
                "attendee_count": 2,
                "start_at": start_at,
                "end_at": end_at,
            },
        )

        assert response.status_code == 201

    def test_canceled_existing_does_not_conflict(
        self, client: TestClient, room_id: int
    ) -> None:
        start_at_str, end_at_str = _slot(10, 11)
        first_response = client.post(
            "/api/v1/reservations",
            json={
                "room_id": room_id,
                "guest_name": "Alice",
                "attendee_count": 2,
                "start_at": start_at_str,
                "end_at": end_at_str,
            },
        )
        assert first_response.status_code == 201
        reservation_id = first_response.json()["id"]

        cancel_at = datetime(2030, 6, 4, 0, 0, tzinfo=JST)
        cancel_response = client.post(
            f"/api/v1/reservations/{reservation_id}/cancel",
            json={"canceled_at": _iso(cancel_at)},
        )
        assert cancel_response.status_code == 200

        response = client.post(
            "/api/v1/reservations",
            json={
                "room_id": room_id,
                "guest_name": "Bob",
                "attendee_count": 2,
                "start_at": start_at_str,
                "end_at": end_at_str,
            },
        )

        assert response.status_code == 201

    def test_non_30_minute_slot_returns_422(self, client: TestClient, room_id: int) -> None:
        start = datetime(2030, 6, 4, 10, 15, tzinfo=JST)
        end = datetime(2030, 6, 4, 11, 0, tzinfo=JST)

        response = client.post(
            "/api/v1/reservations",
            json={
                "room_id": room_id,
                "guest_name": "Alice",
                "attendee_count": 2,
                "start_at": _iso(start),
                "end_at": _iso(end),
            },
        )

        assert response.status_code == 422

    def test_outside_business_hours_returns_422(
        self, client: TestClient, room_id: int
    ) -> None:
        start = datetime(2030, 6, 4, 8, 0, tzinfo=JST)
        end = datetime(2030, 6, 4, 9, 0, tzinfo=JST)

        response = client.post(
            "/api/v1/reservations",
            json={
                "room_id": room_id,
                "guest_name": "Alice",
                "attendee_count": 2,
                "start_at": _iso(start),
                "end_at": _iso(end),
            },
        )

        assert response.status_code == 422

    def test_end_after_close_returns_422(self, client: TestClient, room_id: int) -> None:
        start = datetime(2030, 6, 4, 17, 30, tzinfo=JST)
        end = datetime(2030, 6, 4, 18, 30, tzinfo=JST)

        response = client.post(
            "/api/v1/reservations",
            json={
                "room_id": room_id,
                "guest_name": "Alice",
                "attendee_count": 2,
                "start_at": _iso(start),
                "end_at": _iso(end),
            },
        )

        assert response.status_code == 422

    def test_start_after_end_returns_422(self, client: TestClient, room_id: int) -> None:
        start_at, end_at = _slot(11, 10)

        response = client.post(
            "/api/v1/reservations",
            json={
                "room_id": room_id,
                "guest_name": "Alice",
                "attendee_count": 2,
                "start_at": start_at,
                "end_at": end_at,
            },
        )

        assert response.status_code == 422

    def test_invalid_room_id_returns_422(self, client: TestClient) -> None:
        start_at, end_at = _slot(10, 11)

        response = client.post(
            "/api/v1/reservations",
            json={
                "room_id": 0,
                "guest_name": "Alice",
                "attendee_count": 2,
                "start_at": start_at,
                "end_at": end_at,
            },
        )

        assert response.status_code == 422


class TestCancelReservation:
    def _create(self, client: TestClient, room_id: int) -> str:
        start_at, end_at = _slot(10, 11)
        response = client.post(
            "/api/v1/reservations",
            json={
                "room_id": room_id,
                "guest_name": "Alice",
                "attendee_count": 2,
                "start_at": start_at,
                "end_at": end_at,
            },
        )
        assert response.status_code == 201
        return response.json()["id"]

    def test_cancel_well_before_start_succeeds(
        self, client: TestClient, room_id: int
    ) -> None:
        reservation_id = self._create(client, room_id)
        cancel_at = datetime(2030, 6, 4, 0, 0, tzinfo=JST)

        response = client.post(
            f"/api/v1/reservations/{reservation_id}/cancel",
            json={"canceled_at": _iso(cancel_at)},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "canceled"
        assert body["canceled_at"] is not None

    def test_cancel_inside_deadline_returns_422(
        self, client: TestClient, room_id: int
    ) -> None:
        reservation_id = self._create(client, room_id)
        cancel_at = datetime(2030, 6, 4, 9, 30, tzinfo=JST)

        response = client.post(
            f"/api/v1/reservations/{reservation_id}/cancel",
            json={"canceled_at": _iso(cancel_at)},
        )

        assert response.status_code == 422

    def test_cancel_at_exact_deadline_returns_422(
        self, client: TestClient, room_id: int
    ) -> None:
        reservation_id = self._create(client, room_id)
        start_at = datetime(2030, 6, 4, 10, 0, tzinfo=JST)
        cancel_at = start_at - timedelta(minutes=60)

        response = client.post(
            f"/api/v1/reservations/{reservation_id}/cancel",
            json={"canceled_at": _iso(cancel_at)},
        )

        assert response.status_code == 422

    def test_cancel_non_existent_returns_404(self, client: TestClient) -> None:
        cancel_at = datetime(2030, 6, 4, 0, 0, tzinfo=JST)

        response = client.post(
            "/api/v1/reservations/00000000-0000-0000-0000-000000000000/cancel",
            json={"canceled_at": _iso(cancel_at)},
        )

        assert response.status_code == 404

    def test_cancel_already_canceled_returns_422(
        self, client: TestClient, room_id: int
    ) -> None:
        reservation_id = self._create(client, room_id)
        cancel_at = datetime(2030, 6, 4, 0, 0, tzinfo=JST)
        first = client.post(
            f"/api/v1/reservations/{reservation_id}/cancel",
            json={"canceled_at": _iso(cancel_at)},
        )
        assert first.status_code == 200

        response = client.post(
            f"/api/v1/reservations/{reservation_id}/cancel",
            json={"canceled_at": _iso(cancel_at - timedelta(hours=1))},
        )

        assert response.status_code == 422
