---
name: asb-indie-ideation
description: "Orchestrates a multi-agent entrepreneurial idea discovery and decision system uniting Jason Cohen's 18 A Smart Bear (ASB) skills, Ray Dalio's Decision-Making Principles (believability-weighted specialist panels, evidence believability scoring, 1st/2nd/3rd-order consequences, Expected Value & pre-committed kill triggers, root-cause diagnosis, and cross-run learned principles), and blind, web-grounded 4-persona synthetic interview pre-tests (quarantined and believability-capped at 0.35). Fans out parallel web-researching subagents to mine public pain, synthesize stranger-sortable indie ideas, Fermi-score viability, run adversarial Rude Q&A + Consequence/EV triangulation, dry-run interview scripts against realistic personas, and produce human field-validation kits — strictly without building product code. Load when the user asks to discover, research, score, stress-test, triangulate, run synthetic persona interviews, or compare indie startup ideas using subagents."
---

# ASB + Dalio Indie Idea Foundry — Multi-Agent Orchestrator

This skill coordinates specialized subagents to discover, stress-test, believability-weight, and dry-run indie startup ideas using **A Smart Bear (ASB)** + **Ray Dalio's Decision-Making Principles** + **Grounded Synthetic Persona Pre-Tests**, stopping strictly **before building**.

Read the six reference files as needed (all one level deep):
- [ASB Framework Map](./references/asb-framework-map.md) — how all 18 ASB skills map to pre-build ideation vs. field validation.
- [Dalio Decision Principles](./references/dalio-decision-principles.md) — evidence believability scale, believability-weighted specialist panel, 1st/2nd/3rd-order consequences, EV & kill triggers, root-cause reflection.
- [Synthetic Interview Protocol](./references/synthetic-interview-protocol.md) — 7-part grounded persona system prompt anatomy, 4-archetype heterogeneous panel, blind information barrier, anti-sycophancy rules, and `0.35` believability cap.
- [Inverse Founder-Fit](./references/inverse-founder-fit.md) — working backwards from any vetted idea to derive the Ideal Founder Archetype, Required Voters, Month-6 Personal Hell, 30-day ramp-up curriculum, Co-Founder complement, and 5-minute Self-Fit Mirror.
- [Subagent Roster](./references/subagent-roster.md) — all specialist roles, tool rules, prompts, and refusal conditions.
- [Scoring & Gates](./references/scoring-and-gates.md) — exact `asb-problem` scales/formula, believability weights, `asb-rude-qa`, Needs Stack, Provisional Carol, and Positioning gates.

## Non-Negotiable Rules

1. **No Building.** Never write app code, prototypes, landing pages, or technical implementation plans. Output ends at vetted dossiers, decision records, synthetic pre-test audits, and human interview kits.
2. **Radical Truth & Grounded Synthetic Quarantine.**
   - Blind, anti-sycophantic **synthetic persona interviews** (`workflows/run_synthetic_interviews.py` or Phase 6B of discovery/deep-dive) ARE encouraged to surface objections, test status-quo inertia, and debug leading questions in `VALIDATION-KIT.md`.
   - Every synthetic persona MUST be built with a web-grounded **7-part system prompt**, kept **strictly blind** to the startup idea/hypotheses, run in a **4-archetype heterogeneous panel**, quarantined inside `synthetic-interviews/`, stamped `SYNTHETIC-PRE-TEST`, and capped at **Dalio Believability `0.35`** (never promoted to `✓ VALIDATED` without real human calls).
3. **Pain + Reflection = Progress.** Read `principles/LEARNED-PRINCIPLES.md` at Phase 0; diagnose killed ideas to **root causes** and propose Candidate Principles in `DECISION-MEMO.md`.
4. **Network-Capable Subagents Only.** Always spawn subagents with `type_name="self"` (in `run_workflow`) or `TypeName="self"` (in `invoke_subagent`) so they inherit `search_web` and MCP browser tools. Never use the offline `research` subagent.

## Phase 0 — Intake (Fast & Focused)

1. Read `founder/WHO-ME.md`, `founder/VOTERS.md`, `founder/FOUNDER-PROFILE.md` (if present), and `principles/LEARNED-PRINCIPLES.md`.
2. If no founder profile exists, note once that `asb-who-me` + `asb-voters` sharpens fit, then ask at most **one** compact intake question covering domains/markets, ambition/constraints, and execution mode:
   - **Full Discovery Sprint:** `workflows/discover_ideas.py`
   - **Single-Idea Deep Dive:** `workflows/deep_dive_idea.py`
   - **Standalone 4-Persona Synthetic Pre-Test:** `workflows/run_synthetic_interviews.py`
   - **Interactive Subagent Mode:** Stage-by-stage `invoke_subagent(TypeName="self", ...)`.

## Execution Mode A — Automated Multi-Agent Pipelines (`run_workflow`)

Full discovery sprint (runs synthetic pre-test on the top `synthetic_interview_top_n` survivor(s) by default):
```text
ScriptPath: "/Users/albertjoseph/projects/asb/workflows/discover_ideas.py"
Description: "ASB + Dalio multi-agent indie startup idea discovery and vetting pipeline"
Args: {
  "domains": ["<domain 1>", "<domain 2>", "<domain 3>"],
  "ambition": "indie",
  "ideas_to_generate": 5,
  "max_survivors_for_strategy": 3,
  "synthetic_interview_top_n": 1,
  "constraints": "<optional constraints>",
  "run_slug": "<short-slug>"
}
```

Single-idea deep dive (includes 4-persona blind synthetic pre-test by default):
```text
ScriptPath: "/Users/albertjoseph/projects/asb/workflows/deep_dive_idea.py"
Description: "ASB + Dalio deep-dive vetting and synthetic pre-test for <idea>"
Args: {
  "idea_title": "<short title>",
  "idea_pitch": "<specific buyer, problem, trade-offs, price>",
  "ambition": "indie",
  "run_synthetic_interviews": true,
  "run_slug": "<short-slug>"
}
```

Standalone 4-persona blind synthetic interview pre-test on an existing idea dossier or pitch:
```text
ScriptPath: "/Users/albertjoseph/projects/asb/workflows/run_synthetic_interviews.py"
Description: "Grounded 4-persona blind synthetic interview pre-test for <idea>"
Args: {
  "idea_dir": "/Users/albertjoseph/projects/asb/runs/<run-id>/ideas/<slug>"
}
```

After any workflow finishes:
1. Run `python3 scripts/validate_scorecard.py runs/<run-id>/` to verify Fermi math, EBI, Panel Weighting, and synthetic quarantine (`0.35` cap).
2. Present a concise summary linking to `SHORTLIST.md`, `DECISION-MEMO.md`, `KILLED-IDEAS.md`, `SYNTHETIC-INTERVIEW-REPORT.md`, and `VALIDATION-KIT.md`.
3. Ask which Candidate Principles from `DECISION-MEMO.md` to promote into `principles/LEARNED-PRINCIPLES.md`, and offer to refine `HYPOTHESES.md` via `asb-interview-hypotheses` before real human calls.

## Refusal Conditions

- **Request to build an MVP from synthetic interviews alone:** Refuse the build; synthetic interviews are capped at Believability `0.35` and must be followed by real human interviews (`asb-interview-*`).
- **Request to merge synthetic debriefs into real human `interviews/` or mark hypotheses `✓ VALIDATED`:** Refuse; keep `synthetic-interviews/` strictly quarantined.
- **Request to hide panel splits or curve scores:** Refuse; Radical Truth and Kill Triggers are the value of the system.
