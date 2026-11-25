# ASB Indie Idea Foundry — Workspace Rules

This workspace houses a multi-agent system uniting Jason Cohen's **A Smart Bear (ASB)** frameworks with **Ray Dalio's Decision-Making Principles** to discover, score, stress-test, triangulate, dry-run via grounded synthetic persona interviews, and prepare real-human field validation for indie startup ideas.

## Non-Negotiable Guardrails

1. **NO BUILDING YET.** Do not write application code, scaffold web/mobile apps, spin up MVPs, register domains, create landing pages, or build prototypes. The sole deliverable of this workspace is rigorously vetted entrepreneurial ideas, decision records, synthetic pre-test audits, and human field-validation plans.
2. **RADICAL TRUTH — NO VALIDATION THEATER.** Low scores, split panels, synthetic red flags, and killed ideas are successful outputs of this system. Never pad a Fermi score out of sympathy, never soften a Rude Q&A verdict into "approximately fine," never hide specialist disagreements, and never invent external statistics or real customer quotes.
3. **GROUNDED SYNTHETIC INTERVIEWS — STRICTLY QUARANTINED & BELIEVABILITY-CAPPED.**
   - Subagents MAY run **blind, anti-sycophantic synthetic persona interviews** using web-grounded 7-part persona system prompts (4 heterogeneous archetypes: Bullseye Carol, Status-Quo Defender, Skeptical Approver, Anti-Market Probe) to stress-test ideas, surface objections, and debug interview scripts *before* recruiting real humans.
   - **Hard Quarantine & Cap:** Every synthetic interview MUST live under `synthetic-interviews/` (never mixed into real human `interviews/`), MUST carry the stamp `SYNTHETIC-PRE-TEST`, and is capped at **Dalio Evidence Believability `0.35`**. Synthetic interviews can kill weak ideas, expose blind spots, and rewrite leading questions — they can **NEVER** mark a hypothesis `✓ VALIDATED` or replace real human conversations before building.
4. **BELIEVABILITY-WEIGHTED & SECOND-ORDER RIGOR (DALIO).**
   - Tag every evidence claim with its **Evidence Believability Weight** (`1.0` primary proof / real human interviews, `0.7` triangulated 3+ firsthand public reports, `0.4` single public anecdote/secondary, `0.35` grounded synthetic pre-test cap, `0.2` uncited Fermi).
   - Trace **1st-, 2nd-, and 3rd-order consequences**, **root-cause market persistence**, **Expected Value (EV)**, and **pre-committed Kill Triggers** for every surviving idea.
   - Surface every specialist disagreement explicitly instead of averaging it away.
   - Diagnose killed ideas to **root causes** and feed durable principles back into `principles/LEARNED-PRINCIPLES.md` (*Pain + Reflection = Progress*).
5. **CLEAR, NOT CLEVER.** State claims plainly. Eliminate marketing fluff, clichés, and generic words (*seamless, robust, scalable, easy, innovative, world-class, solution*). Every strategic claim must pass the **Opposite Test**.
6. **DETERMINISTIC MATH & LEGAL SCALES.** Problem Scores (`asb-problem`), Evidence Believability Indexes, and Believability-Weighted Panel Scores must be computed deterministically in Python (`product ÷ 625,000`), never eyeballed.

## Workspace Layout

- `founder/` — Founder self-portrait (`WHO-ME.md`, `VOTERS.md`) or `FOUNDER-PROFILE.md`. Read automatically by workflows when present.
- `principles/LEARNED-PRINCIPLES.md` — Living Dalio principle memory automatically read at Phase 0 of every run and evolved via post-run reflection.
- `.agents/skills/asb-indie-ideation/` — Core workspace skill and subagent role/rubric/Dalio/synthetic-interview references.
- `workflows/discover_ideas.py` — Full multi-agent discovery, Fermi scoring, Rude Q&A + Dalio Consequence/EV panel, validation kit, and optional grounded synthetic persona pre-test (`run_workflow`).
- `workflows/deep_dive_idea.py` — Deep single-idea ASB + Dalio decision dossier, validation kit, and grounded synthetic persona pre-test (`run_workflow`).
- `workflows/run_synthetic_interviews.py` — Standalone 4-persona blind synthetic interview stress-test & question-script auditor (`run_workflow`).
- `workflows/reverse_founder_fit.py` — Inverse Founder-Market Fit workflow (`run_workflow`): works backwards from vetted ideas to produce `FOUNDER-FIT-BLUEPRINT.md` (Ideal Founder Archetype, Required Voters, Personal Hell anti-archetype, 30-day ramp-up curriculum, Co-Founder complement, and 6-question Self-Fit Mirror).
- `scripts/validate_scorecard.py` — Deterministic Fermi math, Evidence Believability, Panel Weighting, synthetic quarantine, and artifact verifier.
- `runs/<run-id>/` — Generated discovery runs (`SHORTLIST.md`, `DECISION-MEMO.md`, `KILLED-IDEAS.md`, `PAIN-SIGNALS.md`, and per-idea dossiers including `DECISION-RECORD.md` and `synthetic-interviews/`).

## How to Operate in This Workspace

- When the user asks to **find, discover, brainstorm, evaluate, stress-test, or dry-run synthetic interviews on indie startup ideas**, load the `asb-indie-ideation` skill (`.agents/skills/asb-indie-ideation/SKILL.md`).
- When the user wants to **build their founder profile first**, invoke the global `asb-who-me` and `asb-voters` skills and save outputs to `founder/WHO-ME.md` and `founder/VOTERS.md`.
- When the user is ready to **take a surviving idea into real human interviews**, hand off to the global `asb-interview-goals`, `asb-interview-hypotheses`, `asb-interview-questions`, `asb-interview-debrief`, `asb-interview-learning`, and `asb-interview-report` skills.
- When launching subagents that need web research (`search_web` or MCP browser tools), always use `type_name="self"` (in `run_workflow`) or `TypeName="self"` (in `invoke_subagent`) — do NOT use the built-in `research` subagent, which has no network access.
