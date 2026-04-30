from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.domain.exceptions import ReservationRuleError
from app.domain.reservation import Reservation, ReservationStatus

JST = ZoneInfo("Asia/Tokyo")
TZ_NAME = "Asia/Tokyo"


def _start_end(start_hour: int, end_hour: int, *, day: int = 4) -> tuple[datetime, datetime]:
    start = datetime(2030, 6, day, start_hour, 0, tzinfo=JST)
    end = datetime(2030, 6, day, end_hour, 0, tzinfo=JST)
    return start, end


class TestReservationCreate:
    def test_create_with_valid_data_succeeds(self) -> None:
        start, end = _start_end(10, 11)

        reservation = Reservation.create(
            room_id=1,
            guest_name="Alice",
            attendee_count=4,
            start_at=start,
            end_at=end,
            timezone=TZ_NAME,
        )

        assert reservation.room_id == 1
        assert reservation.guest_name == "Alice"
        assert reservation.attendee_count == 4
        assert reservation.start_at == start.astimezone(UTC)
        assert reservation.end_at == end.astimezone(UTC)
        assert reservation.timezone == TZ_NAME
        assert reservation.status == ReservationStatus.ACTIVE
        assert reservation.canceled_at is None
        assert reservation.id  # uuid string

    def test_guest_name_is_stripped(self) -> None:
        start, end = _start_end(10, 11)

        reservation = Reservation.create(
            room_id=1,
            guest_name="  Bob  ",
            attendee_count=2,
            start_at=start,
            end_at=end,
            timezone=TZ_NAME,
        )

        assert reservation.guest_name == "Bob"

    def test_direct_instantiation_raises(self) -> None:
        start, end = _start_end(10, 11)
        now = datetime.now(tz=UTC)

        with pytest.raises(ReservationRuleError):
            Reservation(
                id="00000000-0000-0000-0000-000000000000",
                room_id=1,
                guest_name="Alice",
                attendee_count=1,
                start_at=start.astimezone(UTC),
                end_at=end.astimezone(UTC),
                timezone=TZ_NAME,
                status=ReservationStatus.ACTIVE,
                created_at=now,
                canceled_at=None,
            )

    def test_reconstruct_with_naive_datetime_raises(self) -> None:
        naive_start = datetime(2030, 6, 4, 10, 0)
        naive_end = datetime(2030, 6, 4, 11, 0)

        with pytest.raises(ReservationRuleError, match="timezone"):
            Reservation.reconstruct(
                id="abc",
                room_id=1,
                guest_name="Alice",
                attendee_count=1,
                start_at=naive_start,
                end_at=naive_end,
                timezone=TZ_NAME,
                status=ReservationStatus.ACTIVE,
                created_at=datetime.now(tz=UTC),
                canceled_at=None,
            )

    def test_start_after_end_raises(self) -> None:
        start, end = _start_end(11, 10)

        with pytest.raises(ReservationRuleError, match="start_at must be earlier"):
            Reservation.create(
                room_id=1,
                guest_name="Alice",
                attendee_count=1,
                start_at=start,
                end_at=end,
                timezone=TZ_NAME,
            )

    def test_start_equal_end_raises(self) -> None:
        start, end = _start_end(10, 10)

        with pytest.raises(ReservationRuleError):
            Reservation.create(
                room_id=1,
                guest_name="Alice",
                attendee_count=1,
                start_at=start,
                end_at=end,
                timezone=TZ_NAME,
            )

    @pytest.mark.parametrize(
        "minute",
        [1, 15, 29, 31, 45, 59],
    )
    def test_non_30_minute_slot_raises(self, minute: int) -> None:
        start = datetime(2030, 6, 4, 10, minute, tzinfo=JST)
        end = datetime(2030, 6, 4, 12, 0, tzinfo=JST)

        with pytest.raises(ReservationRuleError, match="30-minute slots"):
            Reservation.create(
                room_id=1,
                guest_name="Alice",
                attendee_count=1,
                start_at=start,
                end_at=end,
                timezone=TZ_NAME,
            )

    def test_non_zero_seconds_raises(self) -> None:
        start = datetime(2030, 6, 4, 10, 0, 30, tzinfo=JST)
        end = datetime(2030, 6, 4, 11, 0, tzinfo=JST)

        with pytest.raises(ReservationRuleError):
            Reservation.create(
                room_id=1,
                guest_name="Alice",
                attendee_count=1,
                start_at=start,
                end_at=end,
                timezone=TZ_NAME,
            )

    def test_30_minute_slot_succeeds(self) -> None:
        start = datetime(2030, 6, 4, 10, 30, tzinfo=JST)
        end = datetime(2030, 6, 4, 11, 0, tzinfo=JST)

        reservation = Reservation.create(
            room_id=1,
            guest_name="Alice",
            attendee_count=1,
            start_at=start,
            end_at=end,
            timezone=TZ_NAME,
        )

        assert reservation.start_at.minute == 30 or reservation.start_at.minute == 0

    def test_start_before_business_hours_raises(self) -> None:
        start, end = _start_end(8, 10)

        with pytest.raises(ReservationRuleError, match="start time must be within"):
            Reservation.create(
                room_id=1,
                guest_name="Alice",
                attendee_count=1,
                start_at=start,
                end_at=end,
                timezone=TZ_NAME,
            )

    def test_start_at_close_time_raises(self) -> None:
        start, end = _start_end(18, 19)

        with pytest.raises(ReservationRuleError):
            Reservation.create(
                room_id=1,
                guest_name="Alice",
                attendee_count=1,
                start_at=start,
                end_at=end,
                timezone=TZ_NAME,
            )

    def test_end_after_close_time_raises(self) -> None:
        start = datetime(2030, 6, 4, 17, 30, tzinfo=JST)
        end = datetime(2030, 6, 4, 18, 30, tzinfo=JST)

        with pytest.raises(ReservationRuleError, match="end time must be within"):
            Reservation.create(
                room_id=1,
                guest_name="Alice",
                attendee_count=1,
                start_at=start,
                end_at=end,
                timezone=TZ_NAME,
            )

    def test_open_to_close_succeeds(self) -> None:
        start, end = _start_end(9, 18)

        reservation = Reservation.create(
            room_id=1,
            guest_name="Alice",
            attendee_count=1,
            start_at=start,
            end_at=end,
            timezone=TZ_NAME,
        )

        assert reservation.start_at.astimezone(JST).hour == 9
        assert reservation.end_at.astimezone(JST).hour == 18

    def test_spanning_two_dates_raises(self) -> None:
        start = datetime(2030, 6, 4, 17, 0, tzinfo=JST)
        end = datetime(2030, 6, 5, 10, 0, tzinfo=JST)

        with pytest.raises(ReservationRuleError):
            Reservation.create(
                room_id=1,
                guest_name="Alice",
                attendee_count=1,
                start_at=start,
                end_at=end,
                timezone=TZ_NAME,
            )

    def test_zero_attendee_raises(self) -> None:
        start, end = _start_end(10, 11)

        with pytest.raises(ReservationRuleError, match="Attendee"):
            Reservation.create(
                room_id=1,
                guest_name="Alice",
                attendee_count=0,
                start_at=start,
                end_at=end,
                timezone=TZ_NAME,
            )

    def test_negative_attendee_raises(self) -> None:
        start, end = _start_end(10, 11)

        with pytest.raises(ReservationRuleError):
            Reservation.create(
                room_id=1,
                guest_name="Alice",
                attendee_count=-1,
                start_at=start,
                end_at=end,
                timezone=TZ_NAME,
            )

    def test_empty_guest_name_raises(self) -> None:
        start, end = _start_end(10, 11)

        with pytest.raises(ReservationRuleError, match="Guest name"):
            Reservation.create(
                room_id=1,
                guest_name="   ",
                attendee_count=1,
                start_at=start,
                end_at=end,
                timezone=TZ_NAME,
            )

    def test_non_positive_room_id_raises(self) -> None:
        start, end = _start_end(10, 11)

        with pytest.raises(ReservationRuleError, match="Room ID"):
            Reservation.create(
                room_id=0,
                guest_name="Alice",
                attendee_count=1,
                start_at=start,
                end_at=end,
                timezone=TZ_NAME,
            )


