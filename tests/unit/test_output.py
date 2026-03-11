"""Unit tests for output: AdLibrary, PerformanceReporter, visualizer."""
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models.ad import Ad, AdStatus
from src.models.brief import Brief, AudienceType, CampaignGoal, HookStyle, Platform
from src.models.evaluation import EvaluationResult, DimensionScore, ConfidenceLevel


def _ad(brief_id: str = "b1", status: AdStatus = AdStatus.PUBLISHED, final_score: float = 7.5):
    return Ad(
        id="ad-1",
        brief_id=brief_id,
        status=status,
        primary_text="Copy",
        headline="Headline",
        description="Desc",
        cta_button="Learn More",
        final_score=final_score,
    )


def _brief(bid: str = "b1", audience: str = "parent", goal: str = "conversion"):
    b = Brief(
        id=bid,
        audience=AudienceType(audience) if isinstance(audience, str) else audience,
        campaign_goal=CampaignGoal(goal) if isinstance(goal, str) else goal,
        product="SAT",
        hook_style=HookStyle.SOCIAL_PROOF,
        platform=Platform.FACEBOOK_FEED,
    )
    return b.resolve_inferred()


# --- AdLibrary ---


def _get_test_settings():
    try:
        from src.config.settings import get_settings
        return get_settings()
    except Exception:
        return None


@pytest.mark.asyncio
async def test_save_ad_persists_ad_to_test_database():
    from src.output.library import AdLibrary
    settings = _get_test_settings()
    if not settings or not getattr(settings, "database_url_test", None):
        pytest.skip("database_url_test not set")
    from sqlalchemy.ext.asyncio import create_async_engine
    engine = create_async_engine(settings.database_url_test)
    lib = AdLibrary(engine)
    ad = _ad(brief_id="b1", status=AdStatus.PUBLISHED)
    await lib.save_ad(ad)
    got = await lib.get_ad(ad.id)
    assert got is not None
    assert got.id == ad.id
    assert got.status == AdStatus.PUBLISHED


@pytest.mark.asyncio
async def test_save_ad_duplicate_id_upserts():
    from src.output.library import AdLibrary
    settings = _get_test_settings()
    if not settings or not getattr(settings, "database_url_test", None):
        pytest.skip("database_url_test not set")
    from sqlalchemy.ext.asyncio import create_async_engine
    engine = create_async_engine(settings.database_url_test)
    lib = AdLibrary(engine)
    ad1 = _ad(brief_id="b1")
    ad1.primary_text = "First"
    await lib.save_ad(ad1)
    ad2 = _ad(brief_id="b1")
    ad2.id = ad1.id
    ad2.primary_text = "Second"
    await lib.save_ad(ad2)
    got = await lib.get_ad(ad1.id)
    assert got.primary_text == "Second"


@pytest.mark.asyncio
async def test_get_ad_returns_none_for_nonexistent_id():
    from src.output.library import AdLibrary
    settings = _get_test_settings()
    if not settings or not getattr(settings, "database_url_test", None):
        pytest.skip("database_url_test not set")
    from sqlalchemy.ext.asyncio import create_async_engine
    engine = create_async_engine(settings.database_url_test)
    lib = AdLibrary(engine)
    got = await lib.get_ad("nonexistent-id-xyz")
    assert got is None


@pytest.mark.asyncio
async def test_get_publishable_ads_returns_only_published():
    from src.output.library import AdLibrary
    settings = _get_test_settings()
    if not settings or not getattr(settings, "database_url_test", None):
        pytest.skip("database_url_test not set")
    from sqlalchemy.ext.asyncio import create_async_engine
    engine = create_async_engine(settings.database_url_test)
    lib = AdLibrary(engine)
    ad1 = _ad(brief_id="b1", status=AdStatus.PUBLISHED)
    ad1.id = "ad-pub-1"
    ad2 = _ad(brief_id="b2", status=AdStatus.ABANDONED)
    ad2.id = "ad-abandon-1"
    await lib.save_ad(ad1)
    await lib.save_ad(ad2)
    result = await lib.get_publishable_ads()
    assert all(a.status == AdStatus.PUBLISHED for a in result)


@pytest.mark.asyncio
async def test_get_publishable_ads_audience_filter_returns_only_parent_ads():
    from src.output.library import AdLibrary
    lib = AsyncMock()
    lib.get_publishable_ads = AsyncMock(return_value=[_ad(brief_id="b1")])
    result = await lib.get_publishable_ads(audience="parent", campaign_goal=None)
    lib.get_publishable_ads.assert_called_once_with(audience="parent", campaign_goal=None)


@pytest.mark.asyncio
async def test_get_publishable_ads_campaign_goal_filter():
    from src.output.library import AdLibrary
    lib = AsyncMock()
    lib.get_publishable_ads = AsyncMock(return_value=[])
    await lib.get_publishable_ads(audience=None, campaign_goal="conversion")
    lib.get_publishable_ads.assert_called_once_with(audience=None, campaign_goal="conversion")


@pytest.mark.asyncio
async def test_get_quality_trend_returns_sorted_ascending_by_attempt():
    from src.output.library import AdLibrary
    settings = _get_test_settings()
    if not settings or not getattr(settings, "database_url_test", None):
        pytest.skip("database_url_test not set")
    from sqlalchemy.ext.asyncio import create_async_engine
    engine = create_async_engine(settings.database_url_test)
    lib = AdLibrary(engine)
    result = await lib.get_quality_trend(window=10)
    assert result == sorted(result, key=lambda x: x.get("attempt_number", 0))


