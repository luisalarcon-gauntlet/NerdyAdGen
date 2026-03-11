"""Unit tests for DimensionWeights, KnockoutThresholds, WeightProfile, ProfileRegistry, VarsityTutorsSATProfiles."""
import pytest
from pydantic import ValidationError

from src.models.weights import (
    DimensionWeights,
    KnockoutThresholds,
    WeightProfile,
    ProfileRegistry,
    VarsityTutorsSATProfiles,
    apply_knockouts,
)


# --- DimensionWeights validation ---


def test_weights_summing_to_one_point_zero_is_valid():
    DimensionWeights(
        clarity=0.20,
        value_proposition=0.30,
        cta=0.25,
        brand_voice=0.15,
        emotional_resonance=0.10,
    )


def test_weights_summing_to_point_nine_nine_fails_validation():
    with pytest.raises(ValidationError):
        DimensionWeights(
            clarity=0.20,
            value_proposition=0.30,
            cta=0.24,
            brand_voice=0.15,
            emotional_resonance=0.10,
        )


def test_weights_summing_to_one_point_zero_one_fails_validation():
    with pytest.raises(ValidationError):
        DimensionWeights(
            clarity=0.21,
            value_proposition=0.30,
            cta=0.25,
            brand_voice=0.15,
            emotional_resonance=0.10,
        )


def test_weights_with_negative_value_fails_validation():
    with pytest.raises(ValidationError):
        DimensionWeights(
            clarity=-0.10,
            value_proposition=0.40,
            cta=0.25,
            brand_voice=0.25,
            emotional_resonance=0.20,
        )


def test_weights_single_weight_zero_is_valid():
    DimensionWeights(
        clarity=0.25,
        value_proposition=0.25,
        cta=0.25,
        brand_voice=0.25,
        emotional_resonance=0.0,
    )


# --- KnockoutThresholds enforcement ---


def test_knockout_all_scores_above_thresholds_passed_true():
    thresholds = KnockoutThresholds(clarity=5.0, cta=6.0, brand_voice=5.0)
    scores = {"clarity": 6.0, "cta": 7.0, "brand_voice": 6.0}
    result = apply_knockouts(scores, thresholds)
    assert result.knockout_passed is True
    assert result.knockout_failures == []


def test_knockout_clarity_below_threshold_fails():
    thresholds = KnockoutThresholds(clarity=5.0, cta=6.0, brand_voice=5.0)
    scores = {"clarity": 4.9, "cta": 7.0, "brand_voice": 6.0}
    result = apply_knockouts(scores, thresholds)
    assert result.knockout_passed is False
    assert "clarity" in result.knockout_failures


def test_knockout_clarity_exactly_at_threshold_passed_true():
    thresholds = KnockoutThresholds(clarity=5.0, cta=6.0, brand_voice=5.0)
    scores = {"clarity": 5.0, "cta": 7.0, "brand_voice": 6.0}
    result = apply_knockouts(scores, thresholds)
    assert result.knockout_passed is True


def test_knockout_two_dimensions_below_both_in_failures():
    thresholds = KnockoutThresholds(clarity=5.0, cta=6.0, brand_voice=5.0)
    scores = {"clarity": 4.0, "cta": 5.5, "brand_voice": 6.0}
    result = apply_knockouts(scores, thresholds)
    assert result.knockout_passed is False
    assert "clarity" in result.knockout_failures
    assert "cta" in result.knockout_failures


def test_knockout_result_independent_of_weighted_score():
    thresholds = KnockoutThresholds(clarity=5.0)
    scores = {"clarity": 4.9}
    result = apply_knockouts(scores, thresholds)
    assert result.knockout_passed is False
    assert hasattr(result, "knockout_failures")


def test_knockout_thresholds_all_none_all_pass():
    thresholds = KnockoutThresholds(
        clarity=None, cta=None, brand_voice=None, value_proposition=None, emotional_resonance=None
    )
    scores = {"clarity": 1.0, "cta": 1.0, "brand_voice": 1.0}
    result = apply_knockouts(scores, thresholds)
    assert result.knockout_passed is True
    assert result.knockout_failures == []


# --- WeightProfile ---


def test_weight_profile_weights_not_summing_to_one_fails_validation():
    with pytest.raises(ValidationError):
        WeightProfile(
            profile_id="bad",
            audience="parent",
            campaign_goal="conversion",
            weights=DimensionWeights(
                clarity=0.20,
                value_proposition=0.30,
                cta=0.20,
                brand_voice=0.15,
                emotional_resonance=0.10,
            ),
        )


def test_weight_profile_without_quality_threshold_defaults_to_seven():
    profile = WeightProfile(
        profile_id="test",
        audience="parent",
        campaign_goal="conversion",
        weights=DimensionWeights(
            clarity=0.20,
            value_proposition=0.30,
            cta=0.25,
            brand_voice=0.15,
            emotional_resonance=0.10,
        ),
    )
    assert profile.quality_threshold == 7.0


def test_weight_profile_quality_threshold_stored_correctly():
    profile = WeightProfile(
        profile_id="test",
        audience="parent",
        campaign_goal="conversion",
        quality_threshold=7.5,
        weights=DimensionWeights(
            clarity=0.20,
            value_proposition=0.30,
            cta=0.25,
            brand_voice=0.15,
            emotional_resonance=0.10,
        ),
    )
    assert profile.quality_threshold == 7.5


# --- ProfileRegistry ---


