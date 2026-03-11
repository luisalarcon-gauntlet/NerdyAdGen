"""Feedback loop: score → filter → regenerate → track → repeat.

Runs MIN_CYCLES (3) to MAX_CYCLES (6) over data/generated/ads_raw.json.
Stops early when >80% of ads are publishable (after completing min cycles).

Outputs:
  data/evaluated/generated_ads_scored.json  — best scored version of all ads
  data/output/publishable_ads.json          — ads with aggregate_score >= 7.0
  data/output/iteration_log.json            — per-cycle metrics
"""
import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from anthropic import AsyncAnthropic

from src.config.settings import get_settings
from src.evaluate.judge import ClaudeJudge
from src.models.ad import Ad, AdStatus
from src.models.evaluation import EvaluationResult
from src.models.weights import (
    DimensionWeights,
    KnockoutThresholds,
    WeightProfile,
    VarsityTutorsSATProfiles,
)

logger = logging.getLogger(__name__)

# ── paths ──────────────────────────────────────────────────────────────────
GENERATED_ADS_PATH = Path("data/generated/ads_raw.json")
SCORED_PATH = Path("data/evaluated/generated_ads_scored.json")
PUBLISHABLE_PATH = Path("data/output/publishable_ads.json")
ITERATION_LOG_PATH = Path("data/output/iteration_log.json")

# ── knobs ──────────────────────────────────────────────────────────────────
PUBLISHABLE_THRESHOLD = 7.0
MIN_CYCLES = 3
MAX_CYCLES = 6
EARLY_STOP_RATE = 0.80
MAX_REGEN_ATTEMPTS = 3
REGEN_MODEL = "claude-sonnet-4-6"
REGEN_TEMPERATURE = 0.7

DIMENSIONS = [
    "clarity",
    "value_proposition",
    "cta",
    "brand_voice",
    "emotional_resonance",
]

# ── brief metadata (mirrors generate_ads.py) ───────────────────────────────
_BRIEF_META: dict[str, dict[str, str]] = {
    "brief-parents-awareness": {
        "audience": "parents of high school juniors anxious about college admissions",
        "goal": "awareness",
        "tone": "empowering, reassuring, outcome-focused",
        "cta": "Learn More",
    },
    "brief-parents-conversion": {
        "audience": "parents actively comparing SAT prep options and weighing value",
        "goal": "conversion",
        "tone": "confident, credibility-forward, results-driven",
        "cta": "Sign Up",
    },
    "brief-students-awareness": {
        "audience": "high school students stressed about an upcoming SAT",
        "goal": "awareness",
        "tone": "energetic, empathetic, motivational",
        "cta": "Learn More",
    },
    "brief-students-conversion": {
        "audience": "high school students who want a guaranteed score improvement",
        "goal": "conversion",
        "tone": "direct, specific, results-focused",
        "cta": "Sign Up",
    },
    "brief-both-urgency": {
        "audience": "students and parents with a SAT test date within 8 weeks",
        "goal": "conversion",
        "tone": "urgent, action-oriented, reassuring that there is still time",
        "cta": "Sign Up",
    },
}

_DEFAULT_BRIEF_META: dict[str, str] = {
    "audience": "SAT prep students and parents",
    "goal": "conversion",
    "tone": "empowering, results-focused",
    "cta": "Learn More",
}

# ── weight profile ─────────────────────────────────────────────────────────
_FEEDBACK_PROFILE = WeightProfile(
    profile_id="feedback_loop",
    audience="general",
    campaign_goal="conversion",
    quality_threshold=PUBLISHABLE_THRESHOLD,
    weights=DimensionWeights(
        clarity=0.20,
        value_proposition=0.30,
        cta=0.20,
        brand_voice=0.15,
        emotional_resonance=0.15,
    ),
    knockout_thresholds=KnockoutThresholds(),
)

VALID_CTA_BUTTONS = [
    "Learn More", "Sign Up", "Get Started", "Start Free Trial",
    "Book Now", "Contact Us", "Apply Now", "Download",
]


# ── helpers ────────────────────────────────────────────────────────────────

def _extract_json(raw: str) -> str:
    """Strip markdown fences and extract first {...} block."""
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
                return text[start: i + 1]
    return text[start:]


def _raw_to_ad(raw: dict[str, Any]) -> Ad:
    """Convert a raw or scored ad record to an Ad model for ClaudeJudge."""
    return Ad(
        id=raw.get("ad_id", str(uuid.uuid4())),
        brief_id=raw.get("brief_id", "unknown"),
        status=AdStatus.DRAFT,
        primary_text=raw.get("primary_text") or "",
        headline=raw.get("headline") or "",
        description=raw.get("description") or "",
        cta_button=raw.get("cta_button") or "Learn More",
    )


