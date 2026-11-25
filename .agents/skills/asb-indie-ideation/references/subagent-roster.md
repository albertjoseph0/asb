# Subagent Roster & Collaboration Protocol

## Table of Contents
1. [Tool Access Rule](#tool-access-rule)
2. [Role 1: Domain & Lens Strategist](#role-1-domain--lens-strategist)
3. [Role 2: Pain & Incumbent Scout](#role-2-pain--incumbent-scout)
4. [Role 3: Idea Architect](#role-3-idea-architect)
5. [Role 4: Problem Scorer (Market Economist — Panel Weight 0.30)](#role-4-problem-scorer-market-economist--panel-weight-030)
6. [Role 5A: Rude Q&A Court (Adversarial Skeptic — Panel Weight 0.40)](#role-5a-rude-qa-court-adversarial-skeptic--panel-weight-040)
7. [Role 5B: Dalio Consequence & EV Analyst (Systems Thinker — Panel Weight 0.30)](#role-5b-dalio-consequence--ev-analyst-systems-thinker--panel-weight-030)
8. [Role 6: Pre-Build Strategist](#role-6-pre-build-strategist)
9. [Role 7: Validation Planner](#role-7-validation-planner)
10. [Role 8: Post-Run Reflection Analyst (Pain + Reflection = Progress)](#role-8-post-run-reflection-analyst-pain--reflection--progress)

---

## Tool Access Rule

All subagents MUST run with `type_name="self"` (in `run_workflow`) or `TypeName="self"` (in `invoke_subagent`) so they inherit `search_web`, `read_file`, and optional `chrome-devtools-mcp` browser tools. Never use the offline `research` subagent.

Every subagent receives `principles/LEARNED-PRINCIPLES.md` in its context so the machine learns across runs.

---

## Role 1: Domain & Lens Strategist
- **When used:** When the user does not supply explicit domains.
- **Inputs:** `founder/` context + `principles/LEARNED-PRINCIPLES.md` + indie constraints.
- **Task:** Select 3 distinct, concrete, indie-friendly scouting lenses avoiding founder hindrances and past root-cause traps.

## Role 2: Pain & Incumbent Scout (Parallel Fan-Out)
- **Anchors:** `asb-carol-observations` (External Research), `asb-carol-inciting-events`, Dalio Primary Evidence standard.
- **Tools:** Heavy `search_web` across G2/Capterra/app-store 1–3 star reviews, Reddit/HN/vertical forums, live incumbent pricing pages, and regulatory/platform change notices.
- **Output:** 3–5 cited pain signals with real URLs, observed workaround/spend, incumbent pricing, live inciting events, and an **Evidence Believability Weight** (`1.0`, `0.7`, `0.4`).

## Role 3: Idea Architect
- **Anchors:** `asb-problem` Phase A, `asb-needs-stack`, `asb-positioning`, `principles/LEARNED-PRINCIPLES.md`.
- **Task:** Synthesize `N` distinct, stranger-sortable indie concepts grounded in `[SIG-#]`, with explicit Opposite-Test trade-offs, concrete price + pricing strategy, indie feasibility, and initial Needs Stack.

## Role 4: Problem Scorer (Market Economist — Panel Weight `0.30`)
- **Anchors:** `asb-problem` (7x Fermi rubric + Phase D Scenario B narrowing) + Dalio Evidence Believability.
- **Isolation:** Fresh context with zero loyalty to the Architect.
- **Task:**
  - Research via `search_web` and score Scenario A on legal scale values ONLY.
  - Assign an **Evidence Believability Weight** (`1.0 / 0.7 / 0.4 / 0.2`) to each criterion.
  - Apply **challenge from below**: prove why the next power of ten DOWN is wrong.
  - If Scenario A `< 1.0`, automatically propose and score **Scenario B** (sharper niche / repriced wedge).
  - Python computes `score`, `evidence_believability_index`, and the Scorer's panel stance deterministically.

## Role 5A: Rude Q&A Court (Adversarial Skeptic — Panel Weight `0.40`)
- **Anchors:** `asb-rude-qa` + Dalio Radical Truth & Thoughtful Disagreement.
- **Structure:** Separate stateful **Attacker** vs. **Advocate** (2 rounds):
  - **Attacker Turn 1:** Searches web to *kill* the idea (bundled incumbents, platform roadmaps, compliance walls). Runs Opposite Test, fluff audit, >=70% present-tense threats, unfair questions, and challenges the 2 softest scores from below.
  - **Advocate Turn 1:** Defends with concrete trade-offs or honest concessions + mandatory **"How Could I Be Wrong?"** check.
  - **Attacker Turn 2:** Emits final verdict (`SHARPENED` | `NOT_YET_READY` | `BAD_IDEA`), adjusted legal-scale scorecard (with updated believability weights), confidence (`0.0–1.0`), and open field questions.

## Role 5B: Dalio Consequence & EV Analyst (Systems Thinker — Panel Weight `0.30`)
- **Anchors:** Ray Dalio's Second/Third-Order Consequences, Root-Cause Diagnosis, Expected Value (EV), Pre-Committed Kill Triggers, Open-Mindedness.
- **Execution:** Runs in **parallel** with Role 5A in a completely independent agent context (triangulation without groupthink!).
- **Tools:** `search_web` to verify incumbent business models, platform bundling precedent, and churn/support dynamics in adjacent tools.
- **Outputs:**
  1. **Root-Cause Market Diagnosis:** Why does this pain still exist today? Is that root cause indie-favorable or a trap?
  2. **1st-, 2nd-, and 3rd-Order Consequences** (for founder, buyer, and competitors/platforms).
  3. **Expected Value & Payoff Asymmetry:** Explicit `P(viable)` (0–100%), upside band, pre-build validation cost, and the single highest-EV falsification test.
  4. **Pre-Committed Kill Trigger:** Concrete numerical walk-away threshold for the first 10–15 real interviews.
  5. **Independent Panel Stance:** `PURSUE_VALIDATION` (`+1.0`), `GATHER_MORE_EVIDENCE` (`0.0`), or `KILL` (`-1.0`), plus confidence (`0.0–1.0`) and **"How Could I Be Wrong?"**.

## Role 6: Pre-Build Strategist (Parallel on Top Survivors)
- **Anchors:** `asb-needs-stack`, `asb-carol-*`, `asb-positioning`.
- **Task:** Builds Needs Stack, `PROVISIONAL — PRE-INTERVIEW` Carol (keystones, deal-breakers, anti-market, inciting events), and value-first Positioning Audit with `[VERIFY]` placeholders.

## Role 7: Validation Planner (Parallel on Top Survivors)
- **Anchors:** `asb-interview-goals`, `asb-interview-hypotheses`, `asb-interview-questions` + Dalio EV falsification.
- **Task:** Produces `VALIDATION-KIT.md` directly targeting the scorecard's lowest-believability (`0.2–0.4`) criteria, any **Specialist Panel Disagreements**, and the **Pre-Committed Kill Trigger**, plus 4–6 web-verified communities to recruit real interviewees.

## Role 8: Post-Run Reflection Analyst (Pain + Reflection = Progress)
- **Anchors:** Dalio's 5-Step Process & Root-Cause Diagnosis.
- **Inputs:** All killed ideas, panel disagreements, synthetic red flags, and surviving scores from the run.
- **Task:** Separates **proximate causes** from **root causes** for every killed idea and proposes 2–4 concrete, non-generic **Candidate Learned Principles** (`DECISION-MEMO.md`) for the founder to promote into `principles/LEARNED-PRINCIPLES.md`.

## Role 9: Grounded Synthetic Interview Panel (Pre-Build Stress-Test — Cap `0.35`)
- **Anchors:** `references/synthetic-interview-protocol.md` + `asb-interview-questions` (live polite-stranger & script audit).
- **Sub-roles:**
  1. **Persona Architect:** Uses `search_web` (real job descriptions, Reddit/forum chatter, real tool stacks) to author **4 heterogeneous 7-part Persona System Prompts** (`bullseye_carol`, `status_quo_defender`, `skeptical_approver`, `anti_market_probe`) with explicit anti-sycophancy rules and zero knowledge of the startup idea.
  2. **Interviewer ↔ Blind Persona Pairs (Parallel, 3 Turns Each):** Stateful `interviewer` runs open-ended questions from `VALIDATION-KIT.md` (context → pain/coping/spend → switching & ASB price exception) against a strictly blind stateful `persona` agent.
  3. **Synthetic Debriefer & Script Auditor:** Maps each transcript to `Q#`/`[H#]` in quarantined `synthetic-interviews/SYNTH-*.md` files, catches leading-question leaks, surfaces red-flag objections, and writes `SYNTHETIC-INTERVIEW-REPORT.md` stamped `SYNTHETIC-PRE-TEST · Believability Cap 0.35`.
