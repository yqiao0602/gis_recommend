#!/usr/bin/env python3
"""Build a QGIS operator chain dataset from GitHub crawled scripts.

Reads the crawled GitHub QGIS scripts, extracts processing.run() sequences,
matches operators against the QGIS algorithm catalog, generates task_text
from available signals, and outputs a structured JSONL dataset.

Output structure:
{
    "task_text": "buffer roads and clip by study area",
    "qgis_ops": ["native:buffer", "native:clip"],
    "operator_names": ["Buffer", "Clip"],
    "source": "github_qgis_workflow_A",
    "quality": {
        "all_ops_in_catalog": true,
        "length": 2,
        "has_input_signal": true,
        "has_output_signal": true
    },
    "optional_l3_sequence": ["L3_02_01_01", "L3_02_02_06"]
}

Usage:
    python scripts/build_qgis_chain_dataset.py \
        --output outputs_v2/qgis_chain_dataset.jsonl \
        --min-length 2 --max-length 15
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
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

QGIS_DIR = ROOT / "爬取GithubQGIS"
CATALOG_PATH = QGIS_DIR / "QGIS_Input.csv"
OFFICIAL_OPS_PATH = ROOT.parent / "operators-json" / "qgis_operators.json"

SCRIPT_DIRS = [
    ("QGIS_standard_multi_operator_workflows_v2", "standard_v2"),
    ("github_qgis_workflow", "workflow"),
    ("github_qgis_workflow_A类", "workflow_A"),
]

# ── Operator Catalog ───────────────────────────────────────────────

def load_operator_catalog(path: Path) -> dict[str, dict]:
    """Parse QGIS_Input.csv into {algorithm_id: {name, platform, type}}."""
    catalog = {}
    with path.open("r", encoding="utf-8", errors="ignore") as f:
        # QGIS_Input.csv has malformed structure — read row by row manually
        reader = csv.reader(f)
        for row in reader:
            if len(row) < 6:
                continue
            platform = row[0].strip()
            name = row[2].strip() if len(row) > 2 else ""
            alg_id = row[5].strip() if len(row) > 5 else ""
            if not alg_id or not name:
                continue
            # Determine data type from later columns
            data_type = "unknown"
            for col in row[8:]:
                if col.strip() in ("vector", "raster"):
                    data_type = col.strip()
                    break
            catalog[alg_id.lower()] = {
                "name": name,
                "platform": platform,
                "data_type": data_type,
                "alg_id": alg_id.lower(),
            }
    return catalog


# ── Script Parsing ─────────────────────────────────────────────────

def extract_processing_calls(content: str) -> list[dict]:
    """Extract processing.run() calls with algo name and parameters."""
    calls = []
    pattern = r'processing\.run\(\s*[\"\']([a-z0-9_]+:[a-z0-9_]+)[\"\']'
    for m in re.finditer(pattern, content, re.IGNORECASE):
        calls.append({"alg_id": m.group(1).lower(), "position": m.start()})
    return calls


def extract_task_text(content: str, file_name: str, source: str) -> str:
    """Generate task text from available script signals."""
    parts = []

    # 1) Module/class docstring (first triple-quoted string)
    doc_match = re.search(r'\"\"\"(.+?)\"\"\"', content, re.DOTALL)
    if doc_match:
        doc = doc_match.group(1).strip()
        # Take first meaningful line
        for line in doc.split("\n"):
            line = line.strip()
            if line and not line.startswith("#") and len(line) > 10:
                parts.append(line[:200])
                break

    # 2) Function/class name
    func_match = re.search(
        r'def\s+(\w+)\s*\(', content
    )
    if not func_match:
        func_match = re.search(r'class\s+(\w+)\s*[(:]', content)
    if func_match:
        name = func_match.group(1)
        # Convert snake_case to readable
        readable = name.replace("_", " ").strip()
        if len(readable) > 3:
            parts.append(readable[:100])

    # 3) Script file name
    stem = Path(file_name).stem
    if stem and not stem.startswith("script_"):
        readable = stem.replace("_", " ").strip()
        if len(readable) > 3:
            parts.append(readable[:100])

    # 4) Comment near first processing call
    comment_match = re.search(r'#\s*(.{10,120})', content)
    if comment_match and comment_match.group(1).strip() not in parts:
        parts.append(comment_match.group(1).strip()[:120])

    task_text = " ".join(parts).strip()
    if not task_text or len(task_text) < 5:
        task_text = f"QGIS processing workflow"

    return task_text[:300]


# ── Quality Checks ─────────────────────────────────────────────────

def audit_chain(ops: list[str], catalog: dict[str, dict]) -> dict:
    """Generate quality flags for a QGIS operator chain."""
    flags = {}

    # All ops in catalog
    all_in = all(op.lower() in catalog for op in ops)
    flags["all_ops_in_catalog"] = all_in

    # Length
    flags["length"] = len(ops)

    # Has input/output signals (heuristic: first/last op has INPUT/OUTPUT patterns)
    # Actual I/O check requires parameter-level parsing, not done here
    flags["has_input_signal"] = len(ops) >= 1
    flags["has_output_signal"] = len(ops) >= 1

    # Operator types
    types = []
    for op in ops:
        cat = catalog.get(op.lower(), {})
        t = cat.get("data_type", "unknown")
        types.append(t)
    flags["vector_ops"] = sum(1 for t in types if t == "vector")
    flags["raster_ops"] = sum(1 for t in types if t == "raster")
    flags["is_pure_vector"] = flags["vector_ops"] == len(ops) and len(ops) > 0
    flags["is_pure_raster"] = flags["raster_ops"] == len(ops) and len(ops) > 0
    flags["is_mixed"] = flags["vector_ops"] > 0 and flags["raster_ops"] > 0

    # Transition frequency (pairs that appear often)
    transitions = []
    for i in range(len(ops) - 1):
        transitions.append(f"{ops[i]} -> {ops[i+1]}")
    flags["transitions"] = transitions

    return flags


# ── L3 Mapping (optional) ──────────────────────────────────────────

# QGIS-native semantic tags for operators without L3 mapping
QGIS_SEMANTIC_TAGS = {
    "reprojectlayer": "vector_crs_transform",
    "fixgeometries": "geometry_repair",
    "snapgeometries": "geometry_repair",
    "simplifygeometries": "geometry_simplify",
    "smoothgeometry": "geometry_smooth",
    "checkvalidity": "geometry_validation",
    "deleteholes": "geometry_cleanup",
    "deleteduplicategeometries": "geometry_dedup",
    "removeduplicatevertices": "geometry_dedup",
    "polygonstolines": "geometry_boundary",
    "linestopolygons": "geometry_conversion",
    "extractvertices": "geometry_vertices",
    "pointsalonglines": "geometry_sampling",
    "splitwithlines": "geometry_split",
    "singlepartstomultipart": "geometry_merge",
    "multiparttosingleparts": "geometry_explode",
    "createspatialindex": "index_maintenance",
    "saveselectedfeatures": "data_export",
    "savefeatures": "data_export",
    "rasterize": "rasterize_convert",
    "polygonize": "polygonize_convert",
    "pixelstopolygons": "polygonize_convert",
    "contour": "surface_derivative",
    "contour_polygon": "surface_derivative",
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
    "single sided buffer": "buffer_variant",
}


def _build_semantic_tags(ops: list[str]) -> list[str]:
    """Derive semantic tags for a QGIS chain from operator keywords."""
    tags = []
    seen = set()
    for op in ops:
        name_lower = op.lower().replace("native:", "").replace("qgis:", "").replace("gdal:", "").replace("saga:", "")
        for kw, tag in QGIS_SEMANTIC_TAGS.items():
            if kw.lower() in name_lower and tag not in seen:
                tags.append(tag)
                seen.add(tag)
                break
    return tags


def load_official_qgis_operators(path: Path) -> dict[str, dict]:
    """Load official qgis_operators.json → {identifier_lower: {name, platform, ...}}."""
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        ops_list = json.load(f)
    catalog = {}
    for op in ops_list:
        ident = str(op.get("identifier", "")).lower().strip()
        name = str(op.get("name", "")).strip()
        platform = str(op.get("platform", "")).strip()
        if ident and name:
            catalog[ident] = {"name": name, "platform": platform, "alg_id": ident}
    return catalog


def load_alg_id_crosswalk(path: Path) -> dict[str, str]:
    """Load alg_id → L3 code mapping from crosswalk JSON."""
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    return {
        alg_id: entry.get("l3_code", "")
        for alg_id, entry in data.get("entries", {}).items()
        if entry.get("bridge_type") in ("l3_bridge",)
    }


def map_to_l3(ops: list[str], catalog: dict[str, dict], l3_mapping: dict,
              alg_id_crosswalk: dict[str, str] | None = None) -> Optional[list[str]]:
    """Map QGIS operator chain to L3 codes.

    Priority: alg_id_crosswalk → official name → id_mappings.
    """
    l3_chain = []
    for op in ops:
        op_lower = op.lower()
        l3_code = None

        # 1) Direct alg_id crosswalk
        if alg_id_crosswalk:
            l3_code = alg_id_crosswalk.get(op_lower)

        # 2) Official name → id_mappings
        if not l3_code:
            cat = catalog.get(op_lower, {})
            name = cat.get("name", "")
            if name:
                l3_code = l3_mapping.get(name.lower().strip())

        if not l3_code:
            return None
        l3_chain.append(l3_code)
    return l3_chain


def build_l3_lookup(id_mappings_path: Path) -> dict[str, str]:
    """Build {qgis_name_lower: l3_code} from id_mappings_v2.json."""
    if not id_mappings_path.exists():
        return {}
    with id_mappings_path.open("r", encoding="utf-8") as f:
        idm = json.load(f)
    qgis_to_l3 = idm.get("mapping_metadata", {}).get("qgis_to_l3", {})
    lookup = {}
    for qgis_name, info in qgis_to_l3.items():
        if isinstance(info, dict):
            primary = info.get("primary_l3", "")
            if primary:
                lookup[qgis_name.lower().strip()] = primary
            for cand in info.get("all_candidates", []):
                code = cand.get("l3_code", "") if isinstance(cand, dict) else ""
                if code:
                    lookup[qgis_name.lower().strip()] = code
    return lookup


# ── Main ───────────────────────────────────────────────────────────

def build_dataset(
    *,
    catalog: dict[str, dict],
    l3_lookup: dict[str, str],
    min_length: int = 2,
    max_length: int = 15,
    alg_id_xwalk: dict[str, str] | None = None,
    require_catalog: bool = True,
) -> list[dict]:
    dataset = []
    stats = Counter()

    for dir_name, source_label in SCRIPT_DIRS:
        scripts_dir = QGIS_DIR / dir_name / "downloaded_scripts"
        if not scripts_dir.exists():
            print(f"  [SKIP] {scripts_dir} not found")
            continue

        for file_name in sorted(os.listdir(scripts_dir)):
            file_path = scripts_dir / file_name
            try:
                with file_path.open("r", encoding="utf-8", errors="ignore") as f:
                    content = f.read()
            except Exception:
                continue

            calls = extract_processing_calls(content)
            ops = [c["alg_id"] for c in calls]

            if len(ops) < min_length or len(ops) > max_length:
                stats[f"rejected_length_{'short' if len(ops) < min_length else 'long'}"] += 1
                continue

            if require_catalog and not all(op.lower() in catalog for op in ops):
                stats["rejected_missing_catalog"] += 1
                continue

            task_text = extract_task_text(content, file_name, source_label)
            quality = audit_chain(ops, catalog)
            operator_names = [catalog.get(op.lower(), {}).get("name", op) for op in ops]

            item = {
                "task_text": task_text,
                "qgis_ops": ops,
                "operator_names": operator_names,
                "source": source_label,
                "quality": quality,
            }

            # QGIS-native semantic tags (for operators without L3 mapping)
            semantic_tags = _build_semantic_tags(ops)
            if semantic_tags:
                item["qgis_semantic_tags"] = semantic_tags

            l3_seq = map_to_l3(ops, catalog, l3_lookup, alg_id_xwalk)
            if l3_seq is not None:
                item["optional_l3_sequence"] = l3_seq
                item["training_targets"] = ["qgis_head", "l3_head"]
            else:
                item["training_targets"] = ["qgis_head"]

            dataset.append(item)
            stats["included"] += 1

    stats["total_included"] = stats["included"]
    return dataset, dict(stats)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", default=str(ROOT / "outputs_v2" / "qgis_chain_dataset.jsonl"))
    parser.add_argument("--catalog", default=str(CATALOG_PATH), help="Fallback catalog (QGIS_Input.csv) for data_type info")
    parser.add_argument("--official-ops", default=str(OFFICIAL_OPS_PATH), help="Official qgis_operators.json for identifier→name mapping")
    parser.add_argument("--id-mappings", default=str(ROOT / "outputs_v2" / "id_mappings_v2.json"))
    parser.add_argument("--min-length", type=int, default=2)
    parser.add_argument("--max-length", type=int, default=15)
    parser.add_argument("--require-catalog", action="store_true", default=True)
    parser.add_argument("--summary", default=str(ROOT / "outputs_v2" / "qgis_chain_dataset_summary.json"))
    args = parser.parse_args(argv)

    print("=" * 60)
    print("QGIS Chain Dataset Builder")
    print("=" * 60)

    # Load official operators as primary catalog (identifier → name)
    official_path = Path(args.official_ops)
    catalog = load_official_qgis_operators(official_path)
    print(f"\n[1] Official QGIS operators: {len(catalog)} from {official_path}")

    # Load QGIS_Input.csv as fallback for data_type info
    legacy_catalog = {}
    legacy_path = Path(args.catalog)
    if legacy_path.exists():
        legacy_catalog = load_operator_catalog(legacy_path)
        print(f"    Legacy catalog: {len(legacy_catalog)} operators for data_type")
        # Merge data_type from legacy into official catalog
        for alg_id, info in catalog.items():
            if alg_id in legacy_catalog:
                info["data_type"] = legacy_catalog[alg_id].get("data_type", "unknown")
            else:
                info["data_type"] = "unknown"
    else:
        for info in catalog.values():
            info.setdefault("data_type", "unknown")

    vec_ops = sum(1 for c in catalog.values() if c["data_type"] == "vector")
    rast_ops = sum(1 for c in catalog.values() if c["data_type"] == "raster")
    print(f"    Vector: {vec_ops}, Raster: {rast_ops}")

    print(f"\n[2] Loading L3 mappings ...")
    l3_lookup = build_l3_lookup(Path(args.id_mappings))
    alg_id_xwalk = load_alg_id_crosswalk(ROOT / "outputs_v2" / "qgis_alg_id_crosswalk.json")
    print(f"  {len(l3_lookup)} name-based mappings + {len(alg_id_xwalk)} alg_id crosswalk entries")

    print(f"\n[3] Building dataset ...")
    dataset, stats = build_dataset(
        catalog=catalog,
        l3_lookup=l3_lookup,
        min_length=args.min_length,
        max_length=args.max_length,
        require_catalog=args.require_catalog,
        alg_id_xwalk=alg_id_xwalk,
    )

    # Print stats
    print(f"\n  Rejected (short):     {stats.get('rejected_length_short', 0)}")
    print(f"  Rejected (long):      {stats.get('rejected_length_long', 0)}")
    print(f"  Rejected (no catalog): {stats.get('rejected_missing_catalog', 0)}")
    print(f"  Included:             {stats.get('included', 0)}")

    # Quality breakdown
    with_l3 = sum(1 for d in dataset if "optional_l3_sequence" in d)
    pure_vector = sum(1 for d in dataset if d["quality"]["is_pure_vector"])
    pure_raster = sum(1 for d in dataset if d["quality"]["is_pure_raster"])
    mixed = sum(1 for d in dataset if d["quality"]["is_mixed"])
    print(f"\n  With L3 mapping: {with_l3}/{len(dataset)} ({with_l3/max(len(dataset),1)*100:.1f}%)")
    print(f"  Pure vector:     {pure_vector}")
    print(f"  Pure raster:     {pure_raster}")
    print(f"  Mixed vec+rast:  {mixed}")

    # Unique chains
    unique = set(tuple(d["qgis_ops"]) for d in dataset)
    print(f"  Unique chains:   {len(unique)}")

    # Top operators
    op_counts = Counter()
    for d in dataset:
        for op in d["qgis_ops"]:
            op_counts[op] += 1
    print(f"\n  Top 10 operators:")
    for op, cnt in op_counts.most_common(10):
        name = catalog.get(op, {}).get("name", op)
        print(f"    {op:40s} {name:30s} {cnt:4d}x")

    # Write JSONL
    print(f"\n[4] Writing {len(dataset)} records to {args.output} ...")
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with Path(args.output).open("w", encoding="utf-8") as f:
        for d in dataset:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    print(f"  Done: {args.output}")

    # Write summary
    summary = {
        "total_records": len(dataset),
        "unique_chains": len(unique),
        "with_l3_mapping": with_l3,
        "pure_vector": pure_vector,
        "pure_raster": pure_raster,
        "mixed_vec_rast": mixed,
        "stats": stats,
        "top_operators": dict(op_counts.most_common(30)),
    }
    Path(args.summary).parent.mkdir(parents=True, exist_ok=True)
    with Path(args.summary).open("w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"  Summary: {args.summary}")


if __name__ == "__main__":
    main()
