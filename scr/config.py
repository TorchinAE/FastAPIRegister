from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file="../.env",
        env_file_encoding="utf-8",
    )

    NAME_BASE: str

    @property
    def database_url(self) -> str:
        return f"sqlite+aiosqlite:///{self.NAME_BASE}.db"


settings = Settings()
