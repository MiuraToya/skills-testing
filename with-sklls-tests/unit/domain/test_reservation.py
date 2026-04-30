from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app.domain.exceptions import ReservationRuleError
from app.domain.reservation import Reservation, ReservationStatus

JST = ZoneInfo("Asia/Tokyo")


def _jst(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=JST)


class TestReservationCreate:
    def test_create_with_valid_args_returns_active_reservation(self):
        start = _jst(2026, 5, 1, 10, 0)
        end = _jst(2026, 5, 1, 11, 0)

        reservation = Reservation.create(
            room_id=1,
            guest_name="Alice",
            attendee_count=4,
            start_at=start,
            end_at=end,
            timezone="Asia/Tokyo",
        )

        assert reservation.room_id == 1
        assert reservation.guest_name == "Alice"
        assert reservation.attendee_count == 4
        assert reservation.status == ReservationStatus.ACTIVE
        assert reservation.canceled_at is None
        assert reservation.id  # uuid string

    def test_create_normalizes_times_to_utc(self):
        start = _jst(2026, 5, 1, 10, 0)
        end = _jst(2026, 5, 1, 11, 0)

        reservation = Reservation.create(
            room_id=1,
            guest_name="Alice",
            attendee_count=2,
            start_at=start,
            end_at=end,
            timezone="Asia/Tokyo",
        )

        assert reservation.start_at.utcoffset() == timedelta(0)
        assert reservation.end_at.utcoffset() == timedelta(0)
        assert reservation.start_at.astimezone(JST) == start
        assert reservation.end_at.astimezone(JST) == end

    def test_create_strips_whitespace_from_guest_name(self):
        reservation = Reservation.create(
            room_id=1,
            guest_name="  Bob  ",
            attendee_count=1,
            start_at=_jst(2026, 5, 1, 9, 0),
            end_at=_jst(2026, 5, 1, 9, 30),
            timezone="Asia/Tokyo",
        )

        assert reservation.guest_name == "Bob"


class TestDirectInstantiation:
    def test_direct_instantiation_without_internal_flag_raises_rule_error(self):
        with pytest.raises(ReservationRuleError, match="Reservation.create"):
            Reservation(
                id="x",
                room_id=1,
                guest_name="Alice",
                attendee_count=1,
                start_at=_jst(2026, 5, 1, 9, 0),
                end_at=_jst(2026, 5, 1, 9, 30),
                timezone="Asia/Tokyo",
                status=ReservationStatus.ACTIVE,
                created_at=datetime.now(tz=UTC),
                canceled_at=None,
            )


