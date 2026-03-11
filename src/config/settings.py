"""Single source of truth for configuration. Loads from .env."""
from typing import Literal, Optional

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All configuration. Required keys must be set in .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    # API Keys
    gemini_api_key: str
    anthropic_api_key: str
    langsmith_api_key: str
    nano_banana_api_key: Optional[str] = None

    # Database
    database_url: str
    database_url_test: Optional[str] = None

    # LangSmith
    langsmith_project: str = "nerdy-ad-engine"
    langchain_tracing_v2: bool = True
    langsmith_enabled: bool = True

    # Pipeline behaviour
    quality_threshold: float = Field(default=7.0, ge=1.0, le=10.0)
    max_iteration_attempts: int = 7
    confidence_band: float = 0.75
    pipeline_version: Literal["v1", "v2", "v3"] = "v1"

    # Human review
    human_review_enabled: bool = True
    human_review_urgency_minimum: Literal["low", "medium", "high"] = "low"

    # Logging
    log_file_path: str = "data/pipeline.log"

    # Scraping
    scraping_delay_seconds: float = 2.0
    scraping_jitter_seconds: float = 1.0

    # Calibration (scraper / reference ads)
    calibration_min_annotated: int = Field(default=20, ge=1)
    calibration_pass_threshold: float = Field(default=0.75, ge=0.0, le=1.0)
    calibration_halt_threshold: float = Field(default=0.50, ge=0.0, le=1.0)
    calibration_band_low_max: float = Field(default=6.0, ge=0.0, le=10.0)
    calibration_band_medium_max: float = Field(default=7.5, ge=0.0, le=10.0)
    calibration_band_high_max: float = Field(default=10.0, ge=0.0, le=10.0)


# Singleton for app use
_settings: Optional[Settings] = None


def get_settings() -> Settings:
    """Return cached settings or load from env."""
    global _settings
    if _settings is None:
        _settings = Settings()
    return _settings


# Convenience: allow `from src.config.settings import settings`
def __getattr__(name: str):
    if name == "settings":
        return get_settings()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
