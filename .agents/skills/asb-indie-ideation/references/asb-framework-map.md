# Review of the 18 ASB Skills & Mapping to Multi-Agent Indie Ideation

## Table of Contents
1. [Executive Synthesis](#executive-synthesis)
2. [Skill-by-Skill Mapping](#skill-by-skill-mapping)
3. [Key Epistemic Adaptations for Autonomous Subagents](#key-epistemic-adaptations-for-autonomous-subagents)
4. [Handoff Boundary: Where This System Stops](#handoff-boundary-where-this-system-stops)

---

## Executive Synthesis

Jason Cohen's 18 *A Smart Bear* (`asb-*`) skills form a cohesive strategic operating system across six clusters. Almost all of them are designed as **human-facilitated Socratic exercises** that fight two founder diseases: *optimism bias* and *generic vagueness*.

When adapting them to a multi-agent ideation system for an indie startup, the core design principle is **separation of duties + epistemic labeling**:
- **Generator agents** are separated from **Scorer agents** and **Adversarial Attacker agents** so no agent grades its own homework.
- **Public desk research** (reviews, forums, pricing pages, job boards, regulatory shifts) is treated as *checkable external seed evidence*, never as a substitute for live customer conversations.
- **Downstream customer-truth skills** (Carol definition, positioning specifics, interview hypotheses/debriefs) are either marked strictly `PROVISIONAL` / `[VERIFY]` or emitted as *unowned starter templates* that hand off cleanly to the native `asb-*` skills when the founder goes into the field.

---

## Skill-by-Skill Mapping

### Cluster 1: Founder Self-Discovery & Decisive Advantage (Upstream Input)
| Skill | Canonical Artifact | Role in This System |
| :--- | :--- | :--- |
| `asb-who-me` | `WHO-ME.md` (`M1…`) | **Human-run upstream input** placed in `founder/WHO-ME.md`. Its drives steer domain scouting; its hindrances become hard exclusion filters ("games not to play"). |
| `asb-voters` | `VOTERS.md` (`V1–V2`) | **Human-run upstream input** placed in `founder/VOTERS.md`. Used by Idea Architect to bias toward ideas where the founder's extreme trait overpowers indie weaknesses, and by Scorers on `Eager (Identity)` & `Eager (Comparative)`. |

### Cluster 2: Business-Model Viability (Core Filter)
| Skill | Canonical Artifact | Role in This System |
| :--- | :--- | :--- |
| `asb-problem` | `PROBLEM-SCORE.md` | **Phase 3 (Problem Scorer subagents).** Enforces the stranger-sortable target market gate, Fermi-scores all 7 multiplying criteria (`Plausible × Self-Aware × Lucrative × Liquid × Eager_Identity × Eager_Comparative × Enduring ÷ 625,000`), challenges from below, and runs Scenario B niche narrowing when score `< 1.0`. Math is verified deterministically in Python. |

### Cluster 3: Constructive Devil's Advocate (Core Filter)
| Skill | Canonical Artifact | Role in This System |
| :--- | :--- | :--- |
| `asb-rude-qa` | `RUDE-QA.md` | **Phase 4 (Rude Q&A Court — Attacker vs. Advocate).** Applies the Opposite Test, fluffy-language audit, real-decision check, 70%+ present-tense threats backed by live web research, unfair questions, and the dwell rule. Forces a ternary verdict (`SHARPENED`, `NOT_YET_READY`, `BAD_IDEA`) — never "approximately fine." |

### Cluster 4: Ideal Customer ("Carol") Derivation (External Research + Provisional Pre-Launch Sketch)
| Skill | Canonical Artifact | Role in This System |
| :--- | :--- | :--- |
| `asb-carol-observations` | `OBSERVATIONS.md` (`O1…`) | **Phase 1 (Pain & Incumbent Scouts).** Directly borrows the skill's *External Research* posture: reverse-engineering public reviews, Reddit/HN threads, competitor complaints, and pricing as checkable seed material. |
| `asb-carol-strengths` | `STRENGTHS-WEAKNESSES.md` (`S/W`) | **Phase 2 & 5.** Used in reverse for pre-launch ideation: incumbent weaknesses and deliberate indie trade-offs (passing the Opposite Test) define the proposed product's `S/W` profile. |
| `asb-carol-keystones` | `KEYSTONES.md` (`K1…`) | **Phase 5 (Pre-Build Strategist).** Identifies the extreme customer circumstance that makes the indie product's core strength *required* (not merely preferred), gated on real segments. |
| `asb-carol-dealbreakers` | `DEALBREAKERS.md` (`D1…`) | **Phase 5 (Pre-Build Strategist).** Maps who will *never* buy from an indie product (anti-market) and hones keystone segments with concrete qualifiers. |
| `asb-carol-inciting-events` | `INCITING-EVENTS.md` (`E1…`) | **Phase 1 & 5.** Scouts capture *observed-public* triggers (outages, pricing hikes, compliance deadlines, platform deprecations); Strategist adds *hypothesized* triggers with exact search phrases and findability signals. |
| `asb-carol-define` | `CAROL.md` | **Phase 5 (Provisional Carol).** Synthesizes behavioral/attitudinal markers passing the Marketing/Sales/Product bar, refusing demographic laziness and segment averaging. Explicitly marked **PROVISIONAL — PRE-INTERVIEW**. |

### Cluster 5: Value Ladder & Positioning (Strategic Stress-Test)
| Skill | Canonical Artifact | Role in This System |
| :--- | :--- | :--- |
| `asb-needs-stack` | `NEEDS-STACK.md` (`N1…`) | **Phase 2 & 5.** Prevents building in an obviated dead-end by forcing the agents to name real occupants at your level, steps obviated below, the honest one-level-up promise, and threatening alternatives *above*. |
| `asb-positioning` | `POSITIONING.md` (`P1…`) | **Phase 5 (Positioning Audit).** Tests whether the idea can be pitched as *creating more value* in the buyer's scoreboard currency (not merely "saving time/money"), aligned with one pricing strategy (`More for More` / `More for Less` / `Less for Less`), passing the Opposite Test, with `[VERIFY]` tags for unproven specifics. |

### Cluster 6: Customer Discovery Interviews (Pre-Build Validation Handoff)
| Skill | Canonical Artifact | Role in This System |
| :--- | :--- | :--- |
| `asb-interview-goals` | `GOALS.md` (`G1…`) | **Phase 6 (Validation Planner).** Generates draft decision-traceable goal questions anchored directly to the scorecard's `[fermi]` assumptions and Rude Q&A open questions. |
| `asb-interview-hypotheses` | `HYPOTHESES.md` (`H1…`) | **Phase 6 (Draft Templates Only).** Emits falsifiable, numbered hypothesis *templates* marked **UNOWNED** so the founder runs `asb-interview-hypotheses` to revise and own them before interviewing. |
| `asb-interview-questions` | `QUESTIONS.md` (`Q1…`) | **Phase 6 (Draft Open Questions).** Generates open-ended, non-leading, single-answer questions (polite-stranger tested, zero "would you buy X?" referendums). |
| `asb-interview-debrief` | `interviews/*.md` | **Post-system human phase.** Never simulated by subagents. Run by the founder after each real conversation. |
| `asb-interview-learning` | Updated `H/Q` + log | **Post-system human phase.** Run after 5–10+ real debriefs to validate/tune/disprove hypotheses. |
| `asb-interview-report` | `FINAL-REPORT.md` (`F1…`) | **Post-system human phase.** Synthesizes real interview evidence before writing a single line of app code. |

---

## Key Epistemic Adaptations for Autonomous Subagents

1. **Public Evidence ≠ Human Validation.** Subagents can gather `[research]` evidence (`0.4–1.0`) for `Plausible`, `Lucrative`, `Self-Aware`, and `Eager`. Private buying behavior and exact willingness-to-pay remain `[fermi]` or `HYPOTHESIZED` until real human calls happen.
2. **Grounded Synthetic Pre-Tests Are Quarantined Stress-Tests (`0.35` Cap).** Blind, anti-sycophantic 4-persona synthetic interviews (`synthetic-interviews/`) are an approved *pre-flight dry run* to debug `QUESTIONS.md`, expose obvious workflow/status-quo objections, and test whether qualifier questions filter out the anti-market. They are strictly quarantined from real human `interviews/`, capped at Dalio Believability `0.35`, and can NEVER promote a hypothesis to `✓ VALIDATED`.
3. **Adversarial Isolation.** **Architect**, **Scorer**, **Rude Q&A Attacker**, **Consequence/EV Analyst**, and **Blind Personas** always execute in *separate* agent contexts.
4. **Truth Gate on Specifics.** Following `asb-positioning`, subagents never fabricate benchmarks, case studies, or real customer quotes. Unproven figures carry `[VERIFY: ...]`.

---

## Handoff Boundary: Where This System Stops

This system stops at **Stage 6 (Pre-Build Validation Kit)**:
- You get ranked ideas that survived Fermi math + Rude Q&A.
- You get a Graveyard of killed ideas explaining *why* they died.
- You get draft `GOALS.md`, `HYPOTHESES.md`, `QUESTIONS.md`, and real channels where Carol hangs out.
- **You do NOT get code, UI mockups, or simulated customer interviews.** The next step is picking 1 idea and talking to 10+ real prospects using the native `asb-interview-*` skills.
