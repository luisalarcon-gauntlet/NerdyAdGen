"""Unit tests for batch_runner: checkpointing, failure isolation, batch result counts."""
from unittest.mock import AsyncMock, patch

import pytest

from src.models.brief import Brief, AudienceType, CampaignGoal, HookStyle, Platform
from src.models.ad import Ad, AdStatus


def _resolved_brief(brief_id: str = "brief-1"):
    b = Brief(
        id=brief_id,
        audience=AudienceType.PARENT,
        campaign_goal=CampaignGoal.CONVERSION,
        product="SAT prep",
        hook_style=HookStyle.SOCIAL_PROOF,
        platform=Platform.FACEBOOK_FEED,
    )
    return b.resolve_inferred()


# --- Checkpointing ---


@pytest.mark.asyncio
async def test_completed_brief_id_saved_after_each_ad():
    from src.iterate.batch_runner import BatchRunner, BatchResult
    completed = []
    async def mock_mark_complete(run_id: str, brief_id: str):
        completed.append((run_id, brief_id))

    library = AsyncMock()
    library.mark_brief_complete = mock_mark_complete
    library.get_completed_briefs = AsyncMock(return_value=[])
    runner = BatchRunner(library=library)
    briefs = [_resolved_brief("b1")]
    ad = Ad(brief_id="b1", status=AdStatus.PUBLISHED, primary_text="x", headline="h", description="d", cta_button="cta")
    with patch.object(runner, "_run_single_brief", new_callable=AsyncMock, return_value=(ad, "published")):
        result = await runner.run(run_id="run-1", briefs=briefs)
    assert ("run-1", "b1") in completed


@pytest.mark.asyncio
async def test_resumed_batch_skips_already_completed_briefs():
    from src.iterate.batch_runner import BatchRunner
    library = AsyncMock()
    library.get_completed_briefs = AsyncMock(return_value=["b1", "b2", "b3"])
    library.mark_brief_complete = AsyncMock()
    runner = BatchRunner(library=library)
    briefs = [_resolved_brief("b1"), _resolved_brief("b2"), _resolved_brief("b3"), _resolved_brief("b4")]
    run_one = AsyncMock()
    ad = Ad(brief_id="b4", status=AdStatus.PUBLISHED, primary_text="x", headline="h", description="d", cta_button="cta")
    run_one.return_value = (ad, "published")
    with patch.object(runner, "_run_single_brief", run_one):
        result = await runner.run(run_id="run-1", briefs=briefs)
    assert run_one.await_count == 1


@pytest.mark.asyncio
async def test_new_run_id_starts_fresh_even_if_briefs_completed_in_other_run():
    from src.iterate.batch_runner import BatchRunner
    library = AsyncMock()
    library.get_completed_briefs = AsyncMock(return_value=[])
    library.mark_brief_complete = AsyncMock()
    runner = BatchRunner(library=library)
    briefs = [_resolved_brief("b1")]
    run_one = AsyncMock()
    ad = Ad(brief_id="b1", status=AdStatus.PUBLISHED, primary_text="x", headline="h", description="d", cta_button="cta")
    run_one.return_value = (ad, "published")
    with patch.object(runner, "_run_single_brief", run_one):
        await runner.run(run_id="new-run-2", briefs=briefs)
    library.get_completed_briefs.assert_called_with("new-run-2")
    assert run_one.await_count == 1


# --- Failure isolation ---


@pytest.mark.asyncio
async def test_exception_during_one_brief_logged_as_failed_batch_continues():
    from src.iterate.batch_runner import BatchRunner
    library = AsyncMock()
    library.get_completed_briefs = AsyncMock(return_value=[])
    library.mark_brief_complete = AsyncMock()
    runner = BatchRunner(library=library)
    briefs = [_resolved_brief("b1"), _resolved_brief("b2")]
    call_count = 0
    async def run_one(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("simulated failure")
        ad = Ad(brief_id="b2", status=AdStatus.PUBLISHED, primary_text="x", headline="h", description="d", cta_button="cta")
        return (ad, "published")
    with patch.object(runner, "_run_single_brief", side_effect=run_one):
        result = await runner.run(run_id="run-1", briefs=briefs)
    assert len(result.failed) == 1
    assert result.failed[0] == "b1"


@pytest.mark.asyncio
async def test_failed_brief_does_not_affect_subsequent_briefs():
    from src.iterate.batch_runner import BatchRunner
    library = AsyncMock()
    library.get_completed_briefs = AsyncMock(return_value=[])
    library.mark_brief_complete = AsyncMock()
    runner = BatchRunner(library=library)
    briefs = [_resolved_brief("b1"), _resolved_brief("b2")]
    ad = Ad(brief_id="b2", status=AdStatus.PUBLISHED, primary_text="x", headline="h", description="d", cta_button="cta")
    run_one = AsyncMock(side_effect=[RuntimeError("fail"), (ad, "published")])
    with patch.object(runner, "_run_single_brief", run_one):
        result = await runner.run(run_id="run-1", briefs=briefs)
    assert run_one.await_count == 2
    assert len(result.published) == 1 and len(result.failed) == 1


@pytest.mark.asyncio
async def test_batch_result_published_plus_abandoned_plus_failed_equals_total():
    from src.iterate.batch_runner import BatchRunner, BatchResult
    library = AsyncMock()
    library.get_completed_briefs = AsyncMock(return_value=[])
    library.mark_brief_complete = AsyncMock()
    runner = BatchRunner(library=library)
    briefs = [_resolved_brief("b1"), _resolved_brief("b2"), _resolved_brief("b3")]
    ad_pub = Ad(brief_id="b1", status=AdStatus.PUBLISHED, primary_text="x", headline="h", description="d", cta_button="cta")
    ad_abandon = Ad(brief_id="b2", status=AdStatus.ABANDONED, primary_text="x", headline="h", description="d", cta_button="cta")
    run_one = AsyncMock(side_effect=[
        (ad_pub, "published"),
        (ad_abandon, "abandoned"),
        RuntimeError("fail"),
    ])
    with patch.object(runner, "_run_single_brief", run_one):
        result = await runner.run(run_id="run-1", briefs=briefs)
    total = len(result.published) + len(result.abandoned) + len(result.failed)
    assert total == 3
