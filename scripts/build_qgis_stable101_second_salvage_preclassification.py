#!/usr/bin/env python3
"""Preclassify the second stable101 QGIS review batch from source structure.

This deterministic pass prioritizes human review. It does not adjudicate rows,
grant training admission, call an LLM, or modify the source review package.
"""

from __future__ import annotations

import argparse
import ast
from collections import Counter
import csv
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import tempfile
from typing import Any, Iterable
import warnings


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REVIEW_DIR = (
    ROOT
    / "docs/reports/qgis_mapping_high_impact_blockers_2026-07-24"
    / "stable101_second_source_review_50_v1"
)
DEFAULT_REVIEW_JSONL = DEFAULT_REVIEW_DIR / "stable101_source_review_50_v1.jsonl"
DEFAULT_OUTPUT_DIR = DEFAULT_REVIEW_DIR

CLASS_ORDER = (
    "ready_now",
    "recoverable_call_graph",
    "split_subworkflow",
    "api_pattern_deferred",
    "exclude",
)

HUMAN_FIELDS = (
    "human_workflow_boundary_decision",
    "human_operator_identity_order_decision",
    "human_dependency_decision",
    "human_task_text_usable",
    "human_training_candidate_ready",
    "human_description_generation_ready",
    "human_source_retrieval_ready",
    "human_notes",
)

API_CALL_NAMES = {
    "QgsExpression",
    "QgsFeature",
    "QgsGeometry",
    "QgsRasterCalculator",
    "QgsRasterCalculatorEntry",
    "QgsRasterLayer",
    "QgsSpatialIndex",
    "QgsVectorFileWriter",
    "QgsVectorLayer",
    "edit",
}
API_CALL_SUFFIXES = (
    ".addAttribute",
    ".addAttributes",
    ".addFeature",
    ".addFeatures",
    ".changeAttributeValue",
    ".commitChanges",
    ".dataProvider",
    ".deleteAttribute",
    ".getFeatures",
    ".renameAttribute",
    ".selectByExpression",
    ".selectByIds",
    ".setAttribute",
    ".setGeometry",
    ".startEditing",
    ".updateExtents",
    ".updateFeature",
    ".updateFields",
)
API_CALL_PREFIXES = ("gdal.", "np.", "numpy.")
CONTROL_FLOW_NODES = (
    ast.For,
    ast.AsyncFor,
    ast.While,
    ast.If,
    ast.IfExp,
    ast.Match,
    ast.Try,
)

FIELD_ORDER = [
    "review_index",
    "record_id",
    "source_root_id",
    "source_path",
    "relative_path",
    "source_sha256",
    "ordered_operator_ids",
    "mapped_l3_chain",
    "call_sites",
    "task_text",
    "task_text_quality",
    "salvage_class",
    "classification_status",
    "classification_confidence",
    "classification_reason",
    "suggested_next_action",
    "ast_parse_status",
    "ast_chain_alignment_status",
    "matched_call_count",
    "lexical_scopes",
    "control_flow_kinds",
    "call_graph_status",
    "api_pattern_calls",
    "extra_processing_call_count",
    "task_text_review_required",
    "human_confirmation_required",
    *HUMAN_FIELDS,
    "training_admission",
    "validation_eligible",
    "test_eligible",
    "production_merge",
]


