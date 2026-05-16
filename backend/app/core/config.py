from functools import lru_cache
from typing import Annotated

from pydantic import AnyHttpUrl, Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # ── Database ───────────────────────────────────────────────────────────────
    # Pooled string (PgBouncer) for app runtime
    DATABASE_URL: str
    # Direct string for Alembic migrations (bypasses PgBouncer)
    DATABASE_URL_DIRECT: str

    # ── JWT ────────────────────────────────────────────────────────────────────
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=15, ge=1, le=60)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, ge=1, le=30)

    # ── App ────────────────────────────────────────────────────────────────────
    APP_ENV: str = "development"
    DEBUG: bool = False
    # Comma-separated list in .env → list[str] via validator
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000", "https://kaleidoscopic-puffpuff-66a4da.netlify.app"]

    # ── Security ───────────────────────────────────────────────────────────────
    BCRYPT_ROUNDS: Annotated[int, Field(ge=10, le=14)] = 12
    # Hard cap on note content to prevent payload attacks
    MAX_NOTE_CONTENT_BYTES: int = Field(default=1_048_576, ge=1024)

    @field_validator("CORS_ORIGINS", mode="before")
    @classmethod
    def parse_cors(cls, v: str | list) -> list[str]:
        if isinstance(v, str):
            return [origin.strip() for origin in v.split(",") if origin.strip()]
        return v

    @field_validator("JWT_SECRET_KEY")
    @classmethod
    def secret_must_be_long(cls, v: str) -> str:
        if len(v) < 32:
            raise ValueError("JWT_SECRET_KEY must be at least 32 characters")
        return v

    @field_validator("DATABASE_URL", "DATABASE_URL_DIRECT", mode="before")
    @classmethod
    def ensure_async_driver(cls, v: str) -> str:
        if not isinstance(v, str):
            return v
        
        # 1. Force the asyncpg protocol prefix
        if v.startswith("postgresql://"):
            v = v.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif v.startswith("postgres://"):
            v = v.replace("postgres://", "postgresql+asyncpg://", 1)
            
        # 2. Fix the SSL parameter for asyncpg compatibility
        # If '?sslmode=' is in the URL string, strip it off so it doesn't break asyncpg
        if "?sslmode=" in v or "&sslmode=" in v:
            # Split the connection string at the query parameter
            base_url, _ = v.split("sslmode=", 1)
            # Strip trailing '?' or '&' left behind from splitting
            v = base_url.rstrip("?&")

        return v

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.lower() == "production"


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Cached singleton — settings are read once at startup.
    lru_cache ensures we never re-parse .env on every request.
    """
    return Settings()


# Module-level alias so callers can do: from app.core.config import settings
settings: Settings = get_settings()