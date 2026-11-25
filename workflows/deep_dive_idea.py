"""ASB + Ray Dalio Indie Idea Foundry — Single-Idea Deep-Dive Decision Workflow (Hardened v2).

Incorporates all adversarial Rude Q&A audit fixes:
- True independent Phase 1 Scorer (0.30) vs Phase 2A Rude Q&A Attacker (0.40) vs Phase 2B Consequence/EV (0.30)
- Strict kill gate (BAD_IDEA, KILL, post_score < 0.5, Eager-Id = 0, or panel_weighted_score <= 0.0)
- Bottleneck Believability (min) + anti-inflation [fermi] clamp + deterministic numeric EV
- Conditional Round-2 Dwell turn in Rude Q&A + full founder_context & untruncated learned_principles
- Structured STRATEGY_SCHEMA & VALIDATION_KIT_SCHEMA + full Attack/Defense/Sources rendering
- Grounded 4-persona blind synthetic pre-test (5 single-question turns, distinct persona_model,
  stripped system_prompt for Auditor, leakage check, script rewrites appended to VALIDATION-KIT.md)
- Post-run mini DECISION-MEMO.md reflection.
"""

from datetime import datetime
import json
import math
from pathlib import Path
import re

DIVISOR = 625_000.0
SYNTHETIC_BELIEVABILITY_CAP = 0.35

LEGAL_SCALES = {
    "plausible": [1_000, 10_000, 100_000, 1_000_000, 10_000_000, 100_000_000, 1_000_000_000],
    "self_aware": [0.01, 0.1, 0.5, 1.0],
    "lucrative": [1, 10, 100, 1_000, 10_000, 100_000, 1_000_000],
    "liquid": [0.01, 0.1, 1.0],
    "eager_identity": [0.0, 0.1, 0.5, 1.0],
    "eager_comparative": [0.1, 0.5, 1.0],
    "enduring": [0.01, 0.1, 0.5, 1.0],
}

LOG_SCALE_KEYS = {"plausible", "lucrative"}
LEGAL_BELIEVABILITY = [0.2, 0.4, 0.7, 1.0]
PANEL_WEIGHTS = {"scorer": 0.30, "attacker": 0.40, "consequence_ev": 0.30}
ARCHETYPES = ["bullseye_carol", "status_quo_defender", "skeptical_approver", "anti_market_probe"]

CRITERION_LABELS = {
    "plausible": "Plausible",
    "self_aware": "Self-Aware",
    "lucrative": "Lucrative",
    "liquid": "Liquid",
    "eager_identity": "Eager (Identity)",
    "eager_comparative": "Eager (Comparative)",
    "enduring": "Enduring",
}


def parse_bool(val, default: bool = True) -> bool:
    if val is None:
        return default
    if isinstance(val, bool):
        return val
    s = str(val).strip().lower()
    if s in ("false", "0", "no", "off", ""):
        return False
    if s in ("true", "1", "yes", "on"):
        return True
    return default


def slugify(text: str, max_len: int = 36) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (s[:max_len].strip("-")) or "idea"


def snap_to_legal(criterion: str, value: float) -> float:
    legal = LEGAL_SCALES[criterion]
    fv = float(value)
    if criterion in LOG_SCALE_KEYS and fv > 0:
        lv = math.log10(fv)
        return min(legal, key=lambda x: abs(math.log10(x) - lv))
    return min(legal, key=lambda x: abs(x - fv))


def snap_believability(value: float) -> float:
    return min(LEGAL_BELIEVABILITY, key=lambda x: abs(x - float(value)))


def compute_problem_score(scores: dict) -> dict:
    clean = {}
    product = 1.0
    bels = []
    has_sources = bool(scores.get("sources"))
    for key in LEGAL_SCALES:
        entry = scores[key]
        val = snap_to_legal(key, float(entry["value"]))
        ev_class = entry.get("evidence_class", "[fermi]")
        raw_bel = snap_believability(float(entry.get("believability", 0.2)))
        bel = raw_bel
        note = ""
        if ev_class == "[fermi]" and bel > 0.4:
            bel = 0.4
            note = f" [clamped from {raw_bel} -> 0.4: fermi cap]"
        elif bel >= 0.7 and not has_sources:
            bel = 0.4
            note = f" [clamped from {raw_bel} -> 0.4: no source URLs]"
        clean[key] = {
            "value": val,
            "justification": (entry.get("justification", "").strip() + note).strip(),
            "evidence_class": ev_class,
            "believability": bel,
        }
        product *= val
        bels.append(bel)
    total = round(product / DIVISOR, 4)
    ebi = round(sum(bels) / len(bels), 3)
    bottleneck = round(min(bels), 3)
    if clean["eager_identity"]["value"] == 0.0:
        band = "BLOCKED (Eager-Identity = 0 — structural deal-breaker)"
    elif total >= 2.0:
        band = "STRONG (>= 2.0 — strong bootstrapped / scale-up potential)"
    elif total >= 1.0:
        band = "VIABLE INDIE (>= 1.0 — can sustain an indie company)"
    elif total >= 0.5:
        band = "MARGINAL (0.5–0.99 — needs sharper niche or strong exception)"
    else:
        band = "NOT VIABLE (< 0.5 as scored)"
    return {
        "criteria": clean,
        "raw_product": product,
        "score": total,
        "evidence_believability_index": ebi,
        "bottleneck_believability": bottleneck,
        "band": band,
        "sources": list(scores.get("sources") or []),
    }


def reconcile_rude_qa_scorecard(baseline_raw: dict, adjusted_raw: dict) -> tuple:
    """DP2 (weight evidence by believability): keep a Rude Q&A score change only when it rests on
    evidence at least as believable as the Phase-3 evidence it overturns.

    Returns (merged_raw_scorecard, list_of_reverted_change_notes). Changes in either direction are
    treated the same way, so this cannot inflate a score: it only refuses to let a weaker claim
    overwrite a stronger one. Sources from both scorecards are kept.
    """
    base = compute_problem_score(baseline_raw)["criteria"]
    adj = compute_problem_score(adjusted_raw)["criteria"]
    merged = dict(adjusted_raw)
    merged["sources"] = list(dict.fromkeys(list(baseline_raw.get("sources") or []) + list(adjusted_raw.get("sources") or [])))
    reverted = []
    for key in LEGAL_SCALES:
        if adj[key]["value"] != base[key]["value"] and adj[key]["believability"] < base[key]["believability"]:
            note = (
                f"{key}: Rude Q&A proposed {adj[key]['value']} (believability {adj[key]['believability']}) "
                f"but Phase-3 value {base[key]['value']} rests on stronger evidence "
                f"(believability {base[key]['believability']}); kept Phase-3 value"
            )
            restored = dict(baseline_raw[key])
            restored["justification"] = (str(restored.get("justification", "")).strip() + f" [{note}]").strip()
            merged[key] = restored
            reverted.append(note)
    return merged, reverted


