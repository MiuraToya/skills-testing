from typing import Self

from sqlalchemy.orm import Session, sessionmaker

from app.application.ports import UnitOfWork
from app.infrastructure.reservation_repository import SqlAlchemyReservationRepository
from app.infrastructure.room_repository import SqlAlchemyRoomRepository


class SqlAlchemyUnitOfWork(UnitOfWork):
    def __init__(self, session_factory: sessionmaker) -> None:
        self._session_factory = session_factory
        self._session: Session | None = None

    def __enter__(self) -> Self:
        self._session = self._session_factory()
        self.rooms = SqlAlchemyRoomRepository(self._session)
        self.reservations = SqlAlchemyReservationRepository(self._session)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._session is None:
            return
        if exc_type is not None:
            self._session.rollback()
        self._session.close()
        self._session = None

    def commit(self) -> None:
        if self._session is None:
            raise RuntimeError("UnitOfWork is not active.")
        self._session.commit()

    def rollback(self) -> None:
        if self._session is None:
            raise RuntimeError("UnitOfWork is not active.")
        self._session.rollback()
