"""Unit tests for evaluate: weighted score, knockout, confidence, high-confidence mode, conflict detection."""
from unittest.mock import AsyncMock, patch

import pytest

from src.models.ad import Ad, AdStatus
from src.models.evaluation import (
    EvaluationResult,
    DimensionScore,
    ConfidenceLevel,
)
from src.models.weights import (
    DimensionWeights,
    KnockoutThresholds,
    apply_knockouts,
    VarsityTutorsSATProfiles,
)


# --- Weighted score calculation ---


def test_weighted_score_is_sum_of_score_times_weight_for_all_five_dimensions():
    from src.evaluate.aggregator import compute_weighted_score
    weights = DimensionWeights(
        clarity=0.20,
        value_proposition=0.30,
        cta=0.25,
        brand_voice=0.15,
        emotional_resonance=0.10,
    )
    scores = {
        "clarity": 8.0,
        "value_proposition": 7.0,
        "cta": 6.0,
        "brand_voice": 7.0,
        "emotional_resonance": 6.0,
    }
    result = compute_weighted_score(scores, weights)
    expected = 8 * 0.20 + 7 * 0.30 + 6 * 0.25 + 7 * 0.15 + 6 * 0.10
    assert abs(result - expected) < 0.001


def test_weighted_score_uses_profile_weights_not_equal():
    from src.evaluate.aggregator import compute_weighted_score
    profile = VarsityTutorsSATProfiles.PARENT_CONVERSION
    scores = {
        "clarity": 7.0,
        "value_proposition": 7.0,
        "cta": 7.0,
        "brand_voice": 7.0,
        "emotional_resonance": 7.0,
    }
    result = compute_weighted_score(scores, profile.weights)
    assert abs(result - 7.0) < 0.001


def test_weighted_score_parent_conversion_manual_calculation_matches():
    from src.evaluate.aggregator import compute_weighted_score
    profile = VarsityTutorsSATProfiles.PARENT_CONVERSION
    scores = {
        "clarity": 6.0,
        "value_proposition": 8.0,
        "cta": 7.0,
        "brand_voice": 6.0,
        "emotional_resonance": 5.0,
    }
    result = compute_weighted_score(scores, profile.weights)
    manual = 6 * 0.20 + 8 * 0.30 + 7 * 0.25 + 6 * 0.15 + 5 * 0.10
    assert abs(result - manual) < 0.001


def test_weighted_score_dimension_outside_one_to_ten_raises_value_error():
    from src.evaluate.aggregator import compute_weighted_score
    weights = DimensionWeights(
        clarity=0.20,
        value_proposition=0.30,
        cta=0.25,
        brand_voice=0.15,
        emotional_resonance=0.10,
    )
    scores = {
        "clarity": 10.5,
        "value_proposition": 7.0,
        "cta": 7.0,
        "brand_voice": 7.0,
        "emotional_resonance": 7.0,
    }
    with pytest.raises(ValueError):
        compute_weighted_score(scores, weights)


# --- Knockout enforcement ---


def test_knockout_all_scores_above_thresholds_passed_true():
    from src.models.weights import apply_knockouts
    thresholds = KnockoutThresholds(clarity=5.0, cta=6.0, brand_voice=5.0)
    scores = {"clarity": 6.0, "cta": 7.0, "brand_voice": 6.0}
    result = apply_knockouts(scores, thresholds)
    assert result.knockout_passed is True


def test_knockout_clarity_four_point_nine_threshold_five_failed():
    thresholds = KnockoutThresholds(clarity=5.0, cta=6.0, brand_voice=5.0)
    scores = {"clarity": 4.9, "cta": 7.0, "brand_voice": 6.0}
    result = apply_knockouts(scores, thresholds)
    assert result.knockout_passed is False
    assert "clarity" in result.knockout_failures


def test_knockout_clarity_five_point_zero_exactly_passed_inclusive():
    thresholds = KnockoutThresholds(clarity=5.0, cta=6.0, brand_voice=5.0)
    scores = {"clarity": 5.0, "cta": 7.0, "brand_voice": 6.0}
    result = apply_knockouts(scores, thresholds)
    assert result.knockout_passed is True


