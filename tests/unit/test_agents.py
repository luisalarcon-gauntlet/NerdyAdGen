"""Unit tests for agents: version gating, interface compliance, model validation."""
from unittest.mock import MagicMock, patch

import pytest
from pydantic import ValidationError

from src.models.brief import Brief, AudienceType, CampaignGoal, HookStyle, Platform
from src.models.ad import Ad, AdStatus


def _v1_settings():
    m = MagicMock()
    m.pipeline_version = "v1"
    return m


# --- Version gating (all raise NotImplementedError in V1) ---


@pytest.mark.asyncio
async def test_researcher_agent_research_raises_not_implemented_error():
    from src.agents.researcher import ResearcherAgent
    with patch("src.agents.base.get_settings", return_value=_v1_settings()):
        agent = ResearcherAgent()
        brief = _brief()
        with pytest.raises(NotImplementedError) as exc_info:
            await agent.research(brief, [], [])
    assert "PIPELINE_VERSION" in str(exc_info.value) or "v3" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_writer_agent_write_raises_not_implemented_error():
    from src.agents.writer import WriterAgent
    from src.agents.models import CreativeIntelligenceReport
    with patch("src.agents.base.get_settings", return_value=_v1_settings()):
        agent = WriterAgent()
    brief = _brief()
    report = CreativeIntelligenceReport(
        brief_id="b1",
        winning_hooks=[],
        winning_ctas=[],
        emotional_angles=[],
        competitor_gaps=[],
        recommended_approach="test",
        confidence=0.8,
        created_at="2025-01-01T00:00:00Z",
    )
    with patch("src.agents.base.get_settings", return_value=_v1_settings()):
        with pytest.raises(NotImplementedError) as exc_info:
            await agent.write(brief, report)
    assert "PIPELINE_VERSION" in str(exc_info.value) or "v3" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_editor_agent_edit_raises_not_implemented_error():
    from src.agents.editor import EditorAgent
    from src.generate.base import RegenerationStrategy, RegenerationApproach
    from src.models.evaluation import EvaluationResult, DimensionScore, ConfidenceLevel
    with patch("src.agents.base.get_settings", return_value=_v1_settings()):
        agent = EditorAgent()
    ad = Ad(brief_id="b1", status=AdStatus.DRAFT, primary_text="x", headline="h", description="d", cta_button="cta")
    ev = EvaluationResult(
        ad_id="ad-1",
        attempt_number=1,
        weighted_score=6.0,
        knockout_passed=False,
        knockout_failures=[],
        dimension_scores=[
            DimensionScore(dimension="clarity", score=5.0, rationale="", self_confidence=0.8),
        ],
        requires_human_review=False,
        flags=[],
        confidence=0.8,
        confidence_level=ConfidenceLevel.MEDIUM,
    )
    strategy = RegenerationStrategy("clarity", RegenerationApproach.FULL_REWRITE)
    brief = _brief()
    with patch("src.agents.base.get_settings", return_value=_v1_settings()):
        with pytest.raises(NotImplementedError) as exc_info:
            await agent.edit(ad, ev, strategy, brief)
    assert "PIPELINE_VERSION" in str(exc_info.value) or "v3" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_evaluator_agent_evaluate_raises_not_implemented_error():
    from src.agents.evaluator import EvaluatorAgent
    from src.models.weights import VarsityTutorsSATProfiles
    with patch("src.agents.base.get_settings", return_value=_v1_settings()):
        agent = EvaluatorAgent()
    ad = Ad(brief_id="b1", status=AdStatus.DRAFT, primary_text="x", headline="h", description="d", cta_button="cta")
    profile = VarsityTutorsSATProfiles.PARENT_CONVERSION
    with patch("src.agents.base.get_settings", return_value=_v1_settings()):
        with pytest.raises(NotImplementedError) as exc_info:
            await agent.evaluate(ad, profile)
    assert "PIPELINE_VERSION" in str(exc_info.value) or "v3" in str(exc_info.value).lower()


@pytest.mark.asyncio
async def test_orchestrator_agent_run_brief_raises_not_implemented_error():
    from src.agents.orchestrator import OrchestratorAgent
    with patch("src.agents.base.get_settings", return_value=_v1_settings()):
        agent = OrchestratorAgent()
    brief = _brief()
    with patch("src.agents.base.get_settings", return_value=_v1_settings()):
        with pytest.raises(NotImplementedError) as exc_info:
            await agent.run_brief(brief)
    assert "PIPELINE_VERSION" in str(exc_info.value) or "v3" in str(exc_info.value).lower()


