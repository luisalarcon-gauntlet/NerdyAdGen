"""AdLibrary: repository pattern — only place raw DB queries live. All methods async."""

import json
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, List, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from src.models.ad import Ad, AdStatus
from src.models.evaluation import EvaluationResult, DimensionScore, ConfidenceLevel
from src.models.iteration import IterationRecord, QualityFailureRecord, FailureDiagnosis
from src.models.metrics import TokenUsageRecord
from src.models.scraped_ad import ScrapedAd


class AdLibrary:
    """Single access point for all database operations. Raw SQL lives here only."""

    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine
        self._session_factory = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False, autoflush=False
        )

    @asynccontextmanager
    async def db_session(self) -> AsyncGenerator[AsyncSession, None]:
        """Context manager for a single async session."""
        async with self._session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    async def save_ad(self, ad: Ad) -> None:
        """Upsert ad by id."""
        async with self.db_session() as session:
            await session.execute(
                text("""
                INSERT INTO ads (id, brief_id, status, primary_text, headline, description,
                    cta_button, image_url, image_prompt, final_score, created_at, updated_at)
                VALUES (:id, :brief_id, :status, :primary_text, :headline, :description,
                    :cta_button, :image_url, :image_prompt, :final_score, :created_at, :updated_at)
                ON CONFLICT (id) DO UPDATE SET
                    brief_id = EXCLUDED.brief_id, status = EXCLUDED.status,
                    primary_text = EXCLUDED.primary_text, headline = EXCLUDED.headline,
                    description = EXCLUDED.description, cta_button = EXCLUDED.cta_button,
                    image_url = EXCLUDED.image_url, image_prompt = EXCLUDED.image_prompt,
                    final_score = EXCLUDED.final_score, updated_at = EXCLUDED.updated_at
                """),
                {
                    "id": ad.id,
                    "brief_id": ad.brief_id,
                    "status": ad.status.value,
                    "primary_text": ad.primary_text,
                    "headline": ad.headline,
                    "description": ad.description,
                    "cta_button": ad.cta_button,
                    "image_url": ad.image_url,
                    "image_prompt": ad.image_prompt,
                    "final_score": ad.final_score,
                    "created_at": ad.created_at,
                    "updated_at": ad.updated_at,
                },
            )

    async def get_ad(self, ad_id: str) -> Optional[Ad]:
        """Return ad by id or None."""
        async with self.db_session() as session:
            r = await session.execute(
                text("SELECT id, brief_id, status, primary_text, headline, description, "
                     "cta_button, image_url, image_prompt, final_score, created_at, updated_at "
                     "FROM ads WHERE id = :id"),
                {"id": ad_id},
            )
            row = r.mappings().first()
        if not row:
            return None
        return Ad(
            id=row["id"],
            brief_id=row["brief_id"] or "",
            status=AdStatus(row["status"]) if row["status"] else AdStatus.DRAFT,
            primary_text=row["primary_text"] or "",
            headline=row["headline"] or "",
            description=row["description"] or "",
            cta_button=row["cta_button"] or "",
            image_url=row["image_url"],
            image_prompt=row["image_prompt"],
            final_score=row["final_score"],
            created_at=row["created_at"] or "",
            updated_at=row["updated_at"],
        )

    async def get_publishable_ads(
        self,
        audience: Optional[str] = None,
        campaign_goal: Optional[str] = None,
    ) -> List[Ad]:
        """Return published ads, optionally filtered by audience and campaign_goal via briefs."""
        async with self.db_session() as session:
            if audience or campaign_goal:
                q = """
                SELECT a.id, a.brief_id, a.status, a.primary_text, a.headline, a.description,
                    a.cta_button, a.image_url, a.image_prompt, a.final_score, a.created_at, a.updated_at
                FROM ads a
                LEFT JOIN briefs b ON a.brief_id = b.id
                WHERE a.status = 'published'
                """
                params: dict = {}
                if audience:
                    q += " AND b.audience = :audience"
                    params["audience"] = audience
                if campaign_goal:
                    q += " AND b.campaign_goal = :campaign_goal"
                    params["campaign_goal"] = campaign_goal
                r = await session.execute(text(q), params)
            else:
                r = await session.execute(
                    text("SELECT id, brief_id, status, primary_text, headline, description, "
                         "cta_button, image_url, image_prompt, final_score, created_at, updated_at "
                         "FROM ads WHERE status = 'published'"),
                )
            rows = r.mappings().all()
        return [
            _row_to_ad(row)
            for row in rows
        ]

    async def get_quality_trend(self, window: int = 10) -> List[dict]:
        """Return list of {attempt_number, avg_score, ...} sorted by attempt_number ascending."""
        async with self.db_session() as session:
            r = await session.execute(
                text("""
                SELECT e.attempt_number, AVG(e.weighted_score) AS avg_score
                FROM evaluations e
                GROUP BY e.attempt_number
                ORDER BY e.attempt_number ASC
                LIMIT :limit
                """),
                {"limit": max(window, 100)},
            )
            rows = r.mappings().all()
        return [dict(row) for row in rows]

    async def get_performance_per_token(self) -> dict:
        """North star: quality_per_dollar = avg_quality_published / (total_cost / published_count)."""
        async with self.db_session() as session:
            r = await session.execute(
                text("""
                SELECT COUNT(*) AS total, COALESCE(SUM(final_score), 0) AS sum_score
                FROM ads WHERE status = 'published'
                """),
            )
            pub = r.mappings().first()
            r2 = await session.execute(
                text("SELECT COALESCE(SUM(cost_usd), 0) AS total_cost FROM token_usage"),
            )
            cost_row = r2.mappings().first()
            r3 = await session.execute(text("SELECT COUNT(*) AS total FROM ads"))
            total_gen = (r3.mappings().first() or {}).get("total") or 0
        total_pub = (pub["total"] or 0) or 1
        sum_score = (pub["sum_score"] or 0) or 0.0
        total_cost = (cost_row["total_cost"] or 0) or 0.001
        avg_quality = sum_score / total_pub
        quality_per_dollar = avg_quality / (total_cost / total_pub) if total_cost else 0.0
        return {
            "quality_per_dollar": quality_per_dollar,
            "total_api_cost_usd": total_cost,
            "published_count": total_pub,
            "total_generated": total_gen,
        }

    async def mark_brief_complete(self, run_id: str, brief_id: str) -> None:
        """Persist (run_id, brief_id) checkpoint."""
        from datetime import datetime, timezone
        async with self.db_session() as session:
            await session.execute(
                text("""
                INSERT INTO batch_checkpoints (run_id, brief_id, completed_at)
                VALUES (:run_id, :brief_id, :completed_at)
                ON CONFLICT (run_id, brief_id) DO UPDATE SET completed_at = EXCLUDED.completed_at
                """),
                {"run_id": run_id, "brief_id": brief_id, "completed_at": datetime.now(timezone.utc).isoformat()},
            )

    async def get_completed_briefs(self, run_id: str) -> List[str]:
        """Return list of brief_ids completed for this run_id."""
        async with self.db_session() as session:
            r = await session.execute(
                text("SELECT brief_id FROM batch_checkpoints WHERE run_id = :run_id ORDER BY completed_at"),
                {"run_id": run_id},
            )
            rows = r.mappings().all()
        return [row["brief_id"] for row in rows if row.get("brief_id")]

    async def save_brief(self, brief: "Brief") -> None:
        """Persist brief for join in get_publishable_ads."""
        from src.models.brief import Brief
        b = brief
        async with self.db_session() as session:
            await session.execute(
                text("""
                INSERT INTO briefs (id, audience, campaign_goal, product, hook_style, platform,
                    offer, urgency, social_proof, inferred_profile_id, inferred_length_target, created_at)
                VALUES (:id, :audience, :campaign_goal, :product, :hook_style, :platform,
                    :offer, :urgency, :social_proof, :profile_id, :length_target, :created_at)
                ON CONFLICT (id) DO UPDATE SET
                    audience = EXCLUDED.audience, campaign_goal = EXCLUDED.campaign_goal,
                    product = EXCLUDED.product, hook_style = EXCLUDED.hook_style,
                    platform = EXCLUDED.platform, offer = EXCLUDED.offer,
                    urgency = EXCLUDED.urgency, social_proof = EXCLUDED.social_proof,
                    inferred_profile_id = EXCLUDED.inferred_profile_id,
                    inferred_length_target = EXCLUDED.inferred_length_target
                """),
                {
                    "id": b.id,
                    "audience": b.audience.value if hasattr(b.audience, "value") else str(b.audience),
                    "campaign_goal": b.campaign_goal.value if hasattr(b.campaign_goal, "value") else str(b.campaign_goal),
                    "product": getattr(b, "product", ""),
                    "hook_style": b.hook_style.value if b.hook_style and hasattr(b.hook_style, "value") else None,
                    "platform": b.platform.value if b.platform and hasattr(b.platform, "value") else None,
                    "offer": getattr(b, "offer", None),
                    "urgency": getattr(b, "urgency", None),
                    "social_proof": getattr(b, "social_proof", None),
                    "profile_id": b.inferred.profile_id if getattr(b, "inferred", None) else None,
                    "length_target": b.inferred.ad_length_target if getattr(b, "inferred", None) else None,
                    "created_at": getattr(b, "created_at", ""),
                },
            )

    async def save_evaluation(self, evaluation: EvaluationResult) -> None:
        """Persist evaluation and dimension_scores."""
        async with self.db_session() as session:
            await session.execute(
                text("""
                INSERT INTO evaluations (id, ad_id, attempt_number, weighted_score, knockout_passed,
                    knockout_failures, requires_human_review, flags, confidence, confidence_level, created_at)
                VALUES (:id, :ad_id, :attempt_number, :weighted_score, :knockout_passed,
                    :knockout_failures, :requires_human_review, :flags, :confidence, :confidence_level, :created_at)
                """),
                {
                    "id": evaluation.id,
                    "ad_id": evaluation.ad_id,
                    "attempt_number": evaluation.attempt_number,
                    "weighted_score": evaluation.weighted_score,
                    "knockout_passed": evaluation.knockout_passed,
                    "knockout_failures": json.dumps(evaluation.knockout_failures),
                    "requires_human_review": evaluation.requires_human_review,
                    "flags": json.dumps(evaluation.flags),
                    "confidence": evaluation.confidence,
                    "confidence_level": evaluation.confidence_level.value,
                    "created_at": evaluation.created_at,
                },
            )
            for ds in evaluation.dimension_scores:
                await session.execute(
                    text("""
                    INSERT INTO dimension_scores (id, evaluation_id, dimension, score, rationale, self_confidence)
                    VALUES (:id, :evaluation_id, :dimension, :score, :rationale, :self_confidence)
                    """),
                    {
                        "id": ds.id,
                        "evaluation_id": evaluation.id,
                        "dimension": ds.dimension,
                        "score": ds.score,
                        "rationale": ds.rationale,
                        "self_confidence": ds.self_confidence,
                    },
                )

    async def save_iteration_record(self, record: IterationRecord) -> None:
        """Persist iteration record."""
        async with self.db_session() as session:
            await session.execute(
                text("""
                INSERT INTO iterations (id, ad_id, attempt_number, tier, target_dimension, strategy,
                    score_before, score_after, dimensions_improved, dimensions_regressed,
                    oscillation_detected, cost_usd, created_at)
                VALUES (:id, :ad_id, :attempt_number, :tier, :target_dimension, :strategy,
                    :score_before, :score_after, :dim_improved, :dim_regressed,
                    :oscillation_detected, :cost_usd, :created_at)
                """),
                {
                    "id": record.id,
                    "ad_id": record.ad_id,
                    "attempt_number": record.attempt_number,
                    "tier": record.tier,
                    "target_dimension": record.target_dimension,
                    "strategy": record.strategy,
                    "score_before": record.score_before,
                    "score_after": record.score_after,
                    "dim_improved": json.dumps(record.dimensions_improved),
                    "dim_regressed": json.dumps(record.dimensions_regressed),
                    "oscillation_detected": record.oscillation_detected,
                    "cost_usd": record.cost_usd,
                    "created_at": record.created_at,
                },
            )

    async def save_token_usage(self, record: TokenUsageRecord) -> None:
        """Persist token usage."""
        async with self.db_session() as session:
            await session.execute(
                text("""
                INSERT INTO token_usage (id, ad_id, brief_id, operation, provider, model,
                    input_tokens, output_tokens, cost_usd, created_at)
                VALUES (:id, :ad_id, :brief_id, :operation, :provider, :model,
                    :input_tokens, :output_tokens, :cost_usd, :created_at)
                """),
                {
                    "id": record.id,
                    "ad_id": record.ad_id,
                    "brief_id": record.brief_id,
                    "operation": record.operation,
                    "provider": record.provider,
                    "model": record.model,
                    "input_tokens": record.input_tokens,
                    "output_tokens": record.output_tokens,
                    "cost_usd": record.cost_usd,
                    "created_at": record.created_at,
                },
            )

    async def save_failure_record(self, record: QualityFailureRecord) -> None:
        """Persist quality failure record."""
        from datetime import datetime, timezone
        created = datetime.now(timezone.utc).isoformat()
        async with self.db_session() as session:
            await session.execute(
                text("""
                INSERT INTO quality_failure (id, ad_id, brief_id, attempt_number, failure_pattern,
                    diagnosis_summary, diagnosis_suggested_action, created_at)
                VALUES (:id, :ad_id, :brief_id, :attempt_number, :failure_pattern,
                    :summary, :action, :created_at)
                """),
                {
                    "id": record.id,
                    "ad_id": record.ad_id,
                    "brief_id": record.brief_id,
                    "attempt_number": record.attempt_number,
                    "failure_pattern": record.failure_pattern.value,
                    "summary": record.diagnosis.summary,
                    "action": record.diagnosis.suggested_action,
                    "created_at": created,
                },
            )

    async def save_competitor_ad(self, ad: ScrapedAd) -> None:
        """Upsert a ScrapedAd into reference_ads. Uses ad_library_id for conflict resolution."""
        async with self.db_session() as session:
            await session.execute(
                text("""
                INSERT INTO reference_ads (
                    id, ad_library_id, competitor, primary_text, headline, description,
                    cta_button, platform, ad_format, is_active, carousel_id, raw_html,
                    calibration_quality, calibration_score, scraped_at
                ) VALUES (
                    :id, :ad_library_id, :competitor, :primary_text, :headline, :description,
                    :cta_button, :platform, :ad_format, :is_active, :carousel_id, :raw_html,
                    :calibration_quality, :calibration_score, :scraped_at
                )
                ON CONFLICT (ad_library_id) DO UPDATE SET
                    competitor = EXCLUDED.competitor,
                    primary_text = EXCLUDED.primary_text,
                    headline = EXCLUDED.headline,
                    description = EXCLUDED.description,
                    cta_button = EXCLUDED.cta_button,
                    platform = EXCLUDED.platform,
                    ad_format = EXCLUDED.ad_format,
                    is_active = EXCLUDED.is_active,
                    carousel_id = EXCLUDED.carousel_id,
                    raw_html = EXCLUDED.raw_html,
                    calibration_quality = EXCLUDED.calibration_quality,
                    calibration_score = EXCLUDED.calibration_score,
                    scraped_at = EXCLUDED.scraped_at
                """),
                {
                    "id": ad.ad_library_id,
                    "ad_library_id": ad.ad_library_id,
                    "competitor": ad.competitor,
                    "primary_text": ad.primary_text,
                    "headline": ad.headline,
                    "description": ad.description,
                    "cta_button": ad.cta_button,
                    "platform": ad.platform,
                    "ad_format": ad.ad_format,
                    "is_active": ad.is_active,
                    "carousel_id": ad.carousel_id,
                    "raw_html": ad.raw_html,
                    "calibration_quality": ad.calibration_quality,
                    "calibration_score": ad.calibration_score,
                    "scraped_at": ad.scraped_at,
                },
            )

    async def get_competitor_ads(self, competitor: Optional[str] = None) -> List[ScrapedAd]:
        """Return scraped reference ads, optionally by competitor."""
        async with self.db_session() as session:
            if competitor:
                r = await session.execute(
                    text("SELECT * FROM reference_ads WHERE competitor = :c"),
                    {"c": competitor},
                )
            else:
                r = await session.execute(text("SELECT * FROM reference_ads"))
            rows = r.mappings().all()
        return [_row_to_scraped_ad(row) for row in rows]

    async def get_dimension_averages(self) -> dict:
        """Return average score per dimension across evaluations."""
        async with self.db_session() as session:
            r = await session.execute(
                text("SELECT dimension, AVG(score) AS avg_score FROM dimension_scores GROUP BY dimension"),
            )
            rows = r.mappings().all()
        return {row["dimension"]: float(row["avg_score"]) for row in rows}

    async def get_cost_trend(self) -> List[dict]:
        """Return cost trend data."""
        async with self.db_session() as session:
            r = await session.execute(
                text("SELECT * FROM token_usage ORDER BY created_at"),
            )
            rows = r.mappings().all()
        return [dict(row) for row in rows]

    async def get_failure_patterns(self) -> dict:
        """Return count per FailurePattern for abandoned ads."""
        async with self.db_session() as session:
            r = await session.execute(
                text("SELECT failure_pattern, COUNT(*) AS cnt FROM quality_failure GROUP BY failure_pattern"),
            )
            rows = r.mappings().all()
        return {row["failure_pattern"]: row["cnt"] for row in rows}


