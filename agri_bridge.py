#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Mechanism-to-injection bridge for the agricultural scenarios. The sectoral injection is decomposed as

    q_AGR(0) = pi x phi x h,

pi  = share of the sector's output produced by the exposed activity;
phi = fraction of that activity's facilities/area whose control systems are
      compromised in the incident;
h   = fraction of the exposed activity's output flow lost per unit time while
      the function is down (the operational loss).

Public anchors for pi (ratios only; the CEA year 2024 differs from the 2022
input-output table, so only shares are transferred):
  * Crop production 38,831 EUR M of an agricultural-branch output of 68,430
    EUR M in 2024 (MAPA, Renta Agraria 2024, first estimate, 16-12-2024).
  * Irrigation generates 65 % of the value of crop production; irrigated area
    3,713,936 ha, about 23 % of cultivated land (MAPA press release 9-8-2024,
    ESYRCE 2023).
  * Pigmeat: 11,030 EUR M in 2024, 16.3 % of final agricultural production and
    39.1 % of final livestock production (MAPA, El sector de la carne de cerdo
    en cifras 2024, estimate March 2025).
  * Poultry meat: 6 % of final agricultural production and 13.1 % of final
    livestock production in 2024 (MAPA figures as reported by Mercasa,
    Alimentacion en Espana; see the manuscript reference).
The script prints, for S3/S4, A1 and G1, the exposed share pi, the product
phi x h implied by the point injection and by its range, and example
combinations. It does not estimate phi or h: those require operator or
agronomic data and are flagged as pending. Writes agri_bridge.json.
"""
import json
import os

import scenarios as S

HERE = os.path.dirname(os.path.abspath(__file__))
crop_share = 38831.0 / 68430.0
irrig_share_of_crops = 0.65
pi_irr = crop_share * irrig_share_of_crops
pig_share = 0.163
poultry_share = 0.06
pi_intensive = pig_share + poultry_share

cases = {
    "S3/S4": dict(mechanism="irrigation SCADA/IoT compromise; pumping and water allocation halted",
                  exposed="irrigated crop production", pi=pi_irr, q=S.SCN["S3"]["inj"][0][1],
                  q_range=list(S.RANGES[("S3", "AGR")]["q"])),
    "A1": dict(mechanism="silent fertigation integrity drift (dosing setpoints)",
               exposed="irrigated crop production (fertigated subset not separately measured)", pi=pi_irr,
               q=S.A1_TWO_PHASE["depth"], q_range=list(S.A1_TWO_PHASE["depth_range"])),
    "G1": dict(mechanism="livestock climate/ventilation control compromise in intensive farms",
               exposed="intensive pig and poultry-meat production", pi=pi_intensive,
               q=S.SCN["G1"]["inj"][0][1], q_range=list(S.RANGES[("G1", "AGR")]["q"])),
}
print(f"pi_irr = crop share {crop_share:.3f} x irrigated share of crop value {irrig_share_of_crops:.2f} = {pi_irr:.3f}")
print(f"pi_intensive = pigs {pig_share:.3f} + poultry meat {poultry_share:.3f} = {pi_intensive:.3f} (eggs and other intensive activities not included)")
out = dict(anchors=dict(crop_share_2024=crop_share, irrigated_share_of_crop_value=irrig_share_of_crops,
                        pig_share_of_PFA_2024=pig_share, poultry_meat_share_of_PFA_2024=poultry_share,
                        pi_irr=pi_irr, pi_intensive=pi_intensive), cases={})
for nm, c in cases.items():
    prod = c["q"] / c["pi"]
    prod_range = [c["q_range"][0] / c["pi"], c["q_range"][1] / c["pi"]]
    examples = [dict(phi=phi, h=min(prod / phi, 1.0)) for phi in (0.5, 0.75, 1.0) if prod / phi <= 1.0]
    out["cases"][nm] = dict(**c, phi_times_h=prod, phi_times_h_range=prod_range, examples=examples)
    print(f"\n{nm}: {c['mechanism']}\n  exposed share pi = {c['pi']:.3f}; q = {c['q']} [{c['q_range'][0]}-{c['q_range'][1]}]"
          f" -> phi x h = {prod:.2f} [{prod_range[0]:.2f}-{prod_range[1]:.2f}]")
    for e in examples:
        print(f"    e.g. phi = {e['phi']:.2f} of exposed facilities compromised -> h = {e['h']:.2f} of their output flow lost while down")
json.dump(out, open(os.path.join(HERE, "agri_bridge.json"), "w"), indent=2)
print("\nagri_bridge.json written.")