class TestInvariantsOnCreate:
    @pytest.mark.parametrize("invalid_room_id", [0, -1])
    def test_non_positive_room_id_raises_rule_error(self, invalid_room_id):
        with pytest.raises(ReservationRuleError, match="Room ID"):
            Reservation.create(
                room_id=invalid_room_id,
                guest_name="Alice",
                attendee_count=1,
                start_at=_jst(2026, 5, 1, 9, 0),
                end_at=_jst(2026, 5, 1, 9, 30),
                timezone="Asia/Tokyo",
            )

    def test_blank_guest_name_raises_rule_error(self):
        with pytest.raises(ReservationRuleError, match="Guest name"):
            Reservation.create(
                room_id=1,
                guest_name="   ",
                attendee_count=1,
                start_at=_jst(2026, 5, 1, 9, 0),
                end_at=_jst(2026, 5, 1, 9, 30),
                timezone="Asia/Tokyo",
            )

    @pytest.mark.parametrize("invalid_count", [0, -1])
    def test_non_positive_attendee_count_raises_rule_error(self, invalid_count):
        with pytest.raises(ReservationRuleError, match="Attendee count"):
            Reservation.create(
                room_id=1,
                guest_name="Alice",
                attendee_count=invalid_count,
                start_at=_jst(2026, 5, 1, 9, 0),
                end_at=_jst(2026, 5, 1, 9, 30),
                timezone="Asia/Tokyo",
            )

    def test_reconstruct_with_naive_start_at_raises_rule_error(self):
        # `create()` silently localizes naive inputs via astimezone(),
        # so the timezone-aware invariant is enforced through reconstruct.
        with pytest.raises(ReservationRuleError, match="timezone"):
            Reservation.reconstruct(
                id="r1",
                room_id=1,
                guest_name="Alice",
                attendee_count=1,
                start_at=datetime(2026, 5, 1, 9, 0),
                end_at=_jst(2026, 5, 1, 9, 30).astimezone(UTC),
                timezone="Asia/Tokyo",
                status=ReservationStatus.ACTIVE,
                created_at=datetime(2026, 4, 30, 0, 0, tzinfo=UTC),
                canceled_at=None,
            )

    def test_start_after_end_raises_rule_error(self):
        with pytest.raises(ReservationRuleError, match="earlier than end_at"):
            Reservation.create(
                room_id=1,
                guest_name="Alice",
                attendee_count=1,
                start_at=_jst(2026, 5, 1, 11, 0),
                end_at=_jst(2026, 5, 1, 10, 0),
                timezone="Asia/Tokyo",
            )

    @pytest.mark.parametrize(
        "start_minute",
        [1, 15, 29, 31, 45, 59],
    )
    def test_unaligned_minute_raises_rule_error(self, start_minute):
        with pytest.raises(ReservationRuleError, match="30-minute slots"):
            Reservation.create(
                room_id=1,
                guest_name="Alice",
                attendee_count=1,
                start_at=_jst(2026, 5, 1, 10, start_minute),
                end_at=_jst(2026, 5, 1, 11, 0),
                timezone="Asia/Tokyo",
            )

    def test_non_zero_seconds_raises_rule_error(self):
        start = datetime(2026, 5, 1, 10, 0, 1, tzinfo=JST)
        end = _jst(2026, 5, 1, 11, 0)

        with pytest.raises(ReservationRuleError, match="zero seconds"):
            Reservation.create(
                room_id=1,
                guest_name="Alice",
                attendee_count=1,
                start_at=start,
                end_at=end,
                timezone="Asia/Tokyo",
            )

    @pytest.mark.parametrize(
        "start_hour,end_hour",
        [
            (8, 9),  # before open
            (9, 19),  # after close (end exceeds 18:00)
            (18, 19),  # start at close
        ],
    )
    def test_outside_business_hours_raises_rule_error(self, start_hour, end_hour):
        with pytest.raises(ReservationRuleError, match="business hours"):
            Reservation.create(
                room_id=1,
                guest_name="Alice",
                attendee_count=1,
                start_at=_jst(2026, 5, 1, start_hour, 0),
                end_at=_jst(2026, 5, 1, end_hour, 0),
                timezone="Asia/Tokyo",
            )

    def test_business_hours_boundary_open_to_close_is_allowed(self):
        reservation = Reservation.create(
            room_id=1,
            guest_name="Alice",
            attendee_count=1,
            start_at=_jst(2026, 5, 1, 9, 0),
            end_at=_jst(2026, 5, 1, 18, 0),
            timezone="Asia/Tokyo",
        )

        assert reservation.status == ReservationStatus.ACTIVE

    def test_spanning_two_local_dates_raises_rule_error(self):
        # 23:00 JST -> 02:00 UTC on May 2; end 23:30 JST same idea but spans by tz
        start = _jst(2026, 5, 1, 17, 30)
        end = _jst(2026, 5, 2, 9, 30)

        with pytest.raises(ReservationRuleError):
            Reservation.create(
                room_id=1,
                guest_name="Alice",
                attendee_count=1,
                start_at=start,
                end_at=end,
                timezone="Asia/Tokyo",
            )


class TestReconstructStatusConsistency:
    def test_canceled_status_without_canceled_at_raises_rule_error(self):
        with pytest.raises(ReservationRuleError, match="canceled_at"):
            Reservation.reconstruct(
                id="r1",
                room_id=1,
                guest_name="Alice",
                attendee_count=1,
                start_at=_jst(2026, 5, 1, 9, 0).astimezone(UTC),
                end_at=_jst(2026, 5, 1, 9, 30).astimezone(UTC),
                timezone="Asia/Tokyo",
                status=ReservationStatus.CANCELED,
                created_at=datetime(2026, 4, 30, 0, 0, tzinfo=UTC),
                canceled_at=None,
            )

    def test_active_status_with_canceled_at_raises_rule_error(self):
        with pytest.raises(ReservationRuleError, match="must not have canceled_at"):
            Reservation.reconstruct(
                id="r1",
                room_id=1,
                guest_name="Alice",
                attendee_count=1,
                start_at=_jst(2026, 5, 1, 9, 0).astimezone(UTC),
                end_at=_jst(2026, 5, 1, 9, 30).astimezone(UTC),
                timezone="Asia/Tokyo",
                status=ReservationStatus.ACTIVE,
                created_at=datetime(2026, 4, 30, 0, 0, tzinfo=UTC),
                canceled_at=datetime(2026, 4, 30, 1, 0, tzinfo=UTC),
            )


