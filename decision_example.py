#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Illustrative protection decision on S2.
Two measures with ASSUMED effects (not measured control efficacies):
  A  depth control: reduces q_IAB(0) by 10 % relative (0.20 -> 0.18), e.g.
     segmentation and remote-access hardening that limit the number of plants
     reached by one campaign;
  B  restoration control: reduces the reference time from 14 to 12 days, e.g.
     tested offline backups and rehearsed restoration.
Avoided loss from Eq. (avoided): DG = kappa_j [T dq + q dT - dq dT], with
kappa_j = (1 - a*_jj) w_j / (365 ln100). The joint benefit is smaller than the
sum of the separate benefits by the cross term kappa_j dq dT. Envelopes use
the stored structural draws (A*, x-hat) of the reference Monte Carlo with q, T
at their point values, and, separately, the triangular q, T draws with the
point structure, to show how each benefit scales. Writes decision_example.json.
"""
import json
import os

import numpy as np

import scenarios as S

HERE = os.path.dirname(os.path.abspath(__file__))
cal = S.load_cal("base")
SECT = cal["sectors"]; n = cal["n"]; idx = cal["idx"]
A0 = np.array(cal["Astar"]); x0 = np.array(cal["x"])
j = idx["IAB"]; q, T = 0.20, 14.0
dq, dT = 0.10 * q, 2.0

def kappa(A, x):
    w = x @ np.linalg.inv(np.eye(n) - A)
    return (1 - A[j, j]) * w[j] / (365 * S.LN100)

def benefits(A, x, q, T):
    k = kappa(A, x)
    bA = k * T * dq
    bB = k * q * dT
    joint = k * (T * dq + q * dT - dq * dT)
    return dict(gamma=k * q * T, A=bA, B=bB, sum=bA + bB, joint=joint, cross=k * dq * dT)

pt = benefits(A0, x0, q, T)
# finite-horizon check (H = 120 d) by direct recomputation
def G120(qv, Tv):
    return S.loss(cal, [("IAB", qv, Tv)], False)[1]
chk = dict(A=G120(q, T) - G120(q - dq, T), B=G120(q, T) - G120(q, T - dT),
           joint=G120(q, T) - G120(q - dq, T - dT))
print("Point (Gamma_inf, EUR M):", {k: round(v, 2) for k, v in pt.items()})
print("Finite-horizon check (H=120):", {k: round(v, 2) for k, v in chk.items()})
print(f"naive sum overstates the joint benefit by {pt['cross']:.2f} EUR M ({100*pt['cross']/pt['joint']:.1f} % of the joint benefit)")
print(f"as share of Gamma(S2): A {100*pt['A']/pt['gamma']:.1f} %, B {100*pt['B']/pt['gamma']:.1f} %, joint {100*pt['joint']/pt['gamma']:.1f} %")

mc = np.load(os.path.join(HERE, "mc_samples.npz"))
As, xs = mc["A"], mc["x"]
struct = {k: [] for k in ("A", "B", "joint", "gamma")}
for Ai, xi in zip(As, xs):
    b = benefits(Ai, xi, q, T)
    for k in struct: struct[k].append(b[k])
struct_env = {k: dict(zip(("p5", "p50", "p95"), np.percentile(v, [5, 50, 95]).tolist())) for k, v in struct.items()}
print("Structural envelope (A*, x-hat draws; q, T at point):", {k: {p: round(val, 1) for p, val in e.items()} for k, e in struct_env.items()})

rng = np.random.default_rng([S.SEED, 5])
r = S.RANGES[("S2", "IAB")]
par = {k: [] for k in ("A", "B", "joint", "gamma")}
for _ in range(S.N_SAMPLES):
    qq = S.tri_ppf(rng.uniform(), r["q"][0], q, r["q"][1])
    TT = S.tri_ppf(rng.uniform(), r["T"][0], T, r["T"][1])
    k = kappa(A0, x0)
    dq_ = 0.10 * qq
    par["gamma"].append(k * qq * TT); par["A"].append(k * TT * dq_); par["B"].append(k * qq * min(dT, TT))
    par["joint"].append(k * (TT * dq_ + qq * min(dT, TT) - dq_ * min(dT, TT)))
par_env = {k: dict(zip(("p5", "p50", "p95"), np.percentile(v, [5, 50, 95]).tolist())) for k, v in par.items()}
print("Parametric envelope (triangular q, T; point structure):", {k: {p: round(val, 1) for p, val in e.items()} for k, e in par_env.items()})
json.dump(dict(scenario="S2", q=q, T=T, dq=dq, dT=dT, kappa=kappa(A0, x0), point=pt, finite_horizon_check=chk,
               structural_envelope=struct_env, parametric_envelope=par_env,
               share_of_gamma=dict(A=pt["A"] / pt["gamma"], B=pt["B"] / pt["gamma"], joint=pt["joint"] / pt["gamma"])),
          open(os.path.join(HERE, "decision_example.json"), "w"), indent=2)
print("decision_example.json written.")
