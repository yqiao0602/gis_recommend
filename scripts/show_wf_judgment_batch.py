# -*- coding: utf-8 -*-
"""Display judgment batches for the V2a description-consistency verification."""
import json
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
REPO = Path(__file__).resolve().parents[1]

rows = {}
for l in open(REPO / "docs/reports/qgis_wf_full_v1.jsonl", encoding="utf-8"):
    r = json.loads(l)
    rows[r["wid"]] = r
catalog = {o["operator_id"] for o in json.load(
    open(REPO / "benchmarks/qgis_planner_v1/authority/qgis_catalog.json", encoding="utf-8"))["operators"]}
api_methods = set()
for line in open(REPO / "docs/reports/qgis_api_semantic_production_v2/phase2_adjudicated/adjudication_v1.jsonl", encoding="utf-8"):
    r = json.loads(line)
    if r.get("decision") == "QUALIFIED":
        api_methods.add(r["semantic_action"].split(":")[-1].split(".")[-1])
catalog_by_slug = defaultdict(list)
for op in catalog:
    catalog_by_slug[op.split(":")[-1]].append(op)
PLUMBING = {"setGeometry", "setAttributes", "addFeatures", "addFeature", "addAttribute", "addAttributes",
            "updateFields", "GetRasterBand", "Open", "writeAsVectorFormat", "write", "close", "commitChanges",
            "startEditing", "setField", "setFieldValue", "setValue", "evaluate", "count", "size", "length",
            "addMapLayer", "removeMapLayer", "setCrs", "setDataSource", "isValid", "fields", "getFeatures",
            "featureCount", "extent", "crs", "wkbType", "geometryType", "name", "id", "triggerRepaint",
            "addVectorLayer", "addRasterLayer", "createLayer", "layerByName"}


def chain_of(r):
    out = []
    for i in r["idents"]:
        if ":" in i:
            c = i.replace("processing.run:", "")
            if c in catalog:
                out.append(c)
                continue
            if c.startswith("qgis:"):
                nat = "native:" + c.split(":")[-1]
                if nat in catalog:
                    out.append(nat)
                    continue
        else:
            m = i.split(".")[-1]
            if m in PLUMBING:
                continue
            if catalog_by_slug.get(m):
                out.append(catalog_by_slug[m][0])
                continue
            if m in api_methods:
                out.append("API:" + m)
    return out


if __name__ == "__main__":
    lo, hi = int(sys.argv[1]), int(sys.argv[2])
    sample100 = json.load(open(REPO / "docs/reports/qgis_wf_audit_v2a_pre/sample100_wids.json"))
    for wid in sample100[lo:hi]:
        r = rows[wid]
        print("=" * 85)
        print(wid, "|", r["taskType"], "|", r["name"][:70])
        print("D:", r["desc"][:320].replace("\n", " "))
        print("C:", " -> ".join(chain_of(r))[:210])
