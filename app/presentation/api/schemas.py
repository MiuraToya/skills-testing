from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.domain.reservation import ReservationStatus


class RoomCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    capacity: int = Field(gt=0, le=200)


class RoomResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    capacity: int


class ReservationCreateRequest(BaseModel):
    room_id: int = Field(gt=0)
    guest_name: str = Field(min_length=1, max_length=100)
    attendee_count: int = Field(gt=0, le=200)
    start_at: datetime
    end_at: datetime


class ReservationCancelRequest(BaseModel):
    canceled_at: datetime


class ReservationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    room_id: int
    guest_name: str
    attendee_count: int
    start_at: datetime
    end_at: datetime
    status: ReservationStatus
    created_at: datetime
    canceled_at: datetime | None
