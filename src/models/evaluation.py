"""EvaluationResult, DimensionScore, ConfidenceLevel, FlagType. No imports from other src/."""
import enum
from typing import List

from pydantic import BaseModel, Field

from src.models.ids import generate_id


def _utc_now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


class DimensionScore(BaseModel):
    """Single dimension score from the judge."""

    id: str = Field(default_factory=generate_id)
    dimension: str
    score: float
    rationale: str
    self_confidence: float


class ConfidenceLevel(str, enum.Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class FlagType(str, enum.Enum):
    DIMENSION_CONFLICT = "dimension_conflict"
    OTHER = "other"


class EvaluationResult(BaseModel):
    """Full evaluation for one ad attempt. is_publishable and weakest_dimension are computed."""

    id: str = Field(default_factory=generate_id)
    ad_id: str
    attempt_number: int
    weighted_score: float
    knockout_passed: bool
    knockout_failures: List[str]
    dimension_scores: List[DimensionScore]
    requires_human_review: bool
    flags: List[str]
    confidence: float
    confidence_level: ConfidenceLevel
    created_at: str = Field(default_factory=_utc_now_iso)

    def is_publishable(self, quality_threshold: float) -> bool:
        """True iff knockout passed and weighted_score >= quality_threshold."""
        return self.knockout_passed and self.weighted_score >= quality_threshold

    @property
    def weakest_dimension(self) -> DimensionScore:
        """Lowest-scoring dimension. Ties broken by list order."""
        return min(self.dimension_scores, key=lambda d: d.score)
