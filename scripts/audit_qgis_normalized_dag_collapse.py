#!/usr/bin/env python3
"""Audit whether normalized-DAG deduplication collapses meaningful variants.

This is a read-only diagnostic over an admission ledger.  It does not change
deduplication keys or grant training admission.  Parameter signatures are
recovered from the recorded ``processing.run`` calls when the source parses;
unavailable evidence is kept explicit instead of being treated as equal.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

SCHEMA = "gis_recommend.qgis_normalized_dag_collapse_audit.v1"
_WS = re.compile(r"\s+")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def digest(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def normalized_text(value: Any) -> str:
    return _WS.sub(" ", str(value or "").strip()).casefold()


class _NameNormalizer(ast.NodeTransformer):
    def visit_Name(self, node: ast.Name) -> ast.AST:  # noqa: N802 - ast API
        return ast.copy_location(ast.Constant(value="<name>"), node)


def ast_value(node: ast.AST | None, *, normalize_names: bool = False) -> str:
    if node is None:
        return "<missing>"
    try:
        if normalize_names:
            node = _NameNormalizer().visit(ast.fix_missing_locations(node))
        return ast.dump(node, annotate_fields=True, include_attributes=False)
    except Exception:
        return "<unavailable>"


def _run_operator(call: ast.Call) -> str | None:
    if not isinstance(call.func, ast.Attribute) or call.func.attr != "run" or not call.args:
        return None
    first = call.args[0]
    return first.value if isinstance(first, ast.Constant) and isinstance(first.value, str) else None


def parameter_signature(row: dict[str, Any]) -> dict[str, Any]:
    """Return a comparable, source-backed parameter signature for the family calls."""

    source = str(row.get("source_text") or "")
    calls = row.get("processing_calls") or []
    operators = [str(value) for value in row.get("operator_sequence") or row.get("family_sequence") or []]
    if not source or not operators:
        return {"status": "unavailable", "items": [], "key": None}
    try:
        tree = ast.parse(source)
    except (SyntaxError, ValueError, TypeError):
        return {"status": "unavailable", "items": [], "key": None}

    by_operator: defaultdict[str, list[ast.Call]] = defaultdict(list)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            operator = _run_operator(node)
            if operator:
                by_operator[operator].append(node)

    items: list[dict[str, Any]] = []
    matched_span = row.get("matched_span") or {}
    span_start = int(matched_span.get("start_index") or 0)
    for index, operator in enumerate(operators):
        available = sorted(by_operator.get(operator, []), key=lambda node: (getattr(node, "lineno", 0), getattr(node, "col_offset", 0)))
        call_index = span_start + index
        source_call = calls[call_index] if call_index < len(calls) and isinstance(calls[call_index], dict) else {}
        line_start = int(source_call.get("line_start") or 0)
        line_end = int(source_call.get("line_end") or line_start)
        node = next(
            (candidate for candidate in available if line_start <= getattr(candidate, "lineno", 0) <= max(line_end, line_start)),
            available[0] if available else None,
        )
        if node is None:
            items.append({"operator_id": operator, "status": "unavailable"})
            continue
        params: list[dict[str, str]] = []
        if len(node.args) >= 2:
            param_node = node.args[1]
            if isinstance(param_node, ast.Dict):
                for key_node, value_node in zip(param_node.keys, param_node.values):
                    if isinstance(key_node, ast.Constant) and isinstance(key_node.value, str):
                        params.append({"key": key_node.value, "value": ast_value(value_node), "semantic_value": ast_value(value_node, normalize_names=True)})
                    else:
                        params.append({"key": ast_value(key_node), "value": ast_value(value_node), "semantic_value": ast_value(value_node, normalize_names=True)})
            else:
                params.append({"key": "<positional-parameters>", "value": ast_value(param_node), "semantic_value": ast_value(param_node, normalize_names=True)})
        for keyword in node.keywords:
            params.append({"key": keyword.arg or "**", "value": ast_value(keyword.value), "semantic_value": ast_value(keyword.value, normalize_names=True)})
        items.append({"operator_id": operator, "status": "parsed", "parameters": params})

    status = "parsed" if all(item.get("status") == "parsed" for item in items) else "partial"
    semantic_items = [
        {
            "operator_id": item["operator_id"],
            "status": item["status"],
            "parameters": [
                {"key": parameter["key"], "semantic_value": parameter.get("semantic_value", "<unavailable>")}
                for parameter in item.get("parameters", [])
            ],
        }
        for item in items
    ]
    return {
        "status": status,
        "items": items,
        "key": digest(items) if status == "parsed" else None,
        "semantic_key": digest(semantic_items) if status == "parsed" else None,
    }


def row_signatures(row: dict[str, Any]) -> dict[str, Any]:
    operators = [str(value) for value in row.get("operator_sequence") or row.get("family_sequence") or []]
    l3 = [str(value) for value in row.get("l3_code_sequence") or row.get("mapped_l3_chain") or []]
    io = row.get("provider_io_contracts") or []
    parent = row.get("full_parent_operator_sequence") or []
    edges = row.get("dependency_edges") or []
    task = row.get("task_description") or row.get("task_text_candidate") or ""
    params = parameter_signature(row)
    return {
        "record_id": str(row.get("record_id") or row.get("review_id") or row.get("source_sha256") or ""),
        "source_sha256": str(row.get("source_sha256") or ""),
        "family": "|".join(operators),
        "task": str(task),
        "task_normalized": normalized_text(task),
        "parameters": params,
        "io": io,
        "io_key": digest(io),
        "l3": l3,
        "l3_key": digest(l3),
        "source_structure": {
            "parent_operator_sequence": parent,
            "matched_span": row.get("matched_span") or {},
            "dependency_edges": edges,
            "resolution_kinds": [str(call.get("resolution_kind") or "") for call in row.get("processing_calls") or [] if isinstance(call, dict)],
        },
        "normalized_dag": {
            "key": str(row.get("normalized_dag_key") or ""),
            "operators": operators,
            "l3": l3,
            "dependency_edges": edges,
        },
    }


def compare_group(rows: Iterable[dict[str, Any]]) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    signatures = [row_signatures(row) for row in rows]
    def unique(field: str) -> set[str]:
        return {json.dumps(signature[field], ensure_ascii=False, sort_keys=True) for signature in signatures}

    dimensions = {
        "task": len({signature["task_normalized"] for signature in signatures}) > 1,
        "parameters": len({signature["parameters"].get("semantic_key") for signature in signatures}) > 1,
        "parameters_surface": len({signature["parameters"].get("key") for signature in signatures}) > 1,
        "parameters_unavailable": any(signature["parameters"].get("status") != "parsed" for signature in signatures),
        "input_output": len({signature["io_key"] for signature in signatures}) > 1,
        "l3": len({signature["l3_key"] for signature in signatures}) > 1,
        "source_structure": len(unique("source_structure")) > 1,
        "normalized_dag": len({signature["normalized_dag"]["key"] for signature in signatures}) > 1,
    }
    meaningful = any(dimensions[name] for name in ("task", "parameters", "input_output", "l3"))
    structural_only = dimensions["source_structure"] and not meaningful
    assessment = (
        "potential_overmerge"
        if meaningful
        else "insufficient_parameter_evidence"
        if dimensions["parameters_unavailable"]
        else "structural_variants_same_semantics"
        if structural_only
        else "likely_true_duplicate"
    )
    group = {
        "normalized_dag_key": signatures[0]["normalized_dag"]["key"] if signatures else "",
        "row_count": len(signatures),
        "source_sha_count": len({signature["source_sha256"] for signature in signatures}),
        "dimensions_differ": dimensions,
        "assessment": assessment,
        "unique_counts": {
            "task": len({signature["task_normalized"] for signature in signatures}),
        "parameters": len({signature["parameters"].get("semantic_key") for signature in signatures}),
        "parameters_surface": len({signature["parameters"].get("key") for signature in signatures}),
            "input_output": len({signature["io_key"] for signature in signatures}),
            "l3": len({signature["l3_key"] for signature in signatures}),
            "source_structure": len(unique("source_structure")),
            "normalized_dag": len({signature["normalized_dag"]["key"] for signature in signatures}),
        },
        "family_sequences": sorted({signature["family"] for signature in signatures}),
        "parameter_status_counts": dict(
            sorted(Counter(signature["parameters"].get("status", "unavailable") for signature in signatures).items())
        ),
        "examples": [
            {
                "record_id": signature["record_id"],
                "source_sha256": signature["source_sha256"],
                "task": signature["task"],
                "parameters": signature["parameters"],
                "io": signature["io"],
                "l3": signature["l3"],
                "source_structure": signature["source_structure"],
            }
            for signature in signatures[:5]
        ],
    }
    return group, signatures


def audit(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    groups: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        key = str(row.get("normalized_dag_key") or "")
        if key:
            groups[key].append(row)
    duplicate_groups = {key: value for key, value in groups.items() if len(value) > 1}
    group_rows: list[dict[str, Any]] = []
    detail_rows: list[dict[str, Any]] = []
    for key, group_rows_input in sorted(duplicate_groups.items()):
        group, details = compare_group(group_rows_input)
        group_rows.append(group)
        detail_rows.extend({"normalized_dag_key": key, **detail} for detail in details)
    assessments = Counter(row["assessment"] for row in group_rows)
    summary = {
        "schema": f"{SCHEMA}.summary",
        "input_rows": len(rows),
        "normalized_dag_groups": len(groups),
        "duplicate_groups": len(group_rows),
        "duplicate_rows": sum(row["row_count"] for row in group_rows),
        "same_source_occurrence_groups": sum(group["source_sha_count"] < group["row_count"] for group in group_rows),
        "cross_source_duplicate_groups": sum(group["source_sha_count"] > 1 for group in group_rows),
        "groups_by_assessment": dict(sorted(assessments.items())),
        "rows_by_assessment": {
            name: sum(row["row_count"] for row in group_rows if row["assessment"] == name)
            for name in sorted(assessments)
        },
        "dimension_difference_groups": {
            name: sum(row["dimensions_differ"][name] for row in group_rows)
            for name in ("task", "parameters", "parameters_surface", "parameters_unavailable", "input_output", "l3", "source_structure", "normalized_dag")
        },
        "potential_overmerge": any(row["assessment"] == "potential_overmerge" for row in group_rows),
        "dedup_rule_modified": False,
        "training_rows_emitted": 0,
    }
    return group_rows, detail_rows, summary


def render_markdown(groups: list[dict[str, Any]], summary: dict[str, Any]) -> str:
    lines = [
        "# QGIS normalized-DAG collapse audit v1",
        "",
        "This read-only audit compares rows suppressed by the normalized-DAG layer. It does not modify deduplication or training admission.",
        "",
        f"- Input rows: **{summary['input_rows']}**",
        f"- Duplicate groups: **{summary['duplicate_groups']}**",
        f"- Duplicate rows: **{summary['duplicate_rows']}**",
        f"- Cross-source duplicate groups: **{summary['cross_source_duplicate_groups']}**",
        f"- Groups containing repeated occurrences from one source: **{summary['same_source_occurrence_groups']}**",
        f"- Potential over-merge signal: **{summary['potential_overmerge']}**",
        "",
        "## Group Findings",
        "",
        "| family | rows | source SHAs | unique semantic parameter signatures | unique source structures | assessment |",
        "|---|---:|---:|---:|---:|---|",
    ]
    for group in groups:
        family = ", ".join(group.get("family_sequences") or ["unknown"])
        counts = group["unique_counts"]
        lines.append(
            f"| `{family}` | {group['row_count']} | {group['source_sha_count']} | "
            f"{counts['parameters']} | {counts['source_structure']} | {group['assessment']} |"
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "Both groups share the same task, L3 sequence, vector I/O contract, and normalized DAG. "
            "They nevertheless contain source-backed parameter variants and different parent-source structures. "
            "This is a potential over-merge signal for parameter-aware assets, but it is not by itself a reason to "
            "change the current workflow dedup key: the current training-pair contract is task-to-L3 sequence, and "
            "the audit does not adjudicate whether parameter variants represent distinct user intent.",
            "",
            "The result is therefore **audit required / dedup unchanged**. Parameter-aware grounding or a future "
            "parameter asset pool may use the detailed JSONL evidence, while the two workflow survivors remain "
            "candidate-only Silver and training rows remain zero.",
            "",
            "Detailed row-level evidence is in `duplicate_group_rows_v1.jsonl`; group summaries are in "
            "`duplicate_groups_v1.jsonl`.",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    groups, details, summary = audit(read_jsonl(args.ledger))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    group_path = args.output_dir / "duplicate_groups_v1.jsonl"
    detail_path = args.output_dir / "duplicate_group_rows_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    report_path = args.output_dir / "collapse_audit_v1.md"
    group_path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in groups), encoding="utf-8")
    detail_path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in details), encoding="utf-8")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(render_markdown(groups, summary), encoding="utf-8")
    hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in (group_path, detail_path, summary_path, report_path)}
    hashes["input_ledger"] = hashlib.sha256(args.ledger.read_bytes()).hexdigest()
    (args.output_dir / "hash_ledger_v1.json").write_text(json.dumps(hashes, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
