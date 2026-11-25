"""ASB + Dalio Grounded Synthetic Persona Interview Pre-Test Workflow (Hardened v2).

Fixes applied from adversarial Rude Q&A audit:
- Loads `VALIDATION-KIT.md` FIRST into a dedicated budget so the Interviewer NEVER loses its script.
- Strips `system_prompt` from transcripts passed to the Auditor so Personas #3 & #4 are NEVER truncated.
- Runs 5 focused SINGLE-QUESTION turns (ASB "one question, one answer").
- Distinct `persona_model` tier (default "flash") + neutral card role name + deterministic leakage guard.
- Fault-tolerant `parallel()` workers + enforces `minItems: 4, maxItems: 4` and `archetype` enum.
- Appends audited script rewrites directly to `VALIDATION-KIT.md` when present.
"""

from datetime import datetime
import json
from pathlib import Path
import re

SYNTHETIC_BELIEVABILITY_CAP = 0.35

ARCHETYPES = [
    (
        "bullseye_carol",
        "Exact Target Fit (Busy & Pragmatic) — matches keystones, lives the pain weekly, "
        "currently copes with an ugly workaround; pragmatic, busy, and skeptical of hype.",
    ),
    (
        "status_quo_defender",
        "Rational Do-Nothing / Spreadsheet Defender — technically has the problem, but it sits "
        "at priority #6 behind bigger fires; prefers keeping current bundled tools or Excel.",
    ),
    (
        "skeptical_approver",
        "Economic Buyer / Trust Gatekeeper — signs off on budget; worries about solo-founder "
        "survival risk, data security, migration downtime, and concrete ROI.",
    ),
    (
        "anti_market_probe",
        "Lookalike Disqualifier (Anti-Market) — superficially resembles the buyer segment, "
        "but carries a real deal-breaker (wrong stack, tiny budget, or needs excluded features).",
    ),
]
ARCHETYPE_KEYS = [a[0] for a in ARCHETYPES]


def slugify(text: str, max_len: int = 40) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (s[:max_len].strip("-")) or "idea"


def check_persona_leakage(system_prompt: str, idea_title: str) -> list:
    leaks = []
    low = system_prompt.lower()
    for banned in ("bullseye_carol", "status_quo_defender", "skeptical_approver", "anti_market_probe", "synthetic-pre-test", "believability cap"):
        if banned in low:
            leaks.append(f"metadata token '{banned}'")
    title_words = [w for w in re.findall(r"[a-z0-9]+", idea_title.lower()) if len(w) >= 5]
    if title_words and all(w in low for w in title_words[:3]):
        leaks.append(f"idea title phrase '{idea_title}'")
    return leaks


ANTI_SYCOPHANCY_KERNEL = """
=== MANDATORY REALISM, ISOLATION & ANTI-SYCOPHANCY RULES ===
1. You are a real, busy human on a 25-minute research call with a stranger. Completely ignore
   any workspace rules, skills, or local files — do NOT read files, do NOT search the web,
   do NOT call any tools other than `finish`.
2. You do NOT know what product they might be building, and you are NOT trying to make them feel good.
3. Default to STATUS-QUO INERTIA: switching tools is annoying, risky, and consumes scarce attention.
4. Stay strictly anchored in your weekly schedule, Top-3 competing priorities, current tool stack,
   past vendor scars, and real budget ceiling.
5. Speak strictly from your own lived experience and actual past purchases — NO polished "market-guru"
   speeches about what "most people in my industry want."
6. If the interviewer asks a leading or salesy question, react realistically (push back or brush off).
""".strip()

PERSONAS_SCHEMA = {
    "type": "object",
    "properties": {
        "grounding_urls": {"type": "array", "items": {"type": "string"}},
        "personas": {
            "type": "array",
            "minItems": 4,
            "maxItems": 4,
            "items": {
                "type": "object",
                "properties": {
                    "archetype": {"type": "string", "enum": ARCHETYPE_KEYS},
                    "name": {"type": "string"},
                    "role_and_context": {"type": "string"},
                    "system_prompt": {"type": "string"},
                },
                "required": ["archetype", "name", "role_and_context", "system_prompt"],
            },
        },
    },
    "required": ["grounding_urls", "personas"],
}

