#!/usr/bin/env python3
"""Compact ordered QGIS evidence and build a deterministic coverage pilot."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gis_recommend.data.qgis_pilot import (  # noqa: E402
    PILOT_SCHEMA,
    assert_write_allowed,
    build_coverage_diagnostic_sample,
    compact_api_trace,
    coverage_diagnostic_stratum,
    file_sha256,
)


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_bytes((json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _evidence_source_mode(row: Mapping[str, Any], compact: Mapping[str, Any]) -> str:
    channels = []
    if row.get("processing_algorithms"):
        channels.append("processing")
    if row.get("direct_api"):
        channels.append("direct_api")
    if row.get("custom_algorithms"):
        channels.append("custom")
    if not channels:
        categories = {step.get("category") for step in compact.get("compact_steps", [])}
        if "processing_operator" in categories:
            channels.append("processing")
        if categories.intersection({"semantic_anchor", "data_access", "unknown"}):
            channels.append("direct_api")
    return "+".join(channels) + "_only" if len(channels) == 1 else "+".join(channels) or "unknown"


def _modality_hint(compact: Mapping[str, Any]) -> str:
    vector = False
    raster = False
    vector_families = {
        "buffer",
        "difference",
        "geometry_validation",
        "intersection",
        "simplify",
        "spatial_index",
        "union",
        "vector_export",
    }
    raster_families = {"raster_calculation"}
    for step in compact.get("compact_steps", []):
        operation = str(step.get("operation") or "").lower()
        family = str(step.get("semantic_family") or "")
        l3_code = str(step.get("l3_code") or family)
        vector = vector or family in vector_families or any(
            marker in operation for marker in ("qgsfeature", "qgsgeometry", "qgsvector", "vector")
        )
        raster = raster or family in raster_families or "qgsraster" in operation or "raster" in operation
        if l3_code.startswith("L3_02_"):
            vector = True
        if l3_code.startswith(("L3_03_", "L3_04_")):
            raster = True
        if l3_code in {"L3_01_09_06", "L3_01_09_07"}:
            vector = True
            raster = True
    if vector and raster:
        return "mixed"
    if vector:
        return "vector"
    if raster:
        return "raster"
    return "unknown"


def _trace_length_bucket(source_step_count: int) -> str:
    if source_step_count <= 10:
        return "short"
    if source_step_count <= 50:
        return "medium"
    return "long"


def _compact_record(row: Mapping[str, Any]) -> dict[str, Any] | None:
    if row.get("evidence_tier") == "T0" or row.get("collision_state") == "unresolved_collision":
        return None
    compact = compact_api_trace(row.get("ordered_steps", []))
    if not compact["eligible_for_llm"]:
        return None
    families = compact["semantic_anchor_families"]
    existing_chain = list(row.get("mapped_l3_chain", []))
    primary_family = (
        families[0]
        if families
        else existing_chain[0]
        if existing_chain
        else "explicit_processing"
    )
    source_step_count = int(compact.get("source_step_count") or 0)
    return {
        "schema": PILOT_SCHEMA,
        "kind": "qgis_api_aggregation_candidate_v1",
        "record_id": row.get("record_id"),
        "facts_row_id": row.get("facts_row_id"),
        "script_id": row.get("script_id"),
        "source_script": row.get("source_script"),
        "extraction_group": row.get("extraction_group"),
        "source_aliases": row.get("source_aliases", []),
        "artifact_hashes": row.get("artifact_hashes", {}),
        "collision_state": row.get("collision_state"),
        "evidence_tier": row.get("evidence_tier"),
        "task_type": row.get("task_type"),
        "task_name": row.get("task_name"),
        "task_description": row.get("task_description"),
        "existing_mapped_l3_chain": existing_chain,
        "primary_semantic_family": primary_family,
        "evidence_source_mode": _evidence_source_mode(row, compact),
        "modality_hint": _modality_hint(compact),
        "trace_length_bucket": _trace_length_bucket(source_step_count),
        **compact,
    }


def build_pilot(
    *,
    ordered_evidence: Path,
    output_dir: Path,
    allowed_write_roots: list[Path],
    sample_size: int = 300,
    seed: int = 11420260714,
) -> dict[str, Any]:
    output_dir = assert_write_allowed(output_dir, allowed_write_roots)
    output_dir.mkdir(parents=True, exist_ok=True)
    source_records = 0
    excluded_t0 = 0
    excluded_no_semantic_anchor = 0
    eligible = []
    source_digest = hashlib.sha256()
    with ordered_evidence.open("rb") as handle:
        for raw_line in handle:
            source_digest.update(raw_line)
            if not raw_line.strip():
                continue
            source_records += 1
            row = json.loads(raw_line.decode("utf-8"))
            if row.get("evidence_tier") == "T0" or row.get("collision_state") == "unresolved_collision":
                excluded_t0 += 1
                continue
            compact = _compact_record(row)
            if compact is None:
                excluded_no_semantic_anchor += 1
                continue
            eligible.append(compact)
    pilot = build_coverage_diagnostic_sample(eligible, size=sample_size, seed=seed)
    pool_path = output_dir / "eligible_compact_pool.jsonl"
    pilot_path = output_dir / "pilot_coverage_300.jsonl"
    csv_path = output_dir / "pilot_coverage_300.csv"
    summary_path = output_dir / "pilot_summary.json"
    ledger_path = output_dir / "write_ledger.json"
    _write_jsonl(pool_path, sorted(eligible, key=lambda row: str(row.get("record_id"))))
    _write_jsonl(pilot_path, pilot)
    with csv_path.open("w", encoding="utf-8-sig", newline="") as handle:
        fields = [
            "record_id",
            "extraction_group",
            "evidence_source_mode",
            "modality_hint",
            "trace_length_bucket",
            "evidence_tier",
            "ordering_quality",
            "primary_semantic_family",
            "task_name",
            "task_description",
            "existing_mapped_l3_chain",
            "semantic_anchor_families",
            "compact_step_count",
        ]
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in pilot:
            writer.writerow(
                {
                    **{field: row.get(field) for field in fields},
                    "existing_mapped_l3_chain": json.dumps(row.get("existing_mapped_l3_chain", [])),
                    "semantic_anchor_families": json.dumps(row.get("semantic_anchor_families", [])),
                    "compact_step_count": len(row.get("compact_steps", [])),
                }
            )
    stratum_counts = Counter(coverage_diagnostic_stratum(row) for row in pilot)
    summary = {
        "schema": PILOT_SCHEMA,
        "kind": "qgis_api_aggregation_pilot_summary_v1",
        "input": {
            "path": str(ordered_evidence.resolve()),
            "sha256": source_digest.hexdigest(),
        },
        "seed": seed,
        "requested_pilot_records": sample_size,
        "source_records": source_records,
        "eligible_records": len(eligible),
        "pilot_records": len(pilot),
        "shortfall": max(0, sample_size - len(pilot)),
        "excluded": {
            "t0_or_collision": excluded_t0,
            "no_processing_or_semantic_anchor": excluded_no_semantic_anchor,
        },
        "ordering_quality": dict(sorted(Counter(row["ordering_quality"] for row in pilot).items())),
        "evidence_source_modes": dict(
            sorted(Counter(row["evidence_source_mode"] for row in pilot).items())
        ),
        "modality_hints": dict(sorted(Counter(row["modality_hint"] for row in pilot).items())),
        "trace_length_buckets": dict(
            sorted(Counter(row["trace_length_bucket"] for row in pilot).items())
        ),
        "semantic_families": dict(sorted(Counter(row["primary_semantic_family"] for row in pilot).items())),
        "strata": [
            {
                "extraction_group": key[0],
                "evidence_source_mode": key[1],
                "modality_hint": key[2],
                "trace_length_bucket": key[3],
                "primary_semantic_family": key[4],
                "ordering_quality": key[5],
                "records": count,
            }
            for key, count in sorted(stratum_counts.items())
        ],
        "metric_policy": "coverage_diagnostic_not_accuracy_reference",
    }
    _write_json(summary_path, summary)
    _write_json(
        ledger_path,
        {
            "schema": PILOT_SCHEMA,
            "allowed_write_roots": [str(Path(root).resolve()) for root in allowed_write_roots],
            "created_or_replaced": [
                {"path": str(path), "sha256": file_sha256(path), "size": path.stat().st_size}
                for path in (pool_path, pilot_path, csv_path, summary_path)
            ],
        },
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ordered-evidence", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--allowed-write-root", type=Path, action="append", required=True)
    parser.add_argument("--sample-size", type=int, default=300)
    parser.add_argument("--seed", type=int, default=11420260714)
    args = parser.parse_args(argv)
    summary = build_pilot(
        ordered_evidence=args.ordered_evidence,
        output_dir=args.output_dir,
        allowed_write_roots=args.allowed_write_root,
        sample_size=args.sample_size,
        seed=args.seed,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
