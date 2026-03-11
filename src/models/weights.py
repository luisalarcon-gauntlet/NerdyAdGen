"""DimensionWeights, KnockoutThresholds, WeightProfile, ProfileRegistry. No imports from other src/."""
from typing import Optional

from pydantic import BaseModel, Field, model_validator

from src.models.ids import generate_id


class DimensionWeights(BaseModel):
    """Weights for the five evaluation dimensions. Must sum to 1.0."""

    clarity: float
    value_proposition: float
    cta: float
    brand_voice: float
    emotional_resonance: float

    @model_validator(mode="after")
    def weights_sum_to_one(self) -> "DimensionWeights":
        total = (
            self.clarity
            + self.value_proposition
            + self.cta
            + self.brand_voice
            + self.emotional_resonance
        )
        if abs(total - 1.0) > 1e-9:
            raise ValueError("Weights must sum to 1.0")
        return self

    @model_validator(mode="after")
    def weights_non_negative(self) -> "DimensionWeights":
        for name, val in [
            ("clarity", self.clarity),
            ("value_proposition", self.value_proposition),
            ("cta", self.cta),
            ("brand_voice", self.brand_voice),
            ("emotional_resonance", self.emotional_resonance),
        ]:
            if val < 0:
                raise ValueError(f"Weight {name} must be >= 0")
        return self


class KnockoutThresholds(BaseModel):
    """Per-dimension minimum scores. None means no knockout for that dimension."""

    clarity: Optional[float] = None
    value_proposition: Optional[float] = None
    cta: Optional[float] = None
    brand_voice: Optional[float] = None
    emotional_resonance: Optional[float] = None


class KnockoutResult(BaseModel):
    """Result of applying knockout thresholds to dimension scores."""

    knockout_passed: bool
    knockout_failures: list[str]


def apply_knockouts(scores: dict[str, float], thresholds: KnockoutThresholds) -> KnockoutResult:
    """Check scores against thresholds. Inclusive lower bound (score >= threshold passes)."""
    failures: list[str] = []
    for dim in ["clarity", "value_proposition", "cta", "brand_voice", "emotional_resonance"]:
        thresh = getattr(thresholds, dim, None)
        if thresh is None:
            continue
        score = scores.get(dim)
        if score is not None and score < thresh:
            failures.append(dim)
    return KnockoutResult(knockout_passed=len(failures) == 0, knockout_failures=failures)


class WeightProfile(BaseModel):
    """Audience+goal profile with weights and knockout thresholds."""

    profile_id: str
    audience: str
    campaign_goal: str
    quality_threshold: float = 7.0
    weights: DimensionWeights
    knockout_thresholds: KnockoutThresholds = Field(default_factory=KnockoutThresholds)

    @model_validator(mode="after")
    def weights_must_sum_to_one(self) -> "WeightProfile":
        w = self.weights
        total = w.clarity + w.value_proposition + w.cta + w.brand_voice + w.emotional_resonance
        if abs(total - 1.0) > 1e-9:
            raise ValueError("Profile weights must sum to 1.0")
        return self


class ProfileRegistry:
    """Resolves weight profile by profile_id or (audience, campaign_goal)."""

    def __init__(self) -> None:
        self._by_id: dict[str, WeightProfile] = {}
        self._by_audience_goal: dict[tuple[str, str], WeightProfile] = {}
        self._base_goal: dict[str, WeightProfile] = {}
        self._base_equal: Optional[WeightProfile] = None

    def register(self, profile: WeightProfile) -> None:
        self._by_id[profile.profile_id] = profile
        self._by_audience_goal[(profile.audience, profile.campaign_goal)] = profile
        self._base_goal[profile.campaign_goal] = profile

    def register_base_goal(self, campaign_goal: str, profile: WeightProfile) -> None:
        self._base_goal[campaign_goal] = profile

    def register_base_equal(self, weights: DimensionWeights) -> None:
        self._base_equal = WeightProfile(
            profile_id="base_equal",
            audience="*",
            campaign_goal="*",
            weights=weights,
            knockout_thresholds=KnockoutThresholds(),
        )

    def resolve(
        self,
        *,
        profile_id: Optional[str] = None,
        audience: Optional[str] = None,
        campaign_goal: Optional[str] = None,
    ) -> WeightProfile:
        if profile_id is not None:
            if profile_id in self._by_id:
                return self._by_id[profile_id]
        if audience is not None and campaign_goal is not None:
            key = (audience, campaign_goal)
            if key in self._by_audience_goal:
                return self._by_audience_goal[key]
            if campaign_goal in self._base_goal:
                return self._base_goal[campaign_goal]
        if self._base_equal is not None:
            return self._base_equal
        raise KeyError("No profile found for given profile_id or audience/campaign_goal")


# Singleton registry with Varsity Tutors SAT profiles pre-registered
def _build_varsity_registry() -> ProfileRegistry:
    r = ProfileRegistry()
    r.register(VarsityTutorsSATProfiles.PARENT_CONVERSION)
    r.register(VarsityTutorsSATProfiles.STUDENT_CONVERSION)
    r.register(VarsityTutorsSATProfiles.PARENT_AWARENESS)
    r.register(VarsityTutorsSATProfiles.STUDENT_AWARENESS)
    return r


class VarsityTutorsSATProfiles:
    """Four fixed profiles for VT SAT. Use ProfileRegistry.resolve() for lookup."""

    PARENT_CONVERSION = WeightProfile(
        profile_id="vt_sat_parent_conversion",
        audience="parent",
        campaign_goal="conversion",
        quality_threshold=7.5,
        weights=DimensionWeights(
            clarity=0.20,
            value_proposition=0.30,
            cta=0.25,
            brand_voice=0.15,
            emotional_resonance=0.10,
        ),
        knockout_thresholds=KnockoutThresholds(clarity=5.0, cta=6.0, brand_voice=5.0),
    )
    STUDENT_CONVERSION = WeightProfile(
        profile_id="vt_sat_student_conversion",
        audience="student",
        campaign_goal="conversion",
        quality_threshold=7.5,
        weights=DimensionWeights(
            clarity=0.20,
            value_proposition=0.25,
            cta=0.30,
            brand_voice=0.10,
            emotional_resonance=0.15,
        ),
        knockout_thresholds=KnockoutThresholds(clarity=5.0, cta=6.0),
    )
    PARENT_AWARENESS = WeightProfile(
        profile_id="vt_sat_parent_awareness",
        audience="parent",
        campaign_goal="awareness",
        quality_threshold=7.0,
        weights=DimensionWeights(
            clarity=0.25,
            value_proposition=0.25,
            cta=0.15,
            brand_voice=0.20,
            emotional_resonance=0.15,
        ),
        knockout_thresholds=KnockoutThresholds(clarity=5.0, brand_voice=5.0),
    )
    STUDENT_AWARENESS = WeightProfile(
        profile_id="vt_sat_student_awareness",
        audience="student",
        campaign_goal="awareness",
        quality_threshold=7.0,
        weights=DimensionWeights(
            clarity=0.20,
            value_proposition=0.20,
            cta=0.25,
            brand_voice=0.15,
            emotional_resonance=0.20,
        ),
        knockout_thresholds=KnockoutThresholds(clarity=5.0, cta=5.0),
    )


# Module-level registry for resolve by audience/goal (used by brief resolution)
_profile_registry = _build_varsity_registry()


def get_profile_registry() -> ProfileRegistry:
    return _profile_registry
