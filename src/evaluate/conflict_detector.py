"""Deterministic dimension conflict pattern detection. No LLM."""

PATTERN_HIGH_RESONANCE_LOW_CLARITY = "Great hook, unclear offer"
PATTERN_HIGH_CLARITY_LOW_RESONANCE = "Crystal clear, but nobody cares"
PATTERN_STRONG_CTA_WEAK_VALUE = "Urgent ask with no reason to act"


def detect_conflicts(scores: dict[str, float]) -> list[str]:
    """Detect three conflict patterns from dimension scores. Returns list of flag messages."""
    flags: list[str] = []
    clarity = scores.get("clarity")
    value_proposition = scores.get("value_proposition")
    cta = scores.get("cta")
    emotional_resonance = scores.get("emotional_resonance")

    if emotional_resonance is not None and clarity is not None:
        if emotional_resonance >= 7.5 and clarity <= 5.5:
            flags.append(PATTERN_HIGH_RESONANCE_LOW_CLARITY)
    if clarity is not None and emotional_resonance is not None:
        if clarity >= 8.0 and emotional_resonance <= 4.5:
            flags.append(PATTERN_HIGH_CLARITY_LOW_RESONANCE)
    if cta is not None and value_proposition is not None:
        if cta >= 7.5 and value_proposition <= 5.0:
            flags.append(PATTERN_STRONG_CTA_WEAK_VALUE)

    return flags
