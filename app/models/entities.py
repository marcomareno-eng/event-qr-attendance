"""Modelos relacionales de EventQR."""
import uuid
from datetime import date, datetime
from typing import Optional

from pydantic import NaiveDatetime
from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel


def _utcnow() -> datetime:
    """UTC naive (compatible con columnas TIMESTAMP sin zona)."""
    return datetime.utcnow()


class Event(SQLModel, table=True):
    __tablename__ = "events"

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(max_length=200, index=True)
    description: Optional[str] = Field(default=None)
    location: Optional[str] = Field(default=None, max_length=200)
    start_date: date
    created_at: NaiveDatetime = Field(default_factory=_utcnow)


class Participant(SQLModel, table=True):
    __tablename__ = "participants"

    id: Optional[int] = Field(default=None, primary_key=True)
    full_name: str = Field(max_length=200)
    email: str = Field(max_length=254, index=True)
    organization: Optional[str] = Field(default=None, max_length=200)
    qr_token: uuid.UUID = Field(
        default_factory=uuid.uuid4, unique=True, index=True, nullable=False
    )
    event_id: int = Field(foreign_key="events.id", index=True)
    registered_at: NaiveDatetime = Field(default_factory=_utcnow)


class Attendance(SQLModel, table=True):
    __tablename__ = "attendances"
    __table_args__ = (
        UniqueConstraint(
            "participant_id", "attendance_date", name="uq_attendance_participant_day"
        ),
    )

    id: Optional[int] = Field(default=None, primary_key=True)
    participant_id: int = Field(foreign_key="participants.id", index=True)
    attendance_date: date = Field(index=True)
    check_in_time: NaiveDatetime = Field(default_factory=datetime.now)
    notes: Optional[str] = Field(default=None)