def _to_scored_record(raw: dict[str, Any], result: EvaluationResult) -> dict[str, Any]:
    """Map EvaluationResult + raw ad dict to the output scored schema."""
    scores_map = {d.dimension: d for d in result.dimension_scores}

    def _dim(name: str) -> dict[str, Any]:
        d = scores_map.get(name)
        if d:
            return {"score": d.score, "rationale": d.rationale}
        return {"score": 0.0, "rationale": "dimension missing"}

    return {
        "ad_id": raw.get("ad_id", ""),
        "brief_id": raw.get("brief_id", ""),
        "primary_text": raw.get("primary_text", ""),
        "headline": raw.get("headline", ""),
        "description": raw.get("description", ""),
        "cta_button": raw.get("cta_button", ""),
        "scores": {dim: _dim(dim) for dim in DIMENSIONS},
        "aggregate_score": round(result.weighted_score, 2),
        "publishable": result.weighted_score >= PUBLISHABLE_THRESHOLD,
        "regen_count": raw.get("regen_count", 0),
        "regen_history": raw.get("regen_history", []),
    }


def _worst_dim(rec: dict[str, Any]) -> str:
    """Return the name of the lowest-scoring dimension in a scored record."""
    scores = rec.get("scores", {})
    return min(DIMENSIONS, key=lambda d: scores.get(d, {}).get("score", 10.0))


def _avg_score(records: list[dict[str, Any]]) -> float:
    valid = [
        r["aggregate_score"]
        for r in records
        if "aggregate_score" in r and "error" not in r
    ]
    return round(sum(valid) / len(valid), 3) if valid else 0.0


def _brief_avg_scores(records: list[dict[str, Any]]) -> dict[str, float]:
    by_brief: dict[str, list[float]] = {}
    for r in records:
        if "aggregate_score" in r and "error" not in r:
            bid = r.get("brief_id", "unknown")
            by_brief.setdefault(bid, []).append(r["aggregate_score"])
    return {bid: round(sum(s) / len(s), 3) for bid, s in by_brief.items()}


def _most_improved_dimensions(
    before_map: dict[str, dict[str, Any]],
    after: list[dict[str, Any]],
) -> list[str]:
    """Return top-2 dimensions by total score gain across all regenerated ads."""
    improvements: dict[str, float] = {dim: 0.0 for dim in DIMENSIONS}
    for rec in after:
        ad_id = rec.get("ad_id", "")
        prev = before_map.get(ad_id)
        if not prev:
            continue
        for dim in DIMENSIONS:
            before_score = prev.get("scores", {}).get(dim, {}).get("score", 0.0)
            after_score = rec.get("scores", {}).get(dim, {}).get("score", 0.0)
            improvements[dim] += max(0.0, after_score - before_score)
    sorted_dims = sorted(DIMENSIONS, key=lambda d: improvements[d], reverse=True)
    return [d for d in sorted_dims[:2] if improvements[d] > 0.0]


def _build_regen_prompt(
    rec: dict[str, Any],
    worst_dim: str,
    worst_score: float,
    worst_rationale: str,
    brief_meta: dict[str, str],
) -> str:
    scores = rec.get("scores", {})
    score_lines = "\n".join(
        f"  {dim}: {scores.get(dim, {}).get('score', 0.0):.1f}/10 — "
        f"{scores.get(dim, {}).get('rationale', '')[:120]}"
        for dim in DIMENSIONS
    )
    return f"""You are improving a Facebook/Instagram ad for Varsity Tutors SAT prep.

## Original ad (do NOT copy verbatim — rewrite to fix the target dimension)
Primary text: {rec.get("primary_text", "")}
Headline: {rec.get("headline", "")}
Description: {rec.get("description", "")}
CTA: {rec.get("cta_button", "Learn More")}

## Current dimension scores
{score_lines}

## Target dimension to fix: {worst_dim}
Score: {worst_score:.1f}/10
Issue: {worst_rationale}

## Brief context
Audience: {brief_meta.get("audience", "")}
Goal: {brief_meta.get("goal", "")}
Tone: {brief_meta.get("tone", "")}

## Rewrite instructions
- Fix ONLY the {worst_dim} dimension. Preserve all dimensions that scored >= 7.0.
- Do NOT sacrifice clarity, CTA strength, or brand voice to fix one weak area.
- primary_text: hook in first sentence (≤125 chars), full copy 150-280 chars.
- headline: 5-8 words, benefit-driven.
- description: 20-30 words, front-loaded.
- cta_button must be one of: {", ".join(VALID_CTA_BUTTONS)}

Return ONLY valid JSON, no preamble:
{{"primary_text": "...", "headline": "...", "description": "...", "cta_button": "..."}}"""


# ── core async functions ────────────────────────────────────────────────────

async def _score_all_ads(
    ads: list[dict[str, Any]],
    judge: ClaudeJudge,
    profile: WeightProfile,
) -> list[dict[str, Any]]:
    """Score every ad via ClaudeJudge. Returns list of scored records."""
    scored: list[dict[str, Any]] = []
    total = len(ads)

    for i, raw in enumerate(ads, 1):
        ad_id = raw.get("ad_id", "?")
        brief_id = raw.get("brief_id", "?")
        print(f"  [{i:>3}/{total}] {ad_id[:12]}... brief={brief_id}", end="", flush=True)

        try:
            ad = _raw_to_ad(raw)
            result = await judge.evaluate(ad, profile)
            rec = _to_scored_record(raw, result)
            scored.append(rec)
            marker = "✓" if rec["publishable"] else "✗"
            print(f"  {marker}  score={rec['aggregate_score']:.2f}  worst={_worst_dim(rec)}")
        except Exception as exc:
            logger.error("Scoring failed for %s: %s", ad_id, exc)
            print(f"  ERROR: {exc}")
            scored.append({
                **raw,
                "aggregate_score": 0.0,
                "publishable": False,
                "scores": {},
                "regen_count": raw.get("regen_count", 0),
                "regen_history": raw.get("regen_history", []),
                "error": str(exc),
            })

    return scored


