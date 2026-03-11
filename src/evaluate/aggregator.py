"""Weighted scoring and knockout enforcement for evaluation."""

from src.models.weights import DimensionWeights, KnockoutThresholds, apply_knockouts

DIMENSION_NAMES = [
    "clarity",
    "value_proposition",
    "cta",
    "brand_voice",
    "emotional_resonance",
]

MIN_SCORE = 1.0
MAX_SCORE = 10.0


def compute_weighted_score(
    scores: dict[str, float],
    weights: DimensionWeights,
) -> float:
    """Weighted score = sum(score × weight) for all five dimensions. Scores must be in [1, 10]."""
    for dim in DIMENSION_NAMES:
        s = scores.get(dim)
        if s is not None and (s < MIN_SCORE or s > MAX_SCORE):
            raise ValueError(f"Dimension score {dim}={s} must be between {MIN_SCORE} and {MAX_SCORE}")
    total = 0.0
    for dim in DIMENSION_NAMES:
        s = scores.get(dim, 0.0)
        w = getattr(weights, dim, 0.0)
        total += s * w
    return total
