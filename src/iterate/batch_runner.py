"""Checkpointed batch execution over a list of briefs. Failure isolation per brief."""

from dataclasses import dataclass, field
from typing import List

from src.models.brief import Brief


@dataclass
class BatchResult:
    """Counts and brief_id lists for published, abandoned, failed."""

    published: List[str] = field(default_factory=list)
    abandoned: List[str] = field(default_factory=list)
    failed: List[str] = field(default_factory=list)

    @property
    def total_processed(self) -> int:
        return len(self.published) + len(self.abandoned) + len(self.failed)


class BatchRunner:
    """Processes briefs with checkpointing; one brief failure does not stop the batch."""

    def __init__(self, library) -> None:
        self._library = library

    async def run(self, run_id: str, briefs: List[Brief]) -> BatchResult:
        """Run batch; skip completed briefs for this run_id; isolate failures."""
        completed = await self._library.get_completed_briefs(run_id)
        completed_set = set(completed)
        to_run = [b for b in briefs if b.id not in completed_set]
        result = BatchResult()
        for brief in to_run:
            try:
                ad, status = await self._run_single_brief(brief, run_id)
                if status == "published":
                    result.published.append(brief.id)
                else:
                    result.abandoned.append(brief.id)
                await self._library.mark_brief_complete(run_id, brief.id)
            except Exception:
                result.failed.append(brief.id)
        return result

    async def _run_single_brief(self, brief: Brief, run_id: str):
        """Override in real pipeline; returns (Ad, status_str)."""
        raise NotImplementedError("Subclass or patch for tests")
