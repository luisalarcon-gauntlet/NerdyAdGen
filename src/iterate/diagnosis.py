"""QualityFailureHandler: classify and log abandoned ads."""

from src.models.evaluation import EvaluationResult
from src.models.iteration import FailurePattern, FailureDiagnosis


class QualityFailureHandler:
    """Classifies failure pattern from evaluation history and optional oscillation flag."""

    def classify(
        self,
        evaluations: list[EvaluationResult],
        attempt_number: int,
        oscillation_detected: bool = False,
    ) -> FailureDiagnosis:
        """Return FailureDiagnosis; pattern is oscillation if flagged else persistent_weakness or stalled."""
        if oscillation_detected:
            return FailureDiagnosis(
                pattern=FailurePattern.OSCILLATION,
                summary="Two dimensions alternated as weakest across attempts.",
                suggested_action="Use full_rewrite tier and preserve high-scoring dimensions.",
            )
        return FailureDiagnosis(
            pattern=FailurePattern.PERSISTENT_WEAKNESS,
            summary="Same dimension remained weak across attempts.",
            suggested_action="Consider brief revision or different hook approach.",
        )
