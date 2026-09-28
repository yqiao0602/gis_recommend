#!/usr/bin/env python3
"""Build a deterministic typed GEE operator-to-L3 census from fidelity candidates."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import re
from typing import Any

from gis_recommend.data.gee_operator_canonicalization import (
    load_gee_l3_mapping,
    load_gee_operator_catalog,
    load_gee_skip_operators,
)
from gis_recommend.data.gee_source_extractor import extract_gee_source_evidence
from gis_recommend.data.gee_typed_canonicalization import canonicalize_workflow_calls
from gis_recommend.data.gee_typed_canonicalization import load_typed_l3_overrides


_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_INPUT_ADMISSION = "not_granted_taxonomy_and_task_text_pending"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path} line {line_number} must be an object")
            rows.append(value)
    if not rows:
        raise ValueError(f"{path} contains no rows")
    return rows


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _jsonl_bytes(rows: list[dict[str, Any]]) -> bytes:
    return b"".join(
        (json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode(
            "utf-8"
        )
        for row in rows
    )


def _atomic_write(path: Path, payload: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(f".{path.name}.tmp")
    temporary.write_bytes(payload)
    temporary.replace(path)


def _load_ast(ast_dir: Path, source_sha256: str) -> tuple[dict[str, Any], Path]:
    path = ast_dir / f"{source_sha256}.json"
    if not path.is_file():
        raise ValueError(f"missing AST for source_sha256 {source_sha256}")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("type") != "Program" or not isinstance(
        value.get("body"), list
    ):
        raise ValueError(f"invalid Program AST for source_sha256 {source_sha256}")
    return value, path


def _location_key(location: dict[str, Any] | None) -> tuple[int, int, int, int] | None:
    if not isinstance(location, dict):
        return None
    values = (
        location.get("start_line"),
        location.get("start_column"),
        location.get("end_line"),
        location.get("end_column"),
    )
    return values if all(type(value) is int for value in values) else None


def _ast_call_argument_counts(ast: dict[str, Any]) -> dict[tuple[int, int, int, int], int]:
    counts: dict[tuple[int, int, int, int], int] = {}

    def visit(node: Any) -> None:
        if isinstance(node, list):
            for item in node:
                visit(item)
            return
        if not isinstance(node, dict):
            return
        if node.get("type") == "CallExpression":
            loc = node.get("loc")
            if isinstance(loc, dict):
                start = loc.get("start") or {}
                end = loc.get("end") or {}
                key = (
                    start.get("line"),
                    start.get("column"),
                    end.get("line"),
                    end.get("column"),
                )
                arguments = node.get("arguments")
                if all(type(value) is int for value in key) and isinstance(arguments, list):
                    counts[key] = len(arguments)
        for value in node.values():
            visit(value)

    visit(ast)
    return counts


def _validate_candidate(row: dict[str, Any], index: int) -> tuple[str, str]:
    source_sha256 = row.get("source_sha256")
    workflow_id = row.get("workflow_id")
    if not isinstance(source_sha256, str) or not _SHA256_RE.fullmatch(source_sha256):
        raise ValueError(f"candidate row {index} has invalid source_sha256")
    if not isinstance(workflow_id, str) or not workflow_id:
        raise ValueError(f"candidate row {index} has invalid workflow_id")
    if row.get("fidelity_status") != "passed" or row.get("fail_closed_reasons") not in ([], ()):
        raise ValueError(f"candidate row {index} is not fidelity-passed")
    if row.get("training_admission") != _INPUT_ADMISSION or row.get("training_rows_emitted") != 0:
        raise ValueError(f"candidate row {index} has invalid input admission")
    return source_sha256, workflow_id


def _report(summary: dict[str, Any]) -> str:
    lines = [
        "# GEE Typed Operator/L3 Mapping Census",
        "",
        f"- Decisions: {summary['decision_count']}",
        f"- Mapping complete: {summary['mapping_complete_count']}",
        f"- Fail closed: {summary['fail_closed_count']}",
        f"- Unique mapping-complete sources: {summary['unique_mapping_complete_source_count']}",
        f"- Statuses: {json.dumps(summary['mapping_statuses'], sort_keys=True)}",
        f"- Reasons: {json.dumps(summary['fail_closed_reasons'], sort_keys=True)}",
        f"- Canonical operators: {summary['distinct_canonical_operator_count']}",
        f"- L3 codes: {summary['distinct_l3_count']}",
        "- Admission: task text and final dedup pending; zero training rows emitted.",
        "",
    ]
    return "\n".join(lines)


def build_typed_l3_mapping_census(
    *,
    accepted_candidates_path: Path,
    ast_dir: Path,
    id_mappings_path: Path,
    skip_list_path: Path,
    output_dir: Path,
    l3_overrides_path: Path | None = None,
) -> dict[str, Any]:
    accepted_candidates_path = Path(accepted_candidates_path)
    ast_dir = Path(ast_dir)
    id_mappings_path = Path(id_mappings_path)
    skip_list_path = Path(skip_list_path)
    output_dir = Path(output_dir)
    l3_overrides_path = Path(l3_overrides_path) if l3_overrides_path is not None else None
    if not ast_dir.is_dir():
        raise ValueError(f"missing AST directory: {ast_dir}")

    candidates = _read_jsonl(accepted_candidates_path)
    mapping = load_gee_l3_mapping(id_mappings_path)
    operator_catalog = load_gee_operator_catalog(id_mappings_path)
    skip_operators = load_gee_skip_operators(skip_list_path)
    override_authority = (
        load_typed_l3_overrides(l3_overrides_path, id_mappings_path)
        if l3_overrides_path is not None
        else None
    )
    decisions: list[dict[str, Any]] = []
    complete: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    ast_inputs: dict[str, dict[str, str]] = {}
    seen_keys: set[tuple[str, str]] = set()

    for index, candidate in enumerate(candidates, start=1):
        source_sha256, workflow_id = _validate_candidate(candidate, index)
        key = (source_sha256, workflow_id)
        if key in seen_keys:
            raise ValueError(f"duplicate candidate identity: {source_sha256}/{workflow_id}")
        seen_keys.add(key)
        ast, ast_path = _load_ast(ast_dir, source_sha256)
        ast_inputs[source_sha256] = {
            "path": f"ast/{source_sha256}.json",
            "sha256": _sha256(ast_path),
        }
        source_path = candidate.get("source_path")
        if not isinstance(source_path, str) or not source_path:
            raise ValueError(f"candidate row {index} has invalid source_path")
        source_evidence = extract_gee_source_evidence(
            ast,
            source_path=source_path,
            source_sha256=source_sha256,
        )
        arguments_by_location = _ast_call_argument_counts(ast)
        call_argument_counts = {
            call.ordinal: arguments_by_location[key]
            for call in source_evidence.ordered_calls
            if (key := _location_key(call.source_location)) in arguments_by_location
        }
        decision = canonicalize_workflow_calls(
            candidate,
            source_evidence,
            mapping,
            operator_catalog,
            skip_operators=skip_operators,
            l3_overrides=(override_authority.overrides if override_authority else None),
            call_argument_counts=call_argument_counts,
        )
        row = asdict(decision)
        decisions.append(row)
        if decision.mapping_status == "mapping_complete":
            complete.append(row)
        else:
            failed.append(row)

    status_counts = Counter(row["mapping_status"] for row in decisions)
    reason_counts = Counter(reason for row in failed for reason in row["fail_closed_reasons"])
    canonical_operators = {
        operator for row in decisions for operator in row["canonical_operator_sequence"]
    }
    l3_codes = {code for row in decisions for code in row["l3_sequence"]}
    confidence_counts = Counter(
        "none" if confidence is None else format(confidence, ".12g")
        for row in decisions
        for confidence in row["mapping_confidences"]
    )
    strata: dict[str, dict[str, int]] = {}
    for stratum in sorted({str(row["calibration_stratum"]) for row in decisions}):
        selected = [row for row in decisions if row["calibration_stratum"] == stratum]
        strata[stratum] = {
            "decision_count": len(selected),
            "mapping_complete_count": sum(row["mapping_status"] == "mapping_complete" for row in selected),
            "fail_closed_count": sum(row["mapping_status"] != "mapping_complete" for row in selected),
        }
    summary = {
        "schema": "gis_recommend.gee_typed_l3_mapping_census.v1",
        "decision_count": len(decisions),
        "mapping_complete_count": len(complete),
        "fail_closed_count": len(failed),
        "unique_mapping_complete_source_count": len({row["source_sha256"] for row in complete}),
        "mapping_statuses": dict(sorted(status_counts.items())),
        "fail_closed_reasons": dict(sorted(reason_counts.items())),
        "distinct_canonical_operator_count": len(canonical_operators),
        "distinct_l3_count": len(l3_codes),
        "mapping_confidences": dict(sorted(confidence_counts.items())),
        "l3_override_version": override_authority.version if override_authority else None,
        "l3_override_count": len(override_authority.overrides) if override_authority else 0,
        "strata": strata,
        "training_admission": "not_granted_task_text_and_final_dedup_pending",
        "training_rows_emitted": 0,
    }
    payloads = {
        "typed_mapping_decisions.jsonl": _jsonl_bytes(decisions),
        "mapping_complete_candidates.jsonl": _jsonl_bytes(complete),
        "mapping_fail_closed.jsonl": _jsonl_bytes(failed),
        "summary.json": _json_bytes(summary),
        "report.md": _report(summary).encode("utf-8"),
    }
    for name, payload in payloads.items():
        _atomic_write(output_dir / name, payload)
    ledger_inputs = {
        "accepted_candidates": {
            "path": "accepted_candidates.jsonl",
            "sha256": _sha256(accepted_candidates_path),
        },
        "id_mappings": {"path": id_mappings_path.name, "sha256": _sha256(id_mappings_path)},
        "skip_list": {"path": skip_list_path.name, "sha256": _sha256(skip_list_path)},
        "ast_files": dict(sorted(ast_inputs.items())),
    }
    if l3_overrides_path is not None:
        ledger_inputs["l3_overrides"] = {
            "path": l3_overrides_path.name,
            "sha256": _sha256(l3_overrides_path),
        }
    ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "inputs": ledger_inputs,
        "artifacts": {
            name: {"sha256": hashlib.sha256(payload).hexdigest(), "size_bytes": len(payload)}
            for name, payload in sorted(payloads.items())
        },
    }
    _atomic_write(output_dir / "hash_ledger.json", _json_bytes(ledger))
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--accepted-candidates", type=Path, required=True)
    parser.add_argument("--ast-dir", type=Path, required=True)
    parser.add_argument("--id-mappings", type=Path, required=True)
    parser.add_argument("--skip-list", type=Path, required=True)
    parser.add_argument("--l3-overrides", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    build_typed_l3_mapping_census(
        accepted_candidates_path=args.accepted_candidates,
        ast_dir=args.ast_dir,
        id_mappings_path=args.id_mappings,
        skip_list_path=args.skip_list,
        output_dir=args.output_dir,
        l3_overrides_path=args.l3_overrides,
    )


if __name__ == "__main__":
    main()
