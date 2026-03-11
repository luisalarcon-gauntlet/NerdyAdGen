"""Claude-powered evaluation. Judge only — never generates or suggests edits."""
import json
import logging
import statistics

from src.config.settings import get_settings
from src.evaluate.aggregator import compute_weighted_score
from src.evaluate.confidence import get_confidence_level, should_use_high_confidence_mode
from src.evaluate.conflict_detector import detect_conflicts
from src.evaluate.rubrics import get_rubric_block
from src.models.ad import Ad
from src.models.evaluation import (
    EvaluationResult,
    DimensionScore,
    ConfidenceLevel,
)
from src.models.weights import WeightProfile, apply_knockouts
from src.utils.retry import with_retry
from src.utils.tracking import track_tokens

logger = logging.getLogger(__name__)

HIGH_CONFIDENCE_RUNS = 3
HIGH_CONFIDENCE_TEMPERATURE = 0.2
DEFAULT_TEMPERATURE = 0.3


@with_retry(max_attempts=3, service="claude")
@track_tokens(
    operation="evaluation",
    model="claude-sonnet-4-6",
    provider="anthropic",
    persist_callback=None,
)
async def _call_claude(prompt: str, temperature: float = DEFAULT_TEMPERATURE) -> str:
    """Call Claude Sonnet 4.6; return response text. Patch in tests."""
    from anthropic import AsyncAnthropic
    settings = get_settings()
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    msg = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        temperature=temperature,
        messages=[{"role": "user", "content": prompt}],
    )
    text = msg.content[0].text if msg.content else ""
    logger.info("Claude raw response (first 200 chars): %r", text[:200])
    if not text:
        raise ValueError("Claude returned an empty response")
    return text


def _extract_json(raw: str) -> str:
    """Strip markdown fences and extract the first {...} JSON object from raw text."""
    # Remove ```json ... ``` or ``` ... ``` wrappers
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        # drop first and last fence lines
        inner = []
        in_block = False
        for line in lines:
            if line.startswith("```") and not in_block:
                in_block = True
                continue
            if line.startswith("```") and in_block:
                break
            if in_block:
                inner.append(line)
        text = "\n".join(inner).strip()
    # Find first { ... } block
    start = text.find("{")
    if start == -1:
        return text
    # Find matching closing brace
    depth = 0
    for i, ch in enumerate(text[start:], start=start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return text[start:]


def _parse_dimension_scores(raw: str) -> list[DimensionScore]:
    """Parse Claude JSON response into list of DimensionScore.

    Tolerates markdown fences and preamble text before the JSON object.
    """
    cleaned = _extract_json(raw)
    data = json.loads(cleaned)
    scores = data.get("dimension_scores", [])
    out: list[DimensionScore] = []
    for s in scores:
        out.append(DimensionScore(
            dimension=str(s.get("dimension", "")),
            score=float(s.get("score", 0)),
            rationale=str(s.get("rationale", "")),
            self_confidence=float(s.get("self_confidence", 0.5)),
        ))
    return out


def _scores_dict_from_dimension_scores(dimension_scores: list[DimensionScore]) -> dict[str, float]:
    return {d.dimension: d.score for d in dimension_scores}


def _build_eval_prompt(ad: Ad, profile: WeightProfile) -> str:
    """Build judge prompt with rubric and ad copy. Return ONLY JSON."""
    rubric = get_rubric_block()
    return f"""Score this ad from the rubric anchors. Return ONLY valid JSON — no preamble.

## Rubric
{rubric}

## Ad to score
Primary text: {ad.primary_text}
Headline: {ad.headline}
Description: {ad.description}
CTA: {ad.cta_button}

## Profile
Audience: {profile.audience}
Campaign goal: {profile.campaign_goal}

## Output
JSON with key "dimension_scores": array of {{"dimension", "score", "rationale", "self_confidence"}} for clarity, value_proposition, cta, brand_voice, emotional_resonance. Scores 1.0-10.0."""


class ClaudeJudge:
    """Evaluates ad quality via Claude Sonnet 4.6. Judge only."""

    async def evaluate(
        self,
        ad: Ad,
        profile: WeightProfile,
        attempt_number: int = 1,
    ) -> EvaluationResult:
        settings = get_settings()
        band = settings.confidence_band

        raw = await _call_claude(_build_eval_prompt(ad, profile), temperature=DEFAULT_TEMPERATURE)
        dimension_scores = _parse_dimension_scores(raw)
        scores_dict = _scores_dict_from_dimension_scores(dimension_scores)

        weighted_score = compute_weighted_score(scores_dict, profile.weights)
        knockout_result = apply_knockouts(scores_dict, profile.knockout_thresholds)

        if should_use_high_confidence_mode(weighted_score, profile.quality_threshold, band):
            weighted_scores_for_var = [weighted_score]
            for _ in range(HIGH_CONFIDENCE_RUNS - 1):
                r = await _call_claude(_build_eval_prompt(ad, profile), temperature=HIGH_CONFIDENCE_TEMPERATURE)
                ds = _parse_dimension_scores(r)
                sd = _scores_dict_from_dimension_scores(ds)
                weighted_scores_for_var.append(compute_weighted_score(sd, profile.weights))
            if len(weighted_scores_for_var) >= 2:
                variance = statistics.variance(weighted_scores_for_var)
                normalized = min(variance / 10.0, 1.0)
                confidence = max(0.0, 1.0 - normalized)
            else:
                confidence = 0.8
        else:
            confidence = sum(d.self_confidence for d in dimension_scores) / len(dimension_scores) if dimension_scores else 0.5

        confidence_level = get_confidence_level(confidence)
        flags = detect_conflicts(scores_dict)

        return EvaluationResult(
            ad_id=ad.id,
            attempt_number=attempt_number,
            weighted_score=weighted_score,
            knockout_passed=knockout_result.knockout_passed,
            knockout_failures=knockout_result.knockout_failures,
            dimension_scores=dimension_scores,
            requires_human_review=False,
            flags=flags,
            confidence=confidence,
            confidence_level=confidence_level,
        )


Judge = ClaudeJudge
