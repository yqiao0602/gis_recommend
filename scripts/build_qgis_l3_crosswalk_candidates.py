#!/usr/bin/env python3
"""Build candidate QGIS→L3 mapping crosswalk for high-frequency unmapped operators.

Cross-references QGIS algorithm catalog, L3 hierarchy, and chain dataset to
generate a reviewable CSV of proposed L3 mappings.

Sources:
    - QGIS_Input.csv: operator catalog with names, descriptions, data types
    - id_mappings_v2.json: existing QGIS↔L3 mappings
    - classification_hierarchy_v2.csv: L3 code definitions with names and L2/L1
    - qgis_chain_dataset.jsonl: chain frequency data

Outputs:
    - outputs_v2/qgis_l3_crosswalk_candidates.csv: reviewable mapping proposals
    - outputs_v2/qgis_l3_crosswalk_candidates.json: machine-readable format

Usage:
    python scripts/build_qgis_l3_crosswalk_candidates.py
    python scripts/build_qgis_l3_crosswalk_candidates.py --min-freq 10 --max-candidates 100
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


# ── Helpers ─────────────────────────────────────────────────────────

def normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9]", "", text.lower())


def token_overlap(a: str, b: str) -> int:
    ta = set(normalize(a).split())
    tb = set(normalize(b).split())
    return len(ta & tb)


# ── Main ───────────────────────────────────────────────────────────

def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", default=str(ROOT / "爬取GithubQGIS" / "QGIS_Input.csv"))
    parser.add_argument("--id-mappings", default=str(ROOT / "outputs_v2" / "id_mappings_v2.json"))
    parser.add_argument("--hierarchy", default=str(ROOT / "outputs_v2" / "classification_hierarchy_v2.csv"))
    parser.add_argument("--chain-dataset", default=str(ROOT / "outputs_v2" / "qgis_chain_dataset.jsonl"))
    parser.add_argument("--output-csv", default=str(ROOT / "outputs_v2" / "qgis_l3_crosswalk_candidates.csv"))
    parser.add_argument("--output-json", default=str(ROOT / "outputs_v2" / "qgis_l3_crosswalk_candidates.json"))
    parser.add_argument("--min-freq", type=int, default=5, help="Minimum chain frequency to include")
    parser.add_argument("--max-candidates", type=int, default=200)
    args = parser.parse_args(argv)

    print("=" * 60)
    print("QGIS → L3 Crosswalk Candidate Builder")
    print("=" * 60)

    # ── 1. Load L3 hierarchy ────────────────────────────────────────
    print(f"\n[1] Loading L3 hierarchy ...")
    l3_info: dict[str, dict] = {}
    with Path(args.hierarchy).open("r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            code = row.get("l3_code", "").strip()
            name = row.get("l3_name", "").strip()
            l2 = row.get("l2_code", "").strip()
            l2_name = row.get("l2_name", "").strip()
            l1 = row.get("l1_code", "").strip()
            if code:
                l3_info[code] = {
                    "l3_code": code, "l3_name": name,
                    "l2_code": l2, "l2_name": l2_name, "l1_code": l1,
                }
    print(f"  {len(l3_info)} L3 codes loaded")

    # ── 2. Load existing QGIS↔L3 mappings ───────────────────────────
    print(f"\n[2] Loading existing mappings ...")
    with Path(args.id_mappings).open("r", encoding="utf-8") as f:
        idm = json.load(f)
    qgis_to_l3 = idm.get("mapping_metadata", {}).get("qgis_to_l3", {})

    # Build {qgis_name_lower: l3_code} and {l3_code: [qgis_names]}
    existing_qgis = set()
    l3_to_qgis_names = defaultdict(list)
    for qgis_name, info in qgis_to_l3.items():
        if isinstance(info, dict):
            existing_qgis.add(qgis_name.lower().strip())
            primary = info.get("primary_l3", "")
            if primary:
                l3_to_qgis_names[primary].append(qgis_name)
    print(f"  {len(existing_qgis)} existing QGIS name mappings")

    # ── 3. Load QGIS catalog ────────────────────────────────────────
    print(f"\n[3] Loading QGIS operator catalog ...")
    catalog: dict[str, dict] = {}
    with Path(args.catalog).open("r", encoding="utf-8", errors="ignore") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 6:
                continue
            alg_id = row[5].strip().lower()
            name = row[2].strip() if len(row) > 2 else ""
            platform = row[0].strip()
            # Description is typically in row[4]
            desc = row[4].strip() if len(row) > 4 else ""
            data_type = "unknown"
            for col in row[8:]:
                if col.strip() in ("vector", "raster"):
                    data_type = col.strip()
                    break
            if alg_id and name:
                catalog[alg_id] = {
                    "alg_id": alg_id, "name": name,
                    "platform": platform, "description": desc[:300],
                    "data_type": data_type,
                }
    print(f"  {len(catalog)} operators in catalog")

    # ── 4. Get operator frequency from chain dataset ────────────────
    print(f"\n[4] Computing operator frequency from chain dataset ...")
    op_freq: Counter = Counter()
    chain_count = 0
    with Path(args.chain_dataset).open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            chain_count += 1
            ops = json.loads(line).get("qgis_ops", [])
            for op in ops:
                op_freq[op.lower()] += 1
    print(f"  {chain_count} chains, {len(op_freq)} unique operators")

    # ── 5. Identify unmapped high-frequency operators ───────────────
    print(f"\n[5] Identifying unmapped high-frequency operators ...")
    # Already mapped: check by catalog name or alg_id
    mapping_by_name: dict[str, str] = {}
    for qgis_name, info in qgis_to_l3.items():
        if isinstance(info, dict):
            primary = info.get("primary_l3", "")
            if primary:
                mapping_by_name[qgis_name.lower().strip()] = primary

    unmapped = []
    for alg_id, freq in op_freq.most_common():
        if freq < args.min_freq:
            continue
        cat = catalog.get(alg_id, {})
        cat_name = cat.get("name", "").lower().strip()
        # Check if already mapped by catalog name or alg_id
        is_mapped = (
            cat_name in existing_qgis
            or cat_name in mapping_by_name
            or alg_id in existing_qgis
        )
        if not is_mapped and cat:
            unmapped.append({
                "alg_id": alg_id,
                "catalog_name": cat.get("name", ""),
                "platform": cat.get("platform", ""),
                "data_type": cat.get("data_type", "unknown"),
                "description": cat.get("description", "")[:200],
                "frequency": freq,
            })
    print(f"  {len(unmapped)} unmapped operators with freq >= {args.min_freq}")

    # ── 6. Generate L3 mapping candidates ───────────────────────────
    print(f"\n[6] Generating L3 mapping candidates ...")

    # Keyword → L3 code mapping for common QGIS concepts
    QGIS_KW_TO_L3 = {
        # Vector geometry
        "reproject": "L3_01_02_03",
        "reprojectlayer": "L3_01_02_03",
        "fixgeom": "L3_02_07_01",
        "simplifygeom": "L3_02_07_01",
        "mergevector": "L3_01_03_04",
        "mergelayer": "L3_01_03_04",
        "joinattributesbylocation": "L3_02_04_01",
        "joinattrib": "L3_02_04_01",
        "tablejoin": "L3_02_04_01",
        "spatialjoin": "L3_02_04_01",
        "buffer": "L3_02_01_01",
        "dissolve": "L3_02_03_05",
        "clipvector": "L3_02_02_06",
        "intersection": "L3_02_02_06",
        "difference": "L3_02_02_06",
        "union": "L3_02_02_06",
        "centroid": "L3_02_05_04",
        "extractbylocation": "L3_02_06_03",
        "extractbyattribute": "L3_02_06_02",
        "extractbyexpress": "L3_02_06_02",
        "selectbylocation": "L3_02_06_03",
        "selectbyattribute": "L3_02_06_01",
        "selectbyexpress": "L3_02_06_01",
        "fieldcalc": "L3_01_02_06",
        "savefeature": "L3_07_04_01",
        "export": "L3_07_04_01",
        "multipart": "L3_02_07_01",
        "singlepart": "L3_02_07_01",
        "createindex": "L3_07_01_01",
        "spatialindex": "L3_07_01_01",
        "refactorfield": "L3_01_02_03",
        "renametable": "L3_01_02_03",
        "deletecolumn": "L3_01_02_02",
        "dropfield": "L3_01_02_02",
        "addautoincrement": "L3_01_02_01",
        "addfield": "L3_01_02_01",
        "snapgeom": "L3_02_07_01",
        "voronoi": "L3_02_05_11",
        "delaunay": "L3_02_05_11",
        "convexhull": "L3_02_05_11",
        # Raster
        "warpreproject": "L3_03_01_02",
        "clipraster": "L3_03_01_01",
        "polygonize": "L3_03_01_01",
        "rasterize": "L3_03_01_01",
        "rastercalc": "L3_03_03_A",
        "slope": "L3_04_01_01",
        "aspect": "L3_04_01_01",
        "hillshade": "L3_04_01_01",
        "reclassify": "L3_03_04_01",
        "fillnodata": "L3_03_03_A",
        "fillsink": "L3_04_01_01",
        "contour": "L3_04_01_01",
        "flowaccum": "L3_04_01_01",
        "zonalstat": "L3_03_02_01",
        "mosaic": "L3_03_01_09",
        "translate": "L3_03_01_02",
        "buildvirtualraster": "L3_03_01_09",
        "merge": "L3_03_07_01",
        "rastersampling": "L3_08_01_01",
        "rastersurface": "L3_04_01_01",
        "heatmap": "L3_03_02_03",
        "kerneldensity": "L3_03_02_03",
        # Utility
        "countpointsinpolygon": "L3_02_04_01",
        "creategrid": "L3_02_05_12",
        "randomselection": "L3_02_06_01",
        "pixelstopolygons": "L3_03_01_01",
        "linestopolygon": "L3_02_05_11",
        "polygonstoline": "L3_02_05_11",
    }

    candidates = []
    for item in unmapped[:args.max_candidates]:
        cat_name = item["catalog_name"]
        cat_desc = item["description"]
        alg_id = item["alg_id"]
        data_type = item["data_type"]

        # Check keyword mapping first
        keyword_match = None
        name_lower = (alg_id + " " + cat_name).lower()
        for kw, l3_code in QGIS_KW_TO_L3.items():
            if kw.lower() in name_lower:
                keyword_match = l3_code
                break

        # Score each L3 code by name + description overlap
        l3_scores = []
        for code, info in l3_info.items():
            score = 0
            reasons = []

            # Keyword mapping boost
            if keyword_match and code == keyword_match:
                score += 10
                reasons.append("keyword_match")

            # Name match
            name_overlap = token_overlap(cat_name, info["l3_name"])
            if name_overlap > 0:
                score += name_overlap * 3
                reasons.append(f"name_overlap={name_overlap}")

            # Description keyword match
            if cat_desc:
                desc_overlap = token_overlap(cat_desc, info["l3_name"])
                if desc_overlap > 0:
                    score += desc_overlap
                    reasons.append(f"desc_overlap={desc_overlap}")

            # Data type match
            if data_type == "vector" and "geometry" in info.get("l2_name", "").lower():
                score += 1
                reasons.append("vector_geometry")
            if data_type == "raster" and "raster" in info.get("l1_code", "").lower():
                score += 1
                reasons.append("raster_l1")

            # L2 name overlap
            l2_overlap = token_overlap(cat_name, info.get("l2_name", ""))
            if l2_overlap > 0:
                score += l2_overlap * 2
                reasons.append(f"l2_overlap={l2_overlap}")

            if score > 0:
                l3_scores.append((code, score, reasons))

        l3_scores.sort(key=lambda x: -x[1])

        # Top 3 L3 candidates
        top3 = []
        for code, score, reasons in l3_scores[:3]:
            info = l3_info[code]
            top3.append({
                "l3_code": code,
                "l3_name": info["l3_name"],
                "l2_code": info.get("l2_code", ""),
                "l2_name": info.get("l2_name", ""),
                "score": score,
                "reasons": reasons,
            })

        candidates.append({
            "alg_id": alg_id,
            "catalog_name": cat_name,
            "platform": item["platform"],
            "data_type": data_type,
            "description": cat_desc[:200],
            "frequency": item["frequency"],
            "top_l3_candidates": top3,
            "best_match": top3[0] if top3 else None,
        })

    # ── 7. Write outputs ────────────────────────────────────────────
    print(f"\n[7] Writing outputs ...")

    # CSV for manual review
    with Path(args.output_csv).open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "alg_id", "catalog_name", "platform", "data_type", "frequency",
            "description",
            "proposed_l3_1", "l3_name_1", "l2_name_1", "score_1",
            "proposed_l3_2", "l3_name_2", "l2_name_2", "score_2",
            "proposed_l3_3", "l3_name_3", "l2_name_3", "score_3",
            "review_status", "reviewer_notes",
        ])
        for c in candidates:
            top = c["top_l3_candidates"]
            row = [
                c["alg_id"], c["catalog_name"], c["platform"],
                c["data_type"], c["frequency"], c["description"][:150],
            ]
            for i in range(3):
                if i < len(top):
                    row.extend([top[i]["l3_code"], top[i]["l3_name"],
                                top[i].get("l2_name", ""), top[i]["score"]])
                else:
                    row.extend(["", "", "", ""])
            row.extend(["", ""])  # review_status, reviewer_notes
            writer.writerow(row)
    print(f"  CSV: {args.output_csv} ({len(candidates)} candidates)")

    # JSON for programmatic use
    with Path(args.output_json).open("w", encoding="utf-8") as f:
        json.dump({
            "schema": "gis_recommend.qgis_l3_crosswalk_candidates.v1",
            "total_candidates": len(candidates),
            "min_frequency": args.min_freq,
            "candidates": candidates,
        }, f, indent=2, ensure_ascii=False)
    print(f"  JSON: {args.output_json}")

    # ── Summary ─────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"Summary")
    print(f"{'='*60}")
    high = [c for c in candidates if c["best_match"] and c["best_match"]["score"] >= 3]
    medium = [c for c in candidates if c["best_match"] and 1 <= c["best_match"]["score"] < 3]
    low = [c for c in candidates if not c["best_match"] or c["best_match"]["score"] < 1]
    print(f"  High-confidence (score>=3): {len(high)}")
    print(f"  Medium (score 1-2):        {len(medium)}")
    print(f"  Low/unknown (score<1):     {len(low)}")
    print(f"  Total candidates:          {len(candidates)}")

    print(f"\n  Top 15 high-confidence proposals:")
    for c in high[:15]:
        b = c["best_match"]
        print(f"    {c['alg_id']:45s} → {b['l3_code']:15s} {b['l3_name']:30s} (score={b['score']})")

    print(f"\n  Review workflow:")
    print(f"    1. Open {args.output_csv}")
    print(f"    2. For each row, review proposed L3 codes")
    print(f"    3. Fill review_status: accepted / rejected / uncertain")
    print(f"    4. Run scripts/merge_qgis_l3_crosswalk.py to apply")


if __name__ == "__main__":
    main()
