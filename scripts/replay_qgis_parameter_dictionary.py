#!/usr/bin/env python3
"""Replay the conservative parameter-dictionary recovery rule on a source pool."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any


def _parents(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    return {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}


def _scope(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> ast.AST | None:
    current: ast.AST | None = node
    while current is not None:
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)):
            return current
        current = parents.get(current)
    return None


def _control_path(
    node: ast.AST, parents: dict[ast.AST, ast.AST]
) -> tuple[tuple[ast.AST, str], ...]:
    """Return the enclosing control-flow branches from outermost to innermost."""

    path: list[tuple[ast.AST, str]] = []
    child = node
    parent = parents.get(child)
    blocked = (ast.If, ast.For, ast.AsyncFor, ast.While, ast.Try, ast.With, ast.AsyncWith)
    while parent is not None:
        if isinstance(parent, blocked):
            branch = next(
                (
                    field
                    for field, value in ast.iter_fields(parent)
                    if value is child or isinstance(value, list) and child in value
                ),
                "",
            )
            path.append((parent, branch))
        child = parent
        parent = parents.get(child)
    return tuple(reversed(path))


def _dominates(
    definition: ast.AST, call: ast.Call, parents: dict[ast.AST, ast.AST]
) -> bool:
    definition_path = _control_path(definition, parents)
    call_path = _control_path(call, parents)
    return definition_path == call_path[: len(definition_path)]


def _processing_call(node: ast.Call) -> bool:
    if not isinstance(node.func, ast.Attribute) or node.func.attr != "run":
        return False
    receiver = node.func.value
    if isinstance(receiver, ast.Name):
        return receiver.id in {"processing", "qgis_processing"}
    if isinstance(receiver, ast.Attribute):
        return receiver.attr in {"processing", "processingTools"}
    return False


def inspect_parameter_dictionary(
    source_text: str, *, call_line: int, call_end: int
) -> dict[str, Any]:
    """Return source-backed evidence for the narrow dictionary rule."""

    try:
        tree = ast.parse(source_text)
    except SyntaxError as exc:
        return {"status": "fail_closed", "reason": f"syntax_error:{exc.msg}"}
    parents = _parents(tree)
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and _processing_call(node)
        and node.lineno <= call_end
        and int(node.end_lineno or node.lineno) >= call_line
    ]
    if len(calls) != 1:
        return {"status": "fail_closed", "reason": "call_alignment_not_unique"}
    call = calls[0]
    if len(call.args) < 2:
        return {"status": "not_applicable", "reason": "parameter_argument_absent"}
    if isinstance(call.args[1], ast.Dict):
        return {"status": "not_applicable", "reason": "parameter_argument_literal_dict"}
    if not isinstance(call.args[1], ast.Name):
        return {"status": "fail_closed", "reason": "parameter_argument_not_named"}
    parameter_name = call.args[1].id
    call_scope = _scope(call, parents)

    definitions: list[ast.Assign | ast.AnnAssign] = []
    mutations: list[ast.AST] = []
    for node in ast.walk(tree):
        if int(getattr(node, "lineno", 0)) >= int(call.lineno):
            continue
        if _scope(node, parents) is not call_scope:
            continue
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == parameter_name:
                    definitions.append(node)
                if isinstance(target, ast.Subscript) and isinstance(target.value, ast.Name) and target.value.id == parameter_name:
                    mutations.append(node)
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name) and node.target.id == parameter_name:
            definitions.append(node)
        elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id == parameter_name and node.func.attr in {"update", "setdefault"}:
            mutations.append(node)

    reaching = [node for node in definitions if _dominates(node, call, parents)]
    if not reaching:
        return {"status": "fail_closed", "reason": "ambiguous_reaching_definition"}
    definition = max(reaching, key=lambda node: int(node.lineno))
    intervening_definitions = [
        node
        for node in definitions
        if node is not definition and int(definition.lineno) < int(node.lineno)
    ]
    intervening_mutations = [
        node for node in mutations if int(definition.lineno) < int(node.lineno)
    ]
    if intervening_definitions:
        return {"status": "fail_closed", "reason": "ambiguous_reaching_definition"}
    value = definition.value
    if not isinstance(value, ast.Dict):
        return {"status": "fail_closed", "reason": "definition_not_unconditional_literal_dict"}
    if intervening_mutations:
        return {"status": "fail_closed", "reason": "dictionary_mutation_before_call"}
    keys: list[str] = []
    for key in value.keys:
        if not isinstance(key, ast.Constant) or not isinstance(key.value, str):
            return {"status": "fail_closed", "reason": "dynamic_dictionary_key"}
        keys.append(key.value.upper())
    return {
        "status": "eligible",
        "parameter_name": parameter_name,
        "definition_line": int(definition.lineno),
        "call_line": int(call.lineno),
        "keys": sorted(set(keys)),
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", dir=path.parent, delete=False) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)


def replay(census_rows: list[dict[str, Any]], manifest_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    manifest_by_id = {str(row["record_id"]): row for row in manifest_rows}
    candidates: list[dict[str, Any]] = []
    seen_authorities: set[str] = set()
    for census in sorted(census_rows, key=lambda row: str(row.get("record_id", ""))):
        if "parameter_dictionary" not in (census.get("families") or []) or int(census.get("multi_step_local_unit_count") or 0) < 1:
            continue
        manifest = manifest_by_id.get(str(census["record_id"]))
        if manifest is None or str(manifest.get("source_sha256")) != str(census.get("source_sha256")):
            continue
        authority = str(census.get("source_authority_key"))
        if authority in seen_authorities:
            continue
        source_path = Path(str(manifest.get("source_path", "")))
        row: dict[str, Any] = {
            "schema": "gis_recommend.qgis_parameter_dictionary_replay_row.v1",
            "record_id": str(census["record_id"]),
            "source_authority_key": authority,
            "source_sha256": str(census["source_sha256"]),
            "source_path": str(source_path),
            "family": "parameter_dictionary",
            "rule_id": "resolve-single-scope-parameter-dictionary-v1",
            "operator_ids": manifest.get("ordered_operator_ids", []),
            "mapped_l3_chain": manifest.get("mapped_l3_chain", []),
            "source_snippet": manifest.get("source_snippet", ""),
            "training_admission": "not_granted_replay_sidecar",
            "training_row_emitted": False,
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
        }
        if not source_path.is_file() or _sha256(source_path) != row["source_sha256"]:
            row.update({"replay_status": "fail_closed", "source_verification": "missing_or_sha_mismatch", "evidence": []})
        else:
            source = source_path.read_text(encoding="utf-8-sig", errors="replace")
            evidence = []
            for site in manifest.get("call_sites") or []:
                item = inspect_parameter_dictionary(source, call_line=int(site.get("line_start") or 0), call_end=int(site.get("line_end") or 0))
                evidence.append({"operator_id": site.get("operator_id", ""), **item})
            expected = int((census.get("family_evidence_counts") or {}).get("parameter_dictionary") or 0)
            applicable = [item for item in evidence if item.get("status") != "not_applicable"]
            eligible_count = sum(item.get("status") == "eligible" for item in applicable)
            failed_count = sum(item.get("status") == "fail_closed" for item in applicable)
            if expected > 0 and eligible_count == expected and failed_count == 0:
                status = "rule_candidate"
            elif eligible_count > 0:
                status = "partial_rule_candidate"
            else:
                status = "fail_closed"
            row["expected_family_evidence_count"] = expected
            row["applicable_evidence_count"] = len(applicable)
            row["eligible_evidence_count"] = eligible_count
            row["fail_closed_evidence_count"] = failed_count
            row.update({"replay_status": status, "source_verification": "verified_sha256", "evidence": evidence})
        candidates.append(row)
        seen_authorities.add(authority)
    summary = {
        "schema": "gis_recommend.qgis_parameter_dictionary_replay_summary.v1",
        "input_family_rows": sum("parameter_dictionary" in (row.get("families") or []) for row in census_rows),
        "multi_step_authorities_considered": len(candidates),
        "unique_source_authorities": len(seen_authorities),
        "status_counts": dict(sorted(Counter(row["replay_status"] for row in candidates).items())),
        "source_verification_counts": dict(sorted(Counter(row["source_verification"] for row in candidates).items())),
        "training_admission": "not_granted_replay_sidecar",
        "training_rows_emitted": 0,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }
    return candidates, summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--census", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    rows, summary = replay(_load_jsonl(args.census), _load_jsonl(args.manifest))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    jsonl = args.output_dir / "replay_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    report = args.output_dir / "report_v1.md"
    hashes = args.output_dir / "hash_ledger_v1.json"
    _atomic_write(jsonl, "".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows))
    _atomic_write(summary_path, json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    _atomic_write(report, "# QGIS parameter-dictionary replay v1\n\nReplay sidecar only; no training rows are emitted.\n")
    _atomic_write(hashes, json.dumps({
        "schema": "gis_recommend.hash_ledger.v1",
        "artifacts": {p.name: {"sha256": _sha256(p), "bytes": p.stat().st_size} for p in (jsonl, summary_path, report)},
    }, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
