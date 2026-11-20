"""Lógica de negocio de eventos y participantes (independiente de la UI)."""
import re
from datetime import date

from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlmodel import delete, select

from app.core.database import get_session
from app.models.entities import Attendance, Event, Participant

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


class ValidationError(ValueError):
    """Error de validación de datos de entrada, apto para mostrar al usuario."""


def _clean(value: str | None) -> str | None:
    value = (value or "").strip()
    return value or None


# ------------------------------------------------------------------ Eventos
def create_event(
    name: str,
    description: str | None,
    location: str | None,
    start_date: str | date | None,
) -> Event:
    name = (name or "").strip()
    if not name:
        raise ValidationError("El nombre del evento es obligatorio.")
    if isinstance(start_date, str):
        try:
            start_date = date.fromisoformat(start_date.strip())
        except ValueError as exc:
            raise ValidationError("La fecha de inicio no es válida.") from exc
    if start_date is None:
        raise ValidationError("La fecha de inicio es obligatoria.")

    event = Event(
        name=name,
        description=_clean(description),
        location=_clean(location),
        start_date=start_date,
    )
    with get_session() as session:
        session.add(event)
        session.flush()
        session.refresh(event)
    return event


def list_events() -> list[Event]:
    with get_session() as session:
        stmt = select(Event).order_by(Event.start_date.desc(), Event.id.desc())
        return list(session.exec(stmt).all())


def list_event_summaries() -> list[dict]:
    """Eventos con su número de inscritos."""
    with get_session() as session:
        stmt = (
            select(Event, func.count(Participant.id))
            .join(Participant, Participant.event_id == Event.id, isouter=True)
            .group_by(Event.id)
            .order_by(Event.start_date.desc(), Event.id.desc())
        )
        return [
            {
                "id": event.id,
                "name": event.name,
                "description": event.description or "",
                "location": event.location or "—",
                "start_date": event.start_date.strftime("%d/%m/%Y"),
                "participants": count,
            }
            for event, count in session.exec(stmt).all()
        ]


def get_event(event_id: int) -> Event | None:
    with get_session() as session:
        return session.get(Event, event_id)


def delete_event(event_id: int) -> bool:
    """Elimina el evento junto con sus participantes y asistencias."""
    with get_session() as session:
        event = session.get(Event, event_id)
        if event is None:
            return False
        participant_ids = select(Participant.id).where(Participant.event_id == event_id)
        session.exec(
            delete(Attendance).where(Attendance.participant_id.in_(participant_ids))
        )
        session.exec(delete(Participant).where(Participant.event_id == event_id))
        session.delete(event)
    return True


# ------------------------------------------------------------ Participantes
def register_participant(
    event_id: int | None,
    full_name: str,
    email: str,
    organization: str | None = None,
) -> Participant:
    if not event_id:
        raise ValidationError("Seleccione un evento.")
    full_name = (full_name or "").strip()
    email = (email or "").strip().lower()
    if not full_name:
        raise ValidationError("El nombre completo es obligatorio.")
    if not _EMAIL_RE.match(email):
        raise ValidationError("El correo electrónico no es válido.")

    with get_session() as session:
        if session.get(Event, event_id) is None:
            raise ValidationError("El evento seleccionado ya no existe.")
        duplicate = session.exec(
            select(Participant).where(
                Participant.event_id == event_id, Participant.email == email
            )
        ).first()
        if duplicate is not None:
            raise ValidationError("Ya existe un participante con ese correo en el evento.")

        participant = Participant(
            full_name=full_name,
            email=email,
            organization=_clean(organization),
            event_id=event_id,
        )
        try:
            session.add(participant)
            session.flush()
            session.refresh(participant)
        except IntegrityError as exc:
            raise ValidationError("No se pudo registrar al participante.") from exc
    return participant


def list_participants(event_id: int) -> list[Participant]:
    with get_session() as session:
        stmt = (
            select(Participant)
            .where(Participant.event_id == event_id)
            .order_by(Participant.registered_at.desc(), Participant.id.desc())
        )
        return list(session.exec(stmt).all())
