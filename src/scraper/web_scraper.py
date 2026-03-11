"""Playwright-based Meta Ad Library web scraper.

Uses stealth settings (slow_mo, realistic user-agent, viewport), explicit element
waits, incremental scroll for lazy-loaded ad cards, and exponential backoff for
rate limiting. Saves raw results to data/raw/competitor_ads.json.
"""
import asyncio
import json
import logging
import random
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from urllib.parse import quote_plus

from playwright.async_api import (
    async_playwright,
    BrowserContext,
    Page,
    TimeoutError as PlaywrightTimeoutError,
)

LOG = logging.getLogger(__name__)

RAW_OUTPUT_PATH = Path("data/raw/competitor_ads.json")

COMPETITORS: dict[str, str] = {
    "princeton_review": "Princeton Review SAT",
    "kaplan": "Kaplan Test Prep",
    "khan_academy": "Khan Academy",
    "chegg": "Chegg",
    "varsity_tutors": "Varsity Tutors",
}

# Human-readable brand name fallback when the DOM scrape can't find the advertiser link
_COMPETITOR_BRAND_NAMES: dict[str, str] = {
    "princeton_review": "The Princeton Review",
    "kaplan": "Kaplan Test Prep",
    "khan_academy": "Khan Academy",
    "chegg": "Chegg",
    "varsity_tutors": "Varsity Tutors",
}

_AD_LIBRARY_BASE = "https://www.facebook.com/ads/library/"
_MAX_ADS_PER_COMPETITOR = 15
_SCROLL_PAUSE_MS = 2500
_MAX_SCROLLS = 20
_MAX_RETRIES = 3
_INITIAL_BACKOFF = 5.0
_PAGE_LOAD_TIMEOUT_MS = 60_000
_ELEMENT_WAIT_TIMEOUT_MS = 20_000

_USER_AGENTS = [
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36"
    ),
    (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:124.0) "
        "Gecko/20100101 Firefox/124.0"
    ),
]

# JavaScript that extracts structured ad data from the current page.
#
# Meta Ad Library no longer embeds /ads/library/?id= links in search results.
# Instead, each ad card has:
#   - An <a href="https://www.facebook.com/PAGE/"> link for the advertiser name
#   - One or more <a href="https://l.facebook.com/l.php?u=..."> redirect links
#     whose inner text follows the pattern: DOMAIN\nHeadline\nDescription
#
# The destination URL in the l.php redirect often contains an `exid` param that
# is a stable, ad-specific UUID we can use as the ad_id.
_EXTRACT_ADS_JS = r"""
() => {
    const ads = [];
    const seenIds = new Set();

    const boilerplateRe = /^(Active|Inactive|Sponsored|Ad|See ad details|See summary|About this ad|Report ad|\d[\d,]* (?:impressions?|reach)|All ages|Men|Women|Running|Paused|Log in|Sign [Uu]p)$/i;
    const datePatternsRe = /started running|runs from|running since|ended|^(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+\d/i;
    const ctaRe = /^(learn more|sign up|get started|book now|shop now|subscribe|contact us|apply now|download|enroll now|start free(?: trial)?|try (?:for )?free|get offer|see more|get a quote|watch more|send message|message us|call now|get directions|order now|get access)$/i;
    const domainRe = /^[A-Z0-9][A-Z0-9\-\.]+\.[A-Z]{2,}$/;

    function extractExid(href) {
        try {
            const inner = decodeURIComponent(href.split('u=')[1].split('&h=')[0]);
            const url = new URL(inner);
            return url.searchParams.get('exid');
        } catch(e) { return null; }
    }

    function hashStr(str) {
        let h = 0;
        for (let i = 0; i < Math.min(str.length, 200); i++) {
            h = Math.imul(31, h) + str.charCodeAt(i) | 0;
        }
        return 'web-' + Math.abs(h).toString(36);
    }

    // Anchor on external redirect links — every ad has at least one
    const extLinks = Array.from(
        document.querySelectorAll('a[href*="l.facebook.com/l.php"]')
    );

    for (const link of extLinks) {
        const linkText = (link.innerText || '').trim();
        const linkLines = linkText.split('\n').map(l => l.trim()).filter(l => l.length > 0);

        // Skip single-line CTA buttons (e.g., "Learn More")
        if (linkLines.length < 2) continue;
        // First line must look like an ALL-CAPS domain or short label
        if (!domainRe.test(linkLines[0]) && linkLines[0].length > 60) continue;

        const href = link.getAttribute('href') || '';
        const exid = extractExid(href);
        const adId = exid || hashStr(href);

        if (seenIds.has(adId)) continue;
        seenIds.add(adId);

        // Walk up DOM to find the full card container — one that also holds the
        // advertiser's FB page link. The creative section is nested inside the card.
        const fbLinkSel = 'a[href^="https://www.facebook.com/"]:not([href*="ads/library"]):not([href*="ads/about"]):not([href*="ads/branded"])';
        let container = link.parentElement;
        for (let i = 0; i < 22 && container; i++) {
            const fbTest = container.querySelector(fbLinkSel);
            if (fbTest) break;
            container = container.parentElement;
        }
        if (!container) container = link.parentElement;

        const innerText = (container ? container.innerText : '').trim();
        const bodyLines = innerText.split('\n').map(l => l.trim()).filter(l => l.length > 0);

        // Advertiser name from the FB page link inside this container
        const fbLink = container ? container.querySelector(fbLinkSel) : null;
        const advertiserName = fbLink ? (fbLink.innerText || '').trim() || null : null;

        // Content lines: strip boilerplate, dates, very short fragments
        const contentLines = bodyLines.filter(
            l => !boilerplateRe.test(l) && !datePatternsRe.test(l) && l.length > 1
        );

        // CTA: first line matching CTA pattern anywhere in the card
        let ctaButton = null;
        for (const l of bodyLines) {
            if (ctaRe.test(l)) { ctaButton = l; break; }
        }

        // Primary text: first long body line (30+ chars) that isn't advertiser name or domain
        let primaryText = null;
        for (const l of contentLines) {
            if (
                l.length >= 30 &&
                l !== advertiserName &&
                !domainRe.test(l) &&
                !ctaRe.test(l) &&
                !l.match(/^https?:\/\//)
            ) {
                primaryText = l;
                break;
            }
        }

        // Headline and description come directly from the link text:
        //   linkLines[0] = domain label (e.g., "PRINCETONREVIEW.COM")
        //   linkLines[1] = headline
        //   linkLines[2] = description (optional)
        const headline = linkLines.length >= 2 ? linkLines[1] : null;
        const description = linkLines.length >= 3 ? linkLines[2] : null;

        if (!primaryText && !headline) continue;

        ads.push({
            ad_id: adId,
            advertiser_name: advertiserName,
            primary_text: primaryText,
            headline: headline,
            description: description,
            cta_button: ctaButton,
            raw_text: innerText.substring(0, 2000),
        });
    }

    return ads;
}
"""


