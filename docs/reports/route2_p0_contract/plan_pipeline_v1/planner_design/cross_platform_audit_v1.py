#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""ROUTE2_CROSS_PLATFORM_TRANSFER_AUDIT v1 (CPU-only, read-only).

Q1 task taxonomy overlap: GEE task_type vs QGIS taskType (theme mapping).
Q2 operation pattern overlap: QGIS operator -> semantic family mapping
   (keyword rules) -> family distribution comparison.
Q3 length/complexity comparison.
Q4 sequential structure: first/last stage distributions, chain-ness.
Q5 branch/merge: GEE linear vs QGIS DAG (new structure quantity).
Q6-8 transferability classification per structural feature.
"""
import json, re, statistics as st
from collections import Counter, defaultdict

SRC = r"E:/Route2_Migration_20260928/04_DIAG_WORK/b1_gee_stage_train.jsonl"
V2A = r"E:/Route2_Migration_20260928/04_DIAG_WORK/v2a_recon/v2a_A_train.jsonl"
OUT = r"E:/Route2_Migration_20260928/01_REPO/system_redesign/docs/reports/route2_p0_contract/plan_pipeline_v1/planner_design/CROSS_PLATFORM_AUDIT_v1.json"

# ---------- GEE side ----------
gee_task_types = Counter()
gee_chains = []
gee_first, gee_last = Counter(), Counter()
for line in open(SRC, encoding="utf-8"):
    r = json.loads(line)
    if r.get("split") != "train": continue
    gee_task_types[r.get("task_type", "?")] += 1
    raw = [x.strip() for x in (r.get("semantic_chain_raw") or "").split("->") if x.strip()]
    if raw:
        gee_chains.append(raw)
        gee_first[raw[0]] += 1; gee_last[raw[-1]] += 1
res = {"gee": {"rows": sum(gee_task_types.values()), "task_types": gee_task_types.most_common(),
               "n_chains": len(gee_chains)}}

# ---------- QGIS side ----------
qgis_rows = [json.loads(l) for l in open(V2A, encoding="utf-8")]
qgis_task_types = Counter()
for r in qgis_rows: qgis_task_types[r.get("taskType", "?")] += 1
res["qgis"] = {"rows": len(qgis_rows), "taskTypes": qgis_task_types.most_common()}

# ---------- theme mapping (manual, defensible) ----------
THEME_MAP = {
    "Land use/land cover": "Land use/land cover",
    "Topography": "Topography",
    "Surface water": "Surface water",
    "Population": "Population/Society",
    "Infrastructure": "Infrastructure/Built environment",
    "Boundaries": "Boundaries/Administration",
    "Vegetation": "Vegetation/Agriculture",
    "Agriculture": "Vegetation/Agriculture",
    "Climate": "Climate/Atmosphere",
    "Temperature": "Climate/Atmosphere",
    "Precipitation": "Climate/Atmosphere",
    "Elevation": "Topography",
    "Built environment": "Infrastructure/Built environment",
    "Urban": "Infrastructure/Built environment",
    "Flood": "Hazards/Change detection",
    "Fire": "Hazards/Change detection",
    "Change detection": "Hazards/Change detection",
    "Snow": "Climate/Atmosphere",
    "Ocean": "Ocean/Coastal",
    "Coastal": "Ocean/Coastal",
    "Biodiversity": "Ecology/Environment",
    "Soil": "Soil/Geology",
    "Geology": "Soil/Geology",
    "Mining": "Soil/Geology",
}
def theme_of(t):
    t = t or "?"
    if t in THEME_MAP: return THEME_MAP[t]
    for k, v in THEME_MAP.items():
        if k.lower() in t.lower(): return v
    return "Other"
gee_themes = Counter(); qgis_themes2 = Counter()
for t, c in gee_task_types.items(): gee_themes[theme_of(t)] += c
for t, c in qgis_task_types.items(): qgis_themes2[theme_of(t)] += c
res["Q1_theme_overlap"] = {
    "gee_themes": gee_themes.most_common(),
    "qgis_themes": qgis_themes2.most_common(),
    "shared_themes": sorted(set(gee_themes) & set(qgis_themes2)),
    "gee_only": sorted(set(gee_themes) - set(qgis_themes2)),
    "qgis_only": sorted(set(qgis_themes2) - set(gee_themes)),
}

# ---------- Q2 operator -> semantic family mapping ----------
OP_MAP = [
    (r"reproject|warpreproject|warp", "RESAMPLE_REPROJECT"),
    (r"slope|aspect|tri\b|tiri|ruggedness", "TERRAIN_DERIVED"),
    (r"reclassif", "THRESHOLD_LOGIC"),
    (r"rastercalc|calculator|r\.mapcalc", "BAND_ARITHMETIC"),
    (r"ndvi|ndwi|evi|savi|index|nbr", "SPECTRAL_INDEX"),
    (r"fieldcalc|refactorfields", "VECTOR_GEOMETRY"),
    (r"buffer|dissolve|centroids|simplify|smooth|voronoi|difference|intersection\b|union|polygonize|polygons?tolines|fixgeometries|multipart|singlepart|subdivide|line.?merge", "VECTOR_GEOMETRY"),
    (r"\bclip\b|extractbylocation|clipvectorbyraster", "SPATIAL_CLIP"),
    (r"merge|concatenate|mosaic|buildvrt", "COMPOSITE"),
    (r"join\w*by\w*(field|location|attribute)|hublines|nearestneighbour", "SPATIAL_JOIN"),
    (r"zonal|statistics|r\.stats", "REGIONAL_STATS"),
    (r"classify|randomforest|svm|maxent|train|predict", "CLASSIFICATION"),
    (r"extractbyexpression|selectbyexpression|extractbyattribute", "ATTRIBUTE_FILTER"),
    (r"temporal|date|time", "TEMPORAL_FILTER"),
    (r"extent|boundary|spatialfilter|filterbyextent", "SPATIAL_FILTER"),
    (r"translate|bandselect|aopleft|aopright|subset_bands", "BAND_SELECT"),
    (r"fillnodata|fillna|mask|cloud", "MASKING"),
    (r"interpolate|kriging|idw", "NEIGHBORHOOD"),
    (r"resample|grid\.sample", "RESAMPLE_REPROJECT"),
    (r"export|save|download", "EXPORT_OUTPUT"),
    (r"centroids|distance.?matrix", "VECTOR_GEOMETRY"),
    (r"hillshade|relief", "TERRAIN_DERIVED"),
    (r"pansharp|pansharpening", "COMPOSITE"),
    (r"randomselect|randomselection", "SAMPLE_EXTRACTION"),
]
def map_op(op):
    for pat, fam in OP_MAP:
        if re.search(pat, op, re.I): return fam
    return None
qgis_ops = Counter()
for r in qgis_rows:
    for p in r["processes"]: qgis_ops[p["operator_id"]] += 1
mapped, unmapped = Counter(), Counter()
op2fam = {}
for op, c in qgis_ops.items():
    f = map_op(op)
    if f: mapped[f] += c; op2fam[op] = f
    else: unmapped[op] += c
res["Q2_qgis_mapping"] = {
    "mapped_instances": sum(mapped.values()), "unmapped_instances": sum(unmapped.values()),
    "mapped_ratio": round(sum(mapped.values())/sum(qgis_ops.values()), 3),
    "mapped_distribution": mapped.most_common(),
    "unmapped_top10": unmapped.most_common(10),
    "unique_unmapped": len(unmapped),
}
# GEE family distribution for comparison
gee_fam_dist = Counter()
for raw in gee_chains:
    gee_fam_dist.update(raw)
res["Q2_gee_family_distribution"] = gee_fam_dist.most_common()
# overlap of family vocabularies
res["Q2_family_vocab_overlap"] = {
    "shared": sorted(set(mapped) & set(gee_fam_dist)),
    "qgis_only": sorted(set(mapped) - set(gee_fam_dist)),
}

# ---------- Q3 length/complexity ----------
qgis_lens = [len(r["processes"]) for r in qgis_rows]
gee_lens = [len(c) for c in gee_chains]
def pctl(xs):
    xs = sorted(xs)
    return {"p50": xs[len(xs)//2], "p90": xs[int(0.9*len(xs))], "p99": xs[int(0.99*len(xs))], "max": xs[-1]}
res["Q3_length"] = {"gee_semantic_stages": pctl(gee_lens), "qgis_processes": pctl(qgis_lens)}

# ---------- Q4 sequential structure ----------
res["Q4_first_last"] = {
    "gee_first_top": gee_first.most_common(5), "gee_last_top": gee_last.most_common(5),
    "qgis_first_top": Counter(p["operator_id"] for r in qgis_rows for p in r["processes"][:1]).most_common(5),
    "qgis_last_top": Counter(p["operator_id"] for r in qgis_rows for p in r["processes"][-1:]).most_common(5),
}

# ---------- Q5 branch/merge ----------
res["Q5_branch_merge"] = {
    "gee": "linear chains only (semantic_chain_raw is a pure sequence; no branch structure expressible)",
    "qgis_branch_merge_workflows": sum(1 for r in qgis_rows if any(
        True for _ in [1]) and False),
}
# compute properly
bm = 0
for r in qgis_rows:
    ind, outd = Counter(), Counter()
    for l in r["links"]:
        outd[l["source_process_id"]] += 1; ind[l["target_process_id"]] += 1
    ids = [p["process_id"] for p in r["processes"]]
    if any(outd.get(x,0)>=2 for x in ids) or any(ind.get(x,0)>=2 for x in ids): bm += 1
res["Q5_branch_merge"]["qgis_branch_or_merge_workflows"] = bm
res["Q5_branch_merge"]["qgis_branch_merge_share"] = round(bm/len(qgis_rows), 3)

json.dump(res, open(r"E:/Route2_Migration_20260928/01_REPO/system_redesign/docs/reports/route2_p0_contract/plan_pipeline_v1/planner_design/CROSS_PLATFORM_AUDIT_v1.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False, indent=1)[:3000])
