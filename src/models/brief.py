"""Brief, enums, and inferred resolution. No imports from other src/ except models."""
import enum
from datetime import datetime, timezone
from typing import Optional

from pydantic import BaseModel, Field

from src.models.ids import generate_id


class AudienceType(str, enum.Enum):
    PARENT = "parent"
    STUDENT = "student"


class CampaignGoal(str, enum.Enum):
    AWARENESS = "awareness"
    CONVERSION = "conversion"
    RETARGETING = "retargeting"


class HookStyle(str, enum.Enum):
    FEAR = "fear"
    SOCIAL_PROOF = "social_proof"
    QUESTION = "question"
    STAT = "stat"
    ASPIRATION = "aspiration"


class Platform(str, enum.Enum):
    FACEBOOK_FEED = "facebook_feed"
    INSTAGRAM_FEED = "instagram_feed"
    INSTAGRAM_STORY = "instagram_story"
    FACEBOOK_STORY = "facebook_story"


HOOK_STYLE_MAP = {
    ("parent", "awareness"): HookStyle.FEAR,
    ("parent", "conversion"): HookStyle.SOCIAL_PROOF,
    ("student", "awareness"): HookStyle.QUESTION,
    ("student", "conversion"): HookStyle.STAT,
}

LENGTH_TARGET_MAP = {
    Platform.FACEBOOK_FEED: 125,
    Platform.INSTAGRAM_FEED: 100,
    Platform.INSTAGRAM_STORY: 75,
    Platform.FACEBOOK_STORY: 75,
}

PROFILE_ID_MAP = {
    ("parent", "conversion"): "vt_sat_parent_conversion",
    ("student", "conversion"): "vt_sat_student_conversion",
    ("parent", "awareness"): "vt_sat_parent_awareness",
    ("student", "awareness"): "vt_sat_student_awareness",
}


class InferredBrief(BaseModel):
    """Resolved fields set by Brief.resolve_inferred()."""

    profile_id: str
    hook_style: Optional[HookStyle] = None
    ad_length_target: Optional[int] = None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


class Brief(BaseModel):
    """Campaign brief. Call resolve_inferred() before passing to generator."""

    id: str = Field(default_factory=generate_id)
    audience: AudienceType
    campaign_goal: CampaignGoal
    product: str
    hook_style: Optional[HookStyle] = None
    platform: Optional[Platform] = None
    offer: Optional[str] = None
    urgency: Optional[str] = None
    social_proof: Optional[str] = None
    inferred: Optional[InferredBrief] = None
    created_at: str = Field(default_factory=_utc_now_iso)

    def resolve_inferred(self) -> "Brief":
        """Set inferred profile_id, hook_style, ad_length_target. Idempotent. Returns self."""
        if self.inferred is not None:
            return self
        aud = self.audience.value
        goal = self.campaign_goal.value
        profile_id = PROFILE_ID_MAP.get((aud, goal), "vt_sat_parent_conversion")
        hook = self.hook_style
        if hook is None:
            hook = HOOK_STYLE_MAP.get((aud, goal))
        ad_length_target = None
        if self.platform is not None:
            ad_length_target = LENGTH_TARGET_MAP.get(self.platform)
        self.inferred = InferredBrief(
            profile_id=profile_id,
            hook_style=hook,
            ad_length_target=ad_length_target,
        )
        return self