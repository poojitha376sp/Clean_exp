#!/usr/bin/env python3
"""Check the paper's claim that design-document thresholds (SFV >= 0.80) make
more than 70% of suites fail Gate 2 in a 20-unit pilot.

The original pilot logs are not in the repo, so this reproduces the claim as
closely as the committed data allows:
  * final-run Gate 2 failure, implemented vs. design-doc SFV threshold;
  * first-attempt (pre-repair) failure, which is closest to a pilot that ran
    before the repair loop existed;
  * failure rate over random 20-unit samples, to see whether > 70% is reachable.

Usage:  python3 -B tools/verify_threshold_claim.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from tcgen.gates.config import SFV_THRESHOLD_BY_GROUP, get_group  # noqa: E402

DESIGN_SFV, CLAIM, N_UNITS, DRAWS = 0.80, 0.70, 20, 10000

s = pd.read_csv(ROOT / "runs/ANALYSIS/suites.csv")
s["uid"] = s.project + "/" + s.unit.astype(str)
s["impl_thr"] = s.representation.map(lambda r: SFV_THRESHOLD_BY_GROUP.get(get_group(r), 0.6))


def pct(x):
    return f"{100 * x:.1f}%"


print(f"suites: {len(s)}, distinct units: {s.uid.nunique()}\n")
print("Gate 2 failure rate")
print(f"  final run, implemented thresholds (G2_pass false):   {pct((s.G2_pass != True).mean())}")
print(f"  final run, design-doc SFV >= {DESIGN_SFV}:                  {pct((s.SFV < DESIGN_SFV).mean())}")
print(f"  first attempt, SFV >= {DESIGN_SFV} (pre-repair):            {pct((s.first_SFV < DESIGN_SFV).mean())}")
print(f"  first attempt, group thresholds (approx., pre-repair): {pct((s.first_SFV < s.impl_thr).mean())}")
print("\nBy project, first attempt, SFV >= 0.80:")
print((s.first_SFV < DESIGN_SFV).groupby(s.project).mean().map(pct).to_string())

rng = np.random.default_rng(0)
units = s.uid.unique()
byu = {u: d for u, d in s.groupby("uid")}
rates = {"final": [], "first": []}
for _ in range(DRAWS):
    pick = rng.choice(units, size=N_UNITS, replace=False)
    d = pd.concat([byu[u] for u in pick])
    rates["final"].append((d.SFV < DESIGN_SFV).mean())
    rates["first"].append((d.first_SFV < DESIGN_SFV).mean())
print(f"\nRandom {N_UNITS}-unit samples ({DRAWS} draws), failure rate at SFV >= {DESIGN_SFV}:")
for k, lab in (("final", "final run"), ("first", "first attempt")):
    r = np.array(rates[k])
    print(f"  {lab:14s} min {pct(r.min())}  median {pct(np.median(r))}  max {pct(r.max())}  "
          f"share of draws > {pct(CLAIM)}: {pct((r > CLAIM).mean())}")

print("\nVerdict:",
      "claim reproducible" if np.max(rates["first"]) > CLAIM and np.mean(np.array(rates['first']) > CLAIM) > 0.05
      else f"claim NOT reproduced: > {pct(CLAIM)} failing at Gate 2 is not reached in the committed data")
