"""
Gate 3 -- Functional Semantic Adequacy (+ groundedness Mg).

    FSA = wc*CC + wn*NC + wo*OA + wb*BC + wg*Mg        (weights by system type, config.py)

CC/NC/OA/BC and the concrete-element list come from ONE judge call. The
judge is a different model family from the generators (config.yaml
models.judge) to avoid self-preference bias -- the old pipeline had
gpt-oss-120b grading its own suites.

Added next to it, computed without any LLM:
    traceability = testable requirements with >=1 test case / testable requirements
pass = FSA >= fsa_threshold  AND  traceability == 1.0
"""

import json

from .. import llm
from ..util import CFG, prompt
from .config import get_fsa_weights, get_sufficiency_checklist
from .groundedness import compute_mg


def traceability(test_cases, testable_ids):
    covered = {r for tc in test_cases if isinstance(tc, dict) for r in tc.get("req_ids", [])}
    testable = set(testable_ids)
    if not testable:
        return 1.0, []
    missing = sorted(testable - covered)
    return round(1 - len(missing) / len(testable), 4), missing


def _clamp(x):
    try:
        return min(1.0, max(0.0, float(x)))
    except (TypeError, ValueError):
        return 0.0


def evaluate_fsa(reqs_text, representation, artifact, test_cases, testable_ids, system_type, stage=""):
    p = prompt("fsa_judge", SYSTEM_TYPE=system_type, REP=representation, REQS=reqs_text,
               ARTIFACT=artifact or "(none)", TESTCASES=json.dumps(test_cases, indent=1),
               CHECKLIST=get_sufficiency_checklist(representation))
    raw = llm.call(CFG["models"]["judge"], p, stage=stage)
    parsed = llm.extract_json(raw)
    trace, missing = traceability(test_cases, testable_ids)
    if not isinstance(parsed, dict):
        return {"error": "judge output not parseable", "raw": raw[:2000], "traceability": trace,
                "untraced_reqs": missing, "fsa_score": 0.0, "fsa_pass": False}

    cc, nc, oa, bc = (_clamp(parsed.get(k)) for k in
                      ("clause_coverage", "negative_coverage", "oracle_assertiveness", "boundary_coverage"))
    elements = [e for e in parsed.get("concrete_elements") or [] if isinstance(e, dict)]
    mg = compute_mg(elements)
    w = get_fsa_weights(representation, system_type)
    fsa = w["wc"] * cc + w["wn"] * nc + w["wo"] * oa + w["wb"] * bc + w["wg"] * mg
    thr = CFG["gates"]["fsa_threshold"]
    return {
        "system_type": system_type, "weights": w,
        "clause_coverage": cc, "negative_coverage": nc, "oracle_assertiveness": oa,
        "boundary_coverage": bc, "groundedness_mg": round(mg, 4),
        "hallucinated": [e for e in elements if e.get("grounded") is False],
        "n_concrete_elements": len(elements),
        "uncovered_clauses": parsed.get("uncovered_clauses") or [],
        "weaknesses": parsed.get("weaknesses") or [],
        "traceability": trace, "untraced_reqs": missing,
        "fsa_score": round(fsa, 4), "fsa_threshold": thr,
        "fsa_pass": fsa >= thr and trace == 1.0,
    }
