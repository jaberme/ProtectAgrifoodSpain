#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Single source of truth for the scenario set, parameter ranges, recovery
conventions and loss functions used by every script in this directory
(version of the paper sent to IJCIP). Scripts must import these definitions instead of
re-declaring them, so that manuscript, JSON outputs and figures cannot
diverge.

Model (Santos-Haimes demand-side DIIM, Lian & Haimes 2006 recovery
calibration):
    q_dot = K [A* q + c* - q],   K = diag(k_i),
    k_i   = ln(100) / (T_i (1 - a*_ii))        (isolated 99 % recovery in T_i)
    Gamma(H) = (1/365) x^T int_0^H q(t) dt     [EUR million, 2022 basic prices]
    Gamma_inf (transient shock, c* = 0) = (1/365) x^T (I-A*)^{-1} K^{-1} q(0)
              = sum_{j targeted} q_j(0) T_j (1-a*_jj) w_j / (365 ln 100),
    w_j = [x^T (I-A*)^{-1}]_j  (= x_j m_j, m_j the Leontief output multiplier).
"""
import json
import os

import numpy as np
from scipy.linalg import expm

HERE = os.path.dirname(os.path.abspath(__file__))
LN100 = float(np.log(100.0))
H = 120.0                      # reported horizon (days)
SEED = 20260719
N_SAMPLES = 5000
RHO_SWEEP = [0.0, 0.5, 1.0]    # Gaussian-copula correlation among q,T of a scenario

# Baseline reference recovery times tau_i (days to a 1 % residual in isolation).
# Scenario assumption; only the targeted sectors' values enter Gamma_inf.
TAU_BASE = {"AGR": 20., "IAB": 10., "RET": 7., "ENE": 4., "AGU": 8.,
            "LOG": 6., "ENV": 6., "ROE": 10.,
            # alternative partitions (Section on aggregation sensitivity)
            "RETW": 7., "RETR": 7.}
HEAT_MULT = dict(AGU=2.5, AGR=1.5)
HEAT_MULT_RANGE = dict(AGU=(1.5, 3.5), AGR=(1.2, 2.0))

# Point values = modes of the triangular exploratory distributions.
# Provenance: SA = scenario assumption; A = analogy with the public incident
# record (see the manuscript, Section on attack mechanisms).
SCN = {
    "S1": dict(inj=[("IAB", 0.02, 5)],  heat=False),   # q SA (share x halt) / T A
    "S2": dict(inj=[("IAB", 0.20, 14)], heat=False),   # q SA (stress case) / T A
    "S3": dict(inj=[("AGR", 0.15, 10)], heat=False),   # SA / SA
    "S4": dict(inj=[("AGR", 0.15, 25)], heat=True),    # SA / SA
    "S5": dict(inj=[("IAB", 0.20, 14), ("AGR", 0.15, 25)], heat=True),
    "A1T": dict(inj=[("AGR", 0.10, 30)], heat=False),  # transient forcing comparison (A1-T)
    "G1": dict(inj=[("AGR", 0.12, 8)],  heat=False),   # SA / SA
    "R1": dict(inj=[("RET", 0.04, 9)],  heat=False),   # q SA (share x halt) / T A
    "C1": dict(inj=[("AGR", 0.15, 25), ("IAB", 0.20, 14), ("RET", 0.04, 9)],
               heat=True),                             # components = S4, S2, R1
}
RANGES = {
    ("S1", "IAB"): dict(q=(0.005, 0.03), T=(3, 10)),
    ("S2", "IAB"): dict(q=(0.10, 0.25), T=(7, 45)),
    ("S3", "AGR"): dict(q=(0.10, 0.20), T=(7, 14)),
    ("S4", "AGR"): dict(q=(0.10, 0.20), T=(15, 35)),
    ("S5", "IAB"): dict(q=(0.10, 0.25), T=(7, 45)),
    ("S5", "AGR"): dict(q=(0.10, 0.20), T=(15, 35)),
    ("A1T", "AGR"): dict(q=(0.05, 0.15), T=(21, 45)),
    ("G1", "AGR"): dict(q=(0.08, 0.15), T=(5, 12)),
    ("R1", "RET"): dict(q=(0.01, 0.05), T=(5, 45)),
    ("C1", "AGR"): dict(q=(0.10, 0.20), T=(15, 35)),
    ("C1", "IAB"): dict(q=(0.10, 0.25), T=(7, 45)),
    ("C1", "RET"): dict(q=(0.01, 0.05), T=(5, 45)),
}
for _nm, _sc in SCN.items():
    for _tgt, _q, _T in _sc["inj"]:
        _r = RANGES[(_nm, _tgt)]
        assert _r["q"][0] <= _q <= _r["q"][1] and _r["T"][0] <= _T <= _r["T"][1], (_nm, _tgt)

# Principal representation of the silent integrity attack (A1, two-phase):
# sustained depth c* in AGR until detection at t_d, then transient recovery
# with reference remediation time T_rem. The depth range is that of the
# transient A1-T; the detection-latency range reuses the 'late detection'
# reference-time range of the transient A1-T; the remediation range reuses the
# irrigation SCADA restoration range of S3 (same asset class).
A1_TWO_PHASE = dict(sector="AGR", depth=0.10, depth_range=(0.05, 0.15),
                    t_d=30.0, t_d_range=(21.0, 45.0),
                    T_rem=10.0, T_rem_range=(7.0, 14.0))

# Public anchors of the operator -> sector conversion q_i(0) = sigma_o h_o (1 - s_o).
INJECTION_ANCHORS = dict(
    IAB=dict(sector_output_MEUR=160266.0,
             largest_operator=dict(name="Vall Companys", turnover_2024_MEUR=4163.0),
             next_largest_shares=(0.016, 0.021),
             published_top10=dict(source="Economia 3 ranking, turnover 2023",
                                  turnover_MEUR=27541.0, share=0.172),
             meat_products_output_2022_MEUR=44333.2, meat_share_of_IAB=0.277,
             S1=dict(sigma=0.02, h=1.0, q=0.02, q_range=(0.005, 0.03)),
             S2=dict(interpretation="sector-wide stress: exceeds the published top-10 halted; ~72 % of meat-product output",
                     q=0.20, q_range=(0.10, 0.25))),
    RET=dict(sector_output_MEUR=245096.4,
             output_is="trade services output (wholesale 146297.7 + retail 98798.7), mainly trade margins",
             agrifood_margins_MEUR=60618.4, agrifood_share_of_output=0.247,
             largest_operator=dict(name="Mercadona", net_sales_spain_2025_MEUR=36270.0,
                                   ine_rates=(0.271, 0.284), share_of_RET=(0.040, 0.042),
                                   margin_basis_output_MEUR=(9833.0, 10298.0)),
             R1=dict(sigma=0.040, h=1.0, q=0.04, q_range=(0.01, 0.05)),
             previous_R1=dict(q=0.18, margins_MEUR=44117.0, largest_grocer_equivalents=(4.3, 4.5),
                              share_of_agrifood_margins=0.728)),
)

CALIBRATION_FILES = {"base": "ine_calibration.json",
                     "split": "ine_calibration_split.json",
                     "envp": "ine_calibration_envp.json"}


def load_cal(name="base"):
    """Load a calibration JSON produced by ine_calibration.py."""
    cal = json.load(open(os.path.join(HERE, CALIBRATION_FILES[name])))
    cal["idx"] = {s: i for i, s in enumerate(cal["sectors"])}
    cal["n"] = len(cal["sectors"])
    return cal


def tau_vector(cal, tau_base=None):
    tb = tau_base or TAU_BASE
    return np.array([tb[s] for s in cal["sectors"]], float)


def scenario_tau(cal, inj, heat, tau_base_vec=None, heat_mult=None):
    """Reference-time vector of a scenario: heat multipliers on non-targeted
    climate-exposed sectors, explicit T_i on the targeted sectors."""
    tau = (tau_vector(cal) if tau_base_vec is None else np.array(tau_base_vec, float)).copy()
    hm = heat_mult or HEAT_MULT
    idx = cal["idx"]
    if heat:
        for s, m in hm.items():
            if s in idx:
                tau[idx[s]] *= m
    for tgt, _q, T in inj:
        tau[idx[tgt]] = T
    return tau


def K_matrix(A, tau):
    return np.diag(LN100 / (tau * (1.0 - np.diag(A))))


def q0_vector(cal, inj):
    q0 = np.zeros(cal["n"])
    for tgt, q, _T in inj:
        q0[cal["idx"][tgt]] = q
    return q0


def loss(cal, inj, heat, A=None, x=None, tau_base_vec=None, heat_mult=None, Hh=H):
    """Return (dx_H, Gamma_H, Gamma_inf) for a transient scenario."""
    A = np.array(cal["Astar"]) if A is None else A
    x = np.array(cal["x"]) if x is None else x
    n = cal["n"]
    q0 = q0_vector(cal, inj)
    tau = scenario_tau(cal, inj, heat, tau_base_vec, heat_mult)
    M = K_matrix(A, tau) @ (np.eye(n) - A)
    Minv = np.linalg.inv(M)
    W = Minv @ (np.eye(n) - expm(-M * Hh)) @ q0
    dx = x / 365.0 * W
    return dx, float(dx.sum()), float((x / 365.0 * (Minv @ q0)).sum())


def closed_form_terms(cal, inj, heat, A=None, x=None):
    """Gamma_j of Corollary (linearity): per-target infinite-horizon contributions."""
    A = np.array(cal["Astar"]) if A is None else A
    x = np.array(cal["x"]) if x is None else x
    w = x @ np.linalg.inv(np.eye(cal["n"]) - A)
    tau = scenario_tau(cal, inj, heat)
    idx = cal["idx"]
    return {tgt: float(q * tau[idx[tgt]] * (1 - A[idx[tgt], idx[tgt]]) * w[idx[tgt]] / (365 * LN100))
            for tgt, q, _T in inj}


def trajectory(cal, inj, heat, Hh=H, steps=1200, A=None):
    A = np.array(cal["Astar"]) if A is None else A
    n = cal["n"]
    q0 = q0_vector(cal, inj)
    M = K_matrix(A, scenario_tau(cal, inj, heat)) @ (np.eye(n) - A)
    t = np.linspace(0, Hh, steps)
    Q = np.array([expm(-M * ta) @ q0 for ta in t])
    return t, Q


def two_phase_loss(cal, depth, t_d, T_rem, sector="AGR", A=None, x=None,
                   tau_base_vec=None):
    """Silent integrity attack: sustained c* of given depth in `sector` until
    detection at t_d (phase 1, baseline recovery), then transient recovery with
    the sector's reference time replaced by T_rem (phase 2). Returns
    (Gamma_inf, q_sector(t_d), steady loss rate EUR M/day)."""
    A = np.array(cal["Astar"]) if A is None else A
    x = np.array(cal["x"]) if x is None else x
    n = cal["n"]; idx = cal["idx"]
    tau1 = (tau_vector(cal) if tau_base_vec is None else np.array(tau_base_vec, float)).copy()
    cstar = np.zeros(n); cstar[idx[sector]] = depth
    L = np.linalg.inv(np.eye(n) - A)
    qstar = L @ cstar
    M1 = K_matrix(A, tau1) @ (np.eye(n) - A)
    E1 = expm(-M1 * t_d)
    q_td = (np.eye(n) - E1) @ qstar
    W1 = qstar * t_d - np.linalg.inv(M1) @ (np.eye(n) - E1) @ qstar
    tau2 = tau1.copy(); tau2[idx[sector]] = T_rem
    M2 = K_matrix(A, tau2) @ (np.eye(n) - A)
    W2 = np.linalg.solve(M2, q_td)
    return float(x @ (W1 + W2) / 365.0), float(q_td[idx[sector]]), float(x @ qstar / 365.0)


def tri_ppf(u, lo, mode, hi):
    """Inverse CDF of the triangular distribution (min lo, mode, max hi)."""
    fc = (mode - lo) / (hi - lo)
    if u < fc:
        return lo + np.sqrt(u * (hi - lo) * (mode - lo))
    return hi - np.sqrt((1.0 - u) * (hi - lo) * (hi - mode))


def focal(cal):
    return [s for s in cal["sectors"] if s != "ROE"]


if __name__ == "__main__":
    cal = load_cal()
    print("Scenario point losses (Gamma_120 / Gamma_inf, EUR M):")
    for nm, sc in SCN.items():
        _dx, G, Gi = loss(cal, sc["inj"], sc["heat"])
        print(f"  {nm}: {G:8.1f} / {Gi:8.1f}")
    g, qd, rate = two_phase_loss(cal, **{k: A1_TWO_PHASE[k] for k in ("depth", "t_d", "T_rem")})
    print(f"  A1 (two-phase): {g:8.1f}  q_AGR(t_d)={qd:.3f}  rate={rate:.1f} EUR M/day")
