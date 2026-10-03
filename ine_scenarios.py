#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Point losses, S2 dual ranking, exposure weights and exploratory Monte Carlo
envelopes on the INE TIO-2022 calibration. All scenario definitions come from
scenarios.py (single source of truth).

Monte Carlo (N=5000, seed 20260719): non-zero a*_ij x U[0.8,1.2]; x_i x
U[0.9,1.1]; q, T ~ Triangular(min, mode = point, max); heat multipliers
U[1.5,3.5] (AGU) and U[1.2,2.0] (AGR). Percentiles 5/50/95 are exploratory
'simulation envelopes', not confidence intervals. Dependence sweep: Gaussian
copula with equicorrelation r in {0, 0.5, 1} among all q and T of a scenario
(r = 1 is the comonotonic case). The random-number consumption order of the
reference run is preserved; the draws of the two-phase integrity scenario
(A1, two-phase) come from a separate generator (SeedSequence [seed, 1]), so
the envelopes of the transient scenarios are unchanged with respect to the
earlier run and to the stored results.

Rank frequencies are recorded for three prioritisation criteria among the
focal sectors: w_j (equal integrated inoperability), m_j = w_j / x_j (equal
integrated monetary withdrawal; Leontief output multiplier) and
v_j = tau_j (1 - a*_jj) w_j (equal initial inoperability at baseline recovery).

