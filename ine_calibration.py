#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Empirical calibration of the DIIM from the official INE input-output tables.

Source: Contabilidad Nacional Anual de Espana, Revision Estadistica 2024,
Tablas Input-Output 2022 (published 19-12-2025), file data/cne_tio_22.xlsx:
  - Tabla 2: domestic-production input-output table (65 x 65 domestic flows
    Z, product by product, EUR million, basic prices).
  - Tabla 1, row 'Produccion a precios basicos': output vector x by product.
  - Tabla 5 ('Coeficientes tecnicos interiores'): independent check of
    A = Z diag(x)^-1.

Construction: flow-consistent aggregation Z_agg[I,J] = sum_{p in I, q in J} Z[p,q],
x_agg[I] = sum_{p in I} x[p]; A = Z_agg diag(x_agg)^-1; A* = diag(x)^-1 A diag(x)
(a*_ij = Z_agg[i,j]/x_i, share of supplier i's sales absorbed by customer j).

Partitions (option --partition):
  base : AGR P1; IAB P5; RET P29+P30; ENE P24+P10; AGU P25; LOG P31-P34;
         ENV P8+P13; ROE the remaining 51 products.        -> ine_calibration.json
  split: as base but trade separated into RETW (P29, wholesale) and RETR
         (P30, retail).                                     -> ine_calibration_split.json
  envp : as base but ENV = P13 (rubber and plastics) only; P8 paper -> ROE.
                                                            -> ine_calibration_envp.json
Documented ambiguities: fishing (P3) and forestry (P2) outside AGR; vehicle
trade (P28) outside RET; postal services (P35) outside LOG; ENV is a partial
packaging proxy; tobacco inside IAB.
"""
import argparse
import csv
import json
import os

import numpy as np
import openpyxl

HERE = os.path.dirname(os.path.abspath(__file__))
XLSX = os.environ.get("TIO_XLSX", os.path.join(HERE, "data", "cne_tio_22.xlsx"))

PARTITIONS = {
    "base": {"AGR": [0], "IAB": [4], "RET": [28, 29], "ENE": [23, 9], "AGU": [24],
             "LOG": [30, 31, 32, 33], "ENV": [7, 12]},
    "split": {"AGR": [0], "IAB": [4], "RETW": [28], "RETR": [29], "ENE": [23, 9],
              "AGU": [24], "LOG": [30, 31, 32, 33], "ENV": [7, 12]},
    "envp": {"AGR": [0], "IAB": [4], "RET": [28, 29], "ENE": [23, 9], "AGU": [24],
             "LOG": [30, 31, 32, 33], "ENV": [12]},
}
OUTFILE = {"base": "ine_calibration.json", "split": "ine_calibration_split.json",
           "envp": "ine_calibration_envp.json"}


def read_workbook():
    wb = openpyxl.load_workbook(XLSX, read_only=True, data_only=True)
    rows1 = list(wb['Tabla1'].iter_rows(values_only=True))
    rows2 = list(wb['Tabla2'].iter_rows(values_only=True))
    rows5 = list(wb['Tabla5'].iter_rows(values_only=True))
    NP = 65                       # 64 products + 44bis
    R0, C0 = 9, 2                 # first product row/column in Tabla2
    labels = [str(rows2[R0 + p][1]) for p in range(NP)]
    assert labels[0].startswith('1.') and labels[4].startswith('5.') \
        and labels[64].startswith('64.'), "unexpected product order"
    Z = np.array([[float(rows2[R0 + p][C0 + q] or 0.0) for q in range(NP)]
                  for p in range(NP)])
    tdi = np.array([float(rows2[R0 + p][67] or 0.0) for p in range(NP)])
    assert np.allclose(Z.sum(axis=1), tdi, rtol=1e-6), "row sums != total intermediate demand"
    assert str(rows1[86][1]).startswith('Producci'), rows1[86][1]
    x = np.array([float(rows1[86][C0 + q] or 0.0) for q in range(NP)])
    zero = np.where(x <= 0)[0]
    assert all(Z[:, p].sum() == 0 and Z[p, :].sum() == 0 for p in zero), \
        f"zero output with non-zero flows in {zero}"
    A_full = Z / np.where(x > 0, x, 1.0)[None, :]
    for (i, j) in [(0, 0), (0, 4), (4, 4), (24, 0), (7, 4)]:
        off = float(rows5[9 + i][C0 + j] or 0.0)
        assert abs(A_full[i, j] - off) < 5e-4, (i, j, A_full[i, j], off)
    return labels, Z, x


def aggregate(labels, Z, x, groups):
    NP = len(labels)
    groups = dict(groups)
    used = sorted(sum(groups.values(), []))
    assert len(used) == len(set(used)), "product assigned twice"
    groups["ROE"] = [p for p in range(NP) if p not in used]
    sect = list(groups.keys())
    n = len(sect)
    Zg = np.zeros((n, n)); xg = np.zeros(n)
    for i, si in enumerate(sect):
        xg[i] = x[groups[si]].sum()
        for j, sj in enumerate(sect):
            Zg[i, j] = Z[np.ix_(groups[si], groups[sj])].sum()
    A = Zg / xg[None, :]
    Astar = Zg / xg[:, None]
    rho_A = max(abs(np.linalg.eigvals(A)))
    rho_S = max(abs(np.linalg.eigvals(Astar)))
    assert abs(rho_A - rho_S) < 1e-10 and rho_S < 1
    L = np.linalg.inv(np.eye(n) - Astar)
    w = xg @ L
    w_fwd = xg @ np.linalg.inv(np.eye(n) - A.T)
    mult = np.linalg.inv(np.eye(n) - A).sum(axis=0)     # Leontief output multipliers
    return dict(sectors=sect, groups={s: [labels[p].split('.')[0] for p in groups[s]]
                                       for s in sect if s != "ROE"},
                x=xg.tolist(), A=A.tolist(), Astar=Astar.tolist(), rho=float(rho_S),
                w_backward=dict(zip(sect, w.tolist())),
                w_forward=dict(zip(sect, w_fwd.tolist())),
                output_multiplier=dict(zip(sect, mult.tolist())),
                row_sum_max=float(Astar.sum(axis=1).max()))


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--partition", choices=list(PARTITIONS), default="base")
    args = ap.parse_args()
    labels, Z, x = read_workbook()
    print("Check against Tabla 5 (official technical coefficients): OK")
    out = aggregate(labels, Z, x, PARTITIONS[args.partition])
    out = dict(source="INE, Contabilidad Nacional Anual de Espana RE-2024, TIO 2022 "
                      "(cne_tio_22.xlsx, Tabla 2 produccion interior; Tabla 1 "
                      "produccion a precios basicos), M EUR, precios basicos",
               year=2022, partition=args.partition, **out)
    sect = out["sectors"]; n = len(sect)
    Astar = np.array(out["Astar"]); xg = np.array(out["x"])
    print(f"\npartition={args.partition}  rho(A) = rho(A*) = {out['rho']:.4f}  "
          f"max row sum = {out['row_sum_max']:.4f}")
    print(f"{'sector':6s} {'x (MEUR)':>12s} {'w_bwd':>12s} {'w_fwd':>12s} {'mult':>7s} {'a*_ii':>7s}")
    for i, s in enumerate(sect):
        print(f"{s:6s} {xg[i]:12,.0f} {out['w_backward'][s]:12,.0f} {out['w_forward'][s]:12,.0f} "
              f"{out['output_multiplier'][s]:7.4f} {Astar[i,i]:7.3f}")
    print("\nA* (share of row i's sales absorbed by column j):")
    print("       " + "".join(f"{s:>8s}" for s in sect))
    for i, s in enumerate(sect):
        print(f"{s:6s} " + "".join(f"{Astar[i,j]:8.3f}" for j in range(n)))
    with open(os.path.join(HERE, OUTFILE[args.partition]), "w") as f:
        json.dump(out, f, indent=2, ensure_ascii=False)
    if args.partition == "base":
        with open(os.path.join(HERE, "ine_Astar_8x8.csv"), "w", newline="") as f:
            wcsv = csv.writer(f); wcsv.writerow([""] + sect)
            for i, s in enumerate(sect):
                wcsv.writerow([s] + [f"{Astar[i,j]:.6f}" for j in range(n)])
        with open(os.path.join(HERE, "ine_x_8.csv"), "w", newline="") as f:
            wcsv = csv.writer(f); wcsv.writerow(sect); wcsv.writerow(xg.tolist())
    print(f"\nWritten {OUTFILE[args.partition]}")


if __name__ == "__main__":
    main()
