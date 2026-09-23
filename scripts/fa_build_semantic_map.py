#!/usr/bin/env python3
"""FA-D2 precondition: build qgis_op_semantic_map_v1 (deterministic, frozen).

Maps the OBSERVED operator vocabulary (train+dev+test gold ops of v2a_A plus
the three locked test-111 prediction arms) to coarse platform-agnostic
semantic classes via ORDERED keyword rules (first match wins). No LLM, no
similarity. OTHER_UNMAPPED is preserved — nothing is force-classified.

One refinement pass is allowed before freeze; after this script writes
fa_semantic_map_v1.json the table is frozen for all FA analyses.
"""
import json
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from route2_training.harness import text_to_graph  # noqa: E402

REPO = Path(__file__).resolve().parents[1]

# (class, keywords) — ORDER ENCODES PRECEDENCE (e.g. "clipraster" before
# "clip" so raster clips don't fall into the vector class; "joinbynearest"
# before "join"; "mergevectorlayers" before "merge").
RULES = [
    ("RASTER_CLIP",      ["clipraster"]),
    ("VECTOR_CLIP",      ["native:clip", "gdal:clip"]),
    ("SPATIAL_FILTER",   ["extractbylocation", "selectbylocation", "extractbyextent"]),
    ("ATTRIBUTE_FILTER", ["extractbyexpression", "extractbyattribute",
                          "selectbyexpression", "selectbyattribute"]),
    ("BUFFER",           ["buffer"]),
    ("TERRAIN",          ["slope", "aspect", "hillshade", "relief", "ruggedness"]),
    ("HYDRO",            ["watershed", "water.outlet", "fill.dir"]),
    ("RASTER_CALC",      ["rastercalculator", "rastercalc", "native:rastercalc"]),
    ("RECLASSIFY",       ["reclassify"]),
    ("ZONAL_STATS",      ["zonalstatistics", "zonalhistogram", "zonal"]),
    ("RASTER_SAMPLE",    ["rastersampling"]),
    ("REPROJECT",        ["reproject", "warp", "assignprojection"]),
    ("RASTERIZE",        ["rasterize"]),
    ("POLYGONIZE",       ["polygonize", "r.to.vect", "pixelstopolygons"]),
    ("CONTOUR",          ["contour"]),
    ("RASTER_MERGE",     ["buildvirtualraster", "gdal:merge"]),
    ("RASTER_CALC",      ["rastercalculator", "rastercalc", "mapcalc"]),
    ("RASTER_CONVERT",   ["translate", "convertformat", "fillnodata", "sieve"]),
    ("VECTOR_MERGE",     ["mergevectorlayers", "buildvirtualvector"]),
    ("OVERLAY",          ["union", "intersection", "difference", "symdifference", "overlay"]),
    ("PROXIMITY",        ["distancematrix", "distancetonearesthub", "joinbynearest", "proximity"]),
    ("JOIN",             ["joinattributes", "joinby", "join"]),
    ("AGGREGATE_STATS",  ["countpointsinpolygon", "statisticsbycategories", "aggregate",
                          "basicstatistics", "uniquevalues", "statistics", "cellstatistics"]),
    ("ATTR_TABLE",       ["fieldcalculator", "refactorfields", "deletecolumn", "retainfields",
                          "renametablefield", "addautoincrementalfield", "addgeometrycolumns",
                          "adduniquevalueindexfield", "dropfields", "orderbyexpression",
                          "stringconcatenation", "addxyfields", "addfieldtoattributestable",
                          "removeduplicatesbyattribute"]),
    ("SPLIT",            ["split"]),
    ("DISSOLVE",         ["dissolve"]),
    ("GEOM_MODIFY",      ["fixgeometries", "snap", "checkvalidity", "deleteholes", "smooth",
                          "simplify", "densify", "dropmzvalues", "deleteduplicate",
                          "removeduplicate", "reconstructgeneralized", "setmvalue",
                          "setzvalue", "extendlines"]),
    ("GEOM_CONVERT",     ["polygonstolines", "linestopolygons", "pointstopath", "explodelines",
                          "multiparttosingleparts", "promotetomulti", "centroids",
                          "extractvertices", "extractspecificvertices", "pixelstopoints",
                          "pointsalonglines", "collect", "swapxy", "geometrybyexpression"]),
    ("GEN_GEOMETRY",     ["creategrid", "randompoints", "generatepointspixelcentroidsinpolygon",
                          "rectanglesovalsdiamonds", "createpointslayer", "layerextent"]),
    ("IO_MGMT",          ["postgis", "savefeatures", "saveselectedfeatures", "loadlayer",
                          "filedownloader", "setlayerstyle", "createspatialindex",
                          "packagelayers", "exportlayers", "extractlayers", "package",
                          "spreadsheet", "exportto"]),
]


def classify(op: str):
    low = op.lower()
    for cls, kws in RULES:
        for kw in kws:
            if kw in low:
                return cls, kw
    return "OTHER_UNMAPPED", None


def collect_vocab():
    vocab = Counter()
    for split in ("train", "dev", "test"):
        for line in (REPO / f"docs/reports/v2a_manifest/v2a_A_{split}.jsonl").read_text(
                encoding="utf-8").splitlines():
            r = json.loads(line)
            for p in r["processes"]:
                vocab[p["operator_id"]] += 1
    for f in ("C0_ep20", "A1_ep15", "B1_ep18"):
        for line in (REPO / f"docs/reports/route2_p0_contract/test111_final_v1/{f}_predictions.jsonl").read_text(
                encoding="utf-8").splitlines():
            r = json.loads(line)
            lines = [l.strip() for l in (r.get("raw_generation") or "").splitlines() if l.strip()]
            if not lines:
                continue
            try:
                procs, _ = text_to_graph(lines[0])
            except ValueError:
                continue
            for p in procs:
                vocab[p["operator_id"]] += 1
    return vocab


def main() -> int:
    vocab = collect_vocab()
    mapping, audit = {}, {"by_class": Counter(), "other": Counter(), "rules_hit": Counter()}
    for op, n in vocab.items():
        cls, kw = classify(op)
        mapping[op] = {"class": cls, "rule": kw, "instances": n}
        audit["by_class"][cls] += n
        if cls == "OTHER_UNMAPPED":
            audit["other"][op] = n
        if kw:
            audit["rules_hit"][f"{cls}<{kw}>"] += n

    covered = sum(n for op, n in vocab.items() if mapping[op]["class"] != "OTHER_UNMAPPED")
    out = {
        "schema": "gis_recommend.transfer.fa.semantic_map_v1",
        "version": "v1",
        "n_rules": len(RULES),
        "n_classes": len({c for c, _ in RULES}) + 1,
        "observed_vocab": len(vocab),
        "observed_instances": sum(vocab.values()),
        "coverage_rate": round(covered / max(sum(vocab.values()), 1), 4),
        "mapping": mapping,
        "audit": {"by_class": dict(audit["by_class"]),
                  "other": dict(audit["other"]),
                  "rules_hit": dict(audit["rules_hit"])},
    }
    dest = REPO / "scripts" / "fa_semantic_map_v1.json"
    dest.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print("vocab:", len(vocab), "instances:", sum(vocab.values()),
          "coverage:", out["coverage_rate"])
    print("OTHER_UNMAPPED instances:", sum(audit["other"].values()),
          "distinct:", len(audit["other"]))
    for op, n in sorted(audit["other"].items(), key=lambda kv: -kv[1])[:25]:
        print("  OTHER %6d  %s" % (n, op))
    print("wrote", dest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
