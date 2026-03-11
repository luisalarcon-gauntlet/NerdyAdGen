"""Abstract BaseGenerator interface and regeneration types."""
import enum
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from src.models.ad import Ad
    from src.models.brief import Brief
    from src.models.evaluation import EvaluationResult


class GenerationError(Exception):
    """Raised when generation or parsing fails (e.g. malformed Gemini JSON)."""


class RegenerationApproach(str, enum.Enum):
    """How much of the ad to rewrite when regenerating."""

    FULL_REWRITE = "full_rewrite"
    TARGETED = "targeted"
    TONE_REWRITE = "tone_rewrite"
    HOOK_REWRITE = "hook_rewrite"


class RegenerationStrategy:
    """Dimension that failed and the approach to use for regeneration."""

    def __init__(self, dimension: str, approach: RegenerationApproach) -> None:
        self.dimension = dimension
        self.approach = approach


class BaseGenerator(ABC):
    """All generator versions implement this interface."""

    @abstractmethod
    async def generate(self, brief: "Brief") -> "Ad":
        """Generate a complete ad from a fully resolved brief."""

    @abstractmethod
    async def regenerate(
        self,
        ad: "Ad",
        evaluation: "EvaluationResult",
        strategy: RegenerationStrategy,
    ) -> "Ad":
        """Regenerate ad targeting a specific weak dimension."""
