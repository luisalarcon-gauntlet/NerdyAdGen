"""Ad and AdStatus. No imports from other src/ except models."""
import enum
from typing import Optional

from pydantic import BaseModel, Field

from src.models.ids import generate_id


def _utc_now_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


class AdStatus(str, enum.Enum):
    DRAFT = "draft"
    PUBLISHED = "published"
    ABANDONED = "abandoned"


class Ad(BaseModel):
    """Generated ad. image_url and image_prompt are None in V1."""

    id: str = Field(default_factory=generate_id)
    brief_id: str
    status: AdStatus
    primary_text: str
    headline: str
    description: str
    cta_button: str
    image_url: Optional[str] = None
    image_prompt: Optional[str] = None
    final_score: Optional[float] = None
    created_at: str = Field(default_factory=_utc_now_iso)
    updated_at: Optional[str] = None
