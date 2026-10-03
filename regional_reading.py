#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
National reading of a territorially confined incident (scenario definitions
from scenarios.py). Computes (1) the per-target contributions Gamma_j of C1
and the national loss sum_j theta_j Gamma_j of an incident reproducing the
scenario intensity only among the operators of a territory with output
shares theta_j (INE 2024 shares of Andalusia and of the Mediterranean arc as
proxies: branch-A value added; turnover of CNAE 10-12; turnover of section G),
against theta Gamma with a single share; (2) the location of Gamma_inf by
receiving sector (targeted vs cascade) in S2, S4, R1, C1; (3) the sensitivity
of Gamma_inf(S4) to AGR's purchase structure (off-diagonal column x0.7, x1.3)
and to a reorientation of its sales from industry to trade. Writes
regional_reading.json.
"""
import json
import os

import numpy as np

import scenarios as S

HERE = os.path.dirname(os.path.abspath(__file__))
cal = S.load_cal("base")
SECT = cal["sectors"]; n = cal["n"]; idx = cal["idx"]
A0 = np.array(cal["Astar"]); x0 = np.array(cal["x"])
SHARES = {"Andalusia": {"AGR": 0.3075, "IAB": 0.1410, "RET": 0.1302},
          "Arc": {"AGR": 0.5028, "IAB": 0.5047, "RET": 0.4535}}

gamma_j = S.closed_form_terms(cal, S.SCN["C1"]["inj"], True)
gamma_c1 = sum(gamma_j.values())
reading = {name: dict(shares=th, sum_theta_j_gamma_j=sum(th[j] * gamma_j[j] for j in gamma_j),
                      single_theta_AGR=th["AGR"] * gamma_c1, single_theta_IAB=th["IAB"] * gamma_c1)
           for name, th in SHARES.items()}
print("Gamma_j of C1 (EUR M):", {k: round(v, 2) for k, v in gamma_j.items()},
      f"| total {gamma_c1:.2f} | IAB share {100*gamma_j['IAB']/gamma_c1:.1f} %")
for name, r in reading.items():
    print(f"{name}: sum theta_j Gamma_j = {r['sum_theta_j_gamma_j']:.1f}; theta_AGR*Gamma = {r['single_theta_AGR']:.1f}; "
          f"theta_IAB*Gamma = {r['single_theta_IAB']:.1f}")

location = {}
for nm in ("S2", "S4", "R1", "C1"):
    sc = S.SCN[nm]
    q0 = S.q0_vector(cal, sc["inj"]); tau = S.scenario_tau(cal, sc["inj"], sc["heat"])
    dx = x0 / 365.0 * np.linalg.solve(S.K_matrix(A0, tau) @ (np.eye(n) - A0), q0)
    targets = [idx[t] for t, _q, _T in sc["inj"]]
    own = dx[targets].sum()
    location[nm] = dict(gamma_inf=float(dx.sum()), targeted=float(own), cascade=float(dx.sum() - own),
                        cascade_share=float(1 - own / dx.sum()), by_sector={s: float(dx[idx[s]]) for s in SECT})
    print(f"{nm}: Gamma_inf {dx.sum():.1f}; outside targeted sectors {100*(1-own/dx.sum()):.1f} %")

j = idx["AGR"]; base = sum(S.closed_form_terms(cal, S.SCN["S4"]["inj"], True).values())
variants = {}
for f in (0.7, 1.3):
    A = A0.copy(); off = np.ones(n, bool); off[j] = False; A[off, j] *= f
    variants[f"purchase_column_x{f}"] = sum(S.closed_form_terms(cal, S.SCN["S4"]["inj"], True, A=A).values())
    A = A0.copy(); A[j, off] *= f
    variants[f"sales_row_x{f}"] = sum(S.closed_form_terms(cal, S.SCN["S4"]["inj"], True, A=A).values())
A = A0.copy(); A[j, idx["IAB"]] = 0.30; A[j, idx["RET"]] = 0.20
variants["sales_reoriented_to_trade"] = sum(S.closed_form_terms(cal, S.SCN["S4"]["inj"], True, A=A).values())
sensitivity = {k: dict(gamma_inf=float(v), pct_change=float(100 * (v / base - 1))) for k, v in variants.items()}
print("Sensitivity of Gamma_inf(S4) =", round(base, 1), ":", {k: f"{v['pct_change']:+.1f} %" for k, v in sensitivity.items()})
json.dump(dict(scenario_C1_gamma_j=gamma_j, gamma_C1=gamma_c1, IAB_share_of_gamma_C1=gamma_j["IAB"] / gamma_c1,
               regional_reading=reading, loss_location=location, S4_gamma_inf=float(base),
               S4_structure_sensitivity=sensitivity, a_AGR_IAB=float(A0[j, idx["IAB"]])),
          open(os.path.join(HERE, "regional_reading.json"), "w"), indent=2)
print("regional_reading.json written.")
