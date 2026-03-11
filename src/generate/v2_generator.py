"""V2 stub: image prompt generation. Activates when PIPELINE_VERSION=v2."""

from src.generate.base import BaseGenerator
from src.models.ad import Ad
from src.models.brief import Brief
from src.models.evaluation import EvaluationResult
from src.generate.base import RegenerationStrategy


class V2Generator(BaseGenerator):
    """V2 adds image prompt generation. Stub until PIPELINE_VERSION=v2."""

    async def generate(self, brief: Brief) -> Ad:
        raise NotImplementedError(
            "V2 generator requires PIPELINE_VERSION=v2."
        )

    async def regenerate(
        self,
        ad: Ad,
        evaluation: EvaluationResult,
        strategy: RegenerationStrategy,
    ) -> Ad:
        raise NotImplementedError(
            "V2 generator requires PIPELINE_VERSION=v2."
        )
