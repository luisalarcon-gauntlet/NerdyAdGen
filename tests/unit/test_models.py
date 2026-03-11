"""Unit tests for Ad, EvaluationResult, TokenUsageRecord, and iteration models."""
import pytest
from pydantic import ValidationError

from src.models.ad import Ad, AdStatus
from src.models.brief import Brief, AudienceType, CampaignGoal, Platform
from src.models.evaluation import (
    EvaluationResult,
    DimensionScore,
    ConfidenceLevel,
    FlagType,
)
from src.models.metrics import TokenUsageRecord
from src.models.iteration import (
    IterationRecord,
    QualityFailureRecord,
    FailureDiagnosis,
    FailurePattern,
)


# --- Ad, AdStatus ---


def test_ad_with_required_fields_valid():
    Ad(
        brief_id="brief-1",
        primary_text="Get better SAT scores.",
        headline="SAT Prep",
        description="Expert tutoring.",
        cta_button="Learn More",
        status=AdStatus.DRAFT,
    )


def test_ad_image_url_and_image_prompt_none_in_v1():
    ad = Ad(
        brief_id="brief-1",
        primary_text="Copy",
        headline="Head",
        description="Desc",
        cta_button="Learn More",
        status=AdStatus.DRAFT,
        image_url=None,
        image_prompt=None,
    )
    assert ad.image_url is None
    assert ad.image_prompt is None


def test_ad_id_is_uuid4_string():
    ad = Ad(
        brief_id="brief-1",
        primary_text="Copy",
        headline="Head",
        description="Desc",
        cta_button="Learn More",
        status=AdStatus.DRAFT,
    )
    assert isinstance(ad.id, str)
    assert len(ad.id) == 36
    assert ad.id[8] == "-" and ad.id[13] == "-" and ad.id[18] == "-" and ad.id[23] == "-"


def test_ad_created_at_is_iso8601_utc():
    ad = Ad(
        brief_id="brief-1",
        primary_text="Copy",
        headline="Head",
        description="Desc",
        cta_button="Learn More",
        status=AdStatus.DRAFT,
    )
    assert "T" in ad.created_at
    assert "Z" in ad.created_at or "+" in ad.created_at


# --- EvaluationResult.is_publishable ---


def test_evaluation_result_is_publishable_true_when_knockout_passed_and_score_at_threshold():
    scores = [
        DimensionScore(dimension="clarity", score=7.0, rationale="Ok", self_confidence=0.8),
        DimensionScore(dimension="value_proposition", score=7.0, rationale="Ok", self_confidence=0.8),
        DimensionScore(dimension="cta", score=7.0, rationale="Ok", self_confidence=0.8),
        DimensionScore(dimension="brand_voice", score=7.0, rationale="Ok", self_confidence=0.8),
        DimensionScore(dimension="emotional_resonance", score=7.0, rationale="Ok", self_confidence=0.8),
    ]
    ev = EvaluationResult(
        ad_id="ad-1",
        attempt_number=1,
        weighted_score=7.0,
        knockout_passed=True,
        knockout_failures=[],
        dimension_scores=scores,
        requires_human_review=False,
        flags=[],
        confidence=0.85,
        confidence_level=ConfidenceLevel.HIGH,
    )
    assert ev.is_publishable(quality_threshold=7.0) is True


def test_evaluation_result_is_publishable_false_when_knockout_failed():
    scores = [
        DimensionScore(dimension="clarity", score=4.0, rationale="Low", self_confidence=0.8),
        DimensionScore(dimension="value_proposition", score=8.0, rationale="Ok", self_confidence=0.8),
        DimensionScore(dimension="cta", score=8.0, rationale="Ok", self_confidence=0.8),
        DimensionScore(dimension="brand_voice", score=8.0, rationale="Ok", self_confidence=0.8),
        DimensionScore(dimension="emotional_resonance", score=8.0, rationale="Ok", self_confidence=0.8),
    ]
    ev = EvaluationResult(
        ad_id="ad-1",
        attempt_number=1,
        weighted_score=9.0,
        knockout_passed=False,
        knockout_failures=["clarity"],
        dimension_scores=scores,
        requires_human_review=False,
        flags=[],
        confidence=0.85,
        confidence_level=ConfidenceLevel.HIGH,
    )
    assert ev.is_publishable(quality_threshold=7.0) is False


def test_evaluation_result_is_publishable_false_when_score_below_threshold():
    scores = [
        DimensionScore(dimension="clarity", score=6.5, rationale="Ok", self_confidence=0.8),
        DimensionScore(dimension="value_proposition", score=6.5, rationale="Ok", self_confidence=0.8),
        DimensionScore(dimension="cta", score=6.5, rationale="Ok", self_confidence=0.8),
        DimensionScore(dimension="brand_voice", score=6.5, rationale="Ok", self_confidence=0.8),
        DimensionScore(dimension="emotional_resonance", score=6.5, rationale="Ok", self_confidence=0.8),
    ]
    ev = EvaluationResult(
        ad_id="ad-1",
        attempt_number=1,
        weighted_score=6.9,
        knockout_passed=True,
        knockout_failures=[],
        dimension_scores=scores,
        requires_human_review=False,
        flags=[],
        confidence=0.85,
        confidence_level=ConfidenceLevel.HIGH,
    )
    assert ev.is_publishable(quality_threshold=7.0) is False


