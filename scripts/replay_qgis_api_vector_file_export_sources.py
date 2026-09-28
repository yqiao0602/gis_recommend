#!/usr/bin/env python3
"""Replay vector-file export candidates against read-only QGIS sources."""

from __future__ import annotations

import argparse
import ast
import csv
import hashlib
import io
import json
import tempfile
import tokenize
from collections import Counter
from pathlib import Path
from typing import Any

SCHEMA = "gis_recommend.qgis_api_vector_file_export_source_replay.v1"
SUMMARY_SCHEMA = "gis_recommend.qgis_api_vector_file_export_source_replay_summary.v1"
RULE_ID = "vector-file-export-source-replay-v1"
WRITER_METHODS = {
    "writeasvectorformat",
    "writeasvectorformatv2",
    "writeasvectorformatv3",
}
CONTROL_FLOW_NODES = (
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.If,
    ast.Try,
    ast.Match,
)


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


def _source_text(raw: bytes) -> str:
    encoding, _ = tokenize.detect_encoding(io.BytesIO(raw).readline)
    return raw.decode(encoding)


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


def _literal_string(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _literal_bool(node: ast.AST | None) -> bool | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, bool):
        return node.value
    return None


def _writer_argument(call: ast.Call, index: int, *keyword_names: str) -> ast.AST | None:
    if len(call.args) > index:
        return call.args[index]
    for keyword in call.keywords:
        if keyword.arg in keyword_names:
            return keyword.value
    return None


def _known_format(values: list[str]) -> str:
    markers = {
        "csv": "CSV",
        "esri shapefile": "ESRI Shapefile",
        "flatgeobuf": "FlatGeobuf",
        "geojson": "GeoJSON",
        "gpkg": "GPKG",
        "geopackage": "GPKG",
        "kml": "KML",
        "sqlite": "SQLite",
        "xlsx": "XLSX",
    }
    for value in values:
        lowered = value.lower()
        for marker, canonical in markers.items():
            if marker in lowered:
                return canonical
    return "dynamic_vector_format"


def _parent_map(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    return {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}


def _control_flow_kinds(
    node: ast.AST,
    parents: dict[ast.AST, ast.AST],
) -> list[str]:
    kinds: list[str] = []
    current = parents.get(node)
    while current is not None and not isinstance(
        current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Lambda)
    ):
        if isinstance(current, CONTROL_FLOW_NODES):
            kinds.append(type(current).__name__)
        current = parents.get(current)
    return sorted(set(kinds))


def _same_scope_nodes(
    tree: ast.AST,
    scopes: list[tuple[int, int, str]],
    scope: str,
) -> list[ast.AST]:
    return [
        node
        for node in ast.walk(tree)
        if hasattr(node, "lineno")
        and _scope_for_line(int(node.lineno), scopes) == scope
    ]


def _latest_name_assignment(
    nodes: list[ast.AST],
    name: str,
    before_line: int,
) -> tuple[int, ast.AST] | None:
    definitions: list[tuple[int, ast.AST]] = []
    for node in nodes:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        line = int(node.lineno)
        if line >= before_line:
            continue
        value = node.value
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        if any(isinstance(target, ast.Name) and target.id == name for target in targets):
            definitions.append((line, value))
    return max(definitions, default=None, key=lambda item: item[0])


def _option_assignments(
    nodes: list[ast.AST],
    option_name: str,
    start_line: int,
    before_line: int,
) -> dict[str, tuple[int, ast.AST]]:
    assignments: dict[str, tuple[int, ast.AST]] = {}
    for node in nodes:
        if not isinstance(node, (ast.Assign, ast.AnnAssign)):
            continue
        line = int(node.lineno)
        if line <= start_line or line >= before_line:
            continue
        targets = node.targets if isinstance(node, ast.Assign) else [node.target]
        for target in targets:
            if (
                isinstance(target, ast.Attribute)
                and isinstance(target.value, ast.Name)
                and target.value.id == option_name
            ):
                assignments[target.attr.lower()] = (line, node.value)
    return assignments


def _assignment_control_flow(
    nodes: list[ast.AST],
    parents: dict[ast.AST, ast.AST],
    lines: list[int],
) -> list[str]:
    return sorted(
        {
            kind
            for node in nodes
            if isinstance(node, (ast.Assign, ast.AnnAssign))
            and int(node.lineno) in lines
            for kind in _control_flow_kinds(node, parents)
        }
    )


