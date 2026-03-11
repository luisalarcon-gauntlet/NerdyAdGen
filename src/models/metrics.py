"""TokenUsageRecord, CostCalculator, PerformanceMetrics. No imports from other src/."""
from typing import Optional

from pydantic import BaseModel, Field

from src.models.ids import generate_id


def _utc_now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


# Per million tokens (USD). Claude Sonnet 4.6, Gemini 1.5 Flash.
CLAUDE_SONNET_INPUT_PER_M = 3.0
CLAUDE_SONNET_OUTPUT_PER_M = 15.0
GEMINI_FLASH_INPUT_PER_M = 0.075
GEMINI_FLASH_OUTPUT_PER_M = 0.30


class CostCalculator:
    """Static cost calculation from provider/model and token counts."""

    @staticmethod
    def calculate(
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
    ) -> float:
        if provider == "anthropic" and "claude-sonnet" in model:
            in_cost = (input_tokens / 1_000_000) * CLAUDE_SONNET_INPUT_PER_M
            out_cost = (output_tokens / 1_000_000) * CLAUDE_SONNET_OUTPUT_PER_M
            return in_cost + out_cost
        if provider == "google" and "gemini" in model and "flash" in model:
            in_cost = (input_tokens / 1_000_000) * GEMINI_FLASH_INPUT_PER_M
            out_cost = (output_tokens / 1_000_000) * GEMINI_FLASH_OUTPUT_PER_M
            return in_cost + out_cost
        raise ValueError(f"Unknown provider/model: {provider}/{model}")


class TokenUsageRecord(BaseModel):
    """One API call token usage and cost."""

    id: str = Field(default_factory=generate_id)
    ad_id: str
    brief_id: str
    operation: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cost_usd: float
    created_at: str = Field(default_factory=_utc_now_iso)


class PerformanceMetrics(BaseModel):
    """Aggregated performance metrics (from reporter)."""

    total_ads_generated: int
    total_ads_published: int
    total_api_cost_usd: float
    quality_per_dollar: Optional[float] = None
