"""Validación de tokens QR y registro de asistencia diaria."""
import uuid
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.exc import IntegrityError
from sqlmodel import select

from app.core.database import get_session
from app.models.entities import Attendance, Event, Participant

SUCCESS = "success"
DUPLICATE = "duplicate"
INVALID = "invalid"
NOT_FOUND = "not_found"


@dataclass(frozen=True)
class CheckInResult:
    status: str
    message: str
    participant_name: str | None = None
    event_name: str | None = None
    check_in_time: datetime | None = None

    @property
    def ok(self) -> bool:
        return self.status == SUCCESS


def process_check_in(raw_token: str | None, notes: str | None = None) -> CheckInResult:
    """Valida el token leído y registra la asistencia del día (una vez por día)."""
    raw = (raw_token or "").strip()
    try:
        token = uuid.UUID(raw)
    except ValueError:
        return CheckInResult(INVALID, "El código leído no tiene un formato válido.")

    now = datetime.now()
    today = now.date()

    with get_session() as session:
        participant = session.exec(
            select(Participant).where(Participant.qr_token == token)
        ).first()
        if participant is None:
            return CheckInResult(NOT_FOUND, "No existe ningún participante con ese código.")

        event = session.get(Event, participant.event_id)
        name = participant.full_name
        event_name = event.name if event else None
        participant_id = participant.id

        def _existing() -> Attendance | None:
            return session.exec(
                select(Attendance).where(
                    Attendance.participant_id == participant_id,
                    Attendance.attendance_date == today,
                )
            ).first()

        existing = _existing()
        if existing is not None:
            return CheckInResult(
                DUPLICATE,
                "La asistencia de hoy ya fue registrada.",
                name,
                event_name,
                existing.check_in_time,
            )

        try:
            with session.begin_nested():
                session.add(
                    Attendance(
                        participant_id=participant_id,
                        attendance_date=today,
                        check_in_time=now,
                        notes=(notes or "").strip() or None,
                    )
                )
                session.flush()
        except IntegrityError:
            # Carrera: otro terminal registró la asistencia en el mismo instante.
            existing = _existing()
            return CheckInResult(
                DUPLICATE,
                "La asistencia de hoy ya fue registrada.",
                name,
                event_name,
                existing.check_in_time if existing else now,
            )

    return CheckInResult(SUCCESS, "Asistencia registrada correctamente.", name, event_name, now)
