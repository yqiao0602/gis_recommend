#!/usr/bin/env python3
"""Rank composite producer-mutation-sink QGIS API terminal macros."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

RULE_ID = "qgis-api-producer-mutation-sink-terminal-window-v1"
SPECIFIC_PRODUCERS = {
    "buffer",
    "centroid",
    "combine",
    "convexhull",
    "difference",
    "intersection",
    "interpolate",
    "makevalid",
    "offsetcurve",
    "qgscoordinatetransform",
    "qgsgeometry.frompoint",
    "qgsgeometry.frompointxy",
    "qgsgeometry.frompolygon",
    "qgsgeometry.frompolyline",
    "qgsrastercalculator",
    "simplify",
    "smooth",
    "symdifference",
    "transform",
    "unaryunion",
}
MUTATIONS = {
    "addattribute",
    "addattributes",
    "changeattributevalue",
    "changeattributevalues",
    "setattribute",
    "setattributes",
    "setcrs",
    "setgeometry",
    "updatefeature",
    "updatefields",
}
SINKS = {
    "addfeature",
    "addfeatures",
    "writeraster",
    "writeasvectorformat",
    "writeasvectorformatv2",
    "writeasvectorformatv3",
}
COMPLETED_SEMANTICS = {
    "buffer",
    "centroid",
    "convexhull",
    "difference",
    "intersection",
    "qgsrastercalculator",
    "simplify",
}


def _producer_rollup(producer: str) -> str:
    if producer in {"qgsgeometry.frompoint", "qgsgeometry.frompointxy"}:
        return "point_geometry_construction"
    if producer in {"qgsgeometry.frompolyline", "qgsgeometry.frompolylinexy"}:
        return "polyline_geometry_construction"
    if producer in {"qgsgeometry.frompolygon", "qgsgeometry.frompolygonxy"}:
        return "polygon_geometry_construction"
    if producer == "qgsgeometry.fromwkt":
        return "wkt_geometry_construction"
    if producer == "qgsgeometry.fromrect":
        return "rectangle_geometry_construction"
    if producer == "qgscoordinatetransform":
        return "coordinate_transform"
    if producer == "unaryunion":
        return "unary_union"
    return producer


def _method(name: str) -> str:
    return name.strip().lower().rsplit(".", 1)[-1]


def _producer(name: str) -> str:
    normalized = name.strip().lower()
    method = _method(normalized)
    if normalized.startswith("qgsgeometry.from"):
        return normalized
    if "qgscoordinatetransform" in normalized:
        return "qgscoordinatetransform"
    if "qgsrastercalculator" in normalized:
        return "qgsrastercalculator"
    return method if method in SPECIFIC_PRODUCERS else ""


def _sink(name: str) -> str:
    method = _method(name)
    if method in SINKS:
        return method
    normalized = name.strip().lower()
    if method == "write" and "writer" in normalized:
        return "write"
    return ""


def build_terminal_units(
    row: dict[str, Any], *, maximum_lines: int, maximum_steps: int
) -> list[dict[str, Any]]:
    if row.get("status") != "pattern_candidate":
        return []
    steps = sorted(
        row.get("steps") or [],
        key=lambda item: (int(item.get("line_start") or 0), str(item.get("name") or "")),
    )
    units: list[dict[str, Any]] = []
    for sink_step in steps:
        sink_name = _sink(str(sink_step.get("name") or ""))
        if not sink_name:
            continue
        sink_line = int(sink_step.get("line_start") or 0)
        window = [
            step
            for step in steps
            if 0 <= sink_line - int(step.get("line_start") or 0) <= maximum_lines
        ][-maximum_steps:]
        producers = sorted(
            {
                value
                for step in window
                if (value := _producer(str(step.get("name") or "")))
            }
        )
        mutations = sorted(
            {
                method
                for step in window
                if (method := _method(str(step.get("name") or ""))) in MUTATIONS
            }
        )
        if not producers or not mutations:
            continue
        signature = {
            "producers": producers,
            "mutations": mutations,
            "sink": sink_name,
        }
        unit_id = hashlib.sha256(
            json.dumps(
                {
                    "source_sha256": row.get("source_sha256"),
                    "sink_line": sink_line,
                    "signature": signature,
                },
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        units.append(
            {
                "schema": "gis_recommend.qgis_api_terminal_macro_discovery_unit.v1",
                "terminal_macro_rule_id": RULE_ID,
                "unit_id": unit_id,
                "record_id": row.get("record_id"),
                "source_path": row.get("source_path"),
                "source_sha256": row.get("source_sha256"),
                "source_root_id": row.get("source_root_id"),
                "sink_line": sink_line,
                "window_line_start": min(
                    int(step.get("line_start") or sink_line) for step in window
                ),
                "window_line_end": int(sink_step.get("line_end") or sink_line),
                "producer_signature": producers,
                "mutation_signature": mutations,
                "sink_signature": sink_name,
                "window_call_names": [str(step.get("name") or "") for step in window],
                "completed_semantic_overlap": sorted(
                    set(producers).intersection(COMPLETED_SEMANTICS)
                ),
                "source_verification": row.get("source_verification"),
                "candidate_l3_sequence": [],
                "mapping_status": "not_started_discovery_only",
                "description_fidelity": "not_started",
                "training_admission": "not_granted_terminal_macro_census_only",
                "training_row_emitted": False,
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
                "llm_called": False,
            }
        )
    return units


def _signature_key(row: dict[str, Any]) -> str:
    return json.dumps(
        {
            "producers": row["producer_signature"],
            "mutations": row["mutation_signature"],
            "sink": row["sink_signature"],
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def build_family_census(
    units: list[dict[str, Any]], *, minimum_support: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for unit in units:
        grouped[_signature_key(unit)].append(unit)
    families: list[dict[str, Any]] = []
    priority_units: list[dict[str, Any]] = []
    for signature_key, members in grouped.items():
        signature = json.loads(signature_key)
        source_shas = sorted({str(row["source_sha256"]) for row in members})
        overlap = sorted(
            {
                semantic
                for row in members
                for semantic in row["completed_semantic_overlap"]
            }
        )
        if overlap:
            priority = "defer_completed_semantic_overlap"
        elif len(source_shas) < minimum_support:
            priority = "defer_source_sha_support_below_threshold"
        else:
            priority = "source_replay_required"
        family_id = hashlib.sha256(signature_key.encode("utf-8")).hexdigest()
        families.append(
            {
                "schema": "gis_recommend.qgis_api_terminal_macro_family_census.v1",
                "terminal_macro_rule_id": RULE_ID,
                "family_id": family_id,
                "producer_signature": signature["producers"],
                "mutation_signature": signature["mutations"],
                "sink_signature": signature["sink"],
                "unit_count": len(members),
                "source_sha_support": len(source_shas),
                "support_basis": "source_sha_discovery_only_not_normalized_body_authority",
                "completed_semantic_overlap": overlap,
                "review_priority": priority,
                "example_unit_ids": sorted(row["unit_id"] for row in members)[:10],
                "mapping_rows_emitted": 0,
                "description_fidelity_rows": 0,
                "training_rows_emitted": 0,
                "training_admission": "not_granted_terminal_macro_census_only",
            }
        )
        if priority == "source_replay_required":
            priority_units.extend({**row, "family_id": family_id} for row in members)
    families.sort(
        key=lambda row: (
            row["review_priority"] != "source_replay_required",
            -int(row["source_sha_support"]),
            str(row["family_id"]),
        )
    )
    priority_units.sort(key=lambda row: (str(row["family_id"]), str(row["unit_id"])))
    summary = {
        "schema": "gis_recommend.qgis_api_terminal_macro_census_summary.v1",
        "terminal_macro_rule_id": RULE_ID,
        "terminal_macro_units": len(units),
        "family_count": len(families),
        "priority_family_count": sum(
            row["review_priority"] == "source_replay_required" for row in families
        ),
        "priority_units": len(priority_units),
        "minimum_source_sha_support": minimum_support,
        "support_limitation": "normalized_body_authority_requires_server_source_replay",
        "mapping_rows_emitted": 0,
        "description_fidelity_rows": 0,
        "training_rows_emitted": 0,
        "training_admission": "not_granted_terminal_macro_census_only",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "llm_called": False,
    }
    return families, priority_units, summary


def build_semantic_rollup_census(
    units: list[dict[str, Any]], *, minimum_support: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for unit in units:
        rollups = sorted({_producer_rollup(value) for value in unit["producer_signature"]})
        if len(rollups) != 1:
            continue
        grouped[rollups[0]].append(unit)
    census: list[dict[str, Any]] = []
    priority: list[dict[str, Any]] = []
    for family, members in grouped.items():
        source_shas = {str(row["source_sha256"]) for row in members}
        completed_overlap = sorted(
            {
                semantic
                for row in members
                for semantic in row["completed_semantic_overlap"]
            }
        )
        if completed_overlap:
            review_priority = "defer_completed_semantic_overlap"
        elif len(source_shas) < minimum_support:
            review_priority = "defer_source_sha_support_below_threshold"
        else:
            review_priority = "source_replay_required"
        family_id = hashlib.sha256(
            f"terminal-semantic-rollup-v1:{family}".encode()
        ).hexdigest()
        census.append(
            {
                "schema": "gis_recommend.qgis_api_terminal_macro_semantic_rollup.v1",
                "terminal_macro_rule_id": RULE_ID,
                "family_id": family_id,
                "semantic_family": family,
                "unit_count": len(members),
                "source_sha_support": len(source_shas),
                "exact_signature_count": len({_signature_key(row) for row in members}),
                "producer_variants": sorted(
                    {value for row in members for value in row["producer_signature"]}
                ),
                "mutation_variants": sorted(
                    {value for row in members for value in row["mutation_signature"]}
                ),
                "sink_variants": sorted({str(row["sink_signature"]) for row in members}),
                "completed_semantic_overlap": completed_overlap,
                "review_priority": review_priority,
                "support_basis": "source_sha_discovery_only_not_normalized_body_authority",
                "training_admission": "not_granted_terminal_macro_census_only",
                "training_rows_emitted": 0,
            }
        )
        if review_priority == "source_replay_required":
            priority.extend(
                {**row, "semantic_family": family, "semantic_family_id": family_id}
                for row in members
            )
    census.sort(
        key=lambda row: (
            row["review_priority"] != "source_replay_required",
            -int(row["source_sha_support"]),
            str(row["semantic_family"]),
        )
    )
    priority.sort(
        key=lambda row: (str(row["semantic_family"]), str(row["unit_id"]))
    )
    return census, priority


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)


def _write_json(path: Path, value: Any) -> None:
    _atomic_write(
        path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    _atomic_write(
        path,
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-steps", type=Path, required=True)
    parser.add_argument("--exclude-jsonl", type=Path, action="append", default=[])
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-source-rows", type=int, default=39386)
    parser.add_argument("--expected-pattern-candidates", type=int, default=13554)
    parser.add_argument("--maximum-lines", type=int, default=80)
    parser.add_argument("--maximum-steps", type=int, default=16)
    parser.add_argument("--minimum-support", type=int, default=30)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    rows = _read_jsonl(args.api_steps)
    if len(rows) != args.expected_source_rows:
        raise ValueError("API step source row count mismatch")
    pattern_candidates = [row for row in rows if row.get("status") == "pattern_candidate"]
    if len(pattern_candidates) != args.expected_pattern_candidates:
        raise ValueError("pattern candidate count mismatch")
    excluded_source_shas = {
        str(row.get("source_sha256") or "")
        for path in args.exclude_jsonl
        for row in _read_jsonl(path)
        if row.get("source_sha256")
    }
    remaining = [
        row
        for row in pattern_candidates
        if str(row.get("source_sha256") or "") not in excluded_source_shas
    ]
    units = [
        unit
        for row in remaining
        for unit in build_terminal_units(
            row, maximum_lines=args.maximum_lines, maximum_steps=args.maximum_steps
        )
    ]
    families, priority, summary = build_family_census(
        units, minimum_support=args.minimum_support
    )
    semantic_rollups, semantic_priority = build_semantic_rollup_census(
        units, minimum_support=args.minimum_support
    )
    summary.update(
        {
            "input_source_rows": len(rows),
            "input_pattern_candidates": len(pattern_candidates),
            "excluded_source_sha_count": len(excluded_source_shas),
            "remaining_pattern_candidates": len(remaining),
            "maximum_lines": args.maximum_lines,
            "maximum_steps": args.maximum_steps,
            "semantic_rollup_count": len(semantic_rollups),
            "semantic_priority_family_count": sum(
                row["review_priority"] == "source_replay_required"
                for row in semantic_rollups
            ),
            "semantic_priority_units": len(semantic_priority),
        }
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "terminal_macro_units_v1.jsonl": units,
        "family_census_v1.jsonl": families,
        "priority_candidate_units_v1.jsonl": priority,
        "semantic_rollup_census_v1.jsonl": semantic_rollups,
        "semantic_priority_units_v1.jsonl": semantic_priority,
    }
    paths: list[Path] = []
    for name, output_rows in outputs.items():
        path = args.output_dir / name
        _write_jsonl(path, output_rows)
        paths.append(path)
    summary_path = args.output_dir / "summary_v1.json"
    _write_json(summary_path, summary)
    paths.append(summary_path)
    inputs = [args.api_steps, *args.exclude_jsonl]
    _write_json(
        args.output_dir / "hash_ledger_v1.json",
        {
            "schema": "gis_recommend.hash_ledger.v1",
            "inputs": {
                str(index): {"path": str(path), "sha256": _sha256(path)}
                for index, path in enumerate(inputs)
            },
            "artifacts": {
                path.name: {"bytes": path.stat().st_size, "sha256": _sha256(path)}
                for path in paths
            },
        },
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