# --- EvaluationResult.weakest_dimension ---


def test_evaluation_result_weakest_dimension_returns_lowest_scoring():
    scores = [
        DimensionScore(dimension="clarity", score=8.0, rationale="Ok", self_confidence=0.8),
        DimensionScore(dimension="value_proposition", score=4.0, rationale="Low", self_confidence=0.8),
        DimensionScore(dimension="cta", score=7.0, rationale="Ok", self_confidence=0.8),
        DimensionScore(dimension="brand_voice", score=7.0, rationale="Ok", self_confidence=0.8),
        DimensionScore(dimension="emotional_resonance", score=7.0, rationale="Ok", self_confidence=0.8),
    ]
    ev = EvaluationResult(
        ad_id="ad-1",
        attempt_number=1,
        weighted_score=6.6,
        knockout_passed=True,
        knockout_failures=[],
        dimension_scores=scores,
        requires_human_review=False,
        flags=[],
        confidence=0.85,
        confidence_level=ConfidenceLevel.HIGH,
    )
    assert ev.weakest_dimension.dimension == "value_proposition"
    assert ev.weakest_dimension.score == 4.0


def test_evaluation_result_weakest_dimension_tie_breaks_by_list_order():
    scores = [
        DimensionScore(dimension="clarity", score=5.0, rationale="Ok", self_confidence=0.8),
        DimensionScore(dimension="value_proposition", score=5.0, rationale="Ok", self_confidence=0.8),
        DimensionScore(dimension="cta", score=8.0, rationale="Ok", self_confidence=0.8),
        DimensionScore(dimension="brand_voice", score=8.0, rationale="Ok", self_confidence=0.8),
        DimensionScore(dimension="emotional_resonance", score=8.0, rationale="Ok", self_confidence=0.8),
    ]
    ev = EvaluationResult(
        ad_id="ad-1",
        attempt_number=1,
        weighted_score=6.8,
        knockout_passed=True,
        knockout_failures=[],
        dimension_scores=scores,
        requires_human_review=False,
        flags=[],
        confidence=0.85,
        confidence_level=ConfidenceLevel.HIGH,
    )
    assert ev.weakest_dimension.dimension == "clarity"


# --- TokenUsageRecord ---


def test_token_usage_record_with_required_fields_valid():
    TokenUsageRecord(
        ad_id="ad-1",
        brief_id="brief-1",
        operation="generation",
        provider="google",
        model="gemini-1.5-flash",
        input_tokens=100,
        output_tokens=50,
        cost_usd=0.01,
    )


def test_token_usage_record_id_is_uuid4_string():
    r = TokenUsageRecord(
        ad_id="ad-1",
        brief_id="brief-1",
        operation="evaluation",
        provider="anthropic",
        model="claude-sonnet-4-6",
        input_tokens=200,
        output_tokens=100,
        cost_usd=0.02,
    )
    assert isinstance(r.id, str)
    assert len(r.id) == 36


# --- Iteration models ---


def test_iteration_record_with_required_fields_valid():
    IterationRecord(
        ad_id="ad-1",
        attempt_number=2,
        tier="targeted",
        target_dimension="cta",
        strategy="TARGETED",
        score_before=6.5,
        score_after=7.2,
        dimensions_improved=[],
        dimensions_regressed=[],
        oscillation_detected=False,
        cost_usd=0.01,
    )


def test_quality_failure_record_valid():
    QualityFailureRecord(
        ad_id="ad-1",
        brief_id="brief-1",
        attempt_number=7,
        failure_pattern=FailurePattern.PERSISTENT_WEAKNESS,
        diagnosis=FailureDiagnosis(
            pattern=FailurePattern.PERSISTENT_WEAKNESS,
            summary="Clarity below 6.0 across all attempts",
            suggested_action="Brief revision",
        ),
    )


def test_failure_pattern_enum_values():
    assert FailurePattern.PERSISTENT_WEAKNESS.value == "persistent_weakness"
    assert FailurePattern.OSCILLATION.value == "oscillation"
    assert FailurePattern.STALLED_IMPROVEMENT.value == "stalled_improvement"


def test_failure_diagnosis_with_required_fields_valid():
    d = FailureDiagnosis(
        pattern=FailurePattern.PERSISTENT_WEAKNESS,
        summary="Clarity below 6.0 across all attempts",
        suggested_action="Brief revision",
    )
    assert d.pattern == FailurePattern.PERSISTENT_WEAKNESS
    assert d.summary == "Clarity below 6.0 across all attempts"