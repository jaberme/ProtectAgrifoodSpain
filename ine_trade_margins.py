#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Anclas del sector RET para la conversion operador -> sector .

Lee la Tabla 1 (tabla de origen a precios basicos, con transformacion a
precios de adquisicion) de data/cne_tod_22.xlsx (INE, Contabilidad Nacional
Anual, Revision Estadistica 2024, Tablas de Origen y Destino 2022) y deriva:

  * salida de los servicios de comercio (productos 64 y 65), que es x_RET en
    ine_calibration.json: 146.297,7 + 98.798,7 = 245.096,4 M EUR;
  * margenes comerciales netos reasignados por el INE a esos productos
    (columna 'Margenes comerciales': -135.233,2 y -98.798,7);
  * margenes comerciales generados sobre productos agrarios, pesqueros y
    alimentarios (productos 1, 2, 5, 11-18) y su cuota sobre la salida RET;
  * salida de productos carnicos (producto 11) para dimensionar S2.

Con la cifra de negocios 2022 del comercio (INE, Estadistica Estructural de
Empresas, sector comercio, tabla 76818: G46 574.666,3 y G47 288.562,9 M EUR)
obtiene dos ratios agregados, margenes netos / facturacion y salida de
servicios de comercio / facturacion, que aplicados a las ventas netas de un
distribuidor dan su salida en base margenes y su cuota sigma_o en RET.
Mercadona 2025: 38.178 M EUR netos sin IVA, de los que 39.766/41.858 en
Espana (fuentes en references_corregido.bib). Escribe ine_trade_margins.json.
"""
import json
import os
import re

import openpyxl

HERE = os.path.dirname(os.path.abspath(__file__))
WORKBOOK = os.path.join(HERE, "data", "cne_tod_22.xlsx")
AGRIFOOD = [1, 2, 5, 11, 12, 13, 14, 15, 16, 17, 18]   # productos CPA agregados
TRADE = [64, 65]
MEAT = 11
EEE_2022_TURNOVER = dict(G46=574666.271, G47=288562.944)   # M EUR, INE EEE 2022
MERCADONA = dict(net_sales_ex_vat_2025=38178.0, gross_total=41858.0, gross_spain=39766.0)
IAB_OUTPUT = 160265.5                                         # x_IAB, TIO 2022

rows = list(openpyxl.load_workbook(WORKBOOK, read_only=True, data_only=True)["Tabla1"]
            .iter_rows(values_only=True))
header = next(r for r in rows if r and "Total producción" in r)
col_output = header.index("Total producción")
col_margin = header.index("Márgenes comerciales")
products = {}
for r in rows:
    label = str(r[1]) if len(r) > 1 and r[1] is not None else ""
    m = re.match(r"^\s*(\d+)\s*\.", label)
    if m and isinstance(r[col_output], (int, float)):
        products[int(m.group(1))] = dict(label=label.strip(), output=float(r[col_output]),
                                         margin=float(r[col_margin] or 0.0))

trade_output = sum(products[p]["output"] for p in TRADE)
net_margins = -sum(products[p]["margin"] for p in TRADE)
agrifood_margins = sum(products[p]["margin"] for p in AGRIFOOD)
turnover = EEE_2022_TURNOVER["G46"] + EEE_2022_TURNOVER["G47"]
margin_rate = net_margins / turnover
output_rate = trade_output / turnover
spain_sales = MERCADONA["net_sales_ex_vat_2025"] * MERCADONA["gross_spain"] / MERCADONA["gross_total"]
margin_basis = (spain_sales * margin_rate, spain_sales * output_rate)
share = tuple(v / trade_output for v in margin_basis)
old_r1 = 0.18 * trade_output

out = dict(
    source="INE, Tablas de Origen y Destino 2022 (cne_tod_22.xlsx, Tabla 1) e INE EEE Comercio 2022 (tabla 76818)",
    trade_services_output_MEUR={str(p): products[p]["output"] for p in TRADE} | {"total": trade_output},
    trade_margin_column_MEUR={str(p): products[p]["margin"] for p in TRADE} | {"net_total": net_margins},
    agrifood_margins_MEUR={str(p): products[p]["margin"] for p in AGRIFOOD} | {"total": agrifood_margins},
    agrifood_share_of_RET_output=agrifood_margins / trade_output,
    meat_products_output_MEUR=products[MEAT]["output"],
    meat_share_of_IAB_output=products[MEAT]["output"] / IAB_OUTPUT,
    S2_share_of_meat_output=0.20 * IAB_OUTPUT / products[MEAT]["output"],
    trade_turnover_2022_MEUR=turnover,
    net_margin_rate=margin_rate,
    output_to_turnover_rate=output_rate,
    largest_grocer=dict(net_sales_spain_2025_MEUR=spain_sales, margin_basis_output_MEUR=list(margin_basis),
                        share_of_RET=list(share), sigma_R1=round(share[0], 2)),
    previous_R1=dict(q=0.18, margins_MEUR=old_r1, share_of_agrifood_margins=old_r1 / agrifood_margins,
                     largest_grocer_equivalents=[old_r1 / v for v in margin_basis]),
)
with open(os.path.join(HERE, "ine_trade_margins.json"), "w") as f:
    json.dump(out, f, indent=2, ensure_ascii=False)

print(f"Salida servicios de comercio (64+65): {trade_output:,.1f} M EUR  "
      f"[64: {products[64]['output']:,.1f}; 65: {products[65]['output']:,.1f}]")
print(f"Margenes comerciales netos (64+65):   {net_margins:,.1f} M EUR")
print(f"Margenes agroalimentarios (1,2,5,11-18): {agrifood_margins:,.1f} M EUR = "
      f"{100*agrifood_margins/trade_output:.1f} % de la salida RET")
print(f"Productos carnicos (11): {products[MEAT]['output']:,.1f} M EUR = "
      f"{100*products[MEAT]['output']/IAB_OUTPUT:.1f} % de IAB; S2 (q=0.20) = "
      f"{100*out['S2_share_of_meat_output']:.1f} % de esa salida")
print(f"Facturacion comercio 2022 (G46+G47): {turnover:,.1f}; margen neto/facturacion = "
      f"{100*margin_rate:.1f} %; salida/facturacion = {100*output_rate:.1f} %")
print(f"Mayor distribuidor: ventas netas Espana {spain_sales:,.0f}; salida en base margenes "
      f"{margin_basis[0]:,.0f}-{margin_basis[1]:,.0f}; cuota RET {100*share[0]:.2f}-{100*share[1]:.2f} %")
print(f"R1 anterior (q=0.18): {old_r1:,.0f} M EUR = {100*old_r1/agrifood_margins:.1f} % de los margenes "
      f"agroalimentarios = {old_r1/margin_basis[1]:.1f}-{old_r1/margin_basis[0]:.1f} distribuidores")
