"""
S3 generate -> S4 Gate 2 (SFV) -> S5 Gate 3 (FSA), as one closed loop per
(unit, representation, generator):

    attempt 0: generate
    SFV fails  -> repair with the SFV issues            \\  shared budget of
    FSA fails  -> repair with the judge's findings      /   max_repairs attempts
    (a repaired suite goes through SFV again before FSA)

Every attempt is saved. The final suite is the first attempt that passes both
gates, else the best attempt (SFV pass first, then highest FSA), flagged.
"""

import json

from . import llm
from .gates.config import get_sufficiency_checklist
from .gates.fsa import evaluate_fsa
from .gates.sfv import evaluate_sfv
from .represent import fmt_reqs, REPS_COMPACT
from .util import CFG, prompt, read_json, run_dir, slug, write_json

REP_HINTS = dict(line.split(" — ", 1) for line in REPS_COMPACT.splitlines() if " — " in line)


def _feedback_sfv(s):
    return ("\nYOUR PREVIOUS ATTEMPT FAILED THE SYNTAX GATE (SFV %.2f). Fix these problems and output the full corrected suite:\n"
            % s["sfv_score"]) + "\n".join(f"- {i}" for i in s["issues"]) + "\n"


def _feedback_fsa(f):
    lines = []
    if f.get("untraced_reqs"):
        lines.append(f"- requirements with NO test case: {f['untraced_reqs']} (add at least one each)")
    for c in f.get("uncovered_clauses", [])[:6]:
        lines.append(f"- uncovered clause: {c}")
    for h in f.get("hallucinated", [])[:6]:
        lines.append(f"- ungrounded value '{h.get('value')}' ({h.get('context')}): remove or use the SRS value")
    for w in f.get("weaknesses", [])[:5]:
        lines.append(f"- {w}")
    scores = {k: f.get(k) for k in ("clause_coverage", "negative_coverage", "oracle_assertiveness", "boundary_coverage", "groundedness_mg")}
    return (f"\nYOUR PREVIOUS ATTEMPT FAILED THE ADEQUACY GATE (FSA {f.get('fsa_score')}; sub-scores {scores}). "
            "Output the full improved suite addressing:\n" + "\n".join(lines) + "\n")


def run_one(unit, rep, gen, system_type):
    testable = [r["id"] for r in unit["reqs"]]
    reqs_text = fmt_reqs(unit["reqs"])
    attempts, feedback = [], ""
    for a in range(CFG["pipeline"]["max_repairs"] + 1):
        p = prompt("generate", REP=rep, REP_HINT=REP_HINTS.get(rep, ""), UNIT=unit["unit_id"], REQS=reqs_text,
                   DEPS=fmt_reqs(unit["deps"]), CHECKLIST=get_sufficiency_checklist(rep), FEEDBACK=feedback)
        rec = {"attempt": a, "feedback_given": feedback.strip() or None}
        try:
            raw = llm.call(gen, p, stage="S3_generate")
        except llm.LLMError as e:
            rec["error"] = str(e)
            attempts.append(rec)
            break
        artifact = llm.extract_block(raw, "artifact")
        cases = llm.extract_json(llm.extract_block(raw, "json") or "")
        if cases is None:
            cases = llm.extract_json(raw)
        if isinstance(cases, dict):
            cases = cases.get("test_cases") or cases.get("tests") or []
        rec.update({"artifact": artifact, "test_cases": cases, "raw_if_unparsed": None if artifact else raw[:3000]})
        sfv = evaluate_sfv(rep, artifact, cases, testable)
        rec["sfv"] = sfv
        if not sfv["sfv_pass"]:
            attempts.append(rec)
            feedback = _feedback_sfv(sfv)
            continue
        try:
            fsa = evaluate_fsa(reqs_text, rep, artifact, cases, testable, system_type, stage="S5_fsa")
        except llm.LLMError as e:
            fsa = {"error": str(e), "fsa_pass": False, "fsa_score": 0.0}
        rec["fsa"] = fsa
        attempts.append(rec)
        if fsa.get("fsa_pass"):
            break
        feedback = _feedback_fsa(fsa)

    def rank(r):
        return (bool(r.get("sfv", {}).get("sfv_pass")), bool(r.get("fsa", {}).get("fsa_pass")),
                r.get("fsa", {}).get("fsa_score", 0.0), r.get("sfv", {}).get("sfv_score", 0.0))

    scored = [r for r in attempts if "sfv" in r]
    best = max(scored, key=rank) if scored else None
    return {
        "unit_id": unit["unit_id"], "representation": rep, "generator": gen, "system_type": system_type,
        "n_attempts": len(attempts), "repairs_used": max(0, len(attempts) - 1),
        "final_attempt": best["attempt"] if best else None,
        "gate2_pass": bool(best and best["sfv"]["sfv_pass"]),
        "gate3_pass": bool(best and best.get("fsa", {}).get("fsa_pass")),
        "sfv": best["sfv"] if best else None, "fsa": best.get("fsa") if best else None,
        "artifact": best["artifact"] if best else None,
        "test_cases": best["test_cases"] if best else [],
        "attempts": attempts,
    }


def run(project, gen, units, s2):
    """(unit, representation) suites are independent -> run concurrently
    (pipeline.workers). Finished suites are skipped, so a run can resume."""
    from concurrent.futures import ThreadPoolExecutor
    base = run_dir(project) / slug(gen) / "S3_S5_suites"
    by_unit = {r["unit_id"]: r for r in s2}
    jobs = []
    for u in units:
        sel = by_unit.get(u["unit_id"])
        if sel and sel["chosen"]:
            jobs += [(u, rep, sel["system_type"]) for rep in sel["chosen"]]

    def one(job):
        u, rep, st = job
        out = base / f"{u['unit_id']}__{slug(rep)}.json"
        if out.exists():
            return read_json(out)
        try:
            res = run_one(u, rep, gen, st)
        except Exception as e:                       # never lose the whole run to one suite
            res = {"unit_id": u["unit_id"], "representation": rep, "generator": gen, "system_type": st,
                   "error": f"{type(e).__name__}: {e}", "n_attempts": 0, "repairs_used": 0,
                   "gate2_pass": False, "gate3_pass": False, "sfv": None, "fsa": None, "test_cases": [], "attempts": []}
        write_json(out, res)
        print(f"  S3-S5 [{gen}] {u['unit_id']} / {rep}: attempts={res['n_attempts']} "
              f"SFV={res['sfv'] and res['sfv']['sfv_score']} FSA={res['fsa'] and res['fsa'].get('fsa_score')} "
              f"G2={res['gate2_pass']} G3={res['gate3_pass']}", flush=True)
        return res

    with ThreadPoolExecutor(CFG["pipeline"].get("workers", 1)) as ex:
        return list(ex.map(one, jobs))


def load_all(project, gen):
    base = run_dir(project) / slug(gen) / "S3_S5_suites"
    return [read_json(p) for p in sorted(base.glob("*.json"))] if base.exists() else []
