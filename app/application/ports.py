from abc import ABC, abstractmethod

from app.domain.repositories import ReservationRepository, RoomRepository


class UnitOfWork(ABC):
    rooms: RoomRepository
    reservations: ReservationRepository

    @abstractmethod
    def __enter__(self) -> "UnitOfWork":
        raise NotImplementedError

    @abstractmethod
    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        raise NotImplementedError

    @abstractmethod
    def commit(self) -> None:
        raise NotImplementedError

    @abstractmethod
    def rollback(self) -> None:
        raise NotImplementedError
