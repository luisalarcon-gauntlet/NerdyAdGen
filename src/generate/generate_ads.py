"""Batch ad copy generator using Claude claude-sonnet-4-6 with few-shot examples.

Loads top 3 scored competitor ads as few-shot examples, then generates 10 ads
per brief across 5 briefs (50+ total). Saves to data/generated/ads_raw.json.
"""
import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from anthropic import AsyncAnthropic

logger = logging.getLogger(__name__)

SCORED_ADS_PATH = Path("data/evaluated/competitor_ads_scored.json")
RAW_ADS_PATH = Path("data/raw/competitor_ads.json")
OUTPUT_PATH = Path("data/generated/ads_raw.json")

MODEL = "claude-sonnet-4-6"
TEMPERATURE = 0.7
ADS_PER_BRIEF = 10

VALID_CTA_BUTTONS = [
    "Learn More",
    "Sign Up",
    "Get Started",
    "Start Free Trial",
    "Book Now",
    "Contact Us",
    "Apply Now",
    "Download",
]

# 5 briefs covering the required audience × goal × angle matrix
BRIEFS = [
    {
        "id": "brief-parents-awareness",
        "audience": "parents of high school juniors anxious about college admissions",
        "goal": "awareness",
        "tone": "empowering, reassuring, outcome-focused",
        "cta": "Learn More",
    },
    {
        "id": "brief-parents-conversion",
        "audience": "parents actively comparing SAT prep options and weighing value",
        "goal": "conversion",
        "tone": "confident, credibility-forward, results-driven",
        "cta": "Sign Up",
    },
    {
        "id": "brief-students-awareness",
        "audience": "high school students stressed about an upcoming SAT",
        "goal": "awareness",
        "tone": "energetic, empathetic, motivational",
        "cta": "Learn More",
    },
    {
        "id": "brief-students-conversion",
        "audience": "high school students who want a guaranteed score improvement",
        "goal": "conversion",
        "tone": "direct, specific, results-focused",
        "cta": "Sign Up",
    },
    {
        "id": "brief-both-urgency",
        "audience": "students and parents with a SAT test date within 8 weeks",
        "goal": "conversion",
        "tone": "urgent, action-oriented, reassuring that there is still time",
        "cta": "Sign Up",
    },
]


def _load_top_examples(n: int = 3) -> list[dict[str, Any]]:
    """Return top N ads from competitor_ads_scored.json sorted by aggregate_score."""
    data: list[dict[str, Any]] = json.loads(
        SCORED_ADS_PATH.read_text(encoding="utf-8")
    )
    # Build lookup from raw ads (have headline/description the scored file omits)
    raw_lookup: dict[str, dict[str, Any]] = {}
    if RAW_ADS_PATH.exists():
        raw_data = json.loads(RAW_ADS_PATH.read_text(encoding="utf-8"))
        for r in raw_data:
            raw_lookup[r.get("ad_id", "")] = r

    scored = [r for r in data if "aggregate_score" in r and "error" not in r]
    scored.sort(key=lambda x: x["aggregate_score"], reverse=True)
    top = scored[:n]

    # Enrich with headline/description from raw if available
    for ex in top:
        raw = raw_lookup.get(ex.get("ad_id", ""), {})
        ex.setdefault("headline", raw.get("headline") or "")
        ex.setdefault("description", raw.get("description") or "")
        ex.setdefault("cta_button", raw.get("cta_button") or "Learn More")

    return top


def _format_few_shot_block(examples: list[dict[str, Any]]) -> str:
    """Format top-scoring competitor ads as few-shot examples in the prompt."""
    lines = [
        "## Few-shot examples",
        "Study these top-scoring competitor ads. Learn the hook patterns. Do NOT copy verbatim — write original Varsity Tutors copy.",
        "",
    ]
    for i, ex in enumerate(examples, 1):
        score = ex.get("aggregate_score", 0)
        lines.append(f"### Example {i}  (score: {score:.2f}/10)")
        lines.append(f'Primary text: "{ex.get("primary_text", "")}"')
        if ex.get("headline"):
            lines.append(f'Headline: "{ex["headline"]}"')
        if ex.get("description"):
            lines.append(f'Description: "{ex["description"]}"')
        lines.append(f'CTA: {ex.get("cta_button", "Learn More")}')
        lines.append("")
    return "\n".join(lines)


