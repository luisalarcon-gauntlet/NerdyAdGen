"""
Nerdy Ad Engine — CLI entry point.
Commands: run, scrape, annotate, calibrate, report, run-pipeline, generate-report.
No business logic here; delegates to modules.
"""
import argparse
import asyncio
import logging
import sys

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
    stream=sys.stdout,
)


def _cmd_run(args: argparse.Namespace) -> int:
    """Run full V1 batch pipeline. Delegates to pipeline.run."""
    from src.pipeline.run import run_v1
    run_v1(run_id=None, briefs=None)
    return 0


def _cmd_scrape(args: argparse.Namespace) -> int:
    """Scrape competitor ads via Playwright. Saves to data/raw/competitor_ads.json."""
    from src.scraper.web_scraper import run_scrape, save_ads, validate_output, RAW_OUTPUT_PATH

    try:
        ads = asyncio.run(run_scrape())
        save_ads(ads)
        is_valid, message = validate_output()
        print(f"Scrape complete — {len(ads)} raw records collected.")
        if is_valid:
            print(f"Validation PASSED: {message}")
            print(f"Output: {RAW_OUTPUT_PATH}")
        else:
            print(f"Validation FAILED: {message}")
            return 1
    except Exception as e:
        print(f"Scrape failed: {e}")
        return 1
    return 0


def _cmd_annotate(args: argparse.Namespace) -> int:
    """Launch calibration annotation CLI. Delegates to calibration_cli."""
    from src.scraper.calibration_cli import run_annotation_cli
    run_annotation_cli(competitor=getattr(args, "competitor", None))
    return 0


def _cmd_calibrate(args: argparse.Namespace) -> int:
    """Run calibration check. Delegates to calibration_cli."""
    from src.config.database import get_engine
    from src.output.library import AdLibrary
    from src.scraper.calibration_cli import run_calibration_check
    try:
        engine = get_engine()
        library = AdLibrary(engine)
        verdict = run_calibration_check(library, min_annotated=getattr(args, "min_annotated", None))
        print(f"Calibration verdict: {verdict}")
    except Exception as e:
        print(f"Calibration check failed: {e}")
        return 1
    return 0


def _cmd_score_competitors(args: argparse.Namespace) -> int:
    """Score all competitor ads via ClaudeJudge. Saves to data/evaluated/competitor_ads_scored.json."""
    from src.evaluate.calibrate_competitor_ads import run_competitor_calibration
    return run_competitor_calibration()


def _cmd_generate_ads(args: argparse.Namespace) -> int:
    """Generate 50+ Varsity Tutors ad copies via Claude. Saves to data/generated/ads_raw.json."""
    from src.generate.generate_ads import run_generate_ads
    return run_generate_ads()


def _cmd_run_pipeline(args: argparse.Namespace) -> int:
    """Run full feedback loop: score → filter → regenerate → iterate."""
    from src.iterate.feedback_loop import run_feedback_loop
    return run_feedback_loop()


def _cmd_generate_report(args: argparse.Namespace) -> int:
    """Generate HTML results dashboard from existing output files."""
    from src.iterate.feedback_loop import generate_report, PUBLISHABLE_PATH, ITERATION_LOG_PATH
    if not PUBLISHABLE_PATH.exists():
        print(f"ERROR: {PUBLISHABLE_PATH} not found. Run 'python main.py run-pipeline' first.")
        return 1
    if not ITERATION_LOG_PATH.exists():
        print(f"ERROR: {ITERATION_LOG_PATH} not found. Run 'python main.py run-pipeline' first.")
        return 1
    try:
        report_path = generate_report()
        print(f"Report written to {report_path}")
        print(f"Open in browser: file://{report_path.resolve().as_posix()}")
    except Exception as exc:
        print(f"Report generation failed: {exc}")
        return 1
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    """Generate reports from existing data. Delegates to output.reporter and visualizer."""
    from pathlib import Path
    from src.config.database import get_engine
    from src.output.library import AdLibrary
    from src.output.reporter import PerformanceReporter
    from src.output.visualizer import QualityTrendVisualizer
    reports_dir = Path("reports")
    reports_dir.mkdir(parents=True, exist_ok=True)

    async def _do_report():
        engine = get_engine()
        library = AdLibrary(engine)
        reporter = PerformanceReporter(library=library)
        await reporter.export_json(str(reports_dir / "evaluation_report.json"))
        await reporter.export_csv(str(reports_dir / "evaluation_report.csv"))
        await reporter.generate_cost_report(str(reports_dir / "cost_report.json"))
        viz = QualityTrendVisualizer(library=library)
        await viz.generate(str(reports_dir / "quality_trend.html"))

    try:
        asyncio.run(_do_report())
    except Exception as e:
        print(f"Report generation failed: {e}")
        return 1
    return 0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="Nerdy Ad Engine — Facebook/Instagram ad generation pipeline for Varsity Tutors SAT prep.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    subparsers.add_parser("run", help="Run full V1 batch pipeline")
    run_parser = subparsers.choices["run"]
    run_parser.add_argument("--mode", choices=("v1", "v2", "v3"), default="v1", help="Pipeline version")
    run_parser.set_defaults(handler=_cmd_run)

    subparsers.add_parser("scrape", help="Scrape competitor ads only")
    subparsers.choices["scrape"].set_defaults(handler=_cmd_scrape)

    annotate_parser = subparsers.add_parser("annotate", help="Launch calibration annotation CLI")
    annotate_parser.add_argument("--competitor", type=str, help="Competitor to annotate (e.g. princeton_review)")
    annotate_parser.set_defaults(handler=_cmd_annotate)

    calibrate_parser = subparsers.add_parser("calibrate", help="Run calibration check")
    calibrate_parser.add_argument("--min-annotated", type=int, default=20, help="Minimum annotated ads required")
    calibrate_parser.set_defaults(handler=_cmd_calibrate)

    subparsers.add_parser(
        "score-competitors",
        help="Score all competitor ads via ClaudeJudge; saves to data/evaluated/",
    )
    subparsers.choices["score-competitors"].set_defaults(handler=_cmd_score_competitors)

    subparsers.add_parser(
        "generate-ads",
        help="Generate 50+ Varsity Tutors ads via Claude claude-sonnet-4-6; saves to data/generated/ads_raw.json",
    )
    subparsers.choices["generate-ads"].set_defaults(handler=_cmd_generate_ads)

    subparsers.add_parser(
        "run-pipeline",
        help=(
            "Run full feedback loop over data/generated/ads_raw.json: "
            "score → filter → regenerate → iterate (3+ cycles)"
        ),
    )
    subparsers.choices["run-pipeline"].set_defaults(handler=_cmd_run_pipeline)

    subparsers.add_parser("report", help="Generate reports from existing data")
    subparsers.choices["report"].set_defaults(handler=_cmd_report)

    subparsers.add_parser(
        "generate-report",
        help="Generate self-contained HTML dashboard from data/output/ — no server needed",
    )
    subparsers.choices["generate-report"].set_defaults(handler=_cmd_generate_report)

    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    handler = getattr(args, "handler", None)
    if handler is None:
        return 1
    return handler(args)


if __name__ == "__main__":
    sys.exit(main())
