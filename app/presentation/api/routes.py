from fastapi import APIRouter, Depends, status

from app.application.dto import (
    CancelReservationCommand,
    CreateReservationCommand,
    CreateRoomCommand,
)
from app.application.ports import UnitOfWork
from app.application.services import ReservationService, RoomService
from app.config import settings
from app.presentation.api.dependencies import get_uow
from app.presentation.api.schemas import (
    ReservationCancelRequest,
    ReservationCreateRequest,
    ReservationResponse,
    RoomCreateRequest,
    RoomResponse,
)

router = APIRouter()


@router.post("/rooms", response_model=RoomResponse, status_code=status.HTTP_201_CREATED)
def create_room(
    payload: RoomCreateRequest, uow: UnitOfWork = Depends(get_uow)
) -> RoomResponse:
    service = RoomService(uow=uow)
    room = service.create_room(
        CreateRoomCommand(name=payload.name, capacity=payload.capacity)
    )
    return RoomResponse.model_validate(room)


@router.get("/rooms", response_model=list[RoomResponse])
def list_rooms(uow: UnitOfWork = Depends(get_uow)) -> list[RoomResponse]:
    service = RoomService(uow=uow)
    return [RoomResponse.model_validate(room) for room in service.list_rooms()]


@router.post(
    "/reservations",
    response_model=ReservationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_reservation(
    payload: ReservationCreateRequest, uow: UnitOfWork = Depends(get_uow)
) -> ReservationResponse:
    service = ReservationService(uow=uow, timezone=settings.timezone)
    reservation = service.create_reservation(
        CreateReservationCommand(
            room_id=payload.room_id,
            guest_name=payload.guest_name,
            attendee_count=payload.attendee_count,
            start_at=payload.start_at,
            end_at=payload.end_at,
        )
    )
    return ReservationResponse.model_validate(reservation)


@router.post(
    "/reservations/{reservation_id}/cancel", response_model=ReservationResponse
)
def cancel_reservation(
    reservation_id: str,
    payload: ReservationCancelRequest,
    uow: UnitOfWork = Depends(get_uow),
) -> ReservationResponse:
    service = ReservationService(uow=uow, timezone=settings.timezone)
    reservation = service.cancel_reservation(
        CancelReservationCommand(
            reservation_id=reservation_id,
            canceled_at=payload.canceled_at,
        )
    )
    return ReservationResponse.model_validate(reservation)