def test_knockout_two_failures_both_in_knockout_failures_list():
    thresholds = KnockoutThresholds(clarity=5.0, cta=6.0, brand_voice=5.0)
    scores = {"clarity": 4.0, "cta": 5.5, "brand_voice": 6.0}
    result = apply_knockouts(scores, thresholds)
    assert result.knockout_passed is False
    assert "clarity" in result.knockout_failures
    assert "cta" in result.knockout_failures


def test_knockout_passed_false_does_not_change_weighted_score():
    from src.evaluate.aggregator import compute_weighted_score
    weights = VarsityTutorsSATProfiles.PARENT_CONVERSION.weights
    scores = {"clarity": 4.9, "value_proposition": 8.0, "cta": 8.0, "brand_voice": 8.0, "emotional_resonance": 8.0}
    weighted = compute_weighted_score(scores, weights)
    assert weighted > 7.0
    result = apply_knockouts(scores, VarsityTutorsSATProfiles.PARENT_CONVERSION.knockout_thresholds)
    assert result.knockout_passed is False
    assert abs(compute_weighted_score(scores, weights) - weighted) < 0.001


# --- Confidence level classification ---


def test_confidence_above_point_eighty_is_high():
    from src.evaluate.confidence import get_confidence_level
    assert get_confidence_level(0.85) == ConfidenceLevel.HIGH


def test_confidence_point_eighty_is_medium_not_high():
    from src.evaluate.confidence import get_confidence_level
    assert get_confidence_level(0.80) == ConfidenceLevel.MEDIUM


def test_confidence_sixty_to_eighty_is_medium():
    from src.evaluate.confidence import get_confidence_level
    assert get_confidence_level(0.70) == ConfidenceLevel.MEDIUM


def test_confidence_point_sixty_is_low_not_medium():
    from src.evaluate.confidence import get_confidence_level
    assert get_confidence_level(0.60) == ConfidenceLevel.LOW


def test_confidence_below_point_sixty_is_low():
    from src.evaluate.confidence import get_confidence_level
    assert get_confidence_level(0.50) == ConfidenceLevel.LOW


# --- High confidence mode trigger ---


def test_high_confidence_mode_triggered_when_abs_score_minus_threshold_le_band():
    from src.evaluate.confidence import should_use_high_confidence_mode
    from src.config.settings import get_settings
    assert should_use_high_confidence_mode(7.0, 7.0, 0.75) is True
    assert should_use_high_confidence_mode(7.5, 7.0, 0.75) is True
    assert should_use_high_confidence_mode(6.5, 7.0, 0.75) is True


def test_single_pass_mode_when_abs_score_minus_threshold_gt_band():
    from src.evaluate.confidence import should_use_high_confidence_mode
    assert should_use_high_confidence_mode(8.0, 7.0, 0.75) is False
    assert should_use_high_confidence_mode(5.5, 7.0, 0.75) is False


@pytest.mark.asyncio
async def test_high_confidence_mode_runs_exactly_three_evaluation_calls():
    from src.evaluate.judge import ClaudeJudge
    mock_settings = patch("src.evaluate.judge.get_settings")
    with mock_settings as m:
        m.return_value.confidence_band = 0.75
        with patch("src.evaluate.judge._call_claude", new_callable=AsyncMock) as mock_claude:
            mock_claude.return_value = _mock_claude_eval_response()
            judge = ClaudeJudge()
            ad = Ad(brief_id="b1", primary_text="C", headline="H", description="D", cta_button="Learn More", status=AdStatus.DRAFT)
            profile = VarsityTutorsSATProfiles.PARENT_CONVERSION
            with patch("src.evaluate.judge.should_use_high_confidence_mode", return_value=True):
                await judge.evaluate(ad, profile, attempt_number=1)
            assert mock_claude.call_count == 3


@pytest.mark.asyncio
async def test_single_pass_mode_runs_one_evaluation_call():
    from src.evaluate.judge import ClaudeJudge
    with patch("src.evaluate.judge.get_settings") as m:
        m.return_value.confidence_band = 0.75
        with patch("src.evaluate.judge._call_claude", new_callable=AsyncMock) as mock_claude:
            mock_claude.return_value = _mock_claude_eval_response()
            judge = ClaudeJudge()
            ad = Ad(brief_id="b1", primary_text="C", headline="H", description="D", cta_button="Learn More", status=AdStatus.DRAFT)
            profile = VarsityTutorsSATProfiles.PARENT_CONVERSION
            with patch("src.evaluate.judge.should_use_high_confidence_mode", return_value=False):
                await judge.evaluate(ad, profile, attempt_number=1)
            assert mock_claude.call_count == 1


