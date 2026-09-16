# -*- coding: utf-8 -*-
"""V2a pre-audit: full funnel over the 4,415 extracted QGIS workflows.

Answers the owner's question list (2026-09-16):
  原始多少 / 合法多少 / Gold多少 / Silver多少 / 真正可训练多少 /
  distinct operators / operator support distribution / workflow length /
  DAG 完整率 / 任务类型覆盖 / GDAL-GRASS-native-API 比例

Read-only; every check mechanical and complete (no sampling). Output:
  docs/reports/qgis_wf_audit_v2a_pre/audit_result_v1.json
"""
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
REPO = Path(__file__).resolve().parents[1]

# ── load assets ────────────────────────────────────────────────────────────
catalog = {o["operator_id"] for o in json.load(
    open(REPO / "benchmarks/qgis_planner_v1/authority/qgis_catalog.json", encoding="utf-8"))["operators"]}
l3map_entries = json.load(
    open(REPO / "benchmarks/qgis_planner_v1/authority/qgis_operator_l3_mapping.json", encoding="utf-8"))["entries"]
l3map = {e["operator_id"]: e.get("stable101_l3") for e in l3map_entries}
native_slugs = {k.split(":")[-1] for k in l3map if k.startswith("native:")}

# qualified API semantic bindings (method -> l3)
api_methods = set()
for line in open(REPO / "docs/reports/qgis_api_semantic_production_v2/phase2_adjudicated/adjudication_v1.jsonl", encoding="utf-8"):
    r = json.loads(line)
    if r.get("decision") == "QUALIFIED":
        api_methods.add(r["semantic_action"].split(":")[-1].split(".")[-1])

# slug-liftable: method name equals a catalog operator slug (e.g. buffer -> native:buffer)
catalog_by_slug = defaultdict(list)
for op in catalog:
    catalog_by_slug[op.split(":")[-1]].append(op)

PLUMBING = {
    "setGeometry", "setAttributes", "addFeatures", "addFeature", "addAttribute", "addAttributes",
    "updateFields", "GetRasterBand", "Open", "writeAsVectorFormat", "write", "close", "commitChanges",
    "startEditing", "setField", "setFieldValue", "setValue", "evaluate", "count", "size", "length",
    "addMapLayer", "removeMapLayer", "setCrs", "setDataSource", "isValid", "fields", "getFeatures",
    "featureCount", "extent", "crs", "wkbType", "geometryType", "name", "id", "triggerRepaint",
    "addVectorLayer", "addRasterLayer", "createLayer", "layerByName",
}
ATTR_EDIT = {"changeAttributeValue", "changeAttributeValues", "updateFeature", "deleteFeature",
             "deleteFeatures", "addFeature"}

# leakage: benchmark + val/test 6-grams, and exclusion SHAs
WORD = re.compile(r"[a-z0-9]+")
grams = set()
for f in ("dev_20", "final_100", "refusal_12"):
    for line in open(REPO / f"docs/reports/qgis_planner_eval_v1/materialized/{f}.tasks.jsonl", encoding="utf-8"):
        w = WORD.findall(json.loads(line)["task_text"].lower())
        grams.update(" ".join(w[i:i+6]) for i in range(max(len(w)-5, 0)))
for line in open(REPO / "docs/reports/paper_v1_supervision/paper_v1_supervision_manifest.jsonl", encoding="utf-8"):
    r = json.loads(line)
    if r["split"] in ("val", "test"):
        w = WORD.findall((r.get("task_text") or "").lower())
        grams.update(" ".join(w[i:i+6]) for i in range(max(len(w)-5, 0)))
excl = set(json.load(open(REPO / "outputs_tmp_domain_corpus_paths_v1.excl.json", encoding="utf-8")))
wf_shas = {w: h for w, _, h in (tuple(x) for x in json.load(
    open(Path.home() / "AppData/Local/Temp/qgis_wf_shas.json", encoding="utf-8")))}

# license boilerplate grams to subtract (GPL/MIT/BSD/Apache families, same as domain_corpus fix)
LIC = [
    "this program is free software you can redistribute it and or modify it under the terms of the gnu general public license as published by the free software foundation either version 3 of the license or at your option any later version this program is distributed in the hope that it will be useful but without any warranty without even the implied warranty of merchantability or fitness for a particular purpose see the gnu general public license for more details",
    "permission is hereby granted free of charge to any person obtaining a copy of this software and associated documentation files the software to deal in the software without restriction including without limitation the rights to use copy modify merge publish distribute sublicense and or sell copies of the software and to permit persons to whom the software is furnished to do so subject to the following conditions the above copyright notice and this permission notice shall be included in all copies or substantial portions of the software",
    "redistribution and use in source and binary forms with or without modification are permitted provided that the following conditions are met redistributions of source code must retain the above copyright notice this list of conditions and the following disclaimer",
]
for t in LIC:
    w = WORD.findall(t)
    grams -= {" ".join(w[i:i+6]) for i in range(max(len(w)-5, 0))}


