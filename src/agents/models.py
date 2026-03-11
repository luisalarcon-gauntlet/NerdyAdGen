"""Agent data models: CreativeIntelligenceReport, HookPattern, OrchestratorResult."""

from typing import List, Literal

from pydantic import BaseModel

from src.models.ad import Ad
from src.models.evaluation import EvaluationResult


class HookPattern(BaseModel):
    """Observed hook pattern from competitor ads."""

    style: str
    example: str
    competitor: str
    frequency: int


class CreativeIntelligenceReport(BaseModel):
    """Research output from ResearcherAgent."""

    brief_id: str
    winning_hooks: List[HookPattern]
    winning_ctas: List[str]
    emotional_angles: List[str]
    competitor_gaps: List[str]
    recommended_approach: str
    confidence: float
    created_at: str


OrchestratorStatus = Literal["published", "abandoned", "skipped"]


class OrchestratorResult(BaseModel):
    """Result of OrchestratorAgent.run_brief."""

    status: OrchestratorStatus
    ad: Ad
    evaluation: EvaluationResult
    attempts: int
    intelligence_used: bool
    total_cost_usd: float