def _is_save_options_constructor(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and _method_name(_call_name(node)) == "savevectoroptions"
    )


def _old_writer_has_reprojection(call: ast.Call, layer: ast.AST) -> bool:
    destination_crs = _writer_argument(call, 3, "destCRS", "destinationCrs")
    if destination_crs is None or (
        isinstance(destination_crs, ast.Constant) and destination_crs.value is None
    ):
        return False
    if (
        isinstance(destination_crs, ast.Call)
        and _method_name(_call_name(destination_crs)) == "qgscoordinatereferencesystem"
        and not destination_crs.args
        and not destination_crs.keywords
    ):
        return False
    expected = f"{ast.unparse(layer)}.crs()"
    return ast.unparse(destination_crs) != expected


def _base_result(row: dict[str, Any], status: str) -> dict[str, Any]:
    return {
        **row,
        "schema": SCHEMA,
        "source_replay_rule_id": RULE_ID,
        "source_replay_status": status,
        "source_replay_verification": "not_verified",
        "writer_evidence": [],
        "source_region": "",
        "source_replay_snippet": "",
        "mapping_status": "not_started",
        "description_fidelity": "not_started",
        "deduplication": "not_started",
        "training_admission": "not_granted_source_replay_only",
        "training_row_emitted": False,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }


def _with_source_context(
    result: dict[str, Any],
    row: dict[str, Any],
    text: str,
    first_line: int,
    last_line: int,
) -> dict[str, Any]:
    source_lines = text.splitlines()
    snippet_start = max(1, first_line - 2)
    snippet_end = min(len(source_lines), last_line + 2)
    result.update(
        {
            "source_replay_verification": "verified_sha256",
            "source_region": (
                f"{row.get('source_sha256')}:{first_line}-{last_line}"
            ),
            "source_replay_snippet": "\n".join(
                f"{line_number} | {source_lines[line_number - 1]}"
                for line_number in range(snippet_start, snippet_end + 1)
            ),
        }
    )
    return result


