"""
S2 -- Gate 1 (RSS): the generator picks representations per unit; each pick is
scored by the ported heuristic RSS (m1-m10, weights by inferred system type).
Picks below the threshold are rejected and fed back for a new pick
(<= max_repairs rounds). We also record the heuristic's own top-3 over all 30
representations and report the overlap with the LLM's picks (agreement).
"""

from . import llm
from .gates.config import CATALOG, canonical_rep, infer_system_type
from .gates.rss import evaluate_rss
from .util import CFG, PROMPTS, prompt, slug, write_json, read_json, run_dir

REPS_COMPACT = (PROMPTS / "reps_compact.txt").read_text()


def fmt_reqs(reqs):
    return "\n".join(f"[{r['id']}] ({r.get('kind', '?')}) {r['text']}" for r in reqs) or "(none)"


def unit_text(unit):
    return fmt_reqs(unit["reqs"])


def run_unit(unit, gen, project=None):
    k = CFG["pipeline"].get("reps_per_unit_by_project", {}).get(project, CFG["pipeline"]["reps_per_unit"])
    text = unit_text(unit)
    system_type = infer_system_type(text)
    thr = CFG["gates"]["rss_threshold"]
    heuristic = sorted(((evaluate_rss(text, r, system_type=system_type)["rss_score"], r) for r in CATALOG), reverse=True)
    rejected, accepted, rounds = {}, [], []
    feedback = ""
    for rnd in range(CFG["pipeline"]["max_repairs"] + 1):
        p = prompt("select_reps", UNIT=unit["unit_id"], SECTION=unit["section"], REQS=text,
                   DEPS=fmt_reqs(unit["deps"]), CATALOG=REPS_COMPACT, K=str(k + 1), FEEDBACK=feedback)
        try:
            raw = llm.call(gen, p, stage="S2_rss")
        except llm.LLMError as e:
            rounds.append({"round": rnd, "error": str(e)})
            break
        parsed = llm.extract_json(raw)
        picks = parsed.get("selected", []) if isinstance(parsed, dict) else []
        rec = {"round": rnd, "picks": []}
        for pk in picks:
            name = canonical_rep(str(pk.get("representation", "")))
            if name is None:
                rejected[str(pk.get("representation"))] = "not an exact catalog name"
                rec["picks"].append({"raw": pk.get("representation"), "valid_name": False})
                continue
            if name in accepted or name in rejected:
                continue
            r = evaluate_rss(text, name, system_type=system_type)
            rec["picks"].append({"representation": name, "rss": r["rss_score"], "pass": r["rss_pass"],
                                 "metrics": r["metrics"], "reason": pk.get("reason")})
            if r["rss_pass"]:
                accepted.append(name)
            else:
                rejected[name] = f"RSS {r['rss_score']} < {thr} (metrics {r['metrics']})"
        rounds.append(rec)
        if len(accepted) >= k:
            break
        feedback = ("\nPREVIOUS PICKS REJECTED BY THE RSS GATE -- choose different representations:\n" +
                    "\n".join(f"- {n}: {why}" for n, why in rejected.items()) + "\n")
    chosen = accepted[:k]
    fallback = False
    if not chosen:  # nothing passed: keep the best-scoring valid pick so the unit still gets tests, flagged
        scored = [(p["rss"], p["representation"]) for r in rounds for p in r.get("picks", []) if "rss" in p]
        if scored:
            chosen, fallback = [max(scored)[1]], True
    heur_top = [r for _, r in heuristic[:3]]
    return {
        "unit_id": unit["unit_id"], "generator": gen, "system_type": system_type,
        "chosen": chosen, "gate1_pass": bool(chosen) and not fallback, "fallback_below_threshold": fallback,
        "repair_rounds": len(rounds) - 1, "rounds": rounds, "rejected": rejected,
        "heuristic_top3": [{"representation": r, "rss": s} for s, r in heuristic[:3]],
        "agreement_with_heuristic_top3": round(len(set(chosen) & set(heur_top)) / max(1, len(chosen)), 3),
    }


def run(project, gen, units):
    """Units are independent, so they're sent to the GPU concurrently
    (pipeline.workers); results are written in unit order."""
    from concurrent.futures import ThreadPoolExecutor
    out = run_dir(project) / slug(gen) / "S2_representations.json"
    with ThreadPoolExecutor(CFG["pipeline"].get("workers", 1)) as ex:
        results = list(ex.map(lambda u: run_unit(u, gen, project), units))
    for r in results:
        print(f"  S2 [{gen}] {r['unit_id']}: {r['chosen']} (gate1_pass={r['gate1_pass']}, re-picks={r['repair_rounds']})")
    write_json(out, results)
    return results


def load(project, gen):
    return read_json(run_dir(project) / slug(gen) / "S2_representations.json")
