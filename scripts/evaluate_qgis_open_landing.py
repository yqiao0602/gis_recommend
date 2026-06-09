#!/usr/bin/env python3
"""Evaluate QGIS landing on real user-like tasks (vector/raster/mixed).

Uses the fixed retriever (v3 enriched) to retrieve QGIS chains for 80
open-ended user task descriptions, then outputs results for manual A/B/C grading.

Usage:
    python scripts/evaluate_qgis_open_landing.py
    python scripts/evaluate_qgis_open_landing.py --top-k 5
"""

from __future__ import annotations

import csv, json, sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path: sys.path.insert(0, str(SRC))

from gis_recommend.planning.qgis_chain_planner import QGISChainRetriever, QGISChainEvaluator

DS_PATH = ROOT / "outputs_v2" / "qgis_chain_dataset_v2_enriched_v3.jsonl"
CATALOG = ROOT / "爬取GithubQGIS" / "QGIS_Input.csv"
OUT_DIR = ROOT / "outputs_v2" / "diagnostics" / "open_landing_eval"

# ── Real user-like tasks (80 total) ────────────────────────────────
TASKS = [
    # Vector (40)
    ("vec","Build a 500m buffer around all major roads and clip the result to the city boundary"),
    ("vec","Dissolve parcel polygons by land use type and calculate the total area per class"),
    ("vec","Merge three county shapefiles into a single regional layer"),
    ("vec","Intersect flood hazard zones with residential building footprints"),
    ("vec","Remove the overlapping area between proposed development sites and protected wetlands"),
    ("vec","Create a single unified polygon from multiple watershed boundary layers"),
    ("vec","Clip the electrical transmission line network to the project corridor extent"),
    ("vec","Spatially join census population data to school district polygons"),
    ("vec","Extract all road segments where the surface type is gravel"),
    ("vec","Select buildings that are within 200 meters of a known fault line"),
    ("vec","Reproject the monitoring station layer from WGS84 to UTM zone 33N"),
    ("vec","Fix invalid geometries in the building footprint layer before analysis"),
    ("vec","Simplify the river network geometry for display at 1:250,000 scale"),
    ("vec","Create a regular grid of 1km x 1km sampling cells over the study area"),
    ("vec","Generate Voronoi polygons around weather station points"),
    ("vec","Create a heatmap showing the density of traffic accident points"),
    ("vec","Find the nearest health facility for each village and calculate travel distance"),
    ("vec","Merge all pipeline segments and dissolve boundaries between connected sections"),
    ("vec","Extract by location: find well points that lie within the contaminated zone polygon"),
    ("vec","Join attribute table of soil properties to farm field polygons by field ID"),
    ("vec","Convert polygon boundaries to polylines for cartographic styling"),
    ("vec","Extract the centroid point of each building footprint polygon"),
    ("vec","Split road centerlines at their intersection points"),
    ("vec","Delete holes smaller than 10 square meters from building footprint polygons"),
    ("vec","Smooth the contour lines generated from the DEM for a cleaner map appearance"),
    ("vec","Create a concave hull around GPS tracking points to define the animal home range"),
    ("vec","Generate Thiessen polygons from rain gauge station locations"),
    ("vec","Perform Delaunay triangulation on borehole point data"),
    ("vec","Aggregate incident points by district and count the number per zone"),
    ("vec","Select features by expression: population greater than 50000 AND area less than 100"),
    ("vec","Update the admin boundary layer by adding a field with the region name"),
    ("vec","Export the selected land parcels to a new shapefile"),
    ("vec","Reproject county boundaries to match the project CRS and merge them"),
    ("vec","Buffer streams by 30m, clip to the watershed boundary, dissolve by stream order"),
    ("vec","Snap road endpoints to the nearest intersection vertex"),
    ("vec","Delete duplicate geometries from the merged parcel dataset"),
    ("vec","Join the traffic count table to road segments by road ID"),
    ("vec","Convert singlepart geometries to multipart grouped by region attribute"),
    ("vec","Extract vertices from polygon boundaries for quality control analysis"),
    ("vec","Create a multi-ring buffer at 100m, 200m, and 500m around the factory site"),

    # Raster (25)
    ("rast","Calculate the mean NDVI value within each crop field polygon using zonal statistics"),
    ("rast","Fill nodata gaps in the DEM using inverse distance weighted interpolation"),
    ("rast","Compute a solar radiation index from slope and aspect rasters"),
    ("rast","Polygonize the classified land cover raster into vector format"),
    ("rast","Rasterize the building footprint layer to a 10m resolution grid"),
    ("rast","Extract elevation values from the DEM at each borehole point location"),
    ("rast","Clip the precipitation raster to the country boundary"),
    ("rast","Warp the Landsat scene from UTM to Albers Equal Area projection"),
    ("rast","Translate the GeoTIFF output to Cloud Optimized GeoTIFF format"),
    ("rast","Reclassify the slope raster into three hazard categories: low, medium, high"),
    ("rast","Generate contour lines at 10m intervals from the 5m DEM"),
    ("rast","Create a hillshade layer from the DEM for terrain visualization"),
    ("rast","Clip the MODIS NDVI raster to the state boundary and compute annual statistics"),
    ("rast","Sample the temperature raster values at weather station point locations"),
    ("rast","Build a virtual raster from multiple DEM tiles and clip to the watershed extent"),
    ("rast","Threshold the flood depth raster to identify areas deeper than 2 meters"),
    ("rast","Compute a change detection difference image between two Landsat scenes"),
    ("rast","Mosaic four DEM tiles into a single seamless elevation raster"),
    ("rast","Classify the vegetation density raster into sparse, moderate, and dense categories"),
    ("rast","Rasterize the soil type polygon layer and align it with the existing DEM grid"),
    ("rast","Extract the snow-covered area from MODIS imagery and compute the annual trend"),
    ("rast","Filter the NDVI time series to remove cloud-contaminated observations"),
    ("rast","Calculate the topographic wetness index from the filled DEM"),
    ("rast","Resample the 30m land cover raster to 10m resolution to match Sentinel-2 data"),
    ("rast","Clip the land surface temperature raster to the urban boundary and export"),

    # Mixed (15)
    ("mixed","Convert a classified flood extent raster to vector polygons and simplify the boundaries"),
    ("mixed","Rasterize the zoning map polygons, reclassify to development suitability, and clip to city"),
    ("mixed","Vectorize the binary water mask from SAR imagery and intersect with building footprints"),
    ("mixed","Compute the mean population density for each district by zonal statistics on gridded data"),
    ("mixed","Clip the hazard raster to each administrative zone and calculate the exposed area"),
    ("mixed","Calculate zonal statistics of NDVI for each forest stand polygon and append to table"),
    ("mixed","Rasterize the road network, compute a cost-distance surface, and extract travel time zones"),
    ("mixed","Polygonize the slope classification result, fix geometries, and dissolve by class"),
    ("mixed","Sample the air quality raster at monitoring station points and export as a table"),
    ("mixed","Create a fishnet grid, count points per cell, and convert counts to a heatmap raster"),
    ("mixed","Convert the land cover raster to points, join with parcel polygons, and summarize"),
    ("mixed","Rasterize protected area boundaries, buffer by 500m, and clip the land use raster"),
    ("mixed","Compute zonal statistics of precipitation for each river basin from gridded data"),
    ("mixed","Generate random sampling points within forest polygons and extract NDVI values"),
    ("mixed","Rasterize the building height polygons to 5m grid and compute skyline visibility"),
]

