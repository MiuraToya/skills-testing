from abc import ABC, abstractmethod
from datetime import datetime

from .reservation import Reservation
from .room import Room


class RoomRepository(ABC):
    @abstractmethod
    def add(self, room: Room) -> Room:
        raise NotImplementedError

    @abstractmethod
    def get(self, room_id: int) -> Room | None:
        raise NotImplementedError

    @abstractmethod
    def list_all(self) -> list[Room]:
        raise NotImplementedError


class ReservationRepository(ABC):
    @abstractmethod
    def add(self, reservation: Reservation) -> Reservation:
        raise NotImplementedError

    @abstractmethod
    def get(self, reservation_id: str) -> Reservation | None:
        raise NotImplementedError

    @abstractmethod
    def update(self, reservation: Reservation) -> Reservation:
        raise NotImplementedError

    @abstractmethod
    def list_by_room_and_range(
        self, room_id: int, start_at: datetime, end_at: datetime
    ) -> list[Reservation]:
        raise NotImplementedError
