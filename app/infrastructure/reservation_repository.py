from datetime import UTC, datetime

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.domain.repositories import ReservationRepository
from app.domain.reservation import Reservation, ReservationStatus
from app.infrastructure.db.models import ReservationModel


def _to_reservation_domain(model: ReservationModel) -> Reservation:
    start_at = model.start_at
    end_at = model.end_at
    created_at = model.created_at
    canceled_at = model.canceled_at
    if start_at.tzinfo is None:
        start_at = start_at.replace(tzinfo=UTC)
    if end_at.tzinfo is None:
        end_at = end_at.replace(tzinfo=UTC)
    if created_at.tzinfo is None:
        created_at = created_at.replace(tzinfo=UTC)
    if canceled_at is not None and canceled_at.tzinfo is None:
        canceled_at = canceled_at.replace(tzinfo=UTC)

    return Reservation.reconstruct(
        id=model.id,
        room_id=model.room_id,
        guest_name=model.guest_name,
        attendee_count=model.attendee_count,
        start_at=start_at,
        end_at=end_at,
        timezone="Asia/Tokyo",
        status=model.status,
        created_at=created_at,
        canceled_at=canceled_at,
    )


class SqlAlchemyReservationRepository(ReservationRepository):
    def __init__(self, session: Session) -> None:
        self._session = session

    def add(self, reservation: Reservation) -> Reservation:
        model = ReservationModel(
            id=reservation.id,
            room_id=reservation.room_id,
            guest_name=reservation.guest_name,
            attendee_count=reservation.attendee_count,
            start_at=reservation.start_at,
            end_at=reservation.end_at,
            status=reservation.status,
            created_at=reservation.created_at,
            canceled_at=reservation.canceled_at,
        )
        self._session.add(model)
        self._session.flush()
        return _to_reservation_domain(model)

    def get(self, reservation_id: str) -> Reservation | None:
        model = self._session.get(ReservationModel, reservation_id)
        if model is None:
            return None
        return _to_reservation_domain(model)

    def update(self, reservation: Reservation) -> Reservation:
        model = self._session.get(ReservationModel, reservation.id)
        if model is None:
            raise ValueError(f"Reservation {reservation.id} not found.")
        model.guest_name = reservation.guest_name
        model.attendee_count = reservation.attendee_count
        model.start_at = reservation.start_at
        model.end_at = reservation.end_at
        model.status = reservation.status
        model.canceled_at = reservation.canceled_at
        self._session.flush()
        return _to_reservation_domain(model)

    def list_by_room_and_range(
        self, room_id: int, start_at: datetime, end_at: datetime
    ) -> list[Reservation]:
        stmt = (
            select(ReservationModel)
            .where(ReservationModel.room_id == room_id)
            .where(ReservationModel.status == ReservationStatus.ACTIVE)
            .where(
                or_(
                    and_(
                        ReservationModel.start_at <= start_at,
                        ReservationModel.end_at > start_at,
                    ),
                    and_(
                        ReservationModel.start_at < end_at,
                        ReservationModel.end_at >= end_at,
                    ),
                    and_(
                        ReservationModel.start_at >= start_at,
                        ReservationModel.end_at <= end_at,
                    ),
                )
            )
        )
        models = self._session.scalars(stmt).all()
        return [_to_reservation_domain(model) for model in models]
