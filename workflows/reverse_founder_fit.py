"""ASB + Dalio Inverse Founder-Market Fit Workflow (Work Backwards From Idea -> Ideal Founder).

Given any surviving idea dossier (or a whole run directory, or a raw pitch), works
BACKWARDS using `asb-who-me`, `asb-voters`, and `asb-problem` (Eager-Identity) +
live web research to produce `FOUNDER-FIT-BLUEPRINT.md`:
1. Ideal Founder Archetype ("Who Wins This Easily?")
2. The 1-2 Required Voters (`V1`, optional `V2`) & what weaknesses they overpower
3. Founder Personal Hell (Anti-Archetype — who burns out in Month 6)
4. 30-Day Ramp-Up Curriculum (verified jargon, communities, docs, podcasts, teardowns)
5. Credibility & Co-Founder Complement Bridge (how an outsider moves Eager-Identity up)
6. 5-Minute Self-Fit Mirror (6 binary diagnostic questions + Go Solo / Ramp / Co-Founder / Pass rule)

Run via Antigravity's `run_workflow` tool:
    run_workflow(
        ScriptPath="/Users/albertjoseph/projects/asb/workflows/reverse_founder_fit.py",
        Description="Inverse Founder-Market Fit blueprints for vetted indie ideas",
        Args={"run_dir": "/Users/albertjoseph/projects/asb/runs/<run-id>"}
    )
    # OR Args={"idea_dir": "/Users/albertjoseph/projects/asb/runs/<run-id>/ideas/<slug>"}
    # OR Args={"idea_title": "...", "idea_pitch": "..."}
"""

from datetime import datetime
import json
from pathlib import Path
import re


def slugify(text: str, max_len: int = 40) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (s[:max_len].strip("-")) or "idea"


BLUEPRINT_SCHEMA = {
    "type": "object",
    "properties": {
        "archetype_name": {"type": "string"},
        "archetype_summary": {"type": "string"},
        "ideal_backgrounds_and_drives": {"type": "array", "items": {"type": "string"}},
        "required_voters": {
            "type": "array",
            "minItems": 1,
            "maxItems": 2,
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "voter_headline": {"type": "string"},
                    "what_it_overpowers": {"type": "string"},
                    "reverberates_into": {"type": "string"},
                },
                "required": ["id", "voter_headline", "what_it_overpowers", "reverberates_into"],
            },
        },
        "founder_personal_hell_anti_archetype": {"type": "array", "items": {"type": "string"}},
        "thirty_day_ramp_up_curriculum": {
            "type": "object",
            "properties": {
                "insider_vocabulary_to_master": {"type": "array", "items": {"type": "string"}},
                "verified_learning_sources": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "resource": {"type": "string"},
                            "url": {"type": "string"},
                            "why_it_matters": {"type": "string"},
                        },
                        "required": ["resource", "url", "why_it_matters"],
                    },
                },
                "week_by_week_ramp_plan": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["insider_vocabulary_to_master", "verified_learning_sources", "week_by_week_ramp_plan"],
        },
        "credibility_and_cofounder_bridge": {
            "type": "object",
            "properties": {
                "solo_outsider_feasibility": {
                    "type": "string",
                    "enum": ["SOLO_READY", "SOLO_AFTER_30D_RAMP", "NEEDS_DOMAIN_COFOUNDER", "INSIDER_ONLY"],
                },
                "bridge_moves_for_outsider": {"type": "array", "items": {"type": "string"}},
                "ideal_cofounder_or_advisor_profile": {"type": "string"},
                "where_to_meet_that_cofounder": {"type": "array", "items": {"type": "string"}},
            },
            "required": [
                "solo_outsider_feasibility", "bridge_moves_for_outsider",
                "ideal_cofounder_or_advisor_profile", "where_to_meet_that_cofounder",
            ],
        },
        "five_minute_self_fit_mirror": {
            "type": "array",
            "minItems": 6,
            "maxItems": 6,
            "items": {
                "type": "object",
                "properties": {
                    "question": {"type": "string"},
                    "yes_means": {"type": "string"},
                    "no_means": {"type": "string"},
                },
                "required": ["question", "yes_means", "no_means"],
            },
        },
        "actual_founder_gap_assessment": {"type": "string"},
    },
    "required": [
        "archetype_name", "archetype_summary", "ideal_backgrounds_and_drives",
        "required_voters", "founder_personal_hell_anti_archetype",
        "thirty_day_ramp_up_curriculum", "credibility_and_cofounder_bridge",
        "five_minute_self_fit_mirror", "actual_founder_gap_assessment",
    ],
}

