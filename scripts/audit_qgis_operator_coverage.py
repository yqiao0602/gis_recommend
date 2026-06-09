#!/usr/bin/env python3
"""Audit: trace every GitHub QGIS operator through the full mapping pipeline.

Answers: where exactly does the L3 bridge break?

Categories:
  A. Standard operator WITH L3 mapping      → l3_bridge
  B. Standard operator WITHOUT L3 mapping   → native_bridge / uncertain / rejected
  C. Non-standard/plugin operator           → filtered from dataset

Outputs:
  outputs_v2/diagnostics/qgis_operator_audit.csv
  outputs_v2/diagnostics/qgis_operator_audit.json
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

QGIS_DIR = ROOT / "爬取GithubQGIS"
OFFICIAL_OPS = ROOT.parent / "operators-json" / "qgis_operators.json"
ID_MAPPINGS = ROOT / "outputs_v2" / "id_mappings_v2.json"
LEGACY_CATALOG = QGIS_DIR / "QGIS_Input.csv"
DATASET = ROOT / "outputs_v2" / "qgis_chain_dataset.jsonl"

SCRIPT_DIRS = [
    ("QGIS_standard_multi_operator_workflows_v2", "standard_v2"),
    ("github_qgis_workflow", "workflow"),
    ("github_qgis_workflow_A类", "workflow_A"),
]

# Manually reviewed mappings
ACCEPTED_CROSSWALK = {
    "native:mergevectorlayers": "L3_01_03_04",
    "native:extractbyexpression": "L3_02_06_02",
    "native:extractbyattribute": "L3_02_06_02",
    "qgis:selectbyexpression": "L3_02_06_01",
    "qgis:selectbyattribute": "L3_02_06_01",
    "native:extractbylocation": "L3_02_06_03",
    "native:selectbylocation": "L3_02_06_03",
    "native:joinattributesbylocation": "L3_02_04_01",
    "qgis:joinbylocationsummary": "L3_02_04_01",
    "native:refactorfields": "L3_01_02_03",
    "native:multiringconstantbuffer": "L3_02_01_01",
    "qgis:minimumboundinggeometry": "L3_02_05_12",
    "native:symmetricaldifference": "L3_02_02_05",
    "gdal:warpreproject": "L3_03_05_02",
    "gdal:translate": "L3_07_04_05",
    "gdal:fillnodata": "L3_03_03_A",
    "native:fillnodata": "L3_03_03_A",
    "saga:slopeaspectcurvature": "L3_04_01_01",
}
REJECTED_OPS = {
    "native:createspatialindex", "gdal:rasterize", "gdal:polygonize",
    "native:pixelstopolygons", "gdal:rasterize_over",
    "native:joinattributestable", "native:creategrid",
}
NATIVE_BRIDGE_OPS = {
    "native:reprojectlayer": "qgis_native:vector_crs_transform",
}


def extract_all_ops() -> Counter:
    """Extract ALL processing.run() operators from raw GitHub scripts."""
    counter = Counter()
    for dir_name, _ in SCRIPT_DIRS:
        d = QGIS_DIR / dir_name / "downloaded_scripts"
        if not d.exists():
            continue
        for fn in sorted(os.listdir(d)):
            try:
                content = (d / fn).read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            for m in re.finditer(r'processing\.run\(\s*[\"\']([a-z0-9_]+:[a-z0-9_]+)[\"\']', content, re.IGNORECASE):
                counter[m.group(1).lower()] += 1
    return counter


def load_official() -> dict[str, dict]:
    with open(OFFICIAL_OPS, "r", encoding="utf-8") as f:
        return {str(o.get("identifier", "")).lower().strip(): o for o in json.load(f)}


def load_legacy_catalog() -> dict[str, dict]:
    cat = {}
    with open(LEGACY_CATALOG, "r", encoding="utf-8", errors="ignore") as f:
        for row in csv.reader(f):
            if len(row) < 6:
                continue
            aid = row[5].strip().lower()
            name = row[2].strip() if len(row) > 2 else ""
            dtype = "unknown"
            for col in row[8:]:
                if col.strip() in ("vector", "raster"):
                    dtype = col.strip()
                    break
            if aid:
                cat[aid] = {"name": name, "data_type": dtype}
    return cat


def load_l3_mapping() -> dict[str, str]:
    with open(ID_MAPPINGS, "r", encoding="utf-8") as f:
        idm = json.load(f)
    q2l = idm.get("mapping_metadata", {}).get("qgis_to_l3", {})
    return {k.lower().strip(): v.get("primary_l3", "") if isinstance(v, dict) else ""
            for k, v in q2l.items()}


def load_dataset_ops() -> set[str]:
    ops = set()
    with open(DATASET, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            for op in json.loads(line).get("qgis_ops", []):
                ops.add(op.lower())
    return ops


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--min-freq", type=int, default=1)
    parser.add_argument("--output-dir", default=str(ROOT / "outputs_v2" / "diagnostics"))
    args = parser.parse_args(argv)

    print("=" * 60)
    print("QGIS Operator Coverage Audit")
    print("=" * 60)

    raw_ops = extract_all_ops()
    official = load_official()
    legacy = load_legacy_catalog()
    l3_map = load_l3_mapping()
    dataset_ops = load_dataset_ops()

    print(f"\nRaw GitHub ops:     {len(raw_ops)} unique ({sum(raw_ops.values())} total)")
    print(f"Official operators: {len(official)}")
    print(f"Legacy catalog:     {len(legacy)}")
    print(f"id_mappings keys:   {len(l3_map)}")
    print(f"Dataset ops:        {len(dataset_ops)}")

    # Classify each raw op
    rows = []
    stats = Counter()

    for alg_id, freq in raw_ops.most_common():
        if freq < args.min_freq:
            continue

        in_official = alg_id in official
        in_legacy = alg_id in legacy
        in_dataset = alg_id in dataset_ops
        has_l3 = alg_id in l3_map
        has_crosswalk = alg_id in ACCEPTED_CROSSWALK
        is_rejected = alg_id in REJECTED_OPS
        is_native = alg_id in NATIVE_BRIDGE_OPS

        # Resolve to effective L3
        l3_code = ""
        bridge_type = ""
        if has_l3:
            l3_code = l3_map[alg_id]
            bridge_type = "l3_bridge"
        elif has_crosswalk:
            l3_code = ACCEPTED_CROSSWALK[alg_id]
            bridge_type = "l3_bridge_crosswalk"
        elif is_native:
            l3_code = NATIVE_BRIDGE_OPS[alg_id]
            bridge_type = "native_bridge"
        elif is_rejected:
            bridge_type = "rejected"
        elif in_dataset:
            bridge_type = "dataset_no_bridge"
        else:
            bridge_type = "filtered"

        official_name = official[alg_id]["name"] if in_official else ""
        legacy_name = legacy.get(alg_id, {}).get("name", "") if in_legacy else ""
        dtype = legacy.get(alg_id, {}).get("data_type", "unknown") if in_legacy else "unknown"

        category = ""
        if in_official and (has_l3 or has_crosswalk):
            category = "A_l3_bridge"
        elif in_official:
            category = "B_no_l3"
        else:
            category = "C_non_standard"

        rows.append({
            "alg_id": alg_id,
            "freq": freq,
            "in_official": in_official,
            "in_legacy": in_legacy,
            "in_dataset": in_dataset,
            "has_l3": has_l3,
            "has_crosswalk": has_crosswalk,
            "is_rejected": is_rejected,
            "is_native_bridge": is_native,
            "bridge_type": bridge_type,
            "l3_code": l3_code,
            "category": category,
            "official_name": official_name,
            "legacy_name": legacy_name,
            "data_type": dtype,
        })

        stats[category] += 1
        stats[f"bridge_{bridge_type}"] += 1

    # Print summary
    print(f"\n--- Category breakdown ---")
    total = sum(stats[c] for c in ["A_l3_bridge", "B_no_l3", "C_non_standard"])
    for cat, label in [("A_l3_bridge", "A. Standard + L3 mapped"),
                        ("B_no_l3", "B. Standard, NO L3"),
                        ("C_non_standard", "C. Non-standard/plugin")]:
        n = stats[cat]
        pct = n / max(total, 1) * 100
        freq_sum = sum(r["freq"] for r in rows if r["category"] == cat)
        print(f"  {label:35s}: {n:4d} ops ({pct:5.1f}%), {freq_sum:6d} total occurrences")

    print(f"\n--- Bridge type breakdown ---")
    for bt in ["l3_bridge", "l3_bridge_crosswalk", "native_bridge", "rejected", "dataset_no_bridge", "filtered"]:
        n = stats[f"bridge_{bt}"]
        if n:
            freq_sum = sum(r["freq"] for r in rows if r["bridge_type"] == bt)
            print(f"  {bt:25s}: {n:4d} ops, {freq_sum:6d} occurrences")

    # Top B-category ops (the real gap)
    print(f"\n--- Top 20 Category B ops (standard, no L3) ---")
    b_ops = [r for r in rows if r["category"] == "B_no_l3"]
    for r in sorted(b_ops, key=lambda x: -x["freq"])[:20]:
        flags = ""
        if r["is_rejected"]:
            flags += " [REJECTED]"
        if r["is_native_bridge"]:
            flags += " [NATIVE]"
        print(f"  {r['alg_id']:45s} {r['freq']:5d}x  \"{r['official_name'][:40]}\"{flags}")

    # Write CSV
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_path = out_dir / "qgis_operator_audit.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as f:
        writer = csv.writer(f)
        writer.writerow([
            "alg_id", "freq", "category", "bridge_type", "l3_code",
            "official_name", "data_type", "in_official", "in_dataset",
            "has_l3", "has_crosswalk", "is_rejected", "is_native_bridge",
        ])
        for r in rows:
            writer.writerow([
                r["alg_id"], r["freq"], r["category"], r["bridge_type"], r["l3_code"],
                r["official_name"], r["data_type"], r["in_official"], r["in_dataset"],
                r["has_l3"], r["has_crosswalk"], r["is_rejected"], r["is_native_bridge"],
            ])
    print(f"\nCSV: {csv_path}")

    # Write JSON summary
    json_path = out_dir / "qgis_operator_audit.json"
    with json_path.open("w", encoding="utf-8") as f:
        json.dump({
            "total_unique_ops": len(rows),
            "total_occurrences": sum(r["freq"] for r in rows),
            "category_counts": {k: stats[k] for k in ["A_l3_bridge", "B_no_l3", "C_non_standard"]},
            "bridge_counts": {k: stats[k] for k in stats if k.startswith("bridge_")},
            "top_B_ops": sorted(b_ops, key=lambda x: -x["freq"])[:30],
            "rows": rows,
        }, f, indent=2, ensure_ascii=False)
    print(f"JSON: {json_path}")


if __name__ == "__main__":
    main()