class TestOverlaps:
    @pytest.fixture
    def reservation(self):
        return Reservation.create(
            room_id=1,
            guest_name="Alice",
            attendee_count=1,
            start_at=_jst(2026, 5, 1, 10, 0),
            end_at=_jst(2026, 5, 1, 11, 0),
            timezone="Asia/Tokyo",
        )

    def test_strictly_inside_other_overlaps(self, reservation):
        assert reservation.overlaps(
            _jst(2026, 5, 1, 10, 30).astimezone(UTC),
            _jst(2026, 5, 1, 10, 45).astimezone(UTC),
        )

    def test_partial_left_overlap(self, reservation):
        assert reservation.overlaps(
            _jst(2026, 5, 1, 9, 30).astimezone(UTC),
            _jst(2026, 5, 1, 10, 30).astimezone(UTC),
        )

    def test_partial_right_overlap(self, reservation):
        assert reservation.overlaps(
            _jst(2026, 5, 1, 10, 30).astimezone(UTC),
            _jst(2026, 5, 1, 11, 30).astimezone(UTC),
        )

    def test_adjacent_after_does_not_overlap(self, reservation):
        # Other starts exactly when reservation ends.
        assert not reservation.overlaps(
            _jst(2026, 5, 1, 11, 0).astimezone(UTC),
            _jst(2026, 5, 1, 12, 0).astimezone(UTC),
        )

    def test_adjacent_before_does_not_overlap(self, reservation):
        assert not reservation.overlaps(
            _jst(2026, 5, 1, 9, 0).astimezone(UTC),
            _jst(2026, 5, 1, 10, 0).astimezone(UTC),
        )

    def test_completely_disjoint_does_not_overlap(self, reservation):
        assert not reservation.overlaps(
            _jst(2026, 5, 1, 14, 0).astimezone(UTC),
            _jst(2026, 5, 1, 15, 0).astimezone(UTC),
        )


class TestCancel:
    @pytest.fixture
    def reservation(self):
        return Reservation.create(
            room_id=1,
            guest_name="Alice",
            attendee_count=1,
            start_at=_jst(2026, 5, 10, 14, 0),
            end_at=_jst(2026, 5, 10, 15, 0),
            timezone="Asia/Tokyo",
        )

    def test_cancel_more_than_60min_before_start_marks_canceled(self, reservation):
        # 12:00 JST = 03:00 UTC -> 2 hours before 14:00 JST start.
        now = _jst(2026, 5, 10, 12, 0).astimezone(UTC)

        reservation.cancel(now)

        assert reservation.status == ReservationStatus.CANCELED
        assert reservation.canceled_at == now

    def test_cancel_exactly_at_deadline_raises_rule_error(self, reservation):
        # Deadline is start_at - 60min = 13:00 JST.
        now_at_deadline = _jst(2026, 5, 10, 13, 0).astimezone(UTC)

        with pytest.raises(ReservationRuleError, match="60 minutes"):
            reservation.cancel(now_at_deadline)

    def test_cancel_inside_deadline_raises_rule_error(self, reservation):
        now_inside = _jst(2026, 5, 10, 13, 30).astimezone(UTC)

        with pytest.raises(ReservationRuleError, match="60 minutes"):
            reservation.cancel(now_inside)

    def test_cancel_already_canceled_raises_rule_error(self, reservation):
        reservation.cancel(_jst(2026, 5, 10, 12, 0).astimezone(UTC))

        with pytest.raises(ReservationRuleError, match="already canceled"):
            reservation.cancel(_jst(2026, 5, 10, 12, 30).astimezone(UTC))

    def test_cancel_with_naive_now_raises_rule_error(self, reservation):
        with pytest.raises(ReservationRuleError, match="timezone"):
            reservation.cancel(datetime(2026, 5, 10, 12, 0))
