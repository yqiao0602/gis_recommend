#!/usr/bin/env python3
"""Extract source-backed low-level PyQGIS steps and pattern candidates.

Each input row produces exactly one steps-manifest row.  Patterns require at
least two corroborating GIS families plus an output/boundary signal.  No single
API call is promoted to a Processing operator or an L3 label.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import warnings
from collections import Counter
from pathlib import Path
from typing import Any


PATTERNS: dict[str, tuple[str, ...]] = {
    "vector_layer_io": ("qgsvectorlayer", "qgsvectorfilewriter", "qgsproviderregistry", "addfeature"),
    "feature_geometry": ("qgsfeature.geometry", "qgsgeometry.", "qgsgeometry", ".geometry"),
    "field_attribute_edit": ("qgsfield", "qgsfields", "changeattribute", "updatefields", "setattribute", "addattribute"),
    "crs_transform": ("qgscoordinatereferencesystem", "qgscoordinatetransform", "transformcontext", "setcrs"),
    "raster_io_pixel": ("qgsrasterlayer", "qgsrasterdataprovider", "qgsrasterblock", "qgsrastercalculator", "rasterunitsperpixel"),
    "spatial_index_query": ("qgsspatialindex", "nearestneighbor", ".intersects", "spatialindex"),
    "sink_output": ("qgsfeaturesink", "addfeature", "writeasvector", "qgsvectorfilewriter", ".write", ".output"),
}


def _name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    if isinstance(node, ast.Call):
        return _name(node.func)
    if isinstance(node, ast.Subscript):
        return _name(node.value)
    return ""


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _matched(name: str, tokens: tuple[str, ...]) -> bool:
    return any(token in name for token in tokens)


def extract(row: dict[str, Any]) -> dict[str, Any]:
    path = Path(str(row.get("source_path") or ""))
    expected_sha = str(row.get("source_sha256") or "")
    base = {
        "schema": "gis_recommend.qgis_api_source_steps.v1",
        "record_id": row.get("record_id", ""),
        "source_path": str(path),
        "source_sha256": expected_sha,
        "source_root_id": row.get("source_root_id", ""),
        "primary_layer": row.get("primary_layer", ""),
        "candidate_l3_sequence": [],
        "training_admission": "not_granted",
        "training_row_emitted": False,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }
    if not path.is_file():
        return {**base, "source_verification": "missing", "parse_status": "not_read", "steps": [], "pattern_names": [], "task_boundary_evidence": False, "status": "deferred_source_failure"}
    actual_sha = _sha(path)
    if actual_sha != expected_sha:
        return {**base, "source_verification": "sha_mismatch", "parse_status": "not_parsed", "steps": [], "pattern_names": [], "task_boundary_evidence": False, "status": "deferred_source_failure"}
    source = path.read_text(encoding="utf-8-sig", errors="replace")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(source)
    except SyntaxError:
        return {**base, "source_verification": "verified_sha256", "parse_status": "syntax_error", "steps": [], "pattern_names": [], "task_boundary_evidence": False, "status": "deferred_parse_failure"}

    steps = []
    for node in sorted(ast.walk(tree), key=lambda item: (getattr(item, "lineno", 0), getattr(item, "col_offset", 0))):
        if not isinstance(node, ast.Call):
            continue
        name = _name(node.func).strip().lower()
        matched_patterns = sorted(pattern for pattern, tokens in PATTERNS.items() if _matched(name, tokens))
        if not matched_patterns:
            continue
        steps.append({
            "name": name,
            "line_start": int(node.lineno),
            "line_end": int(node.end_lineno or node.lineno),
            "pattern_names": matched_patterns,
        })
    pattern_names = sorted({pattern for step in steps for pattern in step["pattern_names"]})
    has_boundary_signal = "sink_output" in pattern_names or len(steps) >= 3
    boundary = len(pattern_names) >= 2 and has_boundary_signal
    return {
        **base,
        "source_verification": "verified_sha256",
        "parse_status": "parsed",
        "steps": steps,
        "step_count": len(steps),
        "pattern_names": pattern_names,
        "task_boundary_evidence": boundary,
        "status": "pattern_candidate" if boundary else "deferred_insufficient_task_boundary",
        "reason": "two_or_more_gis_patterns_with_boundary_evidence" if boundary else "single_or_weak_api_signal",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    steps_path = args.output_dir / "api_steps_manifest_v1.jsonl"
    statuses: Counter[str] = Counter()
    patterns: Counter[str] = Counter()
    source_verification: Counter[str] = Counter()
    parse_status: Counter[str] = Counter()
    rows = total_steps = 0
    with args.source_manifest.open(encoding="utf-8") as source_handle, steps_path.open("w", encoding="utf-8", newline="\n") as output_handle:
        for line in source_handle:
            if not line.strip():
                continue
            result = extract(json.loads(line))
            output_handle.write(json.dumps(result, ensure_ascii=False, sort_keys=True) + "\n")
            rows += 1
            total_steps += int(result.get("step_count") or 0)
            statuses[str(result["status"])] += 1
            source_verification[str(result["source_verification"])] += 1
            parse_status[str(result["parse_status"])] += 1
            patterns.update(result.get("pattern_names") or [])
    if rows != 39386:
        raise ValueError(f"API source manifest must contain 39,386 rows, got {rows}")
    summary = {
        "schema": "gis_recommend.qgis_api_source_pattern_census.v1",
        "source_rows": rows,
        "total_extracted_steps": total_steps,
        "source_verification_counts": dict(sorted(source_verification.items())),
        "parse_status_counts": dict(sorted(parse_status.items())),
        "status_counts": dict(sorted(statuses.items())),
        "pattern_support": dict(sorted(patterns.items())),
        "source_disjoint_calibration": "pending",
        "task_boundary_admission": "pending_review",
        "l3_mapping_rows": 0,
        "description_fidelity_rows": 0,
        "dedup_rows": 0,
        "training_rows_emitted": 0,
        "training_admission": "not_granted_pattern_census_only",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "llm_called": False,
    }
    summary_path = args.output_dir / "summary_v1.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output_dir / "hash_ledger_v1.json").write_text(json.dumps({
        "schema": "gis_recommend.hash_ledger.v1",
        "inputs": {"source_manifest": {"path": str(args.source_manifest), "sha256": _sha(args.source_manifest)}},
        "artifacts": {steps_path.name: _sha(steps_path), summary_path.name: _sha(summary_path)},
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
