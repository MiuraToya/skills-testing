from collections.abc import Generator

from app.infrastructure.db.session import SessionLocal
from app.infrastructure.unit_of_work import SqlAlchemyUnitOfWork


def get_uow() -> Generator[SqlAlchemyUnitOfWork, None, None]:
    yield SqlAlchemyUnitOfWork(SessionLocal)
