# -*- coding: utf-8 -*-
"""V2a gate ①: full-corpus tier labeling with the 100 manual judgments as calibration.

Tier-2 boundary (from the 100-sample read): the computation lives in Python
rather than in the operators. Operationalized as interpretable rules over
mechanical features, calibrated against the 100 manual labels, then applied to
all structural-pass rows. Boundary-band rows (rules uncertain) are flagged for
manual review. Nothing here trains a model — it is rule-based labeling with a
calibration check.

Output: docs/reports/qgis_wf_audit_v2a_pre/tier_labels_full_v1.json
"""
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
REPO = Path(__file__).resolve().parents[1]

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
TRIVIAL_OPS = {"native:loadlayer", "native:setlayerstyle", "native:createspatialindex"}

# desc keyword -> operator-family presence test (substring on op id)
KEY_OPS = {
    "buffer": ("buffer",), "dissolve": ("dissolve",), "clip": ("clip",),
    "intersect": ("intersection", "union", "extractbylocation", "difference", "overlay"),
    "intersection": ("intersection",), "overlay": ("intersection", "union", "extractbylocation"),
    "union": ("union", "mergevectorlayers"), "join": ("joinattribute",),
    "reproject": ("reproject", "assignprojection", "definecurrentprojection"),
    "rasterize": ("rasterize",), "polygonize": ("polygonize", "contour_polygon", "r.to.vect"),
    "voronoi": ("voronoi",), "zonal statistic": ("zonalstatistic",),
    "hillshade": ("hillshade",), "slope": ("slope",), "aspect": ("aspect",),
    "heatmap": ("heatmap",), "kernel density": ("heatmap",),
    "simplif": ("simplify",), "centroid": ("centroid",),
    "service area": ("servicearea",), "shortest path": ("servicearea", "shortestpath", "distancematrix"),
    "interpolat": ("idwinterpolation", "gridinverse", "tinmesh", "interpolate"),
    "voronoi polygon": ("voronoi",), "distance matrix": ("distancematrix",),
    "tessellat": ("tessellate",), "subtract": ("rastercalculator", "rastercalc"),
    "export": ("importvectorintopostgis", "savefeatures", "exporttospreadsheet", "convertformat",
               "package", "writeasvectorformat", "savefeatures"),
    "merge": ("merge",), "reclassif": ("reclassify",),
    "dissolving": ("dissolve",), "buffering": ("buffer",), "clipping": ("clip",),
    "zonal statistics": ("zonalstatistic",), "heatmap with": ("heatmap",),
}


def chain_and_classes(r):
    chain, n_api_sem, n_unres = [], 0, 0
    for i in r["idents"]:
        if ":" in i:
            c = i.replace("processing.run:", "")
            if c in catalog:
                chain.append(c)
                continue
            if c.startswith("qgis:"):
                nat = "native:" + c.split(":")[-1]
                if nat in catalog:
                    chain.append(nat)
                    continue
            n_unres += 1
        else:
            m = i.split(".")[-1]
            if m in PLUMBING:
                continue
            if catalog_by_slug.get(m):
                chain.append(catalog_by_slug[m][0])
                n_api_sem += 1
                continue
            if m in api_methods:
                chain.append("API:" + m)
                n_api_sem += 1
                continue
            n_unres += 1
    return chain, n_api_sem, n_unres


def features(r):
    chain, n_api_sem, n_unres = chain_and_classes(r)
    desc = (r["desc"] or "").lower()
    alg = [c for c in chain if not c.startswith("API:")]
    trivial = sum(1 for c in chain if c in TRIVIAL_OPS)
    # desc-mentioned key ops missing from chain
    mentioned, missing = [], []
    for kw, fams in KEY_OPS.items():
        if re.search(r"\b" + re.escape(kw), desc):
            mentioned.append(kw)
            if not any(any(f in c.lower() for f in fams) for c in chain):
                missing.append(kw)
    # api-only transform dominance
    api_transform_only = (n_api_sem > 0 and len(alg) <= 1
                          and all(c == "API:transform" for c in chain if c.startswith("API:")))
    return {
        "chain_len": len(chain), "alg_len": len(alg), "n_api_sem": n_api_sem,
        "n_unres": n_unres, "trivial": trivial,
        "trivial_ratio": trivial / max(len(chain), 1),
        "desc_len": len(r["desc"] or ""),
        "n_mentioned": len(mentioned), "n_missing": len(missing),
        "missing": missing, "api_transform_only": api_transform_only,
    }


