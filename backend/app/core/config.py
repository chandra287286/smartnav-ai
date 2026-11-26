import os
from functools import lru_cache
from typing import List
from pydantic_settings import BaseSettings, SettingsConfigDict


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

    # PostgreSQL + PostGIS in production; defaults to local SQLite if DATABASE_URL isn't set
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./smartnav.db")

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

    @property
    def cors_origins_list(self) -> List[str]:
        return [origin.strip() for origin in self.CORS_ORIGINS.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
