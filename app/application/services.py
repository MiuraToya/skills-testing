from app.application.dto import (
    CancelReservationCommand,
    CreateReservationCommand,
    CreateRoomCommand,
)
from app.application.exceptions import ConflictError, NotFoundError, ValidationError
from app.application.ports import UnitOfWork
from app.domain.reservation import Reservation
from app.domain.room import Room
from app.domain.exceptions import ReservationRuleError
from sqlalchemy.exc import IntegrityError


class RoomService:
    def __init__(self, uow: UnitOfWork) -> None:
        self._uow = uow

    def create_room(self, command: CreateRoomCommand) -> Room:
        try:
            room = Room.create(name=command.name, capacity=command.capacity)
        except ReservationRuleError as exc:
            raise ValidationError(str(exc)) from exc

        with self._uow as uow:
            created = uow.rooms.add(room)
            try:
                uow.commit()
            except IntegrityError as exc:
                uow.rollback()
                raise ConflictError("Room name already exists.") from exc
            return created

    def list_rooms(self) -> list[Room]:
        with self._uow as uow:
            return uow.rooms.list_all()


class ReservationService:
    def __init__(self, uow: UnitOfWork, timezone: str) -> None:
        self._uow = uow
        self._timezone = timezone

    def create_reservation(self, command: CreateReservationCommand) -> Reservation:
        with self._uow as uow:
            room = uow.rooms.get(command.room_id)
            if room is None:
                raise NotFoundError(f"Room {command.room_id} not found.")

            try:
                room.ensure_capacity_for(command.attendee_count)
                reservation = Reservation.create(
                    room_id=command.room_id,
                    guest_name=command.guest_name,
                    attendee_count=command.attendee_count,
                    start_at=command.start_at,
                    end_at=command.end_at,
                    timezone=self._timezone,
                )
            except ReservationRuleError as exc:
                raise ValidationError(str(exc)) from exc

            existing_reservations = uow.reservations.list_by_room_and_range(
                room_id=command.room_id,
                start_at=reservation.start_at,
                end_at=reservation.end_at,
            )
            if any(
                existing.overlaps(reservation.start_at, reservation.end_at)
                for existing in existing_reservations
            ):
                raise ConflictError("Reservation conflicts with existing booking.")

            created = uow.reservations.add(reservation)
            try:
                uow.commit()
            except IntegrityError as exc:
                uow.rollback()
                raise ConflictError(
                    "Failed to create reservation due to data conflict."
                ) from exc
            return created

    def cancel_reservation(self, command: CancelReservationCommand) -> Reservation:
        with self._uow as uow:
            reservation = uow.reservations.get(command.reservation_id)
            if reservation is None:
                raise NotFoundError(f"Reservation {command.reservation_id} not found.")

            try:
                reservation.cancel(command.canceled_at)
            except ReservationRuleError as exc:
                raise ValidationError(str(exc)) from exc

            uow.commit()
            return reservation