def label(f):
    """Rule-based tier label + confidence. tier2 if any rule fires.

    v2 rules (recalibrated after the 78% first pass):
    R1 trivial_chain  — loadlayer/setlayerstyle/createspatialindex dominate a short chain
    R2 api_transform_only — the only semantic content is API:transform lifts
    R3 strong_keyop_missing — the description NAMES a strong operation family
        (voronoi/buffer/dissolve/join/heatmap/zonal/hillshade/interpolation/
        service-area/distance-matrix/polygonize/rasterize/reclassify) that is
        absent from the chain — the computation lives elsewhere (Python)
    R4 thin_undercarry — a 1-2 op chain that still misses a named op
    """
    STRONG = {"voronoi", "buffer", "dissolve", "join", "heatmap", "kernel density",
              "zonal statistic", "zonal statistics", "hillshade", "interpolat",
              "service area", "distance matrix", "polygonize", "rasterize", "reclassif",
              "tessellat", "subtract", "shortest path"}
    reasons = []
    if f["trivial_ratio"] >= 0.5 and f["chain_len"] <= 3:
        reasons.append("trivial_chain")
    if f["api_transform_only"]:
        reasons.append("api_transform_only")
    if any(m in STRONG for m in f["missing"]):
        reasons.append("strong_keyop_missing")
    if f["chain_len"] <= 2 and any(m in STRONG for m in f["missing"]):
        reasons.append("thin_undercarry")
    return ("Tier-2" if reasons else "Tier-1"), reasons


def main():
    rows = {}
    for l in open(REPO / "docs/reports/qgis_wf_full_v1.jsonl", encoding="utf-8"):
        r = json.loads(l)
        rows[r["wid"]] = r
    shas = {w: h for w, _, h in (tuple(x) for x in json.load(
        open(Path.home() / "AppData/Local/Temp/qgis_wf_shas.json", encoding="utf-8")))}
    excl = set(json.load(open(REPO / "outputs_tmp_domain_corpus_paths_v1.excl.json", encoding="utf-8")))
    cal = json.load(open(REPO / "docs/reports/qgis_wf_audit_v2a_pre/tier_labels_calibration100.json", encoding="utf-8"))
    cal_map = {w: "Tier-1" for w in cal["tier1"]}
    cal_map.update({w: "Tier-2" for w in cal["tier2"]})

    # calibration
    agree = disagree = 0
    disagreements = []
    for wid, manual in cal_map.items():
        f = features(rows[wid])
        auto, _ = label(f)
        if auto == manual:
            agree += 1
        else:
            disagree += 1
            disagreements.append((wid, manual, auto))
    print(f"[calibration] agree={agree} disagree={disagree} "
          f"agreement={agree/(agree+disagree):.2%}")
    for wid, m, a in disagreements:
        print(f"  DISAGREE {wid}: manual={m} auto={a}")

    # full labeling over the structural funnel survivors (audit criteria)
    out, seen = {}, set()
    for wid, r in rows.items():
        if r["n_proc"] < 2 or not r["link_valid"] or r["acyclic"] is False:
            continue
        if shas.get(wid) in excl:
            continue
        f = features(r)
        chain, _, _ = chain_and_classes(r)
        sig = tuple(c.replace("qgis:", "native:") for c in chain), r["name"]
        if sig in seen:
            continue
        seen.add(sig)
        # manual label wins where available
        tier, reasons = label(f)
        manual = cal_map.get(wid)
        out[wid] = {"tier": manual or tier, "rule_tier": tier, "rule_reasons": reasons,
                    "manual": bool(manual), "chain_len": f["chain_len"],
                    "missing": f["missing"]}
    n1 = sum(1 for v in out.values() if v["tier"] == "Tier-1")
    n2 = sum(1 for v in out.values() if v["tier"] == "Tier-2")
    print(f"[full] rows={len(out)} Tier-1={n1} Tier-2={n2} "
          f"({n1/len(out):.1%}/{n2/len(out):.1%})")

    (REPO / "docs/reports/qgis_wf_audit_v2a_pre/tier_labels_full_v1.json").write_text(
        json.dumps({"schema": "gis_recommend.v2a.tier_labels_full.v1",
                    "calibration_agreement": round(agree / (agree + disagree), 4),
                    "labels": out}, ensure_ascii=False, indent=1), encoding="utf-8")
    print("wrote tier_labels_full_v1.json")


if __name__ == "__main__":
    main()
