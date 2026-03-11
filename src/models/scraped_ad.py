"""ScrapedAd model for reference ads from Meta Ad Library. No imports from other src/."""
from typing import Optional

from pydantic import BaseModel, model_validator


class ScrapedAd(BaseModel):
    """Reference ad from scraper. primary_text or headline must be present."""

    ad_library_id: str
    competitor: str
    primary_text: Optional[str] = None
    headline: Optional[str] = None
    description: Optional[str] = None
    cta_button: Optional[str] = None
    platform: Optional[str] = None
    ad_format: Optional[str] = None
    is_active: bool = True
    raw_html: str
    scraped_at: str
    carousel_id: Optional[str] = None
    calibration_quality: Optional[str] = None
    calibration_score: Optional[float] = None

    @model_validator(mode="after")
    def primary_text_or_headline_required(self) -> "ScrapedAd":
        if self.primary_text is None and self.headline is None:
            raise ValueError("primary_text or headline must be present")
        return self
