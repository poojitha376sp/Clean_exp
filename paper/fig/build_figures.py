#!/usr/bin/env python3
"""Figures for the 3-gate measurement-validity paper, built directly from
runs/ANALYSIS/suites.csv so every chart traces to the same source as the tables."""
import csv
import os
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch

HERE = os.path.dirname(os.path.abspath(__file__))
CSV = os.path.join(HERE, "..", "..", "runs", "ANALYSIS", "suites.csv")

INK = "#1A2733"
NAVY = "#0E2A47"
TEAL = "#356170"
GOLD = "#B5842A"
MUTE = "#6B7580"
GRID = "#E3E3E3"
plt.rcParams.update({
    "font.family": "DejaVu Serif",
    "axes.edgecolor": "#888888",
    "axes.linewidth": 0.8,
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


# ---------------------------------------------------------------- fig 1: FSA by model (pooled)
model_fsa = {}
for r in rows:
    fsa = fnum(r["FSA"])
    if fsa is None:
        continue
    model_fsa.setdefault(r["model"], []).append(fsa)

order = sorted(model_fsa, key=lambda m: sum(model_fsa[m]) / len(model_fsa[m]), reverse=True)
means = [sum(model_fsa[m]) / len(model_fsa[m]) for m in order]

fig, ax = plt.subplots(figsize=(3.4, 2.6))
bars = ax.barh(range(len(order)), means[::-1], color=TEAL, height=0.62, zorder=3)
ax.set_yticks(range(len(order)))
ax.set_yticklabels(order[::-1], fontsize=7, family="DejaVu Sans")
ax.set_xlabel("mean FSA (pooled across projects)", fontsize=7.5, family="DejaVu Sans")
ax.set_xlim(0, 0.85)
ax.axvline(0.5, color=GOLD, lw=1.1, ls="--", zorder=2)
ax.text(0.505, len(order) - 0.3, "FSA threshold = 0.50", fontsize=6, color=GOLD,
        family="DejaVu Sans", va="top")
ax.grid(axis="x", color=GRID, lw=0.6, zorder=0)
for i, v in enumerate(means[::-1]):
    ax.text(v + 0.012, i, f"{v:.2f}", va="center", fontsize=6.3, family="DejaVu Sans", color=INK)
ax.tick_params(length=0)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
fig.tight_layout(pad=0.4)
fig.savefig(os.path.join(HERE, "fsa_by_model.pdf"))
plt.close(fig)

# ---------------------------------------------------------------- fig 2: FSA / both-pass by representation group
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

SHORT = {
    "Logical/Rules": "Logical/\nRules",
    "Concurrency/Interaction": "Concur./\nInteract.",
    "Programmatic/Code": "Program./\nCode",
    "Scenario/Behavioral": "Scenario/\nBehav.",
    "Math/Symbolic/Contracts": "Math/\nSymb.",
    "Stateful/Transitions": "Stateful/\nTrans.",
}

fig, ax = plt.subplots(figsize=(3.6, 2.5))
x = range(len(groups))
w = 0.36
ax.bar([i - w / 2 for i in x], fsa_means, width=w, color=TEAL, label="mean FSA", zorder=3)
ax.bar([i + w / 2 for i in x], both_means, width=w, color=GOLD, label="both-gates pass rate", zorder=3)
ax.set_xticks(list(x))
labels = [SHORT.get(g, g.replace("/", "/\n")) for g in groups]
ax.set_xticklabels(labels, fontsize=5.6, family="DejaVu Sans", rotation=0)
ax.margins(x=0.02)
ax.set_ylim(0, 1.0)
ax.grid(axis="y", color=GRID, lw=0.6, zorder=0)
ax.legend(fontsize=6, frameon=False, loc="upper right")
ax.tick_params(length=0)
for s in ("top", "right"):
    ax.spines[s].set_visible(False)
fig.tight_layout(pad=0.4)
fig.savefig(os.path.join(HERE, "fsa_by_repr_group.pdf"))
plt.close(fig)

# ---------------------------------------------------------------- fig 3: pipeline schematic (full-width, detailed)
GOLD_L = "#F0DDB0"
fig, ax = plt.subplots(figsize=(15.0, 5.2))
BOX_TOP = 3.95
BOX_BOT = 0.70
ax.set_xlim(0, 16.3)
ax.set_ylim(0, 4.9)
ax.axis("off")


def box(x, y0, y1, w, stage_tag, title, details, color=NAVY):
    h = y1 - y0
    ax.add_patch(FancyBboxPatch((x, y0), w, h, boxstyle="round,pad=0.02,rounding_size=0.07",
                 facecolor=color, edgecolor="none", zorder=3))
    ax.text(x + w / 2, y1 - 0.26, stage_tag, ha="center", va="center", color=GOLD_L,
            fontsize=8.5, family="DejaVu Sans", fontweight="bold", zorder=4,
            alpha=0.9)
    ax.text(x + w / 2, y1 - 0.58, title, ha="center", va="center", color="white",
            fontsize=12.5, family="DejaVu Sans", fontweight="bold", zorder=4)
    ax.plot([x + 0.18, x + w - 0.18], [y1 - 0.84, y1 - 0.84], color="white", lw=0.8,
            alpha=0.35, zorder=4)
    n = len(details)
    top_d = y1 - 1.18
    bot_d = y0 + 0.22
    step = (top_d - bot_d) / max(n - 1, 1) if n > 1 else 0
    for i, line in enumerate(details):
        yy = top_d - i * step if n > 1 else (top_d + bot_d) / 2
        ax.text(x + w / 2, yy, line, ha="center", va="center", color=GOLD_L,
                fontsize=9, family="DejaVu Sans", zorder=4)


def arrow(x0, y0, x1, y1, color=MUTE, lw=2.2):
    ax.add_patch(FancyArrowPatch((x0, y0), (x1, y1), arrowstyle="-|>", mutation_scale=18,
                 color=color, lw=lw, zorder=2))


stages = [
    ("S0–S1", "Ingest + Extract", NAVY,
     ["parse SRS text", "into atomic", "requirement", "clauses"]),
    ("GATE 1", "RSS", TEAL,
     ["RSS = 0.40 M1", "+ 0.30 M2", "+ 0.15 M3 + M4", "pass ≥ 0.60", "≤ 3 re-picks"]),
    ("S3", "Generate", NAVY,
     ["produce test", "suite in chosen", "representation"]),
    ("GATE 2", "SFV", TEAL,
     ["SFV = correct", "elements / total", "elements", "pass ≥ 0.60"]),
    ("GATE 3", "FSA + Mg", TEAL,
     ["FSA = wc C", "+ wn N + wo O", "+ wb B + wg Mg", "Mg = 1 − H/A", "pass ≥ 0.50"]),
    ("S6", "Execute + Audit", GOLD,
     ["run suite vs.", "real code;", "LLM audits", "code match"]),
    ("S7", "Report", NAVY,
     ["aggregate suite-", "and corpus-level", "statistics"]),
]
bw, gap = 2.05, 0.28
x = 0.25
positions = []
for tag, title, color, details in stages:
    box(x, BOX_BOT, BOX_TOP, bw, tag, title, details, color)
    positions.append(x)
    x += bw + gap

for i in range(len(positions) - 1):
    arrow(positions[i] + bw, (BOX_TOP + BOX_BOT) / 2, positions[i + 1], (BOX_TOP + BOX_BOT) / 2)

# repair loop: explicit L-shaped path below the row, from Gate 3 back to S3 Generate
g3x = positions[4] + bw / 2
s3x = positions[2] + bw / 2
y_loop = 0.30
ax.plot([g3x, g3x], [BOX_BOT, y_loop], color=GOLD, lw=1.8, zorder=2)
ax.plot([g3x, s3x], [y_loop, y_loop], color=GOLD, lw=1.8, zorder=2)
ax.add_patch(FancyArrowPatch((s3x, y_loop), (s3x, BOX_BOT), arrowstyle="-|>", mutation_scale=14,
             color=GOLD, lw=1.8, zorder=2))
ax.text((g3x + s3x) / 2, y_loop - 0.20, "closed-loop repair (≤ 3 attempts)", fontsize=11,
        family="DejaVu Sans", color=GOLD, ha="center", fontweight="bold")

fig.tight_layout(pad=0.3)
fig.savefig(os.path.join(HERE, "pipeline.pdf"))
plt.close(fig)

print("wrote fsa_by_model.pdf, fsa_by_repr_group.pdf, pipeline.pdf")
