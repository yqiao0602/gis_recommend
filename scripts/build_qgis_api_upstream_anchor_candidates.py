#!/usr/bin/env python3
"""Resolve calibrated QGIS upstream anchors into candidates or sidecars."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any, Iterable

from scripts.build_qgis_api_geometry_return_alias_candidates import (
    _candidate as _build_exact_return_candidate,
)


RULE_ID = "calibrated-upstream-anchor-resolution-v1"
DOWNSTREAM_UNARY_UNION_TRANSFORMS = {"asgeometrycollection", "polygonize"}


def _method(call_name: str) -> str:
    return call_name.rsplit(".", 1)[-1].lower()


def _downstream_transforms(
    exact_call: dict[str, Any], upstream_calls: list[dict[str, Any]]
) -> list[str]:
    exact_line = int(exact_call["line_start"])
    return [
        str(call["call_name"])
        for call in upstream_calls
        if int(call["line_start"]) >= exact_line
        and _method(str(call["call_name"])) in DOWNSTREAM_UNARY_UNION_TRANSFORMS
    ]


def _sidecar(row: dict[str, Any], status: str) -> dict[str, Any]:
    return {
        **row,
        "schema": "gis_recommend.qgis_api_upstream_anchor_sidecar.v1",
        "anchor_resolution_rule_id": RULE_ID,
        "anchor_candidate_status": status,
        "candidate_l3_sequence": [],
        "mapping_admission": "not_granted_anchor_sidecar",
        "description_fidelity": "not_started",
        "deduplication": "not_started",
        "training_admission": "not_granted_anchor_sidecar",
        "training_row_emitted": False,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }


def _unary_union_candidate(
    row: dict[str, Any], exact_call: dict[str, Any]
) -> dict[str, Any]:
    candidate = _build_exact_return_candidate(row, exact_call)
    candidate.pop("geometry_return_rule_id", None)
    candidate.pop("alias_candidate_status", None)
    candidate.update(
        {
            "schema": "gis_recommend.qgis_api_unary_union_candidate.v1",
            "anchor_resolution_rule_id": RULE_ID,
            "anchor_candidate_status": "resolved_unary_union_local_subworkflow",
            "training_admission": "not_granted_unary_union_candidate",
        }
    )
    return candidate


def build_candidates(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    candidates = []
    sidecar = []
    random_deferred = 0
    unary_deferred = 0
    for row in rows:
        if row.get("training_row_emitted") is not False:
            raise ValueError("anchor candidate input must emit zero training rows")
        anchors = set(row.get("semantic_anchor_families") or [])
        if "random_point_construction" in anchors:
            sidecar.append(
                _sidecar(
                    row,
                    "deferred_control_dependencies_outside_backward_slice",
                )
            )
            random_deferred += 1
            continue
        if "unary_union" not in anchors:
            sidecar.append(_sidecar(row, "deferred_unsupported_anchor_family"))
            continue
        exact_calls = [
            call
            for call in row.get("upstream_calls") or []
            if str(call.get("call_name") or "").lower()
            == "qgsgeometry.unaryunion"
        ]
        if len(exact_calls) != 1:
            sidecar.append(
                _sidecar(row, "deferred_non_unique_unary_union_call")
            )
            unary_deferred += 1
            continue
        downstream_transforms = _downstream_transforms(
            exact_calls[0], list(row.get("upstream_calls") or [])
        )
        if downstream_transforms:
            sidecar.append(
                {
                    **_sidecar(
                        row, "deferred_downstream_geometry_transform"
                    ),
                    "downstream_geometry_transform_calls": downstream_transforms,
                }
            )
            unary_deferred += 1
            continue
        candidates.append(_unary_union_candidate(row, exact_calls[0]))

    summary = {
        "schema": "gis_recommend.qgis_api_upstream_anchor_candidate_summary.v1",
        "anchor_resolution_rule_id": RULE_ID,
        "input_units": len(rows),
        "unary_union_candidate_units": len(candidates),
        "unary_union_source_authorities": len(
            {str(row["source_authority_key"]) for row in candidates}
        ),
        "unary_union_deferred_units": unary_deferred,
        "random_point_deferred_units": random_deferred,
        "sidecar_units": len(sidecar),
        "mapping_rows_emitted": 0,
        "description_fidelity_rows": 0,
        "training_rows_emitted": 0,
        "training_admission": "not_granted_anchor_resolution_only",
    }
    return candidates, sidecar, summary


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


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    _atomic_write(
        path,
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--anchor-candidates", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-rows", type=int, default=73)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    rows = _read_jsonl(args.anchor_candidates)
    if len(rows) != args.expected_rows:
        raise ValueError(f"input rows {len(rows)} != expected {args.expected_rows}")
    candidates, sidecar, summary = build_candidates(rows)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "unary_union_candidates_v1.jsonl": candidates,
        "anchor_sidecar_v1.jsonl": sidecar,
        "random_point_deferred_v1.jsonl": [
            row
            for row in sidecar
            if row.get("anchor_candidate_status")
            == "deferred_control_dependencies_outside_backward_slice"
        ],
    }
    artifacts = []
    for name, output_rows in outputs.items():
        path = args.output_dir / name
        _write_jsonl(path, output_rows)
        artifacts.append(path)
    summary_path = args.output_dir / "summary_v1.json"
    _atomic_write(
        summary_path,
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    artifacts.append(summary_path)
    ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "inputs": {
            "anchor_candidates": {
                "path": str(args.anchor_candidates),
                "sha256": _sha256(args.anchor_candidates),
            }
        },
        "artifacts": {
            path.name: {"sha256": _sha256(path), "bytes": path.stat().st_size}
            for path in artifacts
        },
    }
    _atomic_write(
        args.output_dir / "hash_ledger_v1.json",
        json.dumps(ledger, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
