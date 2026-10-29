"""
Cross-project analysis: every (project x model x unit x representation)
suite in one table, plus the aggregates and statistical tests the final
write-up needs.

    python -m tcgen.analyze                 -> runs/ANALYSIS/{suites.csv, *.csv, analysis.json}
"""

import json
import math
from collections import defaultdict
from statistics import mean, median, pstdev

from . import represent, suite
from .gates.config import get_group
from .util import CFG, ROOT, read_json, run_dir, slug, write_json

# Facts about the subject models (from the model cards), used to group results.
MODEL_META = {
    "phi3.5:3.8b":            {"name": "Phi-3.5-mini",            "params_b": 3.8,  "active_b": 3.8, "family": "Phi",      "code": False, "moe": False},
    "qwen2.5-coder:7b":       {"name": "Qwen2.5-Coder-7B",        "params_b": 7.6,  "active_b": 7.6, "family": "Qwen",     "code": True,  "moe": False},
    "codegemma:7b":           {"name": "CodeGemma-7B",            "params_b": 8.5,  "active_b": 8.5, "family": "Gemma",    "code": True,  "moe": False},
    "llama3.1:8b":            {"name": "Llama-3.1-8B",            "params_b": 8.0,  "active_b": 8.0, "family": "Llama",    "code": False, "moe": False},
    "granite4.1:8b":          {"name": "Granite-4.1-8B",          "params_b": 8.0,  "active_b": 8.0, "family": "Granite",  "code": False, "moe": False},
    "phi4:14b":               {"name": "Phi-4-14B",               "params_b": 14.7, "active_b": 14.7, "family": "Phi",     "code": False, "moe": False},
    "deepseek-coder-v2:16b":  {"name": "DeepSeek-Coder-V2-Lite",  "params_b": 15.7, "active_b": 2.4, "family": "DeepSeek", "code": True,  "moe": True},
    "gemma3:27b":             {"name": "Gemma-3-27B",             "params_b": 27.0, "active_b": 27.0, "family": "Gemma",   "code": False, "moe": False},
    "qwen3:30b-a3b":          {"name": "Qwen3-30B-A3B",           "params_b": 30.5, "active_b": 3.3, "family": "Qwen",     "code": False, "moe": True},
    "qwen2.5-coder:32b":      {"name": "Qwen2.5-Coder-32B",       "params_b": 32.8, "active_b": 32.8, "family": "Qwen",    "code": True,  "moe": False},
    "llama3.3:70b":           {"name": "Llama-3.3-70B",           "params_b": 70.6, "active_b": 70.6, "family": "Llama",   "code": False, "moe": False},
    "granite4.1:8b":          {"name": "Granite-4.1-8B",          "params_b": 8.0,  "active_b": 8.0, "family": "Granite",  "code": False, "moe": False},
    "hf.co/bartowski/Phi-3.5-MoE-instruct-GGUF:Q4_K_M": {"name": "Phi-3.5-MoE", "params_b": 41.9, "active_b": 6.6, "family": "Phi", "code": False, "moe": True},
    "hf.co/bartowski/phi-4-GGUF:Q4_K_M": {"name": "Phi-4-14B", "params_b": 14.7, "active_b": 14.7, "family": "Phi", "code": False, "moe": False},
}
GROUP_NAMES = {1: "Scenario/Behavioral", 2: "Stateful/Transitions", 3: "Concurrency/Interaction",
               4: "Logical/Rules", 5: "Programmatic/Code", 6: "Math/Symbolic/Contracts"}
PROJECTS = ["doorstop", "ventilator", "virtual_clinic"]


def meta(gen):
    return MODEL_META.get(gen.split(":", 1)[1], {"name": gen, "params_b": None, "active_b": None,
                                                  "family": "?", "code": None, "moe": None})


def size_class(p):
    if p is None:
        return "?"
    return "small (<10B)" if p < 10 else ("medium (10-20B)" if p < 20 else "large (>20B)")