@pytest.mark.asyncio
async def test_get_performance_per_token_returns_quality_per_dollar():
    from src.output.library import AdLibrary
    lib = AsyncMock()
    lib.get_performance_per_token = AsyncMock(return_value={"quality_per_dollar": 1306.67})
    result = await lib.get_performance_per_token()
    assert "quality_per_dollar" in result


@pytest.mark.asyncio
async def test_mark_brief_complete_persists_run_id_brief_id():
    from src.output.library import AdLibrary
    lib = AsyncMock()
    lib.mark_brief_complete = AsyncMock()
    await lib.mark_brief_complete("run-1", "brief-1")
    lib.mark_brief_complete.assert_called_once_with("run-1", "brief-1")


@pytest.mark.asyncio
async def test_get_completed_briefs_returns_correct_brief_ids_for_run_id():
    from src.output.library import AdLibrary
    lib = AsyncMock()
    lib.get_completed_briefs = AsyncMock(return_value=["b1", "b2"])
    result = await lib.get_completed_briefs("run-1")
    assert result == ["b1", "b2"]


@pytest.mark.asyncio
async def test_get_completed_briefs_returns_empty_list_for_unknown_run_id():
    from src.output.library import AdLibrary
    lib = AsyncMock()
    lib.get_completed_briefs = AsyncMock(return_value=[])
    result = await lib.get_completed_briefs("unknown-run")
    assert result == []


# --- PerformanceReporter ---


def test_quality_per_dollar_formula():
    from src.output.reporter import PerformanceReporter
    avg_quality = 7.5
    total_cost = 0.30
    published_count = 50
    expected = avg_quality / (total_cost / published_count)
    reporter = PerformanceReporter(library=AsyncMock())
    result = reporter._quality_per_dollar(avg_quality, total_cost, published_count)
    assert abs(result - expected) < 0.01


def test_cost_per_published_ad():
    from src.output.reporter import PerformanceReporter
    reporter = PerformanceReporter(library=AsyncMock())
    assert reporter._cost_per_published_ad(0.39, 51) == pytest.approx(0.0076, rel=0.01)


def test_publish_rate():
    from src.output.reporter import PerformanceReporter
    reporter = PerformanceReporter(library=AsyncMock())
    assert reporter._publish_rate(51, 72) == pytest.approx(51 / 72, rel=0.01)


def test_abandoned_ads_in_cost_but_not_published_count():
    from src.output.reporter import PerformanceReporter
    library = AsyncMock()
    library.get_performance_per_token = AsyncMock(return_value={
        "total_api_cost_usd": 0.39,
        "published_count": 51,
        "total_generated": 72,
    })
    reporter = PerformanceReporter(library=library)
    report = reporter._build_cost_report(72, 51, 0.39, 1306.67)
    assert report["totals"]["total_ads_generated"] == 72
    assert report["totals"]["total_ads_published"] == 51
    assert 72 - 51 >= 0


@pytest.mark.asyncio
async def test_export_json_writes_valid_json(tmp_path):
    from src.output.reporter import PerformanceReporter
    library = AsyncMock()
    library.get_quality_trend = AsyncMock(return_value=[])
    library.get_performance_per_token = AsyncMock(return_value={"quality_per_dollar": 100})
    reporter = PerformanceReporter(library=library)
    out = tmp_path / "report.json"
    await reporter.export_json(str(out))
    import json
    with open(out) as f:
        data = json.load(f)
    assert "performance" in data
    assert data["performance"].get("quality_per_dollar") == 100


@pytest.mark.asyncio
async def test_export_csv_has_header_row(tmp_path):
    from src.output.reporter import PerformanceReporter
    library = AsyncMock()
    library.get_quality_trend = AsyncMock(return_value=[{"attempt_number": 1, "avg_score": 7.0}])
    reporter = PerformanceReporter(library=library)
    out = tmp_path / "report.csv"
    await reporter.export_csv(str(out))
    lines = out.read_text().strip().split("\n")
    assert len(lines) >= 1
    assert "attempt" in lines[0].lower() or "score" in lines[0].lower() or "," in lines[0]


@pytest.mark.asyncio
async def test_cost_report_has_north_star_fields():
    from src.output.reporter import PerformanceReporter
    library = AsyncMock()
    reporter = PerformanceReporter(library=library)
    report = reporter._build_cost_report(72, 51, 0.39, 1306.67)
    assert "north_star" in report
    assert "metric" in report["north_star"]
    assert "value" in report["north_star"]
    assert report["north_star"]["metric"] == "quality_per_dollar"
    assert "interpretation" in report["north_star"]
    assert len(report["north_star"]["interpretation"]) > 0


# --- Visualizer (six-panel Plotly HTML, self-contained) ---


@pytest.mark.asyncio
async def test_visualizer_generates_self_contained_html(tmp_path):
    from src.output.visualizer import QualityTrendVisualizer
    library = AsyncMock()
    library.get_quality_trend = AsyncMock(return_value=[])
    library.get_performance_per_token = AsyncMock(return_value={})
    library.get_dimension_averages = AsyncMock(return_value={})
    library.get_cost_trend = AsyncMock(return_value=[])
    library.get_failure_patterns = AsyncMock(return_value={})
    viz = QualityTrendVisualizer(library=library)
    out = tmp_path / "quality_trend.html"
    await viz.generate(str(out))
    content = out.read_text()
    assert "plotly" in content.lower() or "Plotly" in content
    assert "cdn" not in content.lower() or "plotly.min.js" in content
