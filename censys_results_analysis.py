#!/usr/bin/env python3
"""Offline audit and LaTeX tables from the Censys aggregates.


"""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "censys_results.json"
OUTPUT = ROOT / "repro" / "censys"
ARC = {"Andalusia", "Murcia", "Valencia", "Catalonia"}
PORTS = {
    "ot": [(502, "Modbus"), (102, "S7"), (20000, "DNP3"),
           (47808, "BACnet"), (44818, "EtherNet/IP"),
           (2404, "IEC 60870-5-104"), (4840, "OPC UA"),
           (9600, "FINS"), (1911, "Fox"), (20547, "ProConOS")],
    "iot": [(1883, "MQTT"), (8883, "MQTT over TLS"), (5683, "CoAP")],
    "ra": [(3389, "RDP"), (5900, "VNC"), (5901, "VNC"),
           (23, "Telnet"), (22, "SSH")],
    "db": [(1433, "MSSQL"), (3306, "MySQL/MariaDB"),
           (5432, "PostgreSQL"), (27017, "MongoDB"), (9200, "Elasticsearch")],
}


def tex(value):
    replacements = {"\\": r"\textbackslash{}", "_": r"\_\allowbreak ",
                    "&": r"\&", "%": r"\%", "#": r"\#", "$": r"\$",
                    "{": r"\{", "}": r"\}"}
    return "".join(replacements.get(c, c) for c in str(value))


def number(value):
    return f"{value:,}".replace(",", r"\,")


