"""Consultas tabulares y exportación CSV de asistencia."""
import csv
import io
import re
from datetime import date, datetime

from sqlalchemy import func
from sqlmodel import select

from app.core.database import get_session
from app.models.entities import Attendance, Participant

CSV_HEADERS = ["Fecha", "Hora de ingreso", "Nombre completo", "Correo", "Organización", "Notas"]


def get_attendance_rows(event_id: int, attendance_date: date | None = None) -> list[dict]:
    with get_session() as session:
        stmt = (
            select(Attendance, Participant)
            .join(Participant, Attendance.participant_id == Participant.id)
            .where(Participant.event_id == event_id)
            .order_by(Attendance.attendance_date, Attendance.check_in_time)
        )
        if attendance_date is not None:
            stmt = stmt.where(Attendance.attendance_date == attendance_date)
        return [
            {
                "id": att.id,
                "date": att.attendance_date.strftime("%d/%m/%Y"),
                "time": att.check_in_time.strftime("%H:%M:%S"),
                "full_name": p.full_name,
                "email": p.email,
                "organization": p.organization or "",
                "notes": att.notes or "",
            }
            for att, p in session.exec(stmt).all()
        ]


def get_summary(event_id: int, attendance_date: date | None = None) -> dict:
    with get_session() as session:
        registered = session.exec(
            select(func.count(Participant.id)).where(Participant.event_id == event_id)
        ).one()
        stmt = (
            select(func.count(Attendance.id), func.count(func.distinct(Attendance.participant_id)))
            .join(Participant, Attendance.participant_id == Participant.id)
            .where(Participant.event_id == event_id)
        )
        if attendance_date is not None:
            stmt = stmt.where(Attendance.attendance_date == attendance_date)
        total, unique = session.exec(stmt).one()
    return {"registered": registered, "records": total, "unique": unique}


def export_attendance_csv(event_id: int, attendance_date: date | None = None) -> bytes:
    """CSV en UTF-8 (con BOM para que Excel respete tildes y eñes)."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(CSV_HEADERS)
    for row in get_attendance_rows(event_id, attendance_date):
        writer.writerow(
            [row["date"], row["time"], row["full_name"], row["email"], row["organization"], row["notes"]]
        )
    return buffer.getvalue().encode("utf-8-sig")


def build_filename(event_name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "_", event_name.lower()).strip("_") or "evento"
    return f"asistencia_{slug}_{datetime.now():%Y%m%d_%H%M}.csv"