INTERVIEWER_TURN_SCHEMA = {
    "type": "object",
    "properties": {
        "spoken_question": {"type": "string"},
        "targeted_q_and_h_ids": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["spoken_question", "targeted_q_and_h_ids"],
}

PERSONA_REPLY_SCHEMA = {
    "type": "object",
    "properties": {
        "spoken_response": {"type": "string"},
        "internal_monologue": {"type": "string"},
    },
    "required": ["spoken_response", "internal_monologue"],
}

AUDIT_SCHEMA = {
    "type": "object",
    "properties": {
        "executive_summary": {"type": "string"},
        "per_persona_debriefs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "archetype": {"type": "string", "enum": ARCHETYPE_KEYS},
                    "name": {"type": "string"},
                    "mapped_answers": {"type": "array", "items": {"type": "string"}},
                    "verbatim_vocabulary": {"type": "array", "items": {"type": "string"}},
                    "leading_leaks_detected": {"type": "array", "items": {"type": "string"}},
                    "market_guru_flags": {"type": "array", "items": {"type": "string"}},
                    "key_surprise_or_objection": {"type": "string"},
                },
                "required": [
                    "archetype", "name", "mapped_answers", "verbatim_vocabulary",
                    "leading_leaks_detected", "market_guru_flags", "key_surprise_or_objection",
                ],
            },
        },
        "synthetic_red_flags": {"type": "array", "items": {"type": "string"}},
        "synthetic_directional_signals": {"type": "array", "items": {"type": "string"}},
        "watch_items": {"type": "array", "items": {"type": "string"}},
        "question_script_rewrites": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "question_ref": {"type": "string"},
                    "flaw_detected": {"type": "string"},
                    "improved_question": {"type": "string"},
                },
                "required": ["question_ref", "flaw_detected", "improved_question"],
            },
        },
        "priority_cruxes_for_real_humans": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "executive_summary", "per_persona_debriefs", "synthetic_red_flags",
        "synthetic_directional_signals", "watch_items",
        "question_script_rewrites", "priority_cruxes_for_real_humans",
    ],
}

# ---------------------------------------------------------------------------
# Load Target Context (VALIDATION-KIT.md FIRST with dedicated budget!)
# ---------------------------------------------------------------------------

root = Path(WORKSPACES[0]) if WORKSPACES else Path.cwd()
model_tier = args.get("model", None)
persona_model = args.get("persona_model", "flash")
idea_dir_arg = str(args.get("idea_dir", "")).strip()

validation_kit_text = ""
background_dossier_text = ""
validation_kit_path = None

if idea_dir_arg:
    idea_dir = Path(idea_dir_arg)
    if not idea_dir.is_absolute():
        idea_dir = root / idea_dir
    if not idea_dir.exists():
        raise ValueError(f"idea_dir does not exist: {idea_dir}")
    idea_title = str(args.get("idea_title", idea_dir.name))
    vk_path = idea_dir / "VALIDATION-KIT.md"
    if vk_path.exists():
        validation_kit_path = vk_path
        validation_kit_text = vk_path.read_text(encoding="utf-8")[:10000]
    bg_parts = []
    for fn in ("STRATEGY-BRIEF.md", "DECISION-RECORD.md", "PROBLEM-SCORE.md", "RUDE-QA.md"):
        p = idea_dir / fn
        if p.exists():
            bg_parts.append(f"### {fn}\n{p.read_text(encoding='utf-8')[:3500]}")
    background_dossier_text = "\n\n".join(bg_parts)
    if not validation_kit_text and not background_dossier_text:
        raise ValueError(f"No ASB dossier markdown files found inside {idea_dir}")
