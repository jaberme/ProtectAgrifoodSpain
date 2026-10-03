#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
External contrast of the reference-time <-> direct-loss relation.

Under the exponential convention, an isolated operator fully halted (h_o = 1)
with reference time T loses T/ln100 days of output ('full-stop-equivalent
days', D_eq). Two documented incidents give D_eq independently of the model:
  JBS (May-June 2021): 'less than one day of food production lost', all
    facilities fully operational after four days (JBS press release, cited in
    the manuscript). D_eq < 1 day for a plant-level ransomware outage.
  Maersk / NotPetya (2017), as compiled by Welburn and Strong (2022, Table II
    and Section 4.2): 2017 revenue 30,945 USD M; 10 days to rebuild IT
    systems, about two months to full recovery; 250-300 USD M of lost revenue.
    Their model writes the direct loss as (y_f/365) M_f Lambda, i.e. M_f Lambda
    is D_eq; with Lambda = 10 d they back out M_f in [0.30, 0.35], whereas the
    sector-level resilience of Rose et al. (2007), M_f = 0.052, would give 44
    USD M. Our T = D_eq ln100.
Also: the fraction of each triangular T range below 7 and 30 days against the
Sophos 2025 survey (53 % of victims fully recovered within a week, 81 % within
a month). Writes external_contrast.json.
"""
import json
import os

import numpy as np

import scenarios as S

HERE = os.path.dirname(os.path.abspath(__file__))
LN = S.LN100
maersk = dict(revenue_usdM=30945.0, loss_usdM=(250.0, 300.0), it_rebuild_days=10, full_recovery_days_approx=60,
              ws_resilience_fit=(0.30, 0.35), rose_sector_resilience=0.052, ws_lambda=10)
deq = tuple(l / (maersk["revenue_usdM"] / 365) for l in maersk["loss_usdM"])
T_maersk = tuple(d * LN for d in deq)
rose_direct = maersk["revenue_usdM"] / 365 * maersk["rose_sector_resilience"] * maersk["ws_lambda"]
print(f"Maersk: D_eq = {deq[0]:.2f}-{deq[1]:.2f} d  ->  T = {T_maersk[0]:.1f}-{T_maersk[1]:.1f} d "
      f"(IT rebuild 10 d; full recovery ~60 d); M_f Lambda check: {deq[0]/10:.3f}-{deq[1]/10:.3f} "
      f"(W&S report 0.30-0.35); Rose sector resilience would give {rose_direct:.1f} USD M direct")
jbs = dict(production_lost_days_upper=1.0, fully_operational_days=4)
rows = {}
for nm in ("S1", "S2", "R1"):
    tgt, q, T = S.SCN[nm]["inj"][0]
    lo, hi = S.RANGES[(nm, tgt)]["T"]
    rows[nm] = dict(T_mode=T, T_range=[lo, hi], Deq_mode=T / LN, Deq_range=[lo / LN, hi / LN])
    print(f"{nm}: T mode {T} [{lo}-{hi}] d -> D_eq {T/LN:.2f} [{lo/LN:.2f}-{hi/LN:.2f}] d")

def tri_cdf(v, lo, mode, hi):
    if v <= lo: return 0.0
    if v >= hi: return 1.0
    if v <= mode: return (v - lo) ** 2 / ((hi - lo) * (mode - lo))
    return 1 - (hi - v) ** 2 / ((hi - lo) * (hi - mode))
sophos = dict(within_week=0.53, within_month=0.81)
cdf = {}
for nm in ("S1", "S2", "R1"):
    tgt, q, T = S.SCN[nm]["inj"][0]
    lo, hi = S.RANGES[(nm, tgt)]["T"]
    cdf[nm] = dict(below_7=tri_cdf(7, lo, T, hi), below_30=tri_cdf(30, lo, T, hi))
    print(f"{nm}: P(T<=7 d) = {cdf[nm]['below_7']:.3f}, P(T<=30 d) = {cdf[nm]['below_30']:.3f} "
          f"(survey: 0.53 within a week, 0.81 within a month)")
# does the Maersk-implied T fall inside the declared ranges?
inside = {nm: bool(rows[nm]["T_range"][0] <= T_maersk[0] and T_maersk[1] <= rows[nm]["T_range"][1]) for nm in rows}
ratio_to_mode = {nm: [T_maersk[0] / rows[nm]["T_mode"], T_maersk[1] / rows[nm]["T_mode"]] for nm in rows}
print("Maersk-implied T inside declared range:", inside, " ratio to mode:", {k: [round(a, 2), round(b, 2)] for k, (a, b) in ratio_to_mode.items()})
print(f"JBS: S1 mode implies D_eq = {5/LN:.2f} d vs documented < 1 d (+{100*(5/LN-1):.0f} % above the stated upper bound); "
      f"S1 range gives {3/LN:.2f}-{10/LN:.2f} d")
json.dump(dict(maersk=dict(**maersk, Deq=list(deq), T_implied=list(T_maersk), rose_direct_usdM=rose_direct),
               jbs=dict(**jbs, S1_Deq_mode=5 / LN, S1_Deq_range=[3 / LN, 10 / LN]),
               scenarios=rows, triangular_cdf=cdf, sophos=sophos, maersk_inside_range=inside,
               maersk_ratio_to_mode=ratio_to_mode),
          open(os.path.join(HERE, "external_contrast.json"), "w"), indent=2)
print("external_contrast.json written.")