def suite_rows():
    rows, g1_rows = [], []
    for proj in PROJECTS:
        rd = run_dir(proj)
        if not (rd / "S1_units.json").exists():
            continue
        units = {u["unit_id"]: u for u in read_json(rd / "S1_units.json")}
        for gen in CFG["models"].get("plan", {}).get(proj, CFG["models"]["generators"]):
            m = meta(gen)
            try:
                s2 = represent.load(proj, gen)
            except FileNotFoundError:
                continue
            for r in s2:
                g1_rows.append({"project": proj, "model": m["name"], "unit": r["unit_id"], "gate1_pass": r["gate1_pass"],
                                "fallback": r["fallback_below_threshold"], "re_picks": r["repair_rounds"],
                                "agreement": r["agreement_with_heuristic_top3"], "chosen": r["chosen"],
                                "system_type": r["system_type"]})
            ex = {}
            exp = rd / slug(gen) / "S6_execution_gated.json"
            if exp.exists():
                for c in read_json(exp)["cases"]:
                    ex.setdefault(c["suite"], []).append(c)
            for s in suite.load_all(proj, gen):
                fsa, sfv = s.get("fsa") or {}, s.get("sfv") or {}
                cases = s.get("test_cases") or []
                kinds = defaultdict(int)
                for c in cases:
                    if isinstance(c, dict):
                        kinds[c.get("kind", "?")] += 1
                u = units.get(s["unit_id"], {})
                row = {
                    "project": proj, "model": m["name"], "model_spec": gen, "params_b": m["params_b"],
                    "active_b": m["active_b"], "size_class": size_class(m["params_b"]), "family": m["family"],
                    "code_model": m["code"], "moe": m["moe"],
                    "unit": s["unit_id"], "unit_reqs": len(u.get("req_ids", [])),
                    "representation": s["representation"], "rep_group": GROUP_NAMES.get(get_group(s["representation"])),
                    "system_type": s.get("system_type"),
                    "error": s.get("error"), "attempts": s.get("n_attempts"), "repairs": s.get("repairs_used"),
                    "G2_pass": s.get("gate2_pass"), "G3_pass": s.get("gate3_pass"),
                    "both_pass": bool(s.get("gate2_pass") and s.get("gate3_pass")),
                    "SFV": sfv.get("sfv_score"), "SFV_schema": sfv.get("schema_score"), "SFV_repr": sfv.get("representation_score"),
                    "FSA": fsa.get("fsa_score"), "CC": fsa.get("clause_coverage"), "NC": fsa.get("negative_coverage"),
                    "OA": fsa.get("oracle_assertiveness"), "BC": fsa.get("boundary_coverage"), "Mg": fsa.get("groundedness_mg"),
                    "traceability": fsa.get("traceability"), "hallucinated": len(fsa.get("hallucinated") or []),
                    "concrete_elements": fsa.get("n_concrete_elements"),
                    "n_tests": len(cases), "tests_per_req": round(len(cases) / max(1, len(u.get("req_ids", []))), 2),
                    "n_positive": kinds["positive"], "n_negative": kinds["negative"], "n_boundary": kinds["boundary"],
                    # did repairs help? first-attempt vs final
                    "first_SFV": (s.get("attempts") or [{}])[0].get("sfv", {}).get("sfv_score") if s.get("attempts") else None,
                    "first_FSA": next((a.get("fsa", {}).get("fsa_score") for a in s.get("attempts") or [] if a.get("fsa")), None),
                }
                cs = ex.get(f"{s['unit_id']}/{s['representation']}", [])
                if cs:
                    st = defaultdict(int)
                    for c in cs:
                        st[c["status"]] += 1
                    execd = st["passed"] + st["failed"]
                    row.update({"exec_cases": len(cs), "exec_passed": st["passed"], "exec_failed": st["failed"],
                                "exec_error": st["error"], "exec_skipped": st["skipped"],
                                "exec_rate": round((execd + st["error"]) / len(cs), 3),
                                "exec_pass_rate": round(st["passed"] / execd, 3) if execd else None,
                                "code_mismatch": sum(1 for c in cs if (c.get("triage") or {}).get("verdict") == "code_mismatch"),
                                "test_bug": sum(1 for c in cs if (c.get("triage") or {}).get("verdict") == "test_bug")})
                rows.append(row)
    return rows, g1_rows


