#!/usr/bin/env python3
"""Aggregate-only Censys study.

The only network destination is the documented aggregate endpoint.
No host search, asset lookup, DNS resolution of targets or rescan is implemented.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "repro" / "censys"
ENDPOINT = "https://api.platform.censys.io/v3/global/search/aggregate"
COUNTRY = 'host.location.country_code="ES"'
FIELDS = {"host.location.country_code", "host.location.province",
          "host.services.protocol"}
# Fixed before a successful extraction; these are technical indicators, not
# an exhaustive inventory of ICS or a sector classifier.
ICS = ["MODBUS", "S7", "EIP", "CODESYS", "FINS", "MELSEC", "DNP3",
       "IEC60870_5_104", "OPC_UA", "BACNET", "FOX", "GE_SRTP", "PCWORX",
       "PRO_CON_OS", "PROFINET", "CMORE", "CMORE_HMI", "SCADA_VIEW",
       "REDLION_CRIMSON", "REDLION_WEB"]
REMOTE = ["SSH", "TELNET", "RDP", "VNC", "WINRM", "OPENVPN", "IKE",
          "PPTP"]
IOT = ["MQTT", "COAP"]
TERMS = {
    "AGR": ["fertirrigación", "fertirrigacion", "fertigation",
            "comunidad de regantes", "comunidades de regantes",
            "riego agrícola", "riego agricola", "agricultural irrigation",
            "control de invernaderos", "greenhouse control",
            "explotación ganadera", "explotacion ganadera", "livestock farm"],
    "IAB": ["industria alimentaria", "industria agroalimentaria",
            "procesado de alimentos", "food processing", "food production",
            "matadero", "slaughterhouse", "industria láctea", "industria lactea"],
    "RET": ["distribución alimentaria", "distribucion alimentaria",
            "distribución de alimentos", "distribucion de alimentos",
            "food distribution", "almacén frigorífico", "almacen frigorifico",
            "cadena de frío alimentaria", "food cold chain"],
}
EXTRA = ["regantes", "fertiriego", "irrigation", "invernadero", "greenhouse",
         "ganadería", "ganaderia", "agroalimentario", "agroalimentaria",
         "alimentación", "alimentacion", "agricultura", "agriculture",
         "horticulture", "horticultura", "avicultura", "poultry", "porcino",
         "lácteos", "lacteos", "cold storage", "cadena de frío", "cadena de frio"]
TEXT_FIELDS = ["host.services.banner", "host.services.endpoints.http.body"]
PRODUCT_FIELDS = ["host.hardware.product", "host.services.hardware.product",
                  "host.services.software.product"]
DEVICE_TERMS = {
    "plc": ["PLC", "programmable logic controller"],
    "rtu": ["RTU", "remote terminal unit"],
    "hmi_scada": ["HMI", "SCADA"],
    "gateway": ["gateway", "industrial gateway"],
}


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def text_query(terms, fields=TEXT_FIELDS):
    values = "{" + ", ".join(json.dumps(x, ensure_ascii=False) for x in terms) + "}"
    return "(" + " OR ".join(f"{field}: {values}" for field in fields) + ")"


def protocols(values):
    return "(" + " OR ".join(f'host.services.protocol="{v}"' for v in values) + ")"


def both(*parts):
    return " AND ".join(f"({p})" for p in parts)


def make_plan():
    narrow = text_query([t for terms in TERMS.values() for t in terms])
    expanded = "(" + narrow + " OR " + text_query(EXTRA) + ")"
    technical = protocols(ICS)
    candidates = both(COUNTRY, narrow)
    primary = both(candidates, technical)
    jobs = []

    def add(identifier, query, field="host.location.country_code", filtered=False):
        jobs.append({"id": identifier, "request": {
            "query": query, "field": field, "number_of_buckets": 2000,
            "count_by_level": ".", "filter_by_query": filtered}})

    add("es_ics_total", both(COUNTRY, technical))
    add("es_ics_protocols", both(COUNTRY, technical), "host.services.protocol", True)
    add("lexical_total", candidates)
    add("lexical_protocols", candidates, "host.services.protocol")
    add("primary_total", primary)
    # false intentionally returns co-observed remote services, not just the
    # industrial services that caused a host to enter the primary cohort.
    add("primary_protocols", primary, "host.services.protocol")
    add("primary_regions", primary, "host.location.province")
    add("primary_region_missing", both(primary, "NOT host.location.province: *"))
    add("primary_remote_union", both(primary, protocols(REMOTE)))
    add("primary_iot_union", both(primary, protocols(IOT)))
    add("lexical_remote_union", both(candidates, protocols(REMOTE)))
    add("lexical_iot_union", both(candidates, protocols(IOT)))
    add("expanded_total", both(COUNTRY, expanded))
    add("expanded_ics_total", both(COUNTRY, expanded, technical))
    for sector, terms in TERMS.items():
        add(f"primary_cue_{sector.lower()}", both(COUNTRY, technical, text_query(terms)))
    devices = []
    for device, terms in DEVICE_TERMS.items():
        condition = text_query(terms, PRODUCT_FIELDS)
        devices.append(condition)
        add(f"primary_device_{device}", both(primary, condition))
    add("primary_device_unclassified", both(primary, "NOT (" + " OR ".join(devices) + ")"))
    # An end-of-run control quantifies drift in a live index without IDs.
    add("primary_total_end", primary)
    return {"schema_version": 1, "endpoint": ENDPOINT,
            "unit": "root host documents per bucket; not physical devices",
            "ics_protocols": ICS, "remote_protocols": REMOTE, "iot_protocols": IOT,
            "lexical_terms": TERMS, "expanded_terms": EXTRA,
            "text_fields": TEXT_FIELDS, "device_terms": DEVICE_TERMS,
            "device_product_fields": PRODUCT_FIELDS, "jobs": jobs}


def write_json(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n")


def plan_hash(plan):
    return hashlib.sha256(json.dumps(plan, sort_keys=True, ensure_ascii=False).encode()).hexdigest()


def credentials(path):
    values = {}
    for line in path.read_text().splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            if k.strip() in {"CENSYS_API_TOKEN", "CENSYS_ORG_ID"}:
                values[k.strip()] = v.strip().strip("\"'")
    if not values.get("CENSYS_API_TOKEN") or not values.get("CENSYS_ORG_ID"):
        raise ValueError("Missing Censys credential fields; values not displayed")
    return values


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def normalize_response(data, field):
    """Allow only marginal category counts, discard all other response content."""
    result = data.get("result")
    if not isinstance(result, dict):
        raise ValueError("Missing aggregate result")
    cleaned = {}
    for key in ("total_count", "other_count", "query_duration_millis"):
        v = result.get(key)
        if type(v) is not int or v < 0:
            raise ValueError("Invalid aggregate integer")
        cleaned[key] = v
    flag = result.get("is_more_than_total_hits")
    if type(flag) is not bool:
        raise ValueError("Missing count precision flag")
    cleaned["is_more_than_total_hits"] = flag
    buckets = result.get("buckets") or []
    if not isinstance(buckets, list):
        raise ValueError("Invalid bucket array")
    cleaned["buckets"] = []
    for b in buckets:
        key, count = b.get("key"), b.get("count")
        if not isinstance(key, str) or type(count) is not int or count < 0:
            raise ValueError("Unexpected bucket schema; inspect official API schema")
        if field == "host.location.country_code" and key != "ES":
            raise ValueError("Country bucket outside study boundary")
        if field == "host.services.protocol" and not re.fullmatch(r"[A-Z][A-Z0-9_+.-]{0,79}", key):
            raise ValueError("Unexpected protocol category")
        if field == "host.location.province" and not re.fullmatch(r"[^\d@:/\\<>\n\r]{1,100}", key):
            raise ValueError("Unexpected geographical category")
        cleaned["buckets"].append({"key": key, "count": count})
    return cleaned


def collect(plan, credential_path, output):
    cfg = credentials(credential_path)
    run = {"status": "in_progress", "started_at_utc": now(),
           "plan_sha256": plan_hash(plan), "results": []}
    output.mkdir(parents=True, exist_ok=False)
    write_json(output / "queries.json", plan)
    opener = urllib.request.build_opener(NoRedirect())
    for job in plan["jobs"]:
        payload = job["request"]
        if payload["field"] not in FIELDS or payload["count_by_level"] != ".":
            raise ValueError("Nonaggregate request rejected")
        req = urllib.request.Request(ENDPOINT, data=json.dumps(payload).encode(), headers={
            "Authorization": "Bearer " + cfg["CENSYS_API_TOKEN"],
            "X-Organization-ID": cfg["CENSYS_ORG_ID"],
            "Content-Type": "application/json", "Accept": "application/json",
            "User-Agent": "AgriFoodExposureResearch/1.0 (aggregate-only)"})
        record = {"id": job["id"], "started_at_utc": now()}
        try:
            with opener.open(req, timeout=60) as response:
                data = json.load(response)
            clean = normalize_response(data, payload["field"])
            # Check in memory before serialization, including unexpected echoes.
            encoded = json.dumps(clean, ensure_ascii=False)
            if any(secret in encoded for secret in cfg.values()):
                raise ValueError("Credential echo rejected")
            record.update(status="ok", aggregate=clean)
        except urllib.error.HTTPError as error:
            # Do not print/read a remote error body or exception containing URLs.
            record.update(status="http_error", http_status=error.code)
        except (urllib.error.URLError, TimeoutError, OSError):
            record.update(status="network_error")
        except (ValueError, TypeError, KeyError, AttributeError):
            record.update(status="schema_error")
        record["finished_at_utc"] = now()
        run["results"].append(record)
        write_json(output / "aggregates.json", run)
        print(job["id"], record["status"])
        if record["status"] != "ok":
            run["status"] = "incomplete"
            break  # No automatic retries, fallback wallets or access bypass.
    else:
        run["status"] = "complete"
    run["finished_at_utc"] = now()
    write_json(output / "aggregates.json", run)
    export_csv(run, output)
    return run["status"] == "complete"


def export_csv(run, output):
    # This is a long-form marginal dataset, never a host inventory.
    with (output / "counts.csv").open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(["query_id", "category", "host_count", "other_count",
                         "is_more_than_total_hits", "retrieved_at_utc"])
        for record in run["results"]:
            if record["status"] != "ok":
                continue
            a = record["aggregate"]
            for b in a["buckets"]:
                writer.writerow([record["id"], b["key"], b["count"],
                                 a["other_count"], a["is_more_than_total_hits"],
                                 record["finished_at_utc"]])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collect", action="store_true", help="Run 23 aggregate requests; consumes account credits")
    parser.add_argument("--credentials", type=Path, default=ROOT / "APIs.txt")
    parser.add_argument("--output", type=Path, help="New directory for a live run")
    args = parser.parse_args()
    plan = make_plan()
    if not args.collect:
        write_json(OUT / "queries.json", plan)
        print(f"Offline plan: {len(plan['jobs'])} aggregate queries; no network or credentials read")
        print("SHA-256:", plan_hash(plan))
        return 0
    target = args.output or OUT / datetime.now(timezone.utc).strftime("run_%Y%m%dT%H%M%SZ")
    try:
        return 0 if collect(plan, args.credentials, target) else 1
    except (ValueError, OSError):
        print("Cannot start collection: check credential file and use a new output directory; no details logged", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
