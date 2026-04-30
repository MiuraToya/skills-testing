import pytest

from app.domain.exceptions import ReservationRuleError
from app.domain.room import Room


class TestRoomCreate:
    def test_create_with_valid_args_returns_room_with_id_zero(self):
        room = Room.create(name="Sakura", capacity=8)

        assert room.id == 0
        assert room.name == "Sakura"
        assert room.capacity == 8

    def test_create_strips_whitespace_from_name(self):
        room = Room.create(name="  Sakura  ", capacity=4)

        assert room.name == "Sakura"

    @pytest.mark.parametrize("invalid_name", ["", "   "])
    def test_create_with_blank_name_raises_rule_error(self, invalid_name):
        with pytest.raises(ReservationRuleError, match="Room name is required"):
            Room.create(name=invalid_name, capacity=4)

    @pytest.mark.parametrize("invalid_capacity", [0, -1, -10])
    def test_create_with_non_positive_capacity_raises_rule_error(
        self, invalid_capacity
    ):
        with pytest.raises(ReservationRuleError, match="capacity must be greater"):
            Room.create(name="Sakura", capacity=invalid_capacity)


class TestRoomReconstruct:
    def test_reconstruct_preserves_stored_id(self):
        room = Room.reconstruct(id=42, name="Hinoki", capacity=10)

        assert room.id == 42

    def test_reconstruct_with_negative_id_raises_rule_error(self):
        with pytest.raises(ReservationRuleError, match="Room ID"):
            Room.reconstruct(id=-1, name="Hinoki", capacity=10)


class TestDirectInstantiation:
    def test_direct_instantiation_without_internal_flag_raises_rule_error(self):
        with pytest.raises(ReservationRuleError, match="Room.create"):
            Room(id=1, name="Sakura", capacity=4)


class TestEnsureCapacityFor:
    def test_attendee_within_capacity_passes(self):
        room = Room.reconstruct(id=1, name="Sakura", capacity=8)

        room.ensure_capacity_for(8)

    def test_attendee_exceeds_capacity_raises_rule_error(self):
        room = Room.reconstruct(id=1, name="Sakura", capacity=4)

        with pytest.raises(ReservationRuleError, match="exceeds room capacity"):
            room.ensure_capacity_for(5)

    @pytest.mark.parametrize("invalid_count", [0, -1])
    def test_non_positive_attendee_raises_rule_error(self, invalid_count):
        room = Room.reconstruct(id=1, name="Sakura", capacity=4)

        with pytest.raises(ReservationRuleError, match="Attendee count"):
            room.ensure_capacity_for(invalid_count)
