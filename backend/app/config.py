from functools import lru_cache

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")
    database_url: str = "postgresql+psycopg://risk:risk@localhost:5432/risk"
    telegram_bot_token: SecretStr = SecretStr("")
    telegram_webhook_secret: SecretStr = SecretStr("")
    telegram_bot_username: str = ""
    public_url: str = "https://localhost"
    command_ttl_seconds: int = Field(30, ge=5, le=30)
    online_seconds: int = Field(10, ge=3, le=20)
    session_seconds: int = 3600


@lru_cache
def settings() -> Settings:
    return Settings()