root = Path(WORKSPACES[0]) if WORKSPACES else Path.cwd()
model_tier = args.get("model", None)

founder_chunks = []
for fname in ("WHO-ME.md", "VOTERS.md", "FOUNDER-PROFILE.md"):
    fp = root / "founder" / fname
    if fp.exists():
        txt = fp.read_text(encoding="utf-8").strip()
        if txt:
            founder_chunks.append(f"### {fname}\n{txt[:6000]}")
actual_founder_ctx = "\n\n".join(founder_chunks) or "No actual founder profile on disk yet — provide a general solo-technical-founder gap assessment."

# Resolve target idea directories
targets = []
run_dir_arg = str(args.get("run_dir", "")).strip()
idea_dir_arg = str(args.get("idea_dir", "")).strip()
include_killed = str(args.get("include_killed", False)).strip().lower() in ("true", "1", "yes", "on")  # bool("false") is True

if idea_dir_arg:
    p = Path(idea_dir_arg)
    if not p.is_absolute():
        p = root / p
    if not p.exists():
        raise ValueError(f"idea_dir not found: {p}")
    targets.append({"title": str(args.get("idea_title", p.name)), "dir": p})
elif run_dir_arg:
    rd = Path(run_dir_arg)
    if not rd.is_absolute():
        rd = root / rd
    data_path = rd / "run_data.json"
    if not data_path.exists():
        raise ValueError(f"run_data.json not found in {rd}")
    rd_data = json.loads(data_path.read_text(encoding="utf-8"))
    for s in rd_data.get("survivors", []):
        targets.append({"title": s["title"], "dir": rd / "ideas" / s["slug"]})
    if include_killed or not targets:
        for k in rd_data.get("killed", []):
            d = rd / "ideas" / k["slug"]
            if d.exists():
                targets.append({"title": k["title"], "dir": d})
else:
    title = str(args.get("idea_title", "")).strip()
    pitch = str(args.get("idea_pitch", "")).strip()
    if not title or not pitch:
        raise ValueError("Provide 'run_dir', 'idea_dir', OR both 'idea_title' and 'idea_pitch'.")
    slug = slugify(title)
    d = root / "runs" / f"{datetime.now().strftime('%Y-%m-%d_%H%M')}-founder-fit-{slug}" / "ideas" / slug
    d.mkdir(parents=True, exist_ok=True)
    targets.append({"title": title, "dir": d, "raw_pitch": pitch})

NO_BUILD = "HARD RULE: Do NOT write application code or build prototypes. Cite real URLs from search_web."

phase(f"Inverse Founder-Market Fit ({len(targets)} idea(s))")


