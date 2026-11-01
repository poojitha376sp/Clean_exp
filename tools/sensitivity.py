#!/usr/bin/env python3
"""Weight-sensitivity check for Gate 1 (RSS) and Gate 3 (FSA).

Perturbs each weight of the active profile by +/-0.05 (the other weights are
rescaled proportionally so the profile still sums to 1) and reports how much
the outcomes move. Reads only committed data; writes runs/ANALYSIS/sensitivity.json.

Usage:  python3 -B tools/sensitivity.py
"""
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import kendalltau

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from tcgen.gates.config import (CATALOG, RSS_WEIGHT_PROFILES, get_fsa_weights,  # noqa: E402
                                infer_system_type)
from tcgen.gates.rss import evaluate_rss  # noqa: E402

DELTA = 0.05
FSA_COMP = {"wc": "CC", "wn": "NC", "wo": "OA", "wb": "BC", "wg": "Mg"}
FSA_THR, RSS_THR = 0.5, 0.6


def perturb(w, key, d):
    """Move w[key] by d; rescale the others proportionally so the sum stays 1."""
    new = min(max(w[key] + d, 0.0), 1.0)
    rest = sum(v for k, v in w.items() if k != key)
    if rest <= 0:
        return dict(w)
    return {k: (new if k == key else v * (1 - new) / rest) for k, v in w.items()}


def order(df, col, by):
    return list(df.groupby(by)[col].mean().sort_values(ascending=False).index)


def fsa_check():
    s = pd.read_csv(ROOT / "runs/ANALYSIS/suites.csv")
    j = s[s.FSA.notna()].copy()

    def score(row, w):
        return sum(w[k] * row[c] for k, c in FSA_COMP.items())

    j["base"] = [score(r, get_fsa_weights(r.representation, r.system_type)) for _, r in j.iterrows()]
    recompute_err = float((j.base - j.FSA).abs().max())
    groupings = {"paradigm": "rep_group", "representation": "representation"}
    base_orders = {g: order(j, "base", c) for g, c in groupings.items()}
    door = j[j.project == "doorstop"]
    base_model = order(door, "base", "model")

    flips = n_dec = 0
    changed = {g: 0 for g in groupings}
    changed["model_doorstop"] = 0
    tau_par, max_disp = [], []
    n_pert = 0
    for key in FSA_COMP:
        for d in (-DELTA, DELTA):
            j["p"] = [score(r, perturb(get_fsa_weights(r.representation, r.system_type), key, d))
                      for _, r in j.iterrows()]
            flips += int(((j.base >= FSA_THR) != (j.p >= FSA_THR)).sum())
            n_dec += len(j)
            for g, c in groupings.items():
                o = order(j, "p", c)
                changed[g] += o != base_orders[g]
                if g == "paradigm":
                    b = base_orders[g]
                    tau_par.append(float(kendalltau([b.index(x) for x in o], range(len(o)))[0]))
                    max_disp.append(max(abs(b.index(x) - o.index(x)) for x in b))
            changed["model_doorstop"] += order(j[j.project == "doorstop"], "p", "model") != base_model
            n_pert += 1
    return {
        "n_suites": len(j), "n_perturbations": n_pert, "recompute_max_abs_err": recompute_err,
        "pass_fail_flips": flips, "pass_fail_decisions": n_dec,
        "pass_fail_flip_pct": round(100 * flips / n_dec, 2),
        "orders_changed_of_perturbations": {k: int(v) for k, v in changed.items()},
        "paradigm_baseline_order": base_orders["paradigm"],
        "paradigm_kendall_tau_vs_baseline_min": round(min(tau_par), 3),
        "paradigm_max_rank_displacement_max": int(max(max_disp)),
    }


def rss_check():
    units = []
    for p in ("doorstop", "ventilator", "virtual_clinic"):
        for u in json.load(open(ROOT / f"runs/{p}/S1_units.json")):
            units.append("\n".join(f"[{r['id']}] ({r.get('kind', '?')}) {r['text']}" for r in u["reqs"]))
    reps = list(CATALOG)

    def scores(text, st, key=None, d=0.0):
        out = {}
        for r in reps:
            e = evaluate_rss(text, r, system_type=st)
            w = RSS_WEIGHT_PROFILES[st] if key is None else perturb(RSS_WEIGHT_PROFILES[st], key, d)
            out[r] = sum(w[m] * e["metrics"][m] for m in w)
        return out

    from tcgen.gates.config import get_group
    groups = sorted({get_group(r) for r in reps})

    def par_scores(sc, agg):
        return {g: agg([sc[r] for r in reps if get_group(r) == g]) for g in groups}

    def par_order(sc, agg):
        ps = par_scores(sc, agg)
        return sorted(ps, key=lambda g: (-ps[g], g))

    top1 = top3 = flips = cases = 0
    par = {a: {"full_order_changed": 0, "top_paradigm_changed": 0, "tau": []} for a in ("max", "mean")}
    aggs = {"max": max, "mean": np.mean}
    for text in units:
        st = infer_system_type(text)
        base = scores(text, st)
        bo = sorted(base, key=lambda r: -base[r])
        base_par = {a: par_order(base, f) for a, f in aggs.items()}
        for key, wt in RSS_WEIGHT_PROFILES[st].items():
            if wt == 0:
                continue
            for d in (-DELTA, DELTA):
                sc = scores(text, st, key, d)
                o = sorted(sc, key=lambda r: -sc[r])
                cases += 1
                top1 += o[0] != bo[0]
                top3 += set(o[:3]) != set(bo[:3])
                for a, f in aggs.items():
                    po = par_order(sc, f)
                    par[a]["full_order_changed"] += po != base_par[a]
                    par[a]["top_paradigm_changed"] += po[0] != base_par[a][0]
                    par[a]["tau"].append(float(kendalltau([base_par[a].index(g) for g in po],
                                                          range(len(po)))[0]))
                flips += sum((base[r] >= RSS_THR) != (sc[r] >= RSS_THR) for r in reps)
    return {
        "n_units": len(units), "n_unit_perturbation_cases": cases,
        "top1_changed": int(top1), "top1_changed_pct": round(100 * top1 / cases, 2),
        "top3_set_changed": int(top3), "top3_set_changed_pct": round(100 * top3 / cases, 2),
        "paradigm_ranking_per_unit": {a: {
            "full_order_changed": int(v["full_order_changed"]),
            "full_order_changed_pct": round(100 * v["full_order_changed"] / cases, 2),
            "top_paradigm_changed": int(v["top_paradigm_changed"]),
            "top_paradigm_changed_pct": round(100 * v["top_paradigm_changed"] / cases, 2),
            "kendall_tau_mean": round(float(np.mean(v["tau"])), 3),
            "kendall_tau_min": round(float(np.min(v["tau"])), 3)} for a, v in par.items()},
        "rep_pass_fail_flips": int(flips), "rep_pass_fail_decisions": cases * len(reps),
        "rep_pass_fail_flip_pct": round(100 * flips / (cases * len(reps)), 2),
    }


if __name__ == "__main__":
    res = {"delta": DELTA, "gate3_fsa": fsa_check(), "gate1_rss": rss_check()}
    out = ROOT / "runs/ANALYSIS/sensitivity.json"
    out.write_text(json.dumps(res, indent=2))
    print(json.dumps(res, indent=2))
    print(f"\nwritten: {out.relative_to(ROOT)}")
