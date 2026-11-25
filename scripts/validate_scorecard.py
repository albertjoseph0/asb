#!/usr/bin/env python3
"""Deterministic ASB + Dalio Problem Score, Believability, Panel, EV & Quarantine Validator.

Usage:
    python3 scripts/validate_scorecard.py --self-test
    python3 scripts/validate_scorecard.py --calc 100000 0.5 1000 0.1 0.5 0.5 0.5
    python3 scripts/validate_scorecard.py runs/<run-id>/
    python3 scripts/validate_scorecard.py runs/<run-id>/ideas/<slug>/
    python3 scripts/validate_scorecard.py runs/          # every run; incomplete runs are listed, not failed
"""

import argparse
import ast
import json
import math
from pathlib import Path
import sys

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

LEGAL_BELIEVABILITY = [0.2, 0.35, 0.4, 0.7, 1.0]
PANEL_WEIGHTS = {"scorer": 0.30, "attacker": 0.40, "consequence_ev": 0.30}
ORDERED_KEYS = list(LEGAL_SCALES.keys())
EXPECTED_ARCHETYPES = {"bullseye_carol", "status_quo_defender", "skeptical_approver", "anti_market_probe"}

BANNED_CLICHES = [
    "the holy grail of",
    "the leading provider of",
    "designed with you in mind",
    "putting customers first",
    "proven track record",
    "the go-to choice",
    "game-changing",
    "world-class",
    "best-in-class",
    "cutting-edge",
    "revolutionary",
    "seamless",
    "frictionless",
    "fast and easy",
    "ai-powered",
]


def is_legal(criterion: str, value: float) -> bool:
    return any(abs(float(value) - allowed) < 1e-9 for allowed in LEGAL_SCALES[criterion])


def is_legal_believability(value: float) -> bool:
    return any(abs(float(value) - allowed) < 1e-9 for allowed in LEGAL_BELIEVABILITY)


def compute_score(values: dict) -> float:
    prod = 1.0
    for k in ORDERED_KEYS:
        prod *= float(values[k])
    return round(prod / DIVISOR, 4)


def compute_ebi_and_min(believabilities: list) -> tuple:
    fs = [float(b) for b in believabilities]
    return round(sum(fs) / len(fs), 3), round(min(fs), 3)


def compute_panel(scorer_vote: float, attacker_vote: float, consequence_vote: float) -> tuple:
    weighted = round(
        PANEL_WEIGHTS["scorer"] * scorer_vote
        + PANEL_WEIGHTS["attacker"] * attacker_vote
        + PANEL_WEIGHTS["consequence_ev"] * consequence_vote,
        3,
    )
    votes = [scorer_vote, attacker_vote, consequence_vote]
    return weighted, (max(votes) - min(votes)) >= 1.0


def verify_scorecard_dict(label: str, sc: dict) -> list:
    errors = []
    criteria = sc.get("criteria", {})
    vals = {}
    bels = []
    for k in ORDERED_KEYS:
        if k not in criteria:
            errors.append(f"{label}: missing criterion '{k}'")
            continue
        c = criteria[k]
        v = c["value"]
        if not is_legal(k, v):
            errors.append(f"{label}: illegal scale value for '{k}': {v}")
        vals[k] = v
        if "believability" in c:
            b = float(c["believability"])
            if not is_legal_believability(b):
                errors.append(f"{label}: illegal believability weight for '{k}': {b}")
            if c.get("evidence_class") == "[fermi]" and b > 0.4 + 1e-9:
                errors.append(f"{label}: [fermi] criterion '{k}' exceeds 0.4 believability cap ({b})")
            # Only scorecards written after this check was added carry "sources"; older runs are skipped.
            if "sources" in sc and not sc["sources"] and b >= 0.7 - 1e-9:
                errors.append(f"{label}: '{k}' has believability {b} (>= 0.7) but the scorecard cites no source URLs")
            bels.append(b)
    if len(vals) == len(ORDERED_KEYS):
        expected = compute_score(vals)
        recorded = round(float(sc["score"]), 4)
        if abs(expected - recorded) > 1e-3:
            errors.append(f"{label}: math mismatch — expected {expected}, recorded {recorded}")
    if len(bels) == len(ORDERED_KEYS):
        exp_ebi, exp_min = compute_ebi_and_min(bels)
        if "evidence_believability_index" in sc and abs(exp_ebi - round(float(sc["evidence_believability_index"]), 3)) > 1e-3:
            errors.append(f"{label}: EBI mismatch — expected {exp_ebi}, recorded {sc['evidence_believability_index']}")
        if "bottleneck_believability" in sc and abs(exp_min - round(float(sc["bottleneck_believability"]), 3)) > 1e-3:
            errors.append(f"{label}: bottleneck_believability mismatch — expected {exp_min}, recorded {sc['bottleneck_believability']}")
    return errors


