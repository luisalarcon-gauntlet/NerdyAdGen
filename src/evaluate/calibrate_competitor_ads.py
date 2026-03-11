"""Competitor ad calibration runner.

Loads data/raw/competitor_ads.json, scores all 40 ads via ClaudeJudge
using the competitor_calibration weight profile, and saves results to
data/evaluated/competitor_ads_scored.json in the specified output schema.

Weight rationale documented in docs/decision_log.md Entry 28.
"""
import asyncio
import json
import logging
from pathlib import Path
from typing import Any

from src.evaluate.judge import ClaudeJudge
from src.models.ad import Ad, AdStatus
from src.models.evaluation import EvaluationResult
from src.models.weights import DimensionWeights, KnockoutThresholds, WeightProfile

logger = logging.getLogger(__name__)

RAW_ADS_PATH = Path("data/raw/competitor_ads.json")
OUTPUT_PATH = Path("data/evaluated/competitor_ads_scored.json")
QUALITY_THRESHOLD = 7.0

# Calibration profile: weights as specified in task requirements.
# Rationale documented in decision_log.md Entry 28.
_CALIBRATION_WEIGHTS = DimensionWeights(
    clarity=0.20,
    value_proposition=0.30,
    cta=0.20,
    brand_voice=0.15,
    emotional_resonance=0.15,
)

CALIBRATION_PROFILE = WeightProfile(
    profile_id="competitor_calibration",
    audience="general",
    campaign_goal="competitor_analysis",
    quality_threshold=QUALITY_THRESHOLD,
    weights=_CALIBRATION_WEIGHTS,
    knockout_thresholds=KnockoutThresholds(),  # no knockouts for analysis pass
)


def _scraped_to_ad(raw: dict[str, Any]) -> Ad:
    """Adapt raw scraped-ad JSON to Ad model for ClaudeJudge.

    ScrapedAd has different field names from Ad.  We bridge the two formats
    here rather than polluting either model.
    """
    return Ad(
        id=raw["ad_id"],
        brief_id="competitor_calibration",
        status=AdStatus.DRAFT,
        primary_text=raw.get("primary_text") or "",
        headline=raw.get("headline") or "",
        description=raw.get("description") or "",
        cta_button=raw.get("cta_button") or "",
    )


def _to_output_schema(
    raw: dict[str, Any],
    result: EvaluationResult,
) -> dict[str, Any]:
    """Map EvaluationResult to the calibration output schema."""
    scores_map = {d.dimension: d for d in result.dimension_scores}

    def _dim(name: str) -> dict[str, Any]:
        d = scores_map.get(name)
        if d:
            return {"score": d.score, "rationale": d.rationale}
        return {"score": 0.0, "rationale": "dimension missing from response"}

    return {
        "ad_id": raw["ad_id"],
        "advertiser": raw.get("advertiser_name", ""),
        "competitor": raw.get("competitor", ""),
        "primary_text": raw.get("primary_text") or "",
        "scores": {
            "clarity": _dim("clarity"),
            "value_proposition": _dim("value_proposition"),
            "cta": _dim("cta"),
            "brand_voice": _dim("brand_voice"),
            "emotional_resonance": _dim("emotional_resonance"),
        },
        "aggregate_score": round(result.weighted_score, 2),
        "confidence": result.confidence_level.value,
        "publishable": result.is_publishable(QUALITY_THRESHOLD),
    }


def _error_record(raw: dict[str, Any], exc: Exception) -> dict[str, Any]:
    return {
        "ad_id": raw["ad_id"],
        "advertiser": raw.get("advertiser_name", ""),
        "competitor": raw.get("competitor", ""),
        "primary_text": raw.get("primary_text") or "",
        "error": str(exc),
    }


async def _score_all(raw_ads: list[dict[str, Any]]) -> list[dict[str, Any]]:
    judge = ClaudeJudge()
    total = len(raw_ads)
    results: list[dict[str, Any]] = []

    for i, raw in enumerate(raw_ads, start=1):
        ad_id = raw.get("ad_id", "?")
        competitor = raw.get("competitor", "?")
        logger.info("[%d/%d] Scoring %s (%s)", i, total, ad_id, competitor)
        print(f"[{i}/{total}] {competitor} | {ad_id}")

        try:
            ad = _scraped_to_ad(raw)
            result = await judge.evaluate(ad, CALIBRATION_PROFILE)
            record = _to_output_schema(raw, result)
            results.append(record)
            print(
                f"       aggregate={record['aggregate_score']:.2f} "
                f"confidence={record['confidence']} "
                f"publishable={record['publishable']}"
            )
        except Exception as exc:
            logger.error("Failed to score %s: %s", ad_id, exc)
            print(f"       ERROR: {exc}")
            results.append(_error_record(raw, exc))

    return results


def _print_sanity_check(results: list[dict[str, Any]]) -> None:
    scored = [r for r in results if "aggregate_score" in r]
    errors = [r for r in results if "error" in r]

    if not scored:
        print("\nNo scored ads — nothing to sanity-check.")
        return

    by_score = sorted(scored, key=lambda x: x["aggregate_score"], reverse=True)

    print("\n" + "=" * 70)
    print("SANITY CHECK — Top 5 scoring ads")
    print("=" * 70)
    for r in by_score[:5]:
        print(
            f"  {r['aggregate_score']:.2f} | {r.get('competitor','?'):20s} | "
            f"{r['primary_text'][:55]}"
        )

    print("\n" + "=" * 70)
    print("SANITY CHECK — Bottom 5 scoring ads")
    print("=" * 70)
    for r in by_score[-5:]:
        print(
            f"  {r['aggregate_score']:.2f} | {r.get('competitor','?'):20s} | "
            f"{r['primary_text'][:55]}"
        )

    unpublishable = [r for r in scored if not r.get("publishable")]
    print(
        f"\nFlagged unpublishable (aggregate < {QUALITY_THRESHOLD}): "
        f"{len(unpublishable)}/{len(scored)}"
    )
    if errors:
        print(f"Scoring errors (excluded from totals): {len(errors)}")

    print("=" * 70)


def run_competitor_calibration() -> int:
    """Entry point called from main.py. Returns 0 on success, 1 on failure."""
    if not RAW_ADS_PATH.exists():
        print(f"ERROR: {RAW_ADS_PATH} not found. Run 'python main.py scrape' first.")
        return 1

    raw_ads: list[dict[str, Any]] = json.loads(
        RAW_ADS_PATH.read_text(encoding="utf-8")
    )
    print(f"Loaded {len(raw_ads)} ads from {RAW_ADS_PATH}")

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    results = asyncio.run(_score_all(raw_ads))

    OUTPUT_PATH.write_text(
        json.dumps(results, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print(f"\nSaved {len(results)} records to {OUTPUT_PATH}")

    _print_sanity_check(results)

    scored = [r for r in results if "aggregate_score" in r]
    errors = [r for r in results if "error" in r]

    if errors:
        print(f"\nWARNING: {len(errors)} ads failed to score — inspect errors above.")
        return 1
    if len(scored) < len(raw_ads):
        print("\nWARNING: Not all ads were scored.")
        return 1

    print("\nCalibration complete. Inspect top/bottom 5 above for plausibility.")
    return 0
