#!/usr/bin/env python3
"""Merge reviewed QGIS→L3 crosswalk mappings into id_mappings_v2.json.

Reads a hand-reviewed mapping file (CSV or JSON) and injects accepted mappings
into the active id_mappings, preserving existing entries. Rejected and uncertain
entries are recorded separately.

Usage:
    python scripts/merge_qgis_l3_crosswalk.py
    python scripts/merge_qgis_l3_crosswalk.py --input my_reviewed.csv
    python scripts/merge_qgis_l3_crosswalk.py --dry-run
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sys
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

CROSSWALK_CSV = ROOT / "outputs_v2" / "qgis_l3_crosswalk_candidates.csv"
ID_MAPPINGS_PATH = ROOT / "outputs_v2" / "id_mappings_v2.json"
OUTPUT_ID_MAPPINGS = ROOT / "outputs_v2" / "id_mappings_v2.json"
BACKUP_SUFFIX = ".backup."

# ── User-reviewed mappings ──────────────────────────────────────────
# Format: {alg_id: (l3_code, notes)}
# Only accepted entries are included. All others are rejected or uncertain.

ACCEPTED_MAPPINGS = {
    # High-confidence, semantically correct
    "native:mergevectorlayers":          ("L3_01_03_04", "Merge layers"),
    "native:extractbyexpression":        ("L3_02_06_02", "Extract by Attribute / attribute filter"),
    "native:extractbyattribute":         ("L3_02_06_02", "Extract by Attribute"),
    "qgis:selectbyexpression":           ("L3_02_06_01", "Select by Attribute"),
    "qgis:selectbyattribute":            ("L3_02_06_01", "Select by Attribute"),
    "native:extractbylocation":          ("L3_02_06_03", "Extract by Location / spatial filter"),
    "native:selectbylocation":           ("L3_02_06_03", "Extract by Location"),
    "native:joinattributesbylocation":   ("L3_02_04_01", "Spatial Join"),
    "qgis:joinbylocationsummary":        ("L3_02_04_01", "Spatial Join summary"),
    "native:refactorfields":             ("L3_01_02_03", "Alter Field / field restructure"),
    "native:multiringconstantbuffer":    ("L3_02_01_01", "Buffer"),
    "qgis:minimumboundinggeometry":      ("L3_02_05_12", "Minimum Bounding Geometry"),
    "native:symmetricaldifference":      ("L3_02_02_05", "Symmetrical Difference"),

    # Corrected from auto-mapping
    "gdal:warpreproject":                ("L3_03_05_02", "Reproject raster (warp) — not Alter Field"),
    "gdal:translate":                    ("L3_07_04_05", "Raster format convert/export"),

    # Raster — cautious accepts
    "gdal:fillnodata":                   ("L3_03_03_A", "Raster math / fill"),
    "native:fillnodata":                 ("L3_03_03_A", "Raster math / fill"),
    "saga:slopeaspectcurvature":         ("L3_04_01_01", "Slope — primary; aspect/curvature are secondary"),
}

# Explicitly REJECTED — do NOT merge
REJECTED_ALG_IDS = {
    "native:createspatialindex":     "L3 mismatch — not Apply Simple Symbol, no suitable L3",
    "gdal:rasterize":                "Vector→Raster conversion — no suitable L3",
    "gdal:polygonize":               "Raster→Vector conversion — no suitable L3",
    "native:pixelstopolygons":       "Raster→Vector — no suitable L3",
    "gdal:rasterize_over":           "No suitable L3",
    "native:joinattributestable":    "Table join, not Spatial Join — different semantics",
    "native:creategrid":             "Not Minimum Bounding Geometry",
}

# UNCERTAIN — keep for later review
UNCERTAIN_ALG_IDS = {
    "native:reprojectlayer":         "No L3 for vector reproject",
    "native:fixgeometries":          "Geometry repair — near Multipart but not same",
    "native:snapgeometries":         "Geometry cleanup",
    "native:simplifygeometries":     "Geometry simplification",
    "qgis:checkvalidity":            "Validation — no suitable L3",
    "native:polygonstolines":        "Boundary extraction",
    "qgis:linestopolygons":          "Line→Polygon conversion",
    "native:extractvertices":        "Vertex extraction",
    "native:pointsalonglines":       "Point sampling on lines",
    "native:splitwithlines":         "Split by lines",
    "native:smoothgeometry":         "Geometry smoothing",
    "native:deleteholes":            "Geometry cleanup",
    "native:deleteduplicategeometries": "Dedup",
    "gdal:contour":                  "Contour — not Slope",
    "gdal:contour_polygon":          "Contour polygon",
    "native:saveselectedfeatures":   "Export — needs L3 review",
    "native:savefeatures":           "Export — needs L3 review",
}


def _lookup_alg_id(alg_id: str, catalog: dict[str, dict]) -> dict | None:
    """Find operator info from catalog by alg_id."""
    return catalog.get(alg_id.lower())


def apply_crosswalk(
    id_mappings: dict,
    accepted: dict[str, tuple[str, str]],
    catalog: dict[str, dict],
) -> dict:
    """Inject accepted QGIS alg_id → L3 mappings into id_mappings."""
    new = dict(id_mappings)
    qgis_to_l3 = new.setdefault("mapping_metadata", {}).setdefault("qgis_to_l3", {})

    applied = []
    for alg_id, (l3_code, note) in accepted.items():
        cat = _lookup_alg_id(alg_id, catalog)
        display_name = cat.get("name", alg_id) if cat else alg_id
        # Create a mapping entry
        entry_key = display_name
        if entry_key in qgis_to_l3:
            existing = qgis_to_l3[entry_key]
            existing_primary = existing.get("primary_l3", "") if isinstance(existing, dict) else ""
            if existing_primary:
                # Already mapped — skip or update candidates
                if l3_code not in [c.get("l3_code", "") if isinstance(c, dict) else ""
                                   for c in existing.get("all_candidates", [])]:
                    existing.setdefault("all_candidates", []).append({
                        "l3_code": l3_code,
                        "source": "qgis_l3_crosswalk_reviewed",
                        "note": note,
                    })
                applied.append({"alg_id": alg_id, "status": "candidate_added",
                                "display_name": display_name, "l3_code": l3_code})
            else:
                existing["primary_l3"] = l3_code
                applied.append({"alg_id": alg_id, "status": "primary_set",
                                "display_name": display_name, "l3_code": l3_code})
        else:
            # New mapping
            qgis_to_l3[entry_key] = {
                "primary_l3": l3_code,
                "source": "qgis_l3_crosswalk_reviewed",
                "manual_reviewed": True,
                "review_note": note,
                "all_candidates": [],
            }
            applied.append({"alg_id": alg_id, "status": "new_entry",
                            "display_name": display_name, "l3_code": l3_code})

    new["mapping_metadata"]["qgis_to_l3"] = qgis_to_l3
    return new, applied


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", default=str(CROSSWALK_CSV))
    parser.add_argument("--id-mappings", default=str(ID_MAPPINGS_PATH))
    parser.add_argument("--output", default=str(OUTPUT_ID_MAPPINGS))
    parser.add_argument("--catalog", default=str(ROOT / "爬取GithubQGIS" / "QGIS_Input.csv"))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    print("=" * 60)
    print("QGIS → L3 Crosswalk Merger")
    print("=" * 60)

    # Load catalog
    catalog = {}
    with Path(args.catalog).open("r", encoding="utf-8", errors="ignore") as f:
        for row in csv.reader(f):
            if len(row) < 6:
                continue
            alg_id = row[5].strip().lower()
            name = row[2].strip() if len(row) > 2 else ""
            if alg_id and name:
                catalog[alg_id] = {"name": name, "alg_id": alg_id}

    # Load id_mappings
    id_mappings_path = Path(args.id_mappings)
    with id_mappings_path.open("r", encoding="utf-8") as f:
        id_mappings = json.load(f)

    # Apply accepted
    new_mappings, applied = apply_crosswalk(id_mappings, ACCEPTED_MAPPINGS, catalog)

    # Stats
    print(f"\n  Accepted:  {len(ACCEPTED_MAPPINGS)}")
    print(f"  Rejected:  {len(REJECTED_ALG_IDS)}")
    print(f"  Uncertain: {len(UNCERTAIN_ALG_IDS)}")
    print(f"  Total in review: {len(ACCEPTED_MAPPINGS) + len(REJECTED_ALG_IDS) + len(UNCERTAIN_ALG_IDS)}")

    # Count new L3 codes covered
    before_l3 = set()
    for info in id_mappings.get("mapping_metadata", {}).get("qgis_to_l3", {}).values():
        if isinstance(info, dict):
            p = info.get("primary_l3", "")
            if p:
                before_l3.add(p)
    after_l3 = set()
    for info in new_mappings.get("mapping_metadata", {}).get("qgis_to_l3", {}).values():
        if isinstance(info, dict):
            p = info.get("primary_l3", "")
            if p:
                after_l3.add(p)
    print(f"\n  L3 codes with QGIS mapping: {len(before_l3)} → {len(after_l3)} (+{len(after_l3 - before_l3)})")

    print(f"\n  Applied mappings:")
    for a in applied:
        print(f"    [{a['status']:15s}] {a['alg_id']:40s} → {a['l3_code']}")

    if args.dry_run:
        print(f"\n  [DRY RUN] No changes written.")
        return

    # Backup original
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    backup_path = id_mappings_path.with_suffix(BACKUP_SUFFIX + ts + ".json")
    shutil.copy2(id_mappings_path, backup_path)
    print(f"\n  Backup: {backup_path}")

    # Write
    with Path(args.output).open("w", encoding="utf-8") as f:
        json.dump(new_mappings, f, indent=2, ensure_ascii=False)
    print(f"  Written: {args.output}")

    # Write review summary
    review_json = ROOT / "outputs_v2" / "qgis_l3_crosswalk_review_summary.json"
    with review_json.open("w", encoding="utf-8") as f:
        json.dump({
            "timestamp": ts,
            "accepted": {k: list(v) for k, v in ACCEPTED_MAPPINGS.items()},
            "rejected": dict(REJECTED_ALG_IDS),
            "uncertain": dict(UNCERTAIN_ALG_IDS),
            "applied_count": len(applied),
            "l3_codes_before": sorted(before_l3),
            "l3_codes_after": sorted(after_l3),
            "new_l3_codes": sorted(after_l3 - before_l3),
        }, f, indent=2, ensure_ascii=False)
    print(f"  Review summary: {review_json}")


if __name__ == "__main__":
    main()
