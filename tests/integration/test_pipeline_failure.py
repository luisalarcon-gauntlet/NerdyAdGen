"""Integration: full pipeline with mocked failing evaluation -> abandoned after max_attempts."""
from unittest.mock import AsyncMock, patch

import pytest

from src.models.ad import Ad, AdStatus
from src.models.brief import Brief, AudienceType, CampaignGoal, HookStyle, Platform
from src.models.evaluation import EvaluationResult, DimensionScore, ConfidenceLevel
from src.models.weights import VarsityTutorsSATProfiles


def _resolved_brief(bid: str = "brief-fail-1"):
    b = Brief(
        id=bid,
        audience=AudienceType.PARENT,
        campaign_goal=CampaignGoal.CONVERSION,
        product="SAT prep",
        hook_style=HookStyle.SOCIAL_PROOF,
        platform=Platform.FACEBOOK_FEED,
    )
    return b.resolve_inferred()


def _failing_evaluation(ad_id: str, attempt_number: int):
    return EvaluationResult(
        ad_id=ad_id,
        attempt_number=attempt_number,
        weighted_score=5.0,
        knockout_passed=False,
        knockout_failures=["clarity"],
        dimension_scores=[
            DimensionScore(dimension="clarity", score=5.0, rationale="Weak", self_confidence=0.7),
            DimensionScore(dimension="value_proposition", score=7.0, rationale="OK", self_confidence=0.8),
            DimensionScore(dimension="cta", score=7.0, rationale="OK", self_confidence=0.8),
            DimensionScore(dimension="brand_voice", score=7.0, rationale="OK", self_confidence=0.8),
            DimensionScore(dimension="emotional_resonance", score=7.0, rationale="OK", self_confidence=0.8),
        ],
        requires_human_review=False,
        flags=[],
        confidence=0.7,
        confidence_level=ConfidenceLevel.LOW,
    )


@pytest.mark.asyncio
async def test_full_pipeline_mocked_failing_evaluation_produces_abandoned_after_max_attempts(
    run_migrations, test_db_url
):
    """Full pipeline with mocked failing evaluation produces abandoned ad after max_iteration_attempts."""
    from src.config.settings import get_settings
    from sqlalchemy.ext.asyncio import create_async_engine
    from src.output.library import AdLibrary
    from src.iterate.run_single import run_single_brief_loop
    from src.generate.v1_generator import V1Generator
    from src.evaluate.judge import Judge

    engine = create_async_engine(test_db_url)
    library = AdLibrary(engine)
    brief = _resolved_brief()
    await library.save_brief(brief)
    settings = get_settings()
    max_attempts = settings.max_iteration_attempts

    with patch("src.generate.v1_generator._call_gemini", new_callable=AsyncMock) as mock_gemini:
        mock_gemini.return_value = (
            '{"primary_text": "Copy.", "headline": "Head", '
            '"description": "Desc.", "cta_button": "Learn More", "status": "draft"}'
        )
        judge = Judge()
        with patch.object(judge, "evaluate", new_callable=AsyncMock) as mock_eval:
            async def _eval_async(ad, profile, attempt_number=1):
                return _failing_evaluation(ad.id, attempt_number)
            mock_eval.side_effect = _eval_async
            generator = V1Generator()
            profile = VarsityTutorsSATProfiles.PARENT_CONVERSION
            ad, status = await run_single_brief_loop(
                brief, "run-fail-1", library, generator, judge, profile
            )
    assert status == "abandoned"
    assert ad.status == AdStatus.ABANDONED
    assert ad.final_score == 5.0

    got = await library.get_ad(ad.id)
    assert got is not None
    assert got.status == AdStatus.ABANDONED

    patterns = await library.get_failure_patterns()
    assert patterns
    assert mock_eval.await_count == max_attempts
