#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Sensitivity of exposure criteria and scenario losses to the sector partition. 
Three calibrations built by ine_calibration.py from
the same INE workbook:
  base : eight sectors of the manuscript;
  split: trade separated into wholesale (RETW, P29) and retail (RETR, P30);
  envp : packaging proxy restricted to rubber and plastics (P13).
For each: w_j, m_j = w_j/x_j, v_j and their ranks among focal sectors.
Under 'split', R1 is re-specified on RETR: the largest grocer's margin-basis
output (9,833-10,298 EUR M) divided by retail trade-services output gives its
share of RETR; the point injection is rounded to 0.10 (range 0.05-0.12 kept
proportional to the base range 0.01-0.05 scaled by the 2.5 ratio of output
bases). S2, S4 and C1 are recomputed. Writes partition_sensitivity.json.
"""
import json
import os

import numpy as np

import scenarios as S

HERE = os.path.dirname(os.path.abspath(__file__))
out = {}
for part in ("base", "split", "envp"):
    cal = S.load_cal(part)
    SECT = cal["sectors"]; n = cal["n"]; idx = cal["idx"]
    A = np.array(cal["Astar"]); x = np.array(cal["x"])
    FOCAL = S.focal(cal)
    tau = S.tau_vector(cal)
    w = x @ np.linalg.inv(np.eye(n) - A)
    m = w / x
    v = tau * (1 - np.diag(A)) * w / (365 * S.LN100)
    rk = {c: sorted(FOCAL, key=lambda s: -vals[idx[s]]) for c, vals in (("w", w), ("m", m), ("v", v))}
    rows = {s: dict(x=float(x[idx[s]]), w=float(w[idx[s]]), m=float(m[idx[s]]), v=float(v[idx[s]]),
                    a_jj=float(A[idx[s], idx[s]]),
                    rank_w=rk["w"].index(s) + 1, rank_m=rk["m"].index(s) + 1, rank_v=rk["v"].index(s) + 1)
            for s in FOCAL}
    res = dict(rho=cal["rho"], sectors=SECT, rows=rows,
               ranking_w=rk["w"], ranking_m=rk["m"], ranking_v=rk["v"], losses={})
    print(f"\n=== partition {part}: rho={cal['rho']:.4f}")
    for s in FOCAL:
        r = rows[s]
        print(f"  {s:5s} x={r['x']:10,.0f} w={r['w']:10,.0f} ({r['rank_w']})  m={r['m']:.4f} ({r['rank_m']})  v={r['v']:8.1f} ({r['rank_v']})")
    scn = dict(S.SCN)
    if part == "split":
        mb = S.INJECTION_ANCHORS["RET"]["largest_operator"]["margin_basis_output_MEUR"]
        share = tuple(v_ / x[idx["RETR"]] for v_ in mb)
        res["largest_grocer_share_of_RETR"] = list(share)
        print(f"  largest grocer share of retail trade output: {share[0]:.4f}-{share[1]:.4f}")
        scn = {"S2": S.SCN["S2"], "S4": S.SCN["S4"],
               "R1": dict(inj=[("RETR", 0.10, 9)], heat=False),
               "R1-RETW-0.04": dict(inj=[("RETW", 0.04, 9)], heat=False),
               "C1": dict(inj=[("AGR", 0.15, 25), ("IAB", 0.20, 14), ("RETR", 0.10, 9)], heat=True)}
    elif part == "envp":
        scn = {k: S.SCN[k] for k in ("S2", "S4", "R1", "C1")}
    else:
        scn = {k: S.SCN[k] for k in ("S2", "S4", "R1", "C1")}
    for nm, sc in scn.items():
        dx, G, Gi = S.loss(cal, sc["inj"], sc["heat"])
        res["losses"][nm] = dict(inj=[list(c) for c in sc["inj"]], G=G, Ginf=Gi)
        print(f"  {nm:12s} {sc['inj']}: Gamma_120 = {G:7.1f}")
    # S2 dual ranking under this partition
    t, Q = S.trajectory(cal, S.SCN["S2"]["inj"], False)
    qpeak = Q.max(axis=0); dx2 = S.loss(cal, S.SCN["S2"]["inj"], False)[0]
    res["dual_S2"] = dict(by_peak=sorted(SECT, key=lambda s: -qpeak[idx[s]]),
                          by_loss=sorted(SECT, key=lambda s: -dx2[idx[s]]),
                          qpeak={s: float(qpeak[idx[s]]) for s in SECT}, dx={s: float(dx2[idx[s]]) for s in SECT})
    print("  S2 by peak:", res["dual_S2"]["by_peak"]); print("  S2 by loss:", res["dual_S2"]["by_loss"])
    out[part] = res
json.dump(out, open(os.path.join(HERE, "partition_sensitivity.json"), "w"), indent=2)
print("\npartition_sensitivity.json written.")
