import os
from functools import lru_cache
from typing import List
from urllib.parse import urlsplit
from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def normalize_database_url(raw_url: str) -> str:
    """Normalize PostgreSQL URLs to use psycopg3 (postgresql+psycopg://) and guard empty strings."""
    cleaned = (raw_url or "").strip()
    if not cleaned:
        return "sqlite:///./smartnav.db"
    if cleaned.startswith("postgres://"):
        return "postgresql+psycopg://" + cleaned[len("postgres://") :]
    if cleaned.startswith("postgresql://"):
        return "postgresql+psycopg://" + cleaned[len("postgresql://") :]
    return cleaned


def mask_database_url(url: str) -> str:
    """Return a safe representation of DATABASE_URL with password redacted for logs."""
    try:
        parsed = urlsplit(url)
        if parsed.password:
            netloc = parsed.netloc.replace(f":{parsed.password}@", ":***@")
            return parsed._replace(netloc=netloc).geturl()
        return url
    except Exception:
        return "<invalid-database-url>"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    APP_NAME: str = "SmartNav AI"
    APP_ENV: str = "development"
    DEBUG: bool = True
    SECRET_KEY: str = "dev-only-secret-change-before-production-32chars"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # PostgreSQL + PostGIS required in production; SQLite is allowed only in local dev/test
    DATABASE_URL: str = "sqlite:///./smartnav.db"
    ALLOW_SQLITE_IN_PRODUCTION: bool = False
    DB_INIT_ON_STARTUP: bool = True

    CORS_ORIGINS: str = "http://localhost:5173,https://localhost:5173,http://127.0.0.1:5173"

    NOMINATIM_BASE_URL: str = "https://nominatim.openstreetmap.org"
    NOMINATIM_USER_AGENT: str = "SmartNavAI/1.0 (contact@smartnav.local)"
    OSRM_BASE_URL: str = "https://router.project-osrm.org"
    OVERPASS_BASE_URL: str = "https://overpass-api.de/api/interpreter"

    # Live Traffic Provider (TomTom) - kept strictly on backend
    TRAFFIC_PROVIDER: str = "tomtom"
    TOMTOM_API_KEY: str = ""
    TOMTOM_BASE_URL: str = "https://api.tomtom.com"
    TRAFFIC_CACHE_TTL_SECONDS: int = 35
    TRAFFIC_MONITOR_INTERVAL_SECONDS: int = 45
    REROUTE_COOLDOWN_SECONDS: int = 120
    MIN_TIME_SAVING_SECONDS: int = 300
    MIN_RELATIVE_IMPROVEMENT: float = 0.10

    @field_validator("DATABASE_URL", mode="before")
    @classmethod
    def _normalize_db_url(cls, value: str) -> str:
        return normalize_database_url(value)

    @property
    def is_production(self) -> bool:
        return self.APP_ENV.strip().lower() == "production" or os.getenv("VERCEL") == "1"

    def validate_database_configuration(self) -> None:
        if self.is_production and self.DATABASE_URL.startswith("sqlite") and not self.ALLOW_SQLITE_IN_PRODUCTION:
            raise RuntimeError(
                "DATABASE_URL is not configured for production (refusing SQLite fallback on read-only/ephemeral "
                "production filesystem). Set DATABASE_URL to a PostgreSQL/PostGIS URL (e.g. "
                "postgresql+psycopg://user:password@host:5432/dbname?sslmode=require) on your backend host."
            )

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
