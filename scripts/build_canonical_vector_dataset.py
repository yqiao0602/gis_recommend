#!/usr/bin/env python3
"""Build canonical vector planning dataset from QGIS GitHub workflows.

Maps QGIS operator chains to abstract planning steps, then to L3 codes where possible.

Output structure:
{
    "task_text": "...",
    "modality": "vector/raster/mixed",
    "qgis_ops": ["native:buffer", "native:clip"],
    "planning_steps": ["buffer_analysis", "spatial_clip"],
    "l3_steps": ["L3_02_01_01", "L3_02_02_06"],
    "required_step_families": ["buffer", "overlay_clip"],
    "missing_step_families": [],
    "source": "github_qgis_v2",
    "confidence": 0.85
}

Usage:
    python scripts/build_canonical_vector_dataset.py
"""

from __future__ import annotations

import csv, json, sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path: sys.path.insert(0, str(SRC))

FACTS = ROOT / "爬取GithubQGIS" / "facts_summary1000.csv"
ENRICHED = ROOT / "outputs_v2" / "qgis_chain_dataset_v2_enriched_v3.jsonl"
OFFICIAL_OPS = ROOT.parent / "operators-json" / "qgis_operators.json"
ID_MAPPINGS = ROOT / "outputs_v2" / "id_mappings_v2.json"
OUTPUT = ROOT / "outputs_v2" / "canonical_vector_planning_dataset.jsonl"
SUMMARY = ROOT / "outputs_v2" / "canonical_vector_planning_summary.json"

# ── QGIS op → abstract planning step ───────────────────────────────
QGIS_TO_PLANNING = {
    "buffer": "buffer_analysis",
    "multiringconstantbuffer": "buffer_analysis",
    "singlesidedbuffer": "buffer_analysis",
    "bufferbym": "buffer_analysis",
    "clip": "spatial_clip",
    "extractbyextent": "spatial_clip",
    "dissolve": "spatial_aggregation",
    "intersection": "spatial_intersection",
    "difference": "spatial_difference",
    "union": "spatial_union",
    "symmetricaldifference": "spatial_symmetrical_difference",
    "mergevectorlayers": "layer_merge",
    "extractbyexpression": "attribute_filter",
    "selectbyexpression": "attribute_filter",
    "extractbyattribute": "attribute_filter",
    "selectbyattribute": "attribute_filter",
    "extractbylocation": "spatial_filter",
    "selectbylocation": "spatial_filter",
    "joinattributesbylocation": "spatial_join",
    "joinattributestable": "table_join",
    "joinbynearest": "nearest_join",
    "reprojectlayer": "crs_transform",
    "assignprojection": "crs_transform",
    "warpreproject": "crs_transform",
    "fixgeometries": "geometry_repair",
    "snapgeometries": "geometry_repair",
    "simplifygeometries": "geometry_simplify",
    "smoothgeometry": "geometry_smooth",
    "createspatialindex": "index_maintenance",
    "deleteduplicategeometries": "geometry_dedup",
    "deleteholes": "geometry_cleanup",
    "removeduplicatevertices": "geometry_dedup",
    "checkvalidity": "geometry_validation",
    "centroids": "centroid_extract",
    "polygonstolines": "geometry_conversion",
    "linestopolygons": "geometry_conversion",
    "multiparttosingleparts": "geometry_conversion",
    "singlepartstomultipart": "geometry_conversion",
    "splitwithlines": "geometry_split",
    "extractvertices": "geometry_vertices",
    "pointsalonglines": "geometry_sampling",
    "createconstantrasterlayer": "raster_create",
    "creategrid": "grid_generation",
    "voronoi": "tessellation",
    "countpointsinpolygon": "point_aggregation",
    "aggregate": "point_aggregation",
    "fieldcalculator": "field_calculate",
    "refactorfields": "field_restructure",
    "saveraster": "data_export",
    "savefeatures": "data_export",
    "saveselectedfeatures": "data_export",
    "export": "data_export",
    "rasterize": "rasterize_convert",
    "polygonize": "polygonize_convert",
    "pixelstopolygons": "polygonize_convert",
    "rastersampling": "raster_sampling",
    "rastersurfacevolume": "surface_volume",
    "zonalstatistics": "zonal_statistics",
    "zonalstatisticsfb": "zonal_statistics",
    "rastercalculator": "raster_algebra",
    "cliprasterbymasklayer": "raster_clip",
    "cliprasterbyextent": "raster_clip",
    "reclassifybytable": "reclassify",
    "fillnodata": "gap_fill",
    "translate": "format_convert",
    "buildvirtualraster": "raster_mosaic",
    "contour": "contour_generation",
    "heatmapkerneldensityestimation": "density_analysis",
    "slope": "terrain_analysis",
    "aspect": "terrain_analysis",
    "hillshade": "terrain_analysis",
    "randompointsinpolygons": "random_sampling",
    "randompointinsidepolygons": "random_sampling",
    "pixelstopoints": "raster_to_points",
}

