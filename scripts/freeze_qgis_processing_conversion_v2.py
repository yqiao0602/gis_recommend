#!/usr/bin/env python3
"""Freeze the authority inputs for Processing conversion driver v2."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections.abc import Iterable
from pathlib import Path
from typing import Any

SCHEMA = "gis_recommend.qgis_processing_conversion_freeze.v2"
DEDUPE_FIELDS = (
    "source_region_key",
    "call_graph_key",
    "normalized_dag_key",
    "unified_training_pair_key",
)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _normalized_text(value: Any) -> str:
    return "".join(str(value or "").lower().split())


def _training_pair_key(row: dict[str, Any]) -> str:
    # Authority derivation: scripts.run_qgis_processing_batch._training_pair_key.
    # The authority dedup driver always derives the training-pair key (it has no
    # explicit branch), so the frozen baseline must use the same derivation or
    # candidate-vs-baseline comparison drifts apart.  The frozen explicit value
    # stays on the row for audit only (dedupe_key_provenance).
    payload = {
        "task_name": _normalized_text(row.get("task_name")),
        "task_description": _normalized_text(row.get("task_description")),
        "operator_sequence": [
            str(value)
            for value in (
                row.get("operator_sequence")
                or row.get("operator_ids")
                or row.get("ordered_operator_ids")
                or row.get("canonical_operator_ids")
                or []
            )
        ],
        "l3_code_sequence": list(row.get("l3_code_sequence") or []),
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _derived_structural_key(row: dict[str, Any], field: str) -> str:
    call_sites = (row.get("source_span") or {}).get("call_sites") or row.get("call_sites") or []
    common = {
        "source_sha256": str(row.get("source_sha256") or ""),
        "call_sites": call_sites,
        "workflow_scope": str(row.get("workflow_scope") or ""),
    }
    if field == "source_region_key":
        payload = common
    elif field == "call_graph_key":
        payload = {
            **common,
            "operator_sequence": list(row.get("operator_sequence") or []),
            "dependency_edges": list(row.get("dependency_edges") or []),
        }
    else:
        raise ValueError(f"unsupported structural key: {field}")
    if not common["source_sha256"] or not call_sites:
        raise ValueError(f"cannot derive {field} without source-backed call sites")
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _dedupe_key_value(row: dict[str, Any], field: str) -> tuple[str, str]:
    if field == "unified_training_pair_key":
        return _training_pair_key(row), "explicit_or_deterministic_training_pair"
    explicit = str(row.get(field) or "")
    if explicit:
        return explicit, "explicit"
    if field in {"source_region_key", "call_graph_key"}:
        return _derived_structural_key(row, field), "derived_from_source_facts"
    return "", "missing"


def _require_unique(rows: Iterable[dict[str, Any]], field: str, label: str) -> None:
    values = [str(row.get(field) or "") for row in rows]
    if not values or any(not value for value in values) or len(values) != len(set(values)):
        raise ValueError(f"{label} must have unique non-empty {field}")


def _unit_reference_key(row: dict[str, Any]) -> str:
    identity = {
        "source_sha256": str(row.get("source_sha256") or ""),
        "source_region_key": _dedupe_key_value(row, "source_region_key")[0],
        "call_graph_key": _dedupe_key_value(row, "call_graph_key")[0],
        "normalized_dag_key": str(row.get("normalized_dag_key") or ""),
        "training_pair_key": _training_pair_key(row),
    }
    if any(not value for value in identity.values()):
        raise ValueError("baseline unit is missing a four-layer identity component")
    return hashlib.sha256(
        json.dumps(identity, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def build_cross_pool_baseline(
    processing_rows: list[dict[str, Any]], qgis_rows: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    """Merge references by unit identity while retaining both source pools.

    A source region is not sufficient identity: one source can contain more
    than one admitted local unit.  The stable reference key therefore combines
    source identity with all four dedup dimensions.  Nested sets still preserve
    every individual key for later layer-by-layer suppression.
    """

    grouped: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for pool, rows in (("processing_294", processing_rows), ("qgis_507", qgis_rows)):
        for row in rows:
            grouped.setdefault(_unit_reference_key(row), []).append((pool, row))

    merged: list[dict[str, Any]] = []
    for unit_key, members in sorted(grouped.items()):
        pools = sorted({pool for pool, _ in members})
        key_values = {
            field: sorted(
                {
                    _dedupe_key_value(row, field)[0]
                    for _, row in members
                    if _dedupe_key_value(row, field)[0]
                }
            )
            for field in DEDUPE_FIELDS
        }
        if any(not values for values in key_values.values()):
            raise ValueError(f"baseline unit missing dedup key: {unit_key}")
        merged.append(
            {
                "schema": "gis_recommend.qgis_processing_cross_pool_baseline.v2",
                "unit_reference_key": unit_key,
                "reference_pools": pools,
                "reference_members": [
                    {
                        "pool": pool,
                        "sample_id": str(row.get("sample_id") or ""),
                        "record_id": str(row.get("record_id") or ""),
                        "source_sha256": str(row.get("source_sha256") or ""),
                    }
                    for pool, row in sorted(members, key=lambda item: item[0])
                ],
                "dedupe_key_provenance": {
                    field: sorted(
                        {
                            _dedupe_key_value(row, field)[1]
                            for _, row in members
                        }
                    )
                    for field in DEDUPE_FIELDS
                },
                "dedupe_key_values": key_values,
            }
        )
    return merged


def freeze_authorities(
    source_rows: list[dict[str, Any]],
    processing_rows: list[dict[str, Any]],
    qgis_rows: list[dict[str, Any]],
    *,
    expected_source_rows: int = 8466,
    expected_processing_rows: int = 294,
    expected_qgis_rows: int = 507,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if len(source_rows) != expected_source_rows:
        raise ValueError(f"source rows {len(source_rows)} != {expected_source_rows}")
    _require_unique(source_rows, "source_sha256", "source authority")
    _require_unique(source_rows, "record_id", "source authority")
    if len(processing_rows) != expected_processing_rows:
        raise ValueError(
            f"processing baseline rows {len(processing_rows)} != {expected_processing_rows}"
        )
    if len(qgis_rows) != expected_qgis_rows:
        raise ValueError(f"QGIS baseline rows {len(qgis_rows)} != {expected_qgis_rows}")
    baseline = build_cross_pool_baseline(processing_rows, qgis_rows)
    summary = {
        "schema": SCHEMA,
        "source_authority_rows": len(source_rows),
        "source_authority_unique_sha256": len({row["source_sha256"] for row in source_rows}),
        "processing_unit_baseline_rows": len(processing_rows),
        "qgis_unit_baseline_rows": len(qgis_rows),
        "cross_pool_baseline_unique_units": len(baseline),
        "cross_pool_overlap_units": sum(
            len(row["reference_pools"]) == 2 for row in baseline
        ),
        "source_scan_policy": "all_8466_no_source_level_exclusion",
        "unit_dedup_policy": "cross_pool_baseline_then_candidate_internal",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }
    return baseline, summary


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    content = "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for row in rows
    )
    _atomic_write(path, content)


def _write_json(path: Path, value: dict[str, Any]) -> None:
    _atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-manifest", type=Path, required=True)
    parser.add_argument("--processing-baseline", type=Path, required=True)
    parser.add_argument("--qgis-baseline", type=Path, required=True)
    parser.add_argument("--mapping-input", type=Path, action="append", required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-source-rows", type=int, default=8466)
    parser.add_argument("--expected-processing-rows", type=int, default=294)
    parser.add_argument("--expected-qgis-rows", type=int, default=507)
    args = parser.parse_args(argv)
    inputs = [
        args.source_manifest,
        args.processing_baseline,
        args.qgis_baseline,
        *args.mapping_input,
        args.catalog,
    ]
    missing = [str(path) for path in inputs if not path.is_file()]
    if missing:
        raise ValueError(f"missing freeze input: {missing}")
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")

    baseline, summary = freeze_authorities(
        _read_jsonl(args.source_manifest),
        _read_jsonl(args.processing_baseline),
        _read_jsonl(args.qgis_baseline),
        expected_source_rows=args.expected_source_rows,
        expected_processing_rows=args.expected_processing_rows,
        expected_qgis_rows=args.expected_qgis_rows,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    baseline_path = args.output_dir / "cross_pool_baseline_v2.jsonl"
    summary_path = args.output_dir / "summary_v2.json"
    _write_jsonl(baseline_path, baseline)
    _write_json(summary_path, summary)
    _write_json(
        args.output_dir / "hash_ledger_v2.json",
        {
            "schema": "gis_recommend.hash_ledger.v1",
            "inputs": {
                str(index): {"path": str(path), "sha256": _sha256(path)}
                for index, path in enumerate(inputs)
            },
            "artifacts": {
                baseline_path.name: _sha256(baseline_path),
                summary_path.name: _sha256(summary_path),
            },
        },
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
