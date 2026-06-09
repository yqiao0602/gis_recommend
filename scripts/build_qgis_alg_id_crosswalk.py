#!/usr/bin/env python3
"""Build alg_id → L3 crosswalk JSON for QGIS landing.

Auto-fills known mappings by matching official operator names against
existing id_mappings_v2.json keys. Remaining unmapped ops get marked
for manual review.

Output: outputs_v2/qgis_alg_id_crosswalk.json

Usage:
    python scripts/build_qgis_alg_id_crosswalk.py
    python scripts/build_qgis_alg_id_crosswalk.py --min-freq 5
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

OFFICIAL_OPS = ROOT.parent / "operators-json" / "qgis_operators.json"
ID_MAPPINGS = ROOT / "outputs_v2" / "id_mappings_v2.json"
DATASET = ROOT / "outputs_v2" / "qgis_chain_dataset.jsonl"

# Previously reviewed entries
MANUAL_ACCEPT = {
    "native:mergevectorlayers": ("L3_01_03_04", "accepted", "manual_review"),
    "native:extractbyexpression": ("L3_02_06_02", "accepted", "manual_review"),
    "native:extractbyattribute": ("L3_02_06_02", "accepted", "manual_review"),
    "qgis:selectbyexpression": ("L3_02_06_01", "accepted", "manual_review"),
    "qgis:selectbyattribute": ("L3_02_06_01", "accepted", "manual_review"),
    "native:extractbylocation": ("L3_02_06_03", "accepted", "manual_review"),
    "native:selectbylocation": ("L3_02_06_03", "accepted", "manual_review"),
    "native:joinattributesbylocation": ("L3_02_04_01", "accepted", "manual_review"),
    "qgis:joinbylocationsummary": ("L3_02_04_01", "accepted", "manual_review"),
    "native:refactorfields": ("L3_01_02_03", "accepted", "manual_review"),
    "native:multiringconstantbuffer": ("L3_02_01_01", "accepted", "manual_review"),
    "qgis:minimumboundinggeometry": ("L3_02_05_12", "accepted", "manual_review"),
    "native:symmetricaldifference": ("L3_02_02_05", "accepted", "manual_review"),
    "gdal:warpreproject": ("L3_03_05_02", "accepted", "manual_review"),
    "gdal:translate": ("L3_07_04_05", "accepted", "manual_review"),
    "gdal:fillnodata": ("L3_03_03_A", "accepted", "manual_review"),
    "native:fillnodata": ("L3_03_03_A", "accepted", "manual_review"),
    "saga:slopeaspectcurvature": ("L3_04_01_01", "accepted", "manual_review"),
}

MANUAL_REJECT = {
    "native:createspatialindex",
    "gdal:rasterize",
    "gdal:polygonize",
    "native:pixelstopolygons",
    "gdal:rasterize_over",
    "native:joinattributestable",
    "native:creategrid",
}

MANUAL_NATIVE_BRIDGE = {
    "native:reprojectlayer": "qgis_native:vector_crs_transform",
    # Raster/vector conversion — semantically distinct from existing L3
    "gdal:rasterize": "qgis_native:rasterize_convert",
    "gdal:polygonize": "qgis_native:polygonize_convert",
    "native:creategrid": "qgis_native:grid_generation",
    "native:joinattributestable": "qgis_native:table_join",
    # Geometry repair/cleanup — near L3_02_07_01 but semantically distinct
    "native:fixgeometries": "qgis_native:geometry_repair",
    "native:snapgeometries": "qgis_native:geometry_snap",
    "native:simplifygeometries": "qgis_native:geometry_simplify",
    "native:deleteholes": "qgis_native:geometry_cleanup",
    "native:deleteduplicategeometries": "qgis_native:geometry_dedup",
    "native:smoothgeometry": "qgis_native:geometry_smooth",
    # Geometry conversion — near L3_02_05_11 but QGIS-specific
    "native:polygonstolines": "qgis_native:polygon_to_line",
    "native:splitwithlines": "qgis_native:line_split",
    "native:explodelines": "qgis_native:line_explode",
    "native:pointsalonglines": "qgis_native:point_sampling",
    # Export/IO — near L3_07_04_01 but tool-specific
    "native:saveselectedfeatures": "qgis_native:export_selected",
    "native:exporttospreadsheet": "qgis_native:export_spreadsheet",
    "native:filedownloader": "qgis_native:file_download",
    # Contour generation — L3_04_01_01 exists but contour is derivative
    "gdal:contour": "qgis_native:contour_generation",
    "native:pixelstopoints": "qgis_native:pixels_to_points",
    "qgis:heatmapkerneldensityestimation": "qgis_native:density_heatmap",
    # Aggregation / nearest join
    "native:aggregate": "qgis_native:aggregate",
    "native:joinbynearest": "qgis_native:spatial_join_nn",
    "gdal:proximity": "qgis_native:raster_proximity",
    "qgis:exportaddgeometrycolumns": "qgis_native:export_geom_columns",
}


def load_official() -> dict[str, dict]:
    with open(OFFICIAL_OPS, "r", encoding="utf-8") as f:
        return {str(o.get("identifier", "")).lower().strip(): o for o in json.load(f)}


def load_l3_mapping() -> dict[str, str]:
    with open(ID_MAPPINGS, "r", encoding="utf-8") as f:
        idm = json.load(f)
    q2l = idm.get("mapping_metadata", {}).get("qgis_to_l3", {})
    return {k.lower().strip(): v.get("primary_l3", "") if isinstance(v, dict) else ""
            for k, v in q2l.items()}


def get_op_freq() -> Counter:
    counter = Counter()
    with open(DATASET, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            for op in json.loads(line).get("qgis_ops", []):
                counter[op.lower()] += 1
    return counter


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--min-freq", type=int, default=3)
    parser.add_argument("--output", default=str(ROOT / "outputs_v2" / "qgis_alg_id_crosswalk.json"))
    args = parser.parse_args(argv)

    official = load_official()
    l3_map = load_l3_mapping()
    freq = get_op_freq()

    crosswalk = {}
    stats = Counter()

    for alg_id, count in freq.most_common():
        if count < args.min_freq:
            continue
        op = official.get(alg_id, {})
        official_name = op.get("name", "")

        if alg_id in MANUAL_ACCEPT:
            l3_code, status, source = MANUAL_ACCEPT[alg_id]
            crosswalk[alg_id] = {
                "alg_id": alg_id, "official_name": official_name,
                "l3_code": l3_code, "bridge_type": "l3_bridge",
                "status": status, "source": source, "frequency": count,
            }
            stats["auto_accepted"] += 1
            continue

        if alg_id in MANUAL_REJECT:
            crosswalk[alg_id] = {
                "alg_id": alg_id, "official_name": official_name,
                "l3_code": "", "bridge_type": "rejected",
                "status": "rejected", "source": "manual_review", "frequency": count,
            }
            stats["rejected"] += 1
            continue

        if alg_id in MANUAL_NATIVE_BRIDGE:
            tag = MANUAL_NATIVE_BRIDGE[alg_id]
            crosswalk[alg_id] = {
                "alg_id": alg_id, "official_name": official_name,
                "l3_code": tag, "bridge_type": "native_bridge",
                "status": "accepted", "source": "manual_review", "frequency": count,
            }
            stats["native_bridge"] += 1
            continue

        # Auto-match: official name → id_mappings key
        name_lower = official_name.lower().strip()
        if name_lower in l3_map:
            l3_code = l3_map[name_lower]
            crosswalk[alg_id] = {
                "alg_id": alg_id, "official_name": official_name,
                "l3_code": l3_code, "bridge_type": "l3_bridge",
                "status": "accepted", "source": "auto_name_match", "frequency": count,
            }
            stats["auto_matched"] += 1
        else:
            crosswalk[alg_id] = {
                "alg_id": alg_id, "official_name": official_name,
                "l3_code": "", "bridge_type": "pending",
                "status": "pending_review", "source": "", "frequency": count,
            }
            stats["pending"] += 1

    # Report
    n = len(crosswalk)
    covered = stats["auto_accepted"] + stats["auto_matched"] + stats["native_bridge"]
    total_freq = sum(c["frequency"] for c in crosswalk.values())
    covered_freq = sum(c["frequency"] for c in crosswalk.values()
                       if c["bridge_type"] in ("l3_bridge", "native_bridge"))

    print(f"Crosswalk entries: {n} (freq >= {args.min_freq})")
    print(f"  auto_accepted:  {stats['auto_accepted']}")
    print(f"  auto_matched:   {stats['auto_matched']}  (name → L3 match)")
    print(f"  native_bridge:  {stats['native_bridge']}")
    print(f"  rejected:       {stats['rejected']}")
    print(f"  pending_review: {stats['pending']}")
    print(f"  Covered: {covered}/{n} ops, {covered_freq}/{total_freq} mentions "
          f"({covered_freq/max(total_freq,1)*100:.1f}%)")

    # Show pending
    pending = [v for v in crosswalk.values() if v["bridge_type"] == "pending"]
    print(f"\nTop 20 pending (manual review needed):")
    for v in sorted(pending, key=lambda x: -x["frequency"])[:20]:
        print(f"  {v['alg_id']:45s} {v['frequency']:5d}x  \"{v['official_name'][:45]}\"")

    # Write
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump({
            "schema": "gis_recommend.qgis_alg_id_crosswalk.v1",
            "total_entries": n,
            "coverage_rate": round(covered_freq / max(total_freq, 1), 4),
            "entries": crosswalk,
            "stats": dict(stats),
        }, f, indent=2, ensure_ascii=False)
    print(f"\nWritten: {args.output}")


if __name__ == "__main__":
    main()
