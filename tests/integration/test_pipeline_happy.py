"""Integration: full pipeline with mocked passing evaluation -> published ad in DB."""
from unittest.mock import AsyncMock, patch

import pytest

from src.models.ad import Ad, AdStatus
from src.models.brief import Brief, AudienceType, CampaignGoal, HookStyle, Platform
from src.models.evaluation import EvaluationResult, DimensionScore, ConfidenceLevel
from src.models.weights import VarsityTutorsSATProfiles


def _resolved_brief(bid: str = "brief-happy-1"):
    b = Brief(
        id=bid,
        audience=AudienceType.PARENT,
        campaign_goal=CampaignGoal.CONVERSION,
        product="SAT prep",
        hook_style=HookStyle.SOCIAL_PROOF,
        platform=Platform.FACEBOOK_FEED,
    )
    return b.resolve_inferred()


def _passing_evaluation(ad_id: str, attempt_number: int = 1):
    return EvaluationResult(
        ad_id=ad_id,
        attempt_number=attempt_number,
        weighted_score=8.0,
        knockout_passed=True,
        knockout_failures=[],
        dimension_scores=[
            DimensionScore(dimension="clarity", score=8.0, rationale="Good", self_confidence=0.9),
            DimensionScore(dimension="value_proposition", score=8.0, rationale="Good", self_confidence=0.9),
            DimensionScore(dimension="cta", score=8.0, rationale="Good", self_confidence=0.9),
            DimensionScore(dimension="brand_voice", score=8.0, rationale="Good", self_confidence=0.9),
            DimensionScore(dimension="emotional_resonance", score=8.0, rationale="Good", self_confidence=0.9),
        ],
        requires_human_review=False,
        flags=[],
        confidence=0.9,
        confidence_level=ConfidenceLevel.HIGH,
    )


@pytest.mark.asyncio
async def test_full_pipeline_mocked_passing_evaluation_produces_published_ad(run_migrations, test_db_url):
    """Full pipeline flow with mocked passing evaluation produces a published ad in DB."""
    from sqlalchemy.ext.asyncio import create_async_engine
    from src.output.library import AdLibrary
    from src.iterate.run_single import run_single_brief_loop
    from src.generate.v1_generator import V1Generator
    from src.evaluate.judge import Judge

    engine = create_async_engine(test_db_url)
    library = AdLibrary(engine)
    brief = _resolved_brief()
    await library.save_brief(brief)

    with patch("src.generate.v1_generator._call_gemini", new_callable=AsyncMock) as mock_gemini:
        mock_gemini.return_value = (
            '{"primary_text": "Get better SAT scores.", "headline": "SAT Prep", '
            '"description": "Expert tutoring.", "cta_button": "Learn More", "status": "draft"}'
        )
        judge = Judge()
        with patch.object(judge, "evaluate", new_callable=AsyncMock) as mock_eval:
            async def _passing(ad, profile, attempt_number=1):
                return _passing_evaluation(ad.id, attempt_number)
            mock_eval.side_effect = _passing
            generator = V1Generator()
            profile = VarsityTutorsSATProfiles.PARENT_CONVERSION
            ad, status = await run_single_brief_loop(
                brief, "run-1", library, generator, judge, profile
            )
    assert status == "published"
    assert ad.status == AdStatus.PUBLISHED
    assert ad.final_score == 8.0
    assert ad.brief_id == brief.id

    got = await library.get_ad(ad.id)
    assert got is not None
    assert got.status == AdStatus.PUBLISHED
    assert got.final_score == 8.0
    assert got.brief_id == brief.id
