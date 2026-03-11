"""Unit tests for Brief validation, resolve_inferred(), and CostCalculator."""
import pytest
from pydantic import ValidationError

from src.models.brief import Brief, AudienceType, CampaignGoal, HookStyle, Platform
from src.models.metrics import CostCalculator


# --- Brief required field validation ---


def test_brief_with_audience_campaign_goal_product_valid():
    Brief(audience=AudienceType.PARENT, campaign_goal=CampaignGoal.CONVERSION, product="SAT prep")


def test_brief_missing_audience_fails_validation():
    with pytest.raises(ValidationError):
        Brief(campaign_goal=CampaignGoal.CONVERSION, product="SAT prep")


def test_brief_missing_campaign_goal_fails_validation():
    with pytest.raises(ValidationError):
        Brief(audience=AudienceType.PARENT, product="SAT prep")


def test_brief_missing_product_fails_validation():
    with pytest.raises(ValidationError):
        Brief(audience=AudienceType.PARENT, campaign_goal=CampaignGoal.CONVERSION)


def test_brief_invalid_audience_fails_validation():
    with pytest.raises(ValidationError):
        Brief(audience="invalid", campaign_goal="conversion", product="SAT prep")


def test_brief_invalid_campaign_goal_fails_validation():
    with pytest.raises(ValidationError):
        Brief(audience="parent", campaign_goal="invalid", product="SAT prep")


def test_brief_valid_audiences_parent_and_student():
    Brief(audience=AudienceType.PARENT, campaign_goal=CampaignGoal.CONVERSION, product="SAT")
    Brief(audience=AudienceType.STUDENT, campaign_goal=CampaignGoal.CONVERSION, product="SAT")


def test_brief_valid_campaign_goals_awareness_conversion_retargeting():
    Brief(audience=AudienceType.PARENT, campaign_goal=CampaignGoal.AWARENESS, product="SAT")
    Brief(audience=AudienceType.PARENT, campaign_goal=CampaignGoal.CONVERSION, product="SAT")
    Brief(audience=AudienceType.PARENT, campaign_goal=CampaignGoal.RETARGETING, product="SAT")


# --- Brief.resolve_inferred() ---


def test_resolve_inferred_parent_conversion_sets_profile_id():
    brief = Brief(
        audience=AudienceType.PARENT,
        campaign_goal=CampaignGoal.CONVERSION,
        product="SAT prep",
    )
    brief.resolve_inferred()
    assert brief.inferred is not None
    assert brief.inferred.profile_id == "vt_sat_parent_conversion"


def test_resolve_inferred_student_awareness_sets_profile_id():
    brief = Brief(
        audience=AudienceType.STUDENT,
        campaign_goal=CampaignGoal.AWARENESS,
        product="SAT prep",
    )
    brief.resolve_inferred()
    assert brief.inferred is not None
    assert brief.inferred.profile_id == "vt_sat_student_awareness"


def test_resolve_inferred_parent_awareness_infers_hook_style_fear():
    brief = Brief(
        audience=AudienceType.PARENT,
        campaign_goal=CampaignGoal.AWARENESS,
        product="SAT prep",
    )
    brief.resolve_inferred()
    assert brief.inferred.hook_style == HookStyle.FEAR


def test_resolve_inferred_parent_conversion_infers_hook_style_social_proof():
    brief = Brief(
        audience=AudienceType.PARENT,
        campaign_goal=CampaignGoal.CONVERSION,
        product="SAT prep",
    )
    brief.resolve_inferred()
    assert brief.inferred.hook_style == HookStyle.SOCIAL_PROOF


def test_resolve_inferred_student_awareness_infers_hook_style_question():
    brief = Brief(
        audience=AudienceType.STUDENT,
        campaign_goal=CampaignGoal.AWARENESS,
        product="SAT prep",
    )
    brief.resolve_inferred()
    assert brief.inferred.hook_style == HookStyle.QUESTION