def compute_panel_decision(scorer_calc: dict, attacker_verdict: str, consequence_rec: str) -> dict:
    sc_score = scorer_calc["score"]
    if scorer_calc["criteria"]["eager_identity"]["value"] == 0.0 or sc_score < 0.5:
        scorer_vote = -1.0
    elif sc_score >= 1.0:
        scorer_vote = 1.0
    else:
        scorer_vote = 0.0
    attacker_vote = {"SHARPENED": 1.0, "NOT_YET_READY": 0.0, "BAD_IDEA": -1.0}[attacker_verdict]
    consequence_vote = {"PURSUE_VALIDATION": 1.0, "GATHER_MORE_EVIDENCE": 0.0, "KILL": -1.0}[consequence_rec]
    weighted = round(
        PANEL_WEIGHTS["scorer"] * scorer_vote
        + PANEL_WEIGHTS["attacker"] * attacker_vote
        + PANEL_WEIGHTS["consequence_ev"] * consequence_vote,
        3,
    )
    votes = [scorer_vote, attacker_vote, consequence_vote]
    return {
        "votes": {"scorer": scorer_vote, "attacker": attacker_vote, "consequence_ev": consequence_vote},
        "weights": dict(PANEL_WEIGHTS),
        "panel_weighted_score": weighted,
        "disagreement_flag": (max(votes) - min(votes)) >= 1.0,
    }


def compute_ev_metrics(cev: dict) -> dict:
    p = max(0.0, min(100.0, float(cev.get("p_viable_pct", 0.0))))
    arr = max(0.0, float(cev.get("target_arr_usd", 0.0)))
    hrs = max(1.0, float(cev.get("validation_hours", 20.0)))
    expected_arr = round((p / 100.0) * arr, 2)
    return {
        "p_viable_pct": p,
        "target_arr_usd": arr,
        "validation_hours": hrs,
        "expected_arr_usd": expected_arr,
        "ev_per_validation_hour": round(expected_arr / hrs, 2),
    }


def check_persona_leakage(system_prompt: str, idea_title: str, price_str: str) -> list:
    leaks = []
    low = system_prompt.lower()
    for banned in ("bullseye_carol", "status_quo_defender", "skeptical_approver", "anti_market_probe", "synthetic-pre-test"):
        if banned in low:
            leaks.append(f"metadata token '{banned}'")
    title_words = [w for w in re.findall(r"[a-z0-9]+", idea_title.lower()) if len(w) >= 5]
    if title_words and all(w in low for w in title_words[:3]):
        leaks.append(f"idea title phrase '{idea_title}'")
    pc = price_str.strip().lower()
    if pc and len(pc) >= 3 and pc in low:
        leaks.append(f"target price '{price_str}'")
    return leaks


def fmt_num(key: str, val: float) -> str:
    if key == "plausible":
        return {1_000: "1k", 10_000: "10k", 100_000: "100k", 1_000_000: "1M", 10_000_000: "10M", 100_000_000: "100M", 1_000_000_000: "1B"}.get(int(val), str(val))
    if key == "lucrative":
        return {1: "$1", 10: "$10", 100: "$100", 1_000: "$1k", 10_000: "$10k", 100_000: "$100k", 1_000_000: "$1M"}.get(int(val), f"${val}")
    return str(val)


def _criterion_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "value": {"type": "number"},
            "justification": {"type": "string"},
            "evidence_class": {"type": "string", "enum": ["[research]", "[fermi]", "[data]"]},
            "believability": {"type": "number"},
        },
        "required": ["value", "justification", "evidence_class", "believability"],
    }


SCORECARD_SCHEMA = {
    "type": "object",
    "properties": {
        "target_buyer": {"type": "string"},
        "problem": {"type": "string"},
        "trade_offs": {"type": "string"},
        "price": {"type": "string"},
        "pricing_strategy": {"type": "string", "enum": ["More for More", "More for Less", "Less for Less"]},
        "plausible": _criterion_schema(),
        "self_aware": _criterion_schema(),
        "lucrative": _criterion_schema(),
        "liquid": _criterion_schema(),
        "eager_identity": _criterion_schema(),
        "eager_comparative": _criterion_schema(),
        "enduring": _criterion_schema(),
        "dominant_weak_links": {"type": "array", "items": {"type": "string"}},
        "sources": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "target_buyer", "problem", "trade_offs", "price", "pricing_strategy",
        "plausible", "self_aware", "lucrative", "liquid", "eager_identity",
        "eager_comparative", "enduring", "dominant_weak_links", "sources",
    ],
}

ATTACK_SCHEMA = {
    "type": "object",
    "properties": {
        "opposite_test_failures": {"type": "array", "items": {"type": "string"}},
        "fluffy_words_flagged": {"type": "array", "items": {"type": "string"}},
        "present_tense_threats": {"type": "array", "items": {"type": "string"}},
        "scars_and_founder_fit_attacks": {"type": "array", "items": {"type": "string"}},
        "challenge_from_below": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "criterion": {"type": "string", "enum": list(LEGAL_SCALES.keys())},
                    "current_value": {"type": "number"},
                    "proposed_lower_value": {"type": "number"},
                    "attack": {"type": "string"},
                },
                "required": ["criterion", "current_value", "proposed_lower_value", "attack"],
            },
        },
        "unfair_questions": {"type": "array", "items": {"type": "string"}},
        "competitor_evidence_urls": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "opposite_test_failures", "fluffy_words_flagged", "present_tense_threats",
        "scars_and_founder_fit_attacks", "challenge_from_below",
        "unfair_questions", "competitor_evidence_urls",
    ],
}

ADVOCATE_SCHEMA = {
    "type": "object",
    "properties": {
        "real_decisions_revisions": {"type": "array", "items": {"type": "string"}},
        "threat_responses": {"type": "array", "items": {"type": "string"}},
        "score_defenses_or_concessions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "criterion": {"type": "string", "enum": list(LEGAL_SCALES.keys())},
                    "stance": {"type": "string", "enum": ["defend", "concede"]},
                    "final_value": {"type": "number"},
                    "reasoning": {"type": "string"},
                },
                "required": ["criterion", "stance", "final_value", "reasoning"],
            },
        },
        "unfair_question_answers": {"type": "array", "items": {"type": "string"}},
        "how_could_i_be_wrong": {"type": "string"},
        "honest_concession_if_fatal": {"type": "string"},
    },
    "required": [
        "real_decisions_revisions", "threat_responses",
        "score_defenses_or_concessions", "unfair_question_answers",
        "how_could_i_be_wrong", "honest_concession_if_fatal",
    ],
}

DWELL_CHECK_SCHEMA = {
    "type": "object",
    "properties": {
        "needs_dwell": {"type": "boolean"},
        "dwell_reason": {"type": "string"},
        "dwell_follow_up_questions": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["needs_dwell", "dwell_reason", "dwell_follow_up_questions"],
}

VERDICT_SCHEMA = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": ["SHARPENED", "NOT_YET_READY", "BAD_IDEA"]},
        "verdict_summary": {"type": "string"},
        "real_decisions_locked": {"type": "array", "items": {"type": "string"}},
        "fluff_replaced": {"type": "array", "items": {"type": "string"}},
        "threats_clarified": {"type": "array", "items": {"type": "string"}},
        "adjusted_scorecard": SCORECARD_SCHEMA,
        "open_questions_for_field": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "verdict", "verdict_summary", "real_decisions_locked", "fluff_replaced",
        "threats_clarified", "adjusted_scorecard", "open_questions_for_field",
    ],
}