@dataclass
class Result:
    rows: list[dict[str, Any]]
    report: dict[str, Any]


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _atomic_write_text(path: Path, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def _load_jsonl(path: Path, expected_row_count: int | None) -> list[dict[str, Any]]:
    rows = [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    if expected_row_count is not None and len(rows) != expected_row_count:
        raise ValueError(f"expected {expected_row_count} review rows, got {len(rows)}")
    indices = [int(row["review_index"]) for row in rows]
    if len(indices) != len(set(indices)):
        raise ValueError("review_index values must be unique")
    return sorted(rows, key=lambda row: int(row["review_index"]))


def _expr_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _expr_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""


def _is_processing_run(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call):
        return False
    function_name = _expr_name(node.func)
    return function_name == "processing.run" or function_name.endswith(
        ".processing.run"
    )


def _processing_invocations(tree: ast.AST) -> list[ast.Call]:
    return sorted(
        (node for node in ast.walk(tree) if _is_processing_run(node)),
        key=lambda node: (node.lineno, node.end_lineno or node.lineno),
    )


def _processing_calls(tree: ast.AST) -> list[ast.Call]:
    calls: list[ast.Call] = []
    for node in _processing_invocations(tree):
        if not node.args or not isinstance(node.args[0], ast.Constant):
            continue
        if ":" not in str(node.args[0].value):
            continue
        calls.append(node)
    return sorted(calls, key=lambda node: (node.lineno, node.end_lineno or node.lineno))


def _operator_id(call: ast.Call) -> str:
    return str(call.args[0].value).strip().lower()


def _parents(tree: ast.AST) -> dict[ast.AST, ast.AST]:
    result: dict[ast.AST, ast.AST] = {}
    for node in ast.walk(tree):
        for child in ast.iter_child_nodes(node):
            result[child] = node
    return result


def _scope_key(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> str:
    current = node
    if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
        names = [current.name]
        ancestor = current
        while ancestor in parents:
            ancestor = parents[ancestor]
            if isinstance(ancestor, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                names.append(ancestor.name)
        return ".".join(reversed(names)) + f"@{current.lineno}"
    while current in parents:
        current = parents[current]
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names = [current.name]
            ancestor = current
            while ancestor in parents:
                ancestor = parents[ancestor]
                if isinstance(ancestor, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                    names.append(ancestor.name)
            return ".".join(reversed(names)) + f"@{current.lineno}"
    return "<module>"


def _match_calls(
    processing_calls: list[ast.Call], call_sites: list[dict[str, Any]]
) -> tuple[list[ast.Call], list[str]]:
    matched: list[ast.Call] = []
    failures: list[str] = []
    used: set[int] = set()
    for site in call_sites:
        operator_id = str(site.get("operator_id", "")).strip().lower()
        line_start = int(site.get("line_start", 0))
        line_end = int(site.get("line_end", line_start))
        candidates = [
            call
            for call in processing_calls
            if id(call) not in used
            and _operator_id(call) == operator_id
            and call.lineno <= line_end
            and int(call.end_lineno or call.lineno) >= line_start
        ]
        if not candidates:
            failures.append(f"{operator_id}@{line_start}-{line_end}")
            continue
        chosen = min(candidates, key=lambda call: abs(call.lineno - line_start))
        used.add(id(chosen))
        matched.append(chosen)
    return matched, failures


class _DirectCallVisitor(ast.NodeVisitor):
    def __init__(self, root: ast.AST) -> None:
        self.root = root
        self.names: set[str] = set()

    def visit_Call(self, node: ast.Call) -> None:
        name = _expr_name(node.func)
        if name:
            self.names.add(name.rsplit(".", 1)[-1])
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        if node is self.root:
            self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        if node is self.root:
            self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        if node is self.root:
            self.generic_visit(node)

    def visit_Lambda(self, node: ast.Lambda) -> None:
        if node is self.root:
            self.generic_visit(node)


def _call_graph_status(tree: ast.AST, candidate_scopes: set[str]) -> str:
    if len(candidate_scopes) <= 1:
        return "single_scope"
    parents = _parents(tree)
    definitions = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    key_by_node = {node: _scope_key(node, parents) for node in definitions}
    nodes_by_name: dict[str, list[ast.AST]] = {}
    for node in definitions:
        nodes_by_name.setdefault(node.name, []).append(node)

    graph: dict[str, set[str]] = {"<module>": set()}
    for key in key_by_node.values():
        graph.setdefault(key, set())

    roots: list[tuple[str, ast.AST]] = [("<module>", tree)]
    roots.extend((key_by_node[node], node) for node in definitions)
    for caller_key, root in roots:
        visitor = _DirectCallVisitor(root)
        if isinstance(root, ast.Module):
            for statement in root.body:
                if not isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    visitor.visit(statement)
        else:
            visitor.visit(root)
        for name in visitor.names:
            for target in nodes_by_name.get(name, []):
                graph[caller_key].add(key_by_node[target])

    for root_key in graph:
        reachable: set[str] = set()
        pending = [root_key]
        while pending:
            current = pending.pop()
            if current in reachable:
                continue
            reachable.add(current)
            pending.extend(graph.get(current, set()) - reachable)
        if candidate_scopes <= reachable:
            return f"connected_from:{root_key}"
    return "disconnected_candidate_scopes"


def _control_flow_kinds(
    calls: Iterable[ast.Call], parents: dict[ast.AST, ast.AST]
) -> list[str]:
    kinds: set[str] = set()
    for call in calls:
        current: ast.AST = call
        while current in parents:
            current = parents[current]
            if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.Module)):
                break
            if isinstance(current, CONTROL_FLOW_NODES):
                kinds.add(type(current).__name__)
    return sorted(kinds)


def _is_descendant_of(node: ast.AST, ancestors: set[ast.AST], parents: dict[ast.AST, ast.AST]) -> bool:
    current = node
    while current in parents:
        current = parents[current]
        if current in ancestors:
            return True
    return False


def _is_api_pattern_call(name: str) -> bool:
    return (
        name in API_CALL_NAMES
        or name.startswith(API_CALL_PREFIXES)
        or name.endswith(API_CALL_SUFFIXES)
    )


def _api_pattern_calls(
    tree: ast.AST,
    matched: list[ast.Call],
    parents: dict[ast.AST, ast.AST],
) -> list[str]:
    if not matched:
        return []
    first_line = min(call.lineno for call in matched)
    last_line = max(int(call.end_lineno or call.lineno) for call in matched)
    matched_set: set[ast.AST] = set(matched)
    evidence: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or node in matched_set:
            continue
        if not first_line <= node.lineno <= last_line:
            continue
        if _is_descendant_of(node, matched_set, parents):
            continue
        name = _expr_name(node.func)
        if name and _is_api_pattern_call(name):
            evidence.add(f"{name}@{node.lineno}")
    return sorted(evidence, key=lambda value: (int(value.rsplit("@", 1)[1]), value))


def _base_output_row(review_row: dict[str, Any]) -> dict[str, Any]:
    output = {
        field: review_row.get(field, "")
        for field in (
            "review_index",
            "record_id",
            "source_root_id",
            "source_path",
            "relative_path",
            "source_sha256",
            "ordered_operator_ids",
            "mapped_l3_chain",
            "call_sites",
            "task_text",
            "task_text_quality",
            *HUMAN_FIELDS,
        )
    }
    output.update(
        {
            "classification_status": "preclassification_only",
            "human_confirmation_required": True,
            "training_admission": "not_granted",
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
            "task_text_review_required": review_row.get("task_text_quality")
            != "usable_seed_text",
        }
    )
    return output


def _excluded_row(
    review_row: dict[str, Any], *, reason: str, parse_status: str, matched_count: int = 0
) -> dict[str, Any]:
    output = _base_output_row(review_row)
    output.update(
        {
            "salvage_class": "exclude",
            "classification_confidence": "high",
            "classification_reason": reason,
            "suggested_next_action": "exclude_current_chain_then_review_source_separately",
            "ast_parse_status": parse_status,
            "ast_chain_alignment_status": "failed",
            "matched_call_count": matched_count,
            "lexical_scopes": [],
            "control_flow_kinds": [],
            "call_graph_status": "not_evaluated",
            "api_pattern_calls": [],
            "extra_processing_call_count": 0,
        }
    )
    return output


def _classify_row(review_row: dict[str, Any]) -> dict[str, Any]:
    source_path = Path(str(review_row.get("source_path", "")))
    if not source_path.is_file():
        return _excluded_row(
            review_row, reason="source file is missing", parse_status="not_parsed"
        )
    actual_sha = _sha256(source_path)
    if actual_sha != review_row.get("source_sha256"):
        return _excluded_row(
            review_row, reason="source SHA256 no longer matches review provenance", parse_status="not_parsed"
        )
    if review_row.get("joined_source_status") != "joined_and_chain_verified":
        return _excluded_row(
            review_row, reason="source review row is not joined_and_chain_verified", parse_status="not_parsed"
        )
    if review_row.get("source_snippet_contains_all_ops") is not True:
        return _excluded_row(
            review_row, reason="source snippet does not contain the full proposed chain", parse_status="not_parsed"
        )

    source_text = source_path.read_text(encoding="utf-8", errors="replace")
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", SyntaxWarning)
            tree = ast.parse(source_text)
    except SyntaxError as error:
        return _excluded_row(
            review_row,
            reason=f"source is not parseable Python: line {error.lineno}",
            parse_status="syntax_error",
        )

    call_sites = list(review_row.get("call_sites") or [])
    expected_ops = [str(value).lower() for value in review_row.get("ordered_operator_ids") or []]
    site_ops = [str(site.get("operator_id", "")).lower() for site in call_sites]
    if expected_ops != site_ops:
        return _excluded_row(
            review_row,
            reason="call-site operator order differs from the proposed operator chain",
            parse_status="parsed",
        )

    processing_invocations = _processing_invocations(tree)
    processing_calls = _processing_calls(tree)
    matched, failures = _match_calls(processing_calls, call_sites)
    if failures or len(matched) != len(expected_ops):
        missing = ", ".join(failures) if failures else "unknown alignment failure"
        return _excluded_row(
            review_row,
            reason=f"full executable AST chain could not be aligned: {missing}",
            parse_status="parsed",
            matched_count=len(matched),
        )

    parents = _parents(tree)
    scopes = [_scope_key(call, parents) for call in matched]
    unique_scopes = set(scopes)
    call_graph_status = _call_graph_status(tree, unique_scopes)
    control_flow = _control_flow_kinds(matched, parents)
    api_calls = _api_pattern_calls(tree, matched, parents)
    matched_ids = {id(call) for call in matched}
    first_line = min(call.lineno for call in matched)
    last_line = max(int(call.end_lineno or call.lineno) for call in matched)
    extra_processing = sum(
        1
        for call in processing_invocations
        if id(call) not in matched_ids and first_line <= call.lineno <= last_line
    )

    if len(unique_scopes) > 1:
        if call_graph_status.startswith("connected_from:"):
            salvage_class = "recoverable_call_graph"
            reason = "candidate calls span multiple lexical scopes connected by a local entrypoint"
            action = "recover_entrypoint_call_graph_then_human_review"
            confidence = "medium"
        else:
            salvage_class = "split_subworkflow"
            reason = "candidate calls span disconnected lexical scopes"
            action = "split_by_lexical_scope_then_human_review"
            confidence = "high"
    elif api_calls:
        salvage_class = "api_pattern_deferred"
        reason = "low-level QGIS/GDAL/NumPy transformations occur inside the candidate boundary"
        action = "review_api_pattern_and_processing_dependency"
        confidence = "medium"
    elif control_flow or extra_processing:
        salvage_class = "recoverable_call_graph"
        reason = "branches, loops, exception paths, or extra Processing calls require DAG recovery"
        action = "recover_local_control_flow_dag_then_human_review"
        confidence = "medium"
    else:
        salvage_class = "ready_now"
        reason = "one aligned lexical scope with no detected branch, extra Processing call, or API intermediate"
        action = "prioritize_for_human_boundary_dependency_and_text_review"
        confidence = "medium"

    output = _base_output_row(review_row)
    output.update(
        {
            "salvage_class": salvage_class,
            "classification_confidence": confidence,
            "classification_reason": reason,
            "suggested_next_action": action,
            "ast_parse_status": "parsed",
            "ast_chain_alignment_status": "matched_full_executable_chain",
            "matched_call_count": len(matched),
            "lexical_scopes": scopes,
            "control_flow_kinds": control_flow,
            "call_graph_status": call_graph_status,
            "api_pattern_calls": api_calls,
            "extra_processing_call_count": extra_processing,
        }
    )
    return output


def build_preclassification(
    *, review_jsonl_path: Path, expected_row_count: int | None = 50
) -> Result:
    review_rows = _load_jsonl(review_jsonl_path, expected_row_count)
    rows = [_classify_row(row) for row in review_rows]
    class_counts = Counter(row["salvage_class"] for row in rows)
    report = {
        "schema": "gis_recommend.qgis_stable101_second_salvage_preclassification.v1",
        "inputs": {
            "review_jsonl": str(Path(review_jsonl_path)),
            "review_jsonl_sha256": _sha256(Path(review_jsonl_path)),
        },
        "counts": {
            "rows": len(rows),
            "salvage_classes": {name: class_counts[name] for name in CLASS_ORDER},
            "ast_full_chain_aligned": sum(
                row["ast_chain_alignment_status"] == "matched_full_executable_chain"
                for row in rows
            ),
            "task_text_review_required": sum(
                bool(row["task_text_review_required"]) for row in rows
            ),
        },
        "salvage_classes": {name: class_counts[name] for name in CLASS_ORDER},
        "class_review_indices": {
            name: [row["review_index"] for row in rows if row["salvage_class"] == name]
            for name in CLASS_ORDER
        },
        "decision": {
            "classification_status": "preclassification_only",
            "human_confirmation_required": True,
            "training_admission": "not_granted",
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
            "llm_called": False,
            "next_gate": "human_review_in_batches_of_10",
        },
    }
    return Result(rows=rows, report=report)


def _json_text(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _csv_value(value: Any) -> Any:
    if isinstance(value, (list, dict)):
        return _json_text(value)
    if isinstance(value, bool):
        return "true" if value else "false"
    return value


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELD_ORDER)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field, "")) for field in FIELD_ORDER})


