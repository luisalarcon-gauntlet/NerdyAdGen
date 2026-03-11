"""V3 stub: WriterAgent orchestration. Activates when PIPELINE_VERSION=v3."""

from src.generate.base import BaseGenerator
from src.models.ad import Ad
from src.models.brief import Brief
from src.models.evaluation import EvaluationResult
from src.generate.base import RegenerationStrategy


class V3Generator(BaseGenerator):
    """V3 delegates to WriterAgent. Stub until PIPELINE_VERSION=v3."""

    async def generate(self, brief: Brief) -> Ad:
        raise NotImplementedError(
            "V3 generator requires PIPELINE_VERSION=v3."
        )

    async def regenerate(
        self,
        ad: Ad,
        evaluation: EvaluationResult,
        strategy: RegenerationStrategy,
    ) -> Ad:
        raise NotImplementedError(
            "V3 generator requires PIPELINE_VERSION=v3."
        )
