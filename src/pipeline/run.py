"""V1 batch pipeline: wires generator, judge, library, batch runner."""

import asyncio
from typing import List, Optional

from src.config.database import get_engine
from src.config.settings import get_settings
from src.evaluate.judge import Judge
from src.generate.v1_generator import V1Generator
from src.iterate.batch_runner import BatchResult, BatchRunner
from src.iterate.run_single import run_single_brief_loop
from src.models.brief import Brief
from src.models.weights import get_profile_registry
from src.output.library import AdLibrary


async def run_v1_async(
    run_id: Optional[str] = None,
    briefs: Optional[List[Brief]] = None,
) -> BatchResult:
    """Run V1 batch pipeline. Delegates to BatchRunner and run_single_brief_loop."""
    settings = get_settings()
    engine = get_engine()
    library = AdLibrary(engine)
    generator = V1Generator()
    judge = Judge()
    registry = get_profile_registry()
    profile = registry.resolve(audience="parent", campaign_goal="conversion")

    def _run_one(brief: Brief, rid: str):
        return run_single_brief_loop(brief, rid, library, generator, judge, profile)

    class Runner(BatchRunner):
        async def _run_single_brief(self, brief: Brief, rid: str):
            return await _run_one(brief, rid)

    runner = Runner(library=library)
    rid = run_id or "v1-run"
    brief_list = briefs or []
    return await runner.run(rid, brief_list)


def run_v1(
    run_id: Optional[str] = None,
    briefs: Optional[List[Brief]] = None,
) -> BatchResult:
    """Synchronous entry point for CLI."""
    return asyncio.run(run_v1_async(run_id=run_id, briefs=briefs))
