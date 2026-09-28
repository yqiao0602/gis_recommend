#!/usr/bin/env python3
"""Replay field-schema API review rows against read-only source files."""

from __future__ import annotations

import argparse
import ast
import hashlib
import io
import json
import tempfile
import tokenize
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

SCHEMA = "gis_recommend.qgis_api_field_schema_source_replay.v1"
RULE_ID = "field-schema-addition-source-scope-replay-v1"
ADD_METHODS = {"addattribute", "addattributes"}
UPDATE_METHODS = {"updatefields"}


def _method_name(call_name: str) -> str:
    return call_name.rsplit(".", 1)[-1].lower()


def _call_name(node: ast.Call) -> str:
    parts: list[str] = []
    value: ast.AST = node.func
    while isinstance(value, ast.Attribute):
        parts.append(value.attr)
        value = value.value
    if isinstance(value, ast.Name):
        parts.append(value.id)
    return ".".join(reversed(parts))


def _scope_index(tree: ast.AST) -> list[tuple[int, int, str]]:
    scopes: list[tuple[int, int, str]] = []

    def visit(node: ast.AST, parents: tuple[str, ...]) -> None:
        next_parents = parents
        if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            qualified = ".".join((*parents, node.name))
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                scopes.append(
                    (
                        int(node.lineno),
                        int(getattr(node, "end_lineno", node.lineno)),
                        qualified,
                    )
                )
            next_parents = (*parents, node.name)
        for child in ast.iter_child_nodes(node):
            visit(child, next_parents)

    visit(tree, ())
    return scopes


def _scope_for_line(line: int, scopes: list[tuple[int, int, str]]) -> str:
    containing = [scope for scope in scopes if scope[0] <= line <= scope[1]]
    if not containing:
        return "<module>"
    return min(containing, key=lambda scope: (scope[1] - scope[0], -scope[0]))[2]


def _source_text(raw: bytes) -> str:
    encoding, _ = tokenize.detect_encoding(io.BytesIO(raw).readline)
    return raw.decode(encoding)


def _base_result(row: dict[str, Any], status: str) -> dict[str, Any]:
    return {
        **row,
        "schema": SCHEMA,
        "source_replay_rule_id": RULE_ID,
        "source_replay_status": status,
        "source_verification": "not_verified",
        "lexical_scope": "",
        "scope_call_methods": [],
        "source_call_evidence": [],
        "source_snippet": "",
        "mapping_admission": "not_granted_source_replay_only",
        "description_fidelity": "not_started",
        "deduplication": "not_started",
        "training_admission": "not_granted_source_replay_only",
        "training_row_emitted": False,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }


def replay_row(row: dict[str, Any]) -> dict[str, Any]:
    if row.get("selected_family_id") != "field_schema_addition":
        return _base_result(row, "unexpected_family")
    path = Path(str(row.get("source_path") or ""))
    if not path.is_file():
        return _base_result(row, "source_missing")
    raw = path.read_bytes()
    actual_sha = hashlib.sha256(raw).hexdigest()
    if actual_sha != row.get("source_sha256"):
        result = _base_result(row, "source_sha256_mismatch")
        result["actual_source_sha256"] = actual_sha
        return result
    try:
        text = _source_text(raw)
        tree = ast.parse(text, filename=str(path))
    except (SyntaxError, UnicodeDecodeError, LookupError) as error:
        result = _base_result(row, "source_parse_failure")
        result["source_parse_error"] = f"{type(error).__name__}: {error}"
        return result

    scopes = _scope_index(tree)
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    required_steps = []
    for step in row.get("steps") or []:
        method = _method_name(str(step.get("name") or ""))
        patterns = set(step.get("pattern_names") or [])
        if method in ADD_METHODS:
            role = "field_add"
        elif method in UPDATE_METHODS:
            role = "field_update"
        elif "sink_output" in patterns:
            role = "sink"
        else:
            continue
        required_steps.append((step, method, role))

    roles_present = {role for _, _, role in required_steps}
    if roles_present != {"field_add", "field_update", "sink"}:
        result = _base_result(row, "required_evidence_missing")
        result["required_roles_present"] = sorted(roles_present)
        return result

    evidence: list[dict[str, Any]] = []
    for step, method, role in required_steps:
        line_start = int(step.get("line_start") or 0)
        line_end = int(step.get("line_end") or line_start)
        matched = [
            call
            for call in calls
            if _method_name(_call_name(call)) == method
            and int(getattr(call, "lineno", 0)) <= line_end
            and int(getattr(call, "end_lineno", getattr(call, "lineno", 0)))
            >= line_start
        ]
        if len(matched) != 1:
            result = _base_result(row, "call_site_mismatch")
            result["mismatch_step"] = {
                "name": step.get("name"),
                "line_start": line_start,
                "line_end": line_end,
                "ast_match_count": len(matched),
            }
            return result
        call = matched[0]
        line = int(call.lineno)
        evidence.append(
            {
                "role": role,
                "recorded_name": step.get("name"),
                "ast_call_name": _call_name(call),
                "line_start": line,
                "line_end": int(getattr(call, "end_lineno", line)),
                "lexical_scope": _scope_for_line(line, scopes),
            }
        )

    roles_by_scope: dict[str, set[str]] = defaultdict(set)
    for item in evidence:
        roles_by_scope[str(item["lexical_scope"])].add(str(item["role"]))
    complete_scopes = sorted(
        scope
        for scope, roles in roles_by_scope.items()
        if roles == {"field_add", "field_update", "sink"}
    )
    if not complete_scopes:
        status = "deferred_cross_scope"
        selected_scope = ""
    elif len(complete_scopes) > 1:
        status = "deferred_ambiguous_complete_scopes"
        selected_scope = ""
    else:
        status = "verified_same_scope"
        selected_scope = complete_scopes[0]

    source_lines = text.splitlines()
    selected_evidence = (
        [item for item in evidence if item["lexical_scope"] == selected_scope]
        if selected_scope
        else evidence
    )
    first_line = max(1, min(int(item["line_start"]) for item in selected_evidence) - 5)
    last_line = min(
        len(source_lines),
        max(int(item["line_end"]) for item in selected_evidence) + 5,
    )
    snippet = "\n".join(
        f"{line_number} | {source_lines[line_number - 1]}"
        for line_number in range(first_line, last_line + 1)
    )
    result = _base_result(row, status)
    scope_calls = sorted(
        (
            call
            for call in calls
            if selected_scope
            and _scope_for_line(int(call.lineno), scopes) == selected_scope
        ),
        key=lambda call: (int(call.lineno), int(call.col_offset)),
    )
    result.update(
        {
            "source_verification": "verified_sha256",
            "lexical_scope": selected_scope,
            "complete_scope_count": len(complete_scopes),
            "source_call_evidence": evidence,
            "scope_call_methods": [_method_name(_call_name(call)) for call in scope_calls],
            "source_snippet": snippet,
        }
    )
    return result


def replay_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    replayed = [replay_row(row) for row in rows]
    status_counts = Counter(row["source_replay_status"] for row in replayed)
    summary = {
        "schema": "gis_recommend.qgis_api_field_schema_source_replay_summary.v1",
        "source_replay_rule_id": RULE_ID,
        "input_rows": len(rows),
        "source_replay_status_counts": dict(sorted(status_counts.items())),
        "verified_source_sha256": sum(
            row["source_verification"] == "verified_sha256" for row in replayed
        ),
        "verified_same_scope_rows": status_counts.get("verified_same_scope", 0),
        "mapping_rows_emitted": 0,
        "description_fidelity_rows": 0,
        "training_admission": "not_granted_source_replay_only",
        "training_rows_emitted": 0,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }
    return replayed, summary


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


def _write_json(path: Path, value: Any) -> None:
    _atomic_write(
        path,
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    _atomic_write(
        path,
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows
        ),
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-jsonl", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-rows", type=int, default=30)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    rows = _read_jsonl(args.review_jsonl)
    if len(rows) != args.expected_rows:
        raise ValueError(f"expected {args.expected_rows} rows, got {len(rows)}")
    replayed, summary = replay_rows(rows)
    replay_path = args.output_dir / "source_replay_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    _write_jsonl(replay_path, replayed)
    _write_json(summary_path, summary)
    ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "inputs": {
            args.review_jsonl.name: {
                "path": str(args.review_jsonl),
                "sha256": _sha256(args.review_jsonl),
            }
        },
        "artifacts": {
            replay_path.name: {
                "bytes": replay_path.stat().st_size,
                "sha256": _sha256(replay_path),
            },
            summary_path.name: {
                "bytes": summary_path.stat().st_size,
                "sha256": _sha256(summary_path),
            },
        },
    }
    _write_json(args.output_dir / "hash_ledger_v1.json", ledger)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