def test_profile_registry_register_then_resolve_by_profile_id():
    registry = ProfileRegistry()
    profile = WeightProfile(
        profile_id="my_profile",
        audience="parent",
        campaign_goal="conversion",
        weights=DimensionWeights(
            clarity=0.20, value_proposition=0.30, cta=0.25, brand_voice=0.15, emotional_resonance=0.10
        ),
    )
    registry.register(profile)
    assert registry.resolve(profile_id="my_profile") is profile


def test_profile_registry_exact_audience_goal_match_returns_profile():
    registry = ProfileRegistry()
    profile = WeightProfile(
        profile_id="vt_sat_parent_conversion",
        audience="parent",
        campaign_goal="conversion",
        weights=DimensionWeights(
            clarity=0.20, value_proposition=0.30, cta=0.25, brand_voice=0.15, emotional_resonance=0.10
        ),
    )
    registry.register(profile)
    assert registry.resolve(audience="parent", campaign_goal="conversion") is profile


def test_profile_registry_unknown_audience_known_goal_returns_base_goal_profile():
    registry = ProfileRegistry()
    base_conversion = WeightProfile(
        profile_id="base_conversion",
        audience="parent",
        campaign_goal="conversion",
        weights=DimensionWeights(
            clarity=0.20, value_proposition=0.30, cta=0.25, brand_voice=0.15, emotional_resonance=0.10
        ),
    )
    registry.register(base_conversion)
    result = registry.resolve(audience="unknown_audience", campaign_goal="conversion")
    assert result is base_conversion


def test_profile_registry_unknown_audience_unknown_goal_returns_base_equal():
    registry = ProfileRegistry()
    equal_weights = DimensionWeights(
        clarity=0.20, value_proposition=0.20, cta=0.20, brand_voice=0.20, emotional_resonance=0.20
    )
    registry.register_base_equal(equal_weights)
    result = registry.resolve(audience="unknown", campaign_goal="unknown")
    assert result.weights.clarity == 0.20
    assert result.weights.value_proposition == 0.20


def test_profile_registry_duplicate_profile_id_overwrites():
    registry = ProfileRegistry()
    p1 = WeightProfile(
        profile_id="dup",
        audience="parent",
        campaign_goal="conversion",
        weights=DimensionWeights(
            clarity=0.20, value_proposition=0.30, cta=0.25, brand_voice=0.15, emotional_resonance=0.10
        ),
    )
    p2 = WeightProfile(
        profile_id="dup",
        audience="student",
        campaign_goal="awareness",
        quality_threshold=6.0,
        weights=DimensionWeights(
            clarity=0.20, value_proposition=0.20, cta=0.25, brand_voice=0.15, emotional_resonance=0.20
        ),
    )
    registry.register(p1)
    registry.register(p2)
    assert registry.resolve(profile_id="dup").audience == "student"


def test_profile_registry_resolution_case_sensitive():
    registry = ProfileRegistry()
    profile = WeightProfile(
        profile_id="lower",
        audience="parent",
        campaign_goal="conversion",
        weights=DimensionWeights(
            clarity=0.20, value_proposition=0.30, cta=0.25, brand_voice=0.15, emotional_resonance=0.10
        ),
    )
    base_conversion = WeightProfile(
        profile_id="base_conv",
        audience="parent",
        campaign_goal="conversion",
        weights=DimensionWeights(
            clarity=0.20, value_proposition=0.30, cta=0.25, brand_voice=0.15, emotional_resonance=0.10
        ),
    )
    registry.register(profile)
    registry.register_base_goal("conversion", base_conversion)
    result = registry.resolve(audience="Parent", campaign_goal="conversion")
    assert result is base_conversion


# --- VarsityTutorsSATProfiles ---


def test_varsity_parent_conversion_quality_threshold_is_seven_point_five():
    assert VarsityTutorsSATProfiles.PARENT_CONVERSION.quality_threshold == 7.5


def test_varsity_student_conversion_quality_threshold_is_seven_point_five():
    assert VarsityTutorsSATProfiles.STUDENT_CONVERSION.quality_threshold == 7.5


def test_varsity_parent_awareness_quality_threshold_is_seven():
    assert VarsityTutorsSATProfiles.PARENT_AWARENESS.quality_threshold == 7.0


def test_varsity_student_awareness_quality_threshold_is_seven():
    assert VarsityTutorsSATProfiles.STUDENT_AWARENESS.quality_threshold == 7.0


def test_varsity_all_four_profiles_weights_sum_to_one():
    for profile in [
        VarsityTutorsSATProfiles.PARENT_CONVERSION,
        VarsityTutorsSATProfiles.STUDENT_CONVERSION,
        VarsityTutorsSATProfiles.PARENT_AWARENESS,
        VarsityTutorsSATProfiles.STUDENT_AWARENESS,
    ]:
        w = profile.weights
        total = w.clarity + w.value_proposition + w.cta + w.brand_voice + w.emotional_resonance
        assert abs(total - 1.0) < 1e-9


def test_varsity_parent_awareness_brand_voice_knockout_is_five():
    ko = VarsityTutorsSATProfiles.PARENT_AWARENESS.knockout_thresholds
    assert ko.brand_voice == 5.0


def test_varsity_parent_conversion_cta_knockout_is_six():
    ko = VarsityTutorsSATProfiles.PARENT_CONVERSION.knockout_thresholds
    assert ko.cta == 6.0


def test_varsity_student_conversion_cta_knockout_is_six():
    ko = VarsityTutorsSATProfiles.STUDENT_CONVERSION.knockout_thresholds
    assert ko.cta == 6.0
