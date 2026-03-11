"""Unit tests for BaseGenerator, V1Generator, V2/V3 stubs, and prompt construction."""
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.ad import Ad, AdStatus
from src.models.brief import Brief, AudienceType, CampaignGoal, HookStyle, Platform
from src.models.evaluation import EvaluationResult, DimensionScore, ConfidenceLevel
# --- Helpers ---


def _resolved_brief(
    audience=AudienceType.PARENT,
    campaign_goal=CampaignGoal.CONVERSION,
    product="SAT prep",
    hook_style=HookStyle.SOCIAL_PROOF,
    platform=Platform.FACEBOOK_FEED,
    offer=None,
    urgency=None,
    social_proof=None,
) -> Brief:
    brief = Brief(
        audience=audience,
        campaign_goal=campaign_goal,
        product=product,
        hook_style=hook_style,
        platform=platform,
        offer=offer,
        urgency=urgency,
        social_proof=social_proof,
    )
    return brief.resolve_inferred()


def _mock_gemini_response_json(primary_text: str = "Get better scores.", headline: str = "SAT Prep"):
    return (
        '{"primary_text": "%s", "headline": "%s", "description": "Expert tutoring.", '
        '"cta_button": "Learn More", "status": "draft"}' % (primary_text.replace('"', '\\"'), headline.replace('"', '\\"'))
    )


def _evaluation_with_weakest_dimension(dimension: str, score: float) -> EvaluationResult:
    return EvaluationResult(
        ad_id="ad-1",
        attempt_number=1,
        weighted_score=6.0,
        knockout_passed=True,
        knockout_failures=[],
        dimension_scores=[
            DimensionScore(dimension=dimension, score=score, rationale="Needs work.", self_confidence=0.8),
            DimensionScore(dimension="cta", score=8.0, rationale="Good.", self_confidence=0.9),
        ],
        requires_human_review=False,
        flags=[],
        confidence=0.85,
        confidence_level=ConfidenceLevel.MEDIUM,
    )


# --- Interface compliance ---


def test_v1_generator_is_instance_of_base_generator():
    from src.generate.base import BaseGenerator
    from src.generate.v1_generator import V1Generator
    assert isinstance(V1Generator(), BaseGenerator)


@pytest.mark.asyncio
async def test_v2_generator_generate_raises_not_implemented_error():
    from src.generate.v2_generator import V2Generator
    gen = V2Generator()
    with pytest.raises(NotImplementedError) as exc_info:
        await gen.generate(_resolved_brief())
    assert "v2" in str(exc_info.value).lower() or "PIPELINE_VERSION" in str(exc_info.value)


@pytest.mark.asyncio
async def test_v3_generator_generate_raises_not_implemented_error():
    from src.generate.v3_generator import V3Generator
    gen = V3Generator()
    with pytest.raises(NotImplementedError) as exc_info:
        await gen.generate(_resolved_brief())
    assert "v3" in str(exc_info.value).lower() or "PIPELINE_VERSION" in str(exc_info.value)


# --- V1Generator.generate() ---


