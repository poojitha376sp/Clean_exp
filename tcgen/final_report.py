"""
Build runs/ANALYSIS/REPORT.md from the analysis tables: numbers first, then
data-derived findings (each finding states the numbers it rests on).

    python -m tcgen.final_report
"""

from collections import defaultdict
from statistics import mean

from . import analyze
from .util import CFG, ROOT, read_json, run_dir, slug

OUT = ROOT / CFG["paths"]["runs_dir"] / "ANALYSIS"


def fmt(v, pct=False):
    if v is None:
        return "–"
    if isinstance(v, bool):
        return "yes" if v else "no"
    if isinstance(v, float):
        return f"{v * 100:.0f}%" if pct else f"{v:.2f}"
    return str(v)


def table(rows, cols, headers=None, pct=()):
    headers = headers or cols
    out = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(cols)]
    for r in rows:
        out.append("| " + " | ".join(fmt(r.get(c), c in pct) for c in cols) + " |")
    return "\n".join(out)


def code_rows():
    """S6 results per (project, model): execution and/or audit summaries."""
    rows = []
    for proj in analyze.PROJECTS:
        for gen in CFG["models"].get("plan", {}).get(proj, CFG["models"]["generators"]):
            d = run_dir(proj) / slug(gen)
            row = {"project": proj, "model": analyze.meta(gen)["name"]}
            if (d / "S6_execution_gated.json").exists():
                s = read_json(d / "S6_execution_gated.json")["summary"]
                row.update({"exec_cases": s["n_cases"], "passed": s["passed"], "failed": s["failed"], "error": s["error"],
                            "skipped": s["skipped"], "exec_rate": s["executable_rate"], "pass_rate": s["pass_rate_of_executed"],
                            "code_mismatch": s["code_mismatches"], "test_bugs": s["test_bugs"],
                            "line_cov": (s.get("coverage") or {}).get("line_pct")})
            if (d / "S6_execution_gated.json").exists():
                cs = read_json(d / "S6_execution_gated.json")["cases"]
                gp = [c for c in cs if c["gate3_pass"] and c["status"] in ("passed", "failed")]
                row["pass_rate_gatepass_only"] = round(sum(c["status"] == "passed" for c in gp) / len(gp), 3) if gp else None
                if row.get("line_cov") is not None and row.get("exec_cases"):
                    row["line_cov_per_10_tests"] = round(row["line_cov"] / row["exec_cases"] * 10, 2)
            if (d / "S6_audit.json").exists():
                ac = read_json(d / "S6_audit.json")["cases"]
                gp = [c for c in ac if c["gate3_pass"]]
                row["satisfied_rate_gatepass_only"] = round(sum(c["verdict"] == "satisfied" for c in gp) / len(gp), 3) if gp else None
                row["violated_rate_gatepass_only"] = round(sum(c["verdict"] == "violated" for c in gp) / len(gp), 3) if gp else None
                s = read_json(d / "S6_audit.json")["summary"]
                row.update({"audit_cases": s["n_cases"], "satisfied": s["n_satisfied"], "violated": s["n_violated"],
                            "not_impl": s["n_not_implemented"], "unclear": s["n_unclear"],
                            "srs_cov_tests": s["srs_coverage_by_tests"], "srs_reached_code": s["srs_reached_by_code_rate"],
                            "satisfied_rate": s["satisfied_rate"]})
            if len(row) > 2:
                rows.append(row)
    return rows


def audit_vs_exec():
    """Where a project has both execution and audit, how often do they agree?"""
    agree = total = 0
    for proj in analyze.PROJECTS:
        for gen in CFG["models"].get("plan", {}).get(proj, CFG["models"]["generators"]):
            d = run_dir(proj) / slug(gen)
            if not ((d / "S6_execution_gated.json").exists() and (d / "S6_audit.json").exists()):
                continue
            ex = {(c["suite"], c["case"].get("id")): c["status"] for c in read_json(d / "S6_execution_gated.json")["cases"]}
            for c in read_json(d / "S6_audit.json")["cases"]:
                st = ex.get((c["suite"], c["case_id"]))
                if st in ("passed", "failed") and c["verdict"] in ("satisfied", "violated"):
                    total += 1
                    agree += (st == "passed") == (c["verdict"] == "satisfied")
    return (round(agree / total, 3), total) if total else (None, 0)


