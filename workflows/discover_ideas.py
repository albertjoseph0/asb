"""ASB + Ray Dalio Indie Idea Foundry — Multi-Agent Discovery & Decision Workflow.

Hardened v2 incorporating full adversarial Rude Q&A audit fixes:
- True independent Believability-Weighted Specialist Panel (Phase 3 Problem Scorer 0.30 /
  Phase 4A Rude Q&A Attacker 0.40 / Phase 4B Consequence & EV Analyst 0.30) — zero double-counting.
- Strict kill gate: kills on BAD_IDEA, Consequence/EV KILL, post-score < 0.5, Eager-Id = 0, or
  panel_weighted_score <= 0.0 (no neutral/split false survivors).
- Both Evidence Believability Index (mean) AND Bottleneck Believability (min), with deterministic
  anti-inflation clamping ([fermi] capped <= 0.4; >= 0.7 requires cited URLs).
- Real numeric EV computed deterministically in Python (p_viable_pct * target_arr_usd / validation_hours).
- Conditional Round-2 Dwell turn in Rude Q&A + full founder_context & learned_principles (untruncated!).
- Active-market propagation from Scenario B / Rude Q&A into Strategy, Synthetic Interviews & Shortlist.
- Fault-tolerant parallel() workers + incremental per-phase disk checkpointing (including killed ideas).
- Grounded 4-persona blind synthetic pre-test (5 single-question turns, distinct persona_model tier,
  leakage check, stripped system_prompt for Auditor so Personas #3 & #4 are never truncated, and
  script rewrites appended directly to VALIDATION-KIT.md + fed into Phase 7 Reflection).

Self-contained (no local module imports). All agents run with type_name="self".
"""

from datetime import datetime
import json
import math
from pathlib import Path
import re

# ---------------------------------------------------------------------------
# Deterministic ASB + Dalio Constants & Math (never delegated to LLMs)
# ---------------------------------------------------------------------------

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

CRITERION_LABELS = {
    "plausible": "Plausible",
    "self_aware": "Self-Aware",
    "lucrative": "Lucrative",
    "liquid": "Liquid",
    "eager_identity": "Eager (Identity)",
    "eager_comparative": "Eager (Comparative)",
    "enduring": "Enduring",
}

ARCHETYPES = [
    "bullseye_carol",
    "status_quo_defender",
    "skeptical_approver",
    "anti_market_probe",
]


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


def parse_domains(val) -> list:
    if not val:
        return []
    if isinstance(val, str):
        return [x.strip() for x in val.split(",") if x.strip()]
    if isinstance(val, list):
        return [str(x).strip() for x in val if str(x).strip()]
    return []


def slugify(text: str, max_len: int = 36) -> str:
    s = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return (s[:max_len].strip("-")) or "idea"


def snap_to_legal(criterion: str, value: float) -> float:
    """Snap to exact legal ASB scale (log10 distance for power-of-10 scales)."""
    legal = LEGAL_SCALES[criterion]
    fv = float(value)
    if criterion in LOG_SCALE_KEYS and fv > 0:
        lv = math.log10(fv)
        return min(legal, key=lambda x: abs(math.log10(x) - lv))
    return min(legal, key=lambda x: abs(x - fv))


def snap_believability(value: float) -> float:
    return min(LEGAL_BELIEVABILITY, key=lambda x: abs(x - float(value)))


def compute_problem_score(scores: dict) -> dict:
    """Validate legal scales, enforce anti-inflation believability caps, compute score/EBI/min."""
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
        clamp_note = ""
        if ev_class == "[fermi]" and bel > 0.4:
            bel = 0.4
            clamp_note = " [clamped from " + str(raw_bel) + " -> 0.4: fermi cap]"
        elif bel >= 0.7 and not has_sources and ev_class != "[data]":
            bel = 0.4
            clamp_note = " [clamped from " + str(raw_bel) + " -> 0.4: no source URLs]"
        clean[key] = {
            "value": val,
            "justification": (entry.get("justification", "").strip() + clamp_note).strip(),
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
    }


def compute_panel_decision(
    scorer_calc: dict,
    attacker_verdict: str,
    consequence_rec: str,
) -> dict:
    """True independent Dalio Believability-Weighted Panel (Phase 3 Scorer vs Phase 4A vs Phase 4B)."""
    sc_score = scorer_calc["score"]
    if scorer_calc["criteria"]["eager_identity"]["value"] == 0.0 or sc_score < 0.5:
        scorer_vote = -1.0
    elif sc_score >= 1.0:
        scorer_vote = 1.0
    else:
        scorer_vote = 0.0

    attacker_vote = {"SHARPENED": 1.0, "NOT_YET_READY": 0.0, "BAD_IDEA": -1.0}[attacker_verdict]
    consequence_vote = {
        "PURSUE_VALIDATION": 1.0,
        "GATHER_MORE_EVIDENCE": 0.0,
        "KILL": -1.0,
    }[consequence_rec]

    weighted = round(
        PANEL_WEIGHTS["scorer"] * scorer_vote
        + PANEL_WEIGHTS["attacker"] * attacker_vote
        + PANEL_WEIGHTS["consequence_ev"] * consequence_vote,
        3,
    )
    votes = [scorer_vote, attacker_vote, consequence_vote]
    return {
        "votes": {
            "scorer": scorer_vote,
            "attacker": attacker_vote,
            "consequence_ev": consequence_vote,
        },
        "weights": dict(PANEL_WEIGHTS),
        "panel_weighted_score": weighted,
        "disagreement_flag": (max(votes) - min(votes)) >= 1.0,
    }


def compute_ev_metrics(cev: dict) -> dict:
    p = max(0.0, min(100.0, float(cev.get("p_viable_pct", 0.0))))
    arr = max(0.0, float(cev.get("target_arr_usd", 0.0)))
    hrs = max(1.0, float(cev.get("validation_hours", 20.0)))
    expected_arr = round((p / 100.0) * arr, 2)
    ev_per_hr = round(expected_arr / hrs, 2)
    return {
        "p_viable_pct": p,
        "target_arr_usd": arr,
        "validation_hours": hrs,
        "expected_arr_usd": expected_arr,
        "ev_per_validation_hour": ev_per_hr,
    }


def check_persona_leakage(system_prompt: str, idea_title: str, price_str: str) -> list:
    """Detect accidental leakage of startup title, exact price, or simulation metadata."""
    leaks = []
    low = system_prompt.lower()
    for banned in ("bullseye_carol", "status_quo_defender", "skeptical_approver", "anti_market_probe", "synthetic-pre-test", "believability cap"):
        if banned in low:
            leaks.append(f"metadata token '{banned}'")
    title_words = [w for w in re.findall(r"[a-z0-9]+", idea_title.lower()) if len(w) >= 5]
    if title_words and all(w in low for w in title_words[:3]):
        leaks.append(f"idea title phrase '{idea_title}'")
    price_clean = price_str.strip().lower()
    if price_clean and len(price_clean) >= 3 and price_clean in low:
        leaks.append(f"target price '{price_str}'")
    return leaks


def fmt_num(key: str, val: float) -> str:
    if key == "plausible":
        return {
            1_000: "1k", 10_000: "10k", 100_000: "100k", 1_000_000: "1M",
            10_000_000: "10M", 100_000_000: "100M", 1_000_000_000: "1B",
        }.get(int(val), str(val))
    if key == "lucrative":
        return {
            1: "$1", 10: "$10", 100: "$100", 1_000: "$1k",
            10_000: "$10k", 100_000: "$100k", 1_000_000: "$1M",
        }.get(int(val), f"${val}")
    return str(val)


# ---------------------------------------------------------------------------
# JSON Schemas (zero float enums; strict string enums & array counts)
# ---------------------------------------------------------------------------

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


SCORECARD_OBJECT_SCHEMA = {
    "type": "object",
    "properties": {
        "target_buyer": {"type": "string"},
        "problem": {"type": "string"},
        "trade_offs": {"type": "string"},
        "price": {"type": "string"},
        "pricing_strategy": {
            "type": "string",
            "enum": ["More for More", "More for Less", "Less for Less"],
        },
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
        "plausible", "self_aware", "lucrative", "liquid",
        "eager_identity", "eager_comparative", "enduring",
        "dominant_weak_links", "sources",
    ],
}

DOMAINS_SCHEMA = {
    "type": "object",
    "properties": {
        "lenses": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "domain": {"type": "string"},
                    "search_hypothesis": {"type": "string"},
                    "why_indie_friendly": {"type": "string"},
                },
                "required": ["domain", "search_hypothesis", "why_indie_friendly"],
            },
        }
    },
    "required": ["lenses"],
}

SCOUT_SCHEMA = {
    "type": "object",
    "properties": {
        "domain": {"type": "string"},
        "signals": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "channel": {"type": "string"},
                    "source_url": {"type": "string"},
                    "evidence_believability": {"type": "number"},
                    "affected_buyer": {"type": "string"},
                    "observed_pain_and_workaround": {"type": "string"},
                    "incumbents_and_pricing": {"type": "string"},
                    "inciting_event_observed": {"type": "string"},
                },
                "required": [
                    "title", "channel", "source_url", "evidence_believability",
                    "affected_buyer", "observed_pain_and_workaround",
                    "incumbents_and_pricing", "inciting_event_observed",
                ],
            },
        },
    },
    "required": ["domain", "signals"],
}

ARCHITECT_SCHEMA = {
    "type": "object",
    "properties": {
        "ideas": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "title": {"type": "string"},
                    "one_liner": {"type": "string"},
                    "specific_buyer": {"type": "string"},
                    "specific_problem": {"type": "string"},
                    "deliberate_trade_offs": {"type": "array", "items": {"type": "string"}},
                    "price": {"type": "string"},
                    "pricing_strategy": {
                        "type": "string",
                        "enum": ["More for More", "More for Less", "Less for Less"],
                    },
                    "indie_feasibility": {"type": "string"},
                    "signal_ids": {"type": "array", "items": {"type": "string"}},
                    "needs_stack_sketch": {
                        "type": "object",
                        "properties": {
                            "obviated_below": {"type": "string"},
                            "your_level": {"type": "string"},
                            "promise_one_up": {"type": "string"},
                            "alternatives_above": {"type": "string"},
                        },
                        "required": [
                            "obviated_below", "your_level",
                            "promise_one_up", "alternatives_above",
                        ],
                    },
                },
                "required": [
                    "id", "title", "one_liner", "specific_buyer", "specific_problem",
                    "deliberate_trade_offs", "price", "pricing_strategy",
                    "indie_feasibility", "signal_ids", "needs_stack_sketch",
                ],
            },
        }
    },
    "required": ["ideas"],
}

ATTACK_TURN1_SCHEMA = {
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
        "adjusted_scorecard": SCORECARD_OBJECT_SCHEMA,
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
        "recommendation": {
            "type": "string",
            "enum": ["PURSUE_VALIDATION", "GATHER_MORE_EVIDENCE", "KILL"],
        },
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
                    "role": {
                        "type": "string",
                        "enum": ["purpose", "aspiration", "promise", "your_level", "obviated"],
                    },
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
                        "required": [
                            "id", "moment", "status",
                            "source_or_validation", "findability_and_search_phrases",
                        ],
                    },
                },
            },
            "required": [
                "portrait", "markers", "qualifiers", "disqualifiers_anti_market",
                "keystones", "deal_breakers", "inciting_events",
            ],
        },
        "positioning_audit": {
            "type": "object",
            "properties": {
                "buyer_scoreboard_currency": {"type": "string"},
                "pricing_strategy": {
                    "type": "string",
                    "enum": ["More for More", "More for Less", "Less for Less"],
                },
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
            "required": [
                "buyer_scoreboard_currency", "pricing_strategy",
                "statements", "facts_to_verify",
            ],
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
                "required": [
                    "id", "question", "follow_ups",
                    "hypothesis_ids", "polite_stranger_check",
                ],
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

REFLECTION_SCHEMA = {
    "type": "object",
    "properties": {
        "killed_root_causes": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "idea_title": {"type": "string"},
                    "proximate_cause": {"type": "string"},
                    "root_cause": {"type": "string"},
                    "machine_fix": {"type": "string"},
                },
                "required": ["idea_title", "proximate_cause", "root_cause", "machine_fix"],
            },
        },
        "candidate_principles": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "rule": {"type": "string"},
                    "trigger_evidence": {"type": "string"},
                },
                "required": ["title", "rule", "trigger_evidence"],
            },
        },
        "portfolio_synthesis": {"type": "string"},
    },
    "required": ["killed_root_causes", "candidate_principles", "portfolio_synthesis"],
}


# ---------------------------------------------------------------------------
# Workspace, Founder & Full Learned Principles Loading (NO [:2000] slicing!)
# ---------------------------------------------------------------------------

