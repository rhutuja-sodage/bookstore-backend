from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, read from BOOKWORM_* environment variables or a .env file."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="BOOKWORM_", extra="ignore")

    mongodb_url: str = "mongodb://localhost:27017"
    mongodb_db: str = "bookworm"
    jwt_secret: str = "dev-only-secret-change-me-in-production-0123456789"
    jwt_expire_minutes: int = 60 * 24 * 7
    cors_origins: list[str] = ["http://localhost:4200", "http://localhost:4300"]
    seed_on_startup: bool = True


@lru_cache
def get_settings() -> Settings:
    return Settings()
