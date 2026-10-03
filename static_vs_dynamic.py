#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Three prioritisation criteria among the focal sectors,
each answering a different question about a shock originating in sector j:

  w_j = [x^T (I-A*)^{-1}]_j        equal integrated inoperability q_j(0)/k_j
                                    (fraction of the sector's own output);
  m_j = w_j / x_j                   equal integrated monetary withdrawal
                                    b_j = x_j q_j(0)/(365 k_j) (one euro of
                                    direct output lost); m_j is the column sum
                                    of (I-A)^{-1}, the Leontief output multiplier;
  v_j = tau_j (1-a*_jj) w_j/(365 ln100)   loss per unit of initial inoperability
                                    at the baseline reference recovery time.

Identity: since A* = D^{-1} A D with D = diag(x), (I-A*)^{-1} = D^{-1}(I-A)^{-1}D,
so w_j = x_j sum_i (I-A)^{-1}_ij = x_j m_j exactly.
Writes criteria.json.
"""
import json
import os

import numpy as np

import scenarios as S

HERE = os.path.dirname(os.path.abspath(__file__))
cal = S.load_cal("base")
SECT = cal["sectors"]; n = cal["n"]; idx = cal["idx"]
A = np.array(cal["Astar"]); x = np.array(cal["x"]); Atech = np.array(cal["A"])
FOCAL = S.focal(cal)
tau = S.tau_vector(cal)
L = np.linalg.inv(np.eye(n) - A)
w = x @ L
m = np.linalg.inv(np.eye(n) - Atech).sum(axis=0)
assert np.allclose(m, w / x, rtol=1e-12), "w_j = x_j m_j identity violated"
v = tau * (1 - np.diag(A)) * w / (365 * S.LN100)
colsum_star = L.sum(axis=0)

def ranks(vals):
    order = sorted(FOCAL, key=lambda s: -vals[idx[s]])
    return {s: order.index(s) + 1 for s in FOCAL}
rk = dict(w=ranks(w), m=ranks(m), v=ranks(v))
print(f"{'sec':4s} {'x':>10s} {'w_j':>10s} {'rk':>3s} {'m_j=w/x':>8s} {'rk':>3s} {'tau':>4s} {'a*_jj':>6s} {'v_j':>8s} {'rk':>3s}")
rows = {}
for s in FOCAL:
    i = idx[s]
    print(f"{s:4s} {x[i]:10,.0f} {w[i]:10,.0f} {rk['w'][s]:3d} {m[i]:8.4f} {rk['m'][s]:3d} "
          f"{tau[i]:4.0f} {A[i,i]:6.3f} {v[i]:8.1f} {rk['v'][s]:3d}")
    rows[s] = dict(x=float(x[i]), w=float(w[i]), m=float(m[i]), tau=float(tau[i]),
                   a_jj=float(A[i, i]), v=float(v[i]), colsum_Lstar=float(colsum_star[i]),
                   rank_w=rk["w"][s], rank_m=rk["m"][s], rank_v=rk["v"][s])
print("\nranking by w (equal integrated inoperability):", sorted(FOCAL, key=lambda s: rk["w"][s]))
print("ranking by m (per euro withdrawn, output multiplier):", sorted(FOCAL, key=lambda s: rk["m"][s]))
print("ranking by v (per unit initial inoperability, baseline tau):", sorted(FOCAL, key=lambda s: rk["v"][s]))
json.dump(dict(rows=rows, ROE=dict(x=float(x[idx["ROE"]]), w=float(w[idx["ROE"]]), m=float(m[idx["ROE"]])),
               ranking_w=sorted(FOCAL, key=lambda s: rk["w"][s]),
               ranking_m=sorted(FOCAL, key=lambda s: rk["m"][s]),
               ranking_v=sorted(FOCAL, key=lambda s: rk["v"][s])),
          open(os.path.join(HERE, "criteria.json"), "w"), indent=2)
print("criteria.json written.")