def _build_generation_prompt(brief: dict[str, Any], few_shot_block: str, variation_hint: str = "") -> str:
    """Build Claude prompt for a single ad generation."""
    goal = brief["goal"]
    cta = brief["cta"]

    return f"""You are a world-class direct-response copywriter for Varsity Tutors, a premium SAT/ACT prep brand.

## Brand voice (MUST follow)
- Empowering, knowledgeable, approachable, results-focused
- Lead with OUTCOMES not features
- Use specific numbers: "200+ point improvement" not "better scores"
- Testimonial and story hooks outperform feature lists — bias toward these
- First line of primary_text = the hook; make it impossible to scroll past
- Confident but never arrogant; speak to the parent/student's real anxiety

{few_shot_block}
## Hook patterns to use (rotate across ads — do NOT repeat the same structure)
1. Specific quantified outcome: "Her SAT jumped 360 points in 6 weeks"
2. Surprising stat: "9/10 Varsity Tutors students improve 150+ points"
3. Direct anxious-parent address: "Still worried the SAT will derail college plans?"
4. Bold guarantee: "Guaranteed 200-point improvement — or your money back"
5. Transformation story opener: "Mia bombed the SAT with a 1080. Six weeks later: 1340."
6. Rhetorical question that hits the pain: "Is your teen ready for their SAT next month?"
7. Credibility flash: "Expert tutors. Personalized plan. Real results — guaranteed."

## Your brief
Audience: {brief['audience']}
Campaign goal: {goal}
Tone: {brief['tone']}
{f"Variation focus: {variation_hint}" if variation_hint else ""}

## Ad anatomy requirements
- primary_text: First sentence is the hook (≤125 chars). Full copy 150-280 chars. Conversational, no bullet lists.
- headline: 5-8 words. Benefit-driven. Complements but does NOT duplicate primary_text hook.
- description: 20-30 words. Reinforces headline. Mobile may truncate after ~30 chars so front-load.
- cta_button: "{cta}"

## Output format
Return ONLY a valid JSON object. No preamble, no markdown fences, no explanation.
{{
  "primary_text": "...",
  "headline": "...",
  "description": "...",
  "cta_button": "{cta}"
}}"""


# Variation hints to ensure 10 ads per brief are meaningfully diverse
_VARIATION_HINTS = [
    "Lead with a specific student success story (name, score delta)",
    "Lead with a stat or proof point (number of students, improvement percentage)",
    "Lead with parental anxiety — address the fear directly then pivot to solution",
    "Lead with urgency around test date or college application deadline",
    "Lead with the guarantee or risk-reversal",
    "Lead with social proof (thousands of families, tutor expertise)",
    "Lead with a question that mirrors the reader's internal monologue",
    "Lead with a transformation narrative (before → after)",
    "Lead with speed/efficiency angle (results in X weeks, personalized plan)",
    "Lead with credibility and trust signals (expert tutors, proven curriculum)",
]


def _extract_json(raw: str) -> str:
    """Strip markdown fences and extract the first {...} block."""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.splitlines()
        inner: list[str] = []
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

    start = text.find("{")
    if start == -1:
        return text

    depth = 0
    for i, ch in enumerate(text[start:], start=start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : i + 1]
    return text[start:]


async def _generate_one(
    client: AsyncAnthropic,
    prompt: str,
    brief_id: str,
    ad_index: int,
) -> dict[str, Any]:
    """Call Claude and parse a single ad JSON response."""
    msg = await client.messages.create(
        model=MODEL,
        max_tokens=600,
        temperature=TEMPERATURE,
        messages=[{"role": "user", "content": prompt}],
    )
    raw = msg.content[0].text if msg.content else ""
    json_str = _extract_json(raw)

    try:
        data = json.loads(json_str)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Claude returned unparseable JSON: {exc}\nRaw: {raw[:300]}") from exc

    cta = str(data.get("cta_button", "Learn More")).strip()
    if cta not in VALID_CTA_BUTTONS:
        cta = "Learn More"

    primary = str(data.get("primary_text", "")).strip()
    headline = str(data.get("headline", "")).strip()
    description = str(data.get("description", "")).strip()

    if not primary or not headline:
        raise ValueError(f"Missing required fields — primary: {bool(primary)}, headline: {bool(headline)}")

    return {
        "ad_id": str(uuid.uuid4()),
        "brief_id": brief_id,
        "ad_index": ad_index,
        "primary_text": primary,
        "headline": headline,
        "description": description,
        "cta_button": cta,
        "model": MODEL,
        "temperature": TEMPERATURE,
        "generated_at": datetime.now(timezone.utc).isoformat(),
    }


