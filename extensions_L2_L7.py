#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Conditional extensions on the INE TIO-2022 calibration (scenario definitions
from scenarios.py):

Two-phase integrity attack (principal A1): sustained c* until detection at t_d, transient recovery afterwards (see scenarios.two_phase_loss). Table over t_d and T_rem; ratio to the transient forcing A1-T.

Adversarial timing premium: seasonal T_AGR(t0) with a thermal window of W days; Pi_T = max T / E[T]; scenario-conditioned expected loss under uniform timing.

Single-counted channel corridor: A_max = max(A*, A_fwd) elementwise; same diagonal, hence same K. Gamma_inf under A* (backward) and A_max for ALL scenarios, including the two-phase A1 (both phases with A_max), and the focal ranking under A_max.
Writes extensions.json.
"""
import json
import os

import numpy as np

import scenarios as S

HERE = os.path.dirname(os.path.abspath(__file__))
cal = S.load_cal("base")
SECT = cal["sectors"]; n = cal["n"]; idx = cal["idx"]
A = np.array(cal["Astar"]); x = np.array(cal["x"])
FOCAL = S.focal(cal)
a1 = S.A1_TWO_PHASE
out = {}

print("=== L2: two-phase integrity attack (A1, AGR) ===")
G_T = S.loss(cal, S.SCN["A1T"]["inj"], False)[2]
grid = {}
for t_d in (10, 20, 30, 45):
    for T_rem in (7, 10, 14):
        g, qd, rate = S.two_phase_loss(cal, a1["depth"], t_d, T_rem, a1["sector"])
        grid[f"td{t_d}_Trem{T_rem}"] = dict(t_d=t_d, T_rem=T_rem, gamma=g, q_td=qd)
        if T_rem == 10:
            print(f"  t_d={t_d:3d} d, T_rem={T_rem:2d} d: Gamma = {g:7.1f} EUR M (q_AGR(t_d)={qd:.3f})")
g30, q30, rate = S.two_phase_loss(cal, a1["depth"], a1["t_d"], a1["T_rem"], a1["sector"])
print(f"  steady loss rate while undetected: {rate:.1f} EUR M/day; point {g30:.1f} vs transient A1-T {G_T:.1f} (x{g30/G_T:.2f})")
out["L2"] = dict(point=dict(gamma=g30, q_td=q30, rate=rate, transient=G_T, ratio=g30 / G_T), grid=grid)

print("\n=== L3: adversarial timing premium (irrigation, AGR) ===")
T_base, T_heat, Wd = 10.0, 25.0, 90.0
ET = (Wd * T_heat + (365 - Wd) * T_base) / 365.0
prem = T_heat / ET
G3, G4 = S.loss(cal, S.SCN["S3"]["inj"], False)[1], S.loss(cal, S.SCN["S4"]["inj"], True)[1]
print(f"  E[T]={ET:.2f} d; Pi_T = {prem:.2f}; S3={G3:.1f}, S4={G4:.1f}; expected loss under uniform timing = {G3*ET/T_base:.1f} EUR M")
out["L3"] = dict(T_base=T_base, T_heat=T_heat, window_days=Wd, E_T=ET, premium=prem, S3=G3, S4=G4, uniform_timing_loss=G3 * ET / T_base)

print("\n=== L4: single-counted channel corridor (A_max) ===")
A_fwd = (A * x[:, None] / x[None, :]).T
A_max = np.maximum(A, A_fwd)
assert np.allclose(np.diag(A_max), np.diag(A))
rho_max = max(abs(np.linalg.eigvals(A_max)))
w_max = x @ np.linalg.inv(np.eye(n) - A_max)
w = x @ np.linalg.inv(np.eye(n) - A)
print(f"  rho(A*)={cal['rho']:.4f}  rho(A_max)={rho_max:.4f}")
print("  focal ranking w (backward):", sorted(FOCAL, key=lambda s: -w[idx[s]]))
print("  focal ranking w (A_max)   :", sorted(FOCAL, key=lambda s: -w_max[idx[s]]))
corr = {}
for nm, sc in S.SCN.items():
    lo = S.loss(cal, sc["inj"], sc["heat"])[2]
    hi = S.loss(cal, sc["inj"], sc["heat"], A=A_max)[2]
    corr[nm] = dict(backward=lo, amax=hi, ratio=hi / lo)
lo = S.two_phase_loss(cal, a1["depth"], a1["t_d"], a1["T_rem"], a1["sector"])[0]
hi = S.two_phase_loss(cal, a1["depth"], a1["t_d"], a1["T_rem"], a1["sector"], A=A_max)[0]
corr["A1"] = dict(backward=lo, amax=hi, ratio=hi / lo)
for nm, c in corr.items():
    print(f"  {nm:4s}: [{c['backward']:7.1f} .. {c['amax']:7.1f}]  (x{c['ratio']:.2f})")
order_bwd = sorted(corr, key=lambda k: -corr[k]["backward"]); order_max = sorted(corr, key=lambda k: -corr[k]["amax"])
print("  scenario order backward:", order_bwd); print("  scenario order A_max   :", order_max)
out["L4"] = dict(rho_amax=float(rho_max), ranking_backward=sorted(FOCAL, key=lambda s: -w[idx[s]]),
                 ranking_amax=sorted(FOCAL, key=lambda s: -w_max[idx[s]]),
                 w_amax={s: float(w_max[idx[s]]) for s in SECT}, corridor=corr,
                 scenario_order_backward=order_bwd, scenario_order_amax=order_max)
json.dump(out, open(os.path.join(HERE, "extensions.json"), "w"), indent=2)
print("\nextensions.json written.")
