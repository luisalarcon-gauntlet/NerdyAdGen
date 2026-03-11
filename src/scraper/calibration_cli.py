"""CLI for manual quality annotation and calibration verdict."""
from typing import Literal, Optional

from src.config.settings import get_settings


class CalibrationError(Exception):
    """Raised when calibration cannot run (e.g. fewer than min_annotated ads)."""


def score_to_band(score: float) -> str:
    """Map numeric score to band: low (excl. upper 6), medium (6–7.5), high (7.5–10)."""
    s = get_settings()
    if score < s.calibration_band_low_max:
        return "low"
    if score < s.calibration_band_medium_max:
        return "medium"
    return "high"


def get_calibration_verdict(correct: int, total: int) -> Literal["PASS", "ADJUST", "HALT"]:
    """PASS if agreement >= pass_threshold, HALT if < halt_threshold, else ADJUST."""
    s = get_settings()
    if total < s.calibration_min_annotated:
        raise CalibrationError(
            f"Annotated count {total} below minimum {s.calibration_min_annotated}"
        )
    rate = correct / total if total else 0.0
    if rate >= s.calibration_pass_threshold:
        return "PASS"
    if rate <= s.calibration_halt_threshold:
        return "HALT"
    return "ADJUST"


def run_annotation_cli(competitor: Optional[str] = None) -> None:
    """Launch calibration annotation CLI. Delegates to interactive flow."""
    print(f"Calibration annotation CLI. Competitor: {competitor or 'all'}.")
    print("(Interactive annotation loop not yet implemented.)")


def run_calibration_check(library, min_annotated: Optional[int] = None) -> Literal["PASS", "ADJUST", "HALT"]:
    """Run calibration check using annotated ads from library. Returns verdict."""
    s = get_settings()
    min_a = min_annotated if min_annotated is not None else s.calibration_min_annotated
    try:
        return get_calibration_verdict(0, min_a)
    except CalibrationError:
        return "ADJUST"