# ── Planning step → L3 code ────────────────────────────────────────
PLANNING_TO_L3 = {
    "buffer_analysis": "L3_02_01_01",
    "spatial_clip": "L3_02_02_06",
    "spatial_aggregation": "L3_02_03_05",
    "spatial_overlay": "L3_02_02_06",
    "spatial_intersection": "L3_02_02_01",
    "spatial_difference": "L3_02_02_04",
    "spatial_union": "L3_02_02_02",
    "spatial_symmetrical_difference": "L3_02_02_05",
    "layer_merge": "L3_01_03_04",
    "attribute_filter": "L3_02_06_02",
    "spatial_filter": "L3_02_06_03",
    "spatial_join": "L3_02_04_01",
    "table_join": "L3_02_04_01",
    "nearest_join": "L3_02_04_01",
    "crs_transform": "L3_01_02_03",
    "geometry_repair": "L3_02_07_01",
    "geometry_simplify": "L3_02_07_01",
    "geometry_smooth": "L3_02_07_01",
    "geometry_dedup": "L3_02_07_01",
    "geometry_cleanup": "L3_02_07_01",
    "geometry_validation": "L3_02_07_01",
    "geometry_conversion": "L3_02_05_11",
    "geometry_split": "L3_02_05_11",
    "geometry_vertices": "L3_02_05_11",
    "geometry_sampling": "L3_02_05_11",
    "centroid_extract": "L3_02_05_11",
    "grid_generation": "L3_02_05_12",
    "tessellation": "L3_02_05_11",
    "point_aggregation": "L3_02_04_01",
    "field_calculate": "L3_01_02_06",
    "field_restructure": "L3_01_02_03",
    "data_export": "L3_07_04_01",
    "index_maintenance": "L3_07_01_01",
    "rasterize_convert": "L3_03_01_01",
    "polygonize_convert": "L3_03_01_01",
    "raster_sampling": "L3_03_01_01",
    "surface_volume": "L3_03_02_03",
    "zonal_statistics": "L3_03_02_01",
    "raster_algebra": "L3_03_03_A",
    "raster_clip": "L3_03_01_01",
    "reclassify": "L3_03_04_01",
    "raster_create": "L3_03_07_01",
    "raster_mosaic": "L3_03_07_01",
    "gap_fill": "L3_03_03_A",
    "format_convert": "L3_07_04_05",
    "contour_generation": "L3_04_01_01",
    "density_analysis": "L3_03_02_03",
    "terrain_analysis": "L3_04_01_01",
    "random_sampling": "L3_02_06_01",
    "raster_to_points": "L3_03_01_01",
}

REQUIRED_FAMILIES = {
    "buffer_analysis", "spatial_overlay", "spatial_aggregation",
    "spatial_intersection", "spatial_difference", "spatial_union", "spatial_symmetrical_difference",
    "spatial_clip", "layer_merge", "spatial_filter", "attribute_filter",
    "spatial_join", "crs_transform", "geometry_repair", "geometry_simplify",
    "data_export", "centroid_extract", "geometry_conversion",
    "grid_generation", "tessellation", "point_aggregation",
    "density_analysis", "nearest_join", "zonal_statistics", "field_calculate",
}

