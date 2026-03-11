"""Unit tests for scraper: ad usability, language detection, ScrapedAd, calibration bands and pass rate."""
from unittest.mock import patch

import pytest
from pydantic import ValidationError

from src.scraper.ad_parser import is_ad_usable, get_skip_reason, is_english
from src.scraper.calibration_cli import (
    score_to_band,
    get_calibration_verdict,
    CalibrationError,
)
from src.models.scraped_ad import ScrapedAd


# --- Ad usability filter ---


def test_ad_with_primary_text_is_usable():
    assert is_ad_usable(primary_text="Get better SAT scores.", headline=None) is True


def test_ad_with_only_headline_no_primary_text_is_usable():
    assert is_ad_usable(primary_text=None, headline="SAT Prep") is True


def test_ad_with_neither_primary_text_nor_headline_is_not_usable():
    assert is_ad_usable(primary_text=None, headline=None) is False


def test_ad_with_both_primary_text_and_headline_is_usable():
    assert is_ad_usable(primary_text="Copy", headline="Head") is True


def test_is_usable_false_skip_reason_is_no_copy_text():
    assert get_skip_reason(primary_text=None, headline=None) == "no_copy_text"


def test_is_usable_true_skip_reason_is_none():
    assert get_skip_reason(primary_text="Copy", headline=None) is None
    assert get_skip_reason(primary_text=None, headline="Head") is None


# --- Language detection ---


def test_english_primary_text_is_english_true():
    assert is_english("Improve your SAT score with expert tutoring.") is True


def test_spanish_primary_text_is_english_false():
    assert is_english("Mejora tu puntuación SAT con tutoría experta.") is False


@patch("src.scraper.ad_parser.detect", side_effect=Exception("langdetect failed"))
def test_langdetect_exception_defaults_to_is_english_true(_mock_detect):
    assert is_english("some text") is True


# --- ScrapedAd model validation ---


def test_scraped_ad_with_required_fields_valid():
    ad = ScrapedAd(
        ad_library_id="meta_123",
        competitor="princeton_review",
        primary_text="SAT prep copy",
        raw_html="<div>...</div>",
        scraped_at="2025-03-09T12:00:00Z",
    )
    assert ad.ad_library_id == "meta_123"
    assert ad.competitor == "princeton_review"
    assert ad.primary_text == "SAT prep copy"


def test_scraped_ad_missing_ad_library_id_raises_validation_error():
    with pytest.raises(ValidationError):
        ScrapedAd(
            competitor="princeton_review",
            primary_text="Copy",
            raw_html="<div></div>",
            scraped_at="2025-03-09T12:00:00Z",
        )


def test_scraped_ad_missing_competitor_raises_validation_error():
    with pytest.raises(ValidationError):
        ScrapedAd(
            ad_library_id="meta_123",
            primary_text="Copy",
            raw_html="<div></div>",
            scraped_at="2025-03-09T12:00:00Z",
        )


def test_scraped_ad_calibration_quality_defaults_to_none():
    ad = ScrapedAd(
        ad_library_id="meta_123",
        competitor="kaplan",
        primary_text="Copy",
        raw_html="<div></div>",
        scraped_at="2025-03-09T12:00:00Z",
    )
    assert ad.calibration_quality is None


def test_scraped_ad_calibration_score_defaults_to_none():
    ad = ScrapedAd(
        ad_library_id="meta_123",
        competitor="kaplan",
        primary_text="Copy",
        raw_html="<div></div>",
        scraped_at="2025-03-09T12:00:00Z",
    )
    assert ad.calibration_score is None


def test_scraped_ad_with_headline_only_no_primary_text_valid():
    ad = ScrapedAd(
        ad_library_id="meta_456",
        competitor="khan_academy",
        headline="Headline only",
        raw_html="<div></div>",
        scraped_at="2025-03-09T12:00:00Z",
    )
    assert ad.primary_text is None
    assert ad.headline == "Headline only"


# --- Calibration score band classification ---

_REQUIRED_ENV_FOR_SETTINGS = {
    "GEMINI_API_KEY": "test_gemini_key",
    "ANTHROPIC_API_KEY": "test_anthropic_key",
    "LANGSMITH_API_KEY": "test_langsmith_key",
    "DATABASE_URL": "postgresql+asyncpg://user:pass@localhost:5432/test",
}


