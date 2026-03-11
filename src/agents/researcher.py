"""ResearcherAgent stub. Competitive intelligence only. V3 only."""

from typing import List

from src.agents.base import BaseAgent
from src.agents.models import CreativeIntelligenceReport
from src.models.ad import Ad
from src.models.brief import Brief
from src.models.scraped_ad import ScrapedAd


class ResearcherAgent(BaseAgent):
    """Researcher: competitive intelligence only. Never writes, edits, or evaluates."""

    async def research(
        self,
        brief: Brief,
        competitor_ads: List[ScrapedAd],
        historical_ads: List[Ad],
    ) -> CreativeIntelligenceReport:
        self._check_version()
        raise NotImplementedError(
            "ResearcherAgent activates in V3. Set PIPELINE_VERSION=v3."
        )
