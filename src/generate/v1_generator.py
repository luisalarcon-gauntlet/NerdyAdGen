"""V1 text-only Gemini ad generation."""
import json
from typing import Optional

from src.generate.base import BaseGenerator, GenerationError, RegenerationStrategy
from src.models.ad import Ad, AdStatus
from src.models.brief import Brief, HookStyle
from src.models.evaluation import EvaluationResult
from src.utils.retry import with_retry
from src.utils.tracking import track_tokens


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


@with_retry(max_attempts=3, service="gemini")
@track_tokens(
    operation="generation",
    model="gemini-1.5-flash",
    provider="google",
    persist_callback=None,
)
async def _gemini_api(prompt: str):
    """Call Gemini 1.5 Flash; return raw response for token extraction. Use _call_gemini in code."""
    import google.generativeai as genai
    from src.config.settings import get_settings
    settings = get_settings()
    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")
    return await model.generate_content_async(prompt)


async def _call_gemini(prompt: str) -> str:
    """Call Gemini with prompt; return response text. Patch in tests to avoid real API."""
    response = await _gemini_api(prompt)
    if not response.text:
        raise GenerationError("Empty Gemini response")
    return response.text


def _build_generate_prompt(brief: Brief) -> str:
    """Build the full generation prompt from a resolved brief."""
    inf = brief.inferred
    length_target = inf.ad_length_target if inf and inf.ad_length_target else 125
    hook = inf.hook_style if inf and inf.hook_style else brief.hook_style
    hook_str = hook.value if hook else "n/a"

    parts = [
        "## Brand voice",
        "Empowering, knowledgeable, approachable, results-focused. Confident but not arrogant. Lead with outcomes not features.",
        "",
        "## Brief",
        f"Audience: {brief.audience.value}",
        f"Campaign goal: {brief.campaign_goal.value}",
        f"Product: {brief.product}",
    ]
    if brief.platform is not None:
        parts.append(f"Platform: {brief.platform.value}")
    if brief.offer is not None:
        parts.append(f"Offer: {brief.offer}")
    if brief.urgency is not None:
        parts.append(f"Urgency: {brief.urgency}")
    if brief.social_proof is not None:
        parts.append(f"Social proof: {brief.social_proof}")

    parts.extend([
        "",
        "## Ad anatomy",
        f"Primary text: max {length_target} characters.",
        "Headline: 5–8 words.",
        "Description: 20–30 words.",
        "CTA button: one of " + ", ".join(VALID_CTA_BUTTONS),
        "",
        "## Hook style",
        f"Use hook style: {hook_str}.",
    ])
    if hook == HookStyle.SOCIAL_PROOF:
        parts.append("Include explicit proof elements (testimonials, stats, or evidence).")

    parts.extend([
        "",
        "## Output",
        "Return ONLY valid JSON, no preamble. Keys: primary_text, headline, description, cta_button, status (use \"draft\").",
    ])
    return "\n".join(parts)


def _build_regenerate_prompt(
    ad: Ad,
    evaluation: EvaluationResult,
    strategy: RegenerationStrategy,
) -> str:
    """Build regeneration prompt with original ad, failed dimension, score, rationale."""
    weak = evaluation.weakest_dimension
    parts = [
        "## Original ad",
        f"Primary text: {ad.primary_text}",
        f"Headline: {ad.headline}",
        f"Description: {ad.description}",
        f"CTA: {ad.cta_button}",
        "",
        "## Dimension to improve",
        f"Dimension: {strategy.dimension}",
        f"Score: {weak.score}",
        f"Rationale: {weak.rationale}",
        "",
        "Preserve dimensions that scored >= 7.0. Do not sacrifice other dimensions for this one.",
        "",
        "## Output",
        "Return ONLY valid JSON. Keys: primary_text, headline, description, cta_button, status (\"draft\").",
    ]
    return "\n".join(parts)


def _parse_ad_json(
    raw: str,
    brief_id: str,
    ad_id: Optional[str] = None,
    max_primary_len: Optional[int] = None,
) -> Ad:
    """Parse Gemini JSON into Ad. Raises GenerationError on invalid JSON or missing fields."""
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        raise GenerationError(f"Invalid JSON from Gemini: {e}") from e

    primary = str(data.get("primary_text", "")).strip()
    headline = str(data.get("headline", "")).strip()
    description = str(data.get("description", "")).strip()
    cta = str(data.get("cta_button", "Learn More")).strip()
    if cta not in VALID_CTA_BUTTONS:
        cta = VALID_CTA_BUTTONS[0]
    if max_primary_len and len(primary) > max_primary_len:
        primary = primary[:max_primary_len].rstrip()

    kwargs: dict = {
        "brief_id": brief_id,
        "status": AdStatus.DRAFT,
        "primary_text": primary,
        "headline": headline,
        "description": description,
        "cta_button": cta,
        "image_url": None,
        "image_prompt": None,
    }
    if ad_id is not None:
        kwargs["id"] = ad_id
    return Ad(**kwargs)


class V1Generator(BaseGenerator):
    """Generates ad copy via Gemini 1.5 Flash from a resolved Brief."""

    async def generate(self, brief: Brief) -> Ad:
        prompt = _build_generate_prompt(brief)
        raw = await _call_gemini(prompt)
        max_len = None
        if brief.inferred and brief.inferred.ad_length_target is not None:
            max_len = brief.inferred.ad_length_target
        return _parse_ad_json(raw, brief_id=brief.id, max_primary_len=max_len)

    async def regenerate(
        self,
        ad: Ad,
        evaluation: EvaluationResult,
        strategy: RegenerationStrategy,
    ) -> Ad:
        prompt = _build_regenerate_prompt(ad, evaluation, strategy)
        raw = await _call_gemini(prompt)
        return _parse_ad_json(
            raw,
            brief_id=ad.brief_id,
            ad_id=ad.id,
        )
