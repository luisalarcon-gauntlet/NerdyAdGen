"""Unit tests for Settings and config."""
from typing import Optional

import pytest
from pydantic import ValidationError


# Required env vars for Settings to load (we set these in tests)
_REQUIRED_ENV = {
    "GEMINI_API_KEY": "test_gemini_key",
    "ANTHROPIC_API_KEY": "test_anthropic_key",
    "LANGSMITH_API_KEY": "test_langsmith_key",
    "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost:5432/test",
}


def _set_required_env(monkeypatch: pytest.MonkeyPatch, extra: Optional[dict] = None) -> None:
    for k, v in _REQUIRED_ENV.items():
        monkeypatch.setenv(k, v)
    if extra:
        for k, v in extra.items():
            monkeypatch.setenv(k, v)


def test_settings_loads_from_env_when_all_required_keys_present(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)
    from src.config.settings import Settings
    settings = Settings()
    assert settings.gemini_api_key == "test_gemini_key"
    assert settings.database_url.startswith("postgresql+asyncpg")


def test_settings_missing_gemini_api_key_raises_validation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    from src.config.settings import Settings
    with pytest.raises(ValidationError):
        Settings()


def test_settings_missing_anthropic_api_key_raises_validation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    from src.config.settings import Settings
    with pytest.raises(ValidationError):
        Settings()


def test_settings_missing_database_url_raises_validation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.delenv("DATABASE_URL", raising=False)
    from src.config.settings import Settings
    with pytest.raises(ValidationError):
        Settings()


def test_settings_pipeline_version_not_set_defaults_to_v1(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.delenv("PIPELINE_VERSION", raising=False)
    from src.config.settings import Settings
    settings = Settings()
    assert settings.pipeline_version == "v1"


def test_settings_quality_threshold_not_set_defaults_to_seven(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.delenv("QUALITY_THRESHOLD", raising=False)
    from src.config.settings import Settings
    settings = Settings()
    assert settings.quality_threshold == 7.0


def test_settings_human_review_enabled_not_set_defaults_to_true(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.delenv("HUMAN_REVIEW_ENABLED", raising=False)
    from src.config.settings import Settings
    settings = Settings()
    assert settings.human_review_enabled is True


def test_settings_max_iteration_attempts_not_set_defaults_to_seven(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch)
    monkeypatch.delenv("MAX_ITERATION_ATTEMPTS", raising=False)
    from src.config.settings import Settings
    settings = Settings()
    assert settings.max_iteration_attempts == 7


# --- Settings validation ---


def test_settings_human_review_urgency_minimum_low_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch, {"HUMAN_REVIEW_URGENCY_MINIMUM": "low"})
    from src.config.settings import Settings
    settings = Settings()
    assert settings.human_review_urgency_minimum == "low"


def test_settings_human_review_urgency_minimum_medium_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch, {"HUMAN_REVIEW_URGENCY_MINIMUM": "medium"})
    from src.config.settings import Settings
    settings = Settings()
    assert settings.human_review_urgency_minimum == "medium"


def test_settings_human_review_urgency_minimum_high_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch, {"HUMAN_REVIEW_URGENCY_MINIMUM": "high"})
    from src.config.settings import Settings
    settings = Settings()
    assert settings.human_review_urgency_minimum == "high"


def test_settings_human_review_urgency_minimum_urgent_raises_validation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch, {"HUMAN_REVIEW_URGENCY_MINIMUM": "urgent"})
    from src.config.settings import Settings
    with pytest.raises(ValidationError):
        Settings()


def test_settings_pipeline_version_v1_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch, {"PIPELINE_VERSION": "v1"})
    from src.config.settings import Settings
    assert Settings().pipeline_version == "v1"


def test_settings_pipeline_version_v2_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch, {"PIPELINE_VERSION": "v2"})
    from src.config.settings import Settings
    assert Settings().pipeline_version == "v2"


def test_settings_pipeline_version_v3_valid(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch, {"PIPELINE_VERSION": "v3"})
    from src.config.settings import Settings
    assert Settings().pipeline_version == "v3"


def test_settings_pipeline_version_v4_raises_validation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch, {"PIPELINE_VERSION": "v4"})
    from src.config.settings import Settings
    with pytest.raises(ValidationError):
        Settings()


def test_settings_quality_threshold_zero_point_nine_raises_validation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch, {"QUALITY_THRESHOLD": "0.9"})
    from src.config.settings import Settings
    with pytest.raises(ValidationError):
        Settings()


def test_settings_quality_threshold_ten_point_one_raises_validation_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _set_required_env(monkeypatch, {"QUALITY_THRESHOLD": "10.1"})
    from src.config.settings import Settings
    with pytest.raises(ValidationError):
        Settings()
