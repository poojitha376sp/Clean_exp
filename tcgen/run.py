"""
python -m tcgen.run --project <name> [--stages S0,S1,S2,S3,S6,S7] [--gen <model spec>]

Stages are resumable: each writes its outputs under runs/<project>/ and later
stages read them, so any stage can be re-run on its own. S3 means the whole
S3->S4->S5 closed loop.

Leakage rule: S0-S5 read ONLY inputs/<p>/srs/. The implementation
(inputs/<p>/code/) is first opened in S6, after every suite is frozen.
"""

import argparse

from . import extract, ingest, represent, suite
from .util import CFG

ALL = ["S0", "S1", "S2", "S3", "S6", "S7"]    # S6A = code audit (language-agnostic), run on request


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--project", required=True)
    ap.add_argument("--stages", default=",".join(ALL))
    ap.add_argument("--gen", action="append", help="generator model spec (default: all in config)")
    ap.add_argument("--units", help="comma-separated unit ids to restrict to (smoke tests)")
    ap.add_argument("--judge", help="override models.judge for this run")
    ap.add_argument("--executor", help="override models.executor for this run")
    a = ap.parse_args()
    if a.judge:
        CFG["models"]["judge"] = a.judge
    if a.executor:
        CFG["models"]["executor"] = a.executor
    stages = [s.strip().upper() for s in a.stages.split(",")]
    gens = a.gen or CFG["models"]["generators"]

    if "S0" in stages:
        ingest.run(a.project)
    if "S1" in stages:
        extract.run(a.project)
    units = extract.load_units(a.project) if {"S2", "S3"} & set(stages) else []
    if a.units:
        keep = set(a.units.split(","))
        units = [u for u in units if u["unit_id"] in keep]

    for gen in gens:
        print(f"\n=== generator {gen} ===")
        if "S2" in stages:
            represent.run(a.project, gen, units)
        if "S3" in stages:
            suite.run(a.project, gen, units, represent.load(a.project, gen))
    if "S6" in stages:                       # only after ALL generators finished S0-S5
        from . import execute
        for gen in gens:
            execute.run(a.project, gen)
    if "S6A" in stages:
        from . import audit
        for gen in gens:
            audit.run(a.project, gen)
    if "S7" in stages:
        from . import report
        report.run(a.project, gens)


if __name__ == "__main__":
    main()