async def _regenerate_one(
    client: AsyncAnthropic,
    rec: dict[str, Any],
    judge: ClaudeJudge,
    profile: WeightProfile,
    attempt_num: int,
) -> dict[str, Any]:
    """
    Generate a targeted rewrite for a failing ad, score it, and return
    whichever version (original or regenerated) has the higher aggregate score.
    """
    worst_dim = _worst_dim(rec)
    worst_score = rec.get("scores", {}).get(worst_dim, {}).get("score", 0.0)
    worst_rationale = rec.get("scores", {}).get(worst_dim, {}).get("rationale", "")
    brief_meta = _BRIEF_META.get(rec.get("brief_id", ""), _DEFAULT_BRIEF_META)

    prompt = _build_regen_prompt(rec, worst_dim, worst_score, worst_rationale, brief_meta)

    msg = await client.messages.create(
        model=REGEN_MODEL,
        max_tokens=600,
        temperature=REGEN_TEMPERATURE,
        messages=[{"role": "user", "content": prompt}],
    )
    raw_text = msg.content[0].text if msg.content else ""
    if not raw_text:
        raise ValueError("Empty response from Claude during regeneration")

    json_str = _extract_json(raw_text)
    data = json.loads(json_str)

    cta = str(data.get("cta_button", rec.get("cta_button", "Learn More"))).strip()
    if cta not in VALID_CTA_BUTTONS:
        cta = rec.get("cta_button", "Learn More")

    regen_raw = {
        "ad_id": rec["ad_id"],
        "brief_id": rec.get("brief_id", ""),
        "primary_text": str(data.get("primary_text", rec["primary_text"])).strip(),
        "headline": str(data.get("headline", rec["headline"])).strip(),
        "description": str(data.get("description", rec["description"])).strip(),
        "cta_button": cta,
        "regen_count": rec.get("regen_count", 0) + 1,
        "regen_history": rec.get("regen_history", []),
    }

    # Score the regenerated version
    ad_obj = _raw_to_ad(regen_raw)
    new_result = await judge.evaluate(ad_obj, profile)
    new_rec = _to_scored_record(regen_raw, new_result)

    history_entry: dict[str, Any] = {
        "attempt": attempt_num,
        "targeted_dimension": worst_dim,
        "score_before": rec.get("aggregate_score", 0.0),
        "score_after": new_rec["aggregate_score"],
        "improved": new_rec["aggregate_score"] >= rec.get("aggregate_score", 0.0),
    }

    # Keep the better version
    original_score = rec.get("aggregate_score", 0.0)
    if new_rec["aggregate_score"] >= original_score:
        new_rec["regen_history"] = rec.get("regen_history", []) + [history_entry]
        new_rec["regen_count"] = regen_raw["regen_count"]
        return new_rec
    else:
        kept = dict(rec)
        kept["regen_count"] = regen_raw["regen_count"]
        kept["regen_history"] = rec.get("regen_history", []) + [history_entry]
        return kept


