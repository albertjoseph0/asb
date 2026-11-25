# ASB + Dalio Scoring Rubrics & Quality Gates

## Table of Contents
1. [Problem Score (`asb-problem`) Legal Scales & Math](#problem-score-asb-problem-legal-scales--math)
2. [Dalio Evidence Believability & Panel Weighting Math](#dalio-evidence-believability--panel-weighting-math)
3. [Stranger-Sortable Target Market Gate](#stranger-sortable-target-market-gate)
4. [Rude Q&A (`asb-rude-qa`) Interrogation Checklist](#rude-qa-asb-rude-qa-interrogation-checklist)
5. [Dalio Consequence, EV & Kill-Trigger Gate](#dalio-consequence-ev--kill-trigger-gate)
6. [Needs Stack, Provisional Carol, Positioning & Interview Gates](#needs-stack-provisional-carol-positioning--interview-gates)

---

## Problem Score (`asb-problem`) Legal Scales & Math

Formula:
```text
Score = (Plausible × Self_Aware × Lucrative × Liquid × Eager_Identity × Eager_Comparative × Enduring) ÷ 625,000
```

| # | Criterion | Legal Scale Values (Exact) | What It Measures |
| :--- | :--- | :--- | :--- |
| 1 | **Plausible** | `1000`, `10000`, `100000`, `1000000`, `10000000`, `100000000`, `1000000000` | Number of specific buyers who actually have the problem (`1k`–`1B`). Businesses: ~`100k` suffices; Consumers: ~`10M` needed. |
| 2 | **Self-Aware** | `0.01`, `0.1`, `0.5`, `1.0` | `0.01` few agree/care · `0.1` thought-leaders evangelize · `0.5` industry standard practice · `1.0` almost everyone cares. |
| 3 | **Lucrative** | `1`, `10`, `100`, `1000`, `10000`, `100000`, `1000000` | Demonstrated annual allocated **net revenue** budget (`$1`–`$1M`). Score demonstrated allocation, not wishful sticker price. |
| 4 | **Liquid** | `0.01`, `0.1`, `1.0` | `0.01` every few years / heavy lock-in · `0.1` annual decision · `1.0` always in market, easy to switch. |
| 5 | **Eager (Identity)** | `0`, `0.1`, `0.5`, `1.0` | `0` structurally barred (SOC 2/fiat/policy) · `0.1` structural trust challenges · `0.5` indifferent · `1.0` mission-level pull. |
| 6 | **Eager (Comparative)** | `0.1`, `0.5`, `1.0` | `0.1` no material differentiation · `0.5` strong reason some buy alone · `1.0` one-of-a-kind. |
| 7 | **Enduring** | `0.01`, `0.1`, `0.5`, `1.0` | `0.01` one-off, no loyalty · `0.1` one-off with referrals/repeat · `0.5` recurring problem/revenue · `1.0` strong lock-in / system of record. |

---

## Dalio Evidence Believability & Panel Weighting Math

### 1. Evidence Believability Index (EBI) & Bottleneck Believability
Legal per-criterion believability weights: **`0.2`**, **`0.35`** (synthetic cap), **`0.4`**, **`0.7`**, **`1.0`**.
```text
EBI = round(sum(believability_weights of all 7 criteria) / 7, 3)
Bottleneck_Believability = min(believability_weights of all 7 criteria)
```
Anti-inflation clamps (enforced in Python): `[fermi]` entries are clamped `<= 0.4`; `>= 0.7` requires cited source URLs.

### 2. Independent Believability-Weighted Specialist Panel Score & Numeric EV
Fixed domain-believability weights:
- `Phase 3 Problem Scorer` (independent): **`0.30`** (`>= 1.0` → `+1.0`, `0.5–0.99` → `0.0`, `< 0.5` → `-1.0`)
- `Phase 4A Rude Q&A Attacker`: **`0.40`** (`SHARPENED` → `+1.0`, `NOT_YET_READY` → `0.0`, `BAD_IDEA` → `-1.0`)
- `Phase 4B Consequence & EV Analyst`: **`0.30`** (`PURSUE_VALIDATION` → `+1.0`, `GATHER_MORE_EVIDENCE` → `0.0`, `KILL` → `-1.0`)

```text
Panel_Weighted_Score = round(0.30 * scorer_vote + 0.40 * attacker_vote + 0.30 * consequence_vote, 3)
Expected_ARR_USD     = round((p_viable_pct / 100.0) * target_arr_usd, 2)
EV_Per_Val_Hour      = round(Expected_ARR_USD / max(validation_hours, 1), 2)
```
- **Disagreement Flag:** `True` whenever `max(votes) - min(votes) >= 1.0`.
- **Strict Kill Gate:** Killed if `Attacker == BAD_IDEA`, OR `Consequence/EV == KILL`, OR `Post-Rude-Q&A Score < 0.5`, OR `Eager_Identity == 0`, OR `Panel_Weighted_Score <= 0.0`.

---

## Stranger-Sortable Target Market Gate

Before scoring any idea, it MUST define all four:
1. **Specific Buyer** (stranger-sortable behavioral/circumstantial definition).
2. **Specific Problem** (aware pain with observable current workaround/cost).
3. **Specific Product Trade-Offs** (deliberate refusals passing the Opposite Test).
4. **Specific Price & Pricing Strategy** (`More for More`, `More for Less`, or `Less for Less`).

---

## Rude Q&A (`asb-rude-qa`) Interrogation Checklist

1. **Opposite Test:** Construct the opposite of the core differentiator — if no smart company would pick it, kill or replace.
2. **Fluffy-Language Audit:** Strike *easy, robust, scalable, seamless, frictionless, best-in-class, innovative, AI-powered, world-class, solution, game-changing*.
3. **Real-Decision Coherence:** Named smart alternative rejected + negative consequence accepted + reinforcement across price/product/indie capacity.
4. **Present-Tense Threats (>=70% Bar):** Strike "could"/"might." Cite live competitors/platforms verified via `search_web`.
5. **Challenge From Below:** Attack the 2 softest Problem Score criteria — demand proof why the next legal value DOWN is wrong.

---

## Dalio Consequence, EV & Kill-Trigger Gate

Every surviving candidate must have:
1. **Root-Cause Persistence Diagnosis:** Structural explanation of *why* the pain still exists today.
2. **1st-, 2nd-, and 3rd-Order Consequences:** Explicit chain beyond Day-1 appeal.
3. **Numeric `P(Viable)` + Payoff Asymmetry:** Explicit percentage (never "likely"), realistic indie upside, and cheap pre-build validation cost.
4. **Pre-Committed Kill Trigger:** Concrete walk-away rule for the first 10–15 interviews.
5. **"How Could I Be Wrong?":** Explicit blind-spot statement from both Advocate and Consequence/EV Analyst.

---

## Needs Stack, Provisional Carol, Positioning & Interview Gates

- **Needs Stack (`asb-needs-stack`):** Customer's words, true means-to-an-end links, named real occupants, roles (`obviated` / `your_level` / `promise` / `aspiration` / `purpose`).
- **Provisional Carol (`asb-carol-*`):** Behavioral/attitudinal markers passing Marketing/Sales/Product bar; no demographic laziness; no averaged segments; Inciting Events tagged `OBSERVED-PUBLIC` (with URL) or `HYPOTHESIZED`.
- **Positioning (`asb-positioning`):** Value-first in buyer's scoreboard currency, aligned with declared pricing strategy, Opposite-Test passing, zero clichés, `[VERIFY: ...]` placeholders for unproven specifics.
- **Interview Questions (`asb-interview-questions`):** Open-ended, non-leading, single-answer, polite-stranger tested, probing past/current behavior (never "would you buy X?").
