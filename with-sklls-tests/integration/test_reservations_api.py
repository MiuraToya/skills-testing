from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

JST = ZoneInfo("Asia/Tokyo")


def _iso_jst(year: int, month: int, day: int, hour: int, minute: int = 0) -> str:
    return datetime(year, month, day, hour, minute, tzinfo=JST).isoformat()


@pytest.fixture
def room_id(client) -> int:
    response = client.post(
        "/api/v1/rooms", json={"name": "Sakura", "capacity": 4}
    )
    assert response.status_code == 201
    return response.json()["id"]


class TestCreateReservation:
    def test_valid_payload_creates_reservation_and_returns_201(self, client, room_id):
        payload = {
            "room_id": room_id,
            "guest_name": "Alice",
            "attendee_count": 2,
            "start_at": _iso_jst(2026, 5, 1, 10, 0),
            "end_at": _iso_jst(2026, 5, 1, 11, 0),
        }

        response = client.post("/api/v1/reservations", json=payload)

        assert response.status_code == 201
        body = response.json()
        assert body["room_id"] == room_id
        assert body["status"] == "active"
        assert body["canceled_at"] is None
        assert body["id"]

    def test_unknown_room_returns_404_not_found(self, client):
        payload = {
            "room_id": 9999,
            "guest_name": "Alice",
            "attendee_count": 1,
            "start_at": _iso_jst(2026, 5, 1, 10, 0),
            "end_at": _iso_jst(2026, 5, 1, 11, 0),
        }

        response = client.post("/api/v1/reservations", json=payload)

        assert response.status_code == 404
        assert "Room 9999" in response.json()["error"]

    def test_attendee_exceeds_capacity_returns_422(self, client, room_id):
        payload = {
            "room_id": room_id,
            "guest_name": "Alice",
            "attendee_count": 5,  # capacity is 4
            "start_at": _iso_jst(2026, 5, 1, 10, 0),
            "end_at": _iso_jst(2026, 5, 1, 11, 0),
        }

        response = client.post("/api/v1/reservations", json=payload)

        assert response.status_code == 422
        assert "capacity" in response.json()["error"]

    def test_unaligned_slot_returns_422(self, client, room_id):
        payload = {
            "room_id": room_id,
            "guest_name": "Alice",
            "attendee_count": 1,
            "start_at": _iso_jst(2026, 5, 1, 10, 15),
            "end_at": _iso_jst(2026, 5, 1, 11, 0),
        }

        response = client.post("/api/v1/reservations", json=payload)

        assert response.status_code == 422
        assert "30-minute" in response.json()["error"]

    def test_overlapping_booking_returns_409(self, client, room_id):
        first = {
            "room_id": room_id,
            "guest_name": "Alice",
            "attendee_count": 1,
            "start_at": _iso_jst(2026, 5, 1, 10, 0),
            "end_at": _iso_jst(2026, 5, 1, 11, 0),
        }
        client.post("/api/v1/reservations", json=first)

        overlapping = {
            "room_id": room_id,
            "guest_name": "Bob",
            "attendee_count": 1,
            "start_at": _iso_jst(2026, 5, 1, 10, 30),
            "end_at": _iso_jst(2026, 5, 1, 11, 30),
        }
        response = client.post("/api/v1/reservations", json=overlapping)

        assert response.status_code == 409
        assert "conflict" in response.json()["error"].lower()

    def test_adjacent_booking_returns_201(self, client, room_id):
        client.post(
            "/api/v1/reservations",
            json={
                "room_id": room_id,
                "guest_name": "Alice",
                "attendee_count": 1,
                "start_at": _iso_jst(2026, 5, 1, 10, 0),
                "end_at": _iso_jst(2026, 5, 1, 11, 0),
            },
        )

        response = client.post(
            "/api/v1/reservations",
            json={
                "room_id": room_id,
                "guest_name": "Bob",
                "attendee_count": 1,
                "start_at": _iso_jst(2026, 5, 1, 11, 0),
                "end_at": _iso_jst(2026, 5, 1, 12, 0),
            },
        )

        assert response.status_code == 201


class TestCancelReservation:
    def test_valid_cancel_returns_200_with_canceled_status(self, client, room_id):
        created = client.post(
            "/api/v1/reservations",
            json={
                "room_id": room_id,
                "guest_name": "Alice",
                "attendee_count": 1,
                "start_at": _iso_jst(2026, 5, 10, 14, 0),
                "end_at": _iso_jst(2026, 5, 10, 15, 0),
            },
        ).json()

        response = client.post(
            f"/api/v1/reservations/{created['id']}/cancel",
            json={"canceled_at": _iso_jst(2026, 5, 10, 12, 0)},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "canceled"
        assert body["canceled_at"] is not None

    def test_unknown_reservation_returns_404(self, client):
        response = client.post(
            "/api/v1/reservations/00000000-0000-0000-0000-000000000000/cancel",
            json={"canceled_at": _iso_jst(2026, 5, 10, 12, 0)},
        )

        assert response.status_code == 404

    def test_cancel_inside_deadline_returns_422(self, client, room_id):
        created = client.post(
            "/api/v1/reservations",
            json={
                "room_id": room_id,
                "guest_name": "Alice",
                "attendee_count": 1,
                "start_at": _iso_jst(2026, 5, 10, 14, 0),
                "end_at": _iso_jst(2026, 5, 10, 15, 0),
            },
        ).json()

        response = client.post(
            f"/api/v1/reservations/{created['id']}/cancel",
            json={"canceled_at": _iso_jst(2026, 5, 10, 13, 30)},
        )

        assert response.status_code == 422
        assert "60 minutes" in response.json()["error"]

    def test_canceled_slot_can_be_rebooked(self, client, room_id):
        created = client.post(
            "/api/v1/reservations",
            json={
                "room_id": room_id,
                "guest_name": "Alice",
                "attendee_count": 1,
                "start_at": _iso_jst(2026, 5, 10, 14, 0),
                "end_at": _iso_jst(2026, 5, 10, 15, 0),
            },
        ).json()
        client.post(
            f"/api/v1/reservations/{created['id']}/cancel",
            json={"canceled_at": _iso_jst(2026, 5, 10, 12, 0)},
        )

        response = client.post(
            "/api/v1/reservations",
            json={
                "room_id": room_id,
                "guest_name": "Bob",
                "attendee_count": 1,
                "start_at": _iso_jst(2026, 5, 10, 14, 0),
                "end_at": _iso_jst(2026, 5, 10, 15, 0),
            },
        )

        assert response.status_code == 201