async def build_blueprint_safe(target: dict) -> dict:
    try:
        d = target["dir"]
        title = target["title"]
        parts = []
        if "raw_pitch" in target:
            parts.append(f"### Pitch\n{target['raw_pitch']}")
        for fn in ("STRATEGY-BRIEF.md", "DECISION-RECORD.md", "PROBLEM-SCORE.md", "RUDE-QA.md", "SYNTHETIC-INTERVIEW-REPORT.md"):
            fp = d / fn
            if fp.exists():
                parts.append(f"### {fn}\n{fp.read_text(encoding='utf-8')[:4500]}")
        dossier_text = "\n\n".join(parts)

        bp = await agent(
            prompt=(
                f"{NO_BUILD}\n\n"
                "You are the ASB + Dalio Inverse Founder-Fit Architect (`asb-who-me` + `asb-voters` "
                "applied in REVERSE).\n"
                "Work BACKWARDS from this concrete idea dossier to design the exact Ideal Founder "
                "Archetype, the 1-2 Required Voters, the Month-6 'Personal Hell' Anti-Archetype, a "
                "concrete 30-day Ramp-Up Curriculum (use `search_web` to cite REAL industry communities, "
                "newsletters, podcasts, docs, or forums!), a Credibility/Co-Founder Bridge, and a "
                "6-question binary Self-Fit Mirror.\n\n"
                "Be brutally specific and concrete — NO generic advice like 'be passionate' or 'network'.\n\n"
                f"Idea Title: {title}\n\n"
                f"Idea Dossier:\n{dossier_text[:16000]}\n\n"
                f"Actual Founder Context (for gap assessment):\n{actual_founder_ctx[:4000]}"
            ),
            schema=BLUEPRINT_SCHEMA,
            role=f"Inverse Founder-Fit — {title[:24]}",
            type_name="self",
            model=model_tier,
        )

        ramp = bp["thirty_day_ramp_up_curriculum"]
        bridge = bp["credibility_and_cofounder_bridge"]
        lines = [
            f"# Inverse Founder-Fit Blueprint — {title}",
            "",
            f"**Ideal Founder Archetype:** `{bp['archetype_name']}` · "
            f"**Solo Outsider Feasibility:** `{bridge['solo_outsider_feasibility']}`",
            "",
            f"> {bp['archetype_summary']}",
            "",
            "## 1. Ideal Backgrounds & Energizing Drives (`asb-who-me` in Reverse)",
            *[f"- {x}" for x in bp["ideal_backgrounds_and_drives"]],
            "",
            "## 2. The 1–2 Required Voters (`asb-voters` in Reverse)",
            *[
                f"### {v['id']} — {v['voter_headline']}\n"
                f"- **Overpowers:** {v['what_it_overpowers']}\n"
                f"- **Reverberates into:** {v['reverberates_into']}\n"
                for v in bp["required_voters"]
            ],
            "## 3. Founder Personal Hell — Anti-Archetype ('Who Burns Out by Month 6?')",
            *[f"- {x}" for x in bp["founder_personal_hell_anti_archetype"]],
            "",
            "## 4. 30-Day Ramp-Up Curriculum ('Things to Know Before Calling Buyers')",
            "### Insider Vocabulary & Mental Models to Master",
            *[f"- {v}" for v in ramp["insider_vocabulary_to_master"]],
            "",
            "### Verified Learning Sources (Live Web Research)",
            *[f"- **{r['resource']}** ({r['url']}): {r['why_it_matters']}" for r in ramp["verified_learning_sources"]],
            "",
            "### Week-by-Week Ramp Plan (Zero Code)",
            *[f"- {w}" for w in ramp["week_by_week_ramp_plan"]],
            "",
            "## 5. Credibility & Co-Founder Complement Bridge (`Eager-Identity` Lift)",
            f"- **Solo Outsider Verdict:** `{bridge['solo_outsider_feasibility']}`",
            "### Moves for an Outsider to Earn Trust Quickly",
            *[f"- {m}" for m in bridge["bridge_moves_for_outsider"]],
            "",
            f"### Ideal Co-Founder or Advisor Complement\n{bridge['ideal_cofounder_or_advisor_profile']}",
            "",
            "### Where to Meet That Complement",
            *[f"- {w}" for w in bridge["where_to_meet_that_cofounder"]],
            "",
            "## 6. 5-Minute Founder-Fit Self-Mirror (6 Binary Checks)",
            *[
                f"{idx}. **{q['question']}**\n"
                f"   - *Yes:* {q['yes_means']}\n"
                f"   - *No:* {q['no_means']}"
                for idx, q in enumerate(bp["five_minute_self_fit_mirror"], 1)
            ],
            "",
            "## 7. Gap Assessment Against Current `founder/` Profile",
            bp["actual_founder_gap_assessment"],
            "",
        ]
        out_path = d / "FOUNDER-FIT-BLUEPRINT.md"
        out_path.write_text("\n".join(lines), encoding="utf-8")
        log(f"Wrote {out_path} ({bp['archetype_name']} · {bridge['solo_outsider_feasibility']})")
        return {"ok": True, "title": title, "path": str(out_path), "archetype": bp["archetype_name"], "feasibility": bridge["solo_outsider_feasibility"]}
    except Exception as exc:
        return {"ok": False, "title": target["title"], "error": str(exc)}


results = await parallel(targets, build_blueprint_safe)
print(json.dumps(results, indent=2))
