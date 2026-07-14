#!/usr/bin/env python3
"""Build a real-code evidence matrix for the experimental QGIS taxonomy."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gis_recommend.data.qgis_pilot import PILOT_SCHEMA, assert_write_allowed, file_sha256  # noqa: E402

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))

ADDITIONS = {
    "L3_02_01_02": ("Reproject", ("reprojectlayer", "warpreproject", "reproject"), ("assignprojection",)),
    "L3_02_01_03": ("Fix Geometries", ("fixgeometries", "repairgeometr"), ("checkvalidity", "checkvalid")),
    "L3_02_03_01": ("Grid", ("creategrid", "fishnet", "regularpoints", "creategraticule"), ("rastergrid",)),
    "L3_02_03_02": ("Simplify", ("simplifygeometr", "v.generalize"), ("smooth",)),
    "L3_02_03_03": ("Voronoi", ("voronoi", "thiessen"), ()),
    "L3_02_03_04": ("Delaunay Triangulation", ("delaunay",), ("triangulate",)),
    "L3_02_05_01": ("Delete Duplicate", ("deleteduplicategeometr", "deleteidenticalgeometr"), ("removeduplicatevertices",)),
    "L3_02_05_02": ("Snap", ("snapgeometr", "snapgeometrytolayer", "snappointstogrid"), ()),
    "L3_02_05_03": ("Delete Holes", ("deleteholes", "removeholes"), ()),
    "L3_02_05_04": ("Smooth", ("smoothgeometry", "v.generalize.smooth"), ("simplify",)),
    "L3_02_05_05": ("Concave Hull", ("concavehull", "knearestconcavehull", "alphashape"), ()),
    "L3_02_07_02": ("Polygons to Lines", ("polygonstolines", "polygonstoline"), ("extractboundary",)),
    "L3_02_07_03": ("Extract Vertices", ("extractvertices", "extractspecificvertices"), ("vertices",)),
}

STANDARD_NAMESPACES = {"native", "qgis", "gdal", "grass", "grass7", "saga", "otb", "pdal"}


def normalize_processing_operation(operation: str) -> str:
    normalized = operation.strip().lower()
    while normalized.startswith("processing.run:"):
        normalized = normalized[len("processing.run:") :]
    return normalized


def candidate_matches(operation: str) -> tuple[list[str], list[str]]:
    normalized = operation.lower().replace("_", "")
    direct, boundary = [], []
    for code, (_, accepted, conflicts) in ADDITIONS.items():
        if any(pattern in normalized for pattern in accepted):
            direct.append(code)
        if any(pattern in normalized for pattern in conflicts):
            boundary.append(code)
    if normalized.startswith("gdal:") and "L3_02_01_02" in direct:
        direct.remove("L3_02_01_02")
    return direct, boundary


def _load_facts(path: Path) -> tuple[set[str], dict[str, dict]]:
    scripts, facts = set(), {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            script = row["script_id"]
            scripts.add(f"{script}.py")
            facts[script] = row
    return scripts, facts


def _is_direct_api(row: dict) -> bool:
    source_type = (row.get("api_source_type") or "").lower()
    family = (row.get("platform_family") or "").lower()
    op = (row.get("normalized_api_name") or "").lower()
    return (
        source_type in {"qgis_api", "gdal_api", "qgis_cpp_api", "direct_api"}
        or family in {"qgis", "gdal", "ogr", "pyqgis"}
        or op.startswith(("qgs", "gdal.", "ogr."))
    )


def scan_evidence(extraction_root: Path, facts_scripts: set[str], facts: dict[str, dict]) -> dict:
    processing_counts = Counter()
    processing_scripts: dict[str, set[str]] = defaultdict(set)
    direct_counts = Counter()
    direct_scripts: dict[str, set[str]] = defaultdict(set)
    source_types = Counter()
    matched: dict[str, dict[str, set[str]]] = {
        code: {"direct": set(), "boundary": set()} for code in ADDITIONS
    }
    examples: dict[str, list[dict]] = defaultdict(list)
    rows_scanned = 0
    facts_rows_scanned = 0

    merged = sorted(extraction_root.glob("*/merged_nodes_process.csv"))
    for table in merged:
        group = table.parent.name
        with table.open(encoding="utf-8-sig", newline="") as handle:
            for row in csv.DictReader(handle):
                rows_scanned += 1
                source_script = (row.get("source_script") or "").strip()
                if source_script not in facts_scripts:
                    continue
                facts_rows_scanned += 1
                script_id = Path(source_script).stem
                source_type = (row.get("api_source_type") or "unknown").strip()
                source_types[source_type] += 1
                operation = (row.get("normalized_api_name") or "").strip()
                if not operation:
                    continue
                is_processing = source_type == "qgis_processing_algorithm"
                if is_processing:
                    op = normalize_processing_operation(operation)
                    processing_counts[op] += 1
                    processing_scripts[op].add(script_id)
                    namespace = op.split(":", 1)[0] if ":" in op else ""
                    if namespace and namespace not in STANDARD_NAMESPACES:
                        source_types["custom_processing_algorithm"] += 1
                    evidence_operation = op
                elif _is_direct_api(row):
                    direct_counts[operation] += 1
                    direct_scripts[operation].add(script_id)
                    evidence_operation = operation
                else:
                    continue

                accepted, boundary = candidate_matches(evidence_operation)
                for code in accepted:
                    matched[code]["direct"].add(script_id)
                    if len(examples[code]) < 5:
                        fact = facts.get(script_id, {})
                        examples[code].append({
                            "script_id": script_id,
                            "extraction_group": group,
                            "operation": evidence_operation,
                            "task_name": fact.get("task_name"),
                            "task_description": fact.get("task_description"),
                        })
                for code in boundary:
                    matched[code]["boundary"].add(script_id)

    return {
        "merged_tables": [str(path) for path in merged],
        "rows_scanned": rows_scanned,
        "facts_rows_scanned": facts_rows_scanned,
        "api_source_type_counts": source_types,
        "processing_counts": processing_counts,
        "processing_scripts": processing_scripts,
        "direct_counts": direct_counts,
        "direct_scripts": direct_scripts,
        "candidate_matches": matched,
        "examples": examples,
    }


def build_matrix(scan: dict, crosswalk_path: Path) -> tuple[list[dict], list[dict]]:
    crosswalk = json.loads(crosswalk_path.read_text(encoding="utf-8"))
    entries = crosswalk.get("entries", {})
    rows = []
    for code, (name, accepted, conflicts) in ADDITIONS.items():
        evidence = scan["candidate_matches"][code]
        matching_ops = []
        for operation, scripts in scan["processing_scripts"].items():
            direct, _ = candidate_matches(operation)
            if code in direct:
                matching_ops.append({
                    "operation": operation,
                    "scripts": len(scripts),
                    "calls": scan["processing_counts"][operation],
                    "old_crosswalk": entries.get(operation),
                })
        rows.append({
            "code": code,
            "name": name,
            "accepted_patterns": list(accepted),
            "boundary_patterns": list(conflicts),
            "unique_scripts": len(evidence["direct"]),
            "boundary_scripts": len(evidence["boundary"]),
            "matching_processing_operations": sorted(matching_ops, key=lambda item: (-item["scripts"], item["operation"])),
            "task_examples": scan["examples"].get(code, []),
            "verdict": "PENDING_USER_REVIEW",
        })

    unmapped = []
    for operation, scripts in scan["processing_scripts"].items():
        entry = entries.get(operation, {})
        if entry.get("bridge_type") == "l3_bridge":
            continue
        unmapped.append({
            "operation": operation,
            "scripts": len(scripts),
            "calls": scan["processing_counts"][operation],
            "existing_bridge_type": entry.get("bridge_type", "absent"),
            "existing_target": entry.get("l3_code", ""),
        })
    unmapped.sort(key=lambda item: (-item["scripts"], item["operation"]))
    return rows, unmapped


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--facts-candidates", type=Path, required=True)
    parser.add_argument("--extraction-root", type=Path, required=True)
    parser.add_argument("--crosswalk", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--allowed-write-root", type=Path, action="append", required=True)
    args = parser.parse_args(argv)
    output = assert_write_allowed(args.output_dir, args.allowed_write_root)
    output.mkdir(parents=True, exist_ok=True)
    facts_scripts, facts = _load_facts(args.facts_candidates)
    scan = scan_evidence(args.extraction_root, facts_scripts, facts)
    matrix, unmapped = build_matrix(scan, args.crosswalk)
    report = {
        "schema": PILOT_SCHEMA,
        "kind": "taxonomy_evidence_matrix",
        "inputs": {
            "facts_candidates": str(args.facts_candidates.resolve()),
            "facts_candidates_sha256": file_sha256(args.facts_candidates),
            "crosswalk": str(args.crosswalk.resolve()),
            "crosswalk_sha256": file_sha256(args.crosswalk),
        },
        "scan": {
            "merged_tables": scan["merged_tables"],
            "rows_scanned": scan["rows_scanned"],
            "facts_rows_scanned": scan["facts_rows_scanned"],
            "api_source_type_counts": dict(scan["api_source_type_counts"].most_common()),
            "unique_processing_operations": len(scan["processing_counts"]),
            "unique_direct_apis": len(scan["direct_counts"]),
        },
        "candidate_additions": matrix,
        "top_unmapped_processing_operations": unmapped[:200],
        "top_direct_apis": [
            {"operation": op, "scripts": len(scan["direct_scripts"][op]), "calls": count}
            for op, count in scan["direct_counts"].most_common(200)
        ],
    }
    json_path = output / "taxonomy_evidence_matrix.json"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    csv_path = output / "taxonomy_evidence_matrix.csv"
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=["code", "name", "unique_scripts", "boundary_scripts", "verdict"])
        writer.writeheader()
        writer.writerows({key: row[key] for key in writer.fieldnames} for row in matrix)
    print(json.dumps(report["scan"], ensure_ascii=False, indent=2))
    print(json_path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
