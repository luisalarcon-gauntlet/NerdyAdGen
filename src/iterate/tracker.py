"""IterationTracker: oscillation and regression detection."""

from typing import List

from src.evaluate.aggregator import DIMENSION_NAMES


REGRESSION_THRESHOLD = 0.5


class IterationTracker:
    """Tracks weakest dimension per attempt for oscillation; provides regression detection."""

    def __init__(self) -> None:
        self._weakest_history: List[str] = []

    def record_weakest(self, dimension: str) -> None:
        self._weakest_history.append(dimension)

    def detect_oscillation(self) -> bool:
        """True if the same two dimensions alternate across at least 3 attempts."""
        if len(self._weakest_history) < 3:
            return False
        a, b = self._weakest_history[-3], self._weakest_history[-2]
        c = self._weakest_history[-1]
        if a != b and b != c and a == c:
            return True
        return False


def detect_regressions(
    prev_scores: dict[str, float],
    curr_scores: dict[str, float],
    threshold: float = REGRESSION_THRESHOLD,
) -> List[str]:
    """Dimensions that dropped more than threshold (exclusive). All five dimensions checked."""
    regressed: List[str] = []
    for dim in DIMENSION_NAMES:
        prev = prev_scores.get(dim)
        curr = curr_scores.get(dim)
        if prev is None or curr is None:
            continue
        drop = prev - curr
        if drop > threshold:
            regressed.append(dim)
    return regressed
