#!/usr/bin/env python3
"""Resolve static GRASS ``v.clean`` tool values with an explicit provider enum.

This module is deliberately report-only.  It does not assign an L3 class and
never turns an enum resolution into a training admission.  A provider/version
manifest is required so that an integer is not interpreted against an
unrecorded QGIS/GRASS parameter order.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import sys
import tempfile
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gis_recommend.data.qgis_processing_ast import processing_parameter_nodes


SCHEMA = "gis_recommend.qgis_vclean_tool_enum_resolution.v1"
KNOWN_OPERATOR = "grass7:v.clean"


def _normalise_manifest(manifest: dict[str, Any]) -> dict[str, str]:
    if str(manifest.get("operator_id") or "") != KNOWN_OPERATOR:
        raise ValueError("enum manifest operator_id must be grass7:v.clean")
    version = str(manifest.get("provider_version") or "").strip()
    if not version:
        raise ValueError("enum manifest requires provider_version")
    raw = manifest.get("tools")
    if not isinstance(raw, dict) or not raw:
        raise ValueError("enum manifest requires non-empty tools mapping")
    normalised: dict[str, str] = {}
    for key, value in raw.items():
        key_text = str(key).strip()
        value_text = str(value).strip()
        if not key_text or not value_text or not key_text.isdigit():
            raise ValueError("tool enum keys must be non-negative integer strings")
        normalised[key_text] = value_text
    return normalised


def _literal_values(node: ast.AST, constants: dict[str, ast.AST]) -> tuple[list[Any], str]:
    """Return literal values or a reason code; names resolve only to constants."""
    if isinstance(node, ast.Constant):
        if isinstance(node.value, bool) or not isinstance(node.value, (int, str)):
            return [], "non_integer_or_string_literal"
        return [node.value], "literal"
    if isinstance(node, (ast.List, ast.Tuple, ast.Set)):
        values: list[Any] = []
        for element in node.elts:
            nested, reason = _literal_values(element, constants)
            if reason not in {"literal", "constant_name"}:
                return [], f"container_{reason}"
            values.extend(nested)
        if not values:
            return [], "empty_tool_container"
        return values, "literal_container"
    if isinstance(node, ast.Name) and node.id in constants:
        values, reason = _literal_values(constants[node.id], constants)
        if reason.startswith("container_") or reason in {"literal", "literal_container", "constant_name"}:
            return values, "constant_name"
        return [], f"constant_{reason}"
    return [], "dynamic_expression"


def _constant_assignments(tree: ast.AST) -> dict[str, ast.AST]:
    candidates: dict[str, list[ast.AST]] = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name):
            target = node.targets[0].id
            candidates.setdefault(target, []).append(node.value)
    constants: dict[str, ast.AST] = {}
    for target, values in candidates.items():
        if len(values) != 1:
            continue
        value, reason = _literal_values(values[0], constants)
        if value and reason in {"literal", "literal_container", "constant_name"}:
            constants[target] = values[0]
    return constants


def _processing_calls(tree: ast.AST) -> list[ast.Call]:
    calls: list[ast.Call] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not isinstance(node.func, ast.Attribute):
            continue
        if node.func.attr != "run" or not isinstance(node.func.value, ast.Name) or node.func.value.id != "processing":
            continue
        if not node.args or not isinstance(node.args[0], ast.Constant) or node.args[0].value != KNOWN_OPERATOR:
            continue
        calls.append(node)
    return sorted(calls, key=lambda call: (call.lineno, call.col_offset))


def resolve_source(source: str, manifest: dict[str, Any]) -> dict[str, Any]:
    """Resolve every v.clean call; any uncertain call makes the source deferred."""
    tools = _normalise_manifest(manifest)
    provider_version = str(manifest["provider_version"])
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return {
            "schema": SCHEMA,
            "status": "deferred",
            "provider_version": provider_version,
            "calls": [],
            "reasons": ["syntax_error"],
            "error": str(exc),
            "mapping_admission": "not_granted_enum_only",
            "training_admission": "not_granted",
        }
    constants = _constant_assignments(tree)
    parameter_rows = processing_parameter_nodes(tree, KNOWN_OPERATOR, "tool")
    calls = [row["call"] for row in parameter_rows]
    if not calls:
        return {
            "schema": SCHEMA,
            "status": "deferred",
            "provider_version": provider_version,
            "calls": [],
            "reasons": ["vclean_call_not_found"],
            "mapping_admission": "not_granted_enum_only",
            "training_admission": "not_granted",
        }

    resolved_calls: list[dict[str, Any]] = []
    reasons: list[str] = []
    for ordinal, parameter_row in enumerate(parameter_rows, start=1):
        call = parameter_row["call"]
        value_node = parameter_row["parameter_node"]
        if value_node is None:
            reasons.append(f"call_{ordinal}:tool_parameter_not_static_dict")
            resolved_calls.append({"ordinal": ordinal, "line": call.lineno, "status": "deferred"})
            continue
        values, value_kind = _literal_values(value_node, constants)
        if not values:
            reasons.append(f"call_{ordinal}:{value_kind}")
            resolved_calls.append({"ordinal": ordinal, "line": call.lineno, "status": "deferred", "value_kind": value_kind})
            continue
        enum_rows: list[dict[str, Any]] = []
        unknown = False
        for value in values:
            key = str(value).strip()
            if isinstance(value, str) and not key.isdigit():
                # Named values are accepted only when the provider manifest explicitly lists them.
                by_name = {name: number for number, name in tools.items()}
                number = by_name.get(key)
            else:
                number = key if key.isdigit() else None
            if number is None or number not in tools:
                unknown = True
                enum_rows.append({"raw_value": value, "status": "unknown"})
            else:
                enum_rows.append({"raw_value": value, "enum_id": number, "tool_name": tools[number], "status": "resolved"})
        status = "deferred" if unknown else "resolved"
        if unknown:
            reasons.append(f"call_{ordinal}:unknown_tool_enum")
        resolved_calls.append({
            "ordinal": ordinal,
            "line": call.lineno,
            "value_kind": value_kind,
            "tools": enum_rows,
            "status": status,
        })
    status = "resolved" if not reasons else "deferred"
    return {
        "schema": SCHEMA,
        "status": status,
        "provider_version": provider_version,
        "calls": resolved_calls,
        "reasons": reasons,
        "mapping_admission": "not_granted_enum_only",
        "training_admission": "not_granted",
    }


def build_census(rows: Iterable[dict[str, Any]], manifest: dict[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Resolve queue source snippets without emitting candidate/training rows."""
    output: list[dict[str, Any]] = []
    for row in rows:
        if str(row.get("operator_id") or "") != KNOWN_OPERATOR:
            continue
        samples = row.get("samples") or [row]
        for sample in samples:
            source = str(sample.get("source_text") or sample.get("source_snippet") or "")
            result = resolve_source(source, manifest)
            output.append({
                **result,
                "record_id": str(sample.get("record_id") or row.get("record_id") or ""),
                "source_sha256": str(sample.get("source_sha256") or row.get("source_sha256") or ""),
                "source_path": str(sample.get("source_path") or row.get("source_path") or ""),
                "source_verification": str(sample.get("source_verification") or row.get("source_verification") or ""),
                "training_row_emitted": False,
            })
    summary = {
        "schema": SCHEMA + ".summary",
        "provider_version": str(manifest.get("provider_version") or ""),
        "source_rows": len(output),
        "resolved_rows": sum(row["status"] == "resolved" for row in output),
        "deferred_rows": sum(row["status"] != "resolved" for row in output),
        "resolved_calls": sum(sum(call.get("status") == "resolved" for call in row.get("calls") or []) for row in output),
        "training_rows_emitted": 0,
        "mapping_admission": "not_granted_enum_only",
        "production_merge": "not_granted",
    }
    return output, summary


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-jsonl", type=Path, required=True)
    parser.add_argument("--enum-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    manifest = json.loads(args.enum_manifest.read_text(encoding="utf-8"))
    rows = [json.loads(line) for line in args.input_jsonl.read_text(encoding="utf-8").splitlines() if line.strip()]
    resolved, summary = build_census(rows, manifest)
    rows_path = args.output_dir / "resolution_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    manifest_path = args.output_dir / "provider_enum_manifest_v1.json"
    _write_text(rows_path, "\n".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) for row in resolved) + ("\n" if resolved else ""))
    _write(summary_path, summary)
    _write(manifest_path, manifest)
    _write(args.output_dir / "hash_ledger_v1.json", {
        "schema": "gis_recommend.hash_ledger.v1",
        "inputs": {"input_jsonl": {"path": str(args.input_jsonl), "sha256": _sha256(args.input_jsonl)}, "enum_manifest": {"path": str(args.enum_manifest), "sha256": _sha256(args.enum_manifest)}},
        "artifacts": {rows_path.name: _sha256(rows_path), summary_path.name: _sha256(summary_path), manifest_path.name: _sha256(manifest_path)},
    })
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
