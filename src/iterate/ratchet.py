"""QualityRatchet: threshold management. V1 stub logs would_trigger, never changes threshold."""

import os


RATCHET_TRIGGER_WINDOW = 10
RATCHET_TRIGGER_BUFFER = 0.5
RATCHET_INCREMENT = 0.1
RATCHET_MINIMUM = 7.0
RATCHET_MAXIMUM = 9.0


class QualityRatchet:
    """V1: logs would_trigger, never changes threshold. V3: raises threshold when condition met."""

    def __init__(self, initial_threshold: float = 7.0) -> None:
        self.current_threshold = initial_threshold

    def update(self, recent_scores: list[float]) -> dict:
        """V1: return {would_trigger: bool}, never change current_threshold."""
        version = os.environ.get("PIPELINE_VERSION", "v1")
        if version != "v3":
            would_trigger = self._would_trigger(recent_scores)
            return {"would_trigger": would_trigger}
        would_trigger = self._would_trigger(recent_scores)
        if would_trigger:
            self.current_threshold = min(
                RATCHET_MAXIMUM,
                self.current_threshold + RATCHET_INCREMENT,
            )
        return {"would_trigger": would_trigger}

    def _would_trigger(self, recent_scores: list[float]) -> bool:
        if len(recent_scores) < RATCHET_TRIGGER_WINDOW:
            return False
        window = recent_scores[-RATCHET_TRIGGER_WINDOW:]
        avg = sum(window) / len(window)
        return avg >= self.current_threshold + RATCHET_TRIGGER_BUFFER
