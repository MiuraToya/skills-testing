"""In-memory fakes for application-layer unit tests.

These mirror the production UoW/repository contracts but keep state in
dictionaries so we can exercise services without a database.
"""
from __future__ import annotations

from datetime import datetime
from typing import Self

from sqlalchemy.exc import IntegrityError

from app.application.ports import UnitOfWork
from app.domain.repositories import ReservationRepository, RoomRepository
from app.domain.reservation import Reservation, ReservationStatus
from app.domain.room import Room


class InMemoryRoomRepository(RoomRepository):
    def __init__(self) -> None:
        self._rooms: dict[int, Room] = {}
        self._next_id = 1
        self._unique_names = True

    def add(self, room: Room) -> Room:
        if self._unique_names and any(r.name == room.name for r in self._rooms.values()):
            raise IntegrityError("duplicate name", params=None, orig=Exception())
        new_id = self._next_id
        self._next_id += 1
        stored = Room.reconstruct(id=new_id, name=room.name, capacity=room.capacity)
        self._rooms[new_id] = stored
        return stored

    def get(self, room_id: int) -> Room | None:
        return self._rooms.get(room_id)

    def list_all(self) -> list[Room]:
        return [self._rooms[k] for k in sorted(self._rooms.keys())]


class InMemoryReservationRepository(ReservationRepository):
    def __init__(self) -> None:
        self._reservations: dict[str, Reservation] = {}

    def add(self, reservation: Reservation) -> Reservation:
        self._reservations[reservation.id] = reservation
        return reservation

    def get(self, reservation_id: str) -> Reservation | None:
        return self._reservations.get(reservation_id)

    def update(self, reservation: Reservation) -> Reservation:
        if reservation.id not in self._reservations:
            raise ValueError(f"Reservation {reservation.id} not found.")
        self._reservations[reservation.id] = reservation
        return reservation

    def list_by_room_and_range(
        self, room_id: int, start_at: datetime, end_at: datetime
    ) -> list[Reservation]:
        result = []
        for r in self._reservations.values():
            if r.room_id != room_id:
                continue
            if r.status != ReservationStatus.ACTIVE:
                continue
            if r.start_at < end_at and start_at < r.end_at:
                result.append(r)
        return result


class FakeUnitOfWork(UnitOfWork):
    """In-memory UoW.

    `commit` is observable via the `committed` flag so tests can verify
    services persist deliberately rather than relying on auto-commit.
    A `commit_error` can be injected to simulate IntegrityError on commit.
    """

    def __init__(self) -> None:
        self.rooms = InMemoryRoomRepository()
        self.reservations = InMemoryReservationRepository()
        self.committed = False
        self.rolled_back = False
        self.commit_error: Exception | None = None

    def __enter__(self) -> Self:
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if exc_type is not None and not self.committed:
            self.rolled_back = True

    def commit(self) -> None:
        if self.commit_error is not None:
            raise self.commit_error
        self.committed = True

    def rollback(self) -> None:
        self.rolled_back = True