def replay_row(row: dict[str, Any]) -> dict[str, Any]:
    path = Path(str(row.get("source_path") or ""))
    if not path.is_file():
        return _base_result(row, "deferred_source_not_found")
    raw = path.read_bytes()
    if hashlib.sha256(raw).hexdigest() != str(row.get("source_sha256") or ""):
        return _base_result(row, "deferred_source_sha256_mismatch")
    try:
        text = _source_text(raw)
        tree = ast.parse(text)
    except (SyntaxError, UnicodeDecodeError, tokenize.TokenError):
        result = _base_result(row, "deferred_source_parse_failure")
        result["source_replay_verification"] = "verified_sha256"
        return result

    expected_lines = {int(line) for line in row.get("writer_source_lines") or []}
    calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and _method_name(_call_name(node)) in WRITER_METHODS
        and any(
            int(node.lineno) <= line <= int(getattr(node, "end_lineno", node.lineno))
            for line in expected_lines
        )
    ]
    if not expected_lines or not calls:
        result = _base_result(row, "deferred_writer_call_span_not_found")
        result["source_replay_verification"] = "verified_sha256"
        return result
    if len(calls) != 1:
        result = _base_result(row, "deferred_ambiguous_writer_calls")
        return _with_source_context(
            result,
            row,
            text,
            min(int(call.lineno) for call in calls),
            max(int(getattr(call, "end_lineno", call.lineno)) for call in calls),
        )

    call = calls[0]
    method = _method_name(_call_name(call))
    layer = _writer_argument(call, 0, "layer", "layerToWrite")
    output = _writer_argument(call, 1, "fileName", "filename")
    if layer is None or output is None:
        result = _base_result(row, "deferred_incomplete_writer_arguments")
        return _with_source_context(
            result,
            row,
            text,
            int(call.lineno),
            int(getattr(call, "end_lineno", call.lineno)),
        )

    parents = _parent_map(tree)
    control_flow = _control_flow_kinds(call, parents)
    if control_flow:
        result = _base_result(row, "deferred_control_flow_writer")
        result["writer_evidence"] = [{"control_flow": control_flow}]
        return _with_source_context(
            result,
            row,
            text,
            int(call.lineno),
            int(getattr(call, "end_lineno", call.lineno)),
        )

    scopes = _scope_index(tree)
    scope = _scope_for_line(int(call.lineno), scopes)
    nodes = _same_scope_nodes(tree, scopes, scope)
    option_lines: list[int] = []
    option_values: dict[str, str] = {}
    writer_format = "dynamic_vector_format"
    only_selected: bool | None = None

    if method in {"writeasvectorformatv2", "writeasvectorformatv3"}:
        options = _writer_argument(call, 3, "options")
        if options is None:
            result = _base_result(row, "deferred_unresolved_writer_options")
            return _with_source_context(
                result,
                row,
                text,
                int(call.lineno),
                int(getattr(call, "end_lineno", call.lineno)),
            )
        assignments: dict[str, tuple[int, ast.AST]] = {}
        if isinstance(options, ast.Name):
            definition = _latest_name_assignment(nodes, options.id, int(call.lineno))
            if definition is None or not _is_save_options_constructor(definition[1]):
                result = _base_result(row, "deferred_unresolved_writer_options")
                return _with_source_context(
                    result,
                    row,
                    text,
                    int(call.lineno),
                    int(getattr(call, "end_lineno", call.lineno)),
                )
            option_lines.append(definition[0])
            assignments = _option_assignments(
                nodes,
                options.id,
                definition[0],
                int(call.lineno),
            )
        elif not _is_save_options_constructor(options):
            result = _base_result(row, "deferred_unresolved_writer_options")
            return _with_source_context(
                result,
                row,
                text,
                int(call.lineno),
                int(getattr(call, "end_lineno", call.lineno)),
            )
        if any(key in assignments for key in ("destcrs", "ct")):
            result = _base_result(row, "deferred_writer_reprojection")
            result["writer_evidence"] = [
                {
                    "reprojection_options": sorted(
                        {"destcrs", "ct"} & assignments.keys()
                    )
                }
            ]
            option_line = min(
                assignments[key][0]
                for key in ("destcrs", "ct")
                if key in assignments
            )
            return _with_source_context(
                result,
                row,
                text,
                option_line,
                int(getattr(call, "end_lineno", call.lineno)),
            )
        option_lines.extend(line for line, _ in assignments.values())
        option_values = {
            key: ast.unparse(value) for key, (_, value) in sorted(assignments.items())
        }
        driver = assignments.get("drivername")
        if driver is not None:
            writer_format = _known_format([_literal_string(driver[1]) or ""])
        selected = assignments.get("onlyselectedfeatures")
        if selected is None:
            selected = assignments.get("onlyselected")
        if selected is not None:
            only_selected = _literal_bool(selected[1])
    else:
        legacy_options = _writer_argument(call, 2, "options")
        legacy_definition: tuple[int, ast.AST] | None = None
        if isinstance(legacy_options, ast.Name):
            legacy_definition = _latest_name_assignment(
                nodes, legacy_options.id, int(call.lineno)
            )
        uses_options_overload = _is_save_options_constructor(legacy_options) or (
            legacy_definition is not None
            and _is_save_options_constructor(legacy_definition[1])
        )
        if uses_options_overload:
            assignments = {}
            if isinstance(legacy_options, ast.Name) and legacy_definition is not None:
                option_lines.append(legacy_definition[0])
                assignments = _option_assignments(
                    nodes,
                    legacy_options.id,
                    legacy_definition[0],
                    int(call.lineno),
                )
            if any(key in assignments for key in ("destcrs", "ct")):
                result = _base_result(row, "deferred_writer_reprojection")
                result["writer_evidence"] = [
                    {
                        "reprojection_options": sorted(
                            {"destcrs", "ct"} & assignments.keys()
                        )
                    }
                ]
                return _with_source_context(
                    result,
                    row,
                    text,
                    min(line for line, _ in assignments.values()),
                    int(getattr(call, "end_lineno", call.lineno)),
                )
            option_lines.extend(line for line, _ in assignments.values())
            option_values = {
                key: ast.unparse(value)
                for key, (_, value) in sorted(assignments.items())
            }
            driver = assignments.get("drivername")
            if driver is not None:
                writer_format = _known_format([_literal_string(driver[1]) or ""])
            selected = assignments.get("onlyselectedfeatures")
            if selected is None:
                selected = assignments.get("onlyselected")
            if selected is not None:
                only_selected = _literal_bool(selected[1])
        else:
            if len(call.args) == 3 and not call.keywords:
                result = _base_result(row, "deferred_unresolved_writer_options")
                return _with_source_context(
                    result,
                    row,
                    text,
                    int(call.lineno),
                    int(getattr(call, "end_lineno", call.lineno)),
                )
            if _old_writer_has_reprojection(call, layer):
                result = _base_result(row, "deferred_writer_reprojection")
                return _with_source_context(
                    result,
                    row,
                    text,
                    int(call.lineno),
                    int(getattr(call, "end_lineno", call.lineno)),
                )
            driver = _writer_argument(call, 4, "driverName")
            writer_format = _known_format([_literal_string(driver) or ""])
            only_selected = _literal_bool(
                _writer_argument(call, 5, "onlySelected", "onlySelectedFeatures")
            )

    option_control_flow = _assignment_control_flow(nodes, parents, option_lines)
    if option_control_flow:
        result = _base_result(row, "deferred_control_flow_writer_options")
        result["writer_evidence"] = [
            {"option_control_flow": option_control_flow}
        ]
        return _with_source_context(
            result,
            row,
            text,
            min(option_lines),
            int(getattr(call, "end_lineno", call.lineno)),
        )

    first_line = min([int(call.lineno), *option_lines])
    last_line = max([int(getattr(call, "end_lineno", call.lineno)), *option_lines])
    evidence = {
        "writer_method": method,
        "writer_line_start": int(call.lineno),
        "writer_line_end": int(getattr(call, "end_lineno", call.lineno)),
        "lexical_scope": scope,
        "input_layer_expression": ast.unparse(layer),
        "output_path_expression": ast.unparse(output),
        "writer_format": writer_format,
        "only_selected_features": only_selected,
        "option_assignments": option_values,
        "control_flow": [],
    }
    result = _base_result(row, "verified_complete_vector_file_export")
    result.update(
        {
            "writer_evidence": [evidence],
        }
    )
    return _with_source_context(result, row, text, first_line, last_line)


