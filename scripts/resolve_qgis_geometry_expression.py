#!/usr/bin/env python3
"""Resolve a narrow, deterministic subset of QGIS geometry expressions.

This module is deliberately fail-closed.  The ``geometrybyexpression``
operator is not mapped from its id; only a top-level expression whose
semantics are represented by an existing L3 family can produce a candidate.
The resolver is report-only and never grants taxonomy or training admission.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gis_recommend.data.qgis_processing_ast import processing_parameter_nodes


GEOMETRY_ARG = {"$geometry", "geometry(@feature)"}

# The whitelist is intentionally small.  These are existing stable families;
# adding a QGIS expression function requires a separate source-reviewed rule.
WHITELIST: dict[str, tuple[str, str, int]] = {
    "buffer": ("L3_02_01_01", "Buffer", 2),
    "centroid": ("L3_02_05_11", "Feature to Point", 1),
    "point_on_surface": ("L3_02_05_11", "Feature to Point", 1),
    "start_point": ("L3_02_05_11", "Feature to Point", 1),
    "end_point": ("L3_02_05_11", "Feature to Point", 1),
    "line_interpolate_point": ("L3_02_05_11", "Feature to Point", 2),
    "simplify": ("L3_02_05_01", "Simplify", 2),
}


def _strip_outer(text: str) -> str:
    """Remove balanced outer parentheses without changing inner text."""
    value = text.strip()
    while value.startswith("(") and value.endswith(")"):
        depth = 0
        quote = ""
        balanced = True
        for index, char in enumerate(value):
            if quote:
                if char == quote and (index == 0 or value[index - 1] != "\\"):
                    quote = ""
                continue
            if char in "'\"":
                quote = char
            elif char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0 and index != len(value) - 1:
                    balanced = False
                    break
                if depth < 0:
                    balanced = False
                    break
        if not balanced or depth != 0 or quote:
            break
        value = value[1:-1].strip()
    return value


def _split_args(text: str) -> list[str] | None:
    """Split function arguments at top-level commas, respecting QGIS quotes."""
    args: list[str] = []
    start = 0
    depth = 0
    quote = ""
    for index, char in enumerate(text):
        if quote:
            if char == quote and (index == 0 or text[index - 1] != "\\"):
                quote = ""
            continue
        if char in "'\"":
            quote = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth < 0:
                return None
        elif char == "," and depth == 0:
            args.append(text[start:index].strip())
            start = index + 1
    if quote or depth != 0:
        return None
    tail = text[start:].strip()
    if not tail:
        return None
    args.append(tail)
    return args


def _top_level_call(expression: str) -> tuple[str, list[str]] | None:
    value = _strip_outer(expression)
    match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)\s*\((.*)\)", value, flags=re.S)
    if not match:
        return None
    name, body = match.groups()
    # The final closing parenthesis must close the initial call.  This rejects
    # trailing arithmetic, concatenation, and unbalanced nested expressions.
    depth = 0
    quote = ""
    opening = value.find("(")
    for index, char in enumerate(value[opening:], start=opening):
        if quote:
            if char == quote and value[index - 1] != "\\":
                quote = ""
        elif char in "'\"":
            quote = char
        elif char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0 and index != len(value) - 1:
                return None
            if depth < 0:
                return None
    if quote or depth != 0:
        return None
    args = _split_args(body)
    return (name.lower(), args) if args else None


def _normalise(value: str) -> str:
    return re.sub(r"\s+", " ", value.strip()).lower()


def resolve_geometry_expression(expression: str | None) -> dict[str, Any]:
    """Return a candidate mapping or a deterministic deferred decision."""
    base: dict[str, Any] = {
        "schema": "gis_recommend.qgis_geometry_expression_resolution.v1",
        "operator_id": "native:geometrybyexpression",
        "expression": expression or "",
        "normalized_expression": _normalise(expression or ""),
        "status": "deferred",
        "candidate_l3_code": "",
        "candidate_l3_name": "",
        "required_argument_count": None,
        "rule_id": "",
        "reason": "",
        "mapping_admission": "not_granted",
        "training_admission": "not_granted",
        "training_row_emitted": False,
    }
    if not isinstance(expression, str) or not expression.strip():
        base["reason"] = "expression_missing"
        return base
    # Python-side interpolation/property objects are not QGIS expression AST.
    if any(marker in expression for marker in ("QgsProperty", "\\n", "{", "}")):
        base["reason"] = "dynamic_or_python_expression"
        return base
    parsed = _top_level_call(expression)
    if parsed is None:
        base["reason"] = "not_a_single_top_level_call"
        return base
    name, args = parsed
    rule = WHITELIST.get(name)
    if rule is None:
        base["reason"] = f"function_not_whitelisted:{name}"
        return base
    code, l3_name, required = rule
    if len(args) != required:
        base["reason"] = f"argument_count_mismatch:{name}:{len(args)}:{required}"
        return base
    if name == "buffer" and _normalise(args[0]) not in GEOMETRY_ARG:
        base["reason"] = "buffer_input_not_explicit_geometry"
        return base
    if name in {"centroid", "point_on_surface", "start_point", "end_point"}:
        if _normalise(args[0]) not in GEOMETRY_ARG:
            base["reason"] = "point_input_not_explicit_geometry"
            return base
    if name == "simplify" and _normalise(args[0]) not in GEOMETRY_ARG:
        base["reason"] = "simplify_input_not_explicit_geometry"
        return base
    if name == "line_interpolate_point" and _normalise(args[0]) not in GEOMETRY_ARG:
        base["reason"] = "interpolate_input_not_explicit_geometry"
        return base
    base.update(
        {
            "status": "resolved_candidate",
            "candidate_l3_code": code,
            "candidate_l3_name": l3_name,
            "required_argument_count": required,
            "rule_id": f"geometrybyexpression:{name}:v1",
            "reason": "top_level_whitelist_match",
            "mapping_admission": "proposal_only",
        }
    )
    return base


def resolve_source_expressions(source: str) -> list[dict[str, Any]]:
    """Resolve literal expressions from each source-backed Processing call."""
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [
            {
                **resolve_geometry_expression(None),
                "reason": "source_syntax_error",
                "error": str(exc),
            }
        ]
    output = []
    for parameter in processing_parameter_nodes(
        tree, "native:geometrybyexpression", "EXPRESSION"
    ):
        node = parameter["parameter_node"]
        expression = node.value if isinstance(node, ast.Constant) and isinstance(node.value, str) else None
        result = resolve_geometry_expression(expression)
        if node is None:
            result["reason"] = "expression_parameter_not_static_dict"
        elif expression is None:
            result["reason"] = "expression_parameter_not_literal_string"
        result["line"] = parameter["call"].lineno
        output.append(result)
    return output


def _extract_expressions(snippet: str) -> list[str]:
    """Extract simple literal EXPRESSION values from a harvested snippet."""
    if not snippet:
        return []
    values: list[str] = []
    pattern = re.compile(r"['\"]EXPRESSION['\"]\s*:\s*(['\"])(.*?)\1", re.S)
    for match in pattern.finditer(snippet):
        values.append(match.group(2))
    return values


def build_queue_census(queue: Iterable[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    queue_single_gap_records = 0
    for operator in queue:
        if operator.get("operator_id") != "native:geometrybyexpression":
            continue
        queue_single_gap_records += int(operator.get("single_gap_records") or 0)
        for sample in operator.get("samples") or []:
            expressions = _extract_expressions(str(sample.get("source_snippet") or ""))
            if not expressions:
                result = resolve_geometry_expression(None)
                result["reason"] = "expression_not_present_in_queue_snippet"
                expressions = [""]
            else:
                result = resolve_geometry_expression(expressions[0])
            result.update(
                {
                    "record_id": sample.get("record_id", ""),
                    "source_sha256": sample.get("source_sha256", ""),
                    "source_path": sample.get("source_path", ""),
                    "expression_count_in_snippet": len(expressions),
                }
            )
            rows.append(result)
    summary = {
        "schema": "gis_recommend.qgis_geometry_expression_resolution_summary.v1",
        "operator_id": "native:geometrybyexpression",
        "queue_single_gap_records": queue_single_gap_records,
        "sample_count": len(rows),
        "expression_observed_count": sum(bool(row["expression"]) for row in rows),
        "resolved_candidate_count": sum(row["status"] == "resolved_candidate" for row in rows),
        "deferred_count": sum(row["status"] == "deferred" for row in rows),
        "candidate_l3_codes": sorted({row["candidate_l3_code"] for row in rows if row["candidate_l3_code"]}),
        "mapping_admission": "proposal_only",
        "training_rows_emitted": 0,
        "production_merge": "not_granted",
    }
    return rows, summary


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    rows, summary = build_queue_census(_read_jsonl(args.queue))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    rows_path = args.output_dir / "resolution_ledger_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    report_path = args.output_dir / "report_v1.md"
    rows_path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report_path.write_text(
        "# geometrybyexpression expression-resolution census v1\n\n"
        "Report-only candidate resolution. No mapping, taxonomy, or training admission is granted.\n\n"
        f"- Queue samples: **{summary['sample_count']}**\n"
        f"- Queue single-gap records: **{summary['queue_single_gap_records']}**\n"
        f"- Expressions present in snippets: **{summary['expression_observed_count']}**\n"
        f"- Whitelist candidates: **{summary['resolved_candidate_count']}**\n"
        f"- Deferred: **{summary['deferred_count']}**\n"
        f"- Candidate L3 codes: `{', '.join(summary['candidate_l3_codes']) or 'none'}`\n\n"
        "The resolver accepts only a single top-level call with an explicit `$geometry` input "
        "for existing Buffer, Feature to Point, or Simplify families. Dynamic, nested, "
        "unobserved, and unsupported expressions remain deferred.\n",
        encoding="utf-8",
    )
    hash_path = args.output_dir / "hash_ledger_v1.json"
    hash_path.write_text(
        json.dumps(
            {
                "schema": "gis_recommend.hash_ledger.v1",
                "inputs": {"queue": {"path": str(args.queue), "sha256": _sha256(args.queue)}},
                "artifacts": {
                    rows_path.name: _sha256(rows_path),
                    summary_path.name: _sha256(summary_path),
                    report_path.name: _sha256(report_path),
                },
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
