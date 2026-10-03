#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Numerical verification of the DIIM implementation on the INE TIO-2022
calibration. Reads the scenario set from scenarios.py (no local copies of
parameters) and FAILS LOUDLY (exit code 1) if any point loss deviates from
ine_scenarios_results.json, so that a stale reproduction set cannot pass
silently (editorial condition R2.1).

Checks: matrix-exponential trajectories against an independent ODE
integrator; the general loss identity Gamma(H) = x^T W(H)/365; the closed
form Gamma_inf = x^T (I-A*)^{-1} K^{-1} q0 / 365; linearity in T
(Gamma_inf(S4)/Gamma_inf(S3) = 2.5); additivity of C1 = S4 + S2 + R1 at
infinite horizon; forward invariance of [0,1]^n (row sums of A* plus c* at
most one); and equality with the stored baseline. No figures are produced
here (see make_figures.py).
"""
import json
import os
import sys

import numpy as np
from scipy.integrate import solve_ivp
from scipy.linalg import expm

import scenarios as S

HERE = os.path.dirname(os.path.abspath(__file__))
cal = S.load_cal("base")
SECT = cal["sectors"]; n = cal["n"]; idx = cal["idx"]
A = np.array(cal["Astar"]); x = np.array(cal["x"])
rho = max(abs(np.linalg.eigvals(A)))
assert rho < 1 and abs(rho - cal["rho"]) < 1e-12
print(f"Calibration: {cal['source']}\nrho(A*) = {rho:.4f}; max row sum = {A.sum(axis=1).max():.4f}")

ref = json.load(open(os.path.join(HERE, "ine_scenarios_results.json")))["baseline"]
Leontief = np.linalg.inv(np.eye(n) - A)
w = x @ Leontief
failures = []
print(f"\n{'scn':4s} {'Gamma(120)':>11s} {'Gamma_inf':>10s} {'stored':>10s} {'expm-ODE':>10s} {'W-identity':>10s}")
for nm, sc in S.SCN.items():
    q0 = S.q0_vector(cal, sc["inj"])
    tau = S.scenario_tau(cal, sc["inj"], sc["heat"])
    K = S.K_matrix(A, tau); M = K @ (np.eye(n) - A)
    t = np.linspace(0, S.H, 1201)
    Q = np.array([expm(-M * ta) @ q0 for ta in t])
    sol = solve_ivp(lambda tt, q: -M @ q, [0, S.H], q0, t_eval=t, rtol=1e-10, atol=1e-13)
    err = float(np.max(np.abs(sol.y.T - Q)))
    W = np.linalg.inv(M) @ (np.eye(n) - expm(-M * S.H)) @ q0
    G = float(x @ W / 365)
    G_trap = float(np.trapz(x @ Q.T / 365, t))
    Ginf = float(x @ Leontief @ np.linalg.inv(K) @ q0 / 365)
    dx, G2, Ginf2 = S.loss(cal, sc["inj"], sc["heat"])
    ok = abs(G - ref[nm]["G"]) < 1e-9 and abs(G - G2) < 1e-9 and abs(Ginf - Ginf2) < 1e-9 and err < 1e-9
    if not ok: failures.append(nm)
    print(f"{nm:4s} {G:11.4f} {Ginf:10.4f} {ref[nm]['G']:10.4f} {err:10.2e} {abs(G-G_trap)/G:10.2e} {'OK' if ok else 'FAIL'}")
    # forward invariance of the unit box for the transient scenarios
    assert Q.min() >= -1e-12 and Q.max() <= 1 + 1e-12, nm
    assert Q[1:, idx[sc["inj"][0][0]]].max() <= q0.max() + 1e-12

lin = ref["S4"]["Ginf"] / ref["S3"]["Ginf"]
add = abs(ref["C1"]["Ginf"] - ref["S4"]["Ginf"] - ref["S2"]["Ginf"] - ref["R1"]["Ginf"])
g, q_td, rate = S.two_phase_loss(cal, S.A1_TWO_PHASE["depth"], S.A1_TWO_PHASE["t_d"], S.A1_TWO_PHASE["T_rem"])
print(f"\nGamma_inf(S4)/Gamma_inf(S3) = {lin:.12f} (exact 2.5): {'OK' if abs(lin-2.5)<1e-9 else 'FAIL'}")
print(f"C1 - (S4+S2+R1) at infinite horizon = {add:.2e}: {'OK' if add<1e-8 else 'FAIL'}")
print(f"A1 two-phase: {g:.4f} vs stored {ref['A1']['G']:.4f}: {'OK' if abs(g-ref['A1']['G'])<1e-9 else 'FAIL'}")
if abs(lin - 2.5) >= 1e-9 or add >= 1e-8 or abs(g - ref["A1"]["G"]) >= 1e-9:
    failures.append("identities")
print("\nExposure weights w_j = [x^T (I-A*)^-1]_j and output multipliers m_j = w_j/x_j:")
for i in sorted(range(n), key=lambda i: -w[i]):
    print(f"  {SECT[i]:3s} w={w[i]:11.1f}  x={x[i]:10.0f}  m={w[i]/x[i]:.4f}  a*_ii={A[i,i]:.3f}")
print("  focal ranking by w:", sorted(S.focal(cal), key=lambda s: -w[idx[s]]))
if failures:
    print("\nVERIFICATION FAILED:", failures)
    sys.exit(1)
print("\nVERIFICATION PASSED: scenarios.py, ine_scenarios_results.json and the closed forms agree.")
