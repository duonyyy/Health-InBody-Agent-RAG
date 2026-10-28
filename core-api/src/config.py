"""Configuration settings for Core Business API."""

import os
from pydantic_settings import BaseSettings, SettingsConfigDict


class CoreSettings(BaseSettings):
    port: int = int(os.getenv("PORT", 8000))
    database_url: str = os.getenv(
        "DATABASE_URL",
        "sqlite:///./core_health.db",
    )
    db_pool_size: int = int(os.getenv("DB_POOL_SIZE", 5))
    db_max_overflow: int = int(os.getenv("DB_MAX_OVERFLOW", 10))

    redis_host: str = os.getenv("REDIS_HOST", "localhost")
    redis_port: int = int(os.getenv("REDIS_PORT", 6379))

    agent_service_url: str = os.getenv("AGENT_SERVICE_URL", "http://localhost:8001").rstrip("/")
    ocr_service_url: str = os.getenv("OCR_SERVICE_URL", "http://localhost:18100").rstrip("/")

    auth_mode: str = os.getenv("AUTH_MODE", "development").strip().lower()
    feature_ocr_upload: bool = os.getenv("FEATURE_OCR_UPLOAD", "true").lower() in {"1", "true", "yes", "on"}

    agent_request_timeout: int = int(os.getenv("AGENT_REQUEST_TIMEOUT", 45))

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


settings = CoreSettings()
