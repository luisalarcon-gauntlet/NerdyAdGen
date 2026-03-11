"""WriterAgent stub. First-draft creation only. V3 only."""

from src.agents.base import BaseAgent
from src.agents.models import CreativeIntelligenceReport
from src.models.ad import Ad
from src.models.brief import Brief


class WriterAgent(BaseAgent):
    """Writer: first-draft creation only. Never edits existing copy."""

    async def write(
        self,
        brief: Brief,
        intelligence: CreativeIntelligenceReport,
    ) -> Ad:
        self._check_version()
        raise NotImplementedError(
            "WriterAgent activates in V3. Set PIPELINE_VERSION=v3."
        )