def verify_panel_dict(label: str, panel: dict) -> list:
    errors = []
    votes = panel.get("votes", {})
    for k in ("scorer", "attacker", "consequence_ev"):
        if k not in votes:
            errors.append(f"{label}: missing panel vote '{k}'")
            return errors
    exp_score, exp_split = compute_panel(votes["scorer"], votes["attacker"], votes["consequence_ev"])
    if abs(exp_score - float(panel.get("panel_weighted_score", 999))) > 1e-3:
        errors.append(f"{label}: panel_weighted_score mismatch — expected {exp_score}, recorded {panel.get('panel_weighted_score')}")
    if bool(panel.get("disagreement_flag")) != exp_split:
        errors.append(f"{label}: disagreement_flag mismatch — expected {exp_split}, recorded {panel.get('disagreement_flag')}")
    return errors


def verify_ev_dict(label: str, ev: dict) -> list:
    errors = []
    if not ev:
        return errors
    p = float(ev.get("p_viable_pct", 0.0))
    arr = float(ev.get("target_arr_usd", 0.0))
    hrs = max(1.0, float(ev.get("validation_hours", 20.0)))
    exp_arr = round((p / 100.0) * arr, 2)
    exp_hr = round(exp_arr / hrs, 2)
    if abs(exp_arr - float(ev.get("expected_arr_usd", -1))) > 0.05:
        errors.append(f"{label}: expected_arr_usd mismatch — expected {exp_arr}, recorded {ev.get('expected_arr_usd')}")
    if abs(exp_hr - float(ev.get("ev_per_validation_hour", -1))) > 0.05:
        errors.append(f"{label}: ev_per_validation_hour mismatch — expected {exp_hr}, recorded {ev.get('ev_per_validation_hour')}")
    return errors


def verify_synthetic_dir(idea_dir: Path, slug: str) -> list:
    errors = []
    synth_meta_path = idea_dir / "synthetic-interviews" / "synthetic_meta.json"
    if not synth_meta_path.exists():
        return [f"Missing synthetic quarantine metadata: {synth_meta_path}"]
    sm = json.loads(synth_meta_path.read_text(encoding="utf-8"))
    if float(sm.get("believability_cap", 999)) > SYNTHETIC_BELIEVABILITY_CAP + 1e-9:
        errors.append(f"Synthetic pre-test '{slug}' exceeds cap {SYNTHETIC_BELIEVABILITY_CAP}: {sm.get('believability_cap')}")
    if sm.get("status_tag") != "SYNTHETIC-PRE-TEST":
        errors.append(f"Synthetic pre-test '{slug}' missing SYNTHETIC-PRE-TEST tag.")
    if int(sm.get("personas_count", 0)) != 4 or set(sm.get("archetypes", [])) != EXPECTED_ARCHETYPES:
        errors.append(f"Synthetic pre-test '{slug}' must have 4 distinct archetypes, got {sm.get('archetypes')}")
    if not (idea_dir / "SYNTHETIC-INTERVIEW-REPORT.md").exists():
        errors.append(f"Missing SYNTHETIC-INTERVIEW-REPORT.md for '{slug}'")
    # Content-level quarantine scan of human interviews/ directory
    human_dir = idea_dir / "interviews"
    if human_dir.exists():
        for f in human_dir.glob("*.md"):
            txt = f.read_text(encoding="utf-8", errors="ignore")
            if f.name.startswith("SYNTH-") or "SYNTHETIC-PRE-TEST" in txt or "SYNTHETIC SIMULATION" in txt:
                errors.append(f"Quarantine breach: synthetic material inside human interviews/: {f}")
    return errors