def _set_required_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for k, v in _REQUIRED_ENV_FOR_SETTINGS.items():
        monkeypatch.setenv(k, v)


def test_calibration_score_five_point_nine_is_low(monkeypatch: pytest.MonkeyPatch):
    _set_required_env(monkeypatch)
    monkeypatch.setattr("src.config.settings._settings", None)
    assert score_to_band(5.9) == "low"


def test_calibration_score_six_point_zero_is_medium(monkeypatch: pytest.MonkeyPatch):
    _set_required_env(monkeypatch)
    monkeypatch.setattr("src.config.settings._settings", None)
    assert score_to_band(6.0) == "medium"


def test_calibration_score_seven_point_four_is_medium(monkeypatch: pytest.MonkeyPatch):
    _set_required_env(monkeypatch)
    monkeypatch.setattr("src.config.settings._settings", None)
    assert score_to_band(7.4) == "medium"


def test_calibration_score_seven_point_five_is_high(monkeypatch: pytest.MonkeyPatch):
    _set_required_env(monkeypatch)
    monkeypatch.setattr("src.config.settings._settings", None)
    assert score_to_band(7.5) == "high"


def test_calibration_score_seven_point_six_is_high(monkeypatch: pytest.MonkeyPatch):
    _set_required_env(monkeypatch)
    monkeypatch.setattr("src.config.settings._settings", None)
    assert score_to_band(7.6) == "high"


# --- Calibration pass rate thresholds ---


@patch("src.scraper.calibration_cli.get_settings")
def test_calibration_sixteen_correct_out_of_twenty_is_pass(mock_get_settings):
    mock_get_settings.return_value.calibration_min_annotated = 20
    mock_get_settings.return_value.calibration_pass_threshold = 0.75
    mock_get_settings.return_value.calibration_halt_threshold = 0.50
    assert get_calibration_verdict(correct=16, total=20) == "PASS"


@patch("src.scraper.calibration_cli.get_settings")
def test_calibration_fifteen_correct_out_of_twenty_boundary_is_pass(mock_get_settings):
    mock_get_settings.return_value.calibration_min_annotated = 20
    mock_get_settings.return_value.calibration_pass_threshold = 0.75
    mock_get_settings.return_value.calibration_halt_threshold = 0.50
    assert get_calibration_verdict(correct=15, total=20) == "PASS"


@patch("src.scraper.calibration_cli.get_settings")
def test_calibration_fourteen_correct_out_of_twenty_is_adjust(mock_get_settings):
    mock_get_settings.return_value.calibration_min_annotated = 20
    mock_get_settings.return_value.calibration_pass_threshold = 0.75
    mock_get_settings.return_value.calibration_halt_threshold = 0.50
    assert get_calibration_verdict(correct=14, total=20) == "ADJUST"


@patch("src.scraper.calibration_cli.get_settings")
def test_calibration_ten_correct_out_of_twenty_boundary_is_halt(mock_get_settings):
    mock_get_settings.return_value.calibration_min_annotated = 20
    mock_get_settings.return_value.calibration_pass_threshold = 0.75
    mock_get_settings.return_value.calibration_halt_threshold = 0.50
    assert get_calibration_verdict(correct=10, total=20) == "HALT"


@patch("src.scraper.calibration_cli.get_settings")
def test_calibration_nine_correct_out_of_twenty_is_halt(mock_get_settings):
    mock_get_settings.return_value.calibration_min_annotated = 20
    mock_get_settings.return_value.calibration_pass_threshold = 0.75
    mock_get_settings.return_value.calibration_halt_threshold = 0.50
    assert get_calibration_verdict(correct=9, total=20) == "HALT"


@patch("src.scraper.calibration_cli.get_settings")
def test_calibration_fewer_than_min_annotated_raises_calibration_error(mock_get_settings):
    mock_get_settings.return_value.calibration_min_annotated = 20
    mock_get_settings.return_value.calibration_pass_threshold = 0.75
    mock_get_settings.return_value.calibration_halt_threshold = 0.50
    with pytest.raises(CalibrationError):
        get_calibration_verdict(correct=15, total=19)