root = Path(WORKSPACES[0]) if WORKSPACES else Path.cwd()
founder_dir = root / "founder"
founder_chunks = []
for fname in ("WHO-ME.md", "VOTERS.md", "FOUNDER-PROFILE.md"):
    fpath = founder_dir / fname
    if fpath.exists():
        content = fpath.read_text(encoding="utf-8").strip()
        if content:
            founder_chunks.append(f"### {fname}\n{content[:8000]}")

founder_context = (
    "\n\n".join(founder_chunks)
    if founder_chunks
    else (
        "No founder/WHO-ME.md, founder/VOTERS.md, or founder/FOUNDER-PROFILE.md found. "
        "Assume a solo or 2-person technical indie founder seeking a bootstrapped, self-serve "
        "or low-touch B2B/prosumer business (Problem Score >= 1.0, low support burden, no "
        "multi-year enterprise procurement, no heavy regulatory/HIPAA barriers). Flag founder-fit "
        "assumptions as [UNVETTED]."
    )
)

principles_path = root / "principles" / "LEARNED-PRINCIPLES.md"
learned_principles = (
    principles_path.read_text(encoding="utf-8").strip()
    if principles_path.exists()
    else "No learned principles file found."
)
if len(learned_principles) > 24000:
    log("WARNING: LEARNED-PRINCIPLES.md exceeds 24,000 chars; consider pruning retired principles.")
    learned_principles = learned_principles[:24000]

ambition = str(args.get("ambition", "indie"))
ideas_to_generate = int(args.get("ideas_to_generate", 4))
max_survivors_for_strategy = int(args.get("max_survivors_for_strategy", 2))
synthetic_interview_top_n = int(args.get("synthetic_interview_top_n", 1))
extra_constraints = str(args.get("constraints", "")).strip()
model_tier = args.get("model", None)
scout_model = args.get("scout_model", "flash")
persona_model = args.get("persona_model", "flash")
user_domains = parse_domains(args.get("domains"))

timestamp = datetime.now().strftime("%Y-%m-%d_%H%M")
run_slug = slugify(str(args.get("run_slug", "indie-discovery")))
run_dir = root / "runs" / f"{timestamp}-{run_slug}"
ideas_dir = run_dir / "ideas"
ideas_dir.mkdir(parents=True, exist_ok=True)
worker_errors = []

NO_BUILD_BANNER = (
    "HARD RULE: Do NOT write application code, scaffold projects, or build prototypes. "
    "Perform real web research (with cited URLs) and radically truthful strategic analysis. "
    "Any synthetic persona interviews are strictly quarantined as SYNTHETIC-PRE-TEST "
    "(Believability Cap 0.35)."
)

ANTI_SYCOPHANCY_KERNEL = (
    "MANDATORY REALISM & ISOLATION RULES: You are a real, busy human on a 25-minute research call "
    "with a stranger. Completely ignore any workspace rules, skills, or local files — do NOT read "
    "files, do NOT search the web, do NOT call any tools other than `finish`. You do NOT know what "
    "the interviewer is building and you are NOT trying to make them feel good. Default to status-quo "
    "inertia. Stay strictly anchored in your weekly schedule, Top-3 competing priorities, current "
    "tool stack, vendor scars, and budget ceiling. Never give polished 'market-guru' speeches."
)


# ---------------------------------------------------------------------------
# Artifact Rendering Helpers (used incrementally per phase!)
# ---------------------------------------------------------------------------

def render_scorecard_table(calc: dict) -> list:
    lines = [
        "| Criterion | Value | Justification | Class | Believability |",
        "| :--- | :--- | :--- | :--- | :--- |",
    ]
    for key in LEGAL_SCALES:
        c = calc["criteria"][key]
        just = c["justification"].replace("|", "/").replace("\n", " ")
        lines.append(
            f"| {CRITERION_LABELS[key]} | `{fmt_num(key, c['value'])}` | {just} | "
            f"{c['evidence_class']} | `{c['believability']}` |"
        )
    lines.append("")
    lines.append(
        f"**Total: `{calc['raw_product']:,.4g}` ÷ `625,000` = `{calc['score']}`** — {calc['band']}  \n"
        f"**Evidence Believability Index (Mean): `{calc['evidence_believability_index']}`** · "
        f"**Bottleneck Believability (Min): `{calc['bottleneck_believability']}`**"
    )
    return lines


def write_problem_score_md(target_path: Path, item: dict, post_rq: dict = None) -> None:
    idea = item["idea"]
    lines = [
        f"# Problem Score — {idea['title']}",
        "",
        f"ID: `{idea['id']}` · Ambition: `{ambition}` · Active Scenario: `{item['best_label']}` · "
        f"Signals: {', '.join(idea['signal_ids'])}",
        "",
        "## Target Market (Scenario A)",
        f"- **Buyer:** {item['scenario_a_raw']['target_buyer']}",
        f"- **Problem:** {item['scenario_a_raw']['problem']}",
        f"- **Trade-offs:** {item['scenario_a_raw']['trade_offs']}",
        f"- **Price:** {item['scenario_a_raw']['price']} ({item['scenario_a_raw']['pricing_strategy']})",
        "",
        "## Scores (Scenario A)",
        *render_scorecard_table(item["scenario_a_calc"]),
        "",
        f"**Dominant weak links:** {'; '.join(item['scenario_a_raw']['dominant_weak_links'])}",
        "",
    ]
    if item["scenario_b_raw"] and item["scenario_b_calc"]:
        lines.extend([
            "## Scenario B — Narrowed Niche",
            f"- **Buyer:** {item['scenario_b_raw']['target_buyer']}",
            f"- **Problem:** {item['scenario_b_raw']['problem']}",
            f"- **Trade-offs:** {item['scenario_b_raw']['trade_offs']}",
            f"- **Price:** {item['scenario_b_raw']['price']} ({item['scenario_b_raw']['pricing_strategy']})",
            "",
            *render_scorecard_table(item["scenario_b_calc"]),
            "",
            f"**Dominant weak links:** {'; '.join(item['scenario_b_raw']['dominant_weak_links'])}",
            "",
        ])
    if post_rq:
        lines.extend([
            "## Post-Rude Q&A Adjusted Scores",
            f"- **Locked Buyer:** {post_rq['verdict_out']['adjusted_scorecard']['target_buyer']}",
            f"- **Locked Price:** {post_rq['verdict_out']['adjusted_scorecard']['price']} "
            f"({post_rq['verdict_out']['adjusted_scorecard']['pricing_strategy']})",
            "",
            *render_scorecard_table(post_rq["post_calc"]),
            "",
        ])
    sources = list(dict.fromkeys(
        (item["scenario_a_raw"].get("sources") or [])
        + ((item["scenario_b_raw"] or {}).get("sources") or [])
        + ((post_rq["verdict_out"]["adjusted_scorecard"].get("sources") or []) if post_rq else [])
    ))
    if sources:
        lines.append("## Sources")
        lines.extend([f"- {u}" for u in sources])
        lines.append("")
    target_path.write_text("\n".join(lines), encoding="utf-8")


def write_rude_qa_md(target_path: Path, pr: dict) -> None:
    idea = pr["item"]["idea"]
    rq = pr["rude_qa"]
    a1, d1, v = rq["attack_1"], rq["defense_1"], rq["verdict_out"]
    lines = [
        f"# Rude Q&A — {idea['title']}",
        "",
        f"**Verdict:** `{v['verdict']}` · **Pre-Attack Score:** `{pr['item']['best_calc']['score']}` → "
        f"**Post-Attack Score:** `{rq['post_calc']['score']}` "
        f"(EBI `{rq['post_calc']['evidence_believability_index']}`, Min `{rq['post_calc']['bottleneck_believability']}`) · "
        f"**Dwell Triggered:** `{'Yes' if rq['dwell_triggered'] else 'No'}`",
        "",
        f"> {v['verdict_summary']}",
        "",
        "## Attack Findings (Round 1)",
        "### Opposite Test Failures",
        *([f"- {x}" for x in a1["opposite_test_failures"]] or ["- None flagged."]),
        "",
        "### Fluffy Language Flagged",
        *([f"- {x}" for x in a1["fluffy_words_flagged"]] or ["- None flagged."]),
        "",
        "### Present-Tense Threats (>=70% Bar)",
        *([f"- {x}" for x in a1["present_tense_threats"]] or ["- None flagged."]),
        "",
        "### Scars & Founder-Fit Attacks",
        *([f"- {x}" for x in a1["scars_and_founder_fit_attacks"]] or ["- None flagged."]),
        "",
        "### Challenge From Below (Problem Score)",
        *[
            f"- **{CRITERION_LABELS[c['criterion']]}** (`{c['current_value']}` → `{c['proposed_lower_value']}`): {c['attack']}"
            for c in a1["challenge_from_below"]
        ],
        "",
        "### Unfair Questions",
        *[f"- {q}" for q in a1["unfair_questions"]],
        "",
        "### Competitor / Threat Evidence URLs",
        *([f"- {u}" for u in a1["competitor_evidence_urls"]] or ["- None listed."]),
        "",
        "## Advocate Response (Round 1)",
        "### Real Decision Revisions",
        *([f"- {x}" for x in d1["real_decisions_revisions"]] or ["- None."]),
        "",
        "### Threat Responses",
        *([f"- {x}" for x in d1["threat_responses"]] or ["- None."]),
        "",
        "### Score Defenses / Concessions",
        *[
            f"- **{CRITERION_LABELS[c['criterion']]}** (`{c['stance']}` → `{c['final_value']}`): {c['reasoning']}"
            for c in d1["score_defenses_or_concessions"]
        ],
        "",
        f"**How Could I Be Wrong (Advocate):** {d1['how_could_i_be_wrong']}",
        "",
        f"**Honest Concession Note:** {d1['honest_concession_if_fatal'] or 'None.'}",
        "",
    ]
    if rq["dwell_triggered"] and rq.get("dwell_check") and rq.get("defense_2"):
        dc = rq["dwell_check"]
        d2 = rq["defense_2"]
        lines.extend([
            "## Round 2 — Conditional Dwell Interrogation",
            f"**Why Attacker Dwelt:** {dc['dwell_reason']}",
            *[f"- **Dwell Attack:** {q}" for q in dc["dwell_follow_up_questions"]],
            "",
            "### Advocate Round-2 Sharpened Defense",
            *([f"- {x}" for x in d2["real_decisions_revisions"]] or ["- None."]),
            *([f"- {x}" for x in d2["threat_responses"]] or []),
            f"- **Concession note:** {d2['honest_concession_if_fatal'] or 'None.'}",
            "",
        ])
    lines.extend([
        "## Locked Interrogation Outcomes",
        "### Real Decisions Locked",
        *([f"- {x}" for x in v["real_decisions_locked"]] or ["- None locked."]),
        "",
        "### Fluff Replaced",
        *([f"- {x}" for x in v["fluff_replaced"]] or ["- None."]),
        "",
        "### Threats Clarified",
        *([f"- {x}" for x in v["threats_clarified"]] or ["- None."]),
        "",
        "### Open Questions for Field Interviews",
        *([f"- {x}" for x in v["open_questions_for_field"]] or ["- None."]),
        "",
    ])
    target_path.write_text("\n".join(lines), encoding="utf-8")


