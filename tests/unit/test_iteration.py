"""Unit tests for iterate: tier assignment, oscillation, regression, strategies, ratchet stub, diagnosis."""
import pytest

from src.models.evaluation import EvaluationResult, DimensionScore, ConfidenceLevel
from src.models.iteration import FailurePattern, FailureDiagnosis, IterationRecord
from src.generate.base import RegenerationStrategy, RegenerationApproach


# --- Tier assignment from attempt_number ---


def test_tier_attempt_1_is_targeted():
    from src.iterate.loop import get_tier_for_attempt
    assert get_tier_for_attempt(1) == "targeted"


def test_tier_attempt_3_is_targeted():
    from src.iterate.loop import get_tier_for_attempt
    assert get_tier_for_attempt(3) == "targeted"


def test_tier_attempt_4_is_full_rewrite():
    from src.iterate.loop import get_tier_for_attempt
    assert get_tier_for_attempt(4) == "full_rewrite"


def test_tier_attempt_5_is_full_rewrite():
    from src.iterate.loop import get_tier_for_attempt
    assert get_tier_for_attempt(5) == "full_rewrite"


def test_tier_attempt_6_is_brief_revision():
    from src.iterate.loop import get_tier_for_attempt
    assert get_tier_for_attempt(6) == "brief_revision"


def test_tier_attempt_7_is_abandon():
    from src.iterate.loop import get_tier_for_attempt
    assert get_tier_for_attempt(7) == "abandon"


def test_tier_attempt_10_is_abandon():
    from src.iterate.loop import get_tier_for_attempt
    assert get_tier_for_attempt(10) == "abandon"


# --- Oscillation detection ---


def test_oscillation_detected_when_same_two_dimensions_alternate():
    from src.iterate.tracker import IterationTracker
    tracker = IterationTracker()
    tracker.record_weakest("cta")
    tracker.record_weakest("emotional_resonance")
    tracker.record_weakest("cta")
    assert tracker.detect_oscillation() is True


def test_oscillation_not_detected_when_same_dimension_three_times():
    from src.iterate.tracker import IterationTracker
    tracker = IterationTracker()
    tracker.record_weakest("cta")
    tracker.record_weakest("cta")
    tracker.record_weakest("cta")
    assert tracker.detect_oscillation() is False


def test_oscillation_not_detected_when_three_different_dimensions():
    from src.iterate.tracker import IterationTracker
    tracker = IterationTracker()
    tracker.record_weakest("cta")
    tracker.record_weakest("emotional_resonance")
    tracker.record_weakest("brand_voice")
    assert tracker.detect_oscillation() is False


def test_oscillation_never_detected_with_only_two_attempts():
    from src.iterate.tracker import IterationTracker
    tracker = IterationTracker()
    tracker.record_weakest("cta")
    tracker.record_weakest("emotional_resonance")
    assert tracker.detect_oscillation() is False


def test_oscillation_detected_escalates_to_full_rewrite_regardless_of_attempt():
    from src.iterate.loop import get_tier_for_attempt, get_effective_tier
    # With oscillation, attempt 2 should still yield full_rewrite when we pass oscillation flag
    tier = get_effective_tier(attempt_number=2, oscillation_detected=True)
    assert tier == "full_rewrite"


# --- Regression detection (REGRESSION_THRESHOLD = 0.5) ---


def test_regression_dimension_drops_more_than_half_point_appears_in_list():
    from src.iterate.tracker import detect_regressions
    prev_scores = {"clarity": 7.0, "value_proposition": 8.0, "cta": 6.0, "brand_voice": 7.0, "emotional_resonance": 6.0}
    curr_scores = {"clarity": 6.3, "value_proposition": 8.0, "cta": 6.0, "brand_voice": 7.0, "emotional_resonance": 6.0}
    regressed = detect_regressions(prev_scores, curr_scores)
    assert "clarity" in regressed
    assert len(regressed) == 1


def test_regression_dimension_drops_exactly_half_point_not_in_list():
    from src.iterate.tracker import detect_regressions
    prev_scores = {"clarity": 7.0, "value_proposition": 8.0, "cta": 6.0, "brand_voice": 7.0, "emotional_resonance": 6.0}
    curr_scores = {"clarity": 6.5, "value_proposition": 8.0, "cta": 6.0, "brand_voice": 7.0, "emotional_resonance": 6.0}
    regressed = detect_regressions(prev_scores, curr_scores)
    assert "clarity" not in regressed


def test_regression_dimension_drops_less_than_half_point_not_in_list():
    from src.iterate.tracker import detect_regressions
    prev_scores = {"clarity": 7.0, "value_proposition": 8.0, "cta": 6.0, "brand_voice": 7.0, "emotional_resonance": 6.0}
    curr_scores = {"clarity": 6.6, "value_proposition": 8.0, "cta": 6.0, "brand_voice": 7.0, "emotional_resonance": 6.0}
    regressed = detect_regressions(prev_scores, curr_scores)
    assert "clarity" not in regressed


def test_regression_dimension_improves_not_in_list():
    from src.iterate.tracker import detect_regressions
    prev_scores = {"clarity": 6.0, "value_proposition": 8.0, "cta": 6.0, "brand_voice": 7.0, "emotional_resonance": 6.0}
    curr_scores = {"clarity": 7.0, "value_proposition": 8.0, "cta": 6.0, "brand_voice": 7.0, "emotional_resonance": 6.0}
    regressed = detect_regressions(prev_scores, curr_scores)
    assert len(regressed) == 0