def classify_proc(ident):
    """-> (kind, provider, liftable_to or None, note)"""
    if ":" in ident:
        cand = ident.replace("processing.run:", "")
        prov = cand.split(":")[0]
        if cand in catalog:
            return ("alg", prov, cand, "catalog")
        if cand.startswith("qgis:"):
            nat = "native:" + cand.split(":")[-1]
            if nat in catalog:
                return ("alg", "native", nat, "alias_qgis_to_native")
        return ("alg", prov, None, "not_in_catalog")
    method = ident.split(".")[-1]
    if method in PLUMBING:
        return ("api_plumbing", "api", None, "plumbing")
    if method in ATTR_EDIT:
        return ("api_attr_edit", "api", "native:fieldcalculator", "attr_edit")
    if method in api_methods:
        # semantic binding -> some L3 -> pick representative operator presence later
        return ("api_semantic", "api", method, "binding")
    if catalog_by_slug.get(method):
        return ("api_semantic", "api", catalog_by_slug[method][0], "slug_equiv")
    return ("api_unknown", "api", None, "unresolved")


rows = [json.loads(l) for l in open(REPO / "docs/reports/qgis_wf_full_v1.jsonl", encoding="utf-8")]
funnel = Counter()
tiers = Counter()
support = Counter()
provider_inst = Counter()
kind_inst = Counter()
task_types = Counter()
lengths = []
chain_sigs = {}
leak_hits, sha_excluded = [], 0

for r in rows:
    funnel["raw"] += 1
    if r["n_proc"] == 0:
        funnel["zero_proc"] += 1
        continue
    if r["n_proc"] < 2:
        funnel["single_proc"] += 1
        continue
    funnel["multi_step"] += 1
    if not r["link_valid"]:
        funnel["link_invalid"] += 1
        continue
    funnel["link_valid"] += 1
    if r["acyclic"] is False:
        funnel["cyclic"] += 1
        continue
    funnel["dag_valid"] += 1
    if wf_shas.get(r["wid"]) in excl:
        sha_excluded += 1
        continue
    funnel["sha_pass"] += 1

    # description 6-gram leakage
    w = WORD.findall(r["desc"].lower())
    if {" ".join(w[i:i+6]) for i in range(max(len(w)-5, 0))} & grams:
        leak_hits.append(r["wid"])
        continue
    funnel["leakage_pass"] += 1

    # per-process classification
    resolved, unresolved, plumbing = [], 0, 0
    for ident in r["idents"]:
        kind, prov, target, note = classify_proc(ident)
        kind_inst[kind] += 1
        provider_inst[prov] += 1
        if kind == "alg":
            if target:
                resolved.append(target); support[target] += 1
            else:
                unresolved += 1
        elif kind in ("api_semantic", "api_attr_edit"):
            resolved.append(target); support[target] += 1
        elif kind == "api_plumbing":
            plumbing += 1
        else:
            unresolved += 1

    chain = [x for x in resolved if x and x.startswith(("native:", "qgis:", "gdal:", "grass", "saga"))]
    # dedup by ordered signature (alg chain only)
    sig = tuple(c.replace("qgis:", "native:") for c in chain)
    task_types[r["taskType"] or "?"] += 1
    if sig and sig in chain_sigs:
        funnel["dedup_drop"] += 1
        continue
    if sig:
        chain_sigs[sig] = r["wid"]
    funnel["dedup_pass"] += 1

    # tiering (structural; description-code consistency NOT yet verified)
    if len(chain) >= 2 and unresolved == 0:
        tiers["gold_structural"] += 1
        lengths.append(r["n_proc"])
    elif len(chain) >= 2:
        tiers["silver_structural"] += 1
        lengths.append(r["n_proc"])
    elif len(chain) == 1:
        tiers["single_operator"] += 1
    else:
        tiers["no_resolvable_alg"] += 1

bands = Counter()
for op, c in support.items():
    if c >= 100: bands["core_ge100"] += 1
    elif c >= 30: bands["normal_30_99"] += 1
    elif c >= 10: bands["observe_10_29"] += 1
    elif c >= 3: bands["longtail_3_9"] += 1
    else: bands["rare_1_2"] += 1

result = {
    "schema": "gis_recommend.qgis_wf_v2a_pre_audit.v1",
    "funnel": dict(funnel),
    "tiers": dict(tiers),
    "operator_support": {
        "distinct_operators": len(support),
        "bands": dict(bands),
        "top15": support.most_common(15),
    },
    "provider_instances": dict(provider_inst.most_common()),
    "kind_instances": dict(kind_inst.most_common()),
    "task_type_coverage_top15": task_types.most_common(15),
    "chain_length_of_tiered": {
        "mean": round(sum(lengths)/max(len(lengths),1), 1),
        "median": sorted(lengths)[len(lengths)//2] if lengths else 0,
    },
    "sha_excluded": sha_excluded,
    "leakage_6gram_hits": len(leak_hits),
    "notes": [
        "Structural audit only: description-code consistency NOT verified (needs sampling review).",
        "gold_structural = >=2 catalog-resolvable operators + valid DAG + zero unresolved processes;",
        "silver_structural = >=2 resolvable but some unresolved leftovers.",
        "API lift: slug-equivalence + 998 semantic bindings + attribute-edit classes; plumbing dropped.",
        "qgis: aliases normalized to native:.",
    ],
}
out = REPO / "docs/reports/qgis_wf_audit_v2a_pre/audit_result_v1.json"
out.parent.mkdir(parents=True, exist_ok=True)
out.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps(result, indent=2, ensure_ascii=False))