def agg(rows, key, fields):
    groups = defaultdict(list)
    for r in rows:
        k = tuple(r[x] for x in key) if isinstance(key, (list, tuple)) else r[key]
        groups[k].append(r)
    out = []
    for k, rs in groups.items():
        d = dict(zip(key, k)) if isinstance(key, (list, tuple)) else {key: k}
        d["n_suites"] = len(rs)
        for f in fields:
            vals = [r[f] for r in rs if isinstance(r.get(f), (int, float)) and not isinstance(r.get(f), bool)]
            bools = [r[f] for r in rs if isinstance(r.get(f), bool)]
            if bools and not vals:
                d[f + "_rate"] = round(sum(bools) / len(bools), 3)
            elif vals:
                d[f + "_mean"] = round(mean(vals), 3)
        out.append(d)
    return out


def spearman(xs, ys):
    pairs = [(x, y) for x, y in zip(xs, ys) if isinstance(x, (int, float)) and isinstance(y, (int, float))]
    n = len(pairs)
    if n < 4:
        return None, n

    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(v):
            j = i
            while j + 1 < len(v) and v[order[j + 1]] == v[order[i]]:
                j += 1
            for k in range(i, j + 1):
                r[order[k]] = (i + j) / 2 + 1
            i = j + 1
        return r
    rx, ry = ranks([p[0] for p in pairs]), ranks([p[1] for p in pairs])
    mx, my = mean(rx), mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return (round(num / den, 3) if den else None), n


def mann_whitney(a, b):
    """Two-sided Mann-Whitney U with normal approximation -> (U, p)."""
    a = [x for x in a if isinstance(x, (int, float))]
    b = [x for x in b if isinstance(x, (int, float))]
    if len(a) < 3 or len(b) < 3:
        return None, None
    allv = sorted([(v, 0) for v in a] + [(v, 1) for v in b])
    ranks, i = {}, 0
    vals = [v for v, _ in allv]
    rk = [0.0] * len(vals)
    while i < len(vals):
        j = i
        while j + 1 < len(vals) and vals[j + 1] == vals[i]:
            j += 1
        for k in range(i, j + 1):
            rk[k] = (i + j) / 2 + 1
        i = j + 1
    ra = sum(r for r, (_, g) in zip(rk, allv) if g == 0)
    n1, n2 = len(a), len(b)
    u = ra - n1 * (n1 + 1) / 2
    mu, sigma = n1 * n2 / 2, math.sqrt(n1 * n2 * (n1 + n2 + 1) / 12)
    z = (u - mu) / sigma if sigma else 0
    p = math.erfc(abs(z) / math.sqrt(2))
    return round(u, 1), round(p, 4)


def write_csv(path, rows):
    import csv
    if not rows:
        return
    keys = list(dict.fromkeys(k for r in rows for k in r))
    with open(path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=keys)
        w.writeheader()
        w.writerows(rows)


