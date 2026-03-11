# Nerdy Ad Engine

Autonomous Facebook/Instagram ad generation pipeline for Varsity Tutors SAT prep.

Generates ad copy, evaluates quality across five weighted dimensions, iterates on weak
dimensions, and surfaces only ads that meet a publishable quality threshold — with full
cost tracking, LangSmith observability, and a decision log that documents every
architectural choice.

---

## Results

| Metric | Value |
|---|---|
| Ads Generated | — |
| Ads Published | — |
| Publish Rate | — |
| Avg Quality Score (Published) | — |
| Total API Cost | — |
| Cost Per Published Ad | — |
| **Quality Per Dollar** | — |

*Populated after first full run. See `reports/quality_trend.html` for interactive charts.*

---

## Quick Start

```bash
# 1. Clone
git clone https://github.com/YOUR_USERNAME/nerdy-ad-engine
cd nerdy-ad-engine

# 2. Add API keys
cp .env.example .env
# Edit .env — add GEMINI_API_KEY, ANTHROPIC_API_KEY, LANGSMITH_API_KEY

# 3. Run
docker-compose up --build
```

The pipeline will:
1. Run database migrations automatically
2. Scrape competitor ads from the Meta Ad Library
3. Run calibration against reference ads (one manual annotation step — see below)
4. Generate 50+ ads across audience and goal combinations
5. Evaluate and iterate until quality threshold is met
6. Export reports to `reports/`

**Calibration annotation** is the one manual step. After scraping runs, execute:
```bash
docker-compose exec app python main.py annotate
```
Rate each competitor ad as `low`, `medium`, or `high` quality. Takes ~15 minutes for
70 ads. Then resume the pipeline — calibration check runs automatically.

---

## How It Works

```
Brief → [Gemini 1.5 Flash] Generate Ad
      → [Claude Sonnet 4.6] Evaluate (5 dimensions × profile weights)
      → Score ≥ threshold?
          Yes → Publish to library
          No  → Identify weakest dimension
               → Tier 1 (attempts 1-3): targeted dimension rewrite
               → Tier 2 (attempts 4-5): full ad regeneration
               → Tier 3 (attempt 6):   brief reinterpretation
               → Tier 4 (attempt 7+):  abandon + diagnose
```

**Generator and judge are always different models.** Gemini generates, Claude judges.
A model evaluating its own output scores it higher than it deserves.

---

## Quality Dimensions

Every ad scored 1–10 across five dimensions with goal-dependent weights:

| Dimension | Parent Conv. | Student Conv. | Parent Aware. | Student Aware. |
|---|---|---|---|---|
| Clarity | 0.20 | 0.20 | 0.25 | 0.20 |
| Value Proposition | 0.30 | 0.25 | 0.25 | 0.20 |
| CTA | 0.25 | 0.30 | 0.15 | 0.25 |
| Brand Voice | 0.15 | 0.10 | 0.20 | 0.15 |
| Emotional Resonance | 0.10 | 0.15 | 0.15 | 0.20 |

Publishable threshold: **7.0** (awareness) · **7.5** (conversion).

Knockout thresholds enforce per-dimension floors — an ad with a 4.8 clarity score
is rejected even if the weighted average passes.

---

## Versions

| Version | Status | What It Adds |
|---|---|---|
| V1 | ✅ Active | Text pipeline, 5-dimension evaluation, iteration loop, cost tracking |
| V2 | 🔲 Stub | Nano Banana image generation, visual evaluation, A/B visual variants |
| V3 | 🔲 Stub | Self-healing loop, quality ratchet, Researcher/Writer/Editor/Evaluator agents |

```bash
docker-compose up --build                                                          # V1
docker-compose -f docker-compose.yml -f docker-compose.v2.yml up --build         # V2
docker-compose -f docker-compose.yml -f docker-compose.v3.yml up --build         # V3
```

---

## Project Structure

```
nerdy-ad-engine/
├── .cursor/
│   ├── rules/              # Cursor behavior rules
│   │   ├── main.mdc        # Project identity, architecture rules, code style
│   │   └── tdd.mdc         # AI-TDD workflow — tests before implementation
│   └── mdc/                # Module-level context for Cursor
│       ├── models.mdc
│       ├── generate.mdc
│       ├── evaluate.mdc
│       ├── iterate.mdc
│       ├── output.mdc
│       ├── scraper.mdc
│       ├── utils.mdc
│       ├── agents.mdc
│       └── config_database.mdc
│
├── docs/
│   ├── decision_log.md     # 27 architectural decisions with rationale
│   └── limitations.md      # Documented limitations and known failure modes
│
├── src/
│   ├── models/             # Pydantic data models — no logic
│   ├── config/             # Settings, environment, DB connection
│   ├── scraper/            # Playwright Meta Ad Library scraper
│   ├── generate/           # Gemini ad copy generation
│   ├── evaluate/           # Claude LLM-as-judge evaluation
│   ├── iterate/            # Feedback loop, tier logic, batch runner
│   ├── output/             # Ad library (DB), reporter, Plotly visualizer
│   ├── agents/             # V3 stubs — all raise NotImplementedError in V1
│   ├── integrations/       # Nano Banana client — V2 stub
│   └── utils/              # Retry, circuit breaker, token tracking, logging
│
├── tests/
│   ├── unit/               # No DB, no API calls
│   ├── integration/        # Real Postgres, mocked APIs
│   ├── fixtures/           # Shared test data and mock responses
│   └── calibration/        # Real API calls — run manually
│
├── migrations/             # Alembic schema migrations
├── data/                   # Reference ads, pipeline logs
└── reports/                # Submission artifacts
```

---

## Running Tests

```bash
pytest tests/unit/ -v                              # Fast, no deps
pytest tests/integration/ -v                       # Needs Postgres
pytest tests/ -v --cov=src --cov-report=html       # Full + coverage
pytest tests/calibration/ -v -m calibration        # Manual — real API calls
```

---

## Environment Variables

Full documentation in `.env.example`. Required for V1:

```
GEMINI_API_KEY
ANTHROPIC_API_KEY
LANGSMITH_API_KEY
DATABASE_URL
```

---

## Key Decisions

All 27 decisions with full rationale in `docs/decision_log.md`. Highlights:

- **Gemini generates, Claude judges** — creation and evaluation use different models to eliminate self-grading bias
- **Goal-dependent weight profiles** — parent vs student, awareness vs conversion have different quality drivers
- **Anchor-based rubrics** — without anchors, LLMs cluster toward middle scores; anchors force calibrated judgment
- **Tiered regeneration** — targeted for Tier 1, full rewrite for Tier 2, brief revision for Tier 3
- **Postgres on Railway** — SQLite single-writer lock would require re-architecture for V3 concurrent agents
- **AI-TDD throughout** — Cursor writes failing tests first, implements until green, never the reverse

---

## Submission Artifacts

| File | Description |
|---|---|
| `reports/quality_trend.html` | Interactive Plotly report — open in browser |
| `reports/evaluation_report.json` | Full evaluation data for all 50+ ads |
| `reports/evaluation_report.csv` | CSV for spreadsheet review |
| `reports/cost_report.json` | Performance-per-token metrics |
| `docs/decision_log.md` | 27 architectural decisions |
| `docs/limitations.md` | Documented limitations |