else:
    idea_title = str(args.get("idea_title", "")).strip()
    idea_pitch = str(args.get("idea_pitch", "")).strip()
    if not idea_title or not idea_pitch:
        raise ValueError("Provide either 'idea_dir' OR both 'idea_title' and 'idea_pitch'.")
    slug = slugify(str(args.get("run_slug", idea_title)))
    timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    idea_dir = root / "runs" / f"{timestamp}-synth-{slug}" / "ideas" / slug
    idea_dir.mkdir(parents=True, exist_ok=True)
    qs = args.get("questions") or []
    validation_kit_text = (
        "Starter questions:\n" + "\n".join(f"- {q}" for q in qs)
        if qs
        else "No starter script provided — derive open-ended non-leading questions from the pitch."
    )
    background_dossier_text = f"Idea: {idea_title}\nPitch: {idea_pitch}"

synth_dir = idea_dir / "synthetic-interviews"
synth_dir.mkdir(parents=True, exist_ok=True)

NO_BUILD = (
    "HARD RULE: Do NOT write app code or build prototypes. This is a quarantined synthetic "
    "interview pre-test (Believability Cap 0.35) to debug questions and surface objections."
)

# ---------------------------------------------------------------------------
# Phase 1 — Web-Grounded Persona Architect
# ---------------------------------------------------------------------------

phase("1. Web-Grounded Persona Architect")
log(f"Target dossier: {idea_dir} | Validation kit chars: {len(validation_kit_text)}")

archetypes_desc = "\n".join(f"- `{a}`: {desc}" for a, desc in ARCHETYPES)
persona_pack = await agent(
    prompt=(
        f"{NO_BUILD}\n\n"
        "You are the Persona Architect for an ASB + Dalio Grounded Synthetic Interview Pre-Test.\n"
        "Use `search_web` to ground yourself in REAL public facts about this buyer's world: "
        "actual job postings, daily workflows, real software stacks & pricing, and forum complaints.\n\n"
        f"Validation Kit (FOR YOUR EYES ONLY):\n{validation_kit_text[:6000]}\n\n"
        f"Background Dossier (FOR YOUR EYES ONLY):\n{background_dossier_text[:8000]}\n\n"
        f"Construct EXACTLY 4 distinct personas:\n{archetypes_desc}\n\n"
        "CRITICAL: Keep every `system_prompt` STRICTLY BLIND (never mention the startup title, "
        "product concept, target price, hypotheses, or archetype labels) and include all 7 sections "
        "(Identity & Daily Reality, Current Stack & Spend, Top-3 Competing Priorities, Past Vendor "
        "Scars, Budget & Buying Mechanics, Voice & Bluntness, Status-Quo Realism)."
    ),
    schema=PERSONAS_SCHEMA,
    role="Persona Architect",
    type_name="self",
    model=model_tier,
)

personas = persona_pack["personas"]
leak_warnings = []
for p in personas:
    leaks = check_persona_leakage(p["system_prompt"], idea_title)
    if leaks:
        leak_warnings.append(f"{p['archetype']}: {', '.join(leaks)}")
log(f"Built {len(personas)} personas ({len(persona_pack['grounding_urls'])} URLs, {len(leak_warnings)} leak warnings).")

# ---------------------------------------------------------------------------
# Phase 2 — Parallel 5-Turn Single-Question Blind Interviews (Fault-Tolerant)
# ---------------------------------------------------------------------------

phase("2. Parallel Blind Synthetic Interviews (4 Archetypes × 5 Single-Question Turns)")

INTERVIEWER_SYSTEM_PROMPT = f"""{NO_BUILD}

You are an expert ASB Customer Interviewer (`asb-interview-questions` discipline).
RULES:
- NEVER pitch your product or explain your startup idea.
- Ask ONE single-answer, open-ended, non-leading question per turn (never stack 2-3 unrelated asks).
- Probe REAL PAST BEHAVIOR, current tools, ugly workarounds, and real money spent.
- Apply the ASB Price Exception ONLY in Turn 5 as a neutral category-spend reaction around the
  specific headache the prospect described.
- Do NOT call tools — just output your single question via finish.

=== PRIMARY VALIDATION KIT (GOALS, HYPOTHESES, QUESTIONS) ===
{validation_kit_text}

=== BRIEF CONTEXT ===
{background_dossier_text[:3000]}
"""


