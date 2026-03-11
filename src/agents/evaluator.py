"""EvaluatorAgent stub. Quality judgment only. V3 wraps evaluate module."""

from src.agents.base import BaseAgent
from src.models.ad import Ad
from src.models.evaluation import EvaluationResult
from src.models.weights import WeightProfile


class EvaluatorAgent(BaseAgent):
    """Evaluator: quality judgment only. Never generates or edits. Uses claude-sonnet-4-6."""

    async def evaluate(
        self,
        ad: Ad,
        profile: WeightProfile,
    ) -> EvaluationResult:
        self._check_version()
        raise NotImplementedError(
            "EvaluatorAgent activates in V3. Set PIPELINE_VERSION=v3."
        )
