from sqlalchemy import select
from sqlalchemy.orm import Session

from app.domain.repositories import RoomRepository
from app.domain.room import Room
from app.infrastructure.db.models import RoomModel


def _to_room_domain(model: RoomModel) -> Room:
    return Room.reconstruct(id=model.id, name=model.name, capacity=model.capacity)


class SqlAlchemyRoomRepository(RoomRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, room: Room) -> Room:
        model = RoomModel(name=room.name, capacity=room.capacity)
        self._session.add(model)
        self._session.flush()
        return _to_room_domain(model)

    def get(self, room_id: int) -> Room | None:
        model = self._session.get(RoomModel, room_id)
        if model is None:
            return None
        return _to_room_domain(model)

    def list_all(self) -> list[Room]:
        stmt = select(RoomModel).order_by(RoomModel.id.asc())
        models = self._session.scalars(stmt).all()
        return [_to_room_domain(model) for model in models]
