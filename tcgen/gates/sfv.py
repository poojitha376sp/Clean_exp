"""
Gate 2 -- Syntactic Form Validity.

SFV = 0.5 * schema_score + 0.5 * representation_score

  schema_score          fraction of canonical test cases that validate against
                        schemas/testcase.schema.json (id, traced req_ids, kind,
                        preconditions, steps, expected), with unique ids and
                        req_ids that exist in the unit.
  representation_score  syntax check of the representation artifact itself,
                        routed by the representation's ACTUAL group (the old
                        pipeline hard-coded "Finite State Machine" for every
                        suite). Gherkin uses the official gherkin parser, xUnit
                        uses Python's ast, state machines use a transition check,
                        the rest reuse the old group validators.

pass = every canonical case valid  AND  representation_score >= group threshold.
"""

import json
import re
from pathlib import Path

import jsonschema

from . import sfv_repr
from .config import SFV_THRESHOLD, SFV_THRESHOLD_BY_GROUP, get_group

_SCHEMA = json.loads((Path(__file__).resolve().parents[2] / "schemas" / "testcase.schema.json").read_text())
_VALIDATOR = jsonschema.Draft202012Validator(_SCHEMA)


def check_schema(test_cases, unit_req_ids):
    issues = []
    if not isinstance(test_cases, list) or not test_cases:
        return 0.0, ["No canonical test cases found (expected a JSON list)."]
    valid = 0
    seen = set()
    for i, tc in enumerate(test_cases):
        errs = [e.message for e in _VALIDATOR.iter_errors(tc)] if isinstance(tc, dict) else ["not an object"]
        if isinstance(tc, dict):
            tid = tc.get("id")
            if tid in seen:
                errs.append(f"duplicate id {tid}")
            seen.add(tid)
            unknown = [r for r in tc.get("req_ids", []) if r not in unit_req_ids]
            if unknown:
                errs.append(f"traces to unknown requirement ids {unknown}")
        if errs:
            issues.append(f"test case #{i + 1} ({tc.get('id') if isinstance(tc, dict) else '?'}): " + "; ".join(errs[:3]))
        else:
            valid += 1
    return valid / len(test_cases), issues


def _gherkin(text):
    try:
        from gherkin.parser import Parser
        doc = Parser().parse(text)
        children = doc.get("feature", {}).get("children", []) if doc.get("feature") else []
        scenarios = [c for c in children if "scenario" in c]
        steps = sum(len(c["scenario"].get("steps", [])) for c in scenarios)
        if not scenarios:
            return 0.4, ["Gherkin parsed but contains no Scenario."]
        ok_steps = all(len(c["scenario"].get("steps", [])) >= 2 for c in scenarios)
        return (1.0 if ok_steps else 0.8), ([] if ok_steps else [f"some scenarios have <2 steps ({steps} steps total)"])
    except Exception as e:  # parser raises CompositeParserException with line info
        return 0.0, [f"Gherkin parse error: {str(e).splitlines()[0][:200]}"]


_TRANSITION = re.compile(r"^\s*[\w\[\]().\"' -]+?\s*(-+>|→|=>)\s*[\w\[\]().\"' -]+", re.MULTILINE)


def _state_machine(text):
    transitions = len(_TRANSITION.findall(text))
    states_decl = bool(re.search(r"\bstates?\s*[:=]|^\s*(state\s+\w+|\[\*\])", text, re.IGNORECASE | re.MULTILINE))
    initial = bool(re.search(r"\b(initial|start)\b", text, re.IGNORECASE))
    events = bool(re.search(r"\b(event|trigger|on|guard|when)\b|\[[^\]]+\]", text, re.IGNORECASE))
    checks = {"transitions (>=2)": transitions >= 2, "states declared": states_decl,
              "initial state": initial, "events/guards": events, "balanced brackets": sfv_repr._balanced(text)}
    score = sum(checks.values()) / len(checks)
    return score, [f"missing: {k}" for k, v in checks.items() if not v]


def check_representation(representation, artifact):
    text = artifact or ""
    if not text.strip():
        return 0.0, ["Representation artifact is empty."]
    group = get_group(representation)
    low = representation.lower()
    if "gherkin" in low:
        return _gherkin(text)
    if "xunit" in low:
        r = sfv_repr._xunit_sfv(text)
    elif group == 2:
        return _state_machine(text)
    elif group == 1:
        r = sfv_repr._gherkin_sfv(text) if re.search(r"^\s*Scenario", text, re.MULTILINE) else _structured_flows(text)
    elif group == 3:
        r = sfv_repr._sequence_sfv(text)
    elif group == 4:
        r = sfv_repr._table_sfv(text)
    elif group == 5:
        r = sfv_repr._xunit_sfv(text) if re.search(r"^\s*(def |class |import )", text, re.MULTILINE) else sfv_repr._generic_sfv(text)
    else:
        r = sfv_repr._symbolic_sfv(text)
    return r["score"], r["issues"]


def _structured_flows(text):
    """Use cases / user stories / goal models: named actor + main flow + at
    least one alternative/exception flow, numbered steps."""
    checks = {
        "actor/role": bool(re.search(r"\b(actor|as an?|role|agent)\b", text, re.IGNORECASE)),
        "main flow": bool(re.search(r"\b(main|basic|primary|success)\b.*\b(flow|scenario|path)\b|\bgoal\b", text, re.IGNORECASE)),
        "alternative/exception flow": bool(re.search(r"\b(alternat\w*|exception|extension|obstacle)\b", text, re.IGNORECASE)),
        "numbered steps": bool(re.search(r"^\s*\d+[.)]", text, re.MULTILINE)),
    }
    return {"score": sum(checks.values()) / len(checks), "issues": [f"missing: {k}" for k, v in checks.items() if not v]}


def evaluate_sfv(representation, artifact, test_cases, unit_req_ids):
    group = get_group(representation)
    schema_score, schema_issues = check_schema(test_cases, set(unit_req_ids))
    rep_score, rep_issues = check_representation(representation, artifact)
    threshold = SFV_THRESHOLD_BY_GROUP.get(group, SFV_THRESHOLD)
    return {
        "representation": representation,
        "group": group,
        "schema_score": round(schema_score, 4),
        "representation_score": round(rep_score, 4),
        "sfv_score": round(0.5 * schema_score + 0.5 * rep_score, 4),
        "threshold": threshold,
        "sfv_pass": schema_score == 1.0 and rep_score >= threshold,
        "issues": schema_issues[:10] + rep_issues[:10],
    }
