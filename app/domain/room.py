from dataclasses import dataclass

from .exceptions import ReservationRuleError


@dataclass(frozen=True, slots=True, init=False)
class Room:
    id: int
    name: str
    capacity: int

    def __init__(self, id: int, name: str, capacity: int, *, _internal: bool = False):
        if not _internal:
            raise ReservationRuleError("Room must be created via Room.create().")
        object.__setattr__(self, "id", id)
        object.__setattr__(self, "name", name.strip())
        object.__setattr__(self, "capacity", capacity)
        self._validate_invariants()

    @classmethod
    def create(cls, name: str, capacity: int) -> Room:
        return cls(id=0, name=name, capacity=capacity, _internal=True)

    @classmethod
    def reconstruct(cls, id: int, name: str, capacity: int) -> Room:
        return cls(id=id, name=name, capacity=capacity, _internal=True)

    def _validate_invariants(self) -> None:
        if self.id < 0:
            raise ReservationRuleError("Room ID must be zero or positive.")
        if self.capacity <= 0:
            raise ReservationRuleError("Room capacity must be greater than zero.")
        if not self.name:
            raise ReservationRuleError("Room name is required.")

    def ensure_capacity_for(self, attendee_count: int) -> None:
        if attendee_count <= 0:
            raise ReservationRuleError("Attendee count must be greater than zero.")
        if attendee_count > self.capacity:
            raise ReservationRuleError(
                f"Attendee count ({attendee_count}) exceeds room capacity ({self.capacity})."
            )