def test_regression_two_dimensions_drop_both_appear():
    from src.iterate.tracker import detect_regressions
    prev_scores = {"clarity": 7.0, "value_proposition": 8.0, "cta": 7.0, "brand_voice": 7.0, "emotional_resonance": 6.0}
    curr_scores = {"clarity": 6.2, "value_proposition": 7.2, "cta": 7.0, "brand_voice": 7.0, "emotional_resonance": 6.0}
    regressed = detect_regressions(prev_scores, curr_scores)
    assert "clarity" in regressed
    assert "value_proposition" in regressed
    assert len(regressed) == 2


# --- Strategy selection per dimension ---


def test_strategy_clarity_is_full_rewrite():
    from src.iterate.strategies import get_strategy_for_dimension
    s = get_strategy_for_dimension("clarity")
    assert s.dimension == "clarity"
    assert s.approach == RegenerationApproach.FULL_REWRITE


def test_strategy_cta_is_targeted():
    from src.iterate.strategies import get_strategy_for_dimension
    s = get_strategy_for_dimension("cta")
    assert s.approach == RegenerationApproach.TARGETED


def test_strategy_emotional_resonance_is_hook_rewrite():
    from src.iterate.strategies import get_strategy_for_dimension
    s = get_strategy_for_dimension("emotional_resonance")
    assert s.approach == RegenerationApproach.HOOK_REWRITE


def test_strategy_brand_voice_is_tone_rewrite():
    from src.iterate.strategies import get_strategy_for_dimension
    s = get_strategy_for_dimension("brand_voice")
    assert s.approach == RegenerationApproach.TONE_REWRITE


def test_strategy_value_proposition_is_targeted():
    from src.iterate.strategies import get_strategy_for_dimension
    s = get_strategy_for_dimension("value_proposition")
    assert s.approach == RegenerationApproach.TARGETED


# --- Quality ratchet V1 stub ---


def test_ratchet_v1_never_changes_threshold():
    from src.iterate.ratchet import QualityRatchet
    ratchet = QualityRatchet(initial_threshold=7.0)
    before = ratchet.current_threshold
    ratchet.update(recent_scores=[8.0] * 10)
    assert ratchet.current_threshold == before


def test_ratchet_update_returns_would_trigger_key():
    from src.iterate.ratchet import QualityRatchet
    ratchet = QualityRatchet(initial_threshold=7.0)
    result = ratchet.update(recent_scores=[8.0] * 10)
    assert "would_trigger" in result


def test_ratchet_condition_met_when_avg_exceeds_threshold_plus_buffer():
    from src.iterate.ratchet import QualityRatchet
    ratchet = QualityRatchet(initial_threshold=7.0)
    # 8.0 >= 7.0 + 0.5 → condition met
    result = ratchet.update(recent_scores=[8.0] * 10)
    assert result.get("would_trigger") is True


def test_ratchet_condition_not_met_when_avg_below_threshold_plus_buffer():
    from src.iterate.ratchet import QualityRatchet
    ratchet = QualityRatchet(initial_threshold=7.0)
    # 7.4 < 7.0 + 0.5
    result = ratchet.update(recent_scores=[7.4] * 10)
    assert result.get("would_trigger") is False


def test_ratchet_fewer_than_trigger_window_never_meets_condition():
    from src.iterate.ratchet import QualityRatchet
    ratchet = QualityRatchet(initial_threshold=7.0)
    result = ratchet.update(recent_scores=[9.0] * 5)
    assert result.get("would_trigger") is False


# --- Diagnosis (QualityFailureHandler) ---


def test_diagnosis_classifies_persistent_weakness():
    from src.iterate.diagnosis import QualityFailureHandler
    from src.models.evaluation import EvaluationResult, DimensionScore, ConfidenceLevel
    evals = [
        _eval_with_weakest("cta", 5.0),
        _eval_with_weakest("cta", 5.2),
        _eval_with_weakest("cta", 5.1),
    ]
    handler = QualityFailureHandler()
    diagnosis = handler.classify(evals, attempt_number=4)
    assert diagnosis.pattern == FailurePattern.PERSISTENT_WEAKNESS


def test_diagnosis_classifies_oscillation():
    from src.iterate.diagnosis import QualityFailureHandler
    evals = [
        _eval_with_weakest("cta", 5.0),
        _eval_with_weakest("emotional_resonance", 5.0),
        _eval_with_weakest("cta", 5.0),
    ]
    handler = QualityFailureHandler()
    diagnosis = handler.classify(evals, attempt_number=4, oscillation_detected=True)
    assert diagnosis.pattern == FailurePattern.OSCILLATION


def _eval_with_weakest(dimension: str, score: float) -> EvaluationResult:
    dims = [
        DimensionScore(dimension="clarity", score=7.0, rationale="", self_confidence=0.8),
        DimensionScore(dimension="value_proposition", score=7.0, rationale="", self_confidence=0.8),
        DimensionScore(dimension="cta", score=7.0, rationale="", self_confidence=0.8),
        DimensionScore(dimension="brand_voice", score=7.0, rationale="", self_confidence=0.8),
        DimensionScore(dimension="emotional_resonance", score=7.0, rationale="", self_confidence=0.8),
    ]
    for i, d in enumerate(dims):
        if d.dimension == dimension:
            dims[i] = DimensionScore(dimension=dimension, score=score, rationale="", self_confidence=0.8)
            break
    return EvaluationResult(
        ad_id="ad-1",
        attempt_number=1,
        weighted_score=6.0,
        knockout_passed=False,
        knockout_failures=[],
        dimension_scores=dims,
        requires_human_review=False,
        flags=[],
        confidence=0.8,
        confidence_level=ConfidenceLevel.MEDIUM,
    )
