"""RegenerationStrategy selection per dimension."""

from src.generate.base import RegenerationStrategy, RegenerationApproach


_DIMENSION_APPROACH = {
    "clarity": RegenerationApproach.FULL_REWRITE,
    "cta": RegenerationApproach.TARGETED,
    "emotional_resonance": RegenerationApproach.HOOK_REWRITE,
    "brand_voice": RegenerationApproach.TONE_REWRITE,
    "value_proposition": RegenerationApproach.TARGETED,
}


def get_strategy_for_dimension(dimension: str) -> RegenerationStrategy:
    """Return strategy (dimension + approach) for the given weakest dimension."""
    approach = _DIMENSION_APPROACH.get(dimension, RegenerationApproach.TARGETED)
    return RegenerationStrategy(dimension=dimension, approach=approach)
