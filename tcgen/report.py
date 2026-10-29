"""S7 -- one table per project: gates, repairs, execution, cost. Writes
runs/<p>/S7_report.md and S7_summary.csv."""

import csv
import hashlib
import json
from statistics import mean

from . import represent, suite
from .util import run_dir, slug, read_json


def _m(xs):
    xs = [x for x in xs if isinstance(x, (int, float))]
    return round(mean(xs), 3) if xs else None


def _integrity(project, gen, arm, suites):
    """True if every executed suite still matches the fingerprint frozen
    before the code was opened (S6). None if S6 hasn't run."""
    fp = run_dir(project) / slug(gen) / f"S6_frozen_{arm}.json"
    if not fp.exists():
        return None
    frozen = read_json(fp)["suites"]
    now = {f"{s['unit_id']}/{s['representation']}": hashlib.sha256(json.dumps(s["test_cases"], sort_keys=True).encode()).hexdigest()
           for s in suites if s.get("test_cases")}
    return all(now.get(k) == v for k, v in frozen.items())


def gen_row(project, gen, arm="gated"):
    row = {"generator": gen}
    try:
        s2 = represent.load(project, gen)
    except FileNotFoundError:
        s2 = []
    suites = suite.load_all(project, gen)
    row.update({
        "units": len(s2),
        "G1_pass_rate": _m([1.0 if r["gate1_pass"] else 0.0 for r in s2]),
        "G1_repairs_avg": _m([r["repair_rounds"] for r in s2]),
        "G1_llm_vs_heuristic_agreement": _m([r["agreement_with_heuristic_top3"] for r in s2]),
        "suites": len(suites),
        "G2_pass_rate": _m([1.0 if s["gate2_pass"] else 0.0 for s in suites]),
        "SFV_avg": _m([(s.get("sfv") or {}).get("sfv_score") for s in suites]),
        "G3_pass_rate": _m([1.0 if s["gate3_pass"] else 0.0 for s in suites]),
        "FSA_avg": _m([(s.get("fsa") or {}).get("fsa_score") for s in suites]),
        "CC_avg": _m([(s.get("fsa") or {}).get("clause_coverage") for s in suites]),
        "NC_avg": _m([(s.get("fsa") or {}).get("negative_coverage") for s in suites]),
        "OA_avg": _m([(s.get("fsa") or {}).get("oracle_assertiveness") for s in suites]),
        "BC_avg": _m([(s.get("fsa") or {}).get("boundary_coverage") for s in suites]),
        "Mg_avg": _m([(s.get("fsa") or {}).get("groundedness_mg") for s in suites]),
        "traceability_avg": _m([(s.get("fsa") or {}).get("traceability") for s in suites]),
        "repairs_avg": _m([s["repairs_used"] for s in suites]),
        "test_cases": sum(len(s.get("test_cases") or []) for s in suites),
    })
    row["tests_frozen_before_code_ok"] = _integrity(project, gen, arm, suites)
    ex_path = run_dir(project) / slug(gen) / f"S6_execution_{arm}.json"
    if ex_path.exists():
        ex = read_json(ex_path)
        sm = ex["summary"]
        row.update({k: sm.get(k) for k in ("n_cases", "passed", "failed", "error", "skipped", "not_implemented",
                                            "executable_rate", "pass_rate_of_executed", "code_mismatches", "test_bugs")})
        row["line_cov_pct"] = (sm.get("coverage") or {}).get("line_pct")
        # does passing Gate 3 predict tests that run cleanly?
        for flag in (True, False):
            cs = [c for c in ex["cases"] if c["gate3_pass"] is flag and c["status"] != "missing"]
            row[f"exec_ok_rate_G3{'pass' if flag else 'fail'}"] = _m([1.0 if c["status"] in ("passed", "failed") else 0.0 for c in cs])
    return row


def rep_table(project, gens):
    agg = {}
    for g in gens:
        for s in suite.load_all(project, g):
            a = agg.setdefault(s["representation"], {"n": 0, "g2": 0, "g3": 0, "fsa": []})
            a["n"] += 1
            a["g2"] += s["gate2_pass"]
            a["g3"] += s["gate3_pass"]
            a["fsa"].append((s.get("fsa") or {}).get("fsa_score"))
    return agg


def run(project, gens):
    rows = [gen_row(project, g) for g in gens]
    rd = run_dir(project)
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with open(rd / "S7_summary.csv", "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)
    s1 = read_json(rd / "S1_requirements.json")
    reqs = s1["requirements"]
    md = [f"# Results -- {project}", "",
          f"Requirements extracted: **{len(reqs)}** ({sum(1 for r in reqs if r.get('testable'))} testable), "
          f"extraction chunk failures: {len(s1['failures'])}", "",
          "## Per generator", "", "| metric | " + " | ".join(r["generator"] for r in rows) + " |",
          "|---|" + "---|" * len(rows)]
    for k in keys[1:]:
        md.append(f"| {k} | " + " | ".join(str(r.get(k, "")) for r in rows) + " |")
    md += ["", "## Per representation (all generators)", "", "| representation | suites | G2 pass | G3 pass | FSA avg |", "|---|---|---|---|---|"]
    for rep, a in sorted(rep_table(project, gens).items(), key=lambda x: -x[1]["n"]):
        md.append(f"| {rep} | {a['n']} | {a['g2']} | {a['g3']} | {_m(a['fsa'])} |")
    (rd / "S7_report.md").write_text("\n".join(md) + "\n")
    print(f"  S7 report -> {rd / 'S7_report.md'}")