Outputs: ine_scenarios_results.json, mc_samples.npz. Figures are drawn by
make_figures.py from these files.
"""
import json
import os

import numpy as np
from scipy.stats import norm

import scenarios as S

HERE = os.path.dirname(os.path.abspath(__file__))
cal = S.load_cal("base")
SECT = cal["sectors"]; n = cal["n"]; idx = cal["idx"]
A0 = np.array(cal["Astar"]); x0 = np.array(cal["x"])
NZ = np.argwhere(A0 > 1e-12)
tau_base0 = S.tau_vector(cal)
FOCAL = S.focal(cal)
rng = np.random.default_rng(S.SEED)
rng_a1 = np.random.default_rng([S.SEED, 1])   # separate stream: two-phase draws do not touch the reference stream

# ------------------------------------------------- point results
print("=== BASELINE (INE TIO-2022 calibration, 8 sectors) ===")
print(f"rho(A*) = {cal['rho']:.4f}")
base = {}
for nm, sc in S.SCN.items():
    dx, G, Ginf = S.loss(cal, sc["inj"], sc["heat"])
    base[nm] = dict(G=G, Ginf=Ginf, dx=dx)
    print(f"  {nm}: Gamma(120)={G:8.1f}  Gamma_inf={Ginf:8.1f}  coverage={G/Ginf*100:6.2f}%")
a1d = S.A1_TWO_PHASE
G_a1d, q_td, rate = S.two_phase_loss(cal, a1d["depth"], a1d["t_d"], a1d["T_rem"], a1d["sector"])
base["A1"] = dict(G=G_a1d, Ginf=G_a1d, dx=None)
print(f"  A1 (two-phase, depth {a1d['depth']}, t_d {a1d['t_d']:.0f} d, T_rem {a1d['T_rem']:.0f} d): "
      f"Gamma_inf={G_a1d:8.1f}  q_AGR(t_d)={q_td:.3f}  steady loss rate {rate:.1f} EUR M/day")
mc = base["S4"]["G"] - base["S3"]["G"]
print(f"S4-S3 = {mc:.1f} M EUR = {mc/base['S5']['G']*100:.1f}% of S5; "
      f"multiplier = {base['S4']['G']/base['S3']['G']:.3f}")

L = np.linalg.inv(np.eye(n) - A0)
w0 = x0 @ L
m0 = w0 / x0                                        # Leontief output multipliers
v0 = tau_base0 * (1 - np.diag(A0)) * w0 / (365 * S.LN100)
print("\nOperator -> sector conversion (closed form, EUR M per unit of q):")
for nm in ("S1", "R1"):
    tgt, q, T = S.SCN[nm]["inj"][0]
    j = idx[tgt]
    per_unit = T * (1 - A0[j, j]) * w0[j] / (365 * S.LN100)
    print(f"  {nm} ({tgt}, T={T} d): {per_unit:8.1f} per unit of q; q={q} -> {per_unit*q:6.1f}")

t2, Q2 = S.trajectory(cal, S.SCN["S2"]["inj"], S.SCN["S2"]["heat"])
qpeak2 = Q2.max(axis=0); dx2 = base["S2"]["dx"]
print("\nDual ranking S2 (8 sectors):")
print("  by q_peak:", sorted(SECT, key=lambda s: -qpeak2[idx[s]]))
print("  by dx    :", sorted(SECT, key=lambda s: -dx2[idx[s]]))

A_f0 = (A0 * x0[:, None] / x0[None, :]).T           # A_fwd[j,i] = Z[i,j]/x_j
w_f0 = x0 @ np.linalg.inv(np.eye(n) - A_f0)
print("\nw backward (focal):", sorted(FOCAL, key=lambda s: -w0[idx[s]]))
print("m = w/x   (focal):", sorted(FOCAL, key=lambda s: -m0[idx[s]]))
print("v         (focal):", sorted(FOCAL, key=lambda s: -v0[idx[s]]))
print("w forward (focal):", sorted(FOCAL, key=lambda s: -w_f0[idx[s]]))

# ------------------------------------------------- Monte Carlo
def chol_equicorr(d, rho):
    C = np.full((d, d), rho); np.fill_diagonal(C, 1.0)
    return np.linalg.cholesky(C)

CHOL = {}
def couple(u, rho):
    """u: (ncomp, k) iid uniforms; returns uniforms coupled by an equicorrelated
    Gaussian copula of parameter rho (rho=1: comonotonic)."""
    if rho <= 0.0:
        return u
    if rho >= 1.0:
        return np.full_like(u, u.flat[0])
    key = (u.size, rho)
    if key not in CHOL:
        CHOL[key] = chol_equicorr(u.size, rho)
    z = CHOL[key] @ norm.ppf(u.ravel())
    return norm.cdf(z).reshape(u.shape)

def draw_inj(nm, sc, u):
    inj = []
    for c, (tgt, qpt, Tpt) in enumerate(sc["inj"]):
        r = S.RANGES[(nm, tgt)]
        inj.append((tgt, S.tri_ppf(u[c, 0], r["q"][0], qpt, r["q"][1]),
                         S.tri_ppf(u[c, 1], r["T"][0], Tpt, r["T"][1])))
    return inj

print(f"\n=== ENVELOPES (N={S.N_SAMPLES}, seed {S.SEED}, triangular, rho in {S.RHO_SWEEP}) ===")
G_samp = {rho: {nm: [] for nm in list(S.SCN) + ["A1"]} for rho in S.RHO_SWEEP}
rank_freq = {crit: {s: np.zeros(3) for s in FOCAL} for crit in ("w", "m", "v")}
rank1_fwd = {s: 0 for s in FOCAL}
struct = dict(A=[], x=[], hm=[])
rejected = 0
for it in range(S.N_SAMPLES):
    A = A0.copy()
    for (i, j) in NZ:
        A[i, j] *= rng.uniform(0.8, 1.2)
    if max(abs(np.linalg.eigvals(A))) >= 1:
        rejected += 1
        continue
    xh = x0 * rng.uniform(0.9, 1.1, size=n)
    hm = dict(AGU=rng.uniform(*S.HEAT_MULT_RANGE["AGU"]),
              AGR=rng.uniform(*S.HEAT_MULT_RANGE["AGR"]))
    struct["A"].append(A); struct["x"].append(xh); struct["hm"].append([hm["AGU"], hm["AGR"]])
    Ls = np.linalg.inv(np.eye(n) - A)
    ws = xh @ Ls
    crit = dict(w=ws, m=ws / xh, v=tau_base0 * (1 - np.diag(A)) * ws / (365 * S.LN100))
    for c, vals in crit.items():
        order = sorted(FOCAL, key=lambda s: -vals[idx[s]])
        for r, s in enumerate(order[:3]):
            rank_freq[c][s][r] += 1
    Af = (A * xh[:, None] / xh[None, :]).T
    if max(abs(np.linalg.eigvals(Af))) < 1:
        wf = xh @ np.linalg.inv(np.eye(n) - Af)
        rank1_fwd[max(FOCAL, key=lambda s: wf[idx[s]])] += 1
    for nm, sc in S.SCN.items():
        u = np.empty((len(sc["inj"]), 2))
        for c in range(len(sc["inj"])):
            u[c, 0] = rng.uniform(); u[c, 1] = rng.uniform()
        for rho in S.RHO_SWEEP:
            inj = draw_inj(nm, sc, couple(u, rho))
            _dx, G, _Gi = S.loss(cal, inj, sc["heat"], A=A, x=xh, heat_mult=hm)
            G_samp[rho][nm].append(G)
    # two-phase integrity scenario (depth, t_d, T_rem): separate generator
    u3 = rng_a1.uniform(size=(1, 3))
    for rho in S.RHO_SWEEP:
        uu = couple(u3, rho)[0]
        depth = S.tri_ppf(uu[0], a1d["depth_range"][0], a1d["depth"], a1d["depth_range"][1])
        t_d = S.tri_ppf(uu[1], a1d["t_d_range"][0], a1d["t_d"], a1d["t_d_range"][1])
        T_rem = S.tri_ppf(uu[2], a1d["T_rem_range"][0], a1d["T_rem"], a1d["T_rem_range"][1])
        g, _q, _r = S.two_phase_loss(cal, depth, t_d, T_rem, a1d["sector"], A=A, x=xh)
        G_samp[rho]["A1"].append(g)

nv = S.N_SAMPLES - rejected
print(f"valid samples: {nv} (rejected: {rejected})")
sweep = {}
for rho in S.RHO_SWEEP:
    sweep[rho] = {}
    for nm in G_samp[rho]:
        a = np.array(G_samp[rho][nm])
        p5, p50, p95 = np.percentile(a, [5, 50, 95])
        sweep[rho][nm] = dict(p5=float(p5), p50=float(p50), p95=float(p95), mean=float(a.mean()))
env = sweep[0.0]
print("Reference (rho = 0, independent):")
for nm in env:
    e = env[nm]
    print(f"  {nm:4s}: P5={e['p5']:8.1f}  P50={e['p50']:8.1f}  P95={e['p95']:8.1f}  (point {base[nm]['G']:.1f})")
print("Dependence sweep (P5 / P50 / P95):")
for nm in env:
    cells = "  ".join(f"rho={rho:.1f}: {sweep[rho][nm]['p5']:6.0f}/{sweep[rho][nm]['p50']:6.0f}/"
                      f"{sweep[rho][nm]['p95']:6.0f}" for rho in S.RHO_SWEEP)
    print(f"  {nm:4s}: {cells}")
for c in ("w", "m", "v"):
    print(f"\nRank stability, criterion {c} among focal sectors (rank 1/2/3, %):")
    for s in FOCAL:
        f = rank_freq[c][s] / nv * 100
        if f.sum() > 0:
            print(f"  {s}: {f[0]:5.1f} / {f[1]:5.1f} / {f[2]:5.1f}")
print("Rank-1 forward (focal, %):", {s: round(rank1_fwd[s] / nv * 100, 1) for s in FOCAL if rank1_fwd[s]})

out = dict(
    calibration="INE TIO-2022 (ine_calibration.json)",
    rho=cal["rho"],
    distribution="triangular(min, mode = point value, max) for q_i(0) and T_i; "
                 "uniform for A*, x-hat and heat multipliers",
    horizon_days=S.H, seed=S.SEED, n_samples=S.N_SAMPLES, n_valid=int(nv),
    scenarios={nm: dict(inj=[list(c) for c in sc["inj"]], heat=sc["heat"]) for nm, sc in S.SCN.items()},
    a1_two_phase=dict(a1d),
    ranges={f"{nm}/{tgt}": dict(q=list(r["q"]), T=list(r["T"])) for (nm, tgt), r in S.RANGES.items()},
    tau_base={s: S.TAU_BASE[s] for s in SECT}, heat_mult=S.HEAT_MULT, heat_mult_range=S.HEAT_MULT_RANGE,
    injection_anchors=S.INJECTION_ANCHORS,
    baseline={nm: dict(G=float(base[nm]["G"]), Ginf=float(base[nm]["Ginf"])) for nm in base},
    a1d_point=dict(G=G_a1d, q_td=q_td, steady_rate=rate,
                   ratio_to_transient=G_a1d / base["A1T"]["Ginf"]),
    marginal_climate=float(mc),
    envelopes={nm: {k: float(v) for k, v in env[nm].items()} for nm in env},
    dependence_sweep={f"{rho:.1f}": sweep[rho] for rho in S.RHO_SWEEP},
    dual_S2=dict(qpeak={s: float(qpeak2[idx[s]]) for s in SECT},
                 dx={s: float(dx2[idx[s]]) for s in SECT}),
    w_backward={s: float(w0[idx[s]]) for s in SECT},
    w_forward={s: float(w_f0[idx[s]]) for s in SECT},
    output_multiplier={s: float(m0[idx[s]]) for s in SECT},
    v_recovery_adjusted={s: float(v0[idx[s]]) for s in SECT},
    rank_freq_bwd={s: (rank_freq["w"][s] / nv * 100).tolist() for s in FOCAL},
    rank_freq_multiplier={s: (rank_freq["m"][s] / nv * 100).tolist() for s in FOCAL},
    rank_freq_recovery_adjusted={s: (rank_freq["v"][s] / nv * 100).tolist() for s in FOCAL},
    rank1_fwd={s: rank1_fwd[s] / nv * 100 for s in FOCAL},
)
with open(os.path.join(HERE, "ine_scenarios_results.json"), "w") as f:
    json.dump(out, f, indent=2)
np.savez_compressed(os.path.join(HERE, "mc_samples.npz"),
                    names=np.array(list(G_samp[0.0].keys())),
                    **{f"G_rho{rho:.1f}": np.array([G_samp[rho][nm] for nm in G_samp[rho]]) for rho in S.RHO_SWEEP},
                    A=np.array(struct["A"]), x=np.array(struct["x"]), hm=np.array(struct["hm"]))
print("\nine_scenarios_results.json and mc_samples.npz written.")
