# Grounded Synthetic Persona Interview Protocol (Pre-Build Stress-Test)

## Table of Contents
1. [Purpose & Dalio Epistemic Boundary](#purpose--dalio-epistemic-boundary)
2. [Why Naive LLM Role-Play Fails (And How We Fix It)](#why-naive-llm-role-play-fails-and-how-we-fix-it)
3. [The 7-Part Persona System Prompt Anatomy](#the-7-part-persona-system-prompt-anatomy)
4. [The 4-Archetype Heterogeneous Panel](#the-4-archetype-heterogeneous-panel)
5. [The Blind Information Barrier & 3-Turn Interview Flow](#the-blind-information-barrier--3-turn-interview-flow)
6. [Debriefing, Question Auditing & Quarantine Rules](#debriefing-question-auditing--quarantine-rules)

---

## Purpose & Dalio Epistemic Boundary

Simulated persona interviews are used here as a **fast, low-cost pre-flight stress test** BEFORE recruiting real humans:
- **What they are great at:**
  1. Catching leading, awkward, or compound interview questions in `VALIDATION-KIT.md` (running ASB's *polite-stranger test* live!).
  2. Exposing obvious workflow mismatches, status-quo inertia ("priority #7"), budget-approval friction, and anti-market leakage.
  3. Generating sharper follow-up probes and surfacing blind-spot objections before you burn real outreach leads.
- **What they can NEVER do (Dalio Believability Cap = `0.35`):**
  - Synthetic interviews are capped at **Evidence Believability `0.35`** (below real triangulated public reports `0.7` and real human interviews `1.0`).
  - They can produce **`✗ SYNTHETIC-RED-FLAG`** (kill/narrow signals), **`~ SYNTHETIC-SIGNAL`** (directional prep), and **`👀 WATCH`** items — they can **NEVER** promote a hypothesis to `✓ VALIDATED`.
  - All outputs live strictly in `synthetic-interviews/` and `SYNTHETIC-INTERVIEW-REPORT.md`, quarantined from real human `interviews/` debriefs.

---

## Why Naive LLM Role-Play Fails (And How We Fix It)

| Classic Failure Mode | Mechanical Fix in This Protocol |
| :--- | :--- |
| **Sycophancy** ("Wow, I'd totally pay $99/mo for that!") | Explicit anti-sycophancy instructions + busy/skeptical posture + competing Top-3 priorities where the target pain is NOT automatically #1. |
| **Leaking the Pitch** (Persona reads the startup idea and plays along) | **Strict Blindness Barrier:** The Persona agent's system prompt NEVER mentions the startup idea, product name, price target, or hypotheses. |
| **Cardboard Caricatures** ("I am a busy SMB owner") | **Web-Grounded Persona Builder:** Uses `search_web` on real job descriptions, Reddit/forum threads, and industry tool stacks to populate concrete daily routines, real incumbent tools, and real budget lines. |
| **Echo Chamber** (5 clones of enthusiastic Carol) | **4-Archetype Heterogeneous Panel:** Bullseye Carol + Status-Quo Defender + Skeptical Approver + Anti-Market Probe. |
| **Contaminating Real Evidence** | Hard quarantine (`synthetic-interviews/`), `SYNTHETIC-PRE-TEST` stamp on every file, and `0.35` believability ceiling verified by `scripts/validate_scorecard.py`. |

---

## The 7-Part Persona System Prompt Anatomy

Every Persona System Prompt built by the **Persona Architect** MUST contain all 7 concrete sections:

1. **Identity & Daily Reality:** Exact role, company size/shape, years of experience, physical/workday environment (e.g., *"runs 6 HVAC trucks, in the field until 5pm, only opens QuickBooks at 8:30pm"*).
2. **Current Tool Stack & Actual Spend:** Specific named software/spreadsheets/services they already pay for (grounded in `search_web` norms), plus ugly manual workarounds.
3. **Top-3 Competing Priorities This Quarter:** Three concrete fires competing for their attention and budget right now (so the interviewer has to discover whether the problem even cracks top-3!).
4. **Past Vendor Scars & Switching Anxiety:** One or two specific bad experiences with software migrations, broken promises, hidden fees, or abandoned tools.
5. **Budget Authority & Buying Mechanics:** Whose credit card/budget it comes from, approval threshold, and what makes them say "call me next year."
6. **Voice, Vocabulary & Bluntness:** How they actually talk (plain industry terms, impatient with buzzwords, short answers when uninterested, guarded about sharing numbers until comfortable).
7. **Hard Anti-Sycophancy & Blindness Rules:**
   - *"You are a real, busy human on a 25-minute call with a stranger doing research. You do NOT know what they are building and you are NOT trying to make them feel good."*
   - *"Default to status quo inertia: switching tools is annoying and risky. Only admit willingness to spend money if it genuinely solves a top-3 pain worth more than the hassle."*
   - *"Do NOT volunteer polished 'market-guru' speeches about what 'most people in my industry want' unless prompted — speak strictly from your own concrete week and past purchases."*
   - *"If the interviewer asks a leading or salesy question, react realistically (give a flat polite brush-off or push back)."*

---

## The 4-Archetype Heterogeneous Panel

Every synthetic pre-test runs **4 distinct personas in parallel**:

1. **`bullseye_carol` (Target Fit, Busy & Pragmatic):** Matches Provisional Carol's keystones, has the aware pain, currently uses an ugly workaround — tests whether the pain is urgent *today* and whether the price/trade-offs actually clear switching inertia.
2. **`status_quo_defender` (Rational Do-Nothing / DIY):** Has the problem on paper, but copes with spreadsheets/existing bundled tools and treats it as priority #6 — tests `Self-Aware` and `Liquid` honestly.
3. **`skeptical_approver` (Economic Buyer / Trust Gatekeeper):** Controls budget or vetoes new vendors; worries about solo-founder survival risk, data security, migration downtime, and ROI — tests `Lucrative` and `Eager (Identity)`.
4. **`anti_market_probe` (Lookalike Disqualifier):** Looks superficially like the target market on demographic filters, but carries a Deal-Breaker (wrong stack, tiny budget, or needs an excluded feature) — tests whether our qualifier questions sort them out quickly.

---

## The Blind Information Barrier & 5-Turn Single-Question Flow

For each persona, two stateful agents converse across **5 single-question turns** (honoring ASB's *"one question, one answer"* rule):

- **Persona Agent:** Initialized ONLY with the 7-part Persona System Prompt + Isolation/Anti-Sycophancy Kernel (neutral role label `"Prospect Interviewee — <name>"`, distinct `persona_model` tier default `"flash"` to break same-model lockstep, programmatic leakage check scanning for product titles/prices/archetype tags).
- **Interviewer Agent:** Initialized with `VALIDATION-KIT.md` loaded **first** into a dedicated budget and ASB interviewing discipline (never pitch, never lead, ONE question per turn).

**5-Turn Structure:**
1. **Turn 1 — Single Qualifier:** Role, operation scale, and current tool stack (no pain label or price).
2. **Turn 2 — Single Priorities Question:** Top 2–3 headaches or priorities this quarter.
3. **Turn 3 — Single Episode & Coping:** Last concrete time friction happened and current DIY/incumbent workaround.
4. **Turn 4 — Single Past-Spend & Trust:** Real money spent previously + what makes them wary of small vendors.
5. **Turn 5 — Category-Anchored ASB Price Exception:** Neutral dollar reaction anchored around the specific headache *they described* (no product pitch).

**Auditor & Script Patching:** Before auditing, `system_prompt` is stripped from transcripts so ALL 4 full transcripts fit cleanly with zero truncation. Audited `question_script_rewrites` are appended directly to `VALIDATION-KIT.md` (`[AUDITED-REWRITE]`).

---

## Debriefing, Question Auditing & Quarantine Rules

After all 4 conversations finish, the **Synthetic Debriefer & Script Auditor** produces:
- `synthetic-interviews/PERSONAS.md` — full transparency on all 4 system prompts used.
- `synthetic-interviews/SYNTH-01-<archetype>.md` … `SYNTH-04-<archetype>.md` — mapped `Q#` / `[H#]` debriefs stamped `SYNTHETIC-PRE-TEST · Believability 0.35`.
- `SYNTHETIC-INTERVIEW-REPORT.md` — cross-persona synthesis covering:
  1. **Red Flags & Objections Surfaced** (`✗ SYNTHETIC-RED-FLAG`)
  2. **Directional Signals** (`~ SYNTHETIC-SIGNAL` — never `✓ VALIDATED`)
  3. **Question Script Audit** (which `Q#` questions leaked bias, felt awkward, or failed to sort `anti_market_probe` — with exact rewrites!)
  4. **Updated Focus for Real Human Interviews** (the exact 2–3 cruxes you must verify with 10–15 real humans before building).
