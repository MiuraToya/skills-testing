from datetime import UTC, datetime
from uuid import uuid4
from zoneinfo import ZoneInfo

import pytest

from app.application.dto import (
    CancelReservationCommand,
    CreateReservationCommand,
    CreateRoomCommand,
)
from app.application.exceptions import (
    ConflictError,
    NotFoundError,
    ValidationError,
)
from app.application.services import ReservationService, RoomService
from app.domain.reservation import Reservation, ReservationStatus

from .fakes import FakeUnitOfWork

JST = ZoneInfo("Asia/Tokyo")
TZ = "Asia/Tokyo"


def _jst(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=JST)


@pytest.fixture
def uow_with_room() -> FakeUnitOfWork:
    uow = FakeUnitOfWork()
    RoomService(uow=uow).create_room(CreateRoomCommand(name="Sakura", capacity=4))
    # New UoW state: previous create already committed; reset committed flag so
    # test assertions about "did the service commit?" stay focused on the
    # operation under test.
    uow.committed = False
    return uow


class TestCreateReservation:
    def test_valid_command_persists_reservation_and_commits(self, uow_with_room):
        service = ReservationService(uow=uow_with_room, timezone=TZ)
        command = CreateReservationCommand(
            room_id=1,
            guest_name="Alice",
            attendee_count=2,
            start_at=_jst(2026, 5, 1, 10, 0),
            end_at=_jst(2026, 5, 1, 11, 0),
        )

        reservation = service.create_reservation(command)

        assert reservation.room_id == 1
        assert reservation.status == ReservationStatus.ACTIVE
        assert uow_with_room.committed is True
        assert uow_with_room.reservations.get(reservation.id) is not None

    def test_unknown_room_raises_not_found_error(self):
        uow = FakeUnitOfWork()
        service = ReservationService(uow=uow, timezone=TZ)
        command = CreateReservationCommand(
            room_id=999,
            guest_name="Alice",
            attendee_count=1,
            start_at=_jst(2026, 5, 1, 10, 0),
            end_at=_jst(2026, 5, 1, 11, 0),
        )

        with pytest.raises(NotFoundError, match="Room 999"):
            service.create_reservation(command)

        assert uow.committed is False

    def test_attendee_exceeds_capacity_raises_validation_error(self, uow_with_room):
        service = ReservationService(uow=uow_with_room, timezone=TZ)
        command = CreateReservationCommand(
            room_id=1,
            guest_name="Alice",
            attendee_count=5,  # capacity is 4
            start_at=_jst(2026, 5, 1, 10, 0),
            end_at=_jst(2026, 5, 1, 11, 0),
        )

        with pytest.raises(ValidationError, match="capacity"):
            service.create_reservation(command)

        assert uow_with_room.committed is False

    def test_unaligned_slot_raises_validation_error(self, uow_with_room):
        service = ReservationService(uow=uow_with_room, timezone=TZ)
        command = CreateReservationCommand(
            room_id=1,
            guest_name="Alice",
            attendee_count=1,
            start_at=_jst(2026, 5, 1, 10, 15),
            end_at=_jst(2026, 5, 1, 11, 0),
        )

        with pytest.raises(ValidationError, match="30-minute"):
            service.create_reservation(command)

    def test_overlap_with_existing_active_raises_conflict_error(self, uow_with_room):
        service = ReservationService(uow=uow_with_room, timezone=TZ)
        first = CreateReservationCommand(
            room_id=1,
            guest_name="Alice",
            attendee_count=1,
            start_at=_jst(2026, 5, 1, 10, 0),
            end_at=_jst(2026, 5, 1, 11, 0),
        )
        service.create_reservation(first)

        overlapping = CreateReservationCommand(
            room_id=1,
            guest_name="Bob",
            attendee_count=1,
            start_at=_jst(2026, 5, 1, 10, 30),
            end_at=_jst(2026, 5, 1, 11, 30),
        )
        with pytest.raises(ConflictError, match="conflicts"):
            service.create_reservation(overlapping)

    def test_adjacent_booking_does_not_conflict(self, uow_with_room):
        service = ReservationService(uow=uow_with_room, timezone=TZ)
        service.create_reservation(
            CreateReservationCommand(
                room_id=1,
                guest_name="Alice",
                attendee_count=1,
                start_at=_jst(2026, 5, 1, 10, 0),
                end_at=_jst(2026, 5, 1, 11, 0),
            )
        )

        adjacent = service.create_reservation(
            CreateReservationCommand(
                room_id=1,
                guest_name="Bob",
                attendee_count=1,
                start_at=_jst(2026, 5, 1, 11, 0),
                end_at=_jst(2026, 5, 1, 12, 0),
            )
        )

        assert adjacent.status == ReservationStatus.ACTIVE

    def test_canceled_reservation_does_not_block_new_booking(self, uow_with_room):
        service = ReservationService(uow=uow_with_room, timezone=TZ)
        existing = service.create_reservation(
            CreateReservationCommand(
                room_id=1,
                guest_name="Alice",
                attendee_count=1,
                start_at=_jst(2026, 5, 10, 14, 0),
                end_at=_jst(2026, 5, 10, 15, 0),
            )
        )
        service.cancel_reservation(
            CancelReservationCommand(
                reservation_id=existing.id,
                canceled_at=_jst(2026, 5, 10, 12, 0).astimezone(UTC),
            )
        )

        replacement = service.create_reservation(
            CreateReservationCommand(
                room_id=1,
                guest_name="Bob",
                attendee_count=1,
                start_at=_jst(2026, 5, 10, 14, 0),
                end_at=_jst(2026, 5, 10, 15, 0),
            )
        )

        assert replacement.status == ReservationStatus.ACTIVE


class TestCancelReservation:
    def test_valid_command_marks_canceled_and_commits(self, uow_with_room):
        service = ReservationService(uow=uow_with_room, timezone=TZ)
        created = service.create_reservation(
            CreateReservationCommand(
                room_id=1,
                guest_name="Alice",
                attendee_count=1,
                start_at=_jst(2026, 5, 10, 14, 0),
                end_at=_jst(2026, 5, 10, 15, 0),
            )
        )
        uow_with_room.committed = False

        canceled = service.cancel_reservation(
            CancelReservationCommand(
                reservation_id=created.id,
                canceled_at=_jst(2026, 5, 10, 12, 0).astimezone(UTC),
            )
        )

        assert canceled.status == ReservationStatus.CANCELED
        assert canceled.canceled_at is not None
        assert uow_with_room.committed is True

    def test_unknown_reservation_raises_not_found_error(self, uow_with_room):
        service = ReservationService(uow=uow_with_room, timezone=TZ)
        unknown_id = str(uuid4())

        with pytest.raises(NotFoundError, match=unknown_id):
            service.cancel_reservation(
                CancelReservationCommand(
                    reservation_id=unknown_id,
                    canceled_at=_jst(2026, 5, 10, 12, 0).astimezone(UTC),
                )
            )

    def test_cancel_inside_deadline_raises_validation_error(self, uow_with_room):
        service = ReservationService(uow=uow_with_room, timezone=TZ)
        created = service.create_reservation(
            CreateReservationCommand(
                room_id=1,
                guest_name="Alice",
                attendee_count=1,
                start_at=_jst(2026, 5, 10, 14, 0),
                end_at=_jst(2026, 5, 10, 15, 0),
            )
        )
        too_late = _jst(2026, 5, 10, 13, 30).astimezone(UTC)

        with pytest.raises(ValidationError, match="60 minutes"):
            service.cancel_reservation(
                CancelReservationCommand(
                    reservation_id=created.id,
                    canceled_at=too_late,
                )
            )