class TestReservationOverlaps:
    def _build(self, start_hour: int, end_hour: int) -> Reservation:
        start, end = _start_end(start_hour, end_hour)
        return Reservation.create(
            room_id=1,
            guest_name="Alice",
            attendee_count=1,
            start_at=start,
            end_at=end,
            timezone=TZ_NAME,
        )

    def test_separated_does_not_overlap(self) -> None:
        existing = self._build(10, 11)
        other_start, other_end = _start_end(13, 14)

        assert existing.overlaps(other_start, other_end) is False

    def test_adjacent_at_end_does_not_overlap(self) -> None:
        existing = self._build(10, 11)
        other_start, other_end = _start_end(11, 12)

        assert existing.overlaps(other_start, other_end) is False

    def test_adjacent_at_start_does_not_overlap(self) -> None:
        existing = self._build(11, 12)
        other_start, other_end = _start_end(10, 11)

        assert existing.overlaps(other_start, other_end) is False

    def test_partially_overlapping_overlaps(self) -> None:
        existing = self._build(10, 12)
        other_start, other_end = _start_end(11, 13)

        assert existing.overlaps(other_start, other_end) is True

    def test_fully_contained_overlaps(self) -> None:
        existing = self._build(10, 14)
        other_start, other_end = _start_end(11, 12)

        assert existing.overlaps(other_start, other_end) is True

    def test_identical_overlaps(self) -> None:
        existing = self._build(10, 11)
        other_start, other_end = _start_end(10, 11)

        assert existing.overlaps(other_start, other_end) is True


