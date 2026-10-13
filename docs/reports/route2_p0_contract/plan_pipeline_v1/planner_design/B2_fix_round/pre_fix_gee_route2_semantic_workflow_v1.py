#!/usr/bin/env python3
"""Route-2 B1 semantic-workflow projection v1.

Projects canonical GEE chains (ee_chain_folded in the frozen GEE-Expanded
rows) to platform-free semantic operation sequences, and audits the
projection (coverage, glue share, many-to-one ratio, uniqueness).

Design ruling (owner, 2026-09-17): the semantic layer is a TRAINING-SIDE
intermediate for B1's GEE stage only. It never bridges to QGIS and is never
used at inference (final output is QGIS graphs). Unlike L3 it does not need
platform coverage; it needs faithfulness at the reasoning level.

Rules are deterministic and auditable: exact-match tables + prefix rules.
Aux glue (scalar plumbing, debug) is dropped from the semantic chain and
counted, never silently.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

DROP_CATEGORIES = {"AUX_VALUE", "AUX_DEBUG"}

TEMPORAL = "TEMPORAL_FILTER"
SPATIAL = "SPATIAL_FILTER"
ATTRIBUTE = "ATTRIBUTE_FILTER"
BAND_SEL = "BAND_SELECT"
ARITH = "BAND_ARITHMETIC"
SPECTRAL = "SPECTRAL_INDEX"
THRESH = "THRESHOLD_LOGIC"
MASK = "MASKING"
AGG = "AGGREGATION"
REGSTAT = "REGIONAL_STATS"
CLASSIF = "CLASSIFICATION"
ACCURACY = "ACCURACY_ASSESSMENT"
SAMPLE = "SAMPLE_EXTRACTION"
CLIP = "SPATIAL_CLIP"
VECTGEOM = "VECTOR_GEOMETRY"
R2V = "RASTER_TO_VECTOR"
NEIGH = "NEIGHBORHOOD"
TERRAIN = "TERRAIN_DERIVED"
CLOUD = "CLOUD_PROCESS"
COMPOSITE = "COMPOSITE"
JOIN = "SPATIAL_JOIN"
RESAMP = "RESAMPLE_REPROJECT"
EXPORT = "EXPORT_OUTPUT"
ITER = "ITERATIVE_APPLY"
COLMGMT = "COLLECTION_MGMT"
RLOAD = "RASTER_LOAD"
VLOAD = "VECTOR_LOAD"
GEOMDEF = "GEOMETRY_DEFINE"
AUX = "AUX_VALUE"
OTHER = "OTHER_UNMAPPED"

# bare method name -> category (receiver stripped by the chain builder)
METHOD_MAP = {
    # temporal
    "filterDate": TEMPORAL, "date": TEMPORAL, "calendarRange": TEMPORAL,
    "dayOfYear": TEMPORAL, "hourOfDay": TEMPORAL, "dateRange": TEMPORAL,
    # spatial filter
    "filterBounds": SPATIAL, "intersects": SPATIAL, "withinDistance": SPATIAL,
    # attribute filter
    "filter": ATTRIBUTE, "filterMetadata": ATTRIBUTE, "metadata": ATTRIBUTE,
    "inList": ATTRIBUTE, "has": ATTRIBUTE,
    # band
    "select": BAND_SEL, "addBands": BAND_SEL, "rename": BAND_SEL,
    "bandNames": BAND_SEL, "toBands": BAND_SEL, "cat": BAND_SEL,
    # arithmetic
    "add": ARITH, "subtract": ARITH, "multiply": ARITH, "divide": ARITH,
    "exp": ARITH, "log": ARITH, "log10": ARITH, "sqrt": ARITH, "abs": ARITH,
    "pow": ARITH, "sin": ARITH, "cos": ARITH, "tan": ARITH, "atan": ARITH,
    "atan2": ARITH, "round": ARITH, "floor": ARITH, "ceil": ARITH, "mod": ARITH,
    "toByte": ARITH, "toShort": ARITH, "toInt": ARITH, "toInt16": ARITH,
    "toInt32": ARITH, "toFloat": ARITH, "toDouble": ARITH, "toUint8": ARITH,
    "unitScale": ARITH, "clamp": ARITH, "expression": ARITH, "pixelArea": ARITH,
    # spectral index
    "normalizedDifference": SPECTRAL,
    # threshold logic
    "gt": THRESH, "gte": THRESH, "lt": THRESH, "lte": THRESH,
    "eq": THRESH, "neq": THRESH, "and": THRESH, "or": THRESH,
    "not": THRESH, "where": THRESH,
    # masking
    "mask": MASK, "updateMask": MASK, "unmask": MASK, "selfMask": MASK,
    # aggregation
    "mean": AGG, "median": AGG, "sum": AGG, "min": AGG, "max": AGG,
    "count": AGG, "product": AGG, "mode": AGG, "stdDev": AGG,
    "sampleStdev": AGG, "variance": AGG, "percentile": AGG,
    "combine": AGG, "reduce": AGG,
    # regional statistics
    "reduceRegion": REGSTAT, "reduceRegions": REGSTAT, "reduceColumns": REGSTAT,
    # classification
    "train": CLASSIF, "classify": CLASSIF,
    "confusionMatrix": ACCURACY, "errorMatrix": ACCURACY,
    # sampling
    "sampleRegions": SAMPLE, "stratifiedSample": SAMPLE, "sample": SAMPLE,
    # clip
    "clip": CLIP, "clipToCollection": CLIP,
    # vector geometry
    "buffer": VECTGEOM, "area": VECTGEOM, "intersection": VECTGEOM,
    "union": VECTGEOM, "difference": VECTGEOM, "symmetricDifference": VECTGEOM,
    "convexHull": VECTGEOM, "simplify": VECTGEOM, "dissolve": VECTGEOM,
    "centroid": VECTGEOM, "distance": VECTGEOM, "geometry": VECTGEOM,
    "perimeter": VECTGEOM, "length": VECTGEOM, "bounds": SPATIAL,
    # raster<->vector
    "reduceToVectors": R2V,
    # neighborhood
    "focalMean": NEIGH, "focalMedian": NEIGH, "focalMax": NEIGH,
    "focalMin": NEIGH, "focalMode": NEIGH, "convolve": NEIGH,
    # terrain
    "slope": TERRAIN, "aspect": TERRAIN, "hillshade": TERRAIN,
    # cloud
    "simpleCloudScore": CLOUD, "cloudScore": CLOUD, "cloudProject": CLOUD,
    # composite
    "mosaic": COMPOSITE, "qualityMosaic": COMPOSITE, "simpleComposite": COMPOSITE,
    "composite": COMPOSITE,
    # join
    "saveFirst": JOIN, "saveAll": JOIN, "saveBest": JOIN, "apply": JOIN,
    # resample / reproject
    "resample": RESAMP, "reproject": RESAMP,
    # iterative
    "map": ITER, "iterate": ITER,
    # collection management
    "sort": COLMGMT, "first": COLMGMT, "limit": COLMGMT, "distinct": COLMGMT,
    "size": COLMGMT, "merge": COLMGMT, "flatten": COLMGMT,
    # aux (dropped)
    "set": AUX, "setMulti": AUX, "get": AUX, "getInfo": AUX, "evaluate": AUX,
    "aside": AUX, "toList": AUX, "style": AUX, "visualize": AUX,
    "paint": AUX, "copyProperties": AUX, "makeIndex": AUX,
}

# full canonical names with dedicated semantics (override prefix rules)
EXACT_MAP = {
    "ee.Image": RLOAD, "ee.ImageCollection": RLOAD,
    "ee.ImageCollection.fromImages": RLOAD,
    "ee.FeatureCollection": VLOAD, "ee.Feature": VLOAD,
    "ee.Filter": ATTRIBUTE,
    "ee.Filter.date": TEMPORAL, "ee.Filter.calendarRange": TEMPORAL,
    "ee.Filter.dayOfYear": TEMPORAL, "ee.Filter.hourOfDay": TEMPORAL,
    "ee.Filter.dateRangeContains": TEMPORAL,
    "ee.Filter.bounds": SPATIAL, "ee.Filter.intersects": SPATIAL,
    "ee.Filter.withinDistance": SPATIAL, "ee.Filter.isContained": SPATIAL,
    "ee.Filter.geometry": SPATIAL,
    "ee.Filter.eq": ATTRIBUTE, "ee.Filter.neq": ATTRIBUTE,
    "ee.Filter.gt": ATTRIBUTE, "ee.Filter.gte": ATTRIBUTE,
    "ee.Filter.lt": ATTRIBUTE, "ee.Filter.lte": ATTRIBUTE,
    "ee.Filter.and": ATTRIBUTE, "ee.Filter.or": ATTRIBUTE,
    "ee.Filter.not": ATTRIBUTE, "ee.Filter.inList": ATTRIBUTE,
    "ee.Filter.metadata": ATTRIBUTE, "ee.Filter.equals": ATTRIBUTE,
    "ee.Filter.greaterThan": ATTRIBUTE, "ee.Filter.lessThan": ATTRIBUTE,
    "ee.Filter.stringContains": ATTRIBUTE, "ee.Filter.listContains": ATTRIBUTE,
    "ee.Filter.rangeContains": ATTRIBUTE,
    "ee.Filter.notNull": ATTRIBUTE, "ee.Filter.has": ATTRIBUTE,
    "ee.Algorithms.Terrain": TERRAIN,
    "ee.Algorithms.Landsat.simpleComposite": COMPOSITE,
    "ee.Algorithms.Landsat.simpleCloudScore": CLOUD,
    "ee.Algorithms.If": AUX, "ee.Algorithms.While": AUX,
    "ee.Image.constant": ARITH, "ee.Image.cat": BAND_SEL,
    "ee.Image.pixelLonLat": ARITH, "ee.Image.pixelArea": ARITH,
    "ee.Image.float": ARITH, "ee.Image.byte": ARITH, "ee.Image.int": ARITH,
    "ee.Image.short": ARITH, "ee.Image.long": ARITH, "ee.Image.double": ARITH,
    "ee.Image.int16": ARITH, "ee.Image.int32": ARITH, "ee.Image.int8": ARITH,
    "ee.Image.uint8": ARITH, "ee.Image.uint16": ARITH, "ee.Image.uint32": ARITH,
    "ee.Image.arrayProject": AUX, "ee.Image.arrayOr": AUX,
    "ee.Image.arrayArg": AUX, "ee.Image.arrayGet": AUX,
    "ee.Image.arrayFlatten": AUX, "ee.Image.arraySort": AUX,
    "ee.Image.arrayMask": MASK, "ee.Image.arrayCat": AUX,
    "ee.Clusterer.wekaKMeans": CLASSIF, "ee.Clusterer.wekaCobweb": CLASSIF,
    "ee.Clusterer.wekaXMeans": CLASSIF, "ee.Clusterer.wekaCascadeKMeans": CLASSIF,
    "ee.Image.propertyNames": AUX, "ee.Image.matrixMultiply": ARITH,
    "ee.Image.toArray": AUX, "ee.Image.cast": ARITH, "ee.Image.remap": ARITH,
    "ee.ErrorMargin": AUX, "ee.Projection": AUX, "ee.DateRange": AUX,
    "ee.Image.projection": AUX, "ee.Algorithms.IsEqual": AUX,
    "ee.Algorithms.Image.Segmentation.SNIC": NEIGH,
    "ee.Algorithms.Image.Segmentation.Slic": NEIGH,
    "ee.FeatureCollection.reduceToImage": "VECTOR_TO_RASTER",
    "ee.FeatureCollection.randomPoints": SAMPLE,
}

AUX_PREFIXES = ("ee.Number.", "ee.List.", "ee.Date.", "ee.Dictionary.", "ee.String.",
                "ee.deserializers.", "ee.serializers.", "ee.Array.")
# bare class constructors and namespace roots (scalar/array glue, dropped)
BARE_AUX = {"ee.Number", "ee.Date", "ee.List", "ee.String", "ee.Dictionary",
            "ee.Array", "ee.Geometry", "ee.Algorithms", "ee.Terrain",
            "ee.Filter.string", "ee.Filter.metadata"}


def classify(token: str) -> str:
    if token in EXACT_MAP:
        return EXACT_MAP[token]
    if token in BARE_AUX:
        return AUX if token not in ("ee.Terrain",) else TERRAIN
    if token.startswith(AUX_PREFIXES):
        return AUX
    if token.startswith("ee.Reducer."):
        return AGG
    if token.startswith("ee.Kernel."):
        return NEIGH
    if token.startswith("ee.Geometry."):
        return GEOMDEF
    if token.startswith("Export."):
        return EXPORT
    if token.startswith("ee.Terrain."):
        return TERRAIN
    if token.startswith("ee.Join."):
        return JOIN
    if token.startswith("ee.Classifier."):
        return ACCURACY if "confusion" in token or "errorMatrix" in token else CLASSIF
    if token.startswith("ee.Filter."):
        return METHOD_MAP.get(token.split(".")[-1], ATTRIBUTE)
    if token.startswith("ee.Algorithms."):
        meth = token.split(".")[-1]
        if "Terrain" in token:
            return TERRAIN
        if "Composite" in token:
            return COMPOSITE
        if "loud" in meth:
            return CLOUD
        return METHOD_MAP.get(meth, OTHER)
    if token.startswith(("ee.ImageCollection.", "ee.Image.", "ee.FeatureCollection.",
                         "ee.Feature.", "ee.Geometry.")):
        return METHOD_MAP.get(token.split(".")[-1], OTHER)
    # bare method
    if "." not in token:
        return METHOD_MAP.get(token, OTHER)
    return OTHER


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--rows", type=Path, required=True,
                    help="GEE-Expanded pilot_rows.jsonl (frozen)")
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    args.out.mkdir(parents=True, exist_ok=True)

    cat_counter = Counter()
    unmapped = Counter()
    other_rows = 0
    n_rows = 0
    sem_rows = []
    m21 = Counter()          # semantic chain -> distinct canonical chains
    canon_by_sem = defaultdict(set)

    with open(args.rows, encoding="utf-8") as fh:
        for line in fh:
            r = json.loads(line)
            n_rows += 1
            cats = []
            for tok in r["ee_chain_folded"].split(" -> "):
                c = classify(tok)
                cat_counter[c] += 1
                if c == OTHER:
                    unmapped[tok] += 1
                if c not in DROP_CATEGORIES and c != OTHER:
                    cats.append(c)
                elif c == OTHER:
                    cats.append(c)   # keep OTHER visible in chain for audit
            sem = " -> ".join(cats)
            canon_by_sem[sem].add(r["ee_chain_folded"])
            sem_rows.append({
                "script": r["script"],
                "split": r["split"],
                "task_type": r["task_type"],
                "instruction": r["instruction"],
                "semantic_workflow": sem,
                "gee_canonical_chain": r["ee_chain_folded"],
                "author_proxy": r["author_proxy"],
            })

    total_tok = sum(cat_counter.values())
    dropped = sum(v for k, v in cat_counter.items() if k in DROP_CATEGORIES)
    other = cat_counter.get(OTHER, 0)
    mapped_kept = total_tok - dropped - other
    lens = [len(r["semantic_workflow"].split(" -> ")) for r in sem_rows]
    lens.sort()
    unique_sem = len(canon_by_sem)
    fan_out = sorted((len(v) for v in canon_by_sem.values()), reverse=True)

    stats = {
        "rows": n_rows,
        "tokens_total": total_tok,
        "token_coverage": {
            "mapped_kept": mapped_kept,
            "mapped_kept_pct": round(100 * mapped_kept / total_tok, 2),
            "aux_dropped": dropped,
            "aux_dropped_pct": round(100 * dropped / total_tok, 2),
            "other_unmapped": other,
            "other_unmapped_pct": round(100 * other / total_tok, 2),
        },
        "categories": dict(cat_counter.most_common()),
        "top_unmapped_tokens": unmapped.most_common(40),
        "rows_containing_other": other_rows,
        "semantic_chain_len": {
            "median": statistics.median(lens), "p90": lens[int(len(lens) * 0.9)],
            "max": lens[-1],
        },
        "unique_semantic_workflows": unique_sem,
        "canonical_to_semantic_fanout": {
            "max_canonicals_per_semantic": fan_out[0],
            "p50_canonicals_per_semantic": fan_out[len(fan_out) // 2],
        },
    }
    (args.out / "semantic_stats.json").write_text(
        json.dumps(stats, indent=2, ensure_ascii=False), encoding="utf-8")
    with open(args.out / "semantic_rows.jsonl", "w", encoding="utf-8") as fh:
        for r in sem_rows:
            fh.write(json.dumps(r, ensure_ascii=False) + "\n")

    print(json.dumps({k: stats[k] for k in
                      ("rows", "token_coverage", "semantic_chain_len",
                       "unique_semantic_workflows", "canonical_to_semantic_fanout")},
                     indent=1, ensure_ascii=False))
    print("top unmapped:", unmapped.most_common(15))
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
