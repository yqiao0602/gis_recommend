#!/usr/bin/env python3
"""
Apply manual overrides for the 25 low-confidence REVIEW items.
"""
import json
import sys
from pathlib import Path

BASE = Path(__file__).parent.parent
MAPPING_FILE = BASE / "outputs_v2/mapping_metadata_v2.json"
SKIP_FILE = BASE / "outputs_v2/gee_skip_list_v2.json"

# Manual decisions for the 25 low-confidence REVIEW items
OVERRIDES = {
    # REMOVE (14 items) - delete from mapping entirely
    "REMOVE": [
        ("QGIS", "Rasterize"),
        ("QGIS", "Extract binary field"),
        ("QGIS", "v.in.dxf"),
        ("QGIS", "r.sun.insoltime"),
        ("QGIS", "Raster surface volume"),
        ("QGIS", "GeneratePlyFile"),
        ("QGIS", "Least Cost Paths"),
        ("QGIS", "Polygon Categories to Raster"),
        ("QGIS", "Proximity Raster"),
        ("QGIS", "Sunrise and Sunset"),
        ("QGIS", "Transpose Rasters"),
        ("QGIS", "Build overviews"),
        ("QGIS", "r.ros"),
        ("QGIS", "v.edit"),
    ],

    # SKIP (3 items) - add to skip list
    "SKIP": [
        ("QGIS", "Extract Shapefile encoding"),
        ("QGIS", "ReadImageInfo"),
        ("GEE", "ee.image.pixellonlat"),
    ],

    # REMAP (6 items) - change to new L3
    "REMAP": [
        ("QGIS", "Sieve", "L3_03_04_01"),  # Reclassify
        ("QGIS", "r.fillnulls", "L3_03_05_01"),  # Resample
        ("QGIS", "Filter layers by type", "L3_03_01_03"),  # Extract by Condition
        ("QGIS", "Kernel Density Estimation", "L3_03_02_03"),  # Focal Statistics (keep T2)
        ("QGIS", "Natural Neighbour", "L3_03_05_01"),  # Resample (T3 code deleted, fallback)
        ("GEE", "ee.image.connectedcomponents", "L3_03_04_01"),  # Reclassify
    ],

    # KEEP (2 items) - no change, already best available
    "KEEP": [
        ("QGIS", "Export to PostgreSQL database available connections"),
        ("QGIS", "Export to PostgreSQL database new connection"),
    ],
}

def main():
    # Load mapping
    with open(MAPPING_FILE, encoding="utf-8") as f:
        mapping = json.load(f)

    # Load skip list
    with open(SKIP_FILE, encoding="utf-8") as f:
        skip_list = json.load(f)

    stats = {"removed": 0, "skipped": 0, "remapped": 0, "kept": 0}

    # Process REMOVE
    for side, op in OVERRIDES["REMOVE"]:
        key = "gee_to_l3" if side == "GEE" else "qgis_to_l3"
        if op in mapping[key]:
            old_l3 = mapping[key][op]
            del mapping[key][op]
            stats["removed"] += 1
            print(f"✓ REMOVE {side} `{op}` (was {old_l3})")
        else:
            print(f"⚠ REMOVE {side} `{op}` not found in mapping")

    # Process SKIP
    for side, op in OVERRIDES["SKIP"]:
        key = "gee_to_l3" if side == "GEE" else "qgis_to_l3"
        if op in mapping[key]:
            del mapping[key][op]

        skip_key = "gee_skip_list" if side == "GEE" else "qgis_skip_list"
        if op not in skip_list[skip_key]:
            skip_list[skip_key].append(op)
            stats["skipped"] += 1
            print(f"✓ SKIP {side} `{op}` (added to skip list)")
        else:
            print(f"⚠ SKIP {side} `{op}` already in skip list")

    # Process REMAP
    for side, op, new_l3 in OVERRIDES["REMAP"]:
        key = "gee_to_l3" if side == "GEE" else "qgis_to_l3"
        if op in mapping[key]:
            old_l3 = mapping[key][op]
            mapping[key][op] = new_l3
            stats["remapped"] += 1
            print(f"✓ REMAP {side} `{op}`: {old_l3} → {new_l3}")
        else:
            print(f"⚠ REMAP {side} `{op}` not found in mapping")

    # Process KEEP (just log)
    for side, op in OVERRIDES["KEEP"]:
        key = "gee_to_l3" if side == "GEE" else "qgis_to_l3"
        if op in mapping[key]:
            stats["kept"] += 1
            print(f"✓ KEEP {side} `{op}` (unchanged: {mapping[key][op]})")
        else:
            print(f"⚠ KEEP {side} `{op}` not found in mapping")

    # Write back
    with open(MAPPING_FILE, "w", encoding="utf-8") as f:
        json.dump(mapping, f, indent=2, ensure_ascii=False)

    with open(SKIP_FILE, "w", encoding="utf-8") as f:
        json.dump(skip_list, f, indent=2, ensure_ascii=False)

    print(f"\n✅ Applied overrides: {stats['removed']} removed, {stats['skipped']} skipped, "
          f"{stats['remapped']} remapped, {stats['kept']} kept")
    print(f"   Updated {MAPPING_FILE}")
    print(f"   Updated {SKIP_FILE}")

if __name__ == "__main__":
    main()
