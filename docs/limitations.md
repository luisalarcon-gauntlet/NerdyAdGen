# Limitations — Nerdy Ad Engine

Documented limitations and known failure modes.
Honest acknowledgment of what this system does not do well.

---

## Calibration

**Single annotator.** Calibration uses one annotator to label competitor ads as
low/medium/high quality. Without multiple annotators there is no inter-rater
reliability measurement — we cannot quantify how much annotation variance affects
evaluation accuracy. The 75% agreement threshold is calibrated against one person's
taste, not a validated standard.

*Mitigation:* Structured annotation bands (not freeform) and explicit anchor examples
reduce but do not eliminate individual subjectivity. A production system would require
minimum three annotators.

---

## Generation Prompts

**Calibrated for SAT prep only.** The generation prompt, brand voice guidelines, and
anchor-based rubrics are tuned specifically for Varsity Tutors SAT audience segments.
Applying this pipeline to a different product category — college advising, K-12 math
tutoring, or professional test prep — would require recalibrating generation prompts,
rubric anchors, and weight profile values. The system is not portable without work.

**Hook style rotation.** The brief diversity matrix rotates through six hook styles.
Some hook styles may be more appropriate for certain audience segments than others.
The mapping in `HOOK_STYLE_MAP` is based on reasoning about what should work, not
observed performance data. V3 competitive intelligence loop would replace this with
data-driven hook selection.

---

## Evaluation

**LLM consistency.** Even with anchor-based rubrics and low temperature, Claude will
produce slightly different scores for the same ad across runs. The single-pass fast
mode does not quantify this variance. High-confidence mode (three-pass) reduces
variance but only triggers near threshold. Score differences of ±0.3–0.5 on individual
dimensions should not be interpreted as meaningful signals.

**Self-reported confidence.** In fast mode, the confidence score is self-reported by
Claude in the same call that produces the scores. Self-reported confidence is
unreliable — models tend to overstate confidence in their own output. The three-pass
variance measurement is more reliable but more expensive.

**No ground truth.** Evaluation scores are not validated against actual ad performance
data (CTR, conversion rate, ROAS). The scoring framework predicts publishability based
on quality dimensions, not actual business outcomes. An ad that scores 8.5 may still
underperform in production.

---

## Scraping

**DOM dependency.** The Playwright scraper depends on Meta Ad Library's current DOM
structure. If Meta updates its UI, the scraper will break. Raw HTML is stored for
re-parsing, but the parser itself would need to be updated.

**Active ads only.** The scraper captures ads that are active at scrape time. Historical
performance data for inactive ads is not captured — the most informative ads (those
that ran for months) may no longer be visible.

**Volume limitation.** Meta Ad Library does not expose impression counts, spend levels,
or engagement metrics in its public interface. The system cannot distinguish a
high-performing ad from a low-performing one based on scrape data alone — only copy
patterns can be analyzed.

---

## Cost Tracking

**Hardcoded pricing.** `CostCalculator` rates are hardcoded. If Gemini or Anthropic
changes pricing, the cost report will be wrong until `RATES` is manually updated.
This is a maintenance issue, not a runtime error.

**Estimated not invoiced.** Costs are calculated from token counts and hardcoded rates,
not from actual provider invoices. Token count estimates from provider APIs can differ
slightly from what is actually billed.

---

## Iteration Loop

**No convergence guarantee.** The iteration loop has a maximum attempt ceiling but no
theoretical guarantee that quality improves across attempts. For difficult brief
combinations — highly specific audiences, very constrained value propositions — the
loop may exhaust attempts without reaching threshold. Failure diagnosis captures these
patterns for human review.

**Oscillation detection window.** Oscillation is detected over a window of the last
three attempts. A brief that oscillates slowly (every 4-5 attempts) would not be
detected by the current implementation.

---

## Quality Ratchet

**Stubbed in V1.** The ratchet does not activate. Published ads in V1 are always
evaluated against the fixed threshold from the weight profile. The ratchet's impact
on overall quality improvement cannot be measured from V1 results alone.

---

## Performance Per Token

**Excludes scraping cost.** The north star metric tracks generation and evaluation API
costs. Playwright scraping (CPU + time) and the annotation step (human time) are not
captured in the quality_per_dollar calculation. The reported cost is API cost only.

---

## Scope

**Text only in V1.** V1 generates and evaluates ad copy. Image generation (V2) and
the full visual evaluation loop are stubbed. Published ads in V1 have no creative —
the quality scores reflect copy quality only. Real Facebook/Instagram ad performance
depends on copy and creative together.

**No real Meta API integration.** Generated ads are published to the internal ad
library database. The pipeline does not submit ads to Meta's Ads Manager or validate
them against Meta's content policies. An ad that scores 8.5 in the pipeline may still
be rejected by Meta.
