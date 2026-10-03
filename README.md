<p align="center">
  <img src="agri-food-cyber-climate-banner.png" alt="Cyber attack on irrigation control cascading through Spain's agri-food chain: farm, food industry, logistics, retail, under heatwave conditions" width="100%">
</p>

# Dynamic inoperability analysis of Spain's agri-food system: reproduction set

Code and data that reproduce every number, table and figure of

> **Quantifying Cyber-Induced Cascades under Climate-Conditioned Recovery to
> Prioritise Critical-Infrastructure Defence: A Dynamic Inoperability Analysis
> of Spain's Agri-Food System.**
> D.A. Perdomo (Universidad del Valle), A. Pérez-y-Soto-Dominguez (Universidad
> Nacional de Colombia), J.A. Álvarez-Bermejo (Universidad de Almería,
> corresponding author). Submitted to the *International Journal of Critical
> Infrastructure Protection*.

The model is the demand-side dynamic inoperability input–output model (DIIM)
of Santos and Haimes, calibrated on the official 2022 Spanish input–output
tables (INE, Revisión Estadística 2024) aggregated to eight sectors:
agriculture (AGR), food industry (IAB), trade (RET), energy (ENE), water (AGU),
logistics (LOG), packaging (ENV) and the rest of the economy (ROE). Nine cyber
scenarios (plus a transient comparison case), some under heatwave or drought conditions, give a scenario-conditioned
systemic loss Γ in EUR million, exploratory Monte Carlo envelopes, and a
ranking of sectors for defensive prioritisation.

All results are **scenario-conditioned**: the calibration is empirical, the
shock depths, recovery times and climate multipliers are declared scenario
assumptions. Nothing here is a prediction.

---

## Quick start

```bash
git clone <this repository> repro
cd repro
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python3 run_all.py              # about 50 s; ends with "PIPELINE COMPLETED"
```

`run_all.py` runs the sixteen stages below in dependency order and stops at
the first failure. `diim.py` is a verification stage: it exits with code 1 if
any point loss deviates from the stored `ine_scenarios_results.json`, so a
stale or modified reproduction set cannot pass silently.

Figures are written to `../figs/` (the directory **next to** the clone; it is
created if missing). The option `run_all.py --audit` additionally runs the
manuscript audit `../audit.py`, which is distributed with the manuscript
sources, not with this repository.

Tested on Linux with Python 3.12.3 and the versions pinned in
`requirements.txt` (numpy 1.26.4, scipy 1.11.4, matplotlib 3.6.3,
openpyxl 3.1.5). A full run on 3 October 2026 regenerated the committed JSON
files byte for byte.

---

## How the pipeline fits together

```
 data/cne_tio_22.xlsx ──► ine_calibration.py ──► ine_calibration.json ─┐  (+ _split, _envp)
 (INE input–output 2022)   --partition base|split|envp                 │
                                                                       │
 data/cne_tod_22.xlsx ──► ine_trade_margins.py ──► ine_trade_margins.json  (RET anchors)
                                                                       │
                     scenarios.py  ◄── single source of truth ─────────┤
                     (scenarios, ranges, recovery convention,          │
                      loss functions, two-phase forcing)               │
                            │                                          ▼
                            ├──► ine_scenarios.py ──► ine_scenarios_results.json, mc_samples.npz
                            ├──► diim.py             (verification only, exit 1 on mismatch)
                            ├──► static_vs_dynamic.py ──────────► criteria.json
                            ├──► partition_sensitivity.py ──────► partition_sensitivity.json
                            ├──► recovery_shape.py ─────────────► recovery_shape.json
                            ├──► uncertainty_decomposition.py ──► uncertainty_decomposition.json
                            ├──► decision_example.py ───────────► decision_example.json
                            ├──► external_contrast.py ──────────► external_contrast.json
                            ├──► agri_bridge.py ────────────────► agri_bridge.json
                            ├──► extensions_L2_L7.py ───────────► extensions.json
                            └──► regional_reading.py ───────────► regional_reading.json
                                                                       │
                     make_figures.py  (reads only the JSON files) ◄────┘
                            └──► ../figs/fig_{gamma,cascade,dualrank,criteria,shapes,uncertainty}.png
```