CONSEQUENCE_EV_SCHEMA = {
    "type": "object",
    "properties": {
        "root_cause_persistence": {"type": "string"},
        "root_cause_is_indie_favorable": {"type": "boolean"},
        "first_order_consequences": {"type": "array", "items": {"type": "string"}},
        "second_order_consequences": {"type": "array", "items": {"type": "string"}},
        "third_order_consequences": {"type": "array", "items": {"type": "string"}},
        "p_viable_pct": {"type": "number"},
        "target_arr_usd": {"type": "number"},
        "validation_hours": {"type": "number"},
        "upside_indie_band": {"type": "string"},
        "pre_build_validation_cost": {"type": "string"},
        "highest_ev_falsification_test": {"type": "string"},
        "pre_committed_kill_trigger": {"type": "string"},
        "recommendation": {"type": "string", "enum": ["PURSUE_VALIDATION", "GATHER_MORE_EVIDENCE", "KILL"]},
        "recommendation_reasoning": {"type": "string"},
        "how_could_i_be_wrong": {"type": "string"},
    },
    "required": [
        "root_cause_persistence", "root_cause_is_indie_favorable",
        "first_order_consequences", "second_order_consequences", "third_order_consequences",
        "p_viable_pct", "target_arr_usd", "validation_hours",
        "upside_indie_band", "pre_build_validation_cost",
        "highest_ev_falsification_test", "pre_committed_kill_trigger",
        "recommendation", "recommendation_reasoning", "how_could_i_be_wrong",
    ],
}

STRATEGY_SCHEMA = {
    "type": "object",
    "properties": {
        "needs_stack": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "level": {"type": "string"},
                    "role": {"type": "string", "enum": ["purpose", "aspiration", "promise", "your_level", "obviated"]},
                    "occupants": {"type": "string"},
                    "why_your_level_wins": {"type": "string"},
                },
                "required": ["id", "level", "role", "occupants", "why_your_level_wins"],
            },
        },
        "provisional_carol": {
            "type": "object",
            "properties": {
                "portrait": {"type": "string"},
                "markers": {"type": "array", "items": {"type": "string"}},
                "qualifiers": {"type": "array", "items": {"type": "string"}},
                "disqualifiers_anti_market": {"type": "array", "items": {"type": "string"}},
                "keystones": {"type": "array", "items": {"type": "string"}},
                "deal_breakers": {"type": "array", "items": {"type": "string"}},
                "inciting_events": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "moment": {"type": "string"},
                            "status": {"type": "string", "enum": ["OBSERVED-PUBLIC", "HYPOTHESIZED"]},
                            "source_or_validation": {"type": "string"},
                            "findability_and_search_phrases": {"type": "string"},
                        },
                        "required": ["id", "moment", "status", "source_or_validation", "findability_and_search_phrases"],
                    },
                },
            },
            "required": ["portrait", "markers", "qualifiers", "disqualifiers_anti_market", "keystones", "deal_breakers", "inciting_events"],
        },
        "positioning_audit": {
            "type": "object",
            "properties": {
                "buyer_scoreboard_currency": {"type": "string"},
                "pricing_strategy": {"type": "string", "enum": ["More for More", "More for Less", "Less for Less"]},
                "statements": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "id": {"type": "string"},
                            "role": {"type": "string"},
                            "statement": {"type": "string"},
                            "opposite_test_check": {"type": "string"},
                        },
                        "required": ["id", "role", "statement", "opposite_test_check"],
                    },
                },
                "facts_to_verify": {"type": "array", "items": {"type": "string"}},
            },
            "required": ["buyer_scoreboard_currency", "pricing_strategy", "statements", "facts_to_verify"],
        },
    },
    "required": ["needs_stack", "provisional_carol", "positioning_audit"],
}

VALIDATION_KIT_SCHEMA = {
    "type": "object",
    "properties": {
        "goals": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "question": {"type": "string"},
                    "decision_informed": {"type": "string"},
                },
                "required": ["id", "question", "decision_informed"],
            },
        },
        "hypothesis_templates": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "claim": {"type": "string"},
                    "goal_ids": {"type": "array", "items": {"type": "string"}},
                    "what_changes_if_false": {"type": "string"},
                },
                "required": ["id", "claim", "goal_ids", "what_changes_if_false"],
            },
        },
        "interview_questions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "question": {"type": "string"},
                    "follow_ups": {"type": "array", "items": {"type": "string"}},
                    "hypothesis_ids": {"type": "array", "items": {"type": "string"}},
                    "polite_stranger_check": {"type": "string"},
                },
                "required": ["id", "question", "follow_ups", "hypothesis_ids", "polite_stranger_check"],
            },
        },
        "recruitment_channels": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "channel": {"type": "string"},
                    "url": {"type": "string"},
                    "how_to_approach": {"type": "string"},
                },
                "required": ["channel", "url", "how_to_approach"],
            },
        },
    },
    "required": ["goals", "hypothesis_templates", "interview_questions", "recruitment_channels"],
}

