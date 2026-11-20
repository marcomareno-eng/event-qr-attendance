"""Engine de SQLModel, inicialización del esquema y sesiones transaccionales."""
import logging
import time
from collections.abc import Iterator
from contextlib import contextmanager

from sqlalchemy.exc import OperationalError
from sqlalchemy.pool import NullPool
from sqlmodel import Session, SQLModel, create_engine

from app.core.config import settings

logger = logging.getLogger(__name__)


def normalize_database_url(url: str) -> str:
    """Convierte postgres:// y postgresql:// al dialecto psycopg 3 de SQLAlchemy."""
    url = url.strip()
    if url.startswith("postgres://"):
        url = "postgresql://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


_engine_kwargs: dict = {"pool_pre_ping": True, "echo": False}
if settings.DB_USE_NULLPOOL:
    # Recomendado con el pooler en modo transacción (Supabase, puerto 6543).
    _engine_kwargs["poolclass"] = NullPool

engine = create_engine(normalize_database_url(settings.DATABASE_URL), **_engine_kwargs)


def init_db(retries: int = 10, delay: float = 2.0) -> None:
    """Crea las tablas si no existen, reintentando si la BD aún no está lista."""
    import app.models.entities  # noqa: F401  (registra los modelos en el metadata)

    for attempt in range(1, retries + 1):
        try:
            SQLModel.metadata.create_all(engine)
            return
        except OperationalError as exc:
            if attempt == retries:
                raise
            logger.warning(
                "Base de datos no disponible (intento %s/%s): %s", attempt, retries, exc
            )
            time.sleep(delay)


@contextmanager
def get_session() -> Iterator[Session]:
    """Sesión transaccional: commit al salir, rollback ante cualquier excepción."""
    session = Session(engine, expire_on_commit=False)
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