def test_resolve_inferred_student_conversion_infers_hook_style_stat():
    brief = Brief(
        audience=AudienceType.STUDENT,
        campaign_goal=CampaignGoal.CONVERSION,
        product="SAT prep",
    )
    brief.resolve_inferred()
    assert brief.inferred.hook_style == HookStyle.STAT


def test_resolve_inferred_platform_facebook_feed_sets_ad_length_target_125():
    brief = Brief(
        audience=AudienceType.PARENT,
        campaign_goal=CampaignGoal.CONVERSION,
        product="SAT",
        platform=Platform.FACEBOOK_FEED,
    )
    brief.resolve_inferred()
    assert brief.inferred.ad_length_target == 125


def test_resolve_inferred_platform_instagram_story_sets_ad_length_target_75():
    brief = Brief(
        audience=AudienceType.PARENT,
        campaign_goal=CampaignGoal.CONVERSION,
        product="SAT",
        platform=Platform.INSTAGRAM_STORY,
    )
    brief.resolve_inferred()
    assert brief.inferred.ad_length_target == 75


def test_resolve_inferred_platform_instagram_feed_sets_ad_length_target_100():
    brief = Brief(
        audience=AudienceType.PARENT,
        campaign_goal=CampaignGoal.CONVERSION,
        product="SAT",
        platform=Platform.INSTAGRAM_FEED,
    )
    brief.resolve_inferred()
    assert brief.inferred.ad_length_target == 100


def test_resolve_inferred_returns_self_chainable():
    brief = Brief(
        audience=AudienceType.PARENT,
        campaign_goal=CampaignGoal.CONVERSION,
        product="SAT",
    )
    result = brief.resolve_inferred()
    assert result is brief


def test_resolve_inferred_called_twice_does_not_change_result():
    brief = Brief(
        audience=AudienceType.PARENT,
        campaign_goal=CampaignGoal.CONVERSION,
        product="SAT",
    )
    brief.resolve_inferred()
    first_profile_id = brief.inferred.profile_id
    brief.resolve_inferred()
    assert brief.inferred.profile_id == first_profile_id


# --- CostCalculator ---

# Claude Sonnet 4.6: $3/1M input, $15/1M output (per Anthropic)
# Gemini 1.5 Flash: $0.075/1M input, $0.30/1M output (per Google)


def test_cost_calculator_claude_sonnet_input_matches_anthropic_rate():
    cost = CostCalculator.calculate(provider="anthropic", model="claude-sonnet-4-6", input_tokens=1_000_000, output_tokens=0)
    assert abs(cost - 3.0) < 0.01


def test_cost_calculator_claude_sonnet_output_matches_anthropic_rate():
    cost = CostCalculator.calculate(provider="anthropic", model="claude-sonnet-4-6", input_tokens=0, output_tokens=1_000_000)
    assert abs(cost - 15.0) < 0.01


def test_cost_calculator_gemini_flash_input_matches_google_rate():
    cost = CostCalculator.calculate(provider="google", model="gemini-1.5-flash", input_tokens=1_000_000, output_tokens=0)
    assert abs(cost - 0.075) < 0.001


def test_cost_calculator_gemini_flash_output_matches_google_rate():
    cost = CostCalculator.calculate(provider="google", model="gemini-1.5-flash", input_tokens=0, output_tokens=1_000_000)
    assert abs(cost - 0.30) < 0.001


def test_cost_calculator_unknown_model_raises_value_error():
    with pytest.raises(ValueError):
        CostCalculator.calculate(provider="unknown", model="unknown-model", input_tokens=100, output_tokens=50)


def test_cost_calculator_total_cost_is_input_plus_output():
    in_cost = CostCalculator.calculate(provider="anthropic", model="claude-sonnet-4-6", input_tokens=1000, output_tokens=0)
    out_cost = CostCalculator.calculate(provider="anthropic", model="claude-sonnet-4-6", input_tokens=0, output_tokens=500)
    total = CostCalculator.calculate(provider="anthropic", model="claude-sonnet-4-6", input_tokens=1000, output_tokens=500)
    assert abs(total - (in_cost + out_cost)) < 0.0001
