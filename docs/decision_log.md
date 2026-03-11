# Decision Log — Nerdy Ad Engine

Every architectural decision documented with rationale.
Written in real time — not retrofitted.

Format: What was decided. Why over the alternative. What it unlocks.

---

### Entry 1: Project Choice — Autonomous Ad Engine

*"Chose the Ad Engine over Live Session Analysis and AI Video Tutor. Backend/systems background maps directly to pipeline architecture: generate, evaluate, iterate, log. The project rewards engineering judgment over ML expertise, and the decision log and iteration methodology are explicitly weighted in scoring. Ad copy also has an objective quality proxy — publishable threshold with measurable improvement over cycles — that the other projects lack."*

---

### Entry 2: AI-Native Development Philosophy

*"Every layer of the system is built using AI tooling: scraping, generation, evaluation, iteration, code, and documentation. Cursor for code, Gemini for generation, Claude for judgment. This is itself a documented architectural decision — the system demonstrates what an AI-native ad pipeline looks like end to end, not just at the generation layer."*

---

### Entry 3: Language — Python

*"Python over Go. The pipeline is I/O bound — 95% of execution time is waiting on external APIs. Go's concurrency advantages are irrelevant here. Python has official SDKs for every integration: Gemini, Anthropic, Playwright, SQLAlchemy. Cursor generates more reliable Python for AI-heavy codebases. Fastest path to a working, testable pipeline."*

---

### Entry 4: Generator Model — Gemini 1.5 Flash

*"Gemini chosen for ad copy generation. Nerdy's explicit recommendation. Strong at following structured creative constraints and brand voice. Free tier supports generating 50+ ads during development. Gemini 1.5 Flash as default for cost efficiency — 1.5 Pro available as a quality escalation path for briefs that repeatedly fail quality threshold after Tier 2."*

---

### Entry 5: Judge Model — Claude Sonnet 4.6

*"Claude Sonnet 4.6 chosen exclusively for evaluation. The core design constraint is that generator and judge must be different models — a model evaluating its own output will score it higher than it deserves, degrading the quality signal the entire iteration loop depends on. Claude produces more reliable structured JSON output and stronger per-dimension rationale than Gemini in evaluation roles. This assignment is non-negotiable regardless of cost pressure."*

---

### Entry 6: Weight Profile Architecture

*"Weight profiles implemented as a two-layer hierarchy: reusable base profiles and client-specific overrides. ProfileRegistry resolves with graceful fallback — specific match, then generic goal match, then equal weights. Knockout thresholds modeled separately from weighted scores because they represent categorical rejection — a weighted average can mask a dealbreaker score in a single dimension. Registry accepts runtime registration to support V3 dynamic profile generation from competitive intelligence data."*

---

### Entry 7: Varsity Tutors SAT Weight Profiles — Exact Values

*"Four VT-specific profiles created for parent/student × awareness/conversion. Key deviations from base: parent profiles weight value proposition highest (0.30) — quantifiable outcomes and trust are the primary conversion drivers against Princeton Review and Kaplan. Student awareness weights emotional resonance highest (0.20) — test anxiety and peer pressure are the entry point. Student conversion weights CTA highest (0.30) — test date urgency is a real and specific pressure point. Quality threshold raised to 7.5 for both conversion profiles — higher bar reflects higher cost per conversion and lower tolerance for mediocre output in a decision-driving context."*

---

### Entry 8: Anchor-Based Rubric

*"LLM-as-judge uses anchor-based rubrics per dimension. Without explicit anchors, LLMs cluster toward middle scores, apply inconsistent standards across runs, and justify scores post-hoc rather than deriving them from criteria. Anchors define low, medium, and high bands using VT SAT-specific copy examples. Rubrics injected directly into the judge prompt so the model scores from criteria, not intuition. Calibration against reference ads is a required step before any generation — if the judge cannot reliably distinguish annotated good from annotated bad, the rubric is adjusted before production use."*

---

### Entry 9: Confidence Scoring — Hybrid Model

*"Fast mode (single-pass self-reported confidence) as default. High-confidence mode (three passes, variance-based confidence) triggered only when the weighted score falls within 0.75 points of the publishable threshold. Rationale: LLMs overstate confidence in single-pass evaluation, but tripling API costs for every ad wastes the cost budget. Expensive mode reserved for borderline cases where evaluation error has the highest consequence — a false positive near 7.0 would publish a bad ad; a false negative would abandon a good one. Dimension conflict detection implemented as deterministic post-processing from known conflict patterns, not LLM judgment."*

---

### Entry 10: Iteration Loop — Tiered Regeneration

*"Three-tier regeneration strategy before abandon. Tier 1 targets the weakest dimension with context-aware rewrite instructions (attempts 1–3). Tier 2 triggers full ad regeneration carrying forward what scored ≥ 7.0 (attempts 4–5). Tier 3 reinterprets the brief itself (attempt 6). Tier 4 abandons with full diagnosis (attempt 7+). Targeted regeneration in Tier 1 includes full surrounding copy context — isolated dimension rewrites produce ads where parts score well but the whole doesn't cohere. Oscillation detection escalates early to Tier 2 when the same two dimensions keep trading failures. Regression detection checks all five dimension scores after each attempt — not just the target dimension."*

