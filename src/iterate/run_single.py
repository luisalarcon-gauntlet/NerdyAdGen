"""Single-brief pipeline: generate → evaluate → (publish or abandon). Up to max_attempts."""

from typing import Any, Tuple

from src.config.settings import get_settings
from src.iterate.diagnosis import QualityFailureHandler
from src.iterate.loop import get_tier_for_attempt
from src.iterate.strategies import get_strategy_for_dimension
from src.models.ad import Ad, AdStatus
from src.models.brief import Brief
from src.models.ids import generate_id
from src.models.iteration import FailureDiagnosis, FailurePattern, QualityFailureRecord
from src.utils.circuit_breaker import CircuitOpenError


async def run_single_brief_loop(
    brief: Brief,
    run_id: str,
    library: Any,
    generator: Any,
    judge: Any,
    profile: Any,
) -> Tuple[Ad, str]:
    """Run up to max_iteration_attempts; return (ad, "published") or (ad, "abandoned")."""
    settings = get_settings()
    max_attempts = settings.max_iteration_attempts
    threshold = getattr(profile, "quality_threshold", 7.0)
    evaluations: list = []
    ad = None
    evaluation = None
    for attempt in range(1, max_attempts + 1):
        if attempt == 1:
            try:
                ad = await generator.generate(brief)
            except CircuitOpenError:
                stub = Ad(
                    id=generate_id(),
                    brief_id=brief.id,
                    status=AdStatus.ABANDONED,
                    primary_text="[Skipped: circuit open]",
                    headline="",
                    description="",
                    cta_button="",
                )
                await library.save_ad(stub)
                record = QualityFailureRecord(
                    ad_id=stub.id,
                    brief_id=brief.id,
                    attempt_number=0,
                    failure_pattern=FailurePattern.STALLED_IMPROVEMENT,
                    diagnosis=FailureDiagnosis(
                        pattern=FailurePattern.STALLED_IMPROVEMENT,
                        summary="circuit_open",
                        suggested_action="Retry after cooldown.",
                    ),
                )
                await library.save_failure_record(record)
                return (stub, "abandoned")
        else:
            strategy = get_strategy_for_dimension(evaluation.weakest_dimension.dimension)
            ad = await generator.regenerate(ad, evaluation, strategy)
        evaluation = await judge.evaluate(ad, profile, attempt_number=attempt)
        evaluations.append(evaluation)
        await library.save_evaluation(evaluation)
        ad.final_score = evaluation.weighted_score
        if evaluation.is_publishable(threshold):
            ad.status = AdStatus.PUBLISHED
            await library.save_ad(ad)
            return (ad, "published")
        tier = get_tier_for_attempt(attempt)
        if tier == "abandon":
            handler = QualityFailureHandler()
            diagnosis = handler.classify(evaluations, attempt_number=attempt, oscillation_detected=False)
            record = QualityFailureRecord(
                ad_id=ad.id,
                brief_id=brief.id,
                attempt_number=attempt,
                failure_pattern=diagnosis.pattern,
                diagnosis=diagnosis,
            )
            await library.save_failure_record(record)
            ad.status = AdStatus.ABANDONED
            await library.save_ad(ad)
            return (ad, "abandoned")
    ad.status = AdStatus.ABANDONED
    await library.save_ad(ad)
    return (ad, "abandoned")
