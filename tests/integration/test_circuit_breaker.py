"""Integration: circuit breaker opens on repeated Gemini failures; skipped brief saved as abandoned."""
from unittest.mock import AsyncMock, patch

import pytest

from src.models.brief import Brief, AudienceType, CampaignGoal, HookStyle, Platform
from src.utils.circuit_breaker import CircuitBreaker, CircuitOpenError, CircuitState


def _resolved_brief(bid: str = "brief-circuit-1"):
    b = Brief(
        id=bid,
        audience=AudienceType.PARENT,
        campaign_goal=CampaignGoal.CONVERSION,
        product="SAT prep",
        hook_style=HookStyle.SOCIAL_PROOF,
        platform=Platform.FACEBOOK_FEED,
    )
    return b.resolve_inferred()


@pytest.mark.asyncio
async def test_repeated_gemini_failures_open_circuit_breaker(run_migrations, test_db_url):
    """Repeated Gemini failures open the circuit breaker."""
    cb = CircuitBreaker("gemini")
    for _ in range(5):
        cb.record_failure()
    assert cb.state == CircuitState.OPEN


@pytest.mark.asyncio
async def test_open_circuit_skips_brief_and_saves_abandoned_with_reason_circuit_open(
    run_migrations, test_db_url
):
    """Open circuit skips the brief; skipped brief saved as abandoned with reason=circuit_open."""
    from sqlalchemy.ext.asyncio import create_async_engine
    from src.output.library import AdLibrary
    from src.iterate.run_single import run_single_brief_loop
    from src.generate.v1_generator import V1Generator
    from src.evaluate.judge import Judge
    from src.models.weights import VarsityTutorsSATProfiles

    engine = create_async_engine(test_db_url)
    library = AdLibrary(engine)
    brief = _resolved_brief()
    await library.save_brief(brief)

    async def _generate_raise(_brief):
        raise CircuitOpenError("gemini")

    generator = AsyncMock(spec=V1Generator())
    generator.generate = _generate_raise
    generator.regenerate = AsyncMock()
    judge = Judge()
    profile = VarsityTutorsSATProfiles.PARENT_CONVERSION

    ad, status = await run_single_brief_loop(
        brief, "run-circuit-1", library, generator, judge, profile
    )
    assert status == "abandoned"
    assert ad.status.value == "abandoned"
    assert ad.primary_text == "[Skipped: circuit open]"

    got = await library.get_ad(ad.id)
    assert got is not None
    assert got.status.value == "abandoned"

    patterns = await library.get_failure_patterns()
    assert patterns