Only `ine_calibration.py` and `ine_trade_margins.py` read the INE workbooks.
Every other script reads `scenarios.py` and the JSON files, so manuscript,
results and figures cannot diverge.

---

## Model in five lines

| | |
|---|---|
| Interdependence | a*<sub>ij</sub> = Z<sub>ij</sub> / x<sub>i</sub>, share of supplier *i*'s sales absorbed by customer *j* |
| Recovery | k<sub>i</sub> = ln 100 / (T<sub>i</sub> (1 − a*<sub>ii</sub>)): an isolated sector keeps 1 % of its inoperability after T<sub>i</sub> days |
| Dynamics | q̇ = K [A* q + c* − q], with K = diag(k<sub>i</sub>) |
| Loss | Γ(H) = (1/365) xᵀ ∫₀ᴴ q(t) dt, EUR million at 2022 basic prices, H = 120 days |
| Closed form | Γ<sub>∞</sub> = Σ<sub>j targeted</sub> q<sub>j</sub>(0) T<sub>j</sub> (1 − a*<sub>jj</sub>) w<sub>j</sub> / (365 ln 100), with w<sub>j</sub> = [xᵀ (I − A*)⁻¹]<sub>j</sub> |

---

## Scenarios (`scenarios.py`)

| Scenario | Target(s) | Heat | q(0) point [range] | T days [range] |
|---|---|---|---|---|
| S1 Single food-industry operator at a standstill | IAB | no | 0.02 [0.005, 0.03] | 5 [3, 10] |
| S2 Coordinated industry campaign (harvest; sector-wide stress) | IAB | no | 0.20 [0.10, 0.25] | 14 [7, 45] |
| S3 Irrigation SCADA/IoT compromise | AGR | no | 0.15 [0.10, 0.20] | 10 [7, 14] |
| S4 Irrigation SCADA/IoT compromise, heatwave / scarcity | AGR | yes | 0.15 [0.10, 0.20] | 25 [15, 35] |
| S5 Compound: industry + irrigation, heatwave / scarcity | IAB + AGR | yes | 0.20 / 0.15 | 14 / 25 |
| A1 Silent fertigation integrity drift, two-phase (sustained depth c̄ until detection at t<sub>d</sub>, then remediation T<sub>rem</sub>) | AGR | no | c̄ = 0.10 [0.05, 0.15] | t<sub>d</sub> = 30 [21, 45]; T<sub>rem</sub> = 10 [7, 14] |
| A1-T Transient comparison of A1 | AGR | no | 0.10 [0.05, 0.15] | 30 [21, 45] |
| G1 Livestock climate/ventilation control | AGR | no | 0.12 [0.08, 0.15] | 8 [5, 12] |
| R1 Retail ransomware: ERP, distribution centres, cold chain | RET | no | 0.04 [0.01, 0.05] | 9 [5, 45] |
| C1 Mediterranean-arc motivated compound (harvest + heat) | AGR + IAB + RET | yes | 0.15 / 0.20 / 0.04 | 25 / 14 / 9 |

Point values are the modes of triangular exploratory distributions. Heat
multiplies the baseline recovery time of AGU by 2.5 and of AGR by 1.5.
Baseline recovery times τ = (20, 10, 7, 4, 8, 6, 6, 10) days for
(AGR, IAB, RET, ENE, AGU, LOG, ENV, ROE).

---

## Stage by stage

