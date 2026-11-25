# Ray Dalio's Decision-Making Principles in the ASB Indie Idea Foundry

## Table of Contents
1. [Why ASB + Dalio Fit Together](#why-asb--dalio-fit-together)
2. [Evidence Believability Scale (0.2 – 1.0)](#evidence-believability-scale-02--10)
3. [Believability-Weighted Specialist Panel & Dissent Protocol](#believability-weighted-specialist-panel--dissent-protocol)
4. [First-, Second-, and Third-Order Consequences](#first--second--and-third-order-consequences)
5. [Expected Value (EV) & Pre-Committed Kill Triggers](#expected-value-ev--pre-committed-kill-triggers)
6. [The 5-Step Process & Pain + Reflection = Progress](#the-5-step-process--pain--reflection--progress)
7. [Open-Mindedness: Guarding Against Ego & Blind Spots](#open-mindedness-guarding-against-ego--blind-spots)

---

## Why ASB + Dalio Fit Together

Jason Cohen's **ASB** framework answers *what makes an indie business viable and compelling* (Problem Score, Rude Q&A, Needs Stack, Carol, Positioning, Customer Interviews).
Ray Dalio's **Principles** answers *how a group of minds makes consistently high-quality decisions under uncertainty* (Idea Meritocracy, Radical Truth, Believability Weighting, Second/Third-Order Thinking, Expected Value, and Systematized Learning).

Together, they eliminate the three main failure modes of multi-agent ideation:
1. **Equal-weight consensus mush:** Averaging a well-researched critic with an ungrounded optimist.
2. **First-order seduction:** Chasing an obvious complaint ("Tool X is expensive") without tracing second- and third-order traps (high churn, platform bundling, support collapse).
3. **Static amnesia:** Killing ideas without diagnosing the *root cause* or updating the system's operating principles for the next run.

---

## Evidence Believability Scale (0.2 – 1.0)

Every criterion score and major claim carries an **Evidence Believability Weight**:

| Weight | Tier | Evidence Standard |
| :--- | :--- | :--- |
| **`1.0`** | **Primary Proof** | Direct primary source verified via URL or real human data: live competitor pricing page, public revenue/churn disclosure, regulatory mandate text, official API deprecation notice, or real human customer interview debrief (`interviews/`). |
| **`0.7`** | **Triangulated Field Signal** | 3+ independent firsthand public user reports (Reddit, G2/Capterra, HN, niche forums) describing the same pain, workaround, or spend. |
| **`0.4`** | **Single Anecdote / Secondary** | One public thread/review or a secondary analyst/blog estimate. Useful directionally, weak as proof. |
| **`0.35`** | **Grounded Synthetic Pre-Test (Cap)** | Blind, anti-sycophantic 4-persona synthetic interview dry-run (`synthetic-interviews/`). High value for catching leading questions, status-quo inertia, and obvious objections — strictly capped below real public/human evidence and NEVER eligible to mark hypotheses `✓ VALIDATED`. |
| **`0.2`** | **Pure Fermi / Model Guess** | Uncited order-of-magnitude reasoning. Legal for initial Fermi scoring, but explicitly drags down the **Evidence Believability Index** so the founder knows where certainty is thin. |

**Evidence Believability Index (EBI)** = arithmetic mean of the 7 criterion believability weights (`0.20` to `1.00`), paired with **Bottleneck Believability (`min`)** — both computed deterministically in Python so six `1.0` citations can never mask a single `0.2` fatal assumption. Anti-inflation rule: `[fermi]` criteria are strictly clamped `<= 0.4`, and `>= 0.7` requires cited source URLs.

---

## Believability-Weighted Specialist Panel & Dissent Protocol

In Dalio's Idea Meritocracy, decisions are NOT made by a single judge or a flat average. Each candidate that passes Phase 3 is evaluated by **three independent specialist lenses**, each weighted by its domain believability on indie startup viability:

| Specialist Role | Domain Believability Weight | Primary Authority |
| :--- | :--- | :--- |
| **Problem Scorer (Market Economist)** | **`0.30`** | Market size, demonstrated budget allocation, switching liquidity, recurring economics. |
| **Rude Q&A Attacker (Adversarial Skeptic)** | **`0.40`** | Competitive kill risks, present-tense threats, Opposite Test, structural deal-breakers (highest weight because false positives are far costlier than false negatives). |
| **Consequence & EV Analyst (Systems Thinker)** | **`0.30`** | 2nd/3rd-order consequences, root-cause persistence of the pain, indie execution asymmetry, Expected Value. |

### Deterministic Panel Vote Mapping
Each specialist emits a clear stance mapped numerically:
- `PURSUE_VALIDATION` / `SHARPENED` / `VIABLE (>=1.0)` → **`+1.0`**
- `GATHER_MORE_EVIDENCE` / `NOT_YET_READY` / `MARGINAL (0.5–0.99)` → **`0.0`**
- `KILL` / `BAD_IDEA` / `NOT_VIABLE (<0.5)` → **`-1.0`**

```text
Panel_Weighted_Score = (0.30 × Phase3_Scorer_Vote) + (0.40 × RudeQA_Attacker_Vote) + (0.30 × Consequence_EV_Vote)
```
*(Range: `-1.00` to `+1.00`. Crucially, `Phase3_Scorer_Vote` comes from the independent Phase 3 Problem Scorer — never from the Attacker's adjusted scorecard, preventing double-counting. An idea is killed if `Attacker == BAD_IDEA`, OR `Consequence/EV == KILL`, OR `Post-Rude-Q&A Score < 0.5`, OR `Eager_Identity == 0`, OR `Panel_Weighted_Score <= 0.0`.)*

### Mandatory Radical-Transparency Dissent Rule
- **Never average away a split.** Whenever any two specialists diverge by `>= 1.0` (e.g., Scorer says `+1.0` while Consequence/EV Analyst says `0.0` or `-1.0`), Python sets `disagreement_flag = true`.
- Every flagged disagreement is printed verbatim in `DECISION-RECORD.md` and `DECISION-MEMO.md` with **both causal chains** side-by-side so the founder can examine the exact crux and resolve it in real customer interviews.

---

## First-, Second-, and Third-Order Consequences

*"Failing to consider second- and third-order consequences is the cause of a lot of painfully bad decisions."*

For every candidate passing Phase 3, the **Consequence & EV Analyst** must explicitly trace:
1. **First-Order Consequence (Immediate / Obvious):** What happens on Day 1 if you build and launch this? (Usually looks positive — e.g., *"Angry users of Competitor X sign up at half price."*)
2. **Second-Order Consequence (Months 3–12):** What happens *because of* the first-order effect? (e.g., *"Half-price switchers demand full feature parity with Competitor X and flood a solo founder with support tickets; CAC payback stretches past 18 months."*)
3. **Third-Order Consequence (Years 1–3):** What structural equilibrium emerges? (e.g., *"Platform host ships the feature natively, or competitor drops price; solo founder is trapped in a high-churn commodity."* OR positive compounding: *"Becoming the workflow system of record creates organic peer referrals inside regional trade groups."*)

Also required: **Root-Cause Market Diagnosis** — *"If this pain is real and lucrative, what is the root cause explaining why incumbents haven't already solved it cleanly?"* (Good indie root causes: too small for VC/enterprise ACV, incumbent business-model conflict, unbundled vertical workflow. Bad root causes: buyers won't pay, fatal switching lock-in, platform gatekeeper risk.)

---

## Expected Value (EV) & Pre-Committed Kill Triggers

Dalio frames decisions as **Expected Value calculations**:
```text
EV = (P(Right) × Upside) - (P(Wrong) × Downside)
```
In pre-build indie ideation, you improve EV two ways:
1. **Drive Downside toward zero before building:** Spend 2–3 weeks on 10–15 customer interviews instead of 6 months writing code.
2. **Raise `P(Right)` via targeted falsification:** Test the single highest-uncertainty, highest-impact assumption first.

Every surviving idea's `DECISION-RECORD.md` MUST declare:
- **Current `P(Viable)` estimate** (explicit percentage, e.g., `35%`, never fuzzy words like "likely") and what drives the uncertainty.
- **Payoff Asymmetry:** Realistic indie upside (e.g., `$15k MRR` / `$180k ARR` at 200 customers) vs. pre-build validation cost (e.g., `15 hrs + $0`).
- **Pre-Committed Kill Trigger:** Concrete, falsifiable walk-away rule agreed *before* attachment sets in (e.g., *"If fewer than 3 of 10 interviewed operators have paid >= $100/mo or spent >= 4 hrs/wk on this pain in the last 90 days, KILL the idea."*).

---

## The 5-Step Process & Pain + Reflection = Progress

Dalio's 5-Step Process structures the entire system loop:
1. **Goals:** Anchor to `founder/WHO-ME.md`, `founder/VOTERS.md`, and `principles/LEARNED-PRINCIPLES.md`.
2. **Identify Problems:** Scouts mine public pain; Scorers & Attackers expose weak links and fatal flaws.
3. **Diagnose to Root Causes:** For every killed idea, separate **proximate cause** (the symptom that failed the score) from **root cause** (the underlying structural or scouting error that produced the bad candidate).
4. **Design Plans:** Build `STRATEGY-BRIEF.md`, `VALIDATION-KIT.md`, and explicit Kill Triggers.
5. **Reflect & Evolve the Machine:** Every run emits **Candidate Learned Principles** in `DECISION-MEMO.md`. Approved principles are promoted into `principles/LEARNED-PRINCIPLES.md` and automatically injected into Phase 0 of every future run!

---

## Open-Mindedness: Guarding Against Ego & Blind Spots

- Every Advocate defense and Consequence/EV analysis MUST include an explicit **"How Could I Be Wrong?"** section naming the assumption whose reversal would flip its recommendation.
- Low scores, kills, and split panels are celebrated as **high-value truth**, never softened to protect morale.
