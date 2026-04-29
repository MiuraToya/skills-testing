from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from enum import Enum
from uuid import uuid4
from zoneinfo import ZoneInfo

from .exceptions import ReservationRuleError

BUSINESS_OPEN_HOUR = 9
BUSINESS_CLOSE_HOUR = 18
CANCEL_DEADLINE_MINUTES = 60


class ReservationStatus(str, Enum):
    ACTIVE = "active"
    CANCELED = "canceled"


@dataclass(slots=True, init=False)
class Reservation:
    id: str
    room_id: int
    guest_name: str
    attendee_count: int
    start_at: datetime
    end_at: datetime
    timezone: str
    status: ReservationStatus
    created_at: datetime
    canceled_at: datetime | None

    def __init__(
        self,
        id: str,
        room_id: int,
        guest_name: str,
        attendee_count: int,
        start_at: datetime,
        end_at: datetime,
        timezone: str,
        status: ReservationStatus,
        created_at: datetime,
        canceled_at: datetime | None,
        *,
        _internal: bool = False,
    ):
        if not _internal:
            raise ReservationRuleError(
                "Reservation must be created via Reservation.create()."
            )
        self.id = id
        self.room_id = room_id
        self.guest_name = guest_name.strip()
        self.attendee_count = attendee_count
        self.start_at = start_at
        self.end_at = end_at
        self.timezone = timezone
        self.status = status
        self.created_at = created_at
        self.canceled_at = canceled_at
        self._validate_invariants()

    @classmethod
    def create(
        cls,
        room_id: int,
        guest_name: str,
        attendee_count: int,
        start_at: datetime,
        end_at: datetime,
        timezone: str,
    ) -> "Reservation":
        normalized_start = start_at.astimezone(UTC)
        normalized_end = end_at.astimezone(UTC)
        return cls(
            id=str(uuid4()),
            room_id=room_id,
            guest_name=guest_name,
            attendee_count=attendee_count,
            start_at=normalized_start,
            end_at=normalized_end,
            timezone=timezone,
            status=ReservationStatus.ACTIVE,
            created_at=datetime.now(tz=UTC),
            canceled_at=None,
            _internal=True,
        )

    @classmethod
    def reconstruct(
        cls,
        id: str,
        room_id: int,
        guest_name: str,
        attendee_count: int,
        start_at: datetime,
        end_at: datetime,
        timezone: str,
        status: ReservationStatus,
        created_at: datetime,
        canceled_at: datetime | None,
    ) -> "Reservation":
        return cls(
            id=id,
            room_id=room_id,
            guest_name=guest_name,
            attendee_count=attendee_count,
            start_at=start_at,
            end_at=end_at,
            timezone=timezone,
            status=status,
            created_at=created_at,
            canceled_at=canceled_at,
            _internal=True,
        )

    def _validate_invariants(self) -> None:
        if self.room_id <= 0:
            raise ReservationRuleError("Room ID must be positive.")
        if not self.guest_name:
            raise ReservationRuleError("Guest name is required.")
        if self.attendee_count <= 0:
            raise ReservationRuleError("Attendee count must be greater than zero.")
        self._ensure_timezone_aware(self.start_at, "start_at")
        self._ensure_timezone_aware(self.end_at, "end_at")
        self._ensure_timezone_aware(self.created_at, "created_at")
        if self.canceled_at is not None:
            self._ensure_timezone_aware(self.canceled_at, "canceled_at")
        if self.start_at >= self.end_at:
            raise ReservationRuleError("start_at must be earlier than end_at.")
        self._ensure_slot_alignment(self.start_at, "start_at")
        self._ensure_slot_alignment(self.end_at, "end_at")
        self._ensure_within_business_hours()
        self._ensure_status_consistency()

    def _ensure_status_consistency(self) -> None:
        if self.status == ReservationStatus.CANCELED and self.canceled_at is None:
            raise ReservationRuleError(
                "Canceled reservation must have canceled_at timestamp."
            )
        if self.status == ReservationStatus.ACTIVE and self.canceled_at is not None:
            raise ReservationRuleError("Active reservation must not have canceled_at.")

    @staticmethod
    def _ensure_timezone_aware(value: datetime, field_name: str) -> None:
        if value.tzinfo is None or value.utcoffset() is None:
            raise ReservationRuleError(f"{field_name} must include timezone offset.")

    @staticmethod
    def _ensure_slot_alignment(value: datetime, field_name: str) -> None:
        if value.minute not in (0, 30) or value.second != 0 or value.microsecond != 0:
            raise ReservationRuleError(
                f"{field_name} must align to 30-minute slots with zero seconds."
            )

    def _ensure_within_business_hours(self) -> None:
        tz = ZoneInfo(self.timezone)
        local_start = self.start_at.astimezone(tz)
        local_end = self.end_at.astimezone(tz)
        open_time = local_start.replace(hour=BUSINESS_OPEN_HOUR, minute=0, second=0)
        close_time = local_start.replace(hour=BUSINESS_CLOSE_HOUR, minute=0, second=0)
        if not (open_time <= local_start < close_time):
            raise ReservationRuleError(
                "Reservation start time must be within business hours."
            )
        if not (open_time < local_end <= close_time):
            raise ReservationRuleError(
                "Reservation end time must be within business hours."
            )
        if local_start.date() != local_end.date():
            raise ReservationRuleError(
                "Reservation must start and end on the same day."
            )

    def overlaps(self, other_start_at: datetime, other_end_at: datetime) -> bool:
        return self.start_at < other_end_at and other_start_at < self.end_at

    def cancel(self, now: datetime) -> None:
        self._ensure_timezone_aware(now, "now")
        if self.status == ReservationStatus.CANCELED:
            raise ReservationRuleError("Reservation is already canceled.")
        deadline = self.start_at - timedelta(minutes=CANCEL_DEADLINE_MINUTES)
        if now >= deadline:
            raise ReservationRuleError(
                f"Cancellation is only allowed before {CANCEL_DEADLINE_MINUTES} minutes to start."
            )
        self.status = ReservationStatus.CANCELED
        self.canceled_at = now
