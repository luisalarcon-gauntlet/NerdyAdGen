"""EditorAgent stub. Targeted improvement only. V3 only."""

from src.agents.base import BaseAgent
from src.generate.base import RegenerationStrategy
from src.models.ad import Ad
from src.models.brief import Brief
from src.models.evaluation import EvaluationResult


class EditorAgent(BaseAgent):
    """Editor: targeted improvement only. Never creates from a blank brief."""

    async def edit(
        self,
        ad: Ad,
        evaluation: EvaluationResult,
        strategy: RegenerationStrategy,
        brief: Brief,
    ) -> Ad:
        self._check_version()
        raise NotImplementedError(
            "EditorAgent activates in V3. Set PIPELINE_VERSION=v3."
        )