def validate_path(target: Path) -> int:
    errors = []
    warnings = []

    # Support validating a standalone synthetic idea directory directly!
    data_path = target / "run_data.json"
    if not data_path.exists():
        synth_meta_path = target / "synthetic-interviews" / "synthetic_meta.json"
        if synth_meta_path.exists():
            errors.extend(verify_synthetic_dir(target, target.name))
            if errors:
                print("ERRORS:\n" + "\n".join(f"  - {e}" for e in errors))
                return 1
            print(f"OK: Standalone synthetic pre-test '{target.name}' verified (cap <= {SYNTHETIC_BELIEVABILITY_CAP}, 4 archetypes, quarantined).")
            return 0
        if (target / "candidates.json").exists():
            print(
                f"ERROR: {target.name} is an INCOMPLETE run — candidates.json exists but run_data.json does not, "
                "so the workflow stopped before writing its results. Re-run it, or delete the folder."
            )
        else:
            print(f"ERROR: Neither {data_path} nor {synth_meta_path} found.")
        return 1

    data = json.loads(data_path.read_text(encoding="utf-8"))
    partial = data.get("status") == "partial"
    if partial:
        warnings.append(
            "run_data.json is a mid-run checkpoint (status: partial) — the workflow stopped before Phase 8; "
            "checking the phases that finished."
        )
    if data.get("run_type") in ("discovery", "deep_dive") and not partial and not (target / "DECISION-MEMO.md").exists():
        errors.append(f"Missing required artifact: {target / 'DECISION-MEMO.md'}")

    for s in data.get("survivors", []):
        slug = s["slug"]
        if s.get("verdict") == "BAD_IDEA":
            errors.append(f"Survivor '{slug}' has verdict BAD_IDEA — must be killed.")
        if s.get("consequence_recommendation") == "KILL":
            errors.append(f"Survivor '{slug}' has consequence_recommendation KILL — must be killed.")
        if s.get("panel"):
            errors.extend(verify_panel_dict(f"survivor:{slug}:panel", s["panel"]))
            if float(s["panel"].get("panel_weighted_score", 0.0)) <= 0.0:
                errors.append(f"Survivor '{slug}' has panel_weighted_score <= 0.0 — must be killed.")
        if s.get("ev_metrics"):
            errors.extend(verify_ev_dict(f"survivor:{slug}:ev", s["ev_metrics"]))
        for phase_key in ("scenario_a", "scenario_b", "post_rude_qa"):
            if s.get(phase_key):
                errors.extend(verify_scorecard_dict(f"survivor:{slug}:{phase_key}", s[phase_key]))
        post = s.get("post_rude_qa") or {}
        if float(post.get("score", 0.0)) < 0.5:
            errors.append(f"Survivor '{slug}' post_rude_qa score < 0.5 ({post.get('score')}).")
        if float(((post.get("criteria") or {}).get("eager_identity") or {}).get("value", 0.0)) <= 0.0:
            errors.append(f"Survivor '{slug}' has eager_identity == 0.")

        idea_dir = target / "ideas" / slug
        for req in ("PROBLEM-SCORE.md", "RUDE-QA.md", "DECISION-RECORD.md"):
            if not (idea_dir / req).exists():
                errors.append(f"Missing required artifact: {idea_dir / req}")
        if s.get("has_full_dossier"):
            for req in ("STRATEGY-BRIEF.md", "VALIDATION-KIT.md"):
                p = idea_dir / req
                if not p.exists():
                    errors.append(f"Missing dossier artifact: {p}")
                elif req == "STRATEGY-BRIEF.md":
                    text_lower = p.read_text(encoding="utf-8").lower()
                    for cliche in BANNED_CLICHES:
                        if cliche in text_lower:
                            warnings.append(f"{p.name} ({slug}): contains banned ASB cliché '{cliche}'")
        if s.get("synthetic_pretest") or (idea_dir / "synthetic-interviews" / "synthetic_meta.json").exists():
            errors.extend(verify_synthetic_dir(idea_dir, slug))

    for k in data.get("killed", []):
        slug = k["slug"]
        if k.get("panel"):
            errors.extend(verify_panel_dict(f"killed:{slug}:panel", k["panel"]))
        if k.get("ev_metrics"):
            errors.extend(verify_ev_dict(f"killed:{slug}:ev", k["ev_metrics"]))
        for phase_key in ("scenario_a", "scenario_b", "post_rude_qa"):
            if k.get(phase_key):
                errors.extend(verify_scorecard_dict(f"killed:{slug}:{phase_key}", k[phase_key]))

    if warnings:
        print("WARNINGS:")
        for w in warnings:
            print(f"  - {w}")
    if errors:
        print("ERRORS:")
        for e in errors:
            print(f"  - {e}")
        return 1

    print(
        f"OK{' (PARTIAL)' if partial else ''}: {target.name} verified — "
        f"{len(data.get('survivors', []))} survivors, {len(data.get('killed', []))} killed, "
        f"all ASB Fermi math, Dalio believability/bottleneck, panel weighting, EV & synthetic quarantine valid."
    )
    return 0