def _build_url(query: str) -> str:
    return (
        f"{_AD_LIBRARY_BASE}?active_status=active&ad_type=all&country=US"
        f"&q={quote_plus(query)}&search_type=keyword_unordered"
    )


def _scraped_at() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _dismiss_cookie_banner(page: Page) -> None:
    """Dismiss any cookie consent banner that may block interaction."""
    for text in [
        "Allow essential and optional cookies",
        "Accept All",
        "Allow all cookies",
        "Decline optional cookies",
        "Only allow essential cookies",
    ]:
        try:
            btn = page.get_by_role("button", name=re.compile(text, re.I))
            if await btn.is_visible(timeout=2_500):
                await btn.click()
                await page.wait_for_timeout(1_000)
                return
        except Exception:
            pass


_AD_LINK_SELECTOR = 'a[href*="l.facebook.com/l.php"]'


async def _wait_for_ads(page: Page) -> bool:
    """Wait for at least one external redirect link (ad creative) to appear."""
    try:
        await page.wait_for_selector(
            _AD_LINK_SELECTOR,
            timeout=_ELEMENT_WAIT_TIMEOUT_MS,
            state="attached",
        )
        return True
    except PlaywrightTimeoutError:
        LOG.warning("Timed out waiting for ad content links")
        return False


async def _scroll_to_load_more(page: Page, target_count: int) -> None:
    """Scroll the page incrementally to trigger lazy-loaded ad cards."""
    for scroll_num in range(_MAX_SCROLLS):
        links = await page.query_selector_all(_AD_LINK_SELECTOR)
        if len(links) >= target_count:
            LOG.info(
                "scroll_stop scroll=%d links=%d target=%d",
                scroll_num,
                len(links),
                target_count,
            )
            break
        await page.evaluate("window.scrollBy(0, window.innerHeight * 0.85)")
        pause = _SCROLL_PAUSE_MS + random.randint(0, 800)
        await page.wait_for_timeout(pause)
        LOG.debug("scroll=%d links_found=%d", scroll_num, len(links))