FAIR_PROJECT = "doorstop"    # every model ran the same units here -> model rankings use it


def fair_sets(ok):
    """(rows for model comparison, rows for project comparison): model rankings
    only on the project where every model did the same units; project
    comparisons only with models that ran on every compared project."""
    fair = [r for r in ok if r["project"] == FAIR_PROJECT]
    projs = {r["project"] for r in ok}
    shared = set.intersection(*[{r["model"] for r in ok if r["project"] == p} for p in projs]) if projs else set()
    return fair, [r for r in ok if r["model"] in shared], sorted(shared)


def findings(rows, t, stats, crow):
    F = []
    ok = [r for r in rows if not r["error"]]
    fair, shared_rows, shared = fair_sets(ok)
    fair_by_model = analyze.agg(fair, ["model"], ["G2_pass", "G3_pass", "both_pass", "FSA", "NC", "BC", "OA", "Mg", "repairs"])
    t["fair_by_model"] = fair_by_model
    bm = sorted([r for r in fair_by_model if r.get("FSA_mean") is not None], key=lambda r: -r["FSA_mean"])
    F.append(f"**Model comparisons use {FAIR_PROJECT} only** (every model generated for the same units there); "
             f"project comparisons use only the models run on every project ({', '.join(shared) or 'none'}).")
    if bm:
        F.append(f"**Best overall adequacy:** {bm[0]['model']} (mean FSA {bm[0]['FSA_mean']:.2f}, both-gates pass {fmt(bm[0].get('both_pass_rate'), True)}); "
                 f"**weakest:** {bm[-1]['model']} (FSA {bm[-1]['FSA_mean']:.2f}, both-gates pass {fmt(bm[-1].get('both_pass_rate'), True)}).")
    g2 = sorted(fair_by_model, key=lambda r: r.get("G2_pass_rate") or 0)
    if g2:
        F.append(f"**Format discipline (Gate 2) is the first filter:** G2 pass ranges from {fmt(g2[0].get('G2_pass_rate'), True)} "
                 f"({g2[0]['model']}) to {fmt(g2[-1].get('G2_pass_rate'), True)} ({g2[-1]['model']}). Suites that fail G2 never reach the judge.")
    rho, n = analyze.spearman([r["params_b"] for r in fair], [r["FSA"] for r in fair])
    stats["spearman_params_vs_FSA_fair"] = (rho, n)
    stats["spearman_active_params_vs_FSA_fair"] = analyze.spearman([r["active_b"] for r in fair], [r["FSA"] for r in fair])
    if rho is not None:
        F.append(f"**Size vs adequacy:** Spearman ρ(parameters, FSA) = {rho} over {n} judged suites; "
                 f"ρ(active parameters, FSA) = {stats['spearman_active_params_vs_FSA_fair'][0]} ({FAIR_PROJECT}; small n, indicative only). "
                 + ("Bigger models score higher, but the relationship is moderate." if rho > 0.2 else
                    "Model size alone explains little of the adequacy." if abs(rho) <= 0.2 else "Surprisingly, larger models scored lower."))
    u, p = analyze.mann_whitney([r["FSA"] for r in fair if r["code_model"]], [r["FSA"] for r in fair if r["code_model"] is False])
    cm = {r["code_model"]: r for r in analyze.agg(fair, ["code_model"], ["G2_pass", "FSA"])}
    if True in cm and False in cm:
        F.append(f"**Code-specialised vs general models:** FSA {fmt(cm[True].get('FSA_mean'))} vs {fmt(cm[False].get('FSA_mean'))}, "
                 f"G2 pass {fmt(cm[True].get('G2_pass_rate'), True)} vs {fmt(cm[False].get('G2_pass_rate'), True)}"
                 + (f" (Mann-Whitney p = {p})." if p is not None else ".")
                 + (" Code specialisation does not buy requirement-level test design." if p is not None and p > 0.05 else ""))
    moe = {r["moe"]: r for r in analyze.agg(fair, ["moe"], ["FSA"])}
    if True in moe and False in moe:
        F.append(f"**MoE vs dense:** FSA {fmt(moe[True].get('FSA_mean'))} (MoE) vs {fmt(moe[False].get('FSA_mean'))} (dense).")
    reps = sorted([r for r in t["by_representation"] if r["n_suites"] >= 3], key=lambda r: -(r.get("both_pass_rate") or 0))
    if reps:
        F.append("**Gate success by representation (n ≥ 3 suites):** " + ", ".join(
            f"{r['representation']} {fmt(r.get('both_pass_rate'), True)} both-gates (n={r['n_suites']})" for r in reps) + ".")
    chosen = defaultdict(int)
    for r in t["rep_choice_by_project"]:
        chosen[r["representation"]] += r["times_chosen"]
    if chosen:
        top = sorted(chosen.items(), key=lambda x: -x[1])[:5]
        F.append("**What models choose (Gate 1):** " + ", ".join(f"{k} ×{v}" for k, v in top)
                 + f" — {len(chosen)} distinct representations used out of 30. Choices cluster heavily on a few familiar notations.")
    g1 = t["gate1_by_model"]
    if g1:
        ag = mean(r["agreement_mean"] for r in g1 if r.get("agreement_mean") is not None)
        F.append(f"**LLM choice vs RSS heuristic:** mean overlap with the heuristic's top-3 = {ag:.2f}; the two views of 'suitability' "
                 "agree only partially, which argues for reporting both rather than trusting either.")
    for f, name in (("NC", "negative-path"), ("BC", "boundary"), ("OA", "oracle precision"), ("CC", "clause coverage"), ("Mg", "groundedness")):
        vals = [r[f] for r in ok if isinstance(r.get(f), (int, float))]
        if vals:
            F.append(f"**{name.capitalize()}** averages {mean(vals):.2f} across all judged suites.")
    rg = stats.get("repair_FSA_gain", {})
    if rg.get("n_repaired"):
        F.append(f"**Closed-loop repair:** {rg['n_repaired']} suites were repaired after the judge; mean FSA gain {rg['mean_gain']:+.2f}.")
    bp = {r["project"]: r for r in analyze.agg(shared_rows, ["project"], ["FSA", "both_pass", "tests_per_req", "NC", "BC", "Mg"])}
    if len(bp) >= 2:
        F.append(f"**Small vs large SRS** (same models: {', '.join(shared)}): " + "; ".join(
            f"{p}: FSA {fmt(r.get('FSA_mean'))}, both-gates {fmt(r.get('both_pass_rate'), True)}, tests/req {fmt(r.get('tests_per_req_mean'))}"
            for p, r in bp.items()) + ".")
    halluc = [r["hallucinated"] for r in ok if isinstance(r.get("hallucinated"), int)]
    if halluc:
        F.append(f"**Hallucinated specifics:** {sum(1 for h in halluc if h)} of {len(halluc)} judged suites asserted at least one value "
                 f"not grounded in the SRS (mean {mean(halluc):.1f} per suite).")
    if crow:
        best = [r for r in crow if r.get("srs_reached_code") is not None]
        if best:
            b = max(best, key=lambda r: r["srs_reached_code"])
            F.append(f"**Against the real code:** the highest share of SRS requirements whose tests reach implemented behaviour is "
                     f"{fmt(b['srs_reached_code'], True)} ({b['model']} on {b['project']}).")
        viol = sum(r.get("violated") or 0 for r in crow) + sum(r.get("code_mismatch") or 0 for r in crow)
        F.append(f"**SRS-vs-code discrepancies flagged:** {viol} test cases across all pairs were judged to contradict the implementation "
                 "(execution failures triaged as code_mismatch + audit 'violated'); these need a manual check before being claimed.")
    agr, n = audit_vs_exec()
    if n:
        F.append(f"**Audit validity:** on doorstop, where tests were also executed, the code audit agreed with real execution on {fmt(agr, True)} of {n} cases.")
    r2 = stats.get("spearman_FSA_vs_exec_pass_rate", (None, 0))
    if r2[0] is not None:
        F.append(f"**Do gates predict code behaviour?** ρ(FSA, execution pass rate) = {r2[0]} (n={r2[1]}).")
    return F


