"""@track_tokens decorator: capture token usage from API response and build TokenUsageRecord."""
from functools import wraps
from typing import Callable, Optional, TypeVar

from src.models.metrics import CostCalculator, TokenUsageRecord

T = TypeVar("T")


def _extract_gemini_tokens(response: object) -> tuple[int, int]:
    in_t = getattr(
        getattr(response, "usage_metadata", None),
        "prompt_token_count",
        None,
    )
    out_t = getattr(
        getattr(response, "usage_metadata", None),
        "candidates_token_count",
        None,
    )
    if in_t is None or out_t is None:
        return 0, 0
    return int(in_t), int(out_t)


def _extract_claude_tokens(response: object) -> tuple[int, int]:
    usage = getattr(response, "usage", None)
    if usage is None:
        return 0, 0
    in_t = getattr(usage, "input_tokens", None) or 0
    out_t = getattr(usage, "output_tokens", None) or 0
    return int(in_t), int(out_t)


def track_tokens(
    operation: str,
    model: str,
    provider: str,
    persist_callback: Optional[Callable[[TokenUsageRecord], None]] = None,
):
    """Decorate an async function that returns an API response. Builds TokenUsageRecord from response."""

    def decorator(fn: Callable[..., T]) -> Callable[..., T]:
        @wraps(fn)
        async def wrapper(*args, **kwargs) -> T:
            result = await fn(*args, **kwargs)
            ad_id = kwargs.get("ad_id") or (args[0] if len(args) > 0 else "")
            brief_id = kwargs.get("brief_id") or (args[1] if len(args) > 1 else "")
            if provider == "google" or "gemini" in model:
                input_tokens, output_tokens = _extract_gemini_tokens(result)
            elif provider == "anthropic" or "claude" in model:
                input_tokens, output_tokens = _extract_claude_tokens(result)
            else:
                input_tokens, output_tokens = 0, 0
            cost_usd = CostCalculator.calculate(
                provider=provider,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )
            record = TokenUsageRecord(
                ad_id=ad_id,
                brief_id=brief_id,
                operation=operation,
                provider=provider,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cost_usd=cost_usd,
            )
            if persist_callback:
                persist_callback(record)
            return result

        return wrapper

    return decorator