async def run_single_interview_safe(p: dict) -> dict:
    try:
        full_persona_prompt = f"{p['system_prompt'].strip()}\n\n{ANTI_SYCOPHANCY_KERNEL}"
        persona_agent = agent(
            prompt=full_persona_prompt,
            role=f"Prospect Interviewee — {p['name']}",
            type_name="self",
            model=persona_model,
        )
        interviewer = agent(
            prompt=INTERVIEWER_SYSTEM_PROMPT,
            role=f"ASB Interviewer — {p['name']}",
            type_name="self",
            model=model_tier,
        )
        turns = [
            "TURN 1 (Single Qualifier): Ask ONE natural question about their role, operation scale, and current tool stack. No pain label or price.",
            "TURN 2 (Single Priorities): React briefly, then ask ONE open question about their top 2-3 headaches or priorities this quarter.",
            "TURN 3 (Single Episode & Coping): Ask ONE question probing the last concrete time this friction happened and how they coped.",
            "TURN 4 (Single Past-Spend & Trust): Ask ONE question about real money spent trying to fix this (or why not) and what makes them wary of switching vendors.",
            "TURN 5 (Category Price Reaction): Without pitching a product name, ask ONE blunt reaction question anchored around the price band from the Validation Kit for the specific headache they described.",
        ]
        transcript, last_reply = [], None
        for idx, instr in enumerate(turns, 1):
            iv_prompt = instr if last_reply is None else f"Prospect ({p['name']}) answered:\n\"{last_reply['spoken_response']}\"\n\n{instr}"
            iv_turn = await interviewer(prompt=iv_prompt, schema=INTERVIEWER_TURN_SCHEMA)
            p_reply = await persona_agent(
                prompt=f"Interviewer asks (Turn {idx}/5):\n\"{iv_turn['spoken_question']}\"\n\nAnswer strictly in-character plus candid unspoken `internal_monologue`.",
                schema=PERSONA_REPLY_SCHEMA,
            )
            transcript.append({"turn": idx, "interviewer": iv_turn, "persona": p_reply})
            last_reply = p_reply
        del persona_agent
        del interviewer
        return {"ok": True, "persona": p, "transcript": transcript}
    except Exception as exc:
        return {"ok": False, "persona": p, "error": str(exc)}


iv_wrapped = await parallel(personas, run_single_interview_safe)
interviews = [w for w in iv_wrapped if w["ok"]]
for w in iv_wrapped:
    if not w["ok"]:
        log(f"WARNING: Interview failed [{w['persona']['archetype']}]: {w['error']}")

if not interviews:
    raise RuntimeError("All 4 synthetic interviews failed.")

# ---------------------------------------------------------------------------
# Phase 3 — Synthetic Debriefer & Script Auditor (system_prompt STRIPPED!)
# ---------------------------------------------------------------------------

phase("3. Synthetic Debrief & Question Script Audit")

auditor_payload = [
    {
        "archetype": iv["persona"]["archetype"],
        "name": iv["persona"]["name"],
        "role_and_context": iv["persona"]["role_and_context"],
        "transcript": iv["transcript"],
    }
    for iv in interviews
]

