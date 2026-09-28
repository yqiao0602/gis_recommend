#!/usr/bin/env python3
"""Extract deterministic low-level PyQGIS API patterns from *_steps.csv files.

The extractor identifies repeated API combinations and task-boundary evidence;
it never treats a single API call or an existing L3/LLM label as a training
truth.  Rows without at least two corroborating GIS signals remain deferred.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


EXCLUDED_ROLES = {
    "EXPRESSION_ASSIGNMENT", "UI_TEXT_TRANSLATE", "CONTROL_CONDITION",
    "PYTHON_BUILTIN", "TYPE_CAST", "COLLECTION_SIZE", "TEXT_JOIN",
}

PATTERNS: dict[str, tuple[str, ...]] = {
    "vector_layer_io": ("qgsvectorlayer", "qgsvectorfilewriter", "qgsproviderregistry", "addfeature"),
    "feature_geometry": ("qgsfeature.geometry", "qgsgeometry.", "qgsgeometry", "geometry."),
    "field_attribute_edit": ("qgsfield", "qgsfields", "changeattribute", "updatefields", "setattribute", "addattribute"),
    "crs_transform": ("qgscoordinatereferencesystem", "qgscoordinatetransform", "transformcontext", "setcrs"),
    "raster_io_pixel": ("qgsrasterlayer", "qgsrasterdataprovider", "qgsrasterblock", "qgsrastercalculator", "rasterunitsperpixel"),
    "spatial_index_query": ("qgsspatialindex", "nearestneighbor", ".intersects", "spatialindex"),
    "sink_output": ("qgsfeaturesink", "addfeature", "writeasvector", "qgsvectorfilewriter", "output"),
}


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _signal_matches(api_name: str, pattern: tuple[str, ...]) -> bool:
    return any(token in api_name for token in pattern)


def extract_file(path: Path) -> dict[str, Any]:
    rows: list[dict[str, str]] = []
    with path.open(encoding="utf-8", errors="replace", newline="") as handle:
        rows.extend(csv.DictReader(handle))
    usable = [
        row for row in rows
        if (row.get("semantic_role") or "") not in EXCLUDED_ROLES
        and (row.get("normalized_api_name") or row.get("name") or "").strip()
    ]
    names = [
        (row.get("normalized_api_name") or row.get("name") or "").strip().lower()
        for row in usable
    ]
    matched = {
        pattern: sorted({name for name in names if _signal_matches(name, tokens)})
        for pattern, tokens in PATTERNS.items()
    }
    matched = {key: value for key, value in matched.items() if value}
    gis_rows = [row for row in usable if any(_signal_matches(
        (row.get("normalized_api_name") or row.get("name") or "").strip().lower(), tokens
    ) for tokens in PATTERNS.values())]
    output_types = sorted({(row.get("output_type") or "").strip() for row in gis_rows if row.get("output_type")})
    input_types = sorted({(row.get("input_type") or "").strip() for row in gis_rows if row.get("input_type")})
    pattern_names = sorted(matched)
    boundary_evidence = len(pattern_names) >= 2 and (bool(output_types) or len(gis_rows) >= 3)
    status = "pattern_candidate" if boundary_evidence else "deferred_insufficient_task_boundary"
    reason = "two_or_more_gis_patterns_with_boundary_evidence" if boundary_evidence else "single_or_weak_api_signal"
    return {
        "schema": "gis_recommend.qgis_api_pattern_row.v1",
        "source_path": str(path),
        "source_sha256": _sha256(path),
        "script_id": path.stem.removesuffix("_steps"),
        "raw_step_count": len(rows),
        "usable_step_count": len(usable),
        "gis_signal_step_count": len(gis_rows),
        "pattern_names": pattern_names,
        "pattern_api_names": matched,
        "input_types": input_types,
        "output_types": output_types,
        "task_boundary_evidence": boundary_evidence,
        "status": status,
        "reason": reason,
        "candidate_l3_sequence": [],
        "training_admission": "not_granted",
        "training_row_emitted": False,
    }


def extract_paths(paths: Iterable[Path]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = [extract_file(path) for path in sorted(paths) if path.is_file()]
    counts = Counter(row["status"] for row in rows)
    pattern_counts = Counter(pattern for row in rows for pattern in row["pattern_names"])
    summary = {
        "schema": "gis_recommend.qgis_api_pattern_census.v1",
        "source_file_count": len(rows),
        "status_counts": dict(sorted(counts.items())),
        "pattern_support": dict(sorted(pattern_counts.items())),
        "candidate_l3_rows": 0,
        "training_rows_emitted": 0,
        "training_admission": "not_granted_pattern_census_only",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "llm_called": False,
    }
    return rows, summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    paths = list(args.input_dir.glob("*_steps.csv"))
    rows, summary = extract_paths(paths)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    ledger = args.output_dir / "pattern_ledger_v1.jsonl"
    ledger.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    summary_path = args.output_dir / "summary_v1.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    hash_ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "inputs": {"input_dir": {"path": str(args.input_dir), "file_count": len(paths)}},
        "artifacts": {ledger.name: _sha256(ledger), summary_path.name: _sha256(summary_path)},
    }
    (args.output_dir / "hash_ledger_v1.json").write_text(json.dumps(hash_ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (args.output_dir / "report_v1.md").write_text(
        "# QGIS low-level API pattern census v1\n\n"
        "Deterministic pattern extraction only; no API call is treated as an operator or training truth.\n\n"
        f"- Source step files: **{summary['source_file_count']}**\n"
        f"- Pattern candidates: **{summary['status_counts'].get('pattern_candidate', 0)}**\n"
        f"- Deferred for weak task boundary: **{summary['status_counts'].get('deferred_insufficient_task_boundary', 0)}**\n"
        "- Training rows emitted: **0**\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