| # | Script | What it does | Writes |
|---|---|---|---|
| 1 | `ine_calibration.py --partition base\|split\|envp` | Reads Tables 1, 2 and 5 of the INE workbook, aggregates 65 products to 8 sectors by summing flows, checks accounting identities and ρ(A*) < 1. `split` separates wholesale (RETW) and retail (RETR); `envp` restricts packaging to rubber and plastics | `ine_calibration.json`, `ine_calibration_split.json`, `ine_calibration_envp.json`, `ine_Astar_8x8.csv`, `ine_x_8.csv` |
| 2 | `ine_trade_margins.py` | Trade-services output, net trade margins and agri-food margins from the supply table; the largest grocer's share of RET (4.0–4.2 %), which fixes q<sub>RET</sub>(0) = 0.04 in R1 | `ine_trade_margins.json` |
| 3 | `ine_scenarios.py` | Point losses Γ(120) and Γ<sub>∞</sub>; S2 dual ranking; exposure weights; Monte Carlo (N = 5000, seed 20260719): non-zero a*<sub>ij</sub> × U[0.8, 1.2], x<sub>i</sub> × U[0.9, 1.1], triangular q and T, heat multipliers U[1.5, 3.5] and U[1.2, 2.0]; Gaussian-copula dependence sweep ρ ∈ {0, 0.5, 1}; rank frequencies under three criteria | `ine_scenarios_results.json`, `mc_samples.npz` (structural draws, reused by later stages) |
| 4 | `diim.py` | Verification: matrix-exponential trajectories against an independent ODE integrator; loss identities; linearity in T (S4/S3 = 2.5); additivity of C1 at infinite horizon; forward invariance of [0, 1]ⁿ; equality with the stored baseline. **Exit 1 on any mismatch** | nothing |
| 5 | `static_vs_dynamic.py` | Three prioritisation criteria among focal sectors: w<sub>j</sub>, m<sub>j</sub> = w<sub>j</sub>/x<sub>j</sub> (Leontief output multiplier), v<sub>j</sub> = τ<sub>j</sub>(1 − a*<sub>jj</sub>)w<sub>j</sub> | `criteria.json` |
| 6 | `partition_sensitivity.py` | Criteria and losses under the `base`, `split` and `envp` calibrations; R1 re-specified on RETR under `split` | `partition_sensitivity.json` |
| 7 | `recovery_shape.py` | Exponential, plateau, linear and stepped recovery paths with the same q(0); exact area ratios and DIIM feedback | `recovery_shape.json` |
| 8 | `uncertainty_decomposition.py` | Envelopes under uniform and PERT marginals; one-at-a-time variance shares (depth, recovery, structure); split-half and extra-seed convergence. Slowest stage (≈ 32 s) | `uncertainty_decomposition.json` |
| 9 | `decision_example.py` | Two assumed protection measures on S2 (depth −10 %, reference time 14 → 12 d) and their cross term | `decision_example.json` |
| 10 | `external_contrast.py` | Full-stop-equivalent days of JBS 2021 and Maersk/NotPetya 2017 against the reference-time convention; T ranges against the Sophos 2025 survey | `external_contrast.json` |
| 11 | `agri_bridge.py` | q<sub>AGR</sub>(0) = π × φ × h with public anchors for π (MAPA 2024: crop and irrigation shares, pigmeat, poultry) | `agri_bridge.json` |
| 12 | `extensions_L2_L7.py` | Two-phase integrity attack over detection latency and remediation time; adversarial timing premium; single-counted channel corridor A<sub>max</sub> = max(A*, A<sub>fwd</sub>) | `extensions.json` |
| 13 | `regional_reading.py` | National loss of an incident confined to Andalusia or the Mediterranean arc; location of Γ<sub>∞</sub> by receiving sector; sensitivity to AGR's purchase and sales structure | `regional_reading.json` |
| 14 | `make_figures.py` | All six manuscript figures from the JSON files; no number is typed in the script | `../figs/*.png` |

Each script prints its results to the console as well. Run times on the
verification machine: 50 s in total, of which 14 s for the Monte Carlo and
32 s for the uncertainty decomposition.

---

## Values that identify a faithful run

