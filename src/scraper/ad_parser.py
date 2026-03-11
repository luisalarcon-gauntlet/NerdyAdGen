"""HTML field extraction and ad usability / language checks."""
import re
from typing import Any, Optional

from langdetect import detect


SKIP_REASON_NO_COPY_TEXT = "no_copy_text"


def is_usable(primary_text: Optional[str], headline: Optional[str]) -> bool:
    """Returns False if both primary_text and headline are None or empty."""
    return (primary_text is not None and primary_text.strip() != "") or (
        headline is not None and headline.strip() != ""
    )


def is_ad_usable(
    primary_text: Optional[str],
    headline: Optional[str],
) -> bool:
    """True if ad has primary_text or headline (or both)."""
    return is_usable(primary_text, headline)


def get_skip_reason(
    primary_text: Optional[str],
    headline: Optional[str],
) -> Optional[str]:
    """Returns no_copy_text when neither primary_text nor headline present, else None."""
    if is_ad_usable(primary_text, headline):
        return None
    return SKIP_REASON_NO_COPY_TEXT


def is_english(text: str) -> bool:
    """True if text is detected as English. On langdetect exception, returns True (keep ad)."""
    if not text or not text.strip():
        return True
    try:
        return detect(text) == "en"
    except Exception:
        return True


def _norm(s: Optional[str]) -> Optional[str]:
    """Return stripped string or None if empty."""
    if s is None:
        return None
    t = s.strip()
    return t if t else None


def parse_ad_html(raw_html: str) -> dict[str, Any]:
    """Extract ad fields from raw Meta Ad Library DOM HTML. Returns dict with keys matching ScrapedAd."""
    out: dict[str, Any] = {
        "primary_text": None,
        "headline": None,
        "description": None,
        "cta_button": None,
        "ad_library_id": "",
        "platform": None,
        "ad_format": None,
        "is_active": True,
    }
    if not raw_html or not raw_html.strip():
        return out
    html = raw_html.replace("\n", " ")
    id_match = re.search(r'data-ad-id="([^"]+)"', html) or re.search(
        r'/ads/library/\?id=(\d+)', html
    )
    if id_match:
        out["ad_library_id"] = id_match.group(1)
    primary = re.search(
        r'<(?:div|span)[^>]*class="[^"]*ad.*body[^"]*"[^>]*>([^<]+)</', html, re.I
    ) or re.search(r'<div[^>]*data-testid="ad-card-body"[^>]*>([^<]+)</div>', html, re.I)
    if primary:
        out["primary_text"] = _norm(primary.group(1))
    if not out["primary_text"]:
        first_long = re.search(r'<div[^>]*>([A-Za-z][^<]{20,500})</div>', html)
        if first_long:
            out["primary_text"] = _norm(first_long.group(1))
    headline_m = re.search(
        r'<(?:div|span)[^>]*class="[^"]*headline[^"]*"[^>]*>([^<]+)</', html, re.I
    ) or re.search(r'data-testid="ad-card-headline"[^>]*>([^<]+)<', html, re.I)
    if headline_m:
        out["headline"] = _norm(headline_m.group(1))
    desc_m = re.search(
        r'<(?:div|span)[^>]*class="[^"]*description[^"]*"[^>]*>([^<]+)</', html, re.I
    )
    if desc_m:
        out["description"] = _norm(desc_m.group(1))
    cta_m = re.search(
        r'<(?:span|div|button)[^>]*class="[^"]*cta[^"]*"[^>]*>([^<]+)</', html, re.I
    ) or re.search(r'data-testid="ad-card-cta"[^>]*>([^<]+)<', html, re.I)
    if cta_m:
        out["cta_button"] = _norm(cta_m.group(1))
    return out