async def _generate_brief(
    client: AsyncAnthropic,
    brief: dict[str, Any],
    few_shot_block: str,
) -> list[dict[str, Any]]:
    """Generate ADS_PER_BRIEF ads for one brief, each with a distinct variation hint."""
    ads: list[dict[str, Any]] = []
    brief_id = brief["id"]

    for i in range(ADS_PER_BRIEF):
        variation_hint = _VARIATION_HINTS[i % len(_VARIATION_HINTS)]
        prompt = _build_generation_prompt(brief, few_shot_block, variation_hint=variation_hint)

        logger.info("Generating ad %d/%d for %s", i + 1, ADS_PER_BRIEF, brief_id)
        print(f"  [{i + 1}/{ADS_PER_BRIEF}] {brief_id}  ({variation_hint[:50]}...)")

        max_retries = 3
        for attempt in range(1, max_retries + 1):
            try:
                ad = await _generate_one(client, prompt, brief_id, i + 1)
                ads.append(ad)
                print(f"         OK  headline: {ad['headline'][:65]}")
                break
            except Exception as exc:
                logger.warning("Attempt %d failed for %s ad %d: %s", attempt, brief_id, i + 1, exc)
                if attempt == max_retries:
                    print(f"         SKIP after {max_retries} attempts: {exc}")
                else:
                    await asyncio.sleep(2 ** attempt)

    return ads


async def _run_generation() -> list[dict[str, Any]]:
    """Orchestrate generation across all briefs."""
    from src.config.settings import get_settings

    settings = get_settings()
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)

    print(f"Loading top few-shot examples from {SCORED_ADS_PATH} ...")
    examples = _load_top_examples(n=3)
    scores = [e["aggregate_score"] for e in examples]
    print(f"Top 3 examples  scores={scores}")
    for ex in examples:
        print(f"  [{ex['aggregate_score']:.2f}] {ex.get('primary_text', '')[:80]}")

    few_shot_block = _format_few_shot_block(examples)

    all_ads: list[dict[str, Any]] = []

    for brief in BRIEFS:
        print(f"\n{'─'*60}")
        print(f"Brief: {brief['id']}")
        print(f"  Audience : {brief['audience']}")
        print(f"  Goal     : {brief['goal']}  |  Tone: {brief['tone']}")
        print(f"{'─'*60}")

        ads = await _generate_brief(client, brief, few_shot_block)
        all_ads.extend(ads)
        print(f"  -> {len(ads)}/{ADS_PER_BRIEF} ads generated for {brief['id']}")

    return all_ads


def run_generate_ads() -> int:
    """Entry point called from main.py. Returns 0 on success, 1 on failure."""
    if not SCORED_ADS_PATH.exists():
        print(f"ERROR: {SCORED_ADS_PATH} not found. Run 'python main.py score-competitors' first.")
        return 1

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    all_ads = asyncio.run(_run_generation())

    OUTPUT_PATH.write_text(
        json.dumps(all_ads, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )

    print(f"\n{'='*60}")
    print(f"Generation complete — {len(all_ads)} ads saved to {OUTPUT_PATH}")
    print("By brief:")

    by_brief: dict[str, list[dict]] = {}
    for ad in all_ads:
        by_brief.setdefault(ad["brief_id"], []).append(ad)
    for brief_id, ads in by_brief.items():
        print(f"  {brief_id}: {len(ads)} ads")

    target = len(BRIEFS) * ADS_PER_BRIEF
    if len(all_ads) < 50:
        print(f"\nWARNING: Only {len(all_ads)} ads generated (target: {target}+). Check logs above.")
        return 1

    print(f"\n{len(all_ads)} valid records written to {OUTPUT_PATH}")
    return 0