def validate_runs_dir(runs_dir: Path) -> int:
    """Validate every run folder under runs/. Incomplete runs (no run_data.json) are listed but do not fail."""
    run_dirs = sorted(d for d in runs_dir.iterdir() if d.is_dir())
    failed, incomplete, ok = [], [], 0
    for d in run_dirs:
        if not (d / "run_data.json").exists() and (d / "candidates.json").exists():
            incomplete.append(d.name)
            continue
        print(f"== {d.name}")
        if validate_path(d) == 0:
            ok += 1
        else:
            failed.append(d.name)
    print("")
    print(f"SUMMARY: {ok} valid, {len(failed)} failed, {len(incomplete)} incomplete (stopped before run_data.json).")
    for name in incomplete:
        print(f"  - INCOMPLETE: {name}")
    for name in failed:
        print(f"  - FAILED: {name}")
    return 1 if failed else 0


def load_workflow_math(wf_path: Path) -> dict:
    """Load a workflow's constants and plain (non-async) helper functions without running it.

    Workflows use top-level `await` and runtime globals (agent, parallel, args), so they cannot be
    imported. This keeps only imports, ALL-CAPS constants and `def` functions, so their deterministic
    math can be unit-tested directly instead of trusting a hand-copied duplicate here.
    """
    tree = ast.parse(wf_path.read_text(encoding="utf-8"))
    keep = [
        n for n in tree.body
        if isinstance(n, (ast.Import, ast.ImportFrom, ast.FunctionDef))
        or (isinstance(n, ast.Assign) and all(isinstance(t, ast.Name) and t.id.isupper() for t in n.targets))
    ]
    ns: dict = {}
    exec(compile(ast.Module(body=keep, type_ignores=[]), str(wf_path), "exec"), ns)
    return ns


def _card(values: list, bels: list, classes: list = None, sources: list = None) -> dict:
    classes = classes or ["[research]"] * 7
    card = {k: {"value": v, "believability": b, "evidence_class": c, "justification": "t"}
            for k, v, b, c in zip(ORDERED_KEYS, values, bels, classes)}
    card["sources"] = list(sources or [])
    return card