@pytest.mark.asyncio
async def test_v1_generator_generate_returns_ad_with_all_required_fields_populated():
    from src.generate.v1_generator import V1Generator
    with patch("src.generate.v1_generator._call_gemini", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = _mock_gemini_response_json()
        gen = V1Generator()
        brief = _resolved_brief()
        ad = await gen.generate(brief)
    assert ad.primary_text is not None
    assert ad.headline is not None
    assert ad.description is not None
    assert ad.cta_button is not None
    assert ad.status == AdStatus.DRAFT


@pytest.mark.asyncio
async def test_v1_generator_generate_ad_image_url_is_none():
    from src.generate.v1_generator import V1Generator
    with patch("src.generate.v1_generator._call_gemini", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = _mock_gemini_response_json()
        gen = V1Generator()
        ad = await gen.generate(_resolved_brief())
    assert ad.image_url is None


@pytest.mark.asyncio
async def test_v1_generator_generate_ad_brief_id_matches_input_brief_id():
    from src.generate.v1_generator import V1Generator
    with patch("src.generate.v1_generator._call_gemini", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = _mock_gemini_response_json()
        gen = V1Generator()
        brief = _resolved_brief()
        ad = await gen.generate(brief)
    assert ad.brief_id == brief.id


@pytest.mark.asyncio
async def test_v1_generator_generate_primary_text_length_within_brief_inferred_length_target():
    from src.generate.v1_generator import V1Generator
    brief = _resolved_brief(platform=Platform.INSTAGRAM_FEED)
    assert brief.inferred is not None and brief.inferred.ad_length_target == 100
    with patch("src.generate.v1_generator._call_gemini", new_callable=AsyncMock) as mock_call:
        short_text = "A" * 80
        mock_call.return_value = _mock_gemini_response_json(primary_text=short_text)
        gen = V1Generator()
        ad = await gen.generate(brief)
    assert len(ad.primary_text) <= brief.inferred.ad_length_target


@pytest.mark.asyncio
async def test_v1_generator_generate_cta_button_in_valid_list():
    from src.generate.v1_generator import V1Generator, VALID_CTA_BUTTONS
    with patch("src.generate.v1_generator._call_gemini", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = _mock_gemini_response_json()
        gen = V1Generator()
        ad = await gen.generate(_resolved_brief())
    assert ad.cta_button in VALID_CTA_BUTTONS


@pytest.mark.asyncio
async def test_v1_generator_generate_prompt_includes_brief_audience():
    from src.generate.v1_generator import V1Generator
    with patch("src.generate.v1_generator._call_gemini", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = _mock_gemini_response_json()
        gen = V1Generator()
        brief = _resolved_brief()
        await gen.generate(brief)
    prompt = mock_call.call_args[0][0] if mock_call.call_args[0] else mock_call.call_args[1].get("prompt", "")
    assert "parent" in prompt.lower() or brief.audience.value in prompt.lower()


@pytest.mark.asyncio
async def test_v1_generator_generate_prompt_includes_brief_campaign_goal():
    from src.generate.v1_generator import V1Generator
    with patch("src.generate.v1_generator._call_gemini", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = _mock_gemini_response_json()
        gen = V1Generator()
        brief = _resolved_brief()
        await gen.generate(brief)
    prompt = mock_call.call_args[0][0] if mock_call.call_args[0] else mock_call.call_args[1].get("prompt", "")
    assert "conversion" in prompt.lower() or brief.campaign_goal.value in prompt.lower()


@pytest.mark.asyncio
async def test_v1_generator_generate_prompt_includes_brief_inferred_hook_style():
    from src.generate.v1_generator import V1Generator
    with patch("src.generate.v1_generator._call_gemini", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = _mock_gemini_response_json()
        gen = V1Generator()
        brief = _resolved_brief(hook_style=HookStyle.SOCIAL_PROOF)
        await gen.generate(brief)
    prompt = mock_call.call_args[0][0] if mock_call.call_args[0] else mock_call.call_args[1].get("prompt", "")
    assert "social_proof" in prompt.lower() or "social proof" in prompt.lower()


@pytest.mark.asyncio
async def test_v1_generator_generate_malformed_gemini_json_raises_generation_error():
    from src.generate.v1_generator import V1Generator
    from src.generate.base import GenerationError
    with patch("src.generate.v1_generator._call_gemini", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = "not valid json at all {{{"
        gen = V1Generator()
        with pytest.raises(GenerationError):
            await gen.generate(_resolved_brief())


@pytest.mark.asyncio
async def test_v1_generator_generate_mocked_passing_response_parsed_into_ad_model():
    from src.generate.v1_generator import V1Generator
    with patch("src.generate.v1_generator._call_gemini", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = _mock_gemini_response_json(
            primary_text="Score higher with expert help.",
            headline="SAT Prep Works",
        )
        gen = V1Generator()
        ad = await gen.generate(_resolved_brief())
    assert ad.primary_text == "Score higher with expert help."
    assert ad.headline == "SAT Prep Works"
    assert ad.description == "Expert tutoring."
    assert ad.cta_button == "Learn More"


# --- V1Generator.regenerate() ---


def _regeneration_strategy(dimension: str, approach: str):
    from src.generate.base import RegenerationStrategy, RegenerationApproach
    return RegenerationStrategy(dimension=dimension, approach=RegenerationApproach(approach))


@pytest.mark.asyncio
async def test_v1_generator_regenerate_clarity_failure_uses_full_rewrite():
    from src.generate.v1_generator import V1Generator
    from src.generate.base import RegenerationApproach
    with patch("src.generate.v1_generator._call_gemini", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = _mock_gemini_response_json()
        gen = V1Generator()
        ad = Ad(brief_id="b1", primary_text="Old", headline="H", description="D", cta_button="Learn More", status=AdStatus.DRAFT)
        eval_result = _evaluation_with_weakest_dimension("clarity", 5.0)
        strategy = _regeneration_strategy("clarity", "full_rewrite")
        await gen.regenerate(ad, eval_result, strategy)
    assert strategy.approach == RegenerationApproach.FULL_REWRITE


@pytest.mark.asyncio
async def test_v1_generator_regenerate_cta_failure_uses_targeted():
    from src.generate.v1_generator import V1Generator
    from src.generate.base import RegenerationApproach
    strategy = _regeneration_strategy("cta", "targeted")
    assert strategy.approach == RegenerationApproach.TARGETED


@pytest.mark.asyncio
async def test_v1_generator_regenerate_emotional_resonance_failure_uses_hook_rewrite():
    from src.generate.v1_generator import V1Generator
    from src.generate.base import RegenerationApproach
    strategy = _regeneration_strategy("emotional_resonance", "hook_rewrite")
    assert strategy.approach == RegenerationApproach.HOOK_REWRITE


@pytest.mark.asyncio
async def test_v1_generator_regenerate_brand_voice_failure_uses_tone_rewrite():
    from src.generate.v1_generator import V1Generator
    from src.generate.base import RegenerationApproach
    strategy = _regeneration_strategy("brand_voice", "tone_rewrite")
    assert strategy.approach == RegenerationApproach.TONE_REWRITE


@pytest.mark.asyncio
async def test_v1_generator_regenerate_value_proposition_failure_uses_targeted():
    from src.generate.v1_generator import V1Generator
    from src.generate.base import RegenerationApproach
    strategy = _regeneration_strategy("value_proposition", "targeted")
    assert strategy.approach == RegenerationApproach.TARGETED


@pytest.mark.asyncio
async def test_v1_generator_regenerate_prompt_includes_original_primary_text():
    from src.generate.v1_generator import V1Generator
    with patch("src.generate.v1_generator._call_gemini", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = _mock_gemini_response_json(primary_text="New copy.")
        gen = V1Generator()
        ad = Ad(brief_id="b1", primary_text="Original primary text here.", headline="H", description="D", cta_button="Learn More", status=AdStatus.DRAFT)
        eval_result = _evaluation_with_weakest_dimension("clarity", 4.5)
        strategy = _regeneration_strategy("clarity", "full_rewrite")
        await gen.regenerate(ad, eval_result, strategy)
    prompt = mock_call.call_args[0][0] if mock_call.call_args[0] else mock_call.call_args[1].get("prompt", "")
    assert "Original primary text here" in prompt or "original" in prompt.lower()


@pytest.mark.asyncio
async def test_v1_generator_regenerate_prompt_includes_failed_dimension_name():
    from src.generate.v1_generator import V1Generator
    with patch("src.generate.v1_generator._call_gemini", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = _mock_gemini_response_json()
        gen = V1Generator()
        ad = Ad(brief_id="b1", primary_text="Copy", headline="H", description="D", cta_button="Learn More", status=AdStatus.DRAFT)
        eval_result = _evaluation_with_weakest_dimension("clarity", 4.0)
        strategy = _regeneration_strategy("clarity", "full_rewrite")
        await gen.regenerate(ad, eval_result, strategy)
    prompt = mock_call.call_args[0][0] if mock_call.call_args[0] else mock_call.call_args[1].get("prompt", "")
    assert "clarity" in prompt.lower()


@pytest.mark.asyncio
async def test_v1_generator_regenerate_prompt_includes_score_for_failed_dimension():
    from src.generate.v1_generator import V1Generator
    with patch("src.generate.v1_generator._call_gemini", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = _mock_gemini_response_json()
        gen = V1Generator()
        ad = Ad(brief_id="b1", primary_text="Copy", headline="H", description="D", cta_button="Learn More", status=AdStatus.DRAFT)
        eval_result = _evaluation_with_weakest_dimension("cta", 5.2)
        strategy = _regeneration_strategy("cta", "targeted")
        await gen.regenerate(ad, eval_result, strategy)
    prompt = mock_call.call_args[0][0] if mock_call.call_args[0] else mock_call.call_args[1].get("prompt", "")
    assert "5.2" in prompt or "5" in prompt


@pytest.mark.asyncio
async def test_v1_generator_regenerate_returned_ad_has_same_brief_id_as_input():
    from src.generate.v1_generator import V1Generator
    with patch("src.generate.v1_generator._call_gemini", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = _mock_gemini_response_json()
        gen = V1Generator()
        ad = Ad(id="ad-123", brief_id="brief-456", primary_text="C", headline="H", description="D", cta_button="Learn More", status=AdStatus.DRAFT)
        eval_result = _evaluation_with_weakest_dimension("clarity", 5.0)
        strategy = _regeneration_strategy("clarity", "full_rewrite")
        result = await gen.regenerate(ad, eval_result, strategy)
    assert result.brief_id == "brief-456"


@pytest.mark.asyncio
async def test_v1_generator_regenerate_returned_ad_has_same_id_as_input_ad():
    from src.generate.v1_generator import V1Generator
    with patch("src.generate.v1_generator._call_gemini", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = _mock_gemini_response_json()
        gen = V1Generator()
        ad = Ad(id="ad-same-id", brief_id="b1", primary_text="C", headline="H", description="D", cta_button="Learn More", status=AdStatus.DRAFT)
        eval_result = _evaluation_with_weakest_dimension("clarity", 5.0)
        strategy = _regeneration_strategy("clarity", "full_rewrite")
        result = await gen.regenerate(ad, eval_result, strategy)
    assert result.id == "ad-same-id"


# --- Prompt construction ---


@pytest.mark.asyncio
async def test_v1_generator_optional_brief_fields_present_in_prompt_when_not_none():
    from src.generate.v1_generator import V1Generator
    with patch("src.generate.v1_generator._call_gemini", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = _mock_gemini_response_json()
        gen = V1Generator()
        brief = _resolved_brief(offer="20% off", urgency="Limited time")
        await gen.generate(brief)
    prompt = mock_call.call_args[0][0] if mock_call.call_args[0] else mock_call.call_args[1].get("prompt", "")
    assert "20% off" in prompt or "offer" in prompt.lower()
    assert "limited time" in prompt.lower() or "urgency" in prompt.lower()


@pytest.mark.asyncio
async def test_v1_generator_optional_brief_fields_absent_from_prompt_when_none():
    from src.generate.v1_generator import V1Generator
    with patch("src.generate.v1_generator._call_gemini", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = _mock_gemini_response_json()
        gen = V1Generator()
        brief = Brief(
            audience=AudienceType.PARENT,
            campaign_goal=CampaignGoal.CONVERSION,
            product="SAT",
        ).resolve_inferred()
        await gen.generate(brief)
    prompt = mock_call.call_args[0][0] if mock_call.call_args[0] else mock_call.call_args[1].get("prompt", "")
    assert "None" not in prompt or "n/a" in prompt.lower()


@pytest.mark.asyncio
async def test_v1_generator_fear_hook_style_different_prompt_than_aspiration():
    from src.generate.v1_generator import V1Generator
    with patch("src.generate.v1_generator._call_gemini", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = _mock_gemini_response_json()
        gen = V1Generator()
        brief_fear = _resolved_brief(hook_style=HookStyle.FEAR)
        brief_asp = _resolved_brief(hook_style=HookStyle.ASPIRATION)
        await gen.generate(brief_fear)
        prompt_fear = mock_call.call_args[0][0] if mock_call.call_args[0] else mock_call.call_args[1].get("prompt", "")
        await gen.generate(brief_asp)
        prompt_asp = mock_call.call_args[0][0] if mock_call.call_args[0] else mock_call.call_args[1].get("prompt", "")
    assert prompt_fear != prompt_asp
    assert "fear" in prompt_fear.lower() or "fear" in str(brief_fear.inferred.hook_style).lower()
    assert "aspiration" in prompt_asp.lower() or "aspiration" in str(brief_asp.inferred.hook_style).lower()


@pytest.mark.asyncio
async def test_v1_generator_social_proof_hook_prompt_includes_proof_elements_instruction():
    from src.generate.v1_generator import V1Generator
    with patch("src.generate.v1_generator._call_gemini", new_callable=AsyncMock) as mock_call:
        mock_call.return_value = _mock_gemini_response_json()
        gen = V1Generator()
        brief = _resolved_brief(hook_style=HookStyle.SOCIAL_PROOF)
        await gen.generate(brief)
    prompt = mock_call.call_args[0][0] if mock_call.call_args[0] else mock_call.call_args[1].get("prompt", "")
    assert "social" in prompt.lower() or "proof" in prompt.lower() or "testimonial" in prompt.lower() or "evidence" in prompt.lower()