---

### Entry 11: Quality Ratchet — Stubbed in V1

*"QualityRatchet class implemented in V1 but does not activate. In V1 it logs 'would_trigger' events for post-run analysis without changing any threshold. Rationale: the ratchet requires a meaningful sample of ad library data to make threshold adjustments meaningful — 50 ads is too few to reliably identify that the system has genuinely improved. Activates in V3 after multiple batch runs have established baseline performance distribution."*

---

### Entry 12: Brief Structure — Three-Tier

*"Brief uses required, optional, and inferred tiers. Required fields: audience, campaign_goal, product. Optional fields improve quality but have defaults. Inferred fields are computed automatically at runtime — hook style, length target, and profile ID have deterministic right answers from lookup maps that require no human input. Brief diversity matrix spans 216 combinations across audience, goal, hook style, offer, and urgency. Autonomous brief generation from competitive intelligence gaps stubbed for V3."*

---

### Entry 13: Database — Postgres on Railway

*"Postgres over SQLite. V3 requires concurrent agent writes — SQLite's single-writer lock would require mid-project architectural changes. Railway provisions Postgres via a single DATABASE_URL environment variable — operational overhead is minimal. SQLAlchemy async + Alembic: schema will evolve three times across versions and migration management is a production practice worth demonstrating. Local development runs Postgres in Docker, production on Railway — DATABASE_URL is the only difference."*

---

### Entry 14: Token and Cost Tracking

*"Token and cost tracking implemented as a first-class pipeline metric via decorator pattern — non-invasive, cannot be accidentally omitted. Four cost centers tracked independently: Gemini generation, Claude evaluation, Claude regeneration, Nano Banana (V2). CostCalculator is the single source of truth for provider pricing — rates updated in one file when providers change. North star metric: quality_per_dollar = avg_quality_of_published_ads ÷ (total_cost ÷ published_count). Abandoned ads contribute to total_cost but not to published_count — accurately penalizes expensive failed briefs. Expected finding: evaluation cost approximates generation cost, which motivates the V3 pre-filter stub."*

---

### Entry 15: LangSmith Observability

*"LangSmith chosen for LLM observability. @traceable decorator captures prompt I/O, token counts, costs, and chain traces automatically without custom instrumentation. Evaluation datasets used for calibration — annotated reference ads uploaded as a dataset, judge run programmatically against them, agreement rates visible in LangSmith UI. Prompt version tracking built in — every prompt change and its downstream effect on evaluation scores is automatically recorded. LangSmith circuit-broken out of critical path — its failure never blocks ad generation."*

---

### Entry 16: Failure Handling

*"Three failure types handled differently. API failures: exponential backoff with jitter for transient errors; circuit breaker opens after five consecutive failures per service, tests recovery after 60-second cooldown. Quality failures: abandoned ads saved to database with full iteration history and failure diagnosis — never silently dropped. Failure diagnosis classifies patterns as persistent weakness, oscillation, or stalled improvement. These records are the primary input for V3 self-healing — systematic failure patterns across multiple briefs indicate prompt or rubric problems, not individual ad problems. Batch runs checkpointed after every completed ad — interrupted runs resume from last checkpoint."*

---

### Entry 17: Human Review Gate

*"Human intervention triggered by system uncertainty, not system failure. Four trigger conditions: low judge confidence on borderline scores, systematic brief failure (same brief failing 3+ times), quality ratchet stall (V3), and brand voice knockout clustering (4 in last 10 ads). Each escalation includes trigger context and recommended action. HUMAN_REVIEW_ENABLED and HUMAN_REVIEW_URGENCY_MINIMUM flags allow suppression by urgency level — suppressed escalations still logged for calibration analysis. Human review never covers per-ad approval, real-time monitoring, or manual writing — those are not worth a human's time at scale."*

---

### Entry 18: Scraping Scope and Competitors

*"Four competitors scraped in priority order: Princeton Review (direct SAT prep competitor), Kaplan (positioning comparison), Khan Academy (contrasting ad model and price point), Chegg (lower priority broader edtech). Target 70–170 total ads — pattern recognition requires minimum 15–20 per competitor. Carousel cards extracted as individual records linked by parent ID — each card tests a different hook and must be evaluable individually. Calibration annotation is the one manual step at system initialization."*

---

### Entry 19: Quality Trend Visualization — Plotly

*"Plotly chosen over matplotlib (interactivity) and Streamlit (requires running infrastructure for a submission artifact). Single self-contained HTML file — no CDN, no server — is the right format for a submission package. Six panels cover all metrics the brief explicitly requires plus the failure pattern distribution that surfaces systemic issues. Streamlit stubbed for V3 where a live dashboard querying Postgres continuously is the appropriate tool."*

---

### Entry 20: V2 Visual Evaluation Dimensions

