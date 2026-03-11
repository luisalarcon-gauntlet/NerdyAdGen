"""PerformanceReporter: metrics aggregation and export."""

import csv
import json
from pathlib import Path
from typing import Any

from src.models.metrics import PerformanceMetrics


class PerformanceReporter:
    """Aggregates metrics from AdLibrary and exports JSON/CSV/cost report."""

    def __init__(self, library: Any) -> None:
        self._library = library

    def _quality_per_dollar(
        self, avg_quality: float, total_cost: float, published_count: int
    ) -> float:
        """quality_per_dollar = avg_quality / (total_cost / published_count)."""
        if published_count <= 0 or total_cost <= 0:
            return 0.0
        return avg_quality / (total_cost / published_count)

    def _cost_per_published_ad(self, total_cost: float, published_count: int) -> float:
        """total_cost / published_count."""
        if published_count <= 0:
            return 0.0
        return total_cost / published_count

    def _publish_rate(self, published_count: int, total_generated: int) -> float:
        """published_count / total_generated."""
        if total_generated <= 0:
            return 0.0
        return published_count / total_generated

    def _build_cost_report(
        self,
        total_generated: int,
        published_count: int,
        total_api_cost_usd: float,
        quality_per_dollar: float,
    ) -> dict:
        """Cost report with north_star and totals."""
        cost_per = self._cost_per_published_ad(total_api_cost_usd, published_count)
        return {
            "north_star": {
                "metric": "quality_per_dollar",
                "value": quality_per_dollar,
                "interpretation": (
                    f"Every $1 of API spend produces {quality_per_dollar:.2f} quality points "
                    "across published ads"
                ),
            },
            "totals": {
                "total_ads_generated": total_generated,
                "total_ads_published": published_count,
                "total_api_cost_usd": total_api_cost_usd,
                "cost_per_published_ad_usd": cost_per,
            },
            "by_model": {},
        }

    async def export_json(self, output_path: str) -> None:
        """Write evaluation report as valid JSON."""
        perf = await self._library.get_performance_per_token()
        trend = await self._library.get_quality_trend()
        data = {"performance": perf, "quality_trend": trend}
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(data, f, indent=2)

    async def export_csv(self, output_path: str) -> None:
        """Write quality trend CSV with header row."""
        trend = await self._library.get_quality_trend()
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", newline="") as f:
            if trend:
                w = csv.DictWriter(f, fieldnames=list(trend[0].keys()))
                w.writeheader()
                w.writerows(trend)
            else:
                f.write("attempt_number,avg_score\n")

    async def generate_cost_report(self, output_path: str) -> None:
        """Write cost_report.json with north_star and totals."""
        perf = await self._library.get_performance_per_token()
        total_gen = perf.get("total_generated", 0)
        pub_count = perf.get("published_count", 0)
        total_cost = perf.get("total_api_cost_usd", 0.0)
        qpd = perf.get("quality_per_dollar", 0.0)
        report = self._build_cost_report(total_gen, pub_count, total_cost, qpd)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w") as f:
            json.dump(report, f, indent=2)