def self_test_workflow_math(repo_root: Path) -> None:
    for wf in ("workflows/discover_ideas.py", "workflows/deep_dive_idea.py"):
        ns = load_workflow_math(repo_root / wf)
        # (a) constants must match this validator, or runs and validation silently disagree
        assert ns["LEGAL_SCALES"] == LEGAL_SCALES, f"{wf}: LEGAL_SCALES drifted from validator"
        assert ns["DIVISOR"] == DIVISOR, f"{wf}: DIVISOR drifted"
        assert ns["PANEL_WEIGHTS"] == PANEL_WEIGHTS, f"{wf}: PANEL_WEIGHTS drifted"
        assert ns["SYNTHETIC_BELIEVABILITY_CAP"] == SYNTHETIC_BELIEVABILITY_CAP, f"{wf}: synthetic cap drifted"
        cps = ns["compute_problem_score"]
        # (b) the workflow's own scorer reproduces the ASB anchors
        wp = cps(_card([100_000_000, 0.1, 100, 0.01, 0.5, 0.5, 1.0], [0.7] * 7, sources=["https://example.com"]))
        assert wp["score"] == 4.0, f"{wf}: WP Engine anchor gave {wp['score']}"
        # (c) anti-inflation: [fermi] capped at 0.4; >= 0.7 without sources is clamped for EVERY class
        fermi = cps(_card([100_000] * 1 + [0.5, 1000, 0.1, 0.5, 0.5, 0.5], [1.0] * 7, ["[fermi]"] * 7, ["https://x"]))
        assert all(c["believability"] == 0.4 for c in fermi["criteria"].values()), f"{wf}: fermi cap broken"
        data_no_src = cps(_card([100_000, 0.5, 1000, 0.1, 0.5, 0.5, 0.5], [1.0] * 7, ["[data]"] * 7, []))
        assert all(c["believability"] == 0.4 for c in data_no_src["criteria"].values()), (
            f"{wf}: [data] evidence with no source URLs kept >= 0.7 believability"
        )
        assert not verify_scorecard_dict("t", data_no_src), f"{wf}: validator rejects workflow's own output"
        # (d) DP2 reconciliation: weaker-evidence change reverted, equal-or-stronger change kept
        rec = ns["reconcile_rude_qa_scorecard"]
        base = _card([100_000, 0.5, 1000, 0.1, 0.5, 0.5, 0.5], [0.7, 0.7, 0.7, 0.7, 0.4, 0.7, 0.4], sources=["https://a"])
        adj = _card([100_000, 0.5, 1000, 0.1, 0.1, 0.1, 0.1], [0.7, 0.7, 0.7, 0.7, 0.7, 0.4, 0.4], sources=["https://b"])
        merged, reverted = rec(base, adj)
        post = cps(merged)["criteria"]
        assert post["eager_identity"]["value"] == 0.1, f"{wf}: stronger-evidence downgrade was dropped"
        assert post["eager_comparative"]["value"] == 0.5, f"{wf}: weaker-evidence downgrade was applied"
        assert post["enduring"]["value"] == 0.1, f"{wf}: equal-evidence downgrade was dropped"
        assert post["eager_comparative"]["believability"] == 0.7, f"{wf}: restored criterion lost its sources"
        assert len(reverted) == 1 and "eager_comparative" in reverted[0], f"{wf}: reverted notes wrong: {reverted}"
        assert merged["sources"] == ["https://a", "https://b"], f"{wf}: sources not merged"
        # (e) workflow panel math == validator panel math
        cpd = ns["compute_panel_decision"]
        for verdict, rec_ev in (("SHARPENED", "PURSUE_VALIDATION"), ("BAD_IDEA", "PURSUE_VALIDATION"), ("NOT_YET_READY", "KILL")):
            pd = cpd(wp, verdict, rec_ev)
            v = pd["votes"]
            exp, split = compute_panel(v["scorer"], v["attacker"], v["consequence_ev"])
            assert pd["panel_weighted_score"] == exp and pd["disagreement_flag"] == split, f"{wf}: panel drift"
        print(f"  [PASS] Workflow math (constants, anchors, anti-inflation, DP2 reconciliation, panel): {wf}")