*"Five visual dimensions mirror text evaluation structure: brand consistency, scroll-stop potential, audience relevance, copy harmony, technical quality. Technical quality is the sole knockout — below 5.0 the image is automatically rejected. Combined ad score: text 65%, visual 35% — copy is more determinative of direct response performance on Meta than creative at this campaign stage. Copy harmony explicitly evaluates whether image and text pull in the same emotional direction — dissonance between visual and verbal tone is a common AI generation failure mode. All V2 components stubbed with NotImplementedError in V1."*

---

### Entry 21: V3 Agent Boundaries

*"Four agents, each with one cognitive task. Separation between Writer and Editor is the most important boundary — improvement and creation are different tasks and models perform better when not asked to do both simultaneously. Researcher never writes copy. Evaluator never generates or suggests. Orchestrator makes no creative or evaluative decisions. Claude powers the Evaluator exclusively in V3 as in V1 — judge model independence is non-negotiable regardless of cost pressure. In V1 all agents run stubs with identical interfaces — V3 activation deploys each as a separate Docker service without changing any agent code."*

---

### Entry 22: Nano Banana Integration

*"Nano Banana integrated via httpx REST client. Image dimensions specified per Meta platform specs — incorrect dimensions cause automatic cropping or rejection. Two variants per brief: student-centered process shot and outcome-centered success moment. Two variants chosen over more because additional variants multiply cost without proportional insight at batch scale. Negative prompt explicitly excludes stock photo aesthetic, watermarks, text overlays, and distorted faces — common generation failure modes that would trigger technical quality knockout."*

---

### Entry 23: A/B Variant Generation

*"Text variants use meaningfully different creative approaches — variant A follows the inferred hook style with problem-agitate-solve structure, variant B uses the contrast hook from a rotation map with proof-benefit-CTA structure. Variants test different emotional entry points for the same brief, not rewrites of the same idea. Both evaluated independently through the full iteration loop. Score delta tracked — large deltas indicate the brief combination is sensitive to hook style choice, informing future brief generation."*

---

### Entry 24: Calibration Methodology

*"Structured single-annotator annotation with three explicit quality bands. Pass threshold: 75% agreement. Below 50%: halt — rubric requires fundamental revision. 50–74%: adjust specific failing dimension anchors, rerun. 75%+: proceed. Single annotator is a documented limitation — inter-rater reliability would require multiple annotators and is deferred. Calibration rechecked after any significant prompt change. Minimum 20 annotated ads required before calibration check runs."*

---

### Entry 25: Submission Structure

*"README leads with results table — a recruiter should see quality scores and cost metrics before reading any technical explanation. One-command setup via docker-compose up --build. Alembic migrations run automatically on container start. Submission package includes interactive Plotly report, full evaluation JSON, CSV export, and cost report as top-level artifacts — reviewers should not need to run anything to see results."*

---

### Entry 26: Test Strategy — AI-TDD

*"AI-TDD adopted as the development methodology. Cursor writes failing tests first, receives approval, then implements until tests pass — never the reverse. Test specifications in MDC files are the behavioral contracts. Integration tests use real Postgres test database and mocked API clients — database correctness is worth testing, external API responses are not under our control. 12 minimum tests (9 unit, 3 integration) explicitly documented before any implementation begins."*

---

### Entry 28: Competitor Calibration Weight Profile

*"A dedicated weight profile (competitor_calibration) is used when scoring the 40 scraped competitor ads rather than reusing any VT production profile. Weights: Clarity 20%, Value Proposition 30%, CTA 20%, Brand Voice 15%, Emotional Resonance 15%. Rationale for each weight: Value Proposition is the heaviest (30%) because competitor ads live or die on their ability to express a specific, differentiated outcome — Princeton Review and Kaplan both compete on claimed score improvement numbers, so distinguishing weak from strong value propositions is the highest-signal dimension for competitive intelligence. Clarity and CTA are weighted equally (20% each) — clarity is the gate that determines whether a value proposition can be absorbed at scroll speed; CTA is the mechanism that converts intent to action, and both are necessary conditions for conversion-capable copy. Brand Voice and Emotional Resonance are weighted equally at 15% each — they are meaningful quality signals but secondary to the transactional dimensions for a direct-response calibration pass. Quality threshold of 7.0 matches the system-level QUALITY_THRESHOLD from env — any competitor ad scoring below this is flagged unpublishable, providing a concrete benchmark against which VT-generated ads must improve. No knockout thresholds apply for the competitor calibration pass — the goal is a continuous score distribution across the full ad set, not categorical filtering. Knockout filtering is reserved for VT ads entering the production pipeline."*

---

### Entry 27: Human Review — Two-Flag Architecture

*"Two environment flags rather than one: HUMAN_REVIEW_ENABLED and HUMAN_REVIEW_URGENCY_MINIMUM. A single on/off flag is too coarse — automated batch runs may want to suppress low-urgency escalations while still receiving high-urgency ones. URGENCY_MINIMUM provides this granularity without added complexity. Suppressed escalations are always logged with reason — post-run analysis can verify whether the urgency filter is calibrated correctly for the batch's actual signal rate."*