def _mock_claude_eval_response():
    return """{
        "dimension_scores": [
            {"dimension": "clarity", "score": 7.0, "rationale": "Ok", "self_confidence": 0.8},
            {"dimension": "value_proposition", "score": 7.0, "rationale": "Ok", "self_confidence": 0.8},
            {"dimension": "cta", "score": 7.0, "rationale": "Ok", "self_confidence": 0.8},
            {"dimension": "brand_voice", "score": 7.0, "rationale": "Ok", "self_confidence": 0.8},
            {"dimension": "emotional_resonance", "score": 7.0, "rationale": "Ok", "self_confidence": 0.8}
        ]
    }"""


# --- Conflict detection ---


def test_conflict_emotional_resonance_high_clarity_low_flagged():
    from src.evaluate.conflict_detector import detect_conflicts
    scores = {
        "clarity": 5.0,
        "value_proposition": 7.0,
        "cta": 7.0,
        "brand_voice": 7.0,
        "emotional_resonance": 8.0,
    }
    flags = detect_conflicts(scores)
    assert any("hook" in f.lower() or "unclear" in f.lower() for f in flags)


def test_conflict_emotional_resonance_7_4_clarity_5_5_no_conflict_boundary():
    from src.evaluate.conflict_detector import detect_conflicts
    scores = {
        "clarity": 5.5,
        "value_proposition": 7.0,
        "cta": 7.0,
        "brand_voice": 7.0,
        "emotional_resonance": 7.4,
    }
    flags = detect_conflicts(scores)
    assert len(flags) == 0


def test_conflict_clarity_high_emotional_resonance_low_flagged():
    from src.evaluate.conflict_detector import detect_conflicts
    scores = {
        "clarity": 8.5,
        "value_proposition": 7.0,
        "cta": 7.0,
        "brand_voice": 7.0,
        "emotional_resonance": 4.0,
    }
    flags = detect_conflicts(scores)
    assert any("clear" in f.lower() or "care" in f.lower() for f in flags)


def test_conflict_cta_strong_value_prop_weak_flagged():
    from src.evaluate.conflict_detector import detect_conflicts
    scores = {
        "clarity": 7.0,
        "value_proposition": 4.5,
        "cta": 8.0,
        "brand_voice": 7.0,
        "emotional_resonance": 7.0,
    }
    flags = detect_conflicts(scores)
    assert any("urgent" in f.lower() or "reason" in f.lower() or "act" in f.lower() for f in flags)


def test_conflict_no_pattern_met_returns_empty_flags():
    from src.evaluate.conflict_detector import detect_conflicts
    scores = {
        "clarity": 7.0,
        "value_proposition": 7.0,
        "cta": 7.0,
        "brand_voice": 7.0,
        "emotional_resonance": 7.0,
    }
    assert detect_conflicts(scores) == []


# --- EvaluationResult.is_publishable (evaluate spec) ---


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


def test_evaluation_result_requires_human_review_still_returns_is_publishable_by_score():
    scores = [
        DimensionScore(dimension="clarity", score=7.5, rationale="Ok", self_confidence=0.8),
        DimensionScore(dimension="value_proposition", score=7.5, rationale="Ok", self_confidence=0.8),
        DimensionScore(dimension="cta", score=7.5, rationale="Ok", self_confidence=0.8),
        DimensionScore(dimension="brand_voice", score=7.5, rationale="Ok", self_confidence=0.8),
        DimensionScore(dimension="emotional_resonance", score=7.5, rationale="Ok", self_confidence=0.8),
    ]
    ev = EvaluationResult(
        ad_id="ad-1",
        attempt_number=1,
        weighted_score=7.5,
        knockout_passed=True,
        knockout_failures=[],
        dimension_scores=scores,
        requires_human_review=True,
        flags=[],
        confidence=0.85,
        confidence_level=ConfidenceLevel.HIGH,
    )
    assert ev.is_publishable(quality_threshold=7.0) is True


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
