#!/usr/bin/env python3
"""Figures for the 3-gate measurement-validity paper, built directly from
runs/ANALYSIS/suites.csv so every chart traces to the same source as the
tables. Every figure is sized at (or very close to) the physical width it
will actually be displayed at in the compiled PDF (IEEEtran two-column
textwidth = 7.16in), so point sizes chosen here are the point sizes that
show up on a printed page, not shrunk by a later rescale."""
import csv
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(HERE, "..", "..", "runs", "ANALYSIS", "suites.csv")

TEXTWIDTH = 7.16   # IEEEtran conference, two-column, US letter

INK = "#1A2733"
NAVY = "#0E2A47"
TEAL = "#356170"
GOLD = "#B5842A"
MUTE = "#6B7580"
GRID = "#E3E3E3"
plt.rcParams.update({
    "font.family": "DejaVu Serif",
    "axes.edgecolor": "#888888",
    "axes.linewidth": 0.9,
})

rows = []
with open(CSV, newline="") as f:
    for r in csv.DictReader(f):
        rows.append(r)


def fnum(x):
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


# ---------------------------------------------------------------- fig 1: FSA by model (pooled), full width
model_fsa = {}
for r in rows:
    fsa = fnum(r["FSA"])
    if fsa is None:
        continue
    model_fsa.setdefault(r["model"], []).append(fsa)

order = sorted(model_fsa, key=lambda m: sum(model_fsa[m]) / len(model_fsa[m]), reverse=True)
means = [sum(model_fsa[m]) / len(model_fsa[m]) for m in order]
counts = [len(model_fsa[m]) for m in order]

fig, ax = plt.subplots(figsize=(TEXTWIDTH, 3.1))
bars = ax.barh(range(len(order)), means[::-1], color=TEAL, height=0.6, zorder=3)
ax.set_yticks(range(len(order)))
ax.set_yticklabels(
    [f"{m}  (n={n})" for m, n in zip(order[::-1], counts[::-1])],
    fontsize=10.5, family="DejaVu Sans")
ax.set_xlabel("mean FSA (pooled across the three case studies)", fontsize=10.5, family="DejaVu Sans")
ax.set_xlim(0, 0.85)
ax.axvline(0.5, color=GOLD, lw=1.6, ls="--", zorder=2)
ax.text(0.508, len(order) - 0.3, "FSA pass threshold = 0.50", fontsize=9.5, color=GOLD,
        family="DejaVu Sans", va="top")
ax.grid(axis="x", color=GRID, lw=0.7, zorder=0)
for i, v in enumerate(means[::-1]):
    ax.text(v + 0.012, i, f"{v:.2f}", va="center", fontsize=10, family="DejaVu Sans", color=INK)
ax.tick_params(length=0, labelsize=10.5)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
fig.tight_layout(pad=0.5)
fig.savefig(os.path.join(HERE, "fsa_by_model.pdf"))
plt.close(fig)

# ---------------------------------------------------------------- fig 2: FSA / both-pass by representation group, full width
group_fsa = {}
group_both = {}
for r in rows:
    g = r["rep_group"]
    fsa = fnum(r["FSA"])
    if fsa is not None:
        group_fsa.setdefault(g, []).append(fsa)
    group_both.setdefault(g, []).append(1.0 if r["both_pass"] == "True" else 0.0)

groups = sorted(group_fsa, key=lambda g: sum(group_fsa[g]) / len(group_fsa[g]), reverse=True)
fsa_means = [sum(group_fsa[g]) / len(group_fsa[g]) for g in groups]
both_means = [sum(group_both[g]) / len(group_both[g]) for g in groups]

fig, ax = plt.subplots(figsize=(TEXTWIDTH, 3.2))
x = range(len(groups))
w = 0.34
ax.bar([i - w / 2 for i in x], fsa_means, width=w, color=TEAL, label="mean FSA", zorder=3)
ax.bar([i + w / 2 for i in x], both_means, width=w, color=GOLD, label="both-gates pass rate", zorder=3)
ax.set_xticks(list(x))
ax.set_xticklabels(groups, fontsize=10, family="DejaVu Sans", rotation=12, ha="right")
ax.margins(x=0.03)
ax.set_ylim(0, 1.0)
ax.grid(axis="y", color=GRID, lw=0.7, zorder=0)
ax.legend(fontsize=10, frameon=False, loc="upper right")
ax.tick_params(length=0, labelsize=10.5)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
fig.tight_layout(pad=0.5)
fig.savefig(os.path.join(HERE, "fsa_by_repr_group.pdf"))
plt.close(fig)
print("wrote fsa_by_model.pdf, fsa_by_repr_group.pdf")