# --- Interface compliance ---


def test_researcher_agent_is_subclass_of_base_agent():
    from src.agents.base import BaseAgent
    from src.agents.researcher import ResearcherAgent
    assert issubclass(ResearcherAgent, BaseAgent)


def test_writer_agent_is_subclass_of_base_agent():
    from src.agents.base import BaseAgent
    from src.agents.writer import WriterAgent
    assert issubclass(WriterAgent, BaseAgent)


def test_editor_agent_is_subclass_of_base_agent():
    from src.agents.base import BaseAgent
    from src.agents.editor import EditorAgent
    assert issubclass(EditorAgent, BaseAgent)


def test_evaluator_agent_is_subclass_of_base_agent():
    from src.agents.base import BaseAgent
    from src.agents.evaluator import EvaluatorAgent
    assert issubclass(EvaluatorAgent, BaseAgent)


def test_orchestrator_agent_is_subclass_of_base_agent():
    from src.agents.base import BaseAgent
    from src.agents.orchestrator import OrchestratorAgent
    assert issubclass(OrchestratorAgent, BaseAgent)


# --- Model validation ---


def test_creative_intelligence_report_with_all_required_fields_valid():
    from src.agents.models import CreativeIntelligenceReport, HookPattern
    report = CreativeIntelligenceReport(
        brief_id="b1",
        winning_hooks=[
            HookPattern(style="social_proof", example="Join 10k students", competitor="VT", frequency=5),
        ],
        winning_ctas=["Learn More"],
        emotional_angles=["confidence"],
        competitor_gaps=["price"],
        recommended_approach="Lead with social proof",
        confidence=0.85,
        created_at="2025-01-01T00:00:00Z",
    )
    assert report.brief_id == "b1"
    assert report.confidence == 0.85


def test_hook_pattern_with_style_example_competitor_frequency_valid():
    from src.agents.models import HookPattern
    p = HookPattern(style="stat", example="95% improve", competitor="VT", frequency=3)
    assert p.style == "stat"
    assert p.frequency == 3


def test_orchestrator_result_status_accepts_published_abandoned_skipped():
    from src.agents.models import OrchestratorResult
    from src.models.ad import Ad
    from src.models.evaluation import EvaluationResult, DimensionScore, ConfidenceLevel
    ad = Ad(brief_id="b1", status=AdStatus.PUBLISHED, primary_text="x", headline="h", description="d", cta_button="cta")
    ev = EvaluationResult(
        ad_id="ad-1",
        attempt_number=1,
        weighted_score=8.0,
        knockout_passed=True,
        knockout_failures=[],
        dimension_scores=[
            DimensionScore(dimension="clarity", score=8.0, rationale="", self_confidence=0.9),
        ],
        requires_human_review=False,
        flags=[],
        confidence=0.9,
        confidence_level=ConfidenceLevel.HIGH,
    )
    for status in ("published", "abandoned", "skipped"):
        result = OrchestratorResult(
            status=status,
            ad=ad,
            evaluation=ev,
            attempts=1,
            intelligence_used=False,
            total_cost_usd=0.01,
        )
        assert result.status == status


def test_orchestrator_result_status_rejects_other_strings():
    from src.agents.models import OrchestratorResult
    from src.models.ad import Ad
    from src.models.evaluation import EvaluationResult, DimensionScore, ConfidenceLevel
    ad = Ad(brief_id="b1", status=AdStatus.PUBLISHED, primary_text="x", headline="h", description="d", cta_button="cta")
    ev = EvaluationResult(
        ad_id="ad-1",
        attempt_number=1,
        weighted_score=8.0,
        knockout_passed=True,
        knockout_failures=[],
        dimension_scores=[
            DimensionScore(dimension="clarity", score=8.0, rationale="", self_confidence=0.9),
        ],
        requires_human_review=False,
        flags=[],
        confidence=0.9,
        confidence_level=ConfidenceLevel.HIGH,
    )
    with pytest.raises(ValidationError):
        OrchestratorResult(
            status="invalid",
            ad=ad,
            evaluation=ev,
            attempts=1,
            intelligence_used=False,
            total_cost_usd=0.01,
        )


def _brief():
    b = Brief(
        id="b1",
        audience=AudienceType.PARENT,
        campaign_goal=CampaignGoal.CONVERSION,
        product="SAT prep",
        hook_style=HookStyle.SOCIAL_PROOF,
        platform=Platform.FACEBOOK_FEED,
    )
    return b.resolve_inferred()
