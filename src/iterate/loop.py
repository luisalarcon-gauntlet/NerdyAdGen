"""Core generate → evaluate → improve cycle. Tier logic and effective tier with oscillation."""

from src.iterate.tracker import IterationTracker


def get_tier_for_attempt(attempt_number: int) -> str:
    """Tier from attempt only. 1-3 targeted, 4-5 full_rewrite, 6 brief_revision, 7+ abandon."""
    if attempt_number <= 0:
        return "targeted"
    if attempt_number <= 3:
        return "targeted"
    if attempt_number <= 5:
        return "full_rewrite"
    if attempt_number == 6:
        return "brief_revision"
    return "abandon"


def get_effective_tier(attempt_number: int, oscillation_detected: bool = False) -> str:
    """Tier for this attempt; oscillation escalates to full_rewrite."""
    if oscillation_detected and attempt_number >= 2:
        return "full_rewrite"
    return get_tier_for_attempt(attempt_number)