audit = await agent(
    prompt=(
        f"{NO_BUILD}\n\n"
        "You are the ASB + Dalio Synthetic Debriefer & Script Auditor.\n"
        "Analyze ALL 4 blind synthetic interviews against the Validation Kit.\n\n"
        f"Validation Kit:\n{validation_kit_text[:7000]}\n\n"
        f"All {len(auditor_payload)} Complete Blind Transcripts (system_prompts stripped):\n"
        f"{json.dumps(auditor_payload, indent=2)}\n\n"
        "STRICT EPISTEMIC RULES:\n"
        "1. NEVER claim any hypothesis is 'VALIDATED' — capped at Believability 0.35 (`SYNTHETIC-PRE-TEST`).\n"
        "2. Map per_persona_debriefs for EVERY archetype present.\n"
        "3. Surface red flags, leading interviewer leaks, market-guru flags, concrete Q# rewrites, "
        "and the top 3-4 cruxes to verify with 10-15 real humans."
    ),
    schema=AUDIT_SCHEMA,
    role="Synthetic Debriefer & Auditor",
    type_name="self",
    model=model_tier,
)

# ---------------------------------------------------------------------------
# Phase 4 — Write Quarantined Synthetic Artifacts & Patch VALIDATION-KIT.md
# ---------------------------------------------------------------------------

phase("4. Writing Quarantined Synthetic Artifacts")

persona_md = [
    f"# Synthetic Persona Panel — {idea_title}",
    "",
    f"> ⚠️ **SYNTHETIC-PRE-TEST · Dalio Believability Cap: `{SYNTHETIC_BELIEVABILITY_CAP}`** · "
    f"Persona model: `{persona_model}` · Leak warnings: `{len(leak_warnings)}`",
    "",
    "## Web Grounding Sources",
    *([f"- {u}" for u in persona_pack["grounding_urls"]] or ["- None recorded."]),
    "",
]
if leak_warnings:
    persona_md.extend(["## Leakage Check Warnings", *[f"- {lw}" for lw in leak_warnings], ""])
for i, p in enumerate(personas, 1):
    persona_md.extend([f"## Persona {i}: {p['name']} (`{p['archetype']}`)", f"**Role:** {p['role_and_context']}", "", "```text", p["system_prompt"].strip(), "```", ""])
(synth_dir / "PERSONAS.md").write_text("\n".join(persona_md), encoding="utf-8")

debrief_by_arch = {d["archetype"]: d for d in audit["per_persona_debriefs"]}
for i, iv in enumerate(interviews, 1):
    p = iv["persona"]
    arch = p["archetype"]
    db = debrief_by_arch.get(arch, {})
    lines = [
        f"# SYNTHETIC-PRE-TEST Debrief — {p['name']} (`{arch}`)",
        "",
        f"> ⚠️ **SYNTHETIC SIMULATION — NOT A REAL HUMAN INTERVIEW · Believability Cap `{SYNTHETIC_BELIEVABILITY_CAP}`**",
        "",
        f"**Role:** {p['role_and_context']}",
        "",
        "## Mapped Answers", *([f"- {a}" for a in db.get("mapped_answers", [])] or ["- None mapped."]), "",
        "## Verbatim Vocabulary", *([f"- \"{v}\"" for v in db.get("verbatim_vocabulary", [])] or ["- None noted."]), "",
        "## Script & Bias Diagnostics",
        f"- **Key Surprise / Objection:** {db.get('key_surprise_or_objection', 'None')}",
        f"- **Leading-Question Leaks:** {'; '.join(db.get('leading_leaks_detected', [])) or 'None detected'}",
        f"- **Market-Guru Flags:** {'; '.join(db.get('market_guru_flags', [])) or 'None detected'}",
        "",
        "## Full 5-Turn Blind Transcript", "",
    ]
    for t in iv["transcript"]:
        lines.extend([
            f"### Turn {t['turn']} *(Targets: {', '.join(t['interviewer']['targeted_q_and_h_ids'])})*",
            f"**Interviewer:** {t['interviewer']['spoken_question']}", "",
            f"**{p['name']}:** {t['persona']['spoken_response']}", "",
            f"> *Internal monologue:* {t['persona']['internal_monologue']}", "",
        ])
    (synth_dir / f"SYNTH-0{i}-{arch}.md").write_text("\n".join(lines), encoding="utf-8")

