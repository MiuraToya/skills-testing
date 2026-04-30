import pytest

from app.application.dto import CreateRoomCommand
from app.application.exceptions import ConflictError, ValidationError
from app.application.services import RoomService

from .fakes import FakeUnitOfWork


class TestCreateRoom:
    def test_valid_command_persists_room_and_commits(self):
        uow = FakeUnitOfWork()
        service = RoomService(uow=uow)

        room = service.create_room(CreateRoomCommand(name="Sakura", capacity=8))

        assert room.id == 1
        assert room.name == "Sakura"
        assert room.capacity == 8
        assert uow.committed is True

    def test_invalid_capacity_raises_validation_error_and_does_not_commit(self):
        uow = FakeUnitOfWork()
        service = RoomService(uow=uow)

        with pytest.raises(ValidationError, match="capacity"):
            service.create_room(CreateRoomCommand(name="Sakura", capacity=0))

        assert uow.committed is False
        assert uow.rooms.list_all() == []

    def test_duplicate_name_raises_conflict_error(self):
        uow = FakeUnitOfWork()
        service = RoomService(uow=uow)
        service.create_room(CreateRoomCommand(name="Sakura", capacity=8))

        with pytest.raises(ConflictError, match="already exists"):
            service.create_room(CreateRoomCommand(name="Sakura", capacity=10))


class TestListRooms:
    def test_returns_empty_list_when_no_rooms_exist(self):
        uow = FakeUnitOfWork()
        service = RoomService(uow=uow)

        assert service.list_rooms() == []

    def test_returns_rooms_in_insertion_order(self):
        uow = FakeUnitOfWork()
        service = RoomService(uow=uow)
        service.create_room(CreateRoomCommand(name="Sakura", capacity=8))
        service.create_room(CreateRoomCommand(name="Hinoki", capacity=4))

        rooms = service.list_rooms()

        assert [r.name for r in rooms] == ["Sakura", "Hinoki"]