def classify_planning_step(op_name):
    n = op_name.lower().replace("native:", "").replace("qgis:", "").replace("gdal:", "").replace("saga:", "").replace("grass7:", "")
    for kw, step in sorted(QGIS_TO_PLANNING.items(), key=lambda x: -len(x[0])):
        if kw in n: return step
    return "other"

def main():
    # Load facts
    facts = {}
    with open(FACTS, "r", encoding="utf-8", errors="replace") as f:
        for row in csv.DictReader(f):
            facts[row["File Name"].strip()] = row

    with open(ENRICHED, "r", encoding="utf-8") as f:
        records = [json.loads(line) for line in f if line.strip()]

    print(f"Input: {len(records)} enriched records")

    dataset = []
    stats = Counter()

    for r in records:
        ops = r["qgis_ops"]
        n = len(ops)
        if n < 2: continue

        planning_steps = [classify_planning_step(o) for o in ops]
        l3_steps = [PLANNING_TO_L3.get(s, "") for s in planning_steps]
        has_l3 = all(l3_steps)
        step_families = list(dict.fromkeys(planning_steps))
        missing = [s for s in step_families if s in REQUIRED_FAMILIES and s == "other"]
        required = [s for s in step_families if s in REQUIRED_FAMILIES]

        fact = facts.get(r.get("source_file",""), {})
        task_name = fact.get("Task Name","") or r.get("task_name","")
        task_desc = fact.get("Task Description","") or r.get("task_description","")
        task_text = f"{task_name}. {task_desc}"[:300].strip()

        q = r.get("quality", {})
        modality = "vector" if q.get("is_pure_vector") else ("raster" if q.get("is_pure_raster") else "mixed")

        record = {
            "task_text": task_text,
            "modality": modality,
            "qgis_ops": ops,
            "planning_steps": planning_steps,
            "l3_steps": l3_steps,
            "has_full_l3": has_l3,
            "required_step_families": required,
            "missing_step_families": missing,
            "source": "github_qgis_v2",
            "source_file": r.get("source_file",""),
            "confidence": 0.85 if has_l3 else (0.60 if required else 0.50),
        }
        dataset.append(record)
        stats["total"] += 1
        if has_l3: stats["has_full_l3"] += 1
        if modality == "vector": stats["vector"] += 1
        elif modality == "raster": stats["raster"] += 1
        else: stats["mixed"] += 1

    # Write
    Path(OUTPUT).parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        for r in dataset:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")

    total = stats["total"]
    print(f"\nCanonical dataset: {total} records")
    print(f"  Full L3:  {stats['has_full_l3']}/{total} ({stats['has_full_l3']/total*100:.1f}%)")
    print(f"  Vector:   {stats['vector']}, Raster: {stats['raster']}, Mixed: {stats['mixed']}")

    # Step family distribution
    step_counter = Counter()
    for r in dataset:
        for s in r["required_step_families"]:
            step_counter[s] += 1
    print(f"\nTop planning step families:")
    for s, c in step_counter.most_common(15):
        print(f"  {s:30s}: {c:4d}")

    # Summary
    with open(SUMMARY, "w", encoding="utf-8") as f:
        json.dump({
            "total_records": total,
            "has_full_l3": stats["has_full_l3"],
            "modality": {"vector": stats["vector"], "raster": stats["raster"], "mixed": stats["mixed"]},
            "unique_planning_steps": len(step_counter),
            "top_steps": dict(step_counter.most_common(30)),
        }, f, indent=2, ensure_ascii=False)
    print(f"\nOutput: {OUTPUT}")
    print(f"Summary: {SUMMARY}")

    # Show sample
    print(f"\nSample records:")
    for r in dataset[:3]:
        print(f'  [{r["modality"]}] {r["task_text"][:100]}')
        print(f'    steps: {" → ".join(r["planning_steps"][:6])}')
        l3s = " → ".join(s for s in r["l3_steps"][:6] if s)
        print(f'    L3:    {l3s if l3s else "(partial)"}')


if __name__ == "__main__":
    main()
