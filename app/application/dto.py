from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class CreateRoomCommand:
    name: str
    capacity: int


@dataclass(frozen=True, slots=True)
class CreateReservationCommand:
    room_id: int
    guest_name: str
    attendee_count: int
    start_at: datetime
    end_at: datetime


@dataclass(frozen=True, slots=True)
class CancelReservationCommand:
    reservation_id: str
    canceled_at: datetime