| Quantity | Value | File |
|---|---|---|
| ρ(A*) | 0.4130 | `ine_calibration.json` |
| Exposure weights w (EUR M): RET, IAB, LOG | 405 025, 362 960, 291 364 | `ine_calibration.json` |
| Γ(120) of S2, S5, C1 (EUR M) | 501.6, 763.2, 847.4 | `ine_scenarios_results.json` → `baseline` |
| Cyber-climate margin S4 − S3 (EUR M) | 157.0 | `ine_scenarios_results.json` → `marginal_climate` |
| S2 envelope P5 / P50 / P95 (EUR M, ρ = 0) | 324 / 668 / 1292 | `ine_scenarios_results.json` → `envelopes` |
| Largest grocer's share of RET | 0.040–0.042 | `ine_trade_margins.json` |

---

## Data

| File | Source | Used by |
|---|---|---|
| `data/cne_tio_22.xlsx` | INE, *Contabilidad Nacional Anual de España, Revisión Estadística 2024*, symmetric input–output tables, reference year 2022, published 19 December 2025. Sheets `Tabla1` (production at basic prices), `Tabla2` (domestic product-by-product flows, 65 products, EUR M), `Tabla5` (technical coefficients, verification only) | `ine_calibration.py` |
| `data/cne_tod_22.xlsx` | INE, same release, supply and use tables 2022. Sheet `Tabla1` (supply table at basic prices with the transformation to purchasers' prices) | `ine_trade_margins.py` |

"Revisión Estadística 2024" names the accounting revision; the reference year
of both tables is 2022. The workbooks are official public data under INE's
conditions of use and are not modified by any script. Other anchors (MAPA,
Mercasa, INE structural business statistics, incident reports) are typed as
constants in the scripts that use them, with their sources in the docstrings
and in the manuscript.

---

## Censys exposure supplement (`censys/`)

The manuscript has a supplement on the Internet-facing exposure of the device
classes the scenarios attack, built from **aggregate** Censys Platform
counts for Spain (no host lists, no individual records). This directory keeps:

- `censys/queries.json`, `censys/access_status.json`, `censys_exposure.py`,
  `test_censys_exposure.py`: the earlier aggregate-only query protocol and the
  record of the blocked access attempt, kept as history.
- `censys/results_tables.tex`, `censys/results_audit.json`: tables and audit
  generated by `censys_results_analysis.py` from the supplied aggregate results.
- `censys/README.md`: scope, units and limits of that analysis (in Spanish).

`censys_results_analysis.py` reads `../censys_results.json` and
`censys_exposure.py` reads `../APIs.txt`; neither file is part of this
repository, so these two scripts are not runnable from a clone and are not
part of `run_all.py`. The stored tables are the reproduction artefact.

---

## Repository hygiene

- `__pycache__/` and `run_scenarios.log` are local artefacts, not needed for
  reproduction.
- `mc_samples.npz` (3.9 MB) stores the structural Monte Carlo draws so that
  stages 8 and 9 reuse exactly the reference run; `ine_scenarios.py`
  regenerates it.
- All random draws use `numpy.random.default_rng(20260719)` with a fixed
  consumption order (child seeds `[20260719, k]` for the two-phase A1 and for
  the extra seeds of stage 8), so envelopes are reproduced bit for bit on the
  pinned numpy version.

## Licence and citation

This repository (code, derived data and documentation) is released under the
**Creative Commons Attribution–NonCommercial–NoDerivatives 4.0 International
licence (CC BY-NC-ND 4.0)**. You may copy and redistribute it in any medium or
format for non-commercial purposes, provided you give appropriate credit and
do not distribute modified versions. The full legal code is in
[`LICENSE`](LICENSE) and at
<https://creativecommons.org/licenses/by-nc-nd/4.0/>.

The INE workbooks in `data/` are official public data and remain under INE's
own conditions of use; the licence above does not apply to them.

Please cite the manuscript above when using this material. A persistent
identifier will be added for the accepted version.

<p align="left">
  <a href="https://creativecommons.org/licenses/by-nc-nd/4.0/"><img src="https://licensebuttons.net/l/by-nc-nd/4.0/88x31.png" alt="CC BY-NC-ND 4.0"></a>
</p>
