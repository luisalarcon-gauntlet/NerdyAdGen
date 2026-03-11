"""QualityTrendVisualizer: six-panel Plotly HTML, self-contained (no CDN)."""

from pathlib import Path
from typing import Any


class QualityTrendVisualizer:
    """Generates self-contained Plotly HTML with six panels. No external CDN."""

    def __init__(self, library: Any) -> None:
        self._library = library

    async def generate(self, output_path: str = "reports/quality_trend.html") -> None:
        """Produce six-panel HTML with Plotly embedded (include_plotlyjs=True)."""
        try:
            import plotly.graph_objects as go
            from plotly.subplots import make_subplots
        except ImportError:
            Path(output_path).parent.mkdir(parents=True, exist_ok=True)
            with open(output_path, "w") as f:
                f.write("<!DOCTYPE html><html><body><p>Plotly not installed.</p></body></html>")
            return

        trend = await self._library.get_quality_trend()
        perf = await self._library.get_performance_per_token()
        dim_avg = await self._library.get_dimension_averages()
        cost_trend = await self._library.get_cost_trend()
        failure_patterns = await self._library.get_failure_patterns()

        attempt_nums = [x.get("attempt_number") for x in trend if x.get("attempt_number") is not None]
        avg_scores = [x.get("avg_score") for x in trend if x.get("avg_score") is not None]
        if not attempt_nums:
            attempt_nums = [1]
            avg_scores = [0.0]

        fig = make_subplots(
            rows=2,
            cols=3,
            subplot_titles=(
                "Quality Score Over Cycles",
                "Publish Rate Over Cycles",
                "Dimension Score Radar",
                "Cost Per Published Ad",
                "Failure Pattern Distribution",
                "Performance Summary",
            ),
            specs=[
                [{"type": "scatter"}, {"type": "scatter"}, {"type": "scatterpolar"}],
                [{"type": "scatter"}, {"type": "bar"}, {"type": "table"}],
            ],
        )
        fig.add_trace(
            go.Scatter(x=attempt_nums, y=avg_scores, name="Avg Score", mode="lines+markers"),
            row=1,
            col=1,
        )
        fig.add_hline(y=7.0, line_dash="dash", line_color="red", row=1, col=1)

        pub_rate = 0.0
        if perf.get("total_generated"):
            pub_rate = (perf.get("published_count") or 0) / (perf["total_generated"] or 1)
        fig.add_trace(
            go.Scatter(x=attempt_nums, y=[pub_rate] * len(attempt_nums), name="Publish Rate", mode="lines"),
            row=1,
            col=2,
        )

        dims = list(dim_avg.keys()) or ["clarity", "cta", "value_proposition", "brand_voice", "emotional_resonance"]
        vals = [dim_avg.get(d, 0) for d in dims]
        fig.add_trace(
            go.Scatterpolar(r=vals + [vals[0]], theta=dims + [dims[0]], fill="toself", name="Dimensions"),
            row=1,
            col=3,
        )

        cost_per = 0.0
        if perf.get("published_count"):
            cost_per = (perf.get("total_api_cost_usd") or 0) / (perf["published_count"] or 1)
        fig.add_trace(
            go.Scatter(x=attempt_nums, y=[cost_per] * len(attempt_nums), name="Cost/Ad", mode="lines"),
            row=2,
            col=1,
        )

        pattern_names = list(failure_patterns.keys())
        pattern_counts = list(failure_patterns.values())
        fig.add_trace(
            go.Bar(x=pattern_names, y=pattern_counts, name="Failures"),
            row=2,
            col=2,
        )

        qpd = perf.get("quality_per_dollar", 0)
        fig.add_trace(
            go.Table(
                header=dict(values=["Metric", "Value"]),
                cells=dict(
                    values=[
                        ["quality_per_dollar", "total_published", "total_cost"],
                        [f"{qpd:.2f}", str(perf.get("published_count", 0)), f"${perf.get('total_api_cost_usd', 0):.4f}"],
                    ]
                ),
            ),
            row=2,
            col=3,
        )

        fig.update_layout(height=600, title_text="Quality Trend Report", showlegend=True)
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        fig.write_html(output_path, include_plotlyjs=True, config={"displayModeBar": True})