class TestReservationCancel:
    def _active(self, start_hour: int = 10) -> Reservation:
        start, end = _start_end(start_hour, start_hour + 1)
        return Reservation.create(
            room_id=1,
            guest_name="Alice",
            attendee_count=1,
            start_at=start,
            end_at=end,
            timezone=TZ_NAME,
        )

    def test_cancel_well_before_deadline_succeeds(self) -> None:
        reservation = self._active()
        cancel_at = reservation.start_at - timedelta(hours=2)

        reservation.cancel(cancel_at)

        assert reservation.status == ReservationStatus.CANCELED
        assert reservation.canceled_at == cancel_at

    def test_cancel_just_inside_deadline_succeeds(self) -> None:
        reservation = self._active()
        cancel_at = reservation.start_at - timedelta(minutes=61)

        reservation.cancel(cancel_at)

        assert reservation.status == ReservationStatus.CANCELED

    def test_cancel_at_exact_deadline_raises(self) -> None:
        reservation = self._active()
        cancel_at = reservation.start_at - timedelta(minutes=60)

        with pytest.raises(ReservationRuleError, match="Cancellation"):
            reservation.cancel(cancel_at)

    def test_cancel_after_deadline_raises(self) -> None:
        reservation = self._active()
        cancel_at = reservation.start_at - timedelta(minutes=30)

        with pytest.raises(ReservationRuleError):
            reservation.cancel(cancel_at)

    def test_cancel_already_canceled_raises(self) -> None:
        reservation = self._active()
        reservation.cancel(reservation.start_at - timedelta(hours=2))

        with pytest.raises(ReservationRuleError, match="already canceled"):
            reservation.cancel(reservation.start_at - timedelta(hours=3))

    def test_cancel_with_naive_datetime_raises(self) -> None:
        reservation = self._active()

        with pytest.raises(ReservationRuleError, match="timezone"):
            reservation.cancel(datetime(2030, 6, 4, 5, 0))


class TestReservationReconstruct:
    def test_reconstruct_active_reservation(self) -> None:
        start, end = _start_end(10, 11)
        created = datetime.now(tz=UTC)

        reservation = Reservation.reconstruct(
            id="abc-123",
            room_id=1,
            guest_name="Alice",
            attendee_count=1,
            start_at=start.astimezone(UTC),
            end_at=end.astimezone(UTC),
            timezone=TZ_NAME,
            status=ReservationStatus.ACTIVE,
            created_at=created,
            canceled_at=None,
        )

        assert reservation.id == "abc-123"
        assert reservation.status == ReservationStatus.ACTIVE

    def test_reconstruct_canceled_reservation(self) -> None:
        start, end = _start_end(10, 11)
        created = datetime.now(tz=UTC)
        canceled = datetime.now(tz=UTC)

        reservation = Reservation.reconstruct(
            id="abc-123",
            room_id=1,
            guest_name="Alice",
            attendee_count=1,
            start_at=start.astimezone(UTC),
            end_at=end.astimezone(UTC),
            timezone=TZ_NAME,
            status=ReservationStatus.CANCELED,
            created_at=created,
            canceled_at=canceled,
        )

        assert reservation.status == ReservationStatus.CANCELED
        assert reservation.canceled_at == canceled

    def test_reconstruct_canceled_without_canceled_at_raises(self) -> None:
        start, end = _start_end(10, 11)
        created = datetime.now(tz=UTC)

        with pytest.raises(ReservationRuleError, match="canceled_at"):
            Reservation.reconstruct(
                id="abc-123",
                room_id=1,
                guest_name="Alice",
                attendee_count=1,
                start_at=start.astimezone(UTC),
                end_at=end.astimezone(UTC),
                timezone=TZ_NAME,
                status=ReservationStatus.CANCELED,
                created_at=created,
                canceled_at=None,
            )

    def test_reconstruct_active_with_canceled_at_raises(self) -> None:
        start, end = _start_end(10, 11)
        created = datetime.now(tz=UTC)
        canceled = datetime.now(tz=UTC)

        with pytest.raises(ReservationRuleError, match="must not have canceled_at"):
            Reservation.reconstruct(
                id="abc-123",
                room_id=1,
                guest_name="Alice",
                attendee_count=1,
                start_at=start.astimezone(UTC),
                end_at=end.astimezone(UTC),
                timezone=TZ_NAME,
                status=ReservationStatus.ACTIVE,
                created_at=created,
                canceled_at=canceled,
            )
