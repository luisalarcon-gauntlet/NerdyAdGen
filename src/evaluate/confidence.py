"""Confidence level classification and high-confidence mode trigger."""

from src.models.evaluation import ConfidenceLevel


def get_confidence_level(confidence: float) -> ConfidenceLevel:
    """Classify confidence: >0.80 HIGH, 0.60–0.80 MEDIUM (0.80 is MEDIUM), <0.60 LOW (0.60 is LOW)."""
    if confidence > 0.80:
        return ConfidenceLevel.HIGH
    if confidence > 0.60:
        return ConfidenceLevel.MEDIUM
    return ConfidenceLevel.LOW


def should_use_high_confidence_mode(
    weighted_score: float,
    quality_threshold: float,
    band: float,
) -> bool:
    """True when abs(weighted_score - quality_threshold) <= band (default 0.75)."""
    return abs(weighted_score - quality_threshold) <= band
