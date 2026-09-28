#!/usr/bin/env python3
"""Extract auditable terminal-DAG deltas between QGIS API boundary replays."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any, Iterable


def _method(call_name: str) -> str:
    return call_name.lower().rsplit(".", 1)[-1]


def _terminal_identity(row: dict[str, Any]) -> tuple[Any, ...]:
    terminals = tuple(
        sorted(
            (
                str(step.get("call_name") or ""),
                int(step.get("line_start") or 0),
                int(step.get("line_end") or 0),
                str(step.get("receiver") or ""),
            )
            for step in row.get("steps") or []
            if step.get("terminal_evidence")
        )
    )
    if not terminals:
        raise ValueError("candidate unit lacks terminal identity")
    return (
        str(row.get("record_id") or ""),
        str(row.get("lexical_scope") or ""),
        terminals,
    )


def _index_by_terminal(rows: Iterable[dict[str, Any]]) -> dict[tuple[Any, ...], dict[str, Any]]:
    indexed: dict[tuple[Any, ...], dict[str, Any]] = {}
    for row in rows:
        key = _terminal_identity(row)
        if key in indexed:
            raise ValueError(f"duplicate terminal identity: {key}")
        indexed[key] = row
    return indexed


def _direct_semantic_output(row: dict[str, Any], methods: set[str]) -> bool:
    steps = list(row.get("steps") or [])
    edges = {tuple(edge) for edge in row.get("dependency_edges") or []}
    semantic = {
        index
        for index, step in enumerate(steps)
        if step.get("call_role") in {"geometry_transform", "crs_transform"}
        and _method(str(step.get("call_name") or "")) in methods
    }
    mutations = {
        index
        for index, step in enumerate(steps)
        if step.get("call_role") == "feature_mutation"
        and _method(str(step.get("call_name") or "")) == "setgeometry"
    }
    terminals = {
        index for index, step in enumerate(steps) if step.get("terminal_evidence")
    }
    successors: dict[int, set[int]] = {}
    for source, target in edges:
        successors.setdefault(source, set()).add(target)

    def reaches_terminal(mutation: int) -> bool:
        receiver = str(steps[mutation].get("receiver") or "")
        pending = list(successors.get(mutation, set()))
        visited: set[int] = set()
        while pending:
            current = pending.pop()
            if current in visited:
                continue
            visited.add(current)
            if current in terminals:
                return True
            step = steps[current]
            if (
                step.get("call_role") not in {"feature_mutation", "attribute_mutation"}
                or str(step.get("receiver") or "") != receiver
            ):
                continue
            pending.extend(successors.get(current, set()))
        return False

    return any(
        (source, mutation) in edges and reaches_terminal(mutation)
        for source in semantic
        for mutation in mutations
    )


def extract_delta_units(
    baseline_rows: list[dict[str, Any]],
    current_rows: list[dict[str, Any]],
    *,
    semantic_methods: set[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    allowed = {method.lower() for method in semantic_methods}
    if not allowed:
        raise ValueError("semantic_methods must not be empty")
    baseline = _index_by_terminal(baseline_rows)
    current = _index_by_terminal(current_rows)
    selected = []
    sidecar = []
    changed = 0
    for key in sorted(baseline.keys() & current.keys()):
        old = baseline[key]
        new = current[key]
        if str(old.get("unit_id") or "") == str(new.get("unit_id") or ""):
            continue
        changed += 1
        direct = _direct_semantic_output(new, allowed)
        annotated = {
            **new,
            "baseline_candidate_id": str(old.get("candidate_id") or ""),
            "baseline_unit_id": str(old.get("unit_id") or ""),
            "boundary_delta_status": (
                "calibration_candidate" if direct else "changed_not_selected"
            ),
            "boundary_delta_rule": "direct-semantic-setgeometry-sink-v1",
            "semantic_method_allowlist": sorted(allowed),
            "candidate_l3_sequence": [],
            "training_admission": "not_granted_boundary_delta_only",
            "training_row_emitted": False,
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
        }
        (selected if direct else sidecar).append(annotated)
    summary = {
        "schema": "gis_recommend.qgis_api_boundary_delta_summary.v1",
        "baseline_units": len(baseline_rows),
        "current_units": len(current_rows),
        "shared_terminal_units": len(baseline.keys() & current.keys()),
        "removed_terminal_units": len(baseline.keys() - current.keys()),
        "added_terminal_units": len(current.keys() - baseline.keys()),
        "changed_terminal_units": changed,
        "delta_units": len(selected),
        "delta_authorities": len(
            {str(row.get("source_authority_key") or "") for row in selected}
        ),
        "changed_not_selected": len(sidecar),
        "semantic_method_allowlist": sorted(allowed),
        "training_rows_emitted": 0,
        "training_admission": "not_granted_boundary_delta_only",
    }
    return selected, sidecar, summary


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


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


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--current", type=Path, required=True)
    parser.add_argument("--semantic-method", action="append", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    selected, sidecar, summary = extract_delta_units(
        _read_jsonl(args.baseline),
        _read_jsonl(args.current),
        semantic_methods=set(args.semantic_method),
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    selected_path = args.output_dir / "boundary_delta_candidates_v1.jsonl"
    sidecar_path = args.output_dir / "boundary_delta_sidecar_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    _write_jsonl(selected_path, selected)
    _write_jsonl(sidecar_path, sidecar)
    _atomic_write(
        summary_path,
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    artifacts = (selected_path, sidecar_path, summary_path)
    ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "inputs": {
            "baseline": {"path": str(args.baseline), "sha256": _sha256(args.baseline)},
            "current": {"path": str(args.current), "sha256": _sha256(args.current)},
        },
        "artifacts": {
            path.name: {"bytes": path.stat().st_size, "sha256": _sha256(path)}
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