# ── Main ───────────────────────────────────────────────────────────
def main():
    retriever, evaluator = QGISChainRetriever(DS_PATH), QGISChainEvaluator()

    OUT_DIR.mkdir(parents=True, exist_ok=True)

    results = []
    stats = Counter()
    for modality, task_text in TASKS:
        prefer_vec = modality == "vec"; prefer_rast = modality == "rast"
        prefer_mix = modality == "mixed"
        cands = retriever.retrieve(
            task_text=task_text, l3_codes=[], k=5,
            prefer_vector=prefer_vec, prefer_raster=prefer_rast,
            prefer_mixed=prefer_mix,
        )
        top1 = cands[0] if cands else None
        top1_ops = top1.qgis_ops if top1 else []
        top1_names = top1.operator_names if top1 else []
        top1_qual = evaluator.evaluate(top1_ops).quality_score if top1 else 0.0

        row = {
            "task": task_text, "modality": modality,
            "top1_ops": " -> ".join(top1_ops[:8]),
            "top1_names": " -> ".join(top1_names[:8]),
            "top1_quality": round(top1_qual, 4),
            "n_unique": len(set(tuple(c.qgis_ops) for c in cands)),
            "grade": "",
            "notes": "",
        }
        results.append(row)
        stats["total"] += 1
        if modality == "vec": stats["vec"] += 1
        elif modality == "rast": stats["rast"] += 1
        else: stats["mixed"] += 1

        # Quick auto-check: modality match
        if modality == "vec" and top1:
            row["modality_match"] = "V" if top1.quality.get("is_pure_vector") else "X"
        elif modality == "rast" and top1:
            row["modality_match"] = "V" if top1.quality.get("is_pure_raster") else "X"
        elif modality == "mixed" and top1:
            row["modality_match"] = "V" if top1.quality.get("is_mixed") else "-"
        else:
            row["modality_match"] = "-"

    # Write CSV for manual grading
    csv_path = OUT_DIR / "open_landing_results.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.writer(f)
        w.writerow(["task", "modality", "modality_match", "top1_ops", "top1_names",
                     "top1_quality", "n_unique", "grade", "notes"])
        for r in results:
            w.writerow([r["task"], r["modality"], r["modality_match"],
                        r["top1_ops"], r["top1_names"],
                        r["top1_quality"], r["n_unique"], r["grade"], r["notes"]])

    # Quick stats
    auto_mod_ok = sum(1 for r in results if r.get("modality_match") == "V")
    unique_chains = len(set(r["top1_ops"] for r in results))
    avg_qual = sum(r["top1_quality"] for r in results) / max(len(results), 1)

    print(f"QGIS Open Landing Evaluation")
    print(f"  Tasks: {stats['total']} (V:{stats['vec']} R:{stats['rast']} M:{stats['mixed']})")
    print(f"  Auto modality match: {auto_mod_ok}/{stats['total']} ({auto_mod_ok/stats['total']*100:.0f}%)")
    print(f"  Unique top-1 chains: {unique_chains}")
    print(f"  Avg quality: {avg_qual:.4f}")
    print(f"  Results: {csv_path}")
    print(f"\n  Next: open CSV, fill grade (A/B/C) and notes manually.")


if __name__ == "__main__":
    main()
