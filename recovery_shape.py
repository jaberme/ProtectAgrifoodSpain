#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Temporal form of the targeted sector's recovery.

The reference time T_i of Eq. (k-def) fixes an exponential isolated path
q_j(t) = q_j(0) exp(-t ln100 / T_j), whose integral is q_j(0) T_j / ln100:
T = 5 days is worth 1.09 days of complete standstill of the injected fraction.
Alternative forms with the same q_j(0):
  E      exponential, reference (area T/ln100 per unit q);
  P(D)   plateau of D days at q_j(0) (no restoration yet), then exponential
         with the same T (area D + T/ln100);
  Pend(D) plateau of D days, then exponential reaching 1 % at the same date T
         as E, i.e. with reference time T - D (area D + (T-D)/ln100);
  L      linear ramp to zero at T (staged restoration; area T/2);
  S3     three equal restoration steps at T/3, 2T/3, T (area 2T/3).
With the target's path taken as exogenous (the convention that defines T),
the other sectors respond linearly and their infinite-horizon integrals are
(I - A*_{-j,-j})^{-1} A*_{-j,j} times the target's area, independent of K and
of the form. Hence Gamma_inf = g_j x area_j exactly, and the ratio between
forms equals the ratio of areas. The DIIM proper (target path endogenous)
differs from E only through the feedback the target receives from its
customers; both are reported. A numerical integration of the plateau form
checks the closed form. Writes recovery_shape.json.
"""
import json
import os

import numpy as np
from scipy.integrate import solve_ivp

import scenarios as S

HERE = os.path.dirname(os.path.abspath(__file__))
cal = S.load_cal("base")
SECT = cal["sectors"]; n = cal["n"]; idx = cal["idx"]
A = np.array(cal["Astar"]); x = np.array(cal["x"])
LN = S.LN100

def gain(j):
    """EUR M per (unit q x day) of the target's area: own output plus the
    infinite-horizon response of the other sectors (DC gain, K-independent)."""
    o = [i for i in range(n) if i != j]
    resp = np.linalg.solve(np.eye(n - 1) - A[np.ix_(o, o)], A[np.ix_(o, [j])]).ravel()
    return (x[j] + x[o] @ resp) / 365.0, dict(zip([SECT[i] for i in o], resp))

def clamped_numeric(j, q0, T, D, Hh=400.0):
    """Numerical check: plateau D then exponential (same T), target exogenous."""
    tau = S.tau_vector(cal); tau[j] = T
    K = S.K_matrix(A, tau)
    def qj(t): return q0 if t <= D else q0 * np.exp(-(t - D) * LN / T)
    def rhs(t, y):
        q = y[:n].copy(); q[j] = qj(t)
        dq = K @ (A @ q - q); dq[j] = 0.0
        return np.r_[dq, x @ q / 365.0]
    sol = solve_ivp(rhs, [0, Hh], np.zeros(n + 1), rtol=1e-10, atol=1e-12, max_step=0.5)
    return float(sol.y[-1, -1])

out = dict(convention="target path exogenous; Gamma_inf = g_j * area", scenarios={})
print("form        area/q0 (d)   Gamma_inf (EUR M)   ratio to E")
for nm in ("S1", "S2", "R1", "S3", "G1"):
    tgt, q0, T = S.SCN[nm]["inj"][0]
    j = idx[tgt]
    g, resp = gain(j)
    _dx, _G, Gdiim = S.loss(cal, S.SCN[nm]["inj"], S.SCN[nm]["heat"])
    forms = {"E": T / LN}
    for D in (1.0, 3.0):
        forms[f"P{D:.0f}"] = D + T / LN
        if T - D > 0:
            forms[f"Pend{D:.0f}"] = D + (T - D) / LN
    forms["L"] = T / 2.0
    forms["S3"] = 2 * T / 3.0
    r = S.RANGES[(nm, tgt)]["T"]
    rows = {f: dict(area_days=a, gamma_inf=g * q0 * a, ratio=a / (T / LN)) for f, a in forms.items()}
    chk = clamped_numeric(j, q0, T, 1.0)
    out["scenarios"][nm] = dict(target=tgt, q0=q0, T=T, gain=float(g), gamma_diim=Gdiim,
                                gamma_E_exogenous=g * q0 * T / LN,
                                feedback_pct=100 * (Gdiim / (g * q0 * T / LN) - 1),
                                numeric_check_P1=chk, forms=rows,
                                T_range=list(r), gamma_T_range=[Gdiim * r[0] / T, Gdiim * r[1] / T],
                                T_equivalent_for_L=T * 2 / LN, T_equivalent_for_S3=T * 3 / (2 * LN))
    print(f"\n{nm} ({tgt}, q0={q0}, T={T} d): g_j={g:,.1f} EUR M per unit-day; DIIM proper {Gdiim:.1f}; "
          f"E exogenous {g*q0*T/LN:.1f} (feedback {out['scenarios'][nm]['feedback_pct']:+.2f} %)")
    for f, rw in rows.items():
        print(f"  {f:6s} {rw['area_days']:10.3f} {rw['gamma_inf']:12.1f} {rw['ratio']:10.3f}")
    print(f"  numeric check P1 (H=400 d): {chk:.2f} vs closed form {rows['P1']['gamma_inf']:.2f}")
    print(f"  parametric T range {r} -> Gamma [{Gdiim*r[0]/T:.1f}, {Gdiim*r[1]/T:.1f}]")
json.dump(out, open(os.path.join(HERE, "recovery_shape.json"), "w"), indent=2)
print("\nrecovery_shape.json written.")