def write_decision_record_md(target_path: Path, pr: dict) -> None:
    idea = pr["item"]["idea"]
    rq = pr["rude_qa"]
    cev = pr["consequence_ev"]
    ev_m = pr["ev_metrics"]
    pan = pr["panel"]
    sc_calc = pr["item"]["best_calc"]
    lines = [
        f"# Dalio Decision Record — {idea['title']}",
        "",
        f"**Panel Weighted Score:** `{pan['panel_weighted_score']}` (range `-1.0` to `+1.0`) · "
        f"**Disagreement Flag:** `{'YES — SPLIT PANEL' if pan['disagreement_flag'] else 'No'}` · "
        f"**Phase 3 Scorer:** `{sc_calc['score']}` · **Post-Rude Q&A Score:** `{rq['post_calc']['score']}` · "
        f"**EBI (Mean / Min):** `{rq['post_calc']['evidence_believability_index']}` / `{rq['post_calc']['bottleneck_believability']}`",
        "",
        "## 1. Independent Believability-Weighted Specialist Panel",
        "| Specialist | Weight | Stance | Vote | Key Basis |",
        "| :--- | :--- | :--- | :--- | :--- |",
        f"| Problem Scorer (Phase 3 Market Economist) | `0.30` | `{sc_calc['band'].split(' ')[0]}` | `{pan['votes']['scorer']}` | Independent Phase 3 Score `{sc_calc['score']}` ({pr['item']['best_label']}), EBI `{sc_calc['evidence_believability_index']}` (min `{sc_calc['bottleneck_believability']}`) |",
        f"| Rude Q&A Attacker (Phase 4A Skeptic) | `0.40` | `{rq['verdict_out']['verdict']}` | `{pan['votes']['attacker']}` | Post-Attack Score `{rq['post_calc']['score']}` — {rq['verdict_out']['verdict_summary'].replace('|', '/')} |",
        f"| Consequence & EV Analyst (Phase 4B Systems) | `0.30` | `{cev['recommendation']}` | `{pan['votes']['consequence_ev']}` | {cev['recommendation_reasoning'].replace('|', '/')} |",
        "",
        "## 2. Root-Cause Market Persistence Diagnosis",
        f"- **Why this pain still exists:** {cev['root_cause_persistence']}",
        f"- **Indie-favorable root cause?** `{'Yes' if cev['root_cause_is_indie_favorable'] else 'No (Caution)'}`",
        "",
        "## 3. First-, Second-, and Third-Order Consequences",
        "### First-Order (Day 1 / Immediate)",
        *[f"- {x}" for x in cev["first_order_consequences"]],
        "",
        "### Second-Order (Months 3–12: Support, Churn, CAC, Buyer Behavior)",
        *[f"- {x}" for x in cev["second_order_consequences"]],
        "",
        "### Third-Order (Years 1–3: Platform Bundling, Incumbent Response, Equilibrium)",
        *[f"- {x}" for x in cev["third_order_consequences"]],
        "",
        "## 4. Expected Value (EV — Deterministic Python Math) & Pre-Committed Kill Trigger",
        f"- **Numeric `P(Viable)`:** `{ev_m['p_viable_pct']}%`",
        f"- **Target Year-2 Indie ARR:** `${ev_m['target_arr_usd']:,.0f}` ({cev['upside_indie_band']})",
        f"- **Pre-Build Validation Effort:** `{ev_m['validation_hours']:.0f} hrs` ({cev['pre_build_validation_cost']})",
        f"- **Expected ARR (`P × Target ARR`):** `${ev_m['expected_arr_usd']:,.0f}` (`${ev_m['ev_per_validation_hour']:,.0f}` expected ARR per validation hour)",
        f"- **Highest-EV Falsification Test:** {cev['highest_ev_falsification_test']}",
        f"- **PRE-COMMITTED KILL TRIGGER:** **{cev['pre_committed_kill_trigger']}**",
        "",
        "## 5. Blind-Spot Checks ('How Could I Be Wrong?')",
        f"- **Consequence/EV Analyst:** {cev['how_could_i_be_wrong']}",
        f"- **Rude Q&A Advocate:** {rq['defense_1']['how_could_i_be_wrong']}",
        "",
    ]
    target_path.write_text("\n".join(lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Phase 0 — Domain & Lens Selection
# ---------------------------------------------------------------------------

phase("0. Goals, Principles & Lens Setup")
log(f"Run directory: {run_dir}")
log(f"Founder files loaded: {len(founder_chunks)} | Learned principles chars: {len(learned_principles)}")

if user_domains:
    lenses = [
        {
            "domain": d,
            "search_hypothesis": f"Mine real complaints, ugly workarounds, incumbent pricing, and live inciting events in: {d}",
            "why_indie_friendly": "User-supplied domain lens",
        }
        for d in user_domains
    ]
    log(f"Using {len(lenses)} user-supplied domain lenses.")
else:
    log("No domains supplied; invoking Domain & Lens Strategist...")
    lens_result = await agent(
        prompt=(
            f"{NO_BUILD_BANNER}\n\n"
            "You are the Domain & Lens Strategist for an ASB + Ray Dalio Indie Startup Idea Foundry.\n"
            "Use `search_web` to verify market-size baselines BEFORE selecting 3 distinct, concrete, "
            "indie-friendly market lenses to scout.\n"
            "Avoid broad vague labels ('AI', 'SMBs') AND avoid disconnected sidecars around legacy SORs (DP26) "
            "or dev-tool-for-dev-tool micro-niches (DP25).\n"
            "Each lens MUST target a standalone, single-buyer, daily or per-project core operational product "
            "in a verified 100k-10M non-dev category where the paying buyer owns 100% of input data, "
            "swipes a card without enterprise procurement/regulated-PII barriers (DP10/DP22), and has real "
            "allocated budgets ($100-$1k+/yr).\n\n"
            f"Ambition: {ambition}\n"
            f"Extra constraints: {extra_constraints or 'None'}\n\n"
            f"Founder context:\n{founder_context}\n\n"
            f"Standing Decision Principles (ALL of them):\n{learned_principles}\n\n"
            "Return 3 sharp lenses via finish."
        ),
        schema=DOMAINS_SCHEMA,
        role="Domain & Lens Strategist",
        type_name="self",
        model=model_tier,
    )
    lenses = lens_result["lenses"]
    log(f"Selected lenses: {[l['domain'] for l in lenses]}")


# ---------------------------------------------------------------------------
# Phase 1 — Parallel Pain & Incumbent Scouting (Fault-Tolerant)
# ---------------------------------------------------------------------------

phase("1. Pain & Incumbent Scouting")


async def run_scout_safe(lens: dict) -> dict:
    try:
        res = await agent(
            prompt=(
                f"{NO_BUILD_BANNER}\n\n"
                "You are an ASB + Dalio Pain & Incumbent Scout.\n"
                f"Assigned domain: {lens['domain']}\n"
                f"Search hypothesis: {lens['search_hypothesis']}\n"
                f"Ambition: {ambition} | Extra constraints: {extra_constraints or 'None'}\n\n"
                f"Standing Decision Principles:\n{learned_principles}\n\n"
                "Use `search_web` thoroughly to mine REAL, PUBLIC, CITED pain artifacts:\n"
                "1. 1-3 star reviews on G2, Capterra, Trustpilot, Shopify/WordPress/Chrome app stores.\n"
                "2. Reddit, Hacker News, or niche trade forum threads with ugly workarounds or spend.\n"
                "3. Real incumbent pricing pages proving ALLOCATED BUDGET.\n"
                "4. Live inciting events (pricing hikes, deprecations, compliance deadlines, outages).\n"
                "5. MANDATORY 3-LAYER DE-JARGONIZED FLOOR, TRAILING-18-MO CLOUD/OSS & SWITCHING-RAIL SWEEP (DP18, DP20, DP23):\n"
                "   For EVERY signal you report, actively run web queries for:\n"
                "   (a) de-jargonized horizontal functional-primitive rivals ('free <primitive> tool', '<primitive> under $50', GitHub OSS),\n"
                "   (b) vertical specialists under $100/mo — VERIFY their LIVE 2025-2026 feature pages (never assume an incumbent lacks a feature without checking!),\n"
                "   (c) trailing-18-month native host/cloud/POS/platform add-ons (Shopify, Toast, HubSpot, AWS, Apple, Google, etc.),\n"
                "   (d) switching rails & calendar freeze windows (stored customer cards, annual contracts, tax/BFCM freezes, or true year-round Liquid = 1.0 per-job fresh adoption).\n"
                "   Record what you found honestly inside `incumbents_and_pricing`! Do NOT hide cheap rivals.\n\n"
                "Assign `evidence_believability` strictly from {0.4, 0.7, 1.0}:\n"
                "- 1.0 = direct primary pricing page, official deprecation/regulation, or disclosed data\n"
                "- 0.7 = triangulated across 3+ independent firsthand user reports\n"
                "- 0.4 = single public thread/review or secondary estimate\n"
                "Never invent quotes, URLs, or pricing. Return 3 to 5 signals via finish."
            ),
            schema=SCOUT_SCHEMA,
            role=f"Pain Scout — {lens['domain'][:32]}",
            type_name="self",
            model=scout_model,
        )
        return {"ok": True, "data": res}
    except Exception as exc:
        return {"ok": False, "domain": lens["domain"], "error": str(exc)}


scout_wrapped = await parallel(lenses, run_scout_safe)
scout_reports = []
for w in scout_wrapped:
    if w["ok"]:
        scout_reports.append(w["data"])
    else:
        msg = f"Phase 1 scout failed [{w['domain']}]: {w['error']}"
        log(f"WARNING: {msg}")
        worker_errors.append(msg)

if not scout_reports:
    raise RuntimeError(f"All Phase 1 scouts failed: {worker_errors}")

all_signals = []
sig_idx = 1
for report in scout_reports:
    for sig in report["signals"]:
        sig_copy = dict(sig)
        sig_copy["id"] = f"SIG-{sig_idx}"
        sig_copy["domain"] = report["domain"]
        sig_copy["evidence_believability"] = snap_believability(sig_copy.get("evidence_believability", 0.4))
        all_signals.append(sig_copy)
        sig_idx += 1

log(f"Collected {len(all_signals)} cited public pain signals across {len(scout_reports)} scouts.")

pain_lines = [
    f"# Public Pain Signals — {run_slug}",
    "",
    f"Collected: {datetime.now().strftime('%Y-%m-%d %H:%M')} · Total signals: {len(all_signals)}",
    "",
    "> External research seed material weighted by Dalio Evidence Believability "
    "(`1.0` primary proof, `0.7` triangulated 3+ firsthand reports, `0.4` single anecdote/secondary).",
    "",
]
for s in all_signals:
    pain_lines.extend([
        f"## {s['id']} — {s['title']} *(Believability: `{s['evidence_believability']}`)*",
        f"- **Domain:** {s['domain']}",
        f"- **Channel / Source:** {s['channel']} ({s['source_url']})",
        f"- **Affected Buyer:** {s['affected_buyer']}",
        f"- **Observed Pain & Workaround:** {s['observed_pain_and_workaround']}",
        f"- **Incumbents & Real Pricing:** {s['incumbents_and_pricing']}",
        f"- **Observed Inciting Event:** {s['inciting_event_observed']}",
        "",
    ])
(run_dir / "PAIN-SIGNALS.md").write_text("\n".join(pain_lines), encoding="utf-8")


# ---------------------------------------------------------------------------
# Phase 2 — Market-First Idea Synthesis + Checkpoint
# ---------------------------------------------------------------------------

phase("2. Idea Synthesis")
signals_json = json.dumps(all_signals, indent=2)

architect_out = await agent(
    prompt=(
        f"{NO_BUILD_BANNER}\n\n"
        "You are the ASB + Dalio Idea Architect. Synthesize raw public pain signals into exactly "
        f"{ideas_to_generate} concrete, distinct indie startup ideas.\n\n"
        f"Ambition: {ambition}\n"
        f"Extra constraints: {extra_constraints or 'None'}\n\n"
        f"Founder context:\n{founder_context}\n\n"
        f"Standing Decision Principles (respect EVERY one):\n{learned_principles}\n\n"
        f"Public pain signals (prioritize higher evidence_believability signals):\n{signals_json}\n\n"
        "NON-NEGOTIABLE GATES:\n"
        "1. Stranger-sortable buyer (NEVER 'SMBs', 'indie makers', 'creators', or 'busy teams').\n"
        "2. Ground every idea in specific signal IDs.\n"
        "3. Deliberate trade-offs passing the Opposite Test.\n"
        "4. Concrete price + pricing strategy ('More for More', 'More for Less', 'Less for Less').\n"
        "5. Indie feasibility: buildable & supportable by 1-2 people without enterprise sales.\n"
        "6. Avoid first-order seduction (NEVER pitch pure flat-fee clones of hated flagships where $0-$60/mo vertical tools or POS bundles already exist — DP20).\n"
        "7. WINNING ASB MATH QUADRANT (DP16-DP21): Every idea MUST clear one of two honest structural paths:\n"
        "   - Path A (Per-Project / Per-Campaign / Non-Rip-and-Replace, Liquid = 1.0): Buyer adopts fresh on their NEXT project, client engagement, campaign, or asset WITHOUT migrating stored customer cards, consumer URLs/apps, POS, or annual contracts, AND post-filter Plausible x Lucrative >= $10M (e.g., 100k x $100-$1k/yr or 10k x $1k/yr), with a non-price structural/capability wedge that beats every $0-$60/mo rival found in Phase 1.\n"
        "   - Path B (Massive-Denominator Core Tool, Plausible = 1M-10M at $100/yr): Truly huge existing category (like ConvertKit/WP Engine/Tally/Plausible) whose 1M-10M post-filter buyer pool mathematically absorbs Liquid = 0.1 or 0.01, won via an incumbent-uncopyable architectural or audience specialization (NOT generic flat-fee cloning).\n"
        "8. PER-LENS COVERAGE & REALITY ACCURACY (DP23, DP25): Produce balanced coverage across ALL scouted domain lenses (when generating 3 ideas from 3 lenses, emit EXACTLY 1 idea per lens — never let dev-tool signals crowd out non-dev lenses!). Never claim a named competitor lacks a feature unless verified in the Phase 1 signals; acknowledge every real sub-$100 rival honestly upfront and explain the exact verified structural gap they leave open. Prioritize B2B/SMB recurring workflows (Enduring >= 0.5) over high-churn hobbyist creator apps or one-time cleanup projects. NO artificial multi-trade bundling (DP21), NO ToS-violating portal automation (DP12), NO regulated PII/PHI/NPI stateless-washing or catastrophic liability transfer (DP10, DP22), NO seasonal freeze traps (DP24), and NO greenfield 'newly opening business' escapes (DP19).\n"
        "9. Zero fluff words (seamless, robust, scalable, innovative, AI-powered, easy, solution).\n"
        "10. Sequential IDs: 'IDEA-1', 'IDEA-2', ..."
    ),
    schema=ARCHITECT_SCHEMA,
    role="Idea Architect",
    type_name="self",
    model=model_tier,
)

candidates = architect_out["ideas"]
(run_dir / "candidates.json").write_text(json.dumps(candidates, indent=2), encoding="utf-8")
log(f"Synthesized & checkpointed {len(candidates)} candidate ideas: {[c['title'] for c in candidates]}")


# ---------------------------------------------------------------------------
# Phase 3 — Parallel Fermi Problem Scoring + Scenario B + Checkpoints
# ---------------------------------------------------------------------------

phase("3. Fermi Problem Scoring & Evidence Believability")

SCORING_INSTRUCTIONS = f"""{NO_BUILD_BANNER}

You are an independent ASB Problem Scorer (Market Economist, Panel Weight 0.30).
You have ZERO loyalty to this idea, AND NO CURVE IN EITHER DIRECTION (`asb-problem` rule):
- Challenge optimistic numbers from below: ask what makes the NEXT legal value DOWN wrong.
- Equally, when a criterion genuinely earns a strong value via real evidence or sound structural
  differentiation, record it plainly WITHOUT manufactured skepticism. The goal is a TRUE number,
  not an artificially low one.

Use `search_web` at page-one Fermi depth to verify counts, active demand, competitor
pricing, switching friction, indie trust barriers, and competition.

EXACT LEGAL SCALE VALUES & `asb-problem` DEFINITIONS:
- plausible: {LEGAL_SCALES['plausible']} (specific buyers who actually have the problem)
- self_aware: {LEGAL_SCALES['self_aware']} (0.01 few agree/care; 0.1 thought-leaders evangelize; 0.5 industry standard practice; 1.0 almost everyone cares)
- lucrative: {LEGAL_SCALES['lucrative']} (demonstrated annual allocated net revenue budget — what buyers actually pay today)
- liquid: {LEGAL_SCALES['liquid']} (0.01 every few years / heavy lock-in; 0.1 annual decision; 1.0 always in market / easy per-project or fresh adoption)
- eager_identity: {LEGAL_SCALES['eager_identity']} (0 structurally barred by policy/SOC2/fiat; 0.1 structural trust barriers; 0.5 indifferent / normal indie credit-card swipe; 1.0 mission-level pull)
- eager_comparative: {LEGAL_SCALES['eager_comparative']} (0.1 no material differentiation / commodity clone; 0.5 some things so good that a clear sub-segment buys for them alone — even when free/cheap generalists exist; 1.0 one-of-a-kind with no viable alternative)
- enduring: {LEGAL_SCALES['enduring']} (0.01 one-off no loyalty; 0.1 one-off with repeats/referrals; 0.5 recurring revenue from recurring problem; 1.0 strong system-of-record lock-in)

CANONICAL `asb-problem` CALIBRATION ANCHORS (calibrate your scale strictly to these!):
- Managed WP Hosting (WP Engine): 100M x 0.1 x $100 x 0.01 x 0.5 x 0.5 x 1.0 = 4.0 (NOTE: earned Eager-Comparative = 0.5 despite thousands of $3/mo shared WP hosts!)
- Creator Email Marketing (ConvertKit): 10M x 1.0 x $100 x 0.01 x 0.5 x 0.5 x 0.5 = 2.0 (NOTE: earned Eager-Comparative = 0.5 despite FREE Mailchimp and $19/mo AWeber because creator-specific trade-offs made a clear segment buy for them alone!)
- Consumer Security Software: 1B x 0.01 x $10 x 0.01 x 0.5 x 0.1 x 0.5 = 0.04 (undifferentiated commodity -> 0.1)

CRITICAL CALIBRATION GUARDRAILS (`asb-problem` faithful math — ZERO double-counting, ZERO manufactured cynicism):
1. `Plausible` (DP35): Score the coarse power-of-10 count of specific buyers who HAVE the problem (like WP Engine = 100M WP sites, ConvertKit = 10M creators). Do NOT multiply switching-timing (`Liquid`), awareness (`Self-Aware`), or competitor-preference (`Eager`) filters into `Plausible` — each already multiplies separately!
2. `Eager-Comparative` (DP36): Do NOT require "zero free or sub-$60 competitors exist anywhere" for `0.5` (that is `1.0`!). Give `0.1` if an existing free/cheap tool ALREADY solves the exact core wedge cleanly for the same buyer; give `0.5` if the idea makes a structural trade-off incumbents refuse to copy so a clear sub-segment buys for that difference alone.
3. `Eager-Identity` (DP37): `0.5` ("indifferent, no red flags") is the honest baseline for self-serve credit-card SaaS sold to creators, developers, freelancers, small agencies, or SMB owners (especially when data/infra is customer-owned/portable). Reserve `0.1` for genuine institutional trust walls (SOC 2, Entra Admin Consent, HIPAA/IRS/legal liability).

DALIO EVIDENCE BELIEVABILITY WEIGHT PER CRITERION (exact values from {{0.2, 0.4, 0.7, 1.0}}):
- 1.0 = primary proof (live pricing page, official census/regulatory data, real customer data — MUST cite URL in `sources`)
- 0.7 = triangulated across 3+ independent firsthand public reports (MUST cite URLs in `sources`)
- 0.4 = single public anecdote or credible secondary estimate
- 0.2 = uncited Fermi reasoning (NOTE: '[fermi]' entries are strictly capped <= 0.4!)

Tag each criterion '[research]', '[fermi]', or '[data]'.
"""


async def score_candidate_safe(idea: dict) -> dict:
    try:
        scorer = agent(
            prompt=SCORING_INSTRUCTIONS,
            role=f"Problem Scorer — {idea['title'][:28]}",
            type_name="self",
            model=model_tier,
        )
        idea_json = json.dumps(idea, indent=2)
        scen_a_raw = await scorer(
            prompt=(
                "Score Scenario A using live web research:\n\n"
                f"{idea_json}\n\n"
                f"Ambition: {ambition}\n"
                f"Founder context (for Eager-Identity):\n{founder_context[:2500]}\n\n"
                f"Standing Decision Principles:\n{learned_principles}\n\n"
                "Return the complete Scenario A scorecard via finish."
            ),
            schema=SCORECARD_OBJECT_SCHEMA,
        )
        scen_a_calc = compute_problem_score(scen_a_raw)

        scen_b_raw = None
        scen_b_calc = None
        if scen_a_calc["score"] < 1.0:
            scen_b_raw = await scorer(
                prompt=(
                    f"Scenario A scored {scen_a_calc['score']} (EBI={scen_a_calc['evidence_believability_index']}, "
                    f"Min={scen_a_calc['bottleneck_believability']}).\n"
                    f"Weak links: {scen_a_raw['dominant_weak_links']}\n\n"
                    "Run `asb-problem` Phase D — Scenario B Narrowing:\n"
                    "Propose ONE sharper niche or repriced wedge that concentrates Self-Aware, Lucrative, "
                    "and Eager even if Plausible drops 10x. Only change criteria genuinely affected by "
                    "the niche shift — do NOT inflate unrelated criteria. Score honestly on legal scales."
                ),
                schema=SCORECARD_OBJECT_SCHEMA,
            )
            scen_b_calc = compute_problem_score(scen_b_raw)
        del scorer

        # Choose Scenario B only if it genuinely improves score AND doesn't replace high-EBI A with pure 0.2 guess
        best_label = "Scenario A"
        best_raw = scen_a_raw
        best_calc = scen_a_calc
        if (
            scen_b_calc
            and scen_b_calc["score"] > scen_a_calc["score"]
            and scen_b_calc["evidence_believability_index"] >= max(0.3, scen_a_calc["evidence_believability_index"] - 0.25)
        ):
            best_label = "Scenario B"
            best_raw = scen_b_raw
            best_calc = scen_b_calc

        # Collision-safe slug prefixed with idea ID
        slug = f"{slugify(idea['id'], 12)}-{slugify(idea['title'], 32)}"
        active_market = {
            "scenario_label": best_label,
            "target_buyer": best_raw["target_buyer"],
            "problem": best_raw["problem"],
            "trade_offs": best_raw["trade_offs"],
            "price": best_raw["price"],
            "pricing_strategy": best_raw["pricing_strategy"],
        }
        item = {
            "idea": idea,
            "slug": slug,
            "scenario_a_raw": scen_a_raw,
            "scenario_a_calc": scen_a_calc,
            "scenario_b_raw": scen_b_raw,
            "scenario_b_calc": scen_b_calc,
            "best_label": best_label,
            "best_raw": best_raw,
            "best_calc": best_calc,
            "active_market": active_market,
        }
        # Incremental checkpoint!
        d = ideas_dir / slug
        d.mkdir(parents=True, exist_ok=True)
        write_problem_score_md(d / "PROBLEM-SCORE.md", item)
        return {"ok": True, "data": item}
    except Exception as exc:
        return {"ok": False, "idea": idea["title"], "error": str(exc)}


scored_wrapped = await parallel(candidates, score_candidate_safe)
scored_results = []
for w in scored_wrapped:
    if w["ok"]:
        scored_results.append(w["data"])
    else:
        msg = f"Phase 3 scorer failed [{w['idea']}]: {w['error']}"
        log(f"WARNING: {msg}")
        worker_errors.append(msg)

passing_to_panel = []
killed_ideas = []

for item in scored_results:
    score = item["best_calc"]["score"]
    ebi = item["best_calc"]["evidence_believability_index"]
    mn = item["best_calc"]["bottleneck_believability"]
    log(
        f"{item['idea']['id']} ({item['idea']['title']}): "
        f"A={item['scenario_a_calc']['score']}"
        + (f", B={item['scenario_b_calc']['score']}" if item["scenario_b_calc"] else "")
        + f" -> best={score} (EBI={ebi}, Min={mn}, {item['best_label']})"
    )
    if score >= 0.5 and item["best_calc"]["criteria"]["eager_identity"]["value"] > 0.0:
        passing_to_panel.append(item)
    else:
        killed_ideas.append({
            "stage": "Phase 3 — Problem Score",
            "item": item,
            "reason": (
                f"Best Problem Score = {score} (EBI={ebi}, Min={mn}, {item['best_calc']['band']}). "
                f"Weak links: {'; '.join(item['best_raw']['dominant_weak_links'])}"
            ),
        })

log(f"Passing to Triangulation Panel: {len(passing_to_panel)} | Killed at Problem Score: {len(killed_ideas)}")


# ---------------------------------------------------------------------------
# Phase 4 — Parallel Triangulation Panel (with Conditional Dwell + Founder Context)
# ---------------------------------------------------------------------------

phase("4. Rude Q&A Court (With Dwell) + Dalio Consequence & EV Triangulation")


async def run_rude_qa_court(item: dict, brief: str) -> dict:
    title = item["idea"]["title"]
    attacker = agent(
        prompt=(
            f"{NO_BUILD_BANNER}\n\n"
            "You are the Rude Q&A Interrogator (`asb-rude-qa`, Panel Weight 0.40).\n"
            "Posture: Rude questions, collegial framing. Attack the claim, never the person. "
            "NEVER settle for 'approximately fine.'\n"
            "Use `search_web` specifically to find facts that KILL this idea (free/bundled "
            "incumbents, native platform launches, compliance walls, failed indies).\n"
            "Run Opposite Test, fluff audit, >=70% present-tense threats, scars/founder-fit probe, "
            "unfair questions, and challenge the 2 softest Problem Score criteria from below.\n\n"
            f"Founder context (for scars & Eager-Identity probes):\n{founder_context[:3000]}\n\n"
            f"Standing Decision Principles:\n{learned_principles}"
        ),
        role=f"Rude Q&A Attacker — {title[:24]}",
        type_name="self",
        model=model_tier,
    )
    attack_1 = await attacker(
        prompt=f"Attack this indie startup candidate ruthlessly using live web search:\n\n{brief}",
        schema=ATTACK_TURN1_SCHEMA,
    )

    advocate = agent(
        prompt=(
            f"{NO_BUILD_BANNER}\n\n"
            "You are the Idea Advocate in Rude Q&A. Practice Dalio's open-mindedness: defend with "
            "concrete trade-offs and evidence where strong, CONCEDE honestly where weak, and state "
            "plainly 'how_could_i_be_wrong'. Never use fluff or 'we'll figure it out later'.\n\n"
            f"Founder context:\n{founder_context[:2500]}"
        ),
        role=f"Idea Advocate — {title[:26]}",
        type_name="self",
        model=model_tier,
    )
    defense_1 = await advocate(
        prompt=(
            f"Candidate & active market scorecard:\n{brief}\n\n"
            f"Rude Q&A Attack (Round 1):\n{json.dumps(attack_1, indent=2)}\n\n"
            "Respond crisply and honestly via finish."
        ),
        schema=ADVOCATE_SCHEMA,
    )

    # Conditional Round-2 Dwell check (real asb-rude-qa dwelling!)
    dwell_check = await attacker(
        prompt=(
            f"Advocate Round-1 response:\n{json.dumps(defense_1, indent=2)}\n\n"
            "Did the Advocate dodge any core attack with fluff, wishful thinking, or vague defenses? "
            "Set `needs_dwell: true` ONLY if pressing one more round could decisively clarify or kill "
            "a fuzzy defense; otherwise set `needs_dwell: false`."
        ),
        schema=DWELL_CHECK_SCHEMA,
    )

    defense_2 = None
    dwell_triggered = bool(dwell_check["needs_dwell"])
    if dwell_triggered:
        defense_2 = await advocate(
            prompt=(
                f"The Attacker is DWELLING on weak spots: {dwell_check['dwell_reason']}\n"
                f"Follow-up attacks:\n{json.dumps(dwell_check['dwell_follow_up_questions'], indent=2)}\n\n"
                "Answer sharply with concrete trade-offs or honest concessions via finish."
            ),
            schema=ADVOCATE_SCHEMA,
        )
    del advocate

    verdict_prompt = (
        f"Advocate Round-1 defense:\n{json.dumps(defense_1, indent=2)}\n\n"
        + (f"Advocate Round-2 Dwell defense:\n{json.dumps(defense_2, indent=2)}\n\n" if defense_2 else "")
        + "Judge ruthlessly with NO CURVE IN EITHER DIRECTION (`asb-problem` / `asb-rude-qa` calibration): "
        "stay unsparing against real flaws, fluff, unverified competitor claims, and `Eager-Comparative = 0.1` "
        "undifferentiated clones, AND equally calibrate `Eager-Comparative = 0.5` accurately to `ConvertKit (2.0)` / "
        "`WP Engine (4.0)` (a clear sub-segment buys for a deliberate structural trade-off incumbents refuse to copy — "
        "NOT 'zero competitors on Earth'). Issue `SHARPENED` honestly when the candidate survives your hardest "
        "present-tense attacks with verified >= 1.0 math and concrete locked decisions, `NOT_YET_READY` if viable "
        "but still fuzzy, or `BAD_IDEA` if fatally broken. Emit full `adjusted_scorecard` on exact legal scale "
        "values + legal believability weights ({0.2, 0.4, 0.7, 1.0}; '[fermi]' capped <= 0.4; >= 0.7 requires cited URLs)."
    )
    verdict_out = await attacker(prompt=verdict_prompt, schema=VERDICT_SCHEMA)
    del attacker

    post_calc = compute_problem_score(verdict_out["adjusted_scorecard"])
    return {
        "attack_1": attack_1,
        "defense_1": defense_1,
        "dwell_triggered": dwell_triggered,
        "dwell_check": dwell_check,
        "defense_2": defense_2,
        "verdict_out": verdict_out,
        "post_calc": post_calc,
    }


async def run_consequence_ev_analyst(item: dict, brief: str) -> dict:
    title = item["idea"]["title"]
    return await agent(
        prompt=(
            f"{NO_BUILD_BANNER}\n\n"
            "You are the Ray Dalio Consequence & Expected-Value Analyst (Systems Thinker, Panel Weight 0.30).\n"
            "You run INDEPENDENTLY of Rude Q&A to provide genuine triangulation.\n\n"
            f"Founder context:\n{founder_context[:2500]}\n\n"
            f"Standing Decision Principles (ALL):\n{learned_principles}\n\n"
            f"Candidate & active market scorecard:\n{brief}\n\n"
            "Use `search_web` where helpful to check platform bundling history and adjacent indie unit economics.\n"
            "Deliver:\n"
            "1. Root-Cause Persistence: WHY hasn't this pain been solved cleanly? Indie-favorable or trap?\n"
            "2. 1st-, 2nd-, and 3rd-Order Consequences (Day 1 -> Months 3-12 -> Years 1-3).\n"
            "3. Numeric Expected Value inputs: `p_viable_pct` (0-100), realistic `target_arr_usd` "
            "(Year-2 indie ARR if it works, e.g. 120000), `validation_hours` (hours for 10-15 pre-build "
            "interviews, e.g. 20), plus highest-EV falsification test & concrete `pre_committed_kill_trigger`.\n"
            "4. Independent Recommendation ('PURSUE_VALIDATION', 'GATHER_MORE_EVIDENCE', or 'KILL') + "
            "explicit `how_could_i_be_wrong`.\n"
            "NO CURVE IN EITHER DIRECTION: Recommend `KILL` whenever structural 2nd/3rd-order consequences, "
            "platform bundling, or negative EV make pre-build interviews a waste of time; recommend "
            "`PURSUE_VALIDATION` honestly when root-cause persistence is indie-favorable, EV per validation hour "
            "is genuinely attractive, and clear falsification tests + kill triggers can decide viability in 15-25 hours."
        ),
        schema=CONSEQUENCE_EV_SCHEMA,
        role=f"Dalio Consequence/EV — {title[:22]}",
        type_name="self",
        model=model_tier,
    )


async def run_triangulation_panel_safe(item: dict) -> dict:
    try:
        brief = json.dumps(
            {
                "idea_id": item["idea"]["id"],
                "title": item["idea"]["title"],
                "one_liner": item["idea"]["one_liner"],
                "indie_feasibility": item["idea"]["indie_feasibility"],
                "signal_ids": item["idea"]["signal_ids"],
                "active_market": item["active_market"],
                "scorecard": item["best_raw"],
                "computed_score": item["best_calc"]["score"],
                "evidence_believability_index": item["best_calc"]["evidence_believability_index"],
                "bottleneck_believability": item["best_calc"]["bottleneck_believability"],
                "band": item["best_calc"]["band"],
            },
            indent=2,
        )
        rq_res, conseq_res = await parallel(
            [run_rude_qa_court(item, brief), run_consequence_ev_analyst(item, brief)],
            lambda coro: coro,
        )
        # True independent Scorer vote comes from item["best_calc"] (Phase 3), NOT rq_res["post_calc"]!
        panel = compute_panel_decision(
            item["best_calc"],
            rq_res["verdict_out"]["verdict"],
            conseq_res["recommendation"],
        )
        ev_metrics = compute_ev_metrics(conseq_res)
        # Propagate Rude Q&A locked buyer/price/trade-offs into active_market
        adj = rq_res["verdict_out"]["adjusted_scorecard"]
        locked_market = {
            "scenario_label": f"{item['best_label']} (Post-Rude Q&A)",
            "target_buyer": adj["target_buyer"],
            "problem": adj["problem"],
            "trade_offs": adj["trade_offs"],
            "price": adj["price"],
            "pricing_strategy": adj["pricing_strategy"],
        }
        pr = {
            "item": item,
            "rude_qa": rq_res,
            "consequence_ev": conseq_res,
            "ev_metrics": ev_metrics,
            "panel": panel,
            "locked_market": locked_market,
        }
        # Incremental checkpoint for ALL Phase-4 ideas (including killed ones!)
        d = ideas_dir / item["slug"]
        d.mkdir(parents=True, exist_ok=True)
        write_problem_score_md(d / "PROBLEM-SCORE.md", item, post_rq=rq_res)
        write_rude_qa_md(d / "RUDE-QA.md", pr)
        write_decision_record_md(d / "DECISION-RECORD.md", pr)
        return {"ok": True, "data": pr}
    except Exception as exc:
        return {"ok": False, "idea": item["idea"]["title"], "error": str(exc)}


panel_wrapped = await parallel(passing_to_panel, run_triangulation_panel_safe) if passing_to_panel else []
panel_results = []
for w in panel_wrapped:
    if w["ok"]:
        panel_results.append(w["data"])
    else:
        msg = f"Phase 4 panel failed [{w['idea']}]: {w['error']}"
        log(f"WARNING: {msg}")
        worker_errors.append(msg)

survivors = []
for pr in panel_results:
    verdict = pr["rude_qa"]["verdict_out"]["verdict"]
    conseq_rec = pr["consequence_ev"]["recommendation"]
    post_score = pr["rude_qa"]["post_calc"]["score"]
    ebi = pr["rude_qa"]["post_calc"]["evidence_believability_index"]
    mn = pr["rude_qa"]["post_calc"]["bottleneck_believability"]
    pws = pr["panel"]["panel_weighted_score"]
    split = pr["panel"]["disagreement_flag"]
    title = pr["item"]["idea"]["title"]

    log(
        f"Panel [{title}]: RudeQA={verdict}, ConseqEV={conseq_rec}, "
        f"PostScore={post_score} (EBI={ebi}, Min={mn}), PanelWeighted={pws}, Split={split}"
    )

    # Strict kill gate: BAD_IDEA, Consequence KILL, Post-Score < 0.5, Eager-Id = 0, OR PanelWeighted <= 0.0
    if (
        verdict == "BAD_IDEA"
        or conseq_rec == "KILL"
        or post_score < 0.5
        or pr["rude_qa"]["post_calc"]["criteria"]["eager_identity"]["value"] == 0.0
        or pws <= 0.0
    ):
        killed_ideas.append({
            "stage": "Phase 4 — Rude Q&A + Dalio Panel",
            "item": pr["item"],
            "panel_result": pr,
            "reason": (
                f"Rude Q&A={verdict} | Consequence/EV={conseq_rec} | "
                f"Post-Score={post_score} (EBI={ebi}, Min={mn}) | PanelWeighted={pws}. "
                f"{pr['rude_qa']['verdict_out']['verdict_summary']}"
            ),
        })
    else:
        survivors.append(pr)

survivors.sort(
    key=lambda x: (
        x["panel"]["panel_weighted_score"],
        x["ev_metrics"]["expected_arr_usd"],
        x["rude_qa"]["post_calc"]["score"],
        x["rude_qa"]["post_calc"]["bottleneck_believability"],
    ),
    reverse=True,
)
top_survivors = survivors[:max_survivors_for_strategy]
log(f"Survivors: {len(survivors)} | Deep strategy & validation kit for top {len(top_survivors)}.")


# ---------------------------------------------------------------------------
# Phase 5 & 6 — Pre-Build Strategist + Validation Planner (Fault-Tolerant)
# ---------------------------------------------------------------------------

phase("5 & 6. Pre-Build Strategy & Field Validation Kits")


def write_strategy_md(target_path: Path, entry: dict) -> None:
    idea = entry["pr"]["item"]["idea"]
    lm = entry["pr"]["locked_market"]
    st = entry["strategy"]
    carol = st["provisional_carol"]
    pos = st["positioning_audit"]
    lines = [
        f"# Pre-Build Strategy Brief — {idea['title']}",
        "",
        f"> ⚠️ **PROVISIONAL — PRE-INTERVIEW.** Active Market: `{lm['scenario_label']}` · "
        f"Price: `{lm['price']}` (`{lm['pricing_strategy']}`). Validate with real humans via "
        "`asb-interview-*` before writing code.",
        "",
        "## 1. Needs Stack (Top Ends → Bottom Means)",
        "",
    ]
    for lvl in st["needs_stack"]:
        marker = " ← **YOU ARE HERE**" if lvl["role"] == "your_level" else ""
        star = "★" if lvl["role"] == "purpose" else "→"
        lines.extend([
            f"**{lvl['id']}.** {star} {lvl['level']}{marker}",
            f"- **Role:** `{lvl['role']}`",
            f"- **Occupants:** {lvl['occupants']}",
            f"- **Why your level still wins:** {lvl['why_your_level_wins']}",
            "",
        ])
    lines.extend([
        "## 2. Provisional Carol (Ideal Customer Sketch)",
        "",
        carol["portrait"],
        "",
        "### Behavioral & Circumstantial Markers",
        *[f"- {m}" for m in carol["markers"]],
        "",
        "### Qualifiers & Anti-Market Disqualifiers",
        "**Qualify toward:**",
        *[f"- {q}" for q in carol["qualifiers"]],
        "",
        "**Disqualify away (Anti-Market):**",
        *[f"- {d}" for d in carol["disqualifiers_anti_market"]],
        "",
        "### Provisional Keystones",
        *[f"- {k}" for k in carol["keystones"]],
        "",
        "### Provisional Deal-Breakers",
        *[f"- {d}" for d in carol["deal_breakers"]],
        "",
        "### Inciting Events",
        *[
            f"- **{e['id']} ({e['status']}):** {e['moment']}\n"
            f"  - *Source / Validation:* {e['source_or_validation']}\n"
            f"  - *Findability & Search Phrases:* {e['findability_and_search_phrases']}"
            for e in carol["inciting_events"]
        ],
        "",
        "## 3. Positioning Stress-Test",
        f"- **Buyer's Scoreboard Currency:** {pos['buyer_scoreboard_currency']}",
        f"- **Declared Pricing Strategy:** `{pos['pricing_strategy']}`",
        "",
        "### Candidate Positioning Statements",
        *[
            f"- **{p['id']} [{p['role']}]:** {p['statement']}\n"
            f"  - *Opposite Test:* {p['opposite_test_check']}"
            for p in pos["statements"]
        ],
        "",
        "### Facts to Verify Before Publishing",
        *([f"- {f}" for f in pos["facts_to_verify"]] or ["- None flagged."]),
        "",
    ])
    target_path.write_text("\n".join(lines), encoding="utf-8")


def write_validation_kit_md(target_path: Path, entry: dict, synth_audit: dict = None) -> None:
    idea = entry["pr"]["item"]["idea"]
    lm = entry["pr"]["locked_market"]
    cev = entry["pr"]["consequence_ev"]
    vk = entry["validation_kit"]
    lines = [
        f"# Pre-Build Customer Validation Kit — {idea['title']}",
        "",
        f"> ⚠️ **STOP BEFORE BUILDING.** Active Market: `{lm['scenario_label']}` · Locked Price: `{lm['price']}`.  \n"
        "> These goals, hypothesis templates, and draft questions are starting material. Run "
        "`asb-interview-hypotheses` so every bet is yours before interviewing 10–15 real humans.",
        "",
        f"> **Pre-Committed Kill Trigger (Dalio EV Gate):** {cev['pre_committed_kill_trigger']}",
        "",
        "## 1. Draft Goal Questions (G-numbers)",
        *[f"- **{g['id']}.** {g['question']} *({g['decision_informed']})*" for g in vk["goals"]],
        "",
        "## 2. Unowned Hypothesis Templates (H-numbers — Revise via `asb-interview-hypotheses`)",
        *[
            f"- **{h['id']}.** {h['claim']} `{', '.join(h['goal_ids'])}`\n"
            f"  - *What changes Monday if false:* {h['what_changes_if_false']}"
            for h in vk["hypothesis_templates"]
        ],
        "",
        "## 3. Draft Open-Ended Interview Questions (Q-numbers — Polite-Stranger Tested)",
        *[
            f"- **{q['id']}.** \"{q['question']}\" `{', '.join(q['hypothesis_ids'])}`\n"
            + (f"  - *Follow-ups:* {' · '.join(q['follow_ups'])}\n" if q["follow_ups"] else "")
            + f"  - *Polite-stranger check:* {q['polite_stranger_check']}"
            for q in vk["interview_questions"]
        ],
        "",
        "### Standing Probes",
        '- "Can you walk me through the last specific time that happened?"',
        '- "Tell me more about that."',
        '- "Have you ever spent money trying to fix this? How much? Did it work?"',
        "- Silence (wait 5 seconds — people fill it with the truth).",
        "",
        "## 4. Where to Find Carol (Verified Recruitment Channels)",
        *[f"- **{r['channel']}** ({r['url']}): {r['how_to_approach']}" for r in vk["recruitment_channels"]],
        "",
    ]
    if synth_audit:
        lines.extend([
            "## 5. Post-Synthetic-Pre-Test Script Audit & Red Flags (`SYNTHETIC-PRE-TEST · Cap 0.35`)",
            "*(Apply these rewrites BEFORE calling real humans! See `SYNTHETIC-INTERVIEW-REPORT.md`.)*",
            "",
            "### Question Rewrites Flagged by 4-Persona Dry Run (`[AUDITED-REWRITE]`)",
            *[
                f"- **[AUDITED-REWRITE] {r['question_ref']}** (*{r['flaw_detected']}*): \"{r['improved_question']}\""
                for r in synth_audit.get("question_script_rewrites", [])
            ],
            "",
            "### Synthetic Red Flags to Probe Hard in Real Interviews",
            *([f"- **✗ SYNTHETIC-RED-FLAG:** {x}" for x in synth_audit.get("synthetic_red_flags", [])] or ["- None."]),
            "",
        ])
    target_path.write_text("\n".join(lines), encoding="utf-8")


async def build_strategy_and_validation_safe(pr: dict) -> dict:
    try:
        idea = pr["item"]["idea"]
        title = idea["title"]
        rq = pr["rude_qa"]
        cev = pr["consequence_ev"]
        low_bel_criteria = [
            f"{CRITERION_LABELS[k]} (believability={v['believability']}, value={v['value']})"
            for k, v in rq["post_calc"]["criteria"].items()
            if v["believability"] <= 0.4
        ]
        context_blob = json.dumps(
            {
                "idea_id": idea["id"],
                "title": title,
                "one_liner": idea["one_liner"],
                "locked_market": pr["locked_market"],
                "verdict": rq["verdict_out"]["verdict"],
                "verdict_summary": rq["verdict_out"]["verdict_summary"],
                "real_decisions_locked": rq["verdict_out"]["real_decisions_locked"],
                "threats_clarified": rq["verdict_out"]["threats_clarified"],
                "open_questions_for_field": rq["verdict_out"]["open_questions_for_field"],
                "post_score": rq["post_calc"]["score"],
                "evidence_believability_index": rq["post_calc"]["evidence_believability_index"],
                "bottleneck_believability": rq["post_calc"]["bottleneck_believability"],
                "low_believability_criteria": low_bel_criteria,
                "panel": pr["panel"],
                "consequence_ev": cev,
                "ev_metrics": pr["ev_metrics"],
            },
            indent=2,
        )

        strategist_task = agent(
            prompt=(
                f"{NO_BUILD_BANNER}\n\n"
                "You are the ASB Pre-Build Strategist (`asb-needs-stack`, `asb-carol-*`, `asb-positioning`).\n"
                "Build a crisp pre-launch strategy brief anchored strictly to `locked_market` (NOT stale "
                "Scenario A assumptions!):\n\n"
                f"{context_blob}\n\n"
                "RULES:\n"
                "1. Needs Stack (`N1..`): Customer's words, true means-to-an-end links, named real occupants.\n"
                "2. Provisional Carol: Strictly behavioral/attitudinal markers passing Marketing/Sales/Product bar "
                "(NO demographic laziness, NO averaged segments). Inciting events tagged 'OBSERVED-PUBLIC' "
                "(real URL only) or 'HYPOTHESIZED', with search phrases & findability.\n"
                "3. Positioning Audit: Value-first in buyer's scoreboard currency, aligned with `locked_market` "
                "pricing strategy, Opposite-Test passing, ZERO clichés/generics (no seamless, robust, scalable, "
                "easy, solution, innovative, world-class, game-changing), and [VERIFY: ...] for every unproven claim."
            ),
            schema=STRATEGY_SCHEMA,
            role=f"Pre-Build Strategist — {title[:22]}",
            type_name="self",
            model=model_tier,
        )

        planner_task = agent(
            prompt=(
                f"{NO_BUILD_BANNER}\n\n"
                "You are the ASB + Dalio Validation Planner (`asb-interview-goals`, `asb-interview-hypotheses`, "
                "`asb-interview-questions`). Prepare a human-run customer discovery kit BEFORE writing code.\n\n"
                f"{context_blob}\n\n"
                "RULES:\n"
                "1. Goals (G1..G7): Directly target `low_believability_criteria`, any Specialist Panel "
                "disagreement, `pre_committed_kill_trigger`, and Rude Q&A open questions. NEVER 'Would you buy X?'.\n"
                "2. Hypothesis Templates (H1..H12): Falsifiable with concrete numbers/thresholds mapped to [G#], "
                "stating what changes Monday if false (emitted as UNOWNED TEMPLATES).\n"
                "3. Interview Questions (Q1..Q10): Open-ended, non-leading, SINGLE-ANSWER, polite-stranger tested "
                "questions asking about past/current life, with optional follow-ups.\n"
                "4. Recruitment Channels: Use `search_web` to find 4-6 REAL, VERIFIED communities/URLs where "
                "Carol hangs out to recruit 10-15 real interviewees."
            ),
            schema=VALIDATION_KIT_SCHEMA,
            role=f"Validation Planner — {title[:22]}",
            type_name="self",
            model=model_tier,
        )

        strat, vkit = await parallel([strategist_task, planner_task], lambda t: t)
        entry = {"pr": pr, "strategy": strat, "validation_kit": vkit}
        d = ideas_dir / pr["item"]["slug"]
        d.mkdir(parents=True, exist_ok=True)
        write_strategy_md(d / "STRATEGY-BRIEF.md", entry)
        write_validation_kit_md(d / "VALIDATION-KIT.md", entry)
        return {"ok": True, "data": entry}
    except Exception as exc:
        return {"ok": False, "idea": pr["item"]["idea"]["title"], "error": str(exc)}


enriched_wrapped = await parallel(top_survivors, build_strategy_and_validation_safe) if top_survivors else []
enriched_survivors = []
for w in enriched_wrapped:
    if w["ok"]:
        enriched_survivors.append(w["data"])
    else:
        msg = f"Phase 5/6 failed [{w['idea']}]: {w['error']}"
        log(f"WARNING: {msg}")
        worker_errors.append(msg)


# ---------------------------------------------------------------------------
# Phase 6B — Grounded 4-Persona Blind Synthetic Pre-Test (5 Single-Q Turns)
# ---------------------------------------------------------------------------

synthetic_by_slug = {}
if enriched_survivors and synthetic_interview_top_n > 0:
    phase("6B. Grounded 4-Persona Blind Synthetic Pre-Test (Cap 0.35)")
    synth_targets = enriched_survivors[:synthetic_interview_top_n]

    async def run_synthetic_pretest_safe(entry: dict) -> dict:
        idea = entry["pr"]["item"]["idea"]
        lm = entry["pr"]["locked_market"]
        slug = entry["pr"]["item"]["slug"]
        title = idea["title"]
        try:
            d = ideas_dir / slug
            synth_dir = d / "synthetic-interviews"
            synth_dir.mkdir(parents=True, exist_ok=True)

            dossier_bundle = json.dumps({
                "locked_market": lm,
                "provisional_carol": entry["strategy"]["provisional_carol"],
                "validation_kit": entry["validation_kit"],
                "kill_trigger": entry["pr"]["consequence_ev"]["pre_committed_kill_trigger"],
            }, indent=2)

            persona_pack = await agent(
                prompt=(
                    f"{NO_BUILD_BANNER}\n\n"
                    "You are the Persona Architect. Use `search_web` to ground EXACTLY 4 distinct, realistic "
                    "buyer personas in real job routines, current tool stacks, and real budgets:\n"
                    "- `bullseye_carol`: exact target fit, busy & pragmatic\n"
                    "- `status_quo_defender`: has problem on paper, priority #6, prefers Excel/incumbent\n"
                    "- `skeptical_approver`: controls budget, worries about solo-founder risk & migration\n"
                    "- `anti_market_probe`: lookalike disqualifier carrying a deal-breaker\n\n"
                    "CRITICAL BLINDNESS BARRIER: NEVER mention the startup idea title, proposed product, "
                    "locked target price, hypotheses, or archetype names inside `system_prompt`.\n"
                    "Include all 7 sections inside each `system_prompt`: (1) Identity & Daily Reality, "
                    "(2) Current Stack & Real Spend, (3) Top-3 Competing Priorities, (4) Past Vendor Scars, "
                    "(5) Budget & Buying Mechanics, (6) Voice & Bluntness, (7) Status-Quo Realism.\n\n"
                    f"Dossier (FOR YOUR EYES ONLY):\n{dossier_bundle[:12000]}"
                ),
                schema=SYNTH_PERSONAS_SCHEMA,
                role=f"Persona Architect — {title[:22]}",
                type_name="self",
                model=model_tier,
            )

            personas = persona_pack["personas"]
            leak_warnings = []
            for p in personas:
                leaks = check_persona_leakage(p["system_prompt"], title, lm["price"])
                if leaks:
                    leak_warnings.append(f"{p['archetype']}: {', '.join(leaks)}")

            vkit_json = json.dumps(entry["validation_kit"], indent=2)

            async def _blind_iv_safe(p: dict) -> dict:
                try:
                    # Neutral role name — never leak archetype into persona card title!
                    p_agent = agent(
                        prompt=f"{p['system_prompt'].strip()}\n\n{ANTI_SYCOPHANCY_KERNEL}",
                        role=f"Prospect Interviewee — {p['name']}",
                        type_name="self",
                        model=persona_model,
                    )
                    iv_agent = agent(
                        prompt=(
                            f"{NO_BUILD_BANNER}\n\n"
                            "You are an ASB Customer Interviewer (`asb-interview-questions`).\n"
                            "RULES: Ask ONE single-answer, open-ended, non-leading question per turn "
                            "(never stack 2-3 unrelated asks). Never pitch. Probe past behavior, real "
                            "workarounds, and real past spend. Do NOT call tools — output via finish.\n\n"
                            f"Active Price Anchor (for Turn 5 category spend check ONLY): {lm['price']}\n\n"
                            f"Validation Kit:\n{vkit_json[:8000]}"
                        ),
                        role=f"ASB Interviewer — {p['name']}",
                        type_name="self",
                        model=model_tier,
                    )
                    turns = [
                        "TURN 1 (Single Qualifier Question): Ask ONE natural question to sort their role, operation scale, and current tool stack. No pain label or price.",
                        "TURN 2 (Single Priorities Question): React briefly to Turn 1, then ask ONE open question about their top 2-3 headaches or priorities this quarter.",
                        "TURN 3 (Single Episode & Coping Question): Based on what they said, ask ONE question about the last specific time the relevant friction happened and how they coped.",
                        "TURN 4 (Single Past-Spend & Trust Question): Ask ONE question about what they have actually paid to deal with this (or why they haven't) and what makes them wary of switching vendors.",
                        f"TURN 5 (ASB Price Exception — Category-Anchored): Without pitching a product name, ask ONE blunt reaction question anchored around their own stated headache: e.g., whether spending roughly {lm['price']} on a dedicated tool for that specific workflow sounds reasonable, absurd, or irrelevant compared to their current spend/triggers.",
                    ]
                    transcript = []
                    last = None
                    for idx, t_instr in enumerate(turns, 1):
                        iv_p = t_instr if last is None else f"Prospect replied:\n\"{last['spoken_response']}\"\n\n{t_instr}"
                        iv_q = await iv_agent(prompt=iv_p, schema=SYNTH_IV_TURN_SCHEMA)
                        p_r = await p_agent(
                            prompt=f"Interviewer asks (Turn {idx}/5):\n\"{iv_q['spoken_question']}\"\n\nReply strictly in-character plus unspoken internal_monologue.",
                            schema=SYNTH_PERSONA_REPLY_SCHEMA,
                        )
                        transcript.append({"turn": idx, "interviewer": iv_q, "persona": p_r})
                        last = p_r
                    del p_agent
                    del iv_agent
                    return {"ok": True, "persona": p, "transcript": transcript}
                except Exception as exc:
                    return {"ok": False, "persona": p, "error": str(exc)}

            iv_wrapped = await parallel(personas, _blind_iv_safe)
            synth_interviews = [w for w in iv_wrapped if w["ok"]]
            for w in iv_wrapped:
                if not w["ok"]:
                    worker_errors.append(f"Phase 6B interview failed [{slug}/{w['persona']['archetype']}]: {w['error']}")

            # STRIP system_prompt before passing to Auditor so Personas #3 and #4 are NEVER truncated!
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
                    f"{NO_BUILD_BANNER}\n\n"
                    "Audit ALL 4 blind synthetic interviews (Believability Cap 0.35 — NEVER mark anything "
                    "VALIDATED). Map per_persona_debriefs for every archetype, detect leading interviewer "
                    "leaks & market-guru slips, surface red flags, directional signals, watch items, "
                    "broken-question rewrites, and top cruxes for real humans.\n\n"
                    f"Validation Kit:\n{vkit_json[:5500]}\n\n"
                    f"All 4 Blind Transcripts (system_prompts stripped — complete transcripts):\n"
                    f"{json.dumps(auditor_payload, indent=2)}"
                ),
                schema=SYNTH_AUDIT_SCHEMA,
                role=f"Synthetic Auditor — {title[:22]}",
                type_name="self",
                model=model_tier,
            )

            # Write quarantined synthetic-interviews/ artifacts
            p_md = [
                f"# Synthetic Persona Panel — {title}",
                "",
                f"> ⚠️ **SYNTHETIC-PRE-TEST · Dalio Believability Cap: `{SYNTHETIC_BELIEVABILITY_CAP}`**  \n"
                f"> Persona model tier: `{persona_model}` · Interviewer/Auditor tier: `{model_tier or 'inherit'}` · "
                f"Leakage check warnings: `{len(leak_warnings)}`",
                "",
                "## Web Grounding Sources",
                *([f"- {u}" for u in persona_pack["grounding_urls"]] or ["- None recorded."]),
                "",
            ]
            if leak_warnings:
                p_md.extend(["## Leakage Check Warnings", *[f"- {lw}" for lw in leak_warnings], ""])
            for i, p in enumerate(personas, 1):
                p_md.extend([f"## Persona {i}: {p['name']} (`{p['archetype']}`)", p["role_and_context"], "", "```text", p["system_prompt"].strip(), "```", ""])
            (synth_dir / "PERSONAS.md").write_text("\n".join(p_md), encoding="utf-8")

            debrief_by_arch = {db["archetype"]: db for db in synth_audit["per_persona_debriefs"]}
            for i, iv in enumerate(synth_interviews, 1):
                p = iv["persona"]
                arch = p["archetype"]
                db = debrief_by_arch.get(arch, {})
                t_lines = [
                    f"# SYNTHETIC-PRE-TEST Debrief — {p['name']} (`{arch}`)",
                    "",
                    f"> ⚠️ **SYNTHETIC SIMULATION — NOT A REAL HUMAN INTERVIEW · Believability Cap `{SYNTHETIC_BELIEVABILITY_CAP}`**",
                    "",
                    f"**Role:** {p['role_and_context']}",
                    "",
                    "## Mapped Answers",
                    *([f"- {a}" for a in db.get("mapped_answers", [])] or ["- None mapped."]),
                    "",
                    "## Verbatim Vocabulary",
                    *([f"- \"{v}\"" for v in db.get("verbatim_vocabulary", [])] or ["- None noted."]),
                    "",
                    "## Script & Bias Diagnostics",
                    f"- **Key Surprise / Objection:** {db.get('key_surprise_or_objection', 'None')}",
                    f"- **Leading-Question Leaks:** {'; '.join(db.get('leading_leaks_detected', [])) or 'None detected'}",
                    f"- **Market-Guru Flags:** {'; '.join(db.get('market_guru_flags', [])) or 'None detected'}",
                    "",
                    "## Full 5-Turn Blind Transcript",
                    "",
                ]
                for t in iv["transcript"]:
                    t_lines.extend([
                        f"### Turn {t['turn']} ({', '.join(t['interviewer']['targeted_q_and_h_ids'])})",
                        f"**Interviewer:** {t['interviewer']['spoken_question']}",
                        "",
                        f"**{p['name']}:** {t['persona']['spoken_response']}",
                        "",
                        f"> *Internal monologue:* {t['persona']['internal_monologue']}",
                        "",
                    ])
                (synth_dir / f"SYNTH-0{i}-{arch}.md").write_text("\n".join(t_lines), encoding="utf-8")

            rep_lines = [
                f"# Synthetic Interview Pre-Test Report — {title}",
                "",
                f"> ⚠️ **SYNTHETIC-PRE-TEST · Dalio Believability Cap: `{SYNTHETIC_BELIEVABILITY_CAP}`** (Quarantined from real human `interviews/`)",
                "",
                "## Executive Summary",
                synth_audit["executive_summary"],
                "",
                "## ✗ Synthetic Red Flags",
                *([f"- **✗ SYNTHETIC-RED-FLAG:** {x}" for x in synth_audit["synthetic_red_flags"]] or ["- None."]),
                "",
                "## ~ Synthetic Directional Signals (Verify With Real Humans)",
                *([f"- **~ SYNTHETIC-SIGNAL:** {x}" for x in synth_audit["synthetic_directional_signals"]] or ["- None."]),
                "",
                "## 👀 Watch Items",
                *([f"- **👀 WATCH:** {x}" for x in synth_audit["watch_items"]] or ["- None."]),
                "",
                "## Question Script Rewrites (Also Appended to `VALIDATION-KIT.md`)",
                *[f"- **{r['question_ref']}** (*{r['flaw_detected']}*): \"{r['improved_question']}\"" for r in synth_audit["question_script_rewrites"]],
                "",
                "## Top Cruxes for Real Human Interviews",
                *[f"- {c}" for c in synth_audit["priority_cruxes_for_real_humans"]],
                "",
            ]
            (d / "SYNTHETIC-INTERVIEW-REPORT.md").write_text("\n".join(rep_lines), encoding="utf-8")

            # Patch VALIDATION-KIT.md directly with audited rewrites & red flags!
            write_validation_kit_md(d / "VALIDATION-KIT.md", entry, synth_audit=synth_audit)

            meta = {
                "idea_title": title,
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
            (synth_dir / "synthetic_meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
            log(f"Synthetic pre-test [{title}]: {meta['red_flags_count']} red flags, {meta['script_rewrites_count']} script rewrites.")
            return {"ok": True, "slug": slug, "meta": meta, "red_flags": synth_audit["synthetic_red_flags"]}
        except Exception as exc:
            return {"ok": False, "slug": slug, "idea": title, "error": str(exc)}

    synth_wrapped = await parallel(synth_targets, run_synthetic_pretest_safe)
    for sw in synth_wrapped:
        if sw["ok"]:
            synthetic_by_slug[sw["slug"]] = sw
        else:
            msg = f"Phase 6B synthetic pre-test failed [{sw['idea']}]: {sw['error']}"
            log(f"WARNING: {msg}")
            worker_errors.append(msg)


# ---------------------------------------------------------------------------
# Phase 7 — Dalio Post-Run Reflection (Includes Synthetic Red Flags & Full Kill Details)
# ---------------------------------------------------------------------------

phase("7. Dalio Reflection & Root-Cause Principles")

reflection_input = {
    "lenses": lenses,
    "survivors": [
        {
            "title": s["item"]["idea"]["title"],
            "locked_market": s["locked_market"],
            "post_score": s["rude_qa"]["post_calc"]["score"],
            "ebi": s["rude_qa"]["post_calc"]["evidence_believability_index"],
            "bottleneck_believability": s["rude_qa"]["post_calc"]["bottleneck_believability"],
            "ev_metrics": s["ev_metrics"],
            "panel": s["panel"],
            "rude_qa_verdict": s["rude_qa"]["verdict_out"]["verdict"],
            "consequence_rec": s["consequence_ev"]["recommendation"],
            "kill_trigger": s["consequence_ev"]["pre_committed_kill_trigger"],
            "synthetic_red_flags": (
                synthetic_by_slug[s["item"]["slug"]]["red_flags"]
                if s["item"]["slug"] in synthetic_by_slug
                else []
            ),
        }
        for s in survivors
    ],
    "killed": [
        {
            "title": k["item"]["idea"]["title"],
            "stage": k["stage"],
            "signal_ids": k["item"]["idea"]["signal_ids"],
            "active_market": k["item"]["active_market"],
            "reason": k["reason"],
            "rude_qa_threats": (
                k["panel_result"]["rude_qa"]["verdict_out"]["threats_clarified"]
                if "panel_result" in k
                else []
            ),
            "consequence_reasoning": (
                k["panel_result"]["consequence_ev"]["recommendation_reasoning"]
                if "panel_result" in k
                else ""
            ),
        }
        for k in killed_ideas
    ],
}

reflection = await agent(
    prompt=(
        f"{NO_BUILD_BANNER}\n\n"
        "You are the Dalio Reflection Analyst applying 'Pain + Reflection = Progress' and the "
        "5-Step Process.\n\n"
        f"Existing standing principles (ALL — do not duplicate these):\n{learned_principles}\n\n"
        f"This run's outcomes (including killed Rude Q&A threats and synthetic red flags):\n"
        f"{json.dumps(reflection_input, indent=2)}\n\n"
        "Deliver:\n"
        "1. For EVERY killed idea, separate PROXIMATE CAUSE (symptom) from ROOT CAUSE (scouting, "
        "targeting, or market-structure error) and name the concrete `machine_fix`.\n"
        "2. Propose 2-4 crisp, non-generic Candidate Learned Principles distinct from existing DP# rules.\n"
        "3. A blunt 1-paragraph `portfolio_synthesis` weighing Panel Score, Expected ARR, Bottleneck "
        "Believability, panel disagreements, and synthetic red flags."
    ),
    schema=REFLECTION_SCHEMA,
    role="Dalio Reflection Analyst",
    type_name="self",
    model=model_tier,
)


# ---------------------------------------------------------------------------
# Phase 8 — Write Run-Level Shortlist, Decision Memo, Graveyard & run_data.json
# ---------------------------------------------------------------------------

phase("8. Writing Shortlist, Decision Memo & Run Data")

enriched_by_slug = {e["pr"]["item"]["slug"]: e for e in enriched_survivors}

# KILLED-IDEAS.md
killed_lines = [
    f"# Killed Ideas Graveyard — {run_slug}",
    "",
    f"Run: `{run_dir.name}` · Killed: {len(killed_ideas)} of {len(candidates)} candidates",
    "",
    "> Pain + Reflection = Progress. Per-idea scorecards & Rude Q&A dossiers for killed ideas "
    "are preserved under `ideas/<id>-<slug>/`.",
    "",
]
if not killed_ideas:
    killed_lines.append("*(No candidates were killed in this run — double-check for optimism bias!)*")
else:
    for k in killed_ideas:
        idea = k["item"]["idea"]
        am = k["item"]["active_market"]
        slug = k["item"]["slug"]
        killed_lines.extend([
            f"## {idea['id']} — {idea['title']} *(Killed at: {k['stage']})*",
            f"- **Active Buyer:** {am['target_buyer']}",
            f"- **Price:** {am['price']} ({am['pricing_strategy']})",
            f"- **Phase 3 Score:** `{k['item']['best_calc']['score']}` "
            f"(EBI `{k['item']['best_calc']['evidence_believability_index']}`, Min `{k['item']['best_calc']['bottleneck_believability']}`)",
            f"- **Why It Died:** {k['reason']}",
            f"- **Preserved Files:** `ideas/{slug}/PROBLEM-SCORE.md`"
            + (f", `ideas/{slug}/RUDE-QA.md`, `ideas/{slug}/DECISION-RECORD.md`" if "panel_result" in k else ""),
            "",
        ])
(run_dir / "KILLED-IDEAS.md").write_text("\n".join(killed_lines), encoding="utf-8")

# DECISION-MEMO.md
splits = [pr for pr in panel_results if pr["panel"]["disagreement_flag"]]
memo_lines = [
    f"# Dalio Decision Memo & Post-Run Reflection — {run_slug}",
    "",
    f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')} · Survivors: {len(survivors)} · "
    f"Killed: {len(killed_ideas)} · Worker Warnings: {len(worker_errors)}",
    "",
    "## 1. Portfolio Synthesis",
    reflection["portfolio_synthesis"],
    "",
    "## 2. Specialist Disagreement Log (Radical Transparency)",
    "",
]
if not splits:
    memo_lines.append("*(No specialist panel splits >= 1.0 occurred in Phase 4.)*")
else:
    for pr in splits:
        idea = pr["item"]["idea"]
        v = pr["panel"]["votes"]
        memo_lines.extend([
            f"### SPLIT: {idea['title']} (Panel Weighted: `{pr['panel']['panel_weighted_score']}`)",
            f"- **Votes:** Phase 3 Scorer=`{v['scorer']}` (0.30) · Rude Q&A Attacker=`{v['attacker']}` (0.40) · "
            f"Consequence/EV=`{v['consequence_ev']}` (0.30)",
            f"- **Rude Q&A Read:** `{pr['rude_qa']['verdict_out']['verdict']}` — {pr['rude_qa']['verdict_out']['verdict_summary']}",
            f"- **Consequence/EV Read:** `{pr['consequence_ev']['recommendation']}` — {pr['consequence_ev']['recommendation_reasoning']}",
            f"- **Crux to Test in Real Interviews:** {pr['consequence_ev']['highest_ev_falsification_test']}",
            "",
        ])

memo_lines.extend(["## 3. Root-Cause Diagnosis of Killed Ideas", ""])
if not reflection["killed_root_causes"]:
    memo_lines.append("*(No killed ideas to diagnose.)*")
else:
    for rc in reflection["killed_root_causes"]:
        memo_lines.extend([
            f"### {rc['idea_title']}",
            f"- **Proximate Cause (Symptom):** {rc['proximate_cause']}",
            f"- **Root Cause:** {rc['root_cause']}",
            f"- **Machine Fix for Future Runs:** {rc['machine_fix']}",
            "",
        ])

memo_lines.extend([
    "## 4. Candidate Learned Principles (Promote to `principles/LEARNED-PRINCIPLES.md`)",
    "",
    *[
        f"- **{cp['title']}:** {cp['rule']} *(Evidence: {cp['trigger_evidence']})*"
        for cp in reflection["candidate_principles"]
    ],
    "",
])
if worker_errors:
    memo_lines.extend(["## 5. Non-Fatal Worker Warnings", *[f"- {e}" for e in worker_errors], ""])
(run_dir / "DECISION-MEMO.md").write_text("\n".join(memo_lines), encoding="utf-8")

# SHORTLIST.md
shortlist_lines = [
    f"# Indie Startup Shortlist (ASB + Dalio) — {run_slug}",
    "",
    f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M')} · Ambition: `{ambition}` · "
    f"Signals: {len(all_signals)} · Candidates: {len(candidates)} · "
    f"Survivors: {len(survivors)} · Killed: {len(killed_ideas)}",
    "",
    "> **Status: PRE-BUILD ONLY.** Ranked by Independent Panel Score, Deterministic Expected ARR, "
    "ASB Post-Attack Score, and Bottleneck Believability. Every survivor carries a pre-committed Kill Trigger.",
    "",
    "## Ranked Survivors",
    "",
]
if not survivors:
    shortlist_lines.extend([
        "**Zero candidates survived the ASB + Dalio gauntlet in this run.**",
        "",
        "See `KILLED-IDEAS.md` and `DECISION-MEMO.md` for root-cause diagnosis and Candidate Principles.",
        "",
    ])
else:
    shortlist_lines.extend([
        "| Rank | Idea | Panel | Split? | ASB | EBI (Min) | Exp. ARR | Synth Flags | Dossier |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ])
    for idx, pr in enumerate(survivors, 1):
        idea = pr["item"]["idea"]
        slug = pr["item"]["slug"]
        has_full = slug in enriched_by_slug
        s_info = synthetic_by_slug.get(slug)
        synth_cell = f"`{s_info['meta']['red_flags_count']} flags`" if s_info else "—"
        links = (
            f"[Score](ideas/{slug}/PROBLEM-SCORE.md) · "
            f"[Rude Q&A](ideas/{slug}/RUDE-QA.md) · "
            f"[Decision](ideas/{slug}/DECISION-RECORD.md)"
            + (
                f" · [Strategy](ideas/{slug}/STRATEGY-BRIEF.md) · "
                f"[Validation Kit](ideas/{slug}/VALIDATION-KIT.md)"
                if has_full
                else ""
            )
            + (f" · [Synth Pre-Test](ideas/{slug}/SYNTHETIC-INTERVIEW-REPORT.md)" if s_info else "")
        )
        shortlist_lines.append(
            f"| {idx} | **{idea['title']}** | `{pr['panel']['panel_weighted_score']}` | "
            f"`{'SPLIT' if pr['panel']['disagreement_flag'] else 'Aligned'}` | "
            f"`{pr['rude_qa']['post_calc']['score']}` | "
            f"`{pr['rude_qa']['post_calc']['evidence_believability_index']}` "
            f"(`{pr['rude_qa']['post_calc']['bottleneck_believability']}`) | "
            f"`${pr['ev_metrics']['expected_arr_usd']:,.0f}` | "
            f"{synth_cell} | {links} |"
        )
    shortlist_lines.append("")
    for idx, pr in enumerate(survivors, 1):
        idea = pr["item"]["idea"]
        lm = pr["locked_market"]
        shortlist_lines.extend([
            f"### {idx}. {idea['title']} (Panel `{pr['panel']['panel_weighted_score']}` · "
            f"ASB `{pr['rude_qa']['post_calc']['score']}` · Expected ARR `${pr['ev_metrics']['expected_arr_usd']:,.0f}`)",
            f"- **One-liner:** {idea['one_liner']}",
            f"- **Locked Target Buyer (`{lm['scenario_label']}`):** {lm['target_buyer']}",
            f"- **Locked Price & Strategy:** {lm['price']} ({lm['pricing_strategy']})",
            f"- **Pre-Committed Kill Trigger:** {pr['consequence_ev']['pre_committed_kill_trigger']}",
            f"- **Highest-EV Falsification Test:** {pr['consequence_ev']['highest_ev_falsification_test']}",
            "",
        ])

shortlist_lines.extend([
    "## Artifacts in This Run",
    "- [DECISION-MEMO.md](DECISION-MEMO.md) — Specialist Disagreement Log, Root-Cause Diagnosis & Candidate Principles",
    "- [PAIN-SIGNALS.md](PAIN-SIGNALS.md) — Cited public complaints, workarounds & pricing",
    "- [KILLED-IDEAS.md](KILLED-IDEAS.md) — Graveyard of rejected ideas & preserved dossiers",
    "- [run_data.json](run_data.json) — Machine-readable data for `scripts/validate_scorecard.py`",
    "",
])
(run_dir / "SHORTLIST.md").write_text("\n".join(shortlist_lines), encoding="utf-8")

# run_data.json
run_data = {
    "run_id": run_dir.name,
    "run_type": "discovery",
    "ambition": ambition,
    "lenses": lenses,
    "signals_count": len(all_signals),
    "candidates_count": len(candidates),
    "worker_errors": worker_errors,
    "survivors": [
        {
            "id": pr["item"]["idea"]["id"],
            "title": pr["item"]["idea"]["title"],
            "slug": pr["item"]["slug"],
            "verdict": pr["rude_qa"]["verdict_out"]["verdict"],
            "consequence_recommendation": pr["consequence_ev"]["recommendation"],
            "ev_metrics": pr["ev_metrics"],
            "panel": pr["panel"],
            "best_scenario_label": pr["item"]["best_label"],
            "scenario_a": pr["item"]["scenario_a_calc"],
            "scenario_b": pr["item"]["scenario_b_calc"],
            "post_rude_qa": pr["rude_qa"]["post_calc"],
            "has_full_dossier": pr["item"]["slug"] in enriched_by_slug,
            "synthetic_pretest": (
                synthetic_by_slug[pr["item"]["slug"]]["meta"]
                if pr["item"]["slug"] in synthetic_by_slug
                else None
            ),
        }
        for pr in survivors
    ],
    "killed": [
        {
            "id": k["item"]["idea"]["id"],
            "title": k["item"]["idea"]["title"],
            "slug": k["item"]["slug"],
            "stage": k["stage"],
            "best_scenario_label": k["item"]["best_label"],
            "scenario_a": k["item"]["scenario_a_calc"],
            "scenario_b": k["item"]["scenario_b_calc"],
            "post_rude_qa": k["panel_result"]["rude_qa"]["post_calc"] if "panel_result" in k else None,
            "panel": k["panel_result"]["panel"] if "panel_result" in k else None,
            "ev_metrics": k["panel_result"]["ev_metrics"] if "panel_result" in k else None,
            "reason": k["reason"],
        }
        for k in killed_ideas
    ],
}
(run_dir / "run_data.json").write_text(json.dumps(run_data, indent=2), encoding="utf-8")

print(json.dumps({
    "run_dir": str(run_dir),
    "shortlist": str(run_dir / "SHORTLIST.md"),
    "decision_memo": str(run_dir / "DECISION-MEMO.md"),
    "killed_log": str(run_dir / "KILLED-IDEAS.md"),
    "pain_signals": str(run_dir / "PAIN-SIGNALS.md"),
    "survivors_count": len(survivors),
    "killed_count": len(killed_ideas),
    "panel_splits_count": len(splits),
    "worker_errors_count": len(worker_errors),
    "top_survivors": [
        {
            "title": pr["item"]["idea"]["title"],
            "panel_score": pr["panel"]["panel_weighted_score"],
            "disagreement": pr["panel"]["disagreement_flag"],
            "post_score": pr["rude_qa"]["post_calc"]["score"],
            "ebi": pr["rude_qa"]["post_calc"]["evidence_believability_index"],
            "bottleneck": pr["rude_qa"]["post_calc"]["bottleneck_believability"],
            "expected_arr_usd": pr["ev_metrics"]["expected_arr_usd"],
            "verdict": pr["rude_qa"]["verdict_out"]["verdict"],
            "consequence_rec": pr["consequence_ev"]["recommendation"],
            "synth_red_flags": (
                synthetic_by_slug[pr["item"]["slug"]]["meta"]["red_flags_count"]
                if pr["item"]["slug"] in synthetic_by_slug
                else None
            ),
            "dir": str(ideas_dir / pr["item"]["slug"]),
        }
        for pr in top_survivors
    ],
}, indent=2))
