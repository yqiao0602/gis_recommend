#!/usr/bin/env python3
"""Replay Create Feature Class macro candidates against read-only sources."""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import io
import json
import tempfile
import tokenize
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

SCHEMA = "gis_recommend.qgis_api_create_feature_class_source_replay.v1"
SUMMARY_SCHEMA = "gis_recommend.qgis_api_create_feature_class_source_replay_summary.v1"
RULE_ID = "create-feature-class-source-alias-replay-v1"


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


def _literal_string(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _is_memory_layer_constructor(call: ast.Call) -> bool:
    if _method_name(_call_name(call)) != "qgsvectorlayer":
        return False
    provider: ast.AST | None = call.args[2] if len(call.args) >= 3 else None
    for keyword in call.keywords:
        if keyword.arg in {"providerLib", "provider"}:
            provider = keyword.value
    return (_literal_string(provider) or "").lower() == "memory"


def _geometry_type(call: ast.Call) -> str:
    if not call.args:
        return "dynamic"
    expression = ast.unparse(call.args[0]).lower()
    for value in (
        "multipoint",
        "multilinestring",
        "multipolygon",
        "point",
        "linestring",
        "polygon",
        "none",
    ):
        if value in expression:
            return value
    return "dynamic"


def _contains_fields_call(node: ast.AST) -> bool:
    return any(
        isinstance(child, ast.Call)
        and _method_name(_call_name(child)) == "fields"
        for child in ast.walk(node)
    )


def _known_writer_format(call: ast.Call) -> str:
    values = [
        child.value
        for child in ast.walk(call)
        if isinstance(child, ast.Constant) and isinstance(child.value, str)
    ]
    known = {
        "esri shapefile": "ESRI Shapefile",
        "flatgeobuf": "FlatGeobuf",
        "geojson": "GeoJSON",
        "gpkg": "GPKG",
        "geopackage": "GPKG",
    }
    for value in values:
        lowered = value.lower()
        for marker, canonical in known.items():
            if marker in lowered:
                return canonical
    return "dynamic_vector_format"


def _assignment_target(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    return None


def _base_result(row: dict[str, Any], status: str) -> dict[str, Any]:
    return {
        **row,
        "schema": SCHEMA,
        "macro_source_replay_rule_id": RULE_ID,
        "macro_source_replay_status": status,
        "macro_source_verification": "not_verified",
        "complete_macro_chain_count": 0,
        "macro_chain_evidence": [],
        "macro_source_snippet": "",
        "mapping_status": "not_granted_source_replay_only",
        "description_fidelity": "not_started",
        "deduplication": "not_started",
        "training_admission": "not_granted_source_replay_only",
        "training_row_emitted": False,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }


def replay_row(row: dict[str, Any]) -> dict[str, Any]:
    if row.get("selected_family_id") != "create_feature_class":
        return _base_result(row, "unexpected_family")
    if row.get("macro_boundary_status") != "strict_review_eligible":
        return _base_result(row, "unexpected_census_status")
    if row.get("excluded_high_level_methods"):
        return _base_result(row, "unexpected_high_level_semantics")
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

    selected_scope = str(row.get("lexical_scope") or "")
    scopes = _scope_index(tree)
    nodes = [
        node
        for node in ast.walk(tree)
        if hasattr(node, "lineno")
        and _scope_for_line(int(node.lineno), scopes) == selected_scope
    ]
    calls = sorted(
        (node for node in nodes if isinstance(node, ast.Call)),
        key=lambda node: (int(node.lineno), int(node.col_offset)),
    )
    assignments: dict[str, list[tuple[int, ast.AST]]] = defaultdict(list)
    memory_layers: dict[str, ast.Call] = {}
    for node in nodes:
        targets: list[ast.AST] = []
        value: ast.AST | None = None
        if isinstance(node, ast.Assign):
            targets = list(node.targets)
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            targets = [node.target]
            value = node.value
        if value is None:
            continue
        for target in targets:
            name = _assignment_target(target)
            if not name:
                continue
            assignments[name].append((int(node.lineno), value))
            if isinstance(value, ast.Call) and _is_memory_layer_constructor(value):
                memory_layers[name] = value
    for definitions in assignments.values():
        definitions.sort(key=lambda item: item[0])

    def latest_definition(name: str, before_line: int) -> tuple[int, ast.AST] | None:
        eligible = [item for item in assignments.get(name, []) if item[0] <= before_line]
        return eligible[-1] if eligible else None

    def resolve_layer_name(
        name: str,
        before_line: int,
        seen: frozenset[str] = frozenset(),
    ) -> str | None:
        if name in seen:
            return None
        definition = latest_definition(name, before_line)
        if definition is None:
            return name if name in memory_layers else None
        line, value = definition
        if isinstance(value, ast.Call) and _is_memory_layer_constructor(value):
            return name
        if isinstance(value, ast.Name):
            return resolve_layer_name(value.id, line, seen | {name})
        return None

    def resolve_layer_expr(value: ast.AST, before_line: int) -> str | None:
        if isinstance(value, ast.Name):
            return resolve_layer_name(value.id, before_line)
        return None

    def resolve_provider_receiver(value: ast.AST, before_line: int) -> str | None:
        if (
            isinstance(value, ast.Call)
            and isinstance(value.func, ast.Attribute)
            and value.func.attr.lower() == "dataprovider"
        ):
            return resolve_layer_expr(value.func.value, before_line)
        if not isinstance(value, ast.Name):
            return None
        definition = latest_definition(value.id, before_line)
        if definition is None:
            return None
        line, provider_value = definition
        if isinstance(provider_value, ast.Name):
            return resolve_provider_receiver(provider_value, line)
        if (
            isinstance(provider_value, ast.Call)
            and isinstance(provider_value.func, ast.Attribute)
            and provider_value.func.attr.lower() == "dataprovider"
        ):
            return resolve_layer_expr(provider_value.func.value, line)
        return None

    evidence_by_layer: dict[str, dict[str, Any]] = {
        name: {
            "layer_variable": name,
            "constructor_line": int(call.lineno),
            "constructor_call": _call_name(call),
            "constructor_uri_expression": ast.unparse(call.args[0]) if call.args else "",
            "geometry_type": _geometry_type(call),
            "provider_variables": set(),
            "schema_add_lines": [],
            "schema_commit_lines": [],
            "vector_sink_lines": [],
            "vector_writer_lines": [],
            "schema_copies_input_fields": False,
            "writer_method": "",
            "writer_format": "dynamic_vector_format",
        }
        for name, call in memory_layers.items()
    }
    for call in calls:
        method = _method_name(_call_name(call))
        line = int(call.lineno)
        layer_name: str | None = None
        if method in {"addattribute", "addattributes", "addfeature", "addfeatures"}:
            if isinstance(call.func, ast.Attribute):
                layer_name = resolve_provider_receiver(call.func.value, line)
                provider_receiver = layer_name is not None
                if layer_name is None:
                    layer_name = resolve_layer_expr(call.func.value, line)
                if provider_receiver and isinstance(call.func.value, ast.Name):
                    evidence_by_layer[layer_name]["provider_variables"].add(
                        call.func.value.id
                    )
            if layer_name and method in {"addattribute", "addattributes"}:
                evidence_by_layer[layer_name]["schema_add_lines"].append(line)
                evidence_by_layer[layer_name]["schema_copies_input_fields"] = any(
                    _contains_fields_call(argument) for argument in call.args
                )
            elif layer_name:
                evidence_by_layer[layer_name]["vector_sink_lines"].append(line)
        elif method == "updatefields" and isinstance(call.func, ast.Attribute):
            layer_name = resolve_layer_expr(call.func.value, line)
            if layer_name:
                evidence_by_layer[layer_name]["schema_commit_lines"].append(line)
        elif method.startswith("writeasvectorformat"):
            layer_value = call.args[0] if call.args else None
            if layer_value is None:
                for keyword in call.keywords:
                    if keyword.arg in {"layer", "layerToWrite"}:
                        layer_value = keyword.value
            if layer_value is not None:
                layer_name = resolve_layer_expr(layer_value, line)
            if layer_name:
                evidence_by_layer[layer_name]["vector_writer_lines"].append(line)
                evidence_by_layer[layer_name]["writer_method"] = method
                evidence_by_layer[layer_name]["writer_format"] = _known_writer_format(
                    call
                )

    complete: list[dict[str, Any]] = []
    for item in evidence_by_layer.values():
        add_lines = item["schema_add_lines"]
        commit_lines = item["schema_commit_lines"]
        writer_lines = item["vector_writer_lines"]
        ordered = bool(
            add_lines
            and commit_lines
            and writer_lines
            and item["constructor_line"] <= min(add_lines)
            and min(add_lines) <= min(commit_lines)
            and min(commit_lines) <= max(writer_lines)
        )
        item["ordered_macro_contract"] = ordered
        item["provider_variables"] = sorted(item["provider_variables"])
        last_evidence_line = max(
            [
                item["constructor_line"],
                *item["schema_add_lines"],
                *item["schema_commit_lines"],
                *item["vector_sink_lines"],
                *item["vector_writer_lines"],
            ]
        )
        field_names = {
            value
            for call in calls
            if _method_name(_call_name(call)) == "qgsfield"
            and item["constructor_line"] - 50 <= int(call.lineno) <= last_evidence_line
            and call.args
            for value in [_literal_string(call.args[0])]
            if value
        }
        item["field_names"] = sorted(field_names)
        item["populates_features"] = bool(item["vector_sink_lines"])
        if ordered:
            complete.append(item)

    if not memory_layers:
        status = "deferred_no_memory_layer_constructor"
    elif not complete:
        status = "deferred_incomplete_macro_alias_chain"
    elif len(complete) > 1:
        status = "deferred_ambiguous_complete_macro_chains"
    else:
        status = "verified_complete_macro_alias_chain"

    selected_evidence = complete if complete else list(evidence_by_layer.values())
    evidence_lines = [
        line
        for item in selected_evidence
        for field in (
            "schema_add_lines",
            "schema_commit_lines",
            "vector_sink_lines",
            "vector_writer_lines",
        )
        for line in item[field]
    ] + [item["constructor_line"] for item in selected_evidence]
    source_lines = text.splitlines()
    if evidence_lines:
        first_line = max(1, min(evidence_lines) - 3)
        last_line = min(len(source_lines), max(evidence_lines) + 3)
        snippet = "\n".join(
            f"{line_number} | {source_lines[line_number - 1]}"
            for line_number in range(first_line, last_line + 1)
        )
    else:
        snippet = ""
    result = _base_result(row, status)
    result.update(
        {
            "macro_source_verification": "verified_sha256",
            "memory_layer_constructor_count": len(memory_layers),
            "complete_macro_chain_count": len(complete),
            "macro_chain_evidence": selected_evidence,
            "macro_source_snippet": snippet,
        }
    )
    return result


def replay_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    replayed = [replay_row(row) for row in rows]
    status_counts = Counter(row["macro_source_replay_status"] for row in replayed)
    split_counts = Counter(
        (str(row.get("review_split") or "unknown"), row["macro_source_replay_status"])
        for row in replayed
    )
    summary = {
        "schema": SUMMARY_SCHEMA,
        "macro_source_replay_rule_id": RULE_ID,
        "input_rows": len(rows),
        "source_replay_status_counts": dict(sorted(status_counts.items())),
        "split_status_counts": {
            f"{split_name}:{status}": count
            for (split_name, status), count in sorted(split_counts.items())
        },
        "verified_source_sha256_rows": sum(
            row["macro_source_verification"] == "verified_sha256" for row in replayed
        ),
        "verified_complete_macro_alias_chain_rows": status_counts.get(
            "verified_complete_macro_alias_chain", 0
        ),
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


def _write_review_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "review_split",
        "record_id",
        "source_path",
        "source_sha256",
        "normalized_source_body_sha256",
        "lexical_scope",
        "proposed_l3_code",
        "macro_source_replay_status",
        "complete_macro_chain_count",
        "macro_chain_evidence",
        "macro_source_snippet",
        "human_boundary_decision",
        "human_mapping_decision",
        "human_description_fidelity",
        "human_notes",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    **row,
                    "macro_chain_evidence": json.dumps(
                        row["macro_chain_evidence"], ensure_ascii=False
                    ),
                }
            )
        temporary = Path(handle.name)
    temporary.replace(path)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-jsonl", type=Path, action="append", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-rows", type=int, default=40)
    parser.add_argument("--strict-only", action="store_true")
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    rows = [row for path in args.review_jsonl for row in _read_jsonl(path)]
    if args.strict_only:
        rows = [
            row
            for row in rows
            if row.get("macro_boundary_status") == "strict_review_eligible"
        ]
    if len(rows) != args.expected_rows:
        raise ValueError(f"expected {args.expected_rows} rows, got {len(rows)}")
    replayed, summary = replay_rows(rows)
    replay_path = args.output_dir / "source_replay_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    csv_path = args.output_dir / "source_replay_review_v1.csv"
    _write_jsonl(replay_path, replayed)
    _write_json(summary_path, summary)
    _write_review_csv(csv_path, replayed)
    ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "inputs": {
            path.name: {"path": str(path), "sha256": _sha256(path)}
            for path in args.review_jsonl
        },
        "artifacts": {
            path.name: {"bytes": path.stat().st_size, "sha256": _sha256(path)}
            for path in (replay_path, summary_path, csv_path)
        },
    }
    _write_json(args.output_dir / "hash_ledger_v1.json", ledger)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