def run_self_test() -> int:
    # 1. Canonical ASB calibration anchors
    anchors = [
        ("Managed WP Hosting", [100_000_000, 0.1, 100, 0.01, 0.5, 0.5, 1.0], 4.0),
        ("Creator Email Marketing", [10_000_000, 1.0, 100, 0.01, 0.5, 0.5, 0.5], 2.0),
        ("Consumer Security", [1_000_000_000, 0.01, 10, 0.01, 0.5, 0.1, 0.5], 0.04),
    ]
    for name, vals, expected in anchors:
        mapping = dict(zip(ORDERED_KEYS, vals))
        for k, v in mapping.items():
            assert is_legal(k, v), f"{name}: illegal {k}={v}"
        got = compute_score(mapping)
        assert abs(got - expected) < 1e-6, f"{name}: expected {expected}, got {got}"
        print(f"  [PASS] ASB calibration anchor '{name}': {got}")

    # 2. Illegal scale, log10 snapping sanity & believability checks
    assert not is_legal("self_aware", 0.7)
    assert not is_legal("plausible", 50_000)
    assert not is_legal_believability(0.55)
    assert is_legal_believability(SYNTHETIC_BELIEVABILITY_CAP)
    # Log10 snap check: 40,000 is closer in log10 to 100,000 (0.398) than 10,000 (0.602)
    assert abs(math.log10(40_000) - math.log10(100_000)) < abs(math.log10(40_000) - math.log10(10_000))
    print("  [PASS] Illegal off-scale, log10 scale & believability checks")

    # 3. Dalio EBI + Bottleneck Min + Panel Weighting + Numeric EV math
    ebi, bmin = compute_ebi_and_min([1.0, 1.0, 0.7, 1.0, 0.7, 0.7, 0.2])
    assert abs(ebi - 0.757) < 1e-3 and abs(bmin - 0.2) < 1e-6
    p_aligned, split_aligned = compute_panel(1.0, 1.0, 1.0)
    assert p_aligned == 1.0 and not split_aligned
    p_split, split_flag = compute_panel(1.0, 0.0, -1.0)
    assert p_split == 0.0 and split_flag  # Now killed by strict <= 0.0 gate!
    assert not verify_ev_dict("test", {"p_viable_pct": 35, "target_arr_usd": 120000, "validation_hours": 20, "expected_arr_usd": 42000.0, "ev_per_validation_hour": 2100.0})
    print("  [PASS] Dalio EBI/Bottleneck Min, Panel Weighting (0.30/0.40/0.30) & EV math")

    # 4. Workflow top-level await syntax check
    repo_root = Path(__file__).resolve().parent.parent
    for wf in (
        "workflows/discover_ideas.py",
        "workflows/deep_dive_idea.py",
        "workflows/run_synthetic_interviews.py",
        "workflows/reverse_founder_fit.py",
    ):
        wf_path = repo_root / wf
        assert wf_path.exists(), f"Missing workflow: {wf_path}"
        compile(wf_path.read_text(encoding="utf-8"), str(wf_path), "exec", flags=ast.PyCF_ALLOW_TOP_LEVEL_AWAIT)
        print(f"  [PASS] Workflow syntax (top-level await): {wf}")

    # 5. Learned principles check
    lp = repo_root / "principles" / "LEARNED-PRINCIPLES.md"
    assert lp.exists(), f"Missing {lp}"
    lp_text = lp.read_text(encoding="utf-8")
    assert "DP1" in lp_text and "DP7" in lp_text
    print("  [PASS] Dalio learned principles (DP1-DP7) present")

    # 6. The workflows' own deterministic math (not just this file's copy of it)
    self_test_workflow_math(repo_root)

    # 7. Validator catches a >= 0.7 believability with no sources (new-format scorecards only)
    bad = {"criteria": {k: {"value": v, "believability": 0.7, "evidence_class": "[data]"}
                        for k, v in zip(ORDERED_KEYS, [100_000, 0.5, 1000, 0.1, 0.5, 0.5, 0.5])},
           "score": 1.0, "sources": []}
    assert verify_scorecard_dict("t", bad), "validator missed >= 0.7 believability without sources"
    print("  [PASS] Validator flags >= 0.7 believability without cited sources")

    print("ALL SELF-TESTS PASSED.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="ASB + Dalio Problem Score, Panel & Quarantine Validator")
    parser.add_argument("target", nargs="?", help="Path to runs/<run-id>/ or standalone idea dir")
    parser.add_argument("--self-test", action="store_true", help="Run calibration, Dalio math & syntax tests")
    parser.add_argument(
        "--calc",
        nargs=7,
        type=float,
        metavar=("PLAUSIBLE", "SELF_AWARE", "LUCRATIVE", "LIQUID", "EAGER_ID", "EAGER_COMP", "ENDURING"),
        help="Compute deterministic ASB Problem Score from 7 values",
    )
    ns = parser.parse_args()

    if ns.self_test:
        return run_self_test()

    if ns.calc:
        mapping = dict(zip(ORDERED_KEYS, ns.calc))
        bad = [f"{k}={v}" for k, v in mapping.items() if not is_legal(k, v)]
        if bad:
            print(f"ERROR: Illegal scale value(s): {', '.join(bad)}")
            return 1
        score = compute_score(mapping)
        verdict = (
            "BLOCKED" if mapping["eager_identity"] == 0 else
            "STRONG (>=2)" if score >= 2.0 else
            "VIABLE INDIE (>=1)" if score >= 1.0 else
            "MARGINAL (0.5-0.99)" if score >= 0.5 else
            "NOT VIABLE (<0.5)"
        )
        print(f"Score = {score} — {verdict}")
        return 0

    if ns.target:
        target = Path(ns.target)
        if not (target / "run_data.json").exists() and not (target / "candidates.json").exists() \
                and not (target / "synthetic-interviews").exists() and target.is_dir() \
                and any((d / "run_data.json").exists() or (d / "candidates.json").exists() for d in target.iterdir() if d.is_dir()):
            return validate_runs_dir(target)
        return validate_path(target)

    parser.print_help()
    return 0


if __name__ == "__main__":
    sys.exit(main())