def _render_report(report: dict[str, Any]) -> str:
    lines = [
        "# stable101 Second Batch Salvage Preclassification",
        "",
        "This is deterministic machine preclassification for human review prioritization.",
        "It is not adjudication and grants no training, validation, test, or production admission.",
        "No LLM was called.",
        "",
        "## Counts",
        "",
        f"- Rows: {report['counts']['rows']}",
        f"- Full executable AST chains aligned: {report['counts']['ast_full_chain_aligned']}",
        f"- Task text review required: {report['counts']['task_text_review_required']}",
        f"- Classes: {report['counts']['salvage_classes']}",
        "",
        "## Review Order",
        "",
    ]
    for name in CLASS_ORDER:
        lines.append(f"- {name}: {report['class_review_indices'][name]}")
    lines.extend(
        [
            "",
            "## Rule Boundary",
            "",
            "- ready_now means structurally ready for human review, not training-ready.",
            "- recoverable_call_graph requires deterministic entrypoint or DAG recovery.",
            "- split_subworkflow contains disconnected lexical scopes that must be reviewed separately.",
            "- api_pattern_deferred contains low-level transformations inside the proposed boundary.",
            "- exclude means the current proposed chain lacks a complete executable AST alignment.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_outputs(result: Result, output_dir: Path) -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "csv": output_dir / "second_salvage_preclass_v1.csv",
        "jsonl": output_dir / "second_salvage_preclass_v1.jsonl",
        "summary": output_dir / "second_salvage_preclass_summary_v1.json",
        "report": output_dir / "second_salvage_preclass_report_v1.md",
        "hash_ledger": output_dir / "second_salvage_preclass_hash_v1.json",
    }
    _write_csv(paths["csv"], result.rows)
    _atomic_write_text(
        paths["jsonl"],
        "".join(_json_text(row) + "\n" for row in result.rows),
    )
    _atomic_write_text(paths["summary"], json.dumps(result.report, ensure_ascii=False, indent=2, sort_keys=True))
    _atomic_write_text(paths["report"], _render_report(result.report))
    ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "source_inputs": {
            "review_jsonl": {
                "path": result.report["inputs"]["review_jsonl"],
                "sha256": result.report["inputs"]["review_jsonl_sha256"],
            }
        },
        "artifacts": {
            path.name: {
                "path": str(path),
                "sha256": _sha256(path),
                "bytes": path.stat().st_size,
            }
            for key, path in paths.items()
            if key != "hash_ledger"
        },
    }
    _atomic_write_text(paths["hash_ledger"], json.dumps(ledger, ensure_ascii=False, indent=2, sort_keys=True))
    return paths


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-jsonl", type=Path, default=DEFAULT_REVIEW_JSONL)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--expected-row-count", type=int, default=50)
    args = parser.parse_args(argv)
    result = build_preclassification(
        review_jsonl_path=args.review_jsonl,
        expected_row_count=args.expected_row_count,
    )
    return write_outputs(result, args.output_dir)


if __name__ == "__main__":
    main()