SYNTH_PERSONAS_SCHEMA = {
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
                    "archetype": {"type": "string", "enum": ARCHETYPES},
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

SYNTH_IV_TURN_SCHEMA = {
    "type": "object",
    "properties": {
        "spoken_question": {"type": "string"},
        "targeted_q_and_h_ids": {"type": "array", "items": {"type": "string"}},
    },
    "required": ["spoken_question", "targeted_q_and_h_ids"],
}

SYNTH_PERSONA_REPLY_SCHEMA = {
    "type": "object",
    "properties": {
        "spoken_response": {"type": "string"},
        "internal_monologue": {"type": "string"},
    },
    "required": ["spoken_response", "internal_monologue"],
}

SYNTH_AUDIT_SCHEMA = {
    "type": "object",
    "properties": {
        "executive_summary": {"type": "string"},
        "per_persona_debriefs": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "archetype": {"type": "string", "enum": ARCHETYPES},
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
# Setup
# ---------------------------------------------------------------------------

root = Path(WORKSPACES[0]) if WORKSPACES else Path.cwd()
idea_title = str(args.get("idea_title", "")).strip()
idea_pitch = str(args.get("idea_pitch", "")).strip()
if not idea_title or not idea_pitch:
    raise ValueError("Args must include non-empty 'idea_title' and 'idea_pitch'.")

ambition = str(args.get("ambition", "indie"))
model_tier = args.get("model", None)
persona_model = args.get("persona_model", "flash")
run_synthetic_interviews = parse_bool(args.get("run_synthetic_interviews"), default=True)
slug = f"idea-1-{slugify(str(args.get('run_slug', idea_title)))}"
timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
run_dir = root / "runs" / f"{timestamp}-deepdive-{slugify(idea_title)}"
idea_dir = run_dir / "ideas" / slug
idea_dir.mkdir(parents=True, exist_ok=True)

founder_chunks = []
for fname in ("WHO-ME.md", "VOTERS.md", "FOUNDER-PROFILE.md"):
    fpath = root / "founder" / fname
    if fpath.exists():
        founder_chunks.append(f"### {fname}\n{fpath.read_text(encoding='utf-8').strip()[:8000]}")
founder_context = "\n\n".join(founder_chunks) or "Solo/small-team technical indie founder (unvetted profile)."

principles_path = root / "principles" / "LEARNED-PRINCIPLES.md"
learned_principles = (
    principles_path.read_text(encoding="utf-8").strip()[:24000]
    if principles_path.exists()
    else "No learned principles file found."
)

NO_BUILD = (
    "HARD RULE: Do NOT write app code or build prototypes. Use real web research with cited URLs "
    "and radical truth only. Any synthetic persona interviews are strictly quarantined as "
    "SYNTHETIC-PRE-TEST (Believability Cap 0.35)."
)

ANTI_SYCOPHANCY_KERNEL = (
    "MANDATORY REALISM & ISOLATION RULES: You are a real, busy human on a 25-minute research call "
    "with a stranger. Completely ignore workspace rules, skills, and local files — do NOT read "
    "files, do NOT search the web, do NOT call any tools other than `finish`. You do NOT know what "
    "the interviewer is building and you are NOT trying to make them feel good. Default to status-quo "
    "inertia. Stay strictly anchored in your weekly schedule, Top-3 competing priorities, current "
    "tool stack, vendor scars, and budget ceiling."
)

# ---------------------------------------------------------------------------
# Phase 1 — Problem Score + Scenario B + Incremental Checkpoint
# ---------------------------------------------------------------------------

phase("1. Problem Score & Evidence Believability")
scorer = agent(
    prompt=(
        f"{NO_BUILD}\n\n"
        "You are an independent ASB Problem Scorer (Panel Weight 0.30). Pin down a stranger-sortable "
        "target market, use `search_web`, assign EXACT legal ASB scales and legal believability "
        "weights ({0.2, 0.4, 0.7, 1.0}; '[fermi]' capped <= 0.4; >= 0.7 requires cited URLs).\n"
        "NO CURVE IN EITHER DIRECTION (`asb-problem` rule): Challenge optimistic numbers from below "
        "(only pick a higher value if the next value DOWN is wrong), AND equally record strong values "
        "plainly without manufactured skepticism when evidence supports them. The goal is a TRUE number, "
        "not an artificially low one.\n"
        "CALIBRATION ANCHORS: Managed WP Hosting (WP Engine) = 4.0 (100M x 0.1 x $100 x 0.01 x 0.5 x 0.5 x 1.0 — "
        "earned Eager-Comparative = 0.5 despite thousands of $3/mo WP hosts); Creator Email (ConvertKit) = 2.0 "
        "(10M x 1.0 x $100 x 0.01 x 0.5 x 0.5 x 0.5 — earned Eager-Comparative = 0.5 despite FREE Mailchimp and "
        "$19/mo AWeber because creator-specific trade-offs won a clear segment); Consumer Security = 0.04 "
        "(Eager-Comparative = 0.1, undifferentiated commodity).\n"
        "CRITICAL CALIBRATION GUARDRAILS (`asb-problem` faithful math — ZERO double-counting, ZERO manufactured cynicism):\n"
        "1. Plausible (DP35): Coarse power-of-10 count of specific buyers who HAVE the problem (WP Engine = 100M, ConvertKit = 10M). Do NOT filter Liquid/Self-Aware/Eager inside Plausible (that double-counts factors that already multiply!).\n"
        "2. Eager-Comparative (DP36): 0.1 = no material differentiation / existing free or cheap rival already solves the exact wedge cleanly for the same buyer; 0.5 = structural trade-off incumbents refuse to copy so a clear sub-segment buys for it alone EVEN WHEN cheap generalists/DIY tools exist; 1.0 = one-of-a-kind with no viable alternative.\n"
        "3. Eager-Identity (DP37): 0.5 ('indifferent, no red flags') is the honest baseline for self-serve credit-card SaaS sold to creators, devs, freelancers, small agencies, or SMB owners (especially with customer-owned/portable data). Reserve 0.1 for real institutional trust walls (SOC 2, Entra Admin Consent, HIPAA/IRS/legal liability)."
    ),
    role=f"Problem Scorer — {idea_title[:28]}",
    type_name="self",
    model=model_tier,
)

scen_a_raw = await scorer(
    prompt=(
        f"Idea: {idea_title}\nPitch: {idea_pitch}\nAmbition: {ambition}\n"
        f"Founder context:\n{founder_context}\n\n"
        f"Standing Decision Principles (ALL):\n{learned_principles}\n\n"
        "Score Scenario A honestly using exact legal scales and believability weights."
    ),
    schema=SCORECARD_SCHEMA,
)
scen_a_calc = compute_problem_score(scen_a_raw)
log(f"Scenario A: {scen_a_calc['score']} (EBI={scen_a_calc['evidence_believability_index']}, Min={scen_a_calc['bottleneck_believability']})")

scen_b_raw, scen_b_calc = None, None
if scen_a_calc["score"] < 1.0:
    scen_b_raw = await scorer(
        prompt=(
            f"Scenario A scored {scen_a_calc['score']} (EBI={scen_a_calc['evidence_believability_index']}).\n"
            f"Weak links: {scen_a_raw['dominant_weak_links']}\n\n"
            "Run Scenario B narrowing: propose a sharper niche or repriced wedge, changing only "
            "affected criteria, and score honestly."
        ),
        schema=SCORECARD_SCHEMA,
    )
    scen_b_calc = compute_problem_score(scen_b_raw)
    log(f"Scenario B: {scen_b_calc['score']} (EBI={scen_b_calc['evidence_believability_index']}, Min={scen_b_calc['bottleneck_believability']})")
del scorer

best_label = "Scenario A"
best_raw, best_calc = scen_a_raw, scen_a_calc
if (
    scen_b_calc
    and scen_b_calc["score"] > scen_a_calc["score"]
    and scen_b_calc["evidence_believability_index"] >= max(0.3, scen_a_calc["evidence_believability_index"] - 0.25)
):
    best_label, best_raw, best_calc = "Scenario B", scen_b_raw, scen_b_calc

# ---------------------------------------------------------------------------
# Phase 2 — Parallel Triangulation: Rude Q&A (With Dwell) + Consequence & EV
# ---------------------------------------------------------------------------

phase("2. Rude Q&A Court (With Dwell) + Dalio Consequence & EV Triangulation")
brief = json.dumps({
    "idea_title": idea_title,
    "idea_pitch": idea_pitch,
    "active_scenario": best_label,
    "scorecard": best_raw,
    "computed_score": best_calc["score"],
    "evidence_believability_index": best_calc["evidence_believability_index"],
    "bottleneck_believability": best_calc["bottleneck_believability"],
}, indent=2)


async def run_rude_qa() -> dict:
    attacker = agent(
        prompt=(
            f"{NO_BUILD}\n\n"
            "You are the ASB Rude Q&A Interrogator (Panel Weight 0.40). Search the web specifically "
            "to find real competitors, free alternatives, platform bundling, and structural deal-breakers. "
            "Run Opposite Test, fluff audit, >=70% present-tense threats, scars/founder-fit probe, "
            "unfair questions, and challenge-from-below on the 2 softest Problem Score criteria.\n\n"
            f"Founder context:\n{founder_context}\n\n"
            f"Standing Decision Principles (ALL):\n{learned_principles}"
        ),
        role=f"Rude Q&A Attacker — {idea_title[:24]}",
        type_name="self",
        model=model_tier,
    )
    a1 = await attacker(f"Attack this idea ruthlessly:\n{brief}", schema=ATTACK_SCHEMA)
    advocate = agent(
        prompt=(
            f"{NO_BUILD}\n\nYou are the Idea Advocate in Rude Q&A. Defend with concrete trade-offs "
            f"or concede honestly, and state 'how_could_i_be_wrong'.\n\nFounder context:\n{founder_context}"
        ),
        role=f"Idea Advocate — {idea_title[:26]}",
        type_name="self",
        model=model_tier,
    )
    d1 = await advocate(f"Brief:\n{brief}\n\nAttack:\n{json.dumps(a1, indent=2)}", schema=ADVOCATE_SCHEMA)
    dc = await attacker(
        f"Advocate Round-1 response:\n{json.dumps(d1, indent=2)}\n\nSet needs_dwell=true ONLY if a critical defense stayed fuzzy or wishful.",
        schema=DWELL_CHECK_SCHEMA,
    )
    d2 = None
    if dc["needs_dwell"]:
        d2 = await advocate(
            f"Attacker is DWELLING: {dc['dwell_reason']}\nFollow-ups: {json.dumps(dc['dwell_follow_up_questions'], indent=2)}\nSharpen or concede.",
            schema=ADVOCATE_SCHEMA,
        )
    del advocate
    v_out = await attacker(
        f"Round-1 defense:\n{json.dumps(d1, indent=2)}\n"
        + (f"\nRound-2 Dwell defense:\n{json.dumps(d2, indent=2)}\n" if d2 else "")
        + "\nJudge ruthlessly with NO CURVE IN EITHER DIRECTION (`asb-problem` / `asb-rude-qa` calibration): "
        "stay unsparing against real flaws, fluff, unverified competitor claims, and `Eager-Comparative = 0.1` "
        "undifferentiated clones, AND equally calibrate `Eager-Comparative = 0.5` accurately to `ConvertKit (2.0)` / "
        "`WP Engine (4.0)` (a clear sub-segment buys for a deliberate structural trade-off incumbents refuse to copy — "
        "NOT 'zero competitors on Earth'). Issue `SHARPENED` honestly when the candidate survives your hardest "
        "present-tense attacks with verified >= 1.0 math and concrete locked decisions, `NOT_YET_READY` if viable "
        "but still fuzzy, or `BAD_IDEA` if fatally broken. Emit full `adjusted_scorecard` on exact legal scales "
        "and legal believability weights ({0.2, 0.4, 0.7, 1.0}; '[fermi]' capped <= 0.4; >= 0.7 requires cited URLs).",
        schema=VERDICT_SCHEMA,
    )
    del attacker
    reconciled_scorecard, reverted_changes = reconcile_rude_qa_scorecard(best_raw, v_out["adjusted_scorecard"])
    return {
        "attack_1": a1, "defense_1": d1, "dwell_triggered": bool(dc["needs_dwell"]),
        "dwell_check": dc, "defense_2": d2, "verdict_out": v_out,
        "reverted_changes": reverted_changes,
        "post_calc": compute_problem_score(reconciled_scorecard),
    }


async def run_conseq_ev() -> dict:
    return await agent(
        prompt=(
            f"{NO_BUILD}\n\n"
            "You are the Ray Dalio Consequence & EV Analyst (Panel Weight 0.30). Run independently "
            "of Rude Q&A.\n\n"
            f"Founder context:\n{founder_context}\n\n"
            f"Standing Decision Principles (ALL):\n{learned_principles}\n\n"
            f"Brief:\n{brief}\n\n"
            "Deliver root-cause persistence, 1st/2nd/3rd-order consequences, numeric `p_viable_pct`, "
            "`target_arr_usd`, `validation_hours`, highest-EV falsification test, concrete "
            "`pre_committed_kill_trigger`, independent recommendation, and `how_could_i_be_wrong`.\n"
            "NO CURVE IN EITHER DIRECTION: Recommend `KILL` whenever structural 2nd/3rd-order consequences, "
            "platform bundling, or negative EV make pre-build interviews a waste of time; recommend "
            "`PURSUE_VALIDATION` honestly when root-cause persistence is indie-favorable, EV per validation hour "
            "is genuinely attractive, and clear falsification tests + kill triggers can decide viability in 15-25 hours."
        ),
        schema=CONSEQUENCE_EV_SCHEMA,
        role=f"Dalio Consequence/EV — {idea_title[:22]}",
        type_name="self",
        model=model_tier,
    )


rq_res, conseq_out = await parallel([run_rude_qa(), run_conseq_ev()], lambda coro: coro)
verdict_out = rq_res["verdict_out"]
post_calc = rq_res["post_calc"]
ev_metrics = compute_ev_metrics(conseq_out)
# Independent Phase 1 Scorer vote (best_calc) vs Phase 2A Attacker vs Phase 2B Consequence/EV
panel = compute_panel_decision(best_calc, verdict_out["verdict"], conseq_out["recommendation"])
adj = verdict_out["adjusted_scorecard"]
locked_market = {
    "scenario_label": f"{best_label} (Post-Rude Q&A)",
    "target_buyer": adj["target_buyer"],
    "problem": adj["problem"],
    "trade_offs": adj["trade_offs"],
    "price": adj["price"],
    "pricing_strategy": adj["pricing_strategy"],
}

survived = (
    verdict_out["verdict"] != "BAD_IDEA"
    and conseq_out["recommendation"] != "KILL"
    and post_calc["score"] >= 0.5
    and post_calc["criteria"]["eager_identity"]["value"] > 0.0
    and panel["panel_weighted_score"] > 0.0
)

log(
    f"Panel: RudeQA={verdict_out['verdict']}, ConseqEV={conseq_out['recommendation']}, "
    f"Phase1={best_calc['score']}, Post={post_calc['score']} (EBI={post_calc['evidence_believability_index']}, "
    f"Min={post_calc['bottleneck_believability']}), PanelWeighted={panel['panel_weighted_score']}, "
    f"ExpARR=${ev_metrics['expected_arr_usd']:,.0f}, Survived={survived}"
)

# ---------------------------------------------------------------------------
# Phase 3 — Structured Strategy Brief & Validation Kit + Phase 3B Synthetic Pre-Test
# ---------------------------------------------------------------------------

strat_data, vkit_data, synth_audit, synth_meta = None, None, None, None

if survived:
    phase("3. Strategy Brief & Validation Kit")
    final_brief = json.dumps({
        "idea_title": idea_title,
        "locked_market": locked_market,
        "verdict": verdict_out["verdict"],
        "verdict_summary": verdict_out["verdict_summary"],
        "real_decisions_locked": verdict_out["real_decisions_locked"],
        "threats_clarified": verdict_out["threats_clarified"],
        "open_questions_for_field": verdict_out["open_questions_for_field"],
        "post_score": post_calc["score"],
        "ebi": post_calc["evidence_believability_index"],
        "bottleneck_believability": post_calc["bottleneck_believability"],
        "panel": panel,
        "consequence_ev": conseq_out,
        "ev_metrics": ev_metrics,
    }, indent=2)

    strat_agent = agent(
        prompt=(
            f"{NO_BUILD}\n\nYou are the ASB Pre-Build Strategist. Build Needs Stack, Provisional Carol, "
            "and Positioning Audit (value-first in buyer's scoreboard currency, aligned with locked_market "
            "pricing strategy, Opposite-Test passing, ZERO clichés/generics, [VERIFY: ...] for unproven claims).\n\n"
            f"Context:\n{final_brief}"
        ),
        schema=STRATEGY_SCHEMA,
        role="Pre-Build Strategist",
        type_name="self",
        model=model_tier,
    )
    val_agent = agent(
        prompt=(
            f"{NO_BUILD}\n\nYou are the ASB + Dalio Validation Planner. Build Goals (G1..G7), "
            "UNOWNED Hypothesis Templates (H1..H12), single-answer non-leading Questions (Q1..Q10), "
            "and 4-6 web-verified Recruitment Channels targeting low-believability criteria, any panel "
            "split, and the pre-committed Kill Trigger.\n\n"
            f"Context:\n{final_brief}"
        ),
        schema=VALIDATION_KIT_SCHEMA,
        role="Validation Planner",
        type_name="self",
        model=model_tier,
    )
    strat_data, vkit_data = await parallel([strat_agent, val_agent], lambda t: t)

if survived and run_synthetic_interviews and vkit_data:
    phase("3B. Grounded 4-Persona Blind Synthetic Pre-Test (Cap 0.35)")
    synth_dir = idea_dir / "synthetic-interviews"
    synth_dir.mkdir(parents=True, exist_ok=True)
    vkit_json = json.dumps(vkit_data, indent=2)
    dossier_bundle = json.dumps({
        "locked_market": locked_market,
        "provisional_carol": strat_data["provisional_carol"],
        "validation_kit": vkit_data,
        "kill_trigger": conseq_out["pre_committed_kill_trigger"],
    }, indent=2)

    persona_pack = await agent(
        prompt=(
            f"{NO_BUILD}\n\nYou are the Persona Architect. Use `search_web` to build EXACTLY 4 blind "
            "7-part Persona System Prompts (`bullseye_carol`, `status_quo_defender`, `skeptical_approver`, "
            "`anti_market_probe`). NEVER mention the startup idea, locked price, hypotheses, or archetype "
            "names inside `system_prompt`.\n\nDossier (FOR YOUR EYES ONLY):\n" + dossier_bundle[:12000]
        ),
        schema=SYNTH_PERSONAS_SCHEMA,
        role="Persona Architect",
        type_name="self",
        model=model_tier,
    )
    leak_warnings = []
    for p in persona_pack["personas"]:
        leaks = check_persona_leakage(p["system_prompt"], idea_title, locked_market["price"])
        if leaks:
            leak_warnings.append(f"{p['archetype']}: {', '.join(leaks)}")

    async def _run_blind_iv(p: dict) -> dict:
        p_agent = agent(
            prompt=f"{p['system_prompt'].strip()}\n\n{ANTI_SYCOPHANCY_KERNEL}",
            role=f"Prospect Interviewee — {p['name']}",
            type_name="self",
            model=persona_model,
        )
        iv_agent = agent(
            prompt=(
                f"{NO_BUILD}\n\nYou are an ASB Customer Interviewer. Ask ONE single-answer, open-ended, "
                f"non-leading question per turn. Never pitch. Do NOT call tools.\n\n"
                f"Active Price Anchor (Turn 5 ONLY): {locked_market['price']}\n\nValidation Kit:\n{vkit_json[:8000]}"
            ),
            role=f"ASB Interviewer — {p['name']}",
            type_name="self",
            model=model_tier,
        )
        turns = [
            "TURN 1 (Single Qualifier): Ask ONE natural question about their role, operation scale, and current tools.",
            "TURN 2 (Single Priorities): Ask ONE open question about their top 2-3 headaches/priorities this quarter.",
            "TURN 3 (Single Episode & Coping): Ask ONE question about the last concrete episode and current workaround.",
            "TURN 4 (Single Spend & Trust): Ask ONE question about real money spent and what makes them wary of small vendors.",
            f"TURN 5 (Category Price Reaction): Without pitching a product name, ask ONE blunt reaction question anchored around spending roughly {locked_market['price']} on a dedicated tool for the headache they described.",
        ]
        transcript, last = [], None
        for idx, ti in enumerate(turns, 1):
            iv_p = ti if last is None else f"Prospect replied:\n\"{last['spoken_response']}\"\n\n{ti}"
            iv_q = await iv_agent(prompt=iv_p, schema=SYNTH_IV_TURN_SCHEMA)
            p_r = await p_agent(
                prompt=f"Interviewer asks (Turn {idx}/5):\n\"{iv_q['spoken_question']}\"\n\nReply strictly in-character plus internal_monologue.",
                schema=SYNTH_PERSONA_REPLY_SCHEMA,
            )
            transcript.append({"turn": idx, "interviewer": iv_q, "persona": p_r})
            last = p_r
        del p_agent
        del iv_agent
        return {"persona": p, "transcript": transcript}

    synth_interviews = await parallel(persona_pack["personas"], _run_blind_iv)
    auditor_payload = [
        {
            "archetype": iv["persona"]["archetype"],
            "name": iv["persona"]["name"],
            "role_and_context": iv["persona"]["role_and_context"],
            "transcript": iv["transcript"],
        }
        for iv in synth_interviews
    ]
    synth_audit = await agent(
        prompt=(
            f"{NO_BUILD}\n\nAudit ALL 4 blind synthetic interviews (Believability Cap 0.35 — NEVER mark "
            "anything VALIDATED). Map per_persona_debriefs for all 4 archetypes, surface red flags, "
            "directional signals, watch items, script rewrites, and top cruxes for real humans.\n\n"
            f"Validation Kit:\n{vkit_json[:5500]}\n\nAll 4 Transcripts:\n{json.dumps(auditor_payload, indent=2)}"
        ),
        schema=SYNTH_AUDIT_SCHEMA,
        role="Synthetic Debriefer & Auditor",
        type_name="self",
        model=model_tier,
    )

    p_md = [f"# Synthetic Persona Panel — {idea_title}", "", f"> ⚠️ **SYNTHETIC-PRE-TEST · Cap `{SYNTHETIC_BELIEVABILITY_CAP}`** · Persona model: `{persona_model}`", ""]
    for i, p in enumerate(persona_pack["personas"], 1):
        p_md.extend([f"## Persona {i}: {p['name']} (`{p['archetype']}`)", p["role_and_context"], "", "```text", p["system_prompt"].strip(), "```", ""])
    (synth_dir / "PERSONAS.md").write_text("\n".join(p_md), encoding="utf-8")

    db_by_arch = {db["archetype"]: db for db in synth_audit["per_persona_debriefs"]}
    for i, iv in enumerate(synth_interviews, 1):
        p = iv["persona"]
        db = db_by_arch.get(p["archetype"], {})
        tl = [
            f"# SYNTHETIC-PRE-TEST Debrief — {p['name']} (`{p['archetype']}`)",
            "",
            f"> ⚠️ **SYNTHETIC SIMULATION · Believability Cap `{SYNTHETIC_BELIEVABILITY_CAP}`**",
            "",
            "## Mapped Answers", *([f"- {a}" for a in db.get("mapped_answers", [])] or ["- None."]), "",
            "## Key Surprise / Objection", db.get("key_surprise_or_objection", "None"), "",
            "## Full 5-Turn Transcript", "",
        ]
        for t in iv["transcript"]:
            tl.extend([
                f"### Turn {t['turn']} ({', '.join(t['interviewer']['targeted_q_and_h_ids'])})",
                f"**Interviewer:** {t['interviewer']['spoken_question']}", "",
                f"**{p['name']}:** {t['persona']['spoken_response']}", "",
                f"> *Internal monologue:* {t['persona']['internal_monologue']}", "",
            ])
        (synth_dir / f"SYNTH-0{i}-{p['archetype']}.md").write_text("\n".join(tl), encoding="utf-8")

    rep_lines = [
        f"# Synthetic Interview Pre-Test Report — {idea_title}",
        "",
        f"> ⚠️ **SYNTHETIC-PRE-TEST · Dalio Believability Cap: `{SYNTHETIC_BELIEVABILITY_CAP}`**",
        "",
        "## Executive Summary", synth_audit["executive_summary"], "",
        "## ✗ Synthetic Red Flags", *([f"- **✗ SYNTHETIC-RED-FLAG:** {x}" for x in synth_audit["synthetic_red_flags"]] or ["- None."]), "",
        "## ~ Synthetic Directional Signals", *([f"- **~ SYNTHETIC-SIGNAL:** {x}" for x in synth_audit["synthetic_directional_signals"]] or ["- None."]), "",
        "## 👀 Watch Items", *([f"- **👀 WATCH:** {x}" for x in synth_audit["watch_items"]] or ["- None."]), "",
        "## Question Script Rewrites", *[f"- **{r['question_ref']}** (*{r['flaw_detected']}*): \"{r['improved_question']}\"" for r in synth_audit["question_script_rewrites"]], "",
        "## Top Cruxes for Real Humans", *[f"- {c}" for c in synth_audit["priority_cruxes_for_real_humans"]], "",
    ]
    (idea_dir / "SYNTHETIC-INTERVIEW-REPORT.md").write_text("\n".join(rep_lines), encoding="utf-8")
    synth_meta = {
        "idea_title": idea_title,
        "status_tag": "SYNTHETIC-PRE-TEST",
        "believability_cap": SYNTHETIC_BELIEVABILITY_CAP,
        "personas_count": len(synth_interviews),
        "archetypes": [iv["persona"]["archetype"] for iv in synth_interviews],
        "persona_model": persona_model,
        "leakage_warnings": leak_warnings,
        "red_flags_count": len(synth_audit["synthetic_red_flags"]),
        "script_rewrites_count": len(synth_audit["question_script_rewrites"]),
        "quarantined_dir": "synthetic-interviews",
        "report_file": "SYNTHETIC-INTERVIEW-REPORT.md",
    }
    (synth_dir / "synthetic_meta.json").write_text(json.dumps(synth_meta, indent=2), encoding="utf-8")

# ---------------------------------------------------------------------------
# Phase 4 — Write All Artifacts + Mini Decision Memo
# ---------------------------------------------------------------------------

phase("4. Writing Artifacts")


def render_table(calc: dict) -> str:
    rows = ["| Criterion | Value | Justification | Class | Believability |", "| :--- | :--- | :--- | :--- | :--- |"]
    for k in LEGAL_SCALES:
        c = calc["criteria"][k]
        rows.append(f"| {CRITERION_LABELS[k]} | `{fmt_num(k, c['value'])}` | {c['justification'].replace('|', '/').replace(chr(10), ' ')} | {c['evidence_class']} | `{c['believability']}` |")
    rows.append("")
    rows.append(
        f"**Total: `{calc['raw_product']:,.4g}` ÷ `625,000` = `{calc['score']}`** — {calc['band']}  \n"
        f"**EBI (Mean): `{calc['evidence_believability_index']}`** · **Bottleneck (Min): `{calc['bottleneck_believability']}`**"
    )
    return "\n".join(rows)


sources = list(dict.fromkeys((scen_a_raw.get("sources") or []) + ((scen_b_raw or {}).get("sources") or []) + (adj.get("sources") or [])))
ps_lines = [
    f"# Problem Score — {idea_title}", "",
    f"## Scenario A\n- **Buyer:** {scen_a_raw['target_buyer']}\n- **Problem:** {scen_a_raw['problem']}\n- **Trade-offs:** {scen_a_raw['trade_offs']}\n- **Price:** {scen_a_raw['price']} ({scen_a_raw['pricing_strategy']})\n",
    render_table(scen_a_calc), "",
]
if scen_b_raw and scen_b_calc:
    ps_lines.extend([
        f"## Scenario B\n- **Buyer:** {scen_b_raw['target_buyer']}\n- **Problem:** {scen_b_raw['problem']}\n- **Trade-offs:** {scen_b_raw['trade_offs']}\n- **Price:** {scen_b_raw['price']} ({scen_b_raw['pricing_strategy']})\n",
        render_table(scen_b_calc), "",
    ])
ps_lines.extend(["## Post-Rude Q&A Adjusted Scores", render_table(post_calc), "", "## Sources", *([f"- {u}" for u in sources] or ["- None."]), ""])
(idea_dir / "PROBLEM-SCORE.md").write_text("\n".join(ps_lines), encoding="utf-8")

a1, d1 = rq_res["attack_1"], rq_res["defense_1"]
rq_lines = [
    f"# Rude Q&A — {idea_title}", "",
    f"**Verdict:** `{verdict_out['verdict']}` · **Score:** `{best_calc['score']}` → `{post_calc['score']}` · **Dwell Triggered:** `{'Yes' if rq_res['dwell_triggered'] else 'No'}`", "",
    f"> {verdict_out['verdict_summary']}", "",
    *(
        ["## Score Changes Not Applied (Weaker Evidence Than Phase 1, DP2)",
         *[f"- {n}" for n in rq_res.get("reverted_changes", [])], ""]
        if rq_res.get("reverted_changes") else []
    ),
    "## Attack (Round 1)",
    *([f"- Opposite Test: {x}" for x in a1["opposite_test_failures"]]),
    *([f"- Threat: {x}" for x in a1["present_tense_threats"]]),
    *([f"- Scars/Founder: {x}" for x in a1["scars_and_founder_fit_attacks"]]),
    *([f"- Unfair Q: {q}" for q in a1["unfair_questions"]]), "",
    "## Advocate Defense (Round 1)",
    *([f"- Decision: {x}" for x in d1["real_decisions_revisions"]]),
    f"- **How Could I Be Wrong:** {d1['how_could_i_be_wrong']}", "",
    "## Locked Real Decisions", *([f"- {x}" for x in verdict_out["real_decisions_locked"]] or ["- None."]), "",
    "## Threats Clarified", *([f"- {x}" for x in verdict_out["threats_clarified"]] or ["- None."]), "",
    "## Open Questions for Field Interviews", *([f"- {x}" for x in verdict_out["open_questions_for_field"]] or ["- None."]), "",
]
(idea_dir / "RUDE-QA.md").write_text("\n".join(rq_lines), encoding="utf-8")

dr_lines = [
    f"# Dalio Decision Record — {idea_title}", "",
    f"**Panel Weighted Score:** `{panel['panel_weighted_score']}` · **Split:** `{'YES' if panel['disagreement_flag'] else 'No'}` · **Expected ARR:** `${ev_metrics['expected_arr_usd']:,.0f}` (`P={ev_metrics['p_viable_pct']}%` × `${ev_metrics['target_arr_usd']:,.0f}`)", "",
    "| Specialist | Weight | Vote | Basis |", "| :--- | :--- | :--- | :--- |",
    f"| Problem Scorer (Phase 1) | `0.30` | `{panel['votes']['scorer']}` | Independent Score `{best_calc['score']}`, EBI `{best_calc['evidence_believability_index']}` (min `{best_calc['bottleneck_believability']}`) |",
    f"| Rude Q&A Attacker (Phase 2A) | `0.40` | `{panel['votes']['attacker']}` | `{verdict_out['verdict']}` (Post `{post_calc['score']}`) |",
    f"| Consequence & EV (Phase 2B) | `0.30` | `{panel['votes']['consequence_ev']}` | `{conseq_out['recommendation']}` |", "",
    "## Root-Cause Persistence", f"- {conseq_out['root_cause_persistence']} *(Indie-favorable: `{conseq_out['root_cause_is_indie_favorable']}`)*", "",
    "## 1st / 2nd / 3rd-Order Consequences",
    "### First-Order", *[f"- {x}" for x in conseq_out["first_order_consequences"]], "",
    "### Second-Order", *[f"- {x}" for x in conseq_out["second_order_consequences"]], "",
    "### Third-Order", *[f"- {x}" for x in conseq_out["third_order_consequences"]], "",
    "## EV & Pre-Committed Kill Trigger",
    f"- **Expected ARR / Validation Hour:** `${ev_metrics['ev_per_validation_hour']:,.0f}/hr` (`{ev_metrics['validation_hours']:.0f} hrs`)",
    f"- **Highest-EV Falsification Test:** {conseq_out['highest_ev_falsification_test']}",
    f"- **PRE-COMMITTED KILL TRIGGER:** **{conseq_out['pre_committed_kill_trigger']}**", "",
    "## Blind-Spot Checks", f"- Consequence/EV: {conseq_out['how_could_i_be_wrong']}", f"- Advocate: {d1['how_could_i_be_wrong']}", "",
]
(idea_dir / "DECISION-RECORD.md").write_text("\n".join(dr_lines), encoding="utf-8")

if strat_data:
    carol, pos = strat_data["provisional_carol"], strat_data["positioning_audit"]
    st_lines = [
        f"# Pre-Build Strategy Brief — {idea_title}", "",
        f"> ⚠️ **PROVISIONAL — PRE-INTERVIEW.** Locked Market: `{locked_market['scenario_label']}` · `{locked_market['price']}` (`{locked_market['pricing_strategy']}`)", "",
        "## 1. Needs Stack",
        *[f"- **{n['id']} (`{n['role']}`):** {n['level']} — Occupants: {n['occupants']} · Wins because: {n['why_your_level_wins']}" for n in strat_data["needs_stack"]], "",
        "## 2. Provisional Carol", carol["portrait"], "",
        "### Markers", *[f"- {m}" for m in carol["markers"]], "",
        "### Qualifiers / Anti-Market", *[f"- Qualify: {q}" for q in carol["qualifiers"]], *[f"- Exclude: {d}" for d in carol["disqualifiers_anti_market"]], "",
        "### Inciting Events", *[f"- **{e['id']} ({e['status']}):** {e['moment']} — Findability: {e['findability_and_search_phrases']}" for e in carol["inciting_events"]], "",
        "## 3. Positioning Audit", f"- Currency: {pos['buyer_scoreboard_currency']} · Strategy: `{pos['pricing_strategy']}`",
        *[f"- **{p['id']} [{p['role']}]:** {p['statement']} *(Opposite: {p['opposite_test_check']})*" for p in pos["statements"]], "",
        "### Facts to Verify", *([f"- {f}" for f in pos["facts_to_verify"]] or ["- None."]), "",
    ]
    (idea_dir / "STRATEGY-BRIEF.md").write_text("\n".join(st_lines), encoding="utf-8")

if vkit_data:
    vk_lines = [
        f"# Pre-Build Customer Validation Kit — {idea_title}", "",
        f"> ⚠️ **STOP BEFORE BUILDING.** Kill Trigger: {conseq_out['pre_committed_kill_trigger']}", "",
        "## 1. Draft Goals", *[f"- **{g['id']}.** {g['question']} *({g['decision_informed']})*" for g in vkit_data["goals"]], "",
        "## 2. Unowned Hypothesis Templates", *[f"- **{h['id']}.** {h['claim']} `{', '.join(h['goal_ids'])}` — *If false:* {h['what_changes_if_false']}" for h in vkit_data["hypothesis_templates"]], "",
        "## 3. Draft Open-Ended Questions", *[f"- **{q['id']}.** \"{q['question']}\" `{', '.join(q['hypothesis_ids'])}`" for q in vkit_data["interview_questions"]], "",
        "## 4. Recruitment Channels", *[f"- **{r['channel']}** ({r['url']}): {r['how_to_approach']}" for r in vkit_data["recruitment_channels"]], "",
    ]
    if synth_audit:
        vk_lines.extend([
            "## 5. Post-Synthetic-Pre-Test Script Audit (`SYNTHETIC-PRE-TEST · Cap 0.35`)",
            *[f"- **[AUDITED-REWRITE] {r['question_ref']}** (*{r['flaw_detected']}*): \"{r['improved_question']}\"" for r in synth_audit["question_script_rewrites"]],
            *([f"- **✗ SYNTHETIC-RED-FLAG:** {x}" for x in synth_audit["synthetic_red_flags"]]), "",
        ])
    (idea_dir / "VALIDATION-KIT.md").write_text("\n".join(vk_lines), encoding="utf-8")

(run_dir / "DECISION-MEMO.md").write_text(
    f"# Dalio Deep-Dive Decision Memo — {idea_title}\n\n"
    f"- **Outcome:** `{'SURVIVED TO FIELD VALIDATION' if survived else 'KILLED'}`\n"
    f"- **Independent Panel:** Scorer `{panel['votes']['scorer']}` (0.30) · Attacker `{panel['votes']['attacker']}` (0.40) · Consequence/EV `{panel['votes']['consequence_ev']}` (0.30) → Weighted `{panel['panel_weighted_score']}` (Split: `{panel['disagreement_flag']}`)\n"
    f"- **Expected ARR:** `${ev_metrics['expected_arr_usd']:,.0f}` (`P={ev_metrics['p_viable_pct']}%`)\n"
    f"- **Kill Trigger:** {conseq_out['pre_committed_kill_trigger']}\n",
    encoding="utf-8",
)

run_data = {
    "status": "complete",
    "run_id": run_dir.name,
    "run_type": "deep_dive",
    "ambition": ambition,
    "survivors": [
        {
            "id": "IDEA-1",
            "title": idea_title,
            "slug": slug,
            "verdict": verdict_out["verdict"],
            "consequence_recommendation": conseq_out["recommendation"],
            "ev_metrics": ev_metrics,
            "panel": panel,
            "best_scenario_label": best_label,
            "scenario_a": scen_a_calc,
            "scenario_b": scen_b_calc,
            "post_rude_qa": post_calc,
            "has_full_dossier": bool(strat_data and vkit_data),
            "synthetic_pretest": synth_meta,
        }
    ] if survived else [],
    "killed": [] if survived else [
        {
            "id": "IDEA-1",
            "title": idea_title,
            "slug": slug,
            "stage": "Deep Dive — Rude Q&A + Dalio Panel",
            "best_scenario_label": best_label,
            "scenario_a": scen_a_calc,
            "scenario_b": scen_b_calc,
            "post_rude_qa": post_calc,
            "panel": panel,
            "ev_metrics": ev_metrics,
            "reason": verdict_out["verdict_summary"],
        }
    ],
}
(run_dir / "run_data.json").write_text(json.dumps(run_data, indent=2), encoding="utf-8")

print(json.dumps({
    "run_dir": str(run_dir),
    "idea_dir": str(idea_dir),
    "verdict": verdict_out["verdict"],
    "consequence_rec": conseq_out["recommendation"],
    "panel_weighted_score": panel["panel_weighted_score"],
    "disagreement_flag": panel["disagreement_flag"],
    "phase1_score": best_calc["score"],
    "post_score": post_calc["score"],
    "ebi": post_calc["evidence_believability_index"],
    "bottleneck": post_calc["bottleneck_believability"],
    "expected_arr_usd": ev_metrics["expected_arr_usd"],
    "survived": survived,
    "synth_red_flags": synth_meta["red_flags_count"] if synth_meta else None,
}, indent=2))
