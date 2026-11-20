"""Punto de entrada de EventQR."""
import os

from nicegui import ui

from app.core.config import settings
from app.core.database import init_db
from app.ui.pages import register_pages


def main() -> None:
    init_db()
    register_pages()
    ui.run(
        title=settings.APP_TITLE,
        host="0.0.0.0",
        port=int(os.environ.get("PORT", settings.APP_PORT)),
        storage_secret=settings.STORAGE_SECRET,
        reload=False,
        show=False,
    )


if __name__ in {"__main__", "__mp_main__"}:
    main()
