#!/usr/bin/env python3
"""Build fail-closed geometry-return alias candidates from verified slices."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


EXACT_METHODS = {"buffer", "centroid", "convexhull", "simplify"}
DOWNSTREAM_GEOMETRY_TRANSFORMS = {
    "aswkb",
    "aswkt",
    "cascaded_union",
    "difference",
    "fromwkb",
    "fromwkt",
    "unaryunion",
}
RULE_ID = "verified-setgeometry-backward-slice-exact-method-v2"


def _method(call_name: str) -> str:
    return call_name.rsplit(".", 1)[-1]


def _downstream_geometry_transform_calls(
    exact_call: dict[str, Any], upstream_calls: list[dict[str, Any]]
) -> list[str]:
    exact_line = int(exact_call["line_start"])
    return [
        str(call["call_name"])
        for call in upstream_calls
        if int(call["line_start"]) >= exact_line
        and _method(str(call["call_name"])).lower()
        in DOWNSTREAM_GEOMETRY_TRANSFORMS
    ]


def _annotate_sidecar(row: dict[str, Any], status: str) -> dict[str, Any]:
    return {
        **row,
        "schema": "gis_recommend.qgis_api_geometry_return_alias_sidecar.v1",
        "geometry_return_rule_id": RULE_ID,
        "alias_candidate_status": status,
        "candidate_l3_sequence": [],
        "training_admission": "not_granted_geometry_return_alias_sidecar",
        "training_row_emitted": False,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }


def _candidate(row: dict[str, Any], exact_call: dict[str, Any]) -> dict[str, Any]:
    semantic_step = {
        "step_index": 0,
        "call_name": str(exact_call["call_name"]),
        "call_role": "geometry_transform",
        "pattern_family": "feature_geometry",
        "line_start": int(exact_call["line_start"]),
        "line_end": int(exact_call["line_end"]),
        "lexical_scope": str(row.get("lexical_scope") or ""),
        "receiver": str(exact_call["call_name"]).rsplit(".", 1)[0],
        "assignment_targets": [],
        "consumed_names": [],
        "produced_names": ["<setgeometry_payload_alias>"],
        "terminal_evidence": False,
        "control_path": [],
        "recovery_evidence": "verified_same_scope_backward_slice",
    }
    shifted_steps = [
        {**step, "step_index": index}
        for index, step in enumerate(row.get("steps") or [], start=1)
    ]
    setgeometry_indexes = [
        index
        for index, step in enumerate(shifted_steps, start=1)
        if step.get("call_role") == "feature_mutation"
        and str(step.get("call_name") or "").lower().endswith(".setgeometry")
    ]
    if len(setgeometry_indexes) != 1:
        raise ValueError("resolved alias candidate must contain one setGeometry step")
    edges = sorted(
        [
            [int(source) + 1, int(target) + 1]
            for source, target in row.get("dependency_edges") or []
        ]
        + [[0, setgeometry_indexes[0]]]
    )
    steps = [semantic_step, *shifted_steps]
    payload = {
        "baseline_candidate_id": str(row["candidate_id"]),
        "semantic_call": str(exact_call["call_name"]),
        "semantic_line": int(exact_call["line_start"]),
        "edges": edges,
    }
    unit_id = hashlib.sha256(
        json.dumps(payload, sort_keys=True).encode("utf-8")
    ).hexdigest()
    return {
        **row,
        "schema": "gis_recommend.qgis_api_geometry_return_alias_candidate.v1",
        "baseline_candidate_id": str(row["candidate_id"]),
        "candidate_id": hashlib.sha256(
            f"{row['candidate_id']}|{unit_id}".encode("utf-8")
        ).hexdigest(),
        "unit_id": unit_id,
        "geometry_return_rule_id": RULE_ID,
        "alias_candidate_status": "resolved_exact_geometry_return_alias",
        "recovery_method": "verified_same_scope_backward_slice",
        "semantic_calls": [str(exact_call["call_name"])],
        "steps": steps,
        "dependency_edges": edges,
        "source_span": [
            min(int(step["line_start"]) for step in steps),
            max(int(step["line_end"]) for step in steps),
        ],
        "pattern_names": sorted(
            {
                str(step.get("pattern_family") or "")
                for step in steps
                if step.get("pattern_family")
            }
        ),
        "candidate_l3_sequence": [],
        "description_fidelity": "not_started",
        "deduplication": "not_started",
        "training_admission": "not_granted_geometry_return_alias_candidate",
        "training_row_emitted": False,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }


def build_candidates(
    rows: list[dict[str, Any]],
    *,
    excluded_candidate_ids: set[str] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    excluded_ids = set(excluded_candidate_ids or set())
    candidates: list[dict[str, Any]] = []
    sidecar: list[dict[str, Any]] = []
    broad_rows = []
    excluded_broad_rows = 0
    method_authorities: dict[str, set[str]] = defaultdict(set)
    method_units: Counter[str] = Counter()
    for row in rows:
        if row.get("training_row_emitted") is not False:
            raise ValueError("upstream census input must emit zero training rows")
        upstream_calls = list(row.get("upstream_calls") or [])
        exact_calls = [
            call
            for call in upstream_calls
            if _method(str(call.get("call_name") or "")).lower() in EXACT_METHODS
        ]
        if not exact_calls:
            continue
        if str(row.get("candidate_id") or "") in excluded_ids:
            excluded_broad_rows += 1
            continue
        broad_rows.append(row)
        methods = {
            _method(str(call["call_name"])) for call in exact_calls
        }
        for method in methods:
            method_units[method] += 1
            method_authorities[method].add(str(row["source_authority_key"]))
        if row.get("slice_status") != "resolved_local_call_chain":
            sidecar.append(
                _annotate_sidecar(
                    row, "deferred_ambiguous_reaching_definitions"
                )
            )
        elif len(exact_calls) != 1:
            sidecar.append(
                _annotate_sidecar(row, "deferred_non_unique_exact_method")
            )
        else:
            downstream_transforms = _downstream_geometry_transform_calls(
                exact_calls[0], upstream_calls
            )
            if downstream_transforms:
                sidecar.append(
                    {
                        **_annotate_sidecar(
                            row, "deferred_downstream_geometry_transform"
                        ),
                        "downstream_geometry_transform_calls": downstream_transforms,
                    }
                )
            else:
                candidates.append(_candidate(row, exact_calls[0]))
    summary = {
        "schema": "gis_recommend.qgis_api_geometry_return_alias_candidate_summary.v1",
        "geometry_return_rule_id": RULE_ID,
        "input_units": len(rows),
        "excluded_previously_reviewed_units": excluded_broad_rows,
        "broad_candidate_units": len(broad_rows),
        "broad_candidate_authorities": len(
            {str(row["source_authority_key"]) for row in broad_rows}
        ),
        "resolved_candidate_units": len(candidates),
        "resolved_candidate_authorities": len(
            {str(row["source_authority_key"]) for row in candidates}
        ),
        "ambiguous_candidate_units": len(sidecar),
        "method_unit_counts": dict(sorted(method_units.items())),
        "method_authority_counts": {
            method: len(authorities)
            for method, authorities in sorted(method_authorities.items())
        },
        "mapping_rows_emitted": 0,
        "description_fidelity_rows": 0,
        "training_rows_emitted": 0,
        "training_admission": "not_granted_geometry_return_alias_candidate_only",
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
    parser.add_argument("--mutation-upstream", type=Path, required=True)
    parser.add_argument("--exclude-reviewed", type=Path, action="append", default=[])
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-rows", type=int, default=2605)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    rows = _read_jsonl(args.mutation_upstream)
    if len(rows) != args.expected_rows:
        raise ValueError(f"input rows {len(rows)} != expected {args.expected_rows}")
    excluded_candidate_ids = {
        str(row.get("baseline_candidate_id") or row.get("candidate_id") or "")
        for path in args.exclude_reviewed
        for row in _read_jsonl(path)
    }
    if "" in excluded_candidate_ids:
        raise ValueError("review exclusion row lacks candidate identity")
    candidates, sidecar, summary = build_candidates(
        rows, excluded_candidate_ids=excluded_candidate_ids
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    candidate_path = args.output_dir / "geometry_return_alias_candidates_v1.jsonl"
    sidecar_path = args.output_dir / "geometry_return_alias_sidecar_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    _write_jsonl(candidate_path, candidates)
    _write_jsonl(sidecar_path, sidecar)
    _atomic_write(
        summary_path,
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    artifacts = (candidate_path, sidecar_path, summary_path)
    ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "inputs": {
            "mutation_upstream": {
                "path": str(args.mutation_upstream),
                "sha256": _sha256(args.mutation_upstream),
            },
            **{
                f"exclude_reviewed_{index}": {
                    "path": str(path),
                    "sha256": _sha256(path),
                }
                for index, path in enumerate(args.exclude_reviewed)
            },
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
