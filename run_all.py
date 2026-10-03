#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Reproduce every number, table and figure of the manuscript from a clean
checkout, in dependency order, and fail on the first discrepancy.

    python3 run_all.py            # full pipeline (about 1-2 minutes)
    python3 run_all.py --audit    # also run ../audit.py against the .tex

Stage                         Script                        Output(s)
1 calibration (3 partitions)  ine_calibration.py            ine_calibration*.json, csv
2 trade anchors               ine_trade_margins.py          ine_trade_margins.json
3 point results + Monte Carlo ine_scenarios.py              ine_scenarios_results.json, mc_samples.npz
4 verification (fails loudly) diim.py                       (exit 1 on discrepancy)
5 criteria                    static_vs_dynamic.py          criteria.json
6 partition sensitivity       partition_sensitivity.py      partition_sensitivity.json
7 recovery shape              recovery_shape.py             recovery_shape.json
8 uncertainty decomposition   uncertainty_decomposition.py  uncertainty_decomposition.json
9 decision example            decision_example.py           decision_example.json
10 external contrast          external_contrast.py          external_contrast.json
11 agricultural bridge        agri_bridge.py                agri_bridge.json
12 extensions                 extensions_L2_L7.py           extensions.json
13 regional reading           regional_reading.py           regional_reading.json
14 figures                    make_figures.py               ../figs/*.png
"""
import subprocess
import sys
import time
import os

HERE = os.path.dirname(os.path.abspath(__file__))
STAGES = [
    ("ine_calibration.py", ["--partition", "base"]),
    ("ine_calibration.py", ["--partition", "split"]),
    ("ine_calibration.py", ["--partition", "envp"]),
    ("ine_trade_margins.py", []),
    ("ine_scenarios.py", []),
    ("diim.py", []),
    ("static_vs_dynamic.py", []),
    ("partition_sensitivity.py", []),
    ("recovery_shape.py", []),
    ("uncertainty_decomposition.py", []),
    ("decision_example.py", []),
    ("external_contrast.py", []),
    ("agri_bridge.py", []),
    ("extensions_L2_L7.py", []),
    ("regional_reading.py", []),
    ("make_figures.py", []),
]
t0 = time.time()
for script, args in STAGES:
    t1 = time.time()
    print(f"\n### {script} {' '.join(args)}", flush=True)
    r = subprocess.run([sys.executable, os.path.join(HERE, script)] + args, cwd=HERE)
    if r.returncode != 0:
        print(f"\nPIPELINE FAILED at {script} (exit {r.returncode})")
        sys.exit(r.returncode)
    print(f"    ({time.time()-t1:.1f} s)")
if "--audit" in sys.argv:
    r = subprocess.run([sys.executable, os.path.join(HERE, "..", "audit.py")], cwd=os.path.join(HERE, ".."))
    if r.returncode != 0:
        print("\nAUDIT FAILED"); sys.exit(r.returncode)
print(f"\nPIPELINE COMPLETED in {time.time()-t0:.0f} s")
