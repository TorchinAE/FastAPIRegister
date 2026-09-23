# config.py
import os

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    NAME_BASE: str
    db_echo: bool = False
    REG_SECRET_KEY: str = "dev-secret-key-change-in-production"
    REG_ADMIN_USERNAME: str = "admin"
    REG_ADMIN_PASSWORD: str = "admin123"
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def database_url(self) -> str:
        return f"sqlite+aiosqlite:///{os.path.abspath(self.NAME_BASE)}.db"


settings = Settings()