def _row_to_ad(row: Any) -> Ad:
    return Ad(
        id=row["id"],
        brief_id=row["brief_id"] or "",
        status=AdStatus(row["status"]) if row.get("status") else AdStatus.DRAFT,
        primary_text=row["primary_text"] or "",
        headline=row["headline"] or "",
        description=row["description"] or "",
        cta_button=row["cta_button"] or "",
        image_url=row.get("image_url"),
        image_prompt=row.get("image_prompt"),
        final_score=row.get("final_score"),
        created_at=row.get("created_at") or "",
        updated_at=row.get("updated_at"),
    )


def _row_to_scraped_ad(row: Any) -> ScrapedAd:
    return ScrapedAd(
        ad_library_id=row.get("ad_library_id") or "",
        competitor=row.get("competitor") or "",
        primary_text=row.get("primary_text"),
        headline=row.get("headline"),
        description=row.get("description"),
        cta_button=row.get("cta_button"),
        platform=row.get("platform"),
        ad_format=row.get("ad_format"),
        is_active=row.get("is_active", True),
        raw_html=row.get("raw_html") or "",
        scraped_at=row.get("scraped_at") or "",
        carousel_id=row.get("carousel_id"),
        calibration_quality=row.get("calibration_quality"),
        calibration_score=row.get("calibration_score"),
    )
