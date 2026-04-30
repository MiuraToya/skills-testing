import pytest

from app.domain.exceptions import ReservationRuleError
from app.domain.room import Room


class TestRoomCreate:
    def test_create_with_valid_data_succeeds(self) -> None:
        room = Room.create(name="Conference A", capacity=10)

        assert room.id == 0
        assert room.name == "Conference A"
        assert room.capacity == 10

    def test_name_is_stripped(self) -> None:
        room = Room.create(name="  Conference A  ", capacity=10)

        assert room.name == "Conference A"

    def test_direct_instantiation_raises(self) -> None:
        with pytest.raises(ReservationRuleError, match="Room.create"):
            Room(id=1, name="Conference A", capacity=10)

    def test_empty_name_raises(self) -> None:
        with pytest.raises(ReservationRuleError, match="Room name"):
            Room.create(name="   ", capacity=10)

    def test_zero_capacity_raises(self) -> None:
        with pytest.raises(ReservationRuleError, match="capacity"):
            Room.create(name="Conference A", capacity=0)

    def test_negative_capacity_raises(self) -> None:
        with pytest.raises(ReservationRuleError):
            Room.create(name="Conference A", capacity=-1)


class TestRoomReconstruct:
    def test_reconstruct_with_valid_id(self) -> None:
        room = Room.reconstruct(id=42, name="Conference A", capacity=8)

        assert room.id == 42
        assert room.name == "Conference A"
        assert room.capacity == 8

    def test_reconstruct_with_negative_id_raises(self) -> None:
        with pytest.raises(ReservationRuleError, match="Room ID"):
            Room.reconstruct(id=-1, name="Conference A", capacity=8)


class TestRoomEnsureCapacityFor:
    def test_within_limit_passes(self) -> None:
        room = Room.create(name="Conference A", capacity=10)

        room.ensure_capacity_for(5)

    def test_at_limit_passes(self) -> None:
        room = Room.create(name="Conference A", capacity=10)

        room.ensure_capacity_for(10)

    def test_exceeds_capacity_raises(self) -> None:
        room = Room.create(name="Conference A", capacity=10)

        with pytest.raises(ReservationRuleError, match="exceeds room capacity"):
            room.ensure_capacity_for(11)

    def test_zero_attendee_raises(self) -> None:
        room = Room.create(name="Conference A", capacity=10)

        with pytest.raises(ReservationRuleError, match="Attendee"):
            room.ensure_capacity_for(0)

    def test_negative_attendee_raises(self) -> None:
        room = Room.create(name="Conference A", capacity=10)

        with pytest.raises(ReservationRuleError):
            room.ensure_capacity_for(-1)
