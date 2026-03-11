"""IterationRecord, QualityFailureRecord, FailureDiagnosis, FailurePattern. No imports from other src/."""
import enum
from typing import List

from pydantic import BaseModel, Field

from src.models.ids import generate_id


def _utc_now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


class FailurePattern(str, enum.Enum):
    PERSISTENT_WEAKNESS = "persistent_weakness"
    OSCILLATION = "oscillation"
    STALLED_IMPROVEMENT = "stalled_improvement"


class FailureDiagnosis(BaseModel):
    """Diagnosis for an abandoned ad."""

    pattern: FailurePattern
    summary: str
    suggested_action: str


class IterationRecord(BaseModel):
    """One regeneration attempt."""

    id: str = Field(default_factory=generate_id)
    ad_id: str
    attempt_number: int
    tier: str
    target_dimension: str
    strategy: str
    score_before: float
    score_after: float
    dimensions_improved: List[str]
    dimensions_regressed: List[str]
    oscillation_detected: bool
    cost_usd: float
    created_at: str = Field(default_factory=_utc_now_iso)


class QualityFailureRecord(BaseModel):
    """Record saved when an ad is abandoned."""

    id: str = Field(default_factory=generate_id)
    ad_id: str
    brief_id: str
    attempt_number: int
    failure_pattern: FailurePattern
    diagnosis: FailureDiagnosis