async def _scrape_one_competitor(
    context: BrowserContext,
    competitor_key: str,
    search_query: str,
) -> list[dict[str, Any]]:
    """Scrape a single competitor search page. Returns list of raw ad dicts."""
    url = _build_url(search_query)
    scraped_at = _scraped_at()

    for attempt in range(_MAX_RETRIES):
        page: Optional[Page] = None
        try:
            page = await context.new_page()
            LOG.info(
                "scrape_attempt attempt=%d competitor=%s url=%s",
                attempt + 1,
                competitor_key,
                url,
            )

            await page.goto(
                url, wait_until="domcontentloaded", timeout=_PAGE_LOAD_TIMEOUT_MS
            )
            # Allow React rendering to settle before interacting
            await page.wait_for_timeout(2_500 + random.randint(0, 1_000))
            await _dismiss_cookie_banner(page)

            found = await _wait_for_ads(page)
            if not found:
                page_text = await page.inner_text("body")
                if any(
                    kw in page_text.lower()
                    for kw in ["no ads found", "0 ads match", "no results"]
                ):
                    LOG.info("competitor=%s: zero results page", competitor_key)
                    return []
                raise RuntimeError("Ad content links never appeared in DOM")

            await _scroll_to_load_more(page, target_count=_MAX_ADS_PER_COMPETITOR)
            await page.wait_for_timeout(1_000)

            raw_ads: list[dict] = await page.evaluate(_EXTRACT_ADS_JS)
            LOG.info(
                "competitor=%s raw_ads_extracted=%d", competitor_key, len(raw_ads)
            )

            brand_fallback = _COMPETITOR_BRAND_NAMES.get(competitor_key, competitor_key)
            for raw in raw_ads:
                raw["competitor"] = competitor_key
                raw["scraped_at"] = scraped_at
                raw["source_url"] = url
                # Fill in advertiser_name from known brand when DOM walk didn't find it
                if not raw.get("advertiser_name"):
                    raw["advertiser_name"] = brand_fallback

            return raw_ads[:_MAX_ADS_PER_COMPETITOR]

        except PlaywrightTimeoutError as exc:
            backoff = _INITIAL_BACKOFF * (2**attempt) + random.uniform(0, 2)
            LOG.warning(
                "PlaywrightTimeoutError attempt=%d competitor=%s err=%s backoff=%.1fs",
                attempt + 1,
                competitor_key,
                exc,
                backoff,
            )
            await asyncio.sleep(backoff)

        except Exception as exc:
            backoff = _INITIAL_BACKOFF * (2**attempt) + random.uniform(0, 2)
            LOG.warning(
                "scrape_error attempt=%d competitor=%s err=%s backoff=%.1fs",
                attempt + 1,
                competitor_key,
                exc,
                backoff,
            )
            await asyncio.sleep(backoff)

        finally:
            if page and not page.is_closed():
                await page.close()

    LOG.error(
        "All %d attempts exhausted for competitor=%s", _MAX_RETRIES, competitor_key
    )
    return []


async def run_scrape() -> list[dict[str, Any]]:
    """Scrape all competitors. Returns combined flat list of raw ad dicts."""
    all_ads: list[dict[str, Any]] = []

    async with async_playwright() as pw:
        browser = await pw.chromium.launch(
            headless=True,
            slow_mo=50,
            args=[
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-accelerated-2d-canvas",
                "--no-first-run",
                "--no-zygote",
                "--disable-gpu",
                "--single-process",
            ],
        )
        context = await browser.new_context(
            viewport={"width": 1366, "height": 768},
            user_agent=random.choice(_USER_AGENTS),
            locale="en-US",
            timezone_id="America/New_York",
            java_script_enabled=True,
        )
        # Suppress the navigator.webdriver flag that Playwright sets by default
        await context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )

        for competitor_key, search_query in COMPETITORS.items():
            LOG.info(
                "=== Scraping: %s (query=%r) ===", competitor_key, search_query
            )
            try:
                ads = await _scrape_one_competitor(
                    context, competitor_key, search_query
                )
                all_ads.extend(ads)
                LOG.info(
                    "competitor=%s collected=%d total=%d",
                    competitor_key,
                    len(ads),
                    len(all_ads),
                )
            except Exception as exc:
                LOG.error("competitor=%s fatal error: %s", competitor_key, exc)

            # Polite inter-competitor delay to avoid rate limiting
            delay = 3.0 + random.uniform(0, 2.0)
            LOG.info("Waiting %.1fs before next competitor...", delay)
            await asyncio.sleep(delay)

        await context.close()
        await browser.close()

    return all_ads


def save_ads(ads: list[dict[str, Any]], path: Path = RAW_OUTPUT_PATH) -> None:
    """Persist ad list as JSON."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        json.dump(ads, fh, indent=2, ensure_ascii=False)
    LOG.info("Saved %d ads → %s", len(ads), path)


def validate_output(path: Path = RAW_OUTPUT_PATH) -> tuple[bool, str]:
    """
    Validate the output file.
    A valid record must have advertiser_name, primary_text, and ad_id populated.
    Returns (is_valid, message).
    """
    if not path.exists():
        return False, f"Output file not found: {path}"
    try:
        with open(path, encoding="utf-8") as fh:
            data = json.load(fh)
    except json.JSONDecodeError as exc:
        return False, f"JSON parse error: {exc}"
    if not isinstance(data, list):
        return False, "Top-level JSON value is not an array"
    valid_records = [
        r
        for r in data
        if isinstance(r, dict)
        and r.get("advertiser_name")
        and r.get("primary_text")
        and r.get("ad_id")
    ]
    if len(valid_records) < 10:
        return (
            False,
            f"Only {len(valid_records)} valid records (need ≥10). "
            f"Total records in file: {len(data)}",
        )
    return True, f"{len(valid_records)} valid records ✓"


async def _main_async() -> None:
    LOG.info("Starting Meta Ad Library web scrape...")
    ads = await run_scrape()
    save_ads(ads)
    is_valid, message = validate_output()
    if is_valid:
        LOG.info("SUCCESS: %s", message)
    else:
        LOG.error("VALIDATION FAILED: %s", message)
        raise SystemExit(1)


if __name__ == "__main__":
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        stream=sys.stdout,
    )
    asyncio.run(_main_async())
