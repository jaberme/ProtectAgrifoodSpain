#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
What the exploratory envelopes depend on.

(a) Marginal form: the reference envelopes use triangular(min, mode, max) for
    q and T. They are recomputed with uniform(min, max) and PERT (beta with
    lambda = 4, same min/mode/max) marginals, reusing the stored structural
    draws (A*, x-hat, heat multipliers) of the reference run.
(b) Source of dispersion (one-at-a-time): depth only (q drawn, T and structure
    at point), recovery only (T drawn), structure only (A*, x-hat, heat drawn).
    For a single-target transient scenario Gamma_inf = kappa_j(A*, x) q_j T_j,
    so Var[log Gamma] = Var[log q] + Var[log T] + Var[log kappa] exactly under
    independence; shares are reported on that scale. Compounds and the
    two-phase A1 are reported with the same OAT design (approximate).
(c) Convergence: split-half percentiles of the reference run and three further
    seeds; the maximum relative deviation of P5/P50/P95 is reported.
Writes uncertainty_decomposition.json.
"""
import json
import os

import numpy as np
from scipy.stats import beta as beta_dist

import scenarios as S

HERE = os.path.dirname(os.path.abspath(__file__))
cal = S.load_cal("base")
SECT = cal["sectors"]; n = cal["n"]; idx = cal["idx"]
A0 = np.array(cal["Astar"]); x0 = np.array(cal["x"])
NZ = np.argwhere(A0 > 1e-12)
mc = np.load(os.path.join(HERE, "mc_samples.npz"))
names = list(mc["names"]); As, xs, hms = mc["A"], mc["x"], mc["hm"]
G_ref = {nm: mc["G_rho0.0"][names.index(nm)] for nm in names}
a1 = S.A1_TWO_PHASE
ALL = list(S.SCN) + ["A1"]

def pert_ppf(u, lo, mode, hi, lam=4.0):
    a_ = 1 + lam * (mode - lo) / (hi - lo); b_ = 1 + lam * (hi - mode) / (hi - lo)
    return lo + (hi - lo) * beta_dist.ppf(u, a_, b_)

def uni_ppf(u, lo, mode, hi):
    return lo + u * (hi - lo)

def draw_all(ppf, rng, Astruct, xstruct, hmstruct, vary=("q", "T", "S")):
    """One full pass over the scenarios; returns dict of sample arrays."""
    out = {nm: np.empty(S.N_SAMPLES) for nm in ALL}
    for it in range(S.N_SAMPLES):
        A = Astruct[it] if "S" in vary else A0
        xh = xstruct[it] if "S" in vary else x0
        hm = dict(AGU=hmstruct[it][0], AGR=hmstruct[it][1]) if "S" in vary else S.HEAT_MULT
        for nm, sc in S.SCN.items():
            inj = []
            for tgt, qpt, Tpt in sc["inj"]:
                r = S.RANGES[(nm, tgt)]
                uq, uT = rng.uniform(), rng.uniform()
                qq = ppf(uq, r["q"][0], qpt, r["q"][1]) if "q" in vary else qpt
                TT = ppf(uT, r["T"][0], Tpt, r["T"][1]) if "T" in vary else Tpt
                inj.append((tgt, qq, TT))
            out[nm][it] = S.loss(cal, inj, sc["heat"], A=A, x=xh, heat_mult=hm)[1]
        u = rng.uniform(size=3)
        d = ppf(u[0], *a1["depth_range"][:1], a1["depth"], a1["depth_range"][1]) if "q" in vary else a1["depth"]
        td = ppf(u[1], a1["t_d_range"][0], a1["t_d"], a1["t_d_range"][1]) if "T" in vary else a1["t_d"]
        tr = ppf(u[2], a1["T_rem_range"][0], a1["T_rem"], a1["T_rem_range"][1]) if "T" in vary else a1["T_rem"]
        out["A1"][it] = S.two_phase_loss(cal, d, td, tr, a1["sector"], A=A, x=xh)[0]
    return out

def pct(a):
    p = np.percentile(a, [5, 50, 95]); return dict(p5=float(p[0]), p50=float(p[1]), p95=float(p[2]))

res = dict(reference={nm: pct(G_ref[nm]) for nm in ALL})
# (a) marginals
for label, ppf, seedtag in (("uniform", uni_ppf, 2), ("pert", pert_ppf, 3)):
    rng = np.random.default_rng([S.SEED, seedtag])
    smp = draw_all(ppf, rng, As, xs, hms)
    res[label] = {nm: pct(smp[nm]) for nm in ALL}
    print(f"\n{label} marginals (P5/P50/P95) vs triangular reference:")
    for nm in ALL:
        e, t = res[label][nm], res["reference"][nm]
        print(f"  {nm:4s}: {e['p5']:7.0f}/{e['p50']:7.0f}/{e['p95']:7.0f}   ref {t['p5']:7.0f}/{t['p50']:7.0f}/{t['p95']:7.0f}")
# (b) one at a time (same uniforms for the three variants)
oat = {}
for label, vary in (("depth", ("q",)), ("recovery", ("T",)), ("structure", ("S",)), ("all", ("q", "T", "S"))):
    rng = np.random.default_rng([S.SEED, 4])
    oat[label] = draw_all(S.tri_ppf, rng, As, xs, hms, vary=vary)
res["oat"] = {}
print("\nOne-at-a-time (P5/P95 and share of Var[log Gamma]):")
for nm in ALL:
    tot = np.var(np.log(oat["all"][nm]))
    parts = {k: float(np.var(np.log(oat[k][nm]))) for k in ("depth", "recovery", "structure")}
    res["oat"][nm] = dict(**{k: pct(oat[k][nm]) for k in ("depth", "recovery", "structure", "all")},
                          var_log_total=float(tot), var_log_parts=parts,
                          shares={k: v / sum(parts.values()) for k, v in parts.items()},
                          sum_parts_over_total=sum(parts.values()) / tot)
    sh = res["oat"][nm]["shares"]
    print(f"  {nm:4s}: depth {oat['depth'][nm].min():6.0f}-{np.percentile(oat['depth'][nm],95):6.0f} | "
          f"recovery P5/P95 {res['oat'][nm]['recovery']['p5']:6.0f}/{res['oat'][nm]['recovery']['p95']:6.0f} | "
          f"structure P5/P95 {res['oat'][nm]['structure']['p5']:6.0f}/{res['oat'][nm]['structure']['p95']:6.0f} | "
          f"shares q {100*sh['depth']:4.1f} % T {100*sh['recovery']:4.1f} % S {100*sh['structure']:4.1f} % "
          f"(sum/total {res['oat'][nm]['sum_parts_over_total']:.3f})")
# (c) convergence
halves = {nm: (pct(G_ref[nm][:S.N_SAMPLES // 2]), pct(G_ref[nm][S.N_SAMPLES // 2:])) for nm in ALL}
seeds = {}
for tag in (11, 12, 13):
    rng = np.random.default_rng([S.SEED, tag])
    # fresh structural draws as in ine_scenarios.py, then triangular q,T
    Aset, xset, hset = [], [], []
    for it in range(S.N_SAMPLES):
        A = A0.copy()
        for (i, j) in NZ: A[i, j] *= rng.uniform(0.8, 1.2)
        Aset.append(A); xset.append(x0 * rng.uniform(0.9, 1.1, size=n))
        hset.append([rng.uniform(*S.HEAT_MULT_RANGE["AGU"]), rng.uniform(*S.HEAT_MULT_RANGE["AGR"])])
    seeds[tag] = {nm: pct(v) for nm, v in draw_all(S.tri_ppf, rng, np.array(Aset), np.array(xset), np.array(hset)).items()}
conv = {}
print("\nConvergence: max relative deviation of P5/P50/P95 (split halves; three further seeds):")
for nm in ALL:
    ref = res["reference"][nm]
    dh = max(abs(halves[nm][k][p] - ref[p]) / ref[p] for k in (0, 1) for p in ("p5", "p50", "p95"))
    ds = max(abs(seeds[t][nm][p] - ref[p]) / ref[p] for t in seeds for p in ("p5", "p50", "p95"))
    conv[nm] = dict(split_half_max_rel_dev=float(dh), seeds_max_rel_dev=float(ds),
                    halves=[halves[nm][0], halves[nm][1]], seeds={str(t): seeds[t][nm] for t in seeds})
    print(f"  {nm:4s}: halves {100*dh:4.1f} %   seeds {100*ds:4.1f} %")
res["convergence"] = conv
res["convergence_summary"] = dict(max_split_half=max(c["split_half_max_rel_dev"] for c in conv.values()),
                                  max_seeds=max(c["seeds_max_rel_dev"] for c in conv.values()))
print("overall max:", {k: f"{100*v:.1f} %" for k, v in res["convergence_summary"].items()})
json.dump(res, open(os.path.join(HERE, "uncertainty_decomposition.json"), "w"), indent=2)
print("uncertainty_decomposition.json written.")
