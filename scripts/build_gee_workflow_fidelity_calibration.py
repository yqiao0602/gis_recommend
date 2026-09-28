#!/usr/bin/env python3
"""Build deterministic post-DAG GEE fidelity calibration artifacts."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
import os
from pathlib import Path
import re
import tempfile
from typing import Any, Iterable

from gis_recommend.data.gee_workflow_dag_gate import OutputWorkflowDag
from gis_recommend.data.gee_workflow_fidelity_gate import (
    WorkflowFidelityDecision,
    evaluate_workflow_fidelity,
)


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_WORKFLOW_FIELDS = frozenset(OutputWorkflowDag.__dataclass_fields__)
_WORKFLOW_STATUSES = frozenset({"passed", "fail_closed"})


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _jsonl_bytes(values: Iterable[dict[str, Any]]) -> bytes:
    return "".join(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
        for value in values
    ).encode("utf-8")


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        dir=path.parent, prefix=f".{path.name}.", delete=False
    ) as handle:
        temporary = Path(handle.name)
        handle.write(payload)
        handle.flush()
        os.fsync(handle.fileno())
    try:
        os.replace(temporary, path)
    finally:
        if temporary.exists():
            temporary.unlink()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.is_file():
        raise ValueError(f"missing workflow DAG input: {path}")
    rows: list[dict[str, Any]] = []
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not raw_line.strip():
            continue
        try:
            row = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            raise ValueError(
                f"invalid workflow DAG JSON at line {line_number}: {exc}"
            ) from exc
        if not isinstance(row, dict):
            raise ValueError(f"workflow DAG row {line_number} must be an object")
        rows.append(row)
    return rows


def _string_tuple(value: Any, field: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"workflow field {field} must be a list of strings")
    return tuple(value)


def _int_tuple(value: Any, field: str) -> tuple[int, ...]:
    if not isinstance(value, list) or not all(
        isinstance(item, int) and not isinstance(item, bool) for item in value
    ):
        raise ValueError(f"workflow field {field} must be a list of integers")
    return tuple(value)


def _edge_tuple(value: Any) -> tuple[tuple[str, str], ...]:
    if not isinstance(value, list):
        raise ValueError("workflow field dependency_edges must be a list")
    edges: list[tuple[str, str]] = []
    for edge in value:
        if (
            not isinstance(edge, (list, tuple))
            or len(edge) != 2
            or not all(isinstance(item, str) for item in edge)
        ):
            raise ValueError("workflow dependency edge must contain two strings")
        edges.append((edge[0], edge[1]))
    return tuple(edges)


def _load_workflow(value: Any, *, source_sha256: str, index: int) -> OutputWorkflowDag:
    if not isinstance(value, dict) or set(value) != _WORKFLOW_FIELDS:
        raise ValueError(
            f"workflow schema mismatch for {source_sha256} workflow {index}: "
            f"expected {sorted(_WORKFLOW_FIELDS)}"
        )
    status = value["status"]
    if status not in _WORKFLOW_STATUSES:
        raise ValueError(
            f"invalid workflow status for {source_sha256} workflow {index}: {status!r}"
        )
    string_fields = ("workflow_id", "sink_root_id")
    if any(
        not isinstance(value[field], str) or not value[field] for field in string_fields
    ):
        raise ValueError(
            f"workflow identity is invalid for {source_sha256} workflow {index}"
        )
    sink_line = value["sink_line"]
    if not isinstance(sink_line, int) or isinstance(sink_line, bool) or sink_line < 1:
        raise ValueError(
            f"workflow sink_line is invalid for {source_sha256} workflow {index}"
        )
    return OutputWorkflowDag(
        workflow_id=value["workflow_id"],
        sink_root_id=value["sink_root_id"],
        sink_line=sink_line,
        definition_ids=_string_tuple(value["definition_ids"], "definition_ids"),
        dependency_edges=_edge_tuple(value["dependency_edges"]),
        core_call_ordinals=_int_tuple(
            value["core_call_ordinals"], "core_call_ordinals"
        ),
        core_raw_callees=_string_tuple(value["core_raw_callees"], "core_raw_callees"),
        external_input_identifiers=_string_tuple(
            value["external_input_identifiers"], "external_input_identifiers"
        ),
        unresolved_identifiers=_string_tuple(
            value["unresolved_identifiers"], "unresolved_identifiers"
        ),
        status=status,
        fail_closed_reasons=_string_tuple(
            value["fail_closed_reasons"], "fail_closed_reasons"
        ),
    )


def _load_ast(ast_dir: Path, source_sha256: str) -> tuple[dict[str, Any], Path]:
    ast_path = ast_dir / f"{source_sha256}.json"
    if not ast_path.is_file():
        raise ValueError(f"missing AST for source_sha256 {source_sha256}: {ast_path}")
    if ast_path.name != f"{source_sha256}.json":
        raise ValueError(f"invalid AST filename for source_sha256 {source_sha256}")
    try:
        ast = json.loads(ast_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(
            f"invalid AST JSON for source_sha256 {source_sha256}: {exc}"
        ) from exc
    if (
        not isinstance(ast, dict)
        or ast.get("type") != "Program"
        or not isinstance(ast.get("body"), list)
    ):
        raise ValueError(f"invalid AST root for source_sha256 {source_sha256}")
    return ast, ast_path


def _decision_row(
    source_row: dict[str, Any],
    workflow: OutputWorkflowDag,
    decision: WorkflowFidelityDecision,
) -> dict[str, Any]:
    preserved_source = {
        key: value
        for key, value in source_row.items()
        if key
        not in {
            "workflows",
            "training_admission",
            "training_rows_emitted",
        }
    }
    return {
        **preserved_source,
        **asdict(decision),
        "definition_ids": list(workflow.definition_ids),
        "dependency_edges": [list(edge) for edge in workflow.dependency_edges],
        "core_call_ordinals": list(workflow.core_call_ordinals),
        "core_raw_callees": list(workflow.core_raw_callees),
        "unresolved_identifiers": list(workflow.unresolved_identifiers),
        "training_rows_emitted": 0,
    }


def _report(summary: dict[str, Any]) -> str:
    statuses = summary["fidelity_statuses"]
    reasons = summary["fail_closed_reasons"]
    lines = [
        "# GEE Workflow Fidelity Calibration",
        "",
        "This artifact is a deterministic post-DAG calibration. It emits no training rows.",
        "",
        "## Counts",
        "",
        f"- Sources: {summary['source_count']}",
        f"- Workflows: {summary['workflow_count']}",
        f"- Passed candidates: {statuses.get('passed', 0)}",
        f"- Fail-closed: {statuses.get('fail_closed', 0)}",
        f"- Exact duplicates: {statuses.get('duplicate', 0)}",
        f"- Training rows emitted: {summary['training_rows_emitted']}",
        "",
        "## Fail-Closed Reasons",
        "",
    ]
    lines.extend(f"- `{reason}`: {count}" for reason, count in sorted(reasons.items()))
    if not reasons:
        lines.append("- None")
    lines.extend(
        [
            "",
            "## Admission Boundary",
            "",
            "Passed rows remain `not_granted_taxonomy_and_task_text_pending`.",
            "",
        ]
    )
    return "\n".join(lines)


def build_fidelity_calibration(
    workflow_dags_path: Path,
    ast_dir: Path,
    output_dir: Path,
) -> dict[str, Any]:
    """Validate complete-DAG artifacts and emit deterministic fidelity ledgers."""

    workflow_dags_path = Path(workflow_dags_path)
    ast_dir = Path(ast_dir)
    output_dir = Path(output_dir)
    if not ast_dir.is_dir():
        raise ValueError(f"missing AST directory: {ast_dir}")

    source_rows = _read_jsonl(workflow_dags_path)
    seen_sources: set[str] = set()
    decisions: list[dict[str, Any]] = []
    accepted: list[dict[str, Any]] = []
    rejected: list[dict[str, Any]] = []
    duplicates: list[dict[str, Any]] = []
    ast_inputs: dict[str, dict[str, Any]] = {}

    for source_index, source_row in enumerate(source_rows, start=1):
        source_sha256 = source_row.get("source_sha256")
        if not isinstance(source_sha256, str) or not _SHA256_RE.fullmatch(
            source_sha256
        ):
            raise ValueError(
                f"invalid source_sha256 at workflow DAG row {source_index}"
            )
        if source_sha256 in seen_sources:
            raise ValueError(
                f"duplicate source_sha256 in workflow DAG input: {source_sha256}"
            )
        seen_sources.add(source_sha256)
        raw_workflows = source_row.get("workflows")
        if not isinstance(raw_workflows, list):
            raise ValueError(
                f"workflows must be a list for source_sha256 {source_sha256}"
            )
        workflows = tuple(
            _load_workflow(value, source_sha256=source_sha256, index=index)
            for index, value in enumerate(raw_workflows, start=1)
        )
        workflow_ids = [workflow.workflow_id for workflow in workflows]
        if len(workflow_ids) != len(set(workflow_ids)):
            raise ValueError(f"duplicate workflow_id for source_sha256 {source_sha256}")
        ast, ast_path = _load_ast(ast_dir, source_sha256)
        ast_inputs[source_sha256] = {
            "path": f"ast/{source_sha256}.json",
            "sha256": _sha256(ast_path),
        }
        source_decisions = evaluate_workflow_fidelity(
            source_sha256=source_sha256,
            ast=ast,
            workflows=workflows,
        )
        for workflow, decision in zip(workflows, source_decisions, strict=True):
            row = _decision_row(source_row, workflow, decision)
            decisions.append(row)
            if decision.fidelity_status == "passed":
                accepted.append(row)
            elif decision.fidelity_status == "duplicate":
                duplicates.append(row)
            else:
                rejected.append(row)

    status_counts = Counter(row["fidelity_status"] for row in decisions)
    reason_counts = Counter(
        reason for row in rejected for reason in row.get("fail_closed_reasons", [])
    )
    summary = {
        "schema": "gis_recommend.gee_workflow_fidelity_calibration.v1",
        "source_count": len(source_rows),
        "workflow_count": len(decisions),
        "fidelity_statuses": dict(sorted(status_counts.items())),
        "fail_closed_reasons": dict(sorted(reason_counts.items())),
        "accepted_candidate_count": len(accepted),
        "rejected_count": len(rejected),
        "exact_duplicate_count": len(duplicates),
        "unique_accepted_source_count": len({row["source_sha256"] for row in accepted}),
        "removed_auxiliary_call_count": sum(
            len(row["removed_auxiliary_calls"]) for row in decisions
        ),
        "external_spatial_input_workflow_count": sum(
            bool(row["external_spatial_inputs"]) for row in decisions
        ),
        "training_admission": "not_granted_taxonomy_and_task_text_pending",
        "training_rows_emitted": 0,
    }
    payloads = {
        "fidelity_decisions.jsonl": _jsonl_bytes(decisions),
        "accepted_candidates.jsonl": _jsonl_bytes(accepted),
        "rejected_ledger.jsonl": _jsonl_bytes(rejected),
        "duplicate_ledger.jsonl": _jsonl_bytes(duplicates),
        "summary.json": _json_bytes(summary),
        "report.md": _report(summary).encode("utf-8"),
    }
    for name, payload in payloads.items():
        _atomic_write(output_dir / name, payload)
    ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "inputs": {
            "workflow_dags": {
                "path": "workflow_dags.jsonl",
                "sha256": _sha256(workflow_dags_path),
            },
            "ast_files": dict(sorted(ast_inputs.items())),
        },
        "artifacts": {
            name: {
                "sha256": hashlib.sha256(payload).hexdigest(),
                "size_bytes": len(payload),
            }
            for name, payload in sorted(payloads.items())
        },
    }
    _atomic_write(output_dir / "hash_ledger.json", _json_bytes(ledger))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workflow-dags", type=Path, required=True)
    parser.add_argument("--ast-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    build_fidelity_calibration(
        workflow_dags_path=args.workflow_dags,
        ast_dir=args.ast_dir,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    main()