async def _run_cycle(
    cycle: int,
    current_ads: list[dict[str, Any]],
    judge: ClaudeJudge,
    client: AsyncAnthropic,
    profile: WeightProfile,
    prev_avg_score: float,
) -> tuple[list[dict[str, Any]], dict[str, Any], float]:
    """
    One full cycle: SCORE → FILTER → REGENERATE → metrics.
    Returns (updated_scored_ads, cycle_metrics, avg_score_after_regen).
    """
    print(f"\n{'═' * 70}")
    print(f"  CYCLE {cycle}  —  scoring {len(current_ads)} ads")
    print(f"{'═' * 70}")

    # ── SCORE ──────────────────────────────────────────────────────────────
    scored = await _score_all_ads(current_ads, judge, profile)
    before_map = {r["ad_id"]: r for r in scored if "ad_id" in r}

    publishable_before = [r for r in scored if r.get("publishable", False) and "error" not in r]
    failing = [r for r in scored if not r.get("publishable", False) and "error" not in r]
    errors = [r for r in scored if "error" in r]

    avg_before = _avg_score(scored)
    brief_scores_before = _brief_avg_scores(scored)

    print(f"\n  ── FILTER ──")
    print(f"     Publishable : {len(publishable_before)}/{len(scored)}")
    print(f"     Needs work  : {len(failing)}/{len(scored)}")
    print(f"     Errors      : {len(errors)}")
    print(f"     Avg score   : {avg_before:.3f}")

    # ── REGENERATE ─────────────────────────────────────────────────────────
    print(f"\n  ── REGENERATE ──")
    updated: list[dict[str, Any]] = list(publishable_before)
    failed_ads: list[str] = []

    for rec in failing:
        ad_id = rec.get("ad_id", "?")
        regen_count = rec.get("regen_count", 0)

        if regen_count >= MAX_REGEN_ATTEMPTS:
            logger.info("Ad %s maxed regeneration (%d)", ad_id, regen_count)
            failed_ads.append(ad_id)
            updated.append(rec)
            print(f"     {ad_id[:12]}  MAXED ({regen_count} attempts, score={rec.get('aggregate_score', 0):.2f})")
            continue

        worst = _worst_dim(rec)
        before_score = rec.get("aggregate_score", 0.0)
        print(
            f"     {ad_id[:12]}  regen#{regen_count + 1}  "
            f"score={before_score:.2f}  fixing={worst}",
            end="",
            flush=True,
        )

        try:
            best_rec = await _regenerate_one(client, rec, judge, profile, attempt_num=regen_count + 1)
            after_score = best_rec.get("aggregate_score", 0.0)
            delta = after_score - before_score
            arrow = "↑" if delta > 0 else ("→" if delta == 0 else "↓")
            print(f"  {arrow}  {after_score:.2f}  (Δ{delta:+.2f})")
            updated.append(best_rec)
        except Exception as exc:
            logger.error("Regeneration failed for %s: %s", ad_id, exc)
            print(f"  ERROR: {exc}")
            updated.append(rec)

    updated.extend(errors)

    # ── METRICS ────────────────────────────────────────────────────────────
    publishable_after = [r for r in updated if r.get("publishable", False) and "error" not in r]
    avg_after = _avg_score(updated)
    brief_scores_after = _brief_avg_scores(updated)
    pub_rate = len(publishable_after) / max(len(updated), 1)

    # Quality ratchet
    ratchet_ok = True
    ratchet_flag = None
    if cycle > 1 and avg_after < prev_avg_score:
        ratchet_ok = False
        ratchet_flag = (
            f"Cycle {cycle} avg {avg_after:.3f} < cycle {cycle - 1} avg {prev_avg_score:.3f} "
            f"(Δ{avg_after - prev_avg_score:+.3f})"
        )
        logger.warning("QUALITY RATCHET: %s", ratchet_flag)
        print(f"\n  ⚠ QUALITY RATCHET FLAG: {ratchet_flag}")

    improved_dims = _most_improved_dimensions(before_map, updated)

    print(f"\n  ── CYCLE {cycle} RESULT ──")
    print(f"     Passing before regen : {len(publishable_before)}/{len(scored)}")
    print(f"     Passing after  regen : {len(publishable_after)}/{len(updated)}  ({pub_rate:.1%})")
    print(f"     Avg before           : {avg_before:.3f}")
    print(f"     Avg after            : {avg_after:.3f}  (Δ{avg_after - avg_before:+.3f})")
    if improved_dims:
        print(f"     Most improved dims   : {', '.join(improved_dims)}")
    if failed_ads:
        print(f"     Failed (maxed out)   : {len(failed_ads)} ads")

    metrics: dict[str, Any] = {
        "cycle": cycle,
        "total_ads": len(updated),
        "passing_before_regen": len(publishable_before),
        "passing_after_regen": len(publishable_after),
        "avg_score_before_regen": avg_before,
        "avg_score_after_regen": avg_after,
        "publishable_rate_after": round(pub_rate, 4),
        "threshold": PUBLISHABLE_THRESHOLD,
        "quality_ratchet_ok": ratchet_ok,
        "ratchet_flag": ratchet_flag,
        "dimensions_most_improved": improved_dims,
        "brief_avg_scores": {
            bid: {
                "before": brief_scores_before.get(bid, 0.0),
                "after": brief_scores_after.get(bid, 0.0),
            }
            for bid in sorted(
                set(list(brief_scores_before.keys()) + list(brief_scores_after.keys()))
            )
        },
        "failed_ads": failed_ads,
        "error_ads": [r.get("ad_id", "") for r in errors],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    return updated, metrics, avg_after


async def _run_all_cycles(
    raw_ads: list[dict[str, Any]],
    client: AsyncAnthropic,
    judge: ClaudeJudge,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Orchestrate MIN_CYCLES..MAX_CYCLES iterations. Returns (final_ads, log)."""
    current_ads: list[dict[str, Any]] = raw_ads
    iteration_log: list[dict[str, Any]] = []
    prev_avg = 0.0
    final_scored: list[dict[str, Any]] = []

    for cycle in range(1, MAX_CYCLES + 1):
        updated, metrics, avg_after = await _run_cycle(
            cycle, current_ads, judge, client, _FEEDBACK_PROFILE, prev_avg
        )

        iteration_log.append(metrics)
        final_scored = updated

        # Persist after every cycle so a crash doesn't lose data
        SCORED_PATH.write_text(
            json.dumps(updated, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        ITERATION_LOG_PATH.write_text(
            json.dumps(iteration_log, indent=2, ensure_ascii=False), encoding="utf-8"
        )

        prev_avg = avg_after
        current_ads = updated

        pub_rate = metrics["publishable_rate_after"]
        if cycle >= MIN_CYCLES and pub_rate >= EARLY_STOP_RATE:
            print(f"\n  Early stop after cycle {cycle}: {pub_rate:.1%} >= {EARLY_STOP_RATE:.0%} target")
            break

    return final_scored, iteration_log


# ── summary ────────────────────────────────────────────────────────────────

def _print_summary(
    iteration_log: list[dict[str, Any]],
    final_scored: list[dict[str, Any]],
    publishable: list[dict[str, Any]],
) -> None:
    total = len(final_scored)
    passing = len(publishable)
    rate = passing / max(total, 1)

    first = iteration_log[0] if iteration_log else {}
    last = iteration_log[-1] if iteration_log else {}

    avg_start = first.get("avg_score_before_regen", 0.0)
    avg_end = last.get("avg_score_after_regen", 0.0)
    delta = avg_end - avg_start

    ratchet_flags = [
        m.get("ratchet_flag")
        for m in iteration_log
        if not m.get("quality_ratchet_ok", True)
    ]

    print(f"\n{'═' * 70}")
    print("  FEEDBACK LOOP SUMMARY")
    print(f"{'═' * 70}")
    print(f"  Total ads          : {total}")
    print(f"  Passing rate       : {passing}/{total}  ({rate:.1%})")
    print(f"  Avg score (start)  : {avg_start:.3f}")
    print(f"  Avg score (final)  : {avg_end:.3f}  (Δ{delta:+.3f})")
    print(f"  Cycles completed   : {len(iteration_log)}")
    print()
    print("  Per-cycle progression:")
    for m in iteration_log:
        c = m["cycle"]
        before = m["avg_score_before_regen"]
        after = m["avg_score_after_regen"]
        pb = m["passing_before_regen"]
        pa = m["passing_after_regen"]
        tot = m["total_ads"]
        print(
            f"    Cycle {c}: avg {before:.2f}→{after:.2f}  "
            f"passing {pb}/{tot}→{pa}/{tot}"
        )

    if ratchet_flags:
        print()
        print("  ⚠ Quality ratchet flags:")
        for flag in ratchet_flags:
            print(f"    {flag}")

    print()
    print(f"  Outputs written:")
    print(f"    {SCORED_PATH}")
    print(f"    {PUBLISHABLE_PATH}")
    print(f"    {ITERATION_LOG_PATH}")
    print(f"    {REPORT_PATH}  ← open in browser")
    print(f"{'═' * 70}")


# ── report generator ───────────────────────────────────────────────────────

REPORT_PATH = Path("data/output/report.html")


def generate_report() -> Path:
    """Generate a self-contained HTML results dashboard at data/output/report.html.

    Reads publishable_ads.json and iteration_log.json.
    Writes report.html — no server needed, opens in any browser.
    """
    from collections import Counter

    ads: list[dict[str, Any]] = (
        json.loads(PUBLISHABLE_PATH.read_text(encoding="utf-8"))
        if PUBLISHABLE_PATH.exists()
        else []
    )
    log: list[dict[str, Any]] = (
        json.loads(ITERATION_LOG_PATH.read_text(encoding="utf-8"))
        if ITERATION_LOG_PATH.exists()
        else []
    )

    total = len(ads)
    first_cycle = log[0] if log else {}
    last_cycle = log[-1] if log else {}
    num_cycles = len(log)

    initial_pct = round(
        first_cycle.get("passing_before_regen", 0)
        / max(first_cycle.get("total_ads", 1), 1)
        * 100
    )
    final_pct = round(
        last_cycle.get("passing_after_regen", total)
        / max(last_cycle.get("total_ads", 1), 1)
        * 100
    )

    _brief_labels: dict[str, str] = {
        "brief-parents-awareness": "Parents · Awareness",
        "brief-parents-conversion": "Parents · Conversion",
        "brief-students-awareness": "Students · Awareness",
        "brief-students-conversion": "Students · Conversion",
        "brief-both-urgency": "Both · Urgency",
    }
    _dim_labels: dict[str, str] = {
        "clarity": "Clarity",
        "value_proposition": "Value Prop",
        "cta": "CTA",
        "brand_voice": "Brand Voice",
        "emotional_resonance": "Emotional Resonance",
    }

    top_improved = [
        c["dimensions_most_improved"][0]
        for c in log
        if c.get("dimensions_most_improved")
    ]
    weakest_dim = Counter(top_improved).most_common(1)[0][0] if top_improved else "cta"
    weakest_dim_label = _dim_labels.get(weakest_dim, weakest_dim.replace("_", " ").title())

    top3 = sorted(ads, key=lambda a: a.get("aggregate_score", 0), reverse=True)[:3]

    def _esc(s: str) -> str:
        return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def _score_color(score: float) -> str:
        return "#4ade80" if score >= 8.0 else "#fbbf24" if score >= 7.0 else "#f87171"

    # ── Static HTML fragments ───────────────────────────────────────────────
    top_cards_html = "\n".join(
        '<div class="top-card">'
        f'<div class="top-card-label">{_brief_labels.get(ad.get("brief_id", ""), ad.get("brief_id", ""))}</div>'
        f'<div class="top-card-primary">{_esc(ad.get("primary_text", ""))}</div>'
        f'<div class="top-card-headline">{_esc(ad.get("headline", ""))}</div>'
        f'<div class="top-card-score" style="color:{_score_color(ad.get("aggregate_score", 0))}">'
        f'{ad.get("aggregate_score", 0):.1f}</div>'
        "</div>"
        for ad in top3
    )

    cycle_bars_html = "\n".join(
        f'<div class="cycle-row">'
        f'<span class="cycle-label">Cycle {c["cycle"]}</span>'
        f'<div class="bar-group">'
        f'<div class="bar-track"><div class="bar-fill before" style="width:{round(c.get("passing_before_regen",0)/max(c.get("total_ads",1),1)*100)}%"></div>'
        f'<span class="bar-pct">{round(c.get("passing_before_regen",0)/max(c.get("total_ads",1),1)*100)}%</span></div>'
        f'<div class="bar-track"><div class="bar-fill after" style="width:{round(c.get("passing_after_regen",0)/max(c.get("total_ads",1),1)*100)}%"></div>'
        f'<span class="bar-pct">{round(c.get("passing_after_regen",0)/max(c.get("total_ads",1),1)*100)}%</span></div>'
        "</div></div>"
        for c in log
    )

    ads_json_str = json.dumps(ads, ensure_ascii=False)
    brief_labels_json_str = json.dumps(_brief_labels, ensure_ascii=False)

    # ── CSS ────────────────────────────────────────────────────────────────
    css = """\
:root {
  --bg:#08080f; --card:#171724; --border:rgba(255,255,255,.07);
  --text:#e8e8f4; --muted:#6868a0; --accent:#7c6ff7;
  --green:#4ade80; --yellow:#fbbf24; --red:#f87171;
}
*,*::before,*::after { box-sizing:border-box; margin:0; padding:0; }
body {
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',system-ui,sans-serif;
  background:var(--bg); color:var(--text); line-height:1.6;
}
.act { max-width:960px; margin:0 auto; padding:80px 24px; }
.act+.act { border-top:1px solid var(--border); }
.act-label {
  font-size:10px; font-weight:700; letter-spacing:4px;
  text-transform:uppercase; color:var(--muted); margin-bottom:40px;
}
/* ACT 1 */
.headline-main {
  font-size:clamp(1.8rem,4.5vw,3rem); font-weight:800;
  line-height:1.15; letter-spacing:-.03em; margin-bottom:56px;
}
.hl { color:var(--accent); }
.top-cards { display:grid; grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); gap:16px; }
.top-card {
  background:var(--card); border:1px solid var(--border);
  border-radius:14px; padding:24px; display:flex; flex-direction:column; gap:10px;
}
.top-card-label { font-size:10px; font-weight:700; letter-spacing:2.5px; text-transform:uppercase; color:var(--muted); }
.top-card-primary { font-size:13px; line-height:1.65; flex:1; }
.top-card-headline { font-size:15px; font-weight:700; }
.top-card-score { font-size:40px; font-weight:900; letter-spacing:-.04em; margin-top:6px; }
/* ACT 2 */
.learning-statement {
  font-size:clamp(1.1rem,2.5vw,1.6rem); font-weight:600;
  line-height:1.4; max-width:600px; margin-bottom:40px;
}
.before-after { display:flex; align-items:baseline; gap:16px; flex-wrap:wrap; margin-bottom:48px; }
.stat-before { font-size:2rem; font-weight:800; color:var(--muted); letter-spacing:-.03em; }
.stat-arrow { font-size:1.4rem; color:var(--muted); }
.stat-after { font-size:2rem; font-weight:800; color:var(--green); letter-spacing:-.03em; }
.stat-note { font-size:.8rem; color:var(--muted); align-self:flex-end; padding-bottom:5px; }
.bar-legend { display:flex; gap:20px; margin-bottom:14px; }
.legend-item { display:flex; align-items:center; gap:8px; font-size:11px; color:var(--muted); }
.legend-swatch { width:14px; height:6px; border-radius:2px; display:inline-block; }
.legend-swatch.before { background:rgba(255,255,255,.18); }
.legend-swatch.after { background:var(--green); opacity:.8; }
.cycle-bars { display:flex; flex-direction:column; gap:18px; max-width:560px; }
.cycle-row { display:grid; grid-template-columns:58px 1fr; gap:14px; align-items:center; }
.cycle-label { font-size:11px; font-weight:700; color:var(--muted); }
.bar-group { display:flex; flex-direction:column; gap:5px; }
.bar-track {
  height:20px; background:rgba(255,255,255,.04);
  border-radius:4px; position:relative; display:flex; align-items:center;
}
.bar-fill { height:100%; border-radius:4px; }
.bar-fill.before { background:rgba(255,255,255,.18); }
.bar-fill.after { background:var(--green); opacity:.75; }
.bar-pct { position:absolute; right:-36px; font-size:11px; color:var(--muted); }
/* ACT 3 */
.act3-header { margin-bottom:24px; }
.act3-title { font-size:1.4rem; font-weight:800; margin-bottom:4px; }
.act3-sub { font-size:12px; color:var(--muted); }
.filters { display:flex; gap:8px; flex-wrap:wrap; margin-bottom:20px; }
.filter-btn {
  padding:5px 15px; border-radius:20px; border:1px solid var(--border);
  background:transparent; color:var(--muted); font-size:12px; font-weight:600;
  cursor:pointer; transition:all .15s; letter-spacing:.3px;
}
.filter-btn:hover { border-color:var(--accent); color:var(--text); }
.filter-btn.active { background:var(--accent); border-color:var(--accent); color:#fff; }
.ad-list { display:flex; flex-direction:column; gap:8px; }
.ad-item {
  background:var(--card); border:1px solid var(--border);
  border-radius:10px; overflow:hidden; cursor:pointer; transition:border-color .15s;
}
.ad-item:hover { border-color:rgba(124,111,247,.3); }
.ad-item.expanded { border-color:var(--accent); }
.ad-header { display:grid; grid-template-columns:1fr auto; gap:20px; padding:16px 20px; align-items:start; }
.ad-meta { display:flex; align-items:center; gap:10px; flex-wrap:wrap; margin-bottom:6px; }
.ad-brief-label { font-size:10px; font-weight:700; letter-spacing:2px; text-transform:uppercase; color:var(--muted); }
.badge-regen {
  font-size:9px; font-weight:700; text-transform:uppercase; letter-spacing:1px;
  color:var(--accent); border:1px solid var(--accent); border-radius:10px; padding:1px 7px;
}
.ad-headline { font-size:14px; font-weight:700; margin-bottom:4px; }
.ad-primary { font-size:12px; color:var(--muted); line-height:1.55; }
.ad-score { font-size:26px; font-weight:900; letter-spacing:-.03em; white-space:nowrap; }
.ad-expand { padding:16px 20px; border-top:1px solid var(--border); display:none; }
.ad-item.expanded .ad-expand { display:block; }
.dim-grid { display:flex; flex-direction:column; gap:10px; }
.dim-row { display:grid; grid-template-columns:130px 1fr 36px; gap:12px; align-items:center; }
.dim-name { font-size:11px; color:var(--muted); font-weight:600; }
.dim-bar-track { height:5px; background:rgba(255,255,255,.06); border-radius:3px; }
.dim-bar-fill { height:100%; border-radius:3px; }
.dim-score { font-size:11px; color:var(--muted); text-align:right; font-weight:600; }
footer {
  max-width:960px; margin:0 auto; padding:32px 24px;
  border-top:1px solid var(--border); font-size:11px; color:var(--muted);
}
@media(max-width:600px) {
  .top-cards { grid-template-columns:1fr; }
  .dim-row { grid-template-columns:100px 1fr 30px; }
  .act { padding:48px 16px; }
}"""

    # ── JS ─────────────────────────────────────────────────────────────────
    js_code = """\
const DIMS = ['clarity','value_proposition','cta','brand_voice','emotional_resonance'];
const DIM_LABELS = {
  clarity:'Clarity', value_proposition:'Value Prop', cta:'CTA',
  brand_voice:'Brand Voice', emotional_resonance:'Emotional Resonance'
};
let activeFilter = 'all';

function scoreColor(s) {
  return s >= 8 ? '#4ade80' : s >= 7 ? '#fbbf24' : '#f87171';
}
function esc(str) {
  return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;')
                    .replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function renderFilters() {
  const briefs = [...new Set(ADS.map(a => a.brief_id))].sort();
  const container = document.getElementById('filters');
  container.innerHTML = [
    `<button class="filter-btn active" data-filter="all">All</button>`,
    ...briefs.map(b => `<button class="filter-btn" data-filter="${b}">${esc(BRIEF_LABELS[b]||b)}</button>`)
  ].join('');
  container.addEventListener('click', e => {
    const btn = e.target.closest('.filter-btn');
    if (!btn) return;
    document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
    btn.classList.add('active');
    activeFilter = btn.dataset.filter;
    renderList();
  });
}

function renderList() {
  const list = activeFilter === 'all' ? ADS : ADS.filter(a => a.brief_id === activeFilter);
  const sorted = [...list].sort((a,b) => b.aggregate_score - a.aggregate_score);
  document.getElementById('ad-list').innerHTML = sorted.map(ad => {
    const s = ad.aggregate_score;
    const c = scoreColor(s);
    const label = esc(BRIEF_LABELS[ad.brief_id] || ad.brief_id);
    const regenBadge = ad.regen_count > 0 ? '<span class="badge-regen">Regenerated</span>' : '';
    const dimRows = DIMS.map(d => {
      const ds = (ad.scores[d] || {score:0}).score;
      const dc = scoreColor(ds);
      return `<div class="dim-row">
        <span class="dim-name">${DIM_LABELS[d]}</span>
        <div class="dim-bar-track"><div class="dim-bar-fill" style="width:${Math.round(ds*10)}%;background:${dc}"></div></div>
        <span class="dim-score">${ds.toFixed(1)}</span>
      </div>`;
    }).join('');
    return `<div class="ad-item" onclick="this.classList.toggle('expanded')">
      <div class="ad-header">
        <div>
          <div class="ad-meta"><span class="ad-brief-label">${label}</span>${regenBadge}</div>
          <div class="ad-headline">${esc(ad.headline)}</div>
          <div class="ad-primary">${esc(ad.primary_text)}</div>
        </div>
        <div class="ad-score" style="color:${c}">${s.toFixed(1)}</div>
      </div>
      <div class="ad-expand"><div class="dim-grid">${dimRows}</div></div>
    </div>`;
  }).join('');
}

renderFilters();
renderList();"""

    # ── Assemble ───────────────────────────────────────────────────────────
    body_parts = [
        '<section class="act act1">\n',
        '  <div class="act-label">Act I &mdash; What We Built</div>\n',
        f'  <h1 class="headline-main">{total} ads written.<br>'
        f'<span class="hl">{final_pct}% publishable.</span><br>'
        f'The system made them better automatically.</h1>\n',
        '  <div class="top-cards">\n',
        top_cards_html, "\n",
        "  </div>\n</section>\n",
        '<section class="act act2">\n',
        '  <div class="act-label">Act II &mdash; What the System Learned</div>\n',
        f'  <p class="learning-statement">{weakest_dim_label} was the weakest dimension in every cycle.</p>\n',
        '  <div class="before-after">\n',
        f'    <span class="stat-before">{initial_pct}% passing</span>\n',
        '    <span class="stat-arrow">&rarr;</span>\n',
        f'    <span class="stat-after">{final_pct}% passing</span>\n',
        f'    <span class="stat-note">after {num_cycles} cycles of self-improvement</span>\n',
        "  </div>\n",
        '  <div class="bar-legend">\n',
        '    <span class="legend-item"><span class="legend-swatch before"></span> Before regen</span>\n',
        '    <span class="legend-item"><span class="legend-swatch after"></span> After regen</span>\n',
        "  </div>\n",
        '  <div class="cycle-bars">\n',
        cycle_bars_html, "\n",
        "  </div>\n</section>\n",
        '<section class="act act3">\n',
        '  <div class="act3-header">\n',
        f'    <div class="act3-title">All {total} Ads</div>\n',
        '    <div class="act3-sub">Click any ad to see per-dimension scores</div>\n',
        "  </div>\n",
        '  <div class="filters" id="filters"></div>\n',
        '  <div class="ad-list" id="ad-list"></div>\n',
        "</section>\n",
        f"<footer>Nerdy Ad Engine &mdash; {total} ads &mdash; "
        f"{num_cycles} optimization cycles &mdash; threshold {PUBLISHABLE_THRESHOLD}</footer>\n",
    ]
    body_html = "".join(body_parts)

    html = "".join([
        "<!DOCTYPE html>\n<html lang=\"en\">\n<head>\n",
        "  <meta charset=\"UTF-8\">\n",
        "  <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">\n",
        "  <title>Varsity Tutors SAT &mdash; Campaign Results</title>\n",
        "  <style>\n", css, "\n  </style>\n",
        "</head>\n<body>\n",
        body_html,
        "<script>\n",
        f"const ADS = {ads_json_str};\n",
        f"const BRIEF_LABELS = {brief_labels_json_str};\n",
        js_code,
        "\n</script>\n</body>\n</html>\n",
    ])

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(html, encoding="utf-8")
    return REPORT_PATH


# ── entry point ────────────────────────────────────────────────────────────

def run_feedback_loop() -> int:
    """Entry point called from main.py. Returns 0 on success, 1 on partial failure."""
    if not GENERATED_ADS_PATH.exists():
        print(
            f"ERROR: {GENERATED_ADS_PATH} not found. "
            "Run 'python main.py generate-ads' first."
        )
        return 1

    raw_ads: list[dict[str, Any]] = json.loads(
        GENERATED_ADS_PATH.read_text(encoding="utf-8")
    )
    print(f"Loaded {len(raw_ads)} ads from {GENERATED_ADS_PATH}")

    if not raw_ads:
        print("ERROR: No ads found in generated ads file.")
        return 1

    SCORED_PATH.parent.mkdir(parents=True, exist_ok=True)
    PUBLISHABLE_PATH.parent.mkdir(parents=True, exist_ok=True)
    ITERATION_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    settings = get_settings()
    client = AsyncAnthropic(api_key=settings.anthropic_api_key)
    judge = ClaudeJudge()

    print(f"\nStarting feedback loop — threshold={PUBLISHABLE_THRESHOLD}, "
          f"min_cycles={MIN_CYCLES}, max_cycles={MAX_CYCLES}, "
          f"early_stop={EARLY_STOP_RATE:.0%}")

    final_scored, iteration_log = asyncio.run(
        _run_all_cycles(raw_ads, client, judge)
    )

    publishable = [r for r in final_scored if r.get("publishable", False) and "error" not in r]
    PUBLISHABLE_PATH.write_text(
        json.dumps(publishable, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    _print_summary(iteration_log, final_scored, publishable)

    report_path = generate_report()
    print(f"    {report_path}")

    errors = [r for r in final_scored if "error" in r]
    if errors:
        print(f"\nWARNING: {len(errors)} ads had scoring errors — inspect {SCORED_PATH}")
        return 1

    return 0
