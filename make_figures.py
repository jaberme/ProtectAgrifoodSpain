#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Figures of the manuscript, drawn from the JSON results written by the other
scripts (no numbers are typed here). Print-oriented: single-column figures are
3.4 in wide, double-column 7.0 in, 8-pt text, 300 dpi; one hue per measure,
fixed sector colours across figures, thin marks, recessive grid, no dual axes.

  fig_gamma.png        point loss
  fig_cascade.png      S2 trajectories: targeted sector and coupled sectors
  fig_dualrank.png     S2 dual ranking as two aligned panels
  fig_criteria.png     rank of each focal sector under w, m, v and w (trade split)
  fig_shapes.png       temporal forms of the targeted sector's recovery (S1)
  fig_uncertainty.png  share of log-variance by source (depth/recovery/structure)
"""
import json
import os

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

import scenarios as S

HERE = os.path.dirname(os.path.abspath(__file__))
FIG = os.path.join(HERE, "..", "figs")
os.makedirs(FIG, exist_ok=True)
J = lambda name: json.load(open(os.path.join(HERE, name)))
res = J("ine_scenarios_results.json")
crit = J("criteria.json")
part = J("partition_sensitivity.json")
shape = J("recovery_shape.json")
unc = J("uncertainty_decomposition.json")

INK, INK2, MUTED, GRID, AXIS, SURF = "#0b0b0b", "#52514e", "#8c8b86", "#e6e6e3", "#b3b2ad", "#ffffff"
COL = {"IAB": "#2a78d6", "AGR": "#eb6834", "ENV": "#1baf7a", "LOG": "#eda100", "RET": "#e87ba4",
       "ENE": "#008300", "AGU": "#4a3aa7", "ROE": "#8c8b86", "RETW": "#e87ba4", "RETR": "#c04a78"}
BLUE, ORANGE, AQUA = "#2a78d6", "#eb6834", "#1baf7a"
plt.rcParams.update({"font.size": 8, "font.family": "DejaVu Sans", "axes.edgecolor": AXIS, "axes.linewidth": 0.6,
                     "axes.labelcolor": INK, "xtick.color": INK2, "ytick.color": INK2, "xtick.labelsize": 7.5,
                     "ytick.labelsize": 7.5, "axes.titlesize": 8, "legend.fontsize": 7, "figure.dpi": 300,
                     "savefig.dpi": 300, "axes.spines.top": False, "axes.spines.right": False,
                     "grid.color": GRID, "grid.linewidth": 0.5, "axes.grid": False, "legend.frameon": False})

def tidy(ax, xgrid=False, ygrid=False):
    ax.set_axisbelow(True)
    if xgrid: ax.grid(True, axis="x")
    if ygrid: ax.grid(True, axis="y")
    ax.tick_params(length=2, width=0.5)

# ---------------------------------------------------------------- fig_gamma
order = ["S1", "S2", "S3", "S4", "S5", "A1", "G1", "R1", "C1"]
fig, ax = plt.subplots(figsize=(3.4, 2.7))
y = np.arange(len(order))[::-1]
pts = [res["baseline"][nm]["G"] for nm in order]
p5 = [res["envelopes"][nm]["p5"] for nm in order]
p50 = [res["envelopes"][nm]["p50"] for nm in order]
p95 = [res["envelopes"][nm]["p95"] for nm in order]
ax.barh(y, pts, height=0.5, color=BLUE, zorder=2, label="point (assumed mode)")
ax.hlines(y, p5, p95, color=INK2, lw=1.0, zorder=3, label="P5–P95 envelope")
ax.vlines(p5, y - 0.15, y + 0.15, color=INK2, lw=0.8, zorder=3); ax.vlines(p95, y - 0.15, y + 0.15, color=INK2, lw=0.8, zorder=3)
ax.scatter(p50, y, marker="D", s=16, facecolor=SURF, edgecolor=INK, lw=0.7, zorder=4, label="P50")
ax.set_yticks(y); ax.set_yticklabels(order)
ax.set_xlabel("Γ at 120 days (€ million, 2022 basic prices)", fontsize=7.5)
ax.set_xlim(0, max(p95) * 1.05); ax.set_ylim(-0.7, len(order) - 0.3)
ax.xaxis.set_major_formatter(matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}"))
tidy(ax, xgrid=True)
ax.legend(loc="upper center", bbox_to_anchor=(0.42, -0.26), ncol=3, handlelength=1.3, columnspacing=0.9, borderaxespad=0.0, fontsize=6.8)
fig.savefig(os.path.join(FIG, "fig_gamma.png"), bbox_inches="tight", pad_inches=0.03); plt.close(fig)

# ---------------------------------------------------------------- fig_cascade
cal = S.load_cal("base"); SECT = cal["sectors"]; idx = cal["idx"]
t, Q = S.trajectory(cal, S.SCN["S2"]["inj"], False, Hh=45.0, steps=901)
fig, (a1, a2) = plt.subplots(2, 1, figsize=(3.4, 3.2), sharex=True, gridspec_kw=dict(height_ratios=[1, 1.6], hspace=0.12, left=0.16, right=0.98, top=0.98, bottom=0.13))
a1.plot(t, Q[:, idx["IAB"]], color=COL["IAB"], lw=2.0, solid_capstyle="round")
a1.text(2.0, Q[20, idx["IAB"]], "IAB (targeted)", color=INK, va="bottom", ha="left", fontsize=7.5)
a1.set_ylabel("$q_i(t)$"); a1.set_ylim(0, 0.22); tidy(a1, ygrid=True)
others = ["AGR", "ENV", "LOG", "RET", "AGU", "ENE"]
for s in others:
    a2.plot(t, Q[:, idx[s]], color=COL[s], lw=1.3, solid_capstyle="round", label=s)
a2.plot(t, Q[:, idx["ROE"]], color=COL["ROE"], lw=1.0, ls="--", label="ROE")
for s, off in (("AGR", (4, 2)), ("ENV", (4, 2)), ("LOG", (10, -7))):
    k = int(np.argmax(Q[:, idx[s]])); a2.annotate(s, (t[k], Q[k, idx[s]]), xytext=off, textcoords="offset points", color=INK, fontsize=7)
a2.set_ylabel("$q_i(t)$ (coupled sectors)"); a2.set_xlabel("t (days)")
a2.set_ylim(0, 0.033); a2.set_xlim(0, 45); tidy(a2, ygrid=True)
a2.legend(ncol=4, loc="upper right", handlelength=1.6, columnspacing=0.9)
fig.savefig(os.path.join(FIG, "fig_cascade.png"), bbox_inches="tight", pad_inches=0.03); plt.close(fig)

# ---------------------------------------------------------------- fig_dualrank
qpeak = res["dual_S2"]["qpeak"]; dx = res["dual_S2"]["dx"]
by_loss = sorted(SECT, key=lambda s: -dx[s]); by_peak = sorted(SECT, key=lambda s: -qpeak[s])
rank_peak = {s: by_peak.index(s) + 1 for s in SECT}; rank_loss = {s: by_loss.index(s) + 1 for s in SECT}
fig, (b1, b2) = plt.subplots(1, 2, figsize=(7.0, 2.5), gridspec_kw=dict(wspace=0.45, left=0.06, right=0.99, top=0.97, bottom=0.17))
y = np.arange(len(by_loss))[::-1]
b1.barh(y, [qpeak[s] for s in by_loss], height=0.5, color=ORANGE, zorder=2)
for yi, s in zip(y, by_loss):
    b1.text(qpeak[s] + 0.003, yi, f"{qpeak[s]:.4f}  (rank {rank_peak[s]})", va="center", fontsize=7, color=INK2)
b1.set_yticks(y); b1.set_yticklabels(by_loss); b1.set_xlim(0, 0.30)
b1.set_xlabel("Peak inoperability $q_i^{\\mathrm{peak}}$ in S2"); tidy(b1, xgrid=True)
b2.barh(y, [dx[s] for s in by_loss], height=0.5, color=BLUE, zorder=2)
for yi, s in zip(y, by_loss):
    b2.text(dx[s] + 4, yi, f"{dx[s]:.1f}  (rank {rank_loss[s]})", va="center", fontsize=7, color=INK2)
b2.set_yticks(y); b2.set_yticklabels(by_loss); b2.set_xlim(0, 400)
b2.set_xlabel("Cumulative loss $\\Delta x_i$ at 120 days (€ million)"); tidy(b2, xgrid=True)
fig.savefig(os.path.join(FIG, "fig_dualrank.png"), bbox_inches="tight", pad_inches=0.03); plt.close(fig)

# ---------------------------------------------------------------- fig_criteria (bump chart)
focal = crit["ranking_w"]
cols = [("$w_j$", {s: crit["rows"][s]["rank_w"] for s in focal}),
        ("$m_j=w_j/x_j$", {s: crit["rows"][s]["rank_m"] for s in focal}),
        ("$v_j$", {s: crit["rows"][s]["rank_v"] for s in focal})]
split_rows = part["split"]["rows"]
fig, ax = plt.subplots(figsize=(3.4, 2.9))
xs = [0, 1, 2, 3.1]
for s in focal:
    ys = [c[1][s] for c in cols]
    ax.plot(xs[:3], ys, color=COL[s], lw=1.6, marker="o", ms=4.5, markeredgecolor=SURF, markeredgewidth=0.8, solid_capstyle="round")
    ax.text(-0.12, ys[0], s, ha="right", va="center", fontsize=7.5, color=INK)
    if s != "RET":
        ax.plot([xs[2], xs[3]], [ys[2], split_rows[s]["rank_w"]], color=COL[s], lw=1.2, ls=":")
        ax.plot([xs[3]], [split_rows[s]["rank_w"]], color=COL[s], marker="o", ms=4.5, markeredgecolor=SURF, markeredgewidth=0.8)
for s2 in ("RETW", "RETR"):
    ax.plot([xs[2], xs[3]], [cols[2][1]["RET"], split_rows[s2]["rank_w"]], color=COL[s2], lw=1.2, ls=":")
    ax.plot([xs[3]], [split_rows[s2]["rank_w"]], color=COL[s2], marker="o", ms=4.5, markeredgecolor=SURF, markeredgewidth=0.8)
    ax.text(xs[3] + 0.1, split_rows[s2]["rank_w"], s2, ha="left", va="center", fontsize=7, color=INK)
for s in focal:
    if s != "RET":
        ax.text(xs[3] + 0.1, split_rows[s]["rank_w"], s, ha="left", va="center", fontsize=7, color=INK)
ax.set_xticks(xs); ax.set_xticklabels(["$w_j$", "$m_j$", "$v_j$", "$w_j$\n(trade split)"])
ax.set_yticks(range(1, 9)); ax.set_ylim(8.5, 0.5); ax.set_ylabel("rank among focal sectors")
ax.set_xlim(-0.75, 3.9); tidy(ax, ygrid=True)
fig.tight_layout(pad=0.3); fig.savefig(os.path.join(FIG, "fig_criteria.png")); plt.close(fig)

# ---------------------------------------------------------------- fig_shapes (S1)
s1 = shape["scenarios"]["S1"]; T = s1["T"]; LN = S.LN100
tt = np.linspace(0, 10, 1001)
forms = {"E: exponential, T = 5 d": (np.exp(-tt * LN / T), BLUE),
         "P1: 1-day standstill, then T = 5 d": (np.where(tt <= 1, 1.0, np.exp(-(tt - 1) * LN / T)), ORANGE),
         "Pend1: 1-day standstill, 99 % at day 5": (np.where(tt <= 1, 1.0, np.exp(-(tt - 1) * LN / (T - 1))), AQUA),
         "L: linear restoration to zero at day 5": (np.clip(1 - tt / T, 0, None), "#eda100")}
fig, ax = plt.subplots(figsize=(3.4, 2.5))
for lab, (yv, c) in forms.items():
    ax.plot(tt, yv, color=c, lw=1.8, label=lab, solid_capstyle="round")
areas = {"E": s1["forms"]["E"]["area_days"], "P1": s1["forms"]["P1"]["area_days"], "Pend1": s1["forms"]["Pend1"]["area_days"], "L": s1["forms"]["L"]["area_days"]}
ax.text(6.2, 0.62, "area (days of full standstill\nper unit of $q_j(0)$):\n" + "\n".join(f"{k}: {v:.2f}" for k, v in areas.items()),
        fontsize=7, color=INK2, va="top")
ax.set_xlabel("t (days)"); ax.set_ylabel("$q_j(t)\\,/\\,q_j(0)$"); ax.set_xlim(0, 10); ax.set_ylim(0, 1.05)
tidy(ax, ygrid=True); ax.legend(loc="upper right", bbox_to_anchor=(1.0, 1.02), handlelength=1.6)
fig.tight_layout(pad=0.3); fig.savefig(os.path.join(FIG, "fig_shapes.png")); plt.close(fig)

# ---------------------------------------------------------------- fig_uncertainty (variance shares)
order_u = ["S1", "S2", "S3", "S4", "S5", "A1", "G1", "R1", "C1"]
fig, ax = plt.subplots(figsize=(3.4, 2.5))
y = np.arange(len(order_u))[::-1]
left = np.zeros(len(order_u))
for key, lab, c in (("depth", "shock depth $q_j(0)$", BLUE), ("recovery", "recovery time $T_j$", ORANGE), ("structure", "structure ($A^*$, $\\hat{x}$, heat)", AQUA)):
    vals = np.array([100 * unc["oat"][nm]["shares"][key] for nm in order_u])
    ax.barh(y, vals, left=left, height=0.55, color=c, edgecolor=SURF, linewidth=1.0, label=lab, zorder=2)
    for yi, l0, v in zip(y, left, vals):
        if v >= 12: ax.text(l0 + v / 2, yi, f"{v:.0f}", ha="center", va="center", fontsize=6.5, color=SURF if c != AQUA else INK)
    left += vals
ax.set_yticks(y); ax.set_yticklabels(order_u); ax.set_xlim(0, 100); ax.set_xlabel("share of Var[log Γ] (%)")
tidy(ax, xgrid=True); ax.legend(loc="lower center", bbox_to_anchor=(0.45, 1.0), ncol=3, handlelength=1.2, columnspacing=0.7, fontsize=6.5)
fig.savefig(os.path.join(FIG, "fig_uncertainty.png"), bbox_inches="tight", pad_inches=0.03); plt.close(fig)
print("figures written to", os.path.abspath(FIG), ":", sorted(os.listdir(FIG)))