def run():
    out = ROOT / CFG["paths"]["runs_dir"] / "ANALYSIS"
    out.mkdir(parents=True, exist_ok=True)
    rows, g1 = suite_rows()
    ok = [r for r in rows if not r["error"]]
    F = ["G2_pass", "G3_pass", "both_pass", "SFV", "FSA", "CC", "NC", "OA", "BC", "Mg", "traceability",
         "hallucinated", "repairs", "n_tests", "tests_per_req", "exec_rate", "exec_pass_rate", "code_mismatch"]
    tables = {
        "by_model": agg(ok, ["model"], F),
        "by_project": agg(ok, ["project"], F),
        "by_model_project": agg(ok, ["project", "model"], F),
        "by_representation": agg(ok, ["representation"], F),
        "by_rep_group": agg(ok, ["rep_group"], F),
        "by_size_class": agg(ok, ["size_class"], F),
        "by_code_model": agg(ok, ["code_model"], F),
        "by_moe": agg(ok, ["moe"], F),
        "by_family": agg(ok, ["family"], F),
        "by_system_type": agg(ok, ["system_type"], F),
        "gate1_by_model": agg(g1, ["model"], ["gate1_pass", "fallback", "re_picks", "agreement"]),
        "gate1_by_project": agg(g1, ["project"], ["gate1_pass", "fallback", "re_picks", "agreement"]),
    }
    rep_choice = defaultdict(lambda: defaultdict(int))
    for r in g1:
        for rep in r["chosen"]:
            rep_choice[r["project"]][rep] += 1
    tables["rep_choice_by_project"] = [{"project": p, "representation": rep, "times_chosen": n}
                                       for p, d in rep_choice.items() for rep, n in sorted(d.items(), key=lambda x: -x[1])]
    for name, t in tables.items():
        write_csv(out / f"{name}.csv", t)
    write_csv(out / "suites.csv", rows)
    write_csv(out / "gate1_units.csv", g1)

    stats = {}
    for f in ("FSA", "CC", "NC", "BC", "OA", "Mg", "SFV", "n_tests", "repairs"):
        stats[f"spearman_params_vs_{f}"] = spearman([r["params_b"] for r in ok], [r[f] for r in ok])
        stats[f"spearman_active_params_vs_{f}"] = spearman([r["active_b"] for r in ok], [r[f] for r in ok])
    stats["spearman_FSA_vs_exec_pass_rate"] = spearman([r["FSA"] for r in ok], [r.get("exec_pass_rate") for r in ok])
    stats["spearman_FSA_vs_code_mismatch"] = spearman([r["FSA"] for r in ok], [r.get("code_mismatch") for r in ok])
    stats["spearman_unit_size_vs_FSA"] = spearman([r["unit_reqs"] for r in ok], [r["FSA"] for r in ok])
    stats["mw_code_vs_general_FSA"] = mann_whitney([r["FSA"] for r in ok if r["code_model"]], [r["FSA"] for r in ok if r["code_model"] is False])
    stats["mw_code_vs_general_SFV"] = mann_whitney([r["SFV"] for r in ok if r["code_model"]], [r["SFV"] for r in ok if r["code_model"] is False])
    stats["mw_small_vs_large_FSA"] = mann_whitney([r["FSA"] for r in ok if r["size_class"] == "small (<10B)"],
                                                  [r["FSA"] for r in ok if r["size_class"] == "large (>20B)"])
    stats["mw_doorstop_vs_ventilator_FSA"] = mann_whitney([r["FSA"] for r in ok if r["project"] == "doorstop"],
                                                          [r["FSA"] for r in ok if r["project"] == "ventilator"])
    rep_gain = [(r["FSA"] - r["first_FSA"]) for r in ok if isinstance(r["FSA"], float) and isinstance(r["first_FSA"], float) and r["repairs"]]
    stats["repair_FSA_gain"] = {"n_repaired": len(rep_gain), "mean_gain": round(mean(rep_gain), 3) if rep_gain else None}
    stats["counts"] = {"suites": len(rows), "suites_ok": len(ok), "errors": len(rows) - len(ok),
                       "tests": sum(r["n_tests"] for r in ok),
                       "pairs_project_model": len({(r["project"], r["model"]) for r in ok})}
    write_json(out / "analysis.json", {"stats": stats, "tables": tables})
    print(json.dumps(stats, indent=1)[:3000])
    return rows, tables, stats


if __name__ == "__main__":
    run()
