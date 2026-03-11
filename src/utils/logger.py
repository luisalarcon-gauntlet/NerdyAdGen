"""Structured JSON event logger. One JSON object per line."""
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.config.settings import get_settings

# Required keys per event (for validation/documentation). All events get timestamp + level.
EVENTS = {
    "ad_generated": {"ad_id", "brief_id", "attempt_number"},
    "ad_evaluated": {"ad_id", "weighted_score", "knockout_passed", "attempt_number"},
    "ad_published": {"ad_id", "final_score", "total_attempts", "total_cost_usd"},
    "ad_abandoned": {"ad_id", "brief_id", "failure_pattern", "total_attempts"},
    "api_error": {"service", "error_type", "error_message", "attempt_number"},
    "retry_attempt": {"service", "attempt_number", "delay_seconds"},
    "circuit_breaker_opened": {"service", "consecutive_failures"},
    "circuit_breaker_closed": {"service"},
    "human_review_escalated": {"trigger_type", "urgency", "brief_id"},
    "human_review_suppressed": {"trigger_type", "reason"},
    "iteration_cycle_complete": {"cycle_number", "published_count", "abandoned_count", "avg_score"},
    "batch_started": {"run_id", "total_briefs"},
    "batch_resumed": {"run_id", "skipping_count"},
    "ratchet_would_trigger": {"current_threshold", "avg_score", "window_size"},
}


class StructuredLogger:
    """Log events as one JSON object per line to settings.log_file_path."""

    def log(self, event: str, level: str = "info", **kwargs: Any) -> None:
        payload = {
            "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "event": event,
            "level": level,
            **kwargs,
        }
        path = get_settings().log_file_path
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload) + "\n")


structured_logger = StructuredLogger()
