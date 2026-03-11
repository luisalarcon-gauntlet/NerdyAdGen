"""OrchestratorAgent stub. Routing and coordination only. V3 only."""

from src.agents.base import BaseAgent
from src.agents.models import OrchestratorResult
from src.models.brief import Brief


class OrchestratorAgent(BaseAgent):
    """Orchestrator: routing and coordination only. No creative or evaluative decisions."""

    async def run_brief(self, brief: Brief) -> OrchestratorResult:
        self._check_version()
        raise NotImplementedError(
            "OrchestratorAgent activates in V3. Set PIPELINE_VERSION=v3."
        )
