#!/usr/bin/env python3
"""Add deterministic processing.run call spans to a source manifest."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
from typing import Any


def _name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        base = _name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""


def _operator(node: ast.Call) -> str | None:
    if node.args and isinstance(node.args[0], ast.Constant):
        value = str(node.args[0].value).strip().lower()
        return value if ":" in value else None
    return None


def enrich(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    enriched = []
    parsed = syntax_errors = sha_failures = 0
    for row in rows:
        path = Path(str(row.get("source_path") or ""))
        expected = str(row.get("source_sha256") or "")
        actual = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else ""
        if actual != expected:
            sha_failures += 1
            enriched.append({**row, "call_sites": [], "call_site_status": "source_sha_mismatch"})
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8-sig", errors="replace"))
        except SyntaxError:
            syntax_errors += 1
            enriched.append({**row, "call_sites": [], "call_site_status": "syntax_error"})
            continue
        sites = []
        for node in sorted(ast.walk(tree), key=lambda item: (getattr(item, "lineno", 0), getattr(item, "col_offset", 0))):
            if not isinstance(node, ast.Call) or _name(node.func) != "processing.run":
                continue
            operator_id = _operator(node)
            if operator_id is None:
                continue
            sites.append({
                "line_start": int(node.lineno),
                "line_end": int(node.end_lineno or node.lineno),
                "operator_id": operator_id,
            })
        parsed += 1
        enriched.append({**row, "call_sites": sites, "call_site_status": "parsed"})
    return enriched, {
        "schema": "gis_recommend.qgis_processing_call_site_enrichment_summary.v1",
        "input_rows": len(rows),
        "parsed_rows": parsed,
        "syntax_errors": syntax_errors,
        "sha_failures": sha_failures,
        "rows_with_literal_processing_calls": sum(bool(row.get("call_sites")) for row in enriched),
        "training_rows_emitted": 0,
        "training_admission": "not_granted_call_site_enrichment_only",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.input.read_text(encoding="utf-8").splitlines() if line.strip()]
    enriched, summary = enrich(rows)
    args.output.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in enriched), encoding="utf-8")
    args.summary.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