report_lines = [
    f"# Synthetic Interview Pre-Test Report — {idea_title}",
    "",
    f"> ⚠️ **SYNTHETIC-PRE-TEST · Dalio Believability Cap: `{SYNTHETIC_BELIEVABILITY_CAP}`** (Quarantined from real human `interviews/`)",
    "",
    "## Executive Summary", audit["executive_summary"], "",
    "## ✗ Synthetic Red Flags", *([f"- **✗ SYNTHETIC-RED-FLAG:** {x}" for x in audit["synthetic_red_flags"]] or ["- None."]), "",
    "## ~ Synthetic Directional Signals (Verify With Real Humans)", *([f"- **~ SYNTHETIC-SIGNAL:** {x}" for x in audit["synthetic_directional_signals"]] or ["- None."]), "",
    "## 👀 Watch Items", *([f"- **👀 WATCH:** {x}" for x in audit["watch_items"]] or ["- None."]), "",
    "## Question Script Rewrites",
    *[f"- **{r['question_ref']}** (*{r['flaw_detected']}*): \"{r['improved_question']}\"" for r in audit["question_script_rewrites"]],
    "",
    "## Top Cruxes for 10–15 Real Humans", *[f"- {c}" for c in audit["priority_cruxes_for_real_humans"]], "",
    "## Quarantined Transcripts",
    "- [PERSONAS.md](synthetic-interviews/PERSONAS.md)",
    *[f"- [SYNTH-0{i}-{iv['persona']['archetype']}.md](synthetic-interviews/SYNTH-0{i}-{iv['persona']['archetype']}.md)" for i, iv in enumerate(interviews, 1)],
    "",
]
(idea_dir / "SYNTHETIC-INTERVIEW-REPORT.md").write_text("\n".join(report_lines), encoding="utf-8")

# Append audited rewrites to VALIDATION-KIT.md if present and not already patched
if validation_kit_path and validation_kit_path.exists():
    existing = validation_kit_path.read_text(encoding="utf-8")
    if "Post-Synthetic-Pre-Test Script Audit" not in existing:
        patch = [
            "",
            "## Post-Synthetic-Pre-Test Script Audit (`SYNTHETIC-PRE-TEST · Cap 0.35`)",
            *[f"- **[AUDITED-REWRITE] {r['question_ref']}** (*{r['flaw_detected']}*): \"{r['improved_question']}\"" for r in audit["question_script_rewrites"]],
            *([f"- **✗ SYNTHETIC-RED-FLAG:** {x}" for x in audit["synthetic_red_flags"]]),
            "",
        ]
        validation_kit_path.write_text(existing.rstrip() + "\n" + "\n".join(patch), encoding="utf-8")

meta = {
    "idea_title": idea_title,
    "status_tag": "SYNTHETIC-PRE-TEST",
    "believability_cap": SYNTHETIC_BELIEVABILITY_CAP,
    "personas_count": len(interviews),
    "archetypes": [iv["persona"]["archetype"] for iv in interviews],
    "persona_model": persona_model,
    "leakage_warnings": leak_warnings,
    "red_flags_count": len(audit["synthetic_red_flags"]),
    "script_rewrites_count": len(audit["question_script_rewrites"]),
    "quarantined_dir": "synthetic-interviews",
    "report_file": "SYNTHETIC-INTERVIEW-REPORT.md",
}
(synth_dir / "synthetic_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")

print(json.dumps({
    "idea_dir": str(idea_dir),
    "report": str(idea_dir / "SYNTHETIC-INTERVIEW-REPORT.md"),
    "personas_file": str(synth_dir / "PERSONAS.md"),
    "believability_cap": SYNTHETIC_BELIEVABILITY_CAP,
    "personas_run": len(interviews),
    "leakage_warnings_count": len(leak_warnings),
    "red_flags_count": len(audit["synthetic_red_flags"]),
    "script_rewrites_count": len(audit["question_script_rewrites"]),
}, indent=2))