def replay_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    replayed = [replay_row(row) for row in rows]
    status_counts = Counter(row["source_replay_status"] for row in replayed)
    split_counts = Counter(
        (str(row.get("review_split") or "unknown"), row["source_replay_status"])
        for row in replayed
    )
    summary = {
        "schema": SUMMARY_SCHEMA,
        "source_replay_rule_id": RULE_ID,
        "input_rows": len(rows),
        "source_replay_status_counts": dict(sorted(status_counts.items())),
        "split_status_counts": {
            f"{split_name}:{status}": count
            for (split_name, status), count in sorted(split_counts.items())
        },
        "verified_source_sha256_rows": sum(
            row["source_replay_verification"] == "verified_sha256" for row in replayed
        ),
        "verified_complete_rows": status_counts.get(
            "verified_complete_vector_file_export", 0
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


def select_rows(
    rows: list[dict[str, Any]],
    *,
    family_boundary_status: str | None,
) -> list[dict[str, Any]]:
    if family_boundary_status is None:
        return rows
    return [
        row
        for row in rows
        if row.get("family_boundary_status") == family_boundary_status
    ]


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
        "source_authority_key",
        "proposed_l3_code",
        "source_replay_status",
        "source_replay_verification",
        "source_region",
        "writer_evidence",
        "source_replay_snippet",
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
                    "writer_evidence": json.dumps(
                        row["writer_evidence"], ensure_ascii=False
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
    parser.add_argument("--expected-rows", type=int, default=60)
    parser.add_argument("--family-boundary-status")
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    manifest_rows = [row for path in args.review_jsonl for row in _read_jsonl(path)]
    rows = select_rows(
        manifest_rows,
        family_boundary_status=args.family_boundary_status,
    )
    if len(rows) != args.expected_rows:
        raise ValueError(f"expected {args.expected_rows} rows, got {len(rows)}")
    replayed, summary = replay_rows(rows)
    summary["input_manifest_rows"] = len(manifest_rows)
    summary["family_boundary_status_filter"] = args.family_boundary_status
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