def main():
    source_bytes = SOURCE.read_bytes()
    data = json.loads(source_bytes)
    queries = data["queries"]
    audit = {"source": "censys_results.json",
             "source_sha256": hashlib.sha256(source_bytes).hexdigest(),
             "generated_utc": data["generated_utc"],
             "query_count": len(queries), "errors": {}, "sums_checked": 0,
             "geographical_margins": {}, "bucket_limits_reached": [],
             "provenance": "user confirmed live Censys API queries; numerical checks do not independently authenticate origin"}
    for key, query in queries.items():
        result = query["result"]
        if "error" in result:
            audit["errors"][key] = result["error"]
            continue
        buckets = result["buckets"]
        assert len({b["key"] for b in buckets}) == len(buckets), key
        assert all(type(b["count"]) is int and b["count"] >= 0 for b in buckets), key
        assert sum(b["count"] for b in buckets) == result["sum_of_buckets"], key
        audit["sums_checked"] += 1
        if len(buckets) == query["number_of_buckets"]:
            audit["bucket_limits_reached"].append(key)
        if query["field"] == "host.location.province":
            arc = sum(b["count"] for b in buckets if b["key"] in ARC)
            total = result["sum_of_buckets"]
            audit["geographical_margins"][key] = {
                "returned_region_sum": total, "arc_sum": arc,
                "arc_share_percent": 100 * arc / total if total else None}

    def buckets(key):
        return {b["key"]: b["count"] for b in queries[key]["result"]["buckets"]}

    base = buckets("spain_by_province")
    industrial = buckets("ot_all_by_province")
    overlap = buckets("ra_plus_ot")
    assert set(industrial) <= set(base) and set(overlap) <= set(industrial)
    assert ARC <= set(base) and ARC <= set(industrial) and ARC <= set(overlap)
    for region, count in industrial.items():
        assert count <= base[region]
        assert overlap.get(region, 0) <= count
    for group in PORTS:
        for port, _ in PORTS[group]:
            for region, count in buckets(f"{group}_{port}").items():
                assert count <= base[region]
                if group == "ot":
                    assert count <= industrial[region]
    audit["subset_checks"] = "passed for all returned geographical buckets"
    margins = audit["geographical_margins"]
    b = margins["ot_all_by_province"]["returned_region_sum"]
    a = margins["ot_all_by_province"]["arc_sum"]
    r = margins["ra_plus_ot"]["returned_region_sum"]
    ra = margins["ra_plus_ot"]["arc_sum"]
    audit["derived"] = {
        "remote_port_cooccurrence_percent": 100*r/b,
        "arc_remote_port_cooccurrence_percent": 100*ra/a,
        "madrid_aragon_industrial_share_percent": 100*(industrial["Madrid"]+industrial["Aragon"])/b,
        "industrial_port_marginal_sum": sum(margins[f"ot_{p}"]["returned_region_sum"] for p, _ in PORTS["ot"]),
    }

    lines = ["% Generated offline by repro/censys_results_analysis.py; do not edit."]

    def macro(name, value):
        lines.append("\\newcommand{\\" + name + "}{" + value + "}")

    macro("CensysSourceHash", audit["source_sha256"])
    macro("CensysBase", number(margins["spain_by_province"]["returned_region_sum"]))
    macro("CensysIndustrial", number(b))
    macro("CensysArcIndustrial", number(a))
    macro("CensysOverlap", number(r))
    macro("CensysArcOverlap", number(ra))
    macro("CensysArcBase", number(margins["spain_by_province"]["arc_sum"]))
    macro("CensysArcBasePct", f"{margins['spain_by_province']['arc_share_percent']:.1f}")
    macro("CensysArcIndustrialPct", f"{100*a/b:.1f}")
    macro("CensysOverlapPct", f"{100*r/b:.1f}")
    macro("CensysArcOverlapPct", f"{100*ra/a:.1f}")
    macro("CensysLeadingRegionsPct", f"{audit['derived']['madrid_aragon_industrial_share_percent']:.1f}")

    def rows_for(group):
        rows = []
        for port, label in PORTS[group]:
            m = margins[f"{group}_{port}"]
            rows.append(f"{port} & {tex(label)} & {number(m['returned_region_sum'])} & "
                        f"{number(m['arc_sum'])} & {m['arc_share_percent']:.1f}" + r"\\")
        return "\n".join(rows)

    for group, name in [("ot", "Industrial"), ("iot", "IoT"), ("ra", "Remote"), ("db", "Database")]:
        macro("Censys" + name + "Rows", rows_for(group))

    regions = []
    for region in sorted(base, key=lambda x: industrial.get(x, -1), reverse=True):
        label = r"\textbf{" + tex(region) + "}" if region in ARC else tex(region)
        ot = number(industrial[region]) if region in industrial else r"\NR"
        co = number(overlap[region]) if region in overlap else r"\NR"
        share = f"{100*industrial[region]/b:.2f}" if region in industrial else r"\NR"
        regions.append(f"{label} & {number(base[region])} & {ot} & {co} & {share}" + r"\\")
    macro("CensysRegionRows", "\n".join(regions))

    protocols = buckets("spain_service_mix")
    chosen = ["MODBUS", "FINS", "EIP", "S7", "OPC_UA", "BACNET", "FOX",
              "MQTT", "COAP", "SSH", "RDP", "VNC", "TELNET", "WINRM",
              "IKE", "OPENVPN", "PPTP"]
    macro("CensysProtocolRows", "\n".join(
        f"{tex(p)} & {number(protocols[p])}" + r"\\" for p in chosen))
    macro("CensysHTTP", number(protocols["HTTP"]))
    macro("CensysPortMarginalSum", number(audit["derived"]["industrial_port_marginal_sum"]))
    products = buckets("ot_products")
    selected = [("codesys", "Controller-programming/runtime software"),
                ("niagara4", "Supervisory/automation software"),
                ("openvpn_access_server", "Remote-access software"),
                ("openssh", "Remote-administration software"),
                ("tightvnc", "Remote-desktop software")]
    macro("CensysProductRows", "\n".join(
        f"{tex(label)} & {tex(p)} & {number(products[p])}" + r"\\" for p, label in selected))
    macro("CensysProductSum", number(queries["ot_products"]["result"]["sum_of_buckets"]))
    macro("CensysVendorSum", number(queries["ot_vendors"]["result"]["sum_of_buckets"]))
    OUTPUT.mkdir(exist_ok=True, parents=True)
    (OUTPUT / "results_tables.tex").write_text("\n".join(lines) + "\n")
    (OUTPUT / "results_audit.json").write_text(json.dumps(audit, ensure_ascii=False, indent=2) + "\n")
    print(f"PASS: {audit['sums_checked']} bucket sums and geographic subset checks; "
          f"{len(audit['errors'])} error responses retained as unavailable")
    print("Generated aggregate tables and audit; no network calls or credential access")


if __name__ == "__main__":
    main()
