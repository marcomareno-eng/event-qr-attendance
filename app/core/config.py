"""Configuración de la aplicación mediante variables de entorno / .env."""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql://eventqr:eventqr@localhost:5432/eventqr"
    STORAGE_SECRET: str = "cambia-esto-en-produccion"
    APP_TITLE: str = "EventQR"
    APP_PORT: int = 8080
    DB_USE_NULLPOOL: bool = False

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


settings = Settings()