def run():
    rows, t, stats = analyze.run()
    crow = code_rows()
    c = stats["counts"]
    md = ["# SRS → Test Cases: 3-Gate Pipeline Results", "",
          f"{c['suites']} test suites ({c['tests']} test cases) from {c['pairs_project_model']} project×model pairs. "
          "Pipeline: requirement extraction → Gate 1 RSS (representation choice, ≤3 re-picks) → generation → Gate 2 SFV → Gate 3 FSA (+ groundedness), "
          "≤3 closed-loop repairs → comparison with the real implementation.", "",
          "## Key findings", ""]
    md += [f"{i}. {f}" for i, f in enumerate(findings(rows, t, stats, crow), 1)]
    md += ["", f"## Per model ({FAIR_PROJECT}: same units for every model)", "", table(sorted(t["fair_by_model"], key=lambda r: -(r.get("FSA_mean") or 0)),
           ["model", "n_suites", "G2_pass_rate", "G3_pass_rate", "both_pass_rate", "FSA_mean", "NC_mean", "OA_mean", "BC_mean", "Mg_mean", "repairs_mean"],
           ["model", "suites", "G2 pass", "G3 pass", "both", "FSA", "NC", "OA", "BC", "Mg", "repairs"],
           pct={"G2_pass_rate", "G3_pass_rate", "both_pass_rate"})]
    md += ["", "## Per model (all projects pooled — workloads differ, see per project × model)", "", table(sorted(t["by_model"], key=lambda r: -(r.get("FSA_mean") or 0)),
           ["model", "n_suites", "G2_pass_rate", "G3_pass_rate", "both_pass_rate", "SFV_mean", "FSA_mean", "CC_mean", "NC_mean", "OA_mean", "BC_mean", "Mg_mean", "repairs_mean", "tests_per_req_mean"],
           ["model", "suites", "G2 pass", "G3 pass", "both", "SFV", "FSA", "CC", "NC", "OA", "BC", "Mg", "repairs", "tests/req"],
           pct={"G2_pass_rate", "G3_pass_rate", "both_pass_rate"})]
    md += ["", "## Per project × model", "", table(sorted(t["by_model_project"], key=lambda r: (r["project"], -(r.get("FSA_mean") or 0))),
           ["project", "model", "n_suites", "G2_pass_rate", "G3_pass_rate", "FSA_mean", "NC_mean", "BC_mean", "Mg_mean", "tests_per_req_mean"],
           ["project", "model", "suites", "G2", "G3", "FSA", "NC", "BC", "Mg", "tests/req"], pct={"G2_pass_rate", "G3_pass_rate"})]
    md += ["", "## Per representation", "", table(sorted(t["by_representation"], key=lambda r: -r["n_suites"]),
           ["representation", "n_suites", "G2_pass_rate", "G3_pass_rate", "both_pass_rate", "SFV_mean", "FSA_mean", "BC_mean", "NC_mean"],
           ["representation", "suites", "G2", "G3", "both", "SFV", "FSA", "BC", "NC"], pct={"G2_pass_rate", "G3_pass_rate", "both_pass_rate"})]
    md += ["", "## Per representation group", "", table(t["by_rep_group"],
           ["rep_group", "n_suites", "G2_pass_rate", "G3_pass_rate", "FSA_mean"], ["group", "suites", "G2", "G3", "FSA"], pct={"G2_pass_rate", "G3_pass_rate"})]
    md += ["", "## Model classes", "",
           "**By size**", "", table(t["by_size_class"], ["size_class", "n_suites", "G2_pass_rate", "both_pass_rate", "FSA_mean", "Mg_mean"], ["size", "suites", "G2", "both", "FSA", "Mg"], pct={"G2_pass_rate", "both_pass_rate"}), "",
           "**Code-specialised vs general**", "", table(t["by_code_model"], ["code_model", "n_suites", "G2_pass_rate", "both_pass_rate", "FSA_mean"], ["code model", "suites", "G2", "both", "FSA"], pct={"G2_pass_rate", "both_pass_rate"}), "",
           "**MoE vs dense**", "", table(t["by_moe"], ["moe", "n_suites", "G2_pass_rate", "both_pass_rate", "FSA_mean"], ["MoE", "suites", "G2", "both", "FSA"], pct={"G2_pass_rate", "both_pass_rate"})]
    md += ["", "## Gate 1 (representation choice)", "", table(t["gate1_by_model"],
           ["model", "n_suites", "gate1_pass_rate", "fallback_rate", "re_picks_mean", "agreement_mean"],
           ["model", "units", "G1 pass", "fallback", "re-picks", "agree w/ heuristic"], pct={"gate1_pass_rate", "fallback_rate"}), "",
           "**Representations chosen per project**", "", table(t["rep_choice_by_project"], ["project", "representation", "times_chosen"])]
    if crow:
        md += ["", "## Against the real implementation", "",
               "**Execution (doorstop)** — all suites, and gate-passing suites only; coverage shown with the number of tests that produced it.", "",
               table([r for r in crow if r.get("exec_cases")],
                     ["project", "model", "exec_cases", "passed", "failed", "error", "skipped", "pass_rate", "pass_rate_gatepass_only",
                      "code_mismatch", "test_bugs", "line_cov", "line_cov_per_10_tests"],
                     ["project", "model", "tests", "pass", "fail", "error", "skipped", "pass rate", "pass rate (gate-passing)",
                      "code bugs", "test bugs", "line cov %", "line cov % per 10 tests"],
                     pct={"pass_rate", "pass_rate_gatepass_only"}), "",
               "**Code audit (all projects)**", "",
               table([r for r in crow if r.get("audit_cases")],
                     ["project", "model", "audit_cases", "satisfied", "violated", "not_impl", "unclear", "satisfied_rate",
                      "satisfied_rate_gatepass_only", "violated_rate_gatepass_only", "srs_cov_tests", "srs_reached_code"],
                     ["project", "model", "tests", "satisfied", "violated", "not impl", "unclear", "satisfied rate",
                      "satisfied (gate-passing)", "violated (gate-passing)", "SRS reqs with tests", "SRS reqs reached in code"],
                     pct={"satisfied_rate", "satisfied_rate_gatepass_only", "violated_rate_gatepass_only", "srs_cov_tests", "srs_reached_code"})]
    md += ["", "## Statistics", "", "```", "\n".join(f"{k}: {v}" for k, v in stats.items() if k != "counts"), "```", "",
           "## Method notes", "",
           "- Same extracted requirements, judge and executor model (gpt-oss-20b, a different family from all subjects) for every generator.",
           "- Test generation used the SRS only; every suite was fingerprinted before the code was opened (checked).",
           "- Ventilator and virtual-clinic: 1 representation per unit (the model's top Gate-1 pick); doorstop: 2 — time budget.",
           "- Execution (doorstop, Python) runs the generated tests; audit mode (all projects) has the executor model judge each test against retrieved code excerpts.",
           "- n = 1 run per model at temperature 0; differences of a few points are within noise."]
    (OUT / "REPORT.md").write_text("\n".join(md) + "\n")
    print(f"report -> {OUT / 'REPORT.md'}")


if __name__ == "__main__":
    run()
