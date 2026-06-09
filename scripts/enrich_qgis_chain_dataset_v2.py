#!/usr/bin/env python3
"""Enrich qgis_chain_dataset_v2.jsonl with full metadata.

Step 1: Load v2 candidate pool → add operator_names, modality, L3/native bridge, semantic tags.
Step 2: Filter vector subset for downstream training.

Usage:
    python scripts/enrich_qgis_chain_dataset_v2.py
    python scripts/enrich_qgis_chain_dataset_v2.py --min-length 2 --max-length 15
"""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

V2_INPUT = ROOT / "outputs_v2" / "qgis_chain_dataset_v2.jsonl"
OFFICIAL_OPS = ROOT.parent / "operators-json" / "qgis_operators.json"
LEGACY_CATALOG = ROOT / "爬取GithubQGIS" / "QGIS_Input.csv"
CROSSWALK = ROOT / "outputs_v2" / "qgis_alg_id_crosswalk.json"
ID_MAPPINGS = ROOT / "outputs_v2" / "id_mappings_v2.json"

OUTPUT_ENRICHED = ROOT / "outputs_v2" / "qgis_chain_dataset_v2_enriched.jsonl"
OUTPUT_SUMMARY = ROOT / "outputs_v2" / "qgis_chain_dataset_v2_enriched_summary.json"
OUTPUT_VECTOR = ROOT / "outputs_v2" / "qgis_vector_chain_candidates.jsonl"

VECTOR_KW = {
    "buffer", "clip", "dissolve", "intersection", "difference",
    "mergevectorlayers", "extractbyexpression", "extractbylocation",
    "joinattributesbylocation", "joinattributestable",
    "reprojectlayer", "fixgeometries", "simplifygeometries",
    "snapgeometries", "creategrid", "joinbynearest",
    "centroids", "countpointsinpolygon", "polygonstolines",
    "splitwithlines", "refactorfields",
}

# ── Loaders ────────────────────────────────────────────────────────

def load_official_ops(path: Path) -> dict[str, dict]:
    with path.open("r", encoding="utf-8") as f:
        return {str(o.get("identifier", "")).lower().strip(): o for o in json.load(f)}


def load_legacy_catalog(path: Path) -> dict[str, dict]:
    cat = {}
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        for row in csv.reader(f):
            if len(row) < 6: continue
            aid = row[5].strip().lower()
            dtype = "unknown"
            for col in row[8:]:
                if col.strip() in ("vector", "raster"):
                    dtype = col.strip(); break
            cat[aid] = {"data_type": dtype}
    return cat


def load_crosswalk(path: Path) -> dict[str, dict]:
    if not path.exists(): return {}
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("entries", {})


def load_l3_mapping(path: Path) -> dict[str, str]:
    with path.open("r", encoding="utf-8") as f:
        idm = json.load(f)
    return {k.lower().strip(): v.get("primary_l3", "") if isinstance(v, dict) else ""
            for k, v in idm.get("mapping_metadata", {}).get("qgis_to_l3", {}).items()}


# ── Semantic tags ──────────────────────────────────────────────────

QGIS_SEMANTIC_TAGS = {
    "reprojectlayer": "vector_crs_transform",
    "fixgeometries": "geometry_repair",
    "snapgeometries": "geometry_repair",
    "simplifygeometries": "geometry_simplify",
    "smoothgeometry": "geometry_smooth",
    "checkvalidity": "geometry_validation",
    "deleteholes": "geometry_cleanup",
    "deleteduplicategeometries": "geometry_dedup",
    "polygonstolines": "geometry_boundary",
    "linestopolygons": "geometry_conversion",
    "extractvertices": "geometry_vertices",
    "pointsalonglines": "geometry_sampling",
    "splitwithlines": "geometry_split",
    "createspatialindex": "index_maintenance",
    "saveselectedfeatures": "data_export",
    "savefeatures": "data_export",
    "rasterize": "rasterize_convert",
    "polygonize": "polygonize_convert",
    "pixelstopolygons": "polygonize_convert",
    "contour": "surface_derivative",
    "joinattributestable": "table_join",
    "joinattributesbylocation": "spatial_join",
    "creategrid": "grid_generation",
    "extractbyexpression": "attribute_filter",
    "selectbyexpression": "attribute_select",
    "extractbylocation": "spatial_filter",
    "selectbylocation": "spatial_select",
    "refactorfields": "field_restructure",
    "renametablefield": "field_rename",
    "deletecolumn": "field_remove",
    "addautoincrementalfield": "field_add",
    "fieldcalculator": "field_calculate",
    "centroids": "centroid_extract",
    "minimumboundinggeometry": "bounding_geometry",
    "symmetricaldifference": "spatial_overlay",
    "mergevectorlayers": "layer_merge",
    "multiringconstantbuffer": "buffer_variant",
    # Missing operators from 80-task open landing eval
    "voronoi": "voronoi", "thiessen": "voronoi",
    "heatmapkerneldensityestimation": "density_heatmap",
    "joinbynearest": "nearest_neighbor", "distancetonearesthub": "nearest_neighbor",
    "concavehull": "concave_hull", "convexhull": "convex_hull",
    "delaunaytriangulation": "triangulation",
    "rastersampling": "raster_sampling", "rastersurfacevolume": "surface_volume",
    "zonalstatistics": "zonal_statistics", "zonalstatisticsfb": "zonal_statistics",
    "extractbyextent": "spatial_clip",
    "difference": "spatial_overlay",
    "countpointsinpolygon": "point_count",
    "randompointsinpolygons": "random_sampling",
    "smooth": "geometry_smooth", "smoothgeometry": "geometry_smooth",
}


def build_semantic_tags(ops: list[str]) -> list[str]:
    tags, seen = [], set()
    for op in ops:
        name = op.lower().replace("native:", "").replace("qgis:", "").replace("gdal:", "").replace("saga:", "")
        for kw, tag in QGIS_SEMANTIC_TAGS.items():
            if kw in name and tag not in seen:
                tags.append(tag); seen.add(tag); break
    return tags


# ── Main ───────────────────────────────────────────────────────────

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=str(V2_INPUT))
    parser.add_argument("--min-length", type=int, default=2)
    parser.add_argument("--max-length", type=int, default=15)
    args = parser.parse_args(argv)

    official = load_official_ops(OFFICIAL_OPS)
    legacy = load_legacy_catalog(LEGACY_CATALOG)
    xwalk = load_crosswalk(CROSSWALK)
    l3_map = load_l3_mapping(ID_MAPPINGS)

    # Read v2 candidates
    records = []
    with Path(args.input).open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line: continue
            records.append(json.loads(line))

    print(f"Loaded {len(records)} records from {args.input}")

    enriched = []
    stats = Counter()
    vector_candidates = []

    for r in records:
        ops = r["qgis_ops"]
        n = len(ops)
        if n < args.min_length or n > args.max_length:
            stats["rejected_length"] += 1
            continue

        # Operator names
        names = []
        all_in_catalog = True
        data_types = []
        for op in ops:
            o = official.get(op.lower(), {})
            name = o.get("name", op) if o else op
            names.append(name)
            # Data type from legacy
            dt = legacy.get(op.lower(), {}).get("data_type", "unknown")
            data_types.append(dt)
            if not o: all_in_catalog = False

        # Modality
        vec = sum(1 for t in data_types if t == "vector")
        rast = sum(1 for t in data_types if t == "raster")
        if vec > 0 and rast > 0:
            modality = "mixed"
        elif rast > vec:
            modality = "pure_raster"
        else:
            modality = "pure_vector"

        # L3 mapping via crosswalk + name-based
        l3_seq = []
        has_full_l3 = True
        for op in ops:
            l3 = None
            if op.lower() in xwalk:
                e = xwalk[op.lower()]
                if e.get("bridge_type") == "l3_bridge":
                    l3 = e.get("l3_code", "")
            if not l3:
                o = official.get(op.lower(), {})
                name = o.get("name", "").lower().strip() if o else ""
                if name:
                    l3 = l3_map.get(name, "")
            if not l3:
                has_full_l3 = False
            l3_seq.append(l3)

        # Semantic tags
        sem_tags = build_semantic_tags(ops)

        # Native bridge
        native_bridge_ops = []
        for op in ops:
            e = xwalk.get(op.lower(), {})
            if e.get("bridge_type") == "native_bridge":
                native_bridge_ops.append(e.get("l3_code", ""))

        entry = {
            "qgis_ops": ops,
            "operator_names": names,
            "n_steps": n,
            "modality": modality,
            "quality": {
                "is_pure_vector": modality == "pure_vector",
                "is_pure_raster": modality == "pure_raster",
                "is_mixed": modality == "mixed",
                "all_in_catalog": all_in_catalog,
                "vec_count": vec,
                "rast_count": rast,
            },
            "optional_l3_sequence": l3_seq if has_full_l3 else None,
            "has_full_l3": has_full_l3,
            "qgis_semantic_tags": sem_tags,
            "native_bridge_ops": native_bridge_ops,
            "training_targets": (["qgis_head", "l3_head"] if has_full_l3 else ["qgis_head"]),
            "source": "github_qgis_v2",
            "source_file": r.get("source_file", ""),
        }
        enriched.append(entry)
        stats["total_enriched"] += 1
        stats[f"modality_{modality}"] += 1
        if has_full_l3: stats["has_full_l3"] += 1

        # Vector filter
        has_vector_kw = any(
            any(kw in op.lower().replace("native:", "").replace("qgis:", "")
                for kw in VECTOR_KW) for op in ops
        )
        if (modality in ("pure_vector", "mixed")
                and all_in_catalog
                and has_vector_kw
                and n >= args.min_length):
            vector_candidates.append(entry)
            stats["vector_candidates"] += 1

    # Write enriched
    Path(OUTPUT_ENRICHED).parent.mkdir(parents=True, exist_ok=True)
    with OUTPUT_ENRICHED.open("w", encoding="utf-8") as f:
        for e in enriched:
            f.write(json.dumps(e, ensure_ascii=False) + "\n")
    print(f"\nEnriched: {len(enriched)} records -> {OUTPUT_ENRICHED}")

    # Write vector subset
    with OUTPUT_VECTOR.open("w", encoding="utf-8") as f:
        for v in vector_candidates:
            f.write(json.dumps(v, ensure_ascii=False) + "\n")
    print(f"Vector candidates: {len(vector_candidates)} records -> {OUTPUT_VECTOR}")

    # Summary
    summary = {
        "input_records": len(records),
        "rejected_length": stats["rejected_length"],
        "total_enriched": stats["total_enriched"],
        "has_full_l3": stats["has_full_l3"],
        "modality_pure_vector": stats["modality_pure_vector"],
        "modality_pure_raster": stats["modality_pure_raster"],
        "modality_mixed": stats["modality_mixed"],
        "vector_candidates": stats["vector_candidates"],
        "output_enriched": str(OUTPUT_ENRICHED),
        "output_vector": str(OUTPUT_VECTOR),
    }
    with OUTPUT_SUMMARY.open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"\nSummary -> {OUTPUT_SUMMARY}")
    print(f"  Full L3: {stats['has_full_l3']}/{stats['total_enriched']} ({stats['has_full_l3']/max(stats['total_enriched'],1)*100:.1f}%)")
    print(f"  Vector candidates: {stats['vector_candidates']}")


if __name__ == "__main__":
    main()
