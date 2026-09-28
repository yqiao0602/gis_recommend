#!/usr/bin/env python3
"""De-duplicate conditional-path census units by source body and scope AST."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any

from gis_recommend.data.qgis_source_authority import source_authority


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = (
    ROOT
    / "docs/reports/qgis_conditional_path_full_source_census_v1/matched_units.jsonl"
)
DEFAULT_OUTPUT_DIR = (
    ROOT / "docs/reports/qgis_conditional_path_full_source_census_v1/dedup_v1"
)


def _scope_name(node: ast.AST, parents: dict[ast.AST, ast.AST]) -> str:
    names: list[str] = []
    current = node
    while not isinstance(current, ast.Module):
        if isinstance(current, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            names.append(current.name)
        if current not in parents:
            break
        current = parents[current]
    return ".".join(reversed(names)) or "<module>"


def _scope_ast_hash(source_text: str, scope_name: str) -> str:
    tree = ast.parse(source_text)
    parents = {
        child: parent
        for parent in ast.walk(tree)
        for child in ast.iter_child_nodes(parent)
    }
    candidates = [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef))
        and _scope_name(node, parents) == scope_name
    ]
    if len(candidates) != 1:
        raise ValueError(f"lexical scope not unique: {scope_name}")
    dumped = ast.dump(candidates[0], annotate_fields=True, include_attributes=False)
    return hashlib.sha256(dumped.encode("utf-8")).hexdigest()


def dedup_conditional_path_units(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    enriched: list[dict[str, Any]] = []
    for row in rows:
        path = Path(str(row["source_path"]))
        declared_sha = str(row["content_sha256"])
        if hashlib.sha256(path.read_bytes()).hexdigest() != declared_sha:
            raise ValueError(f"source sha mismatch: {path}")
        source_text = path.read_text(encoding="utf-8", errors="replace")
        authority = source_authority(path, source_sha256=declared_sha)
        scope_hash = _scope_ast_hash(source_text, str(row["lexical_scope"]))
        rule_payload = {
            "scope_ast_sha256": scope_hash,
            "path_operator_ids": row["path_operator_ids"],
        }
        rule_key = hashlib.sha256(
            json.dumps(rule_payload, sort_keys=True, separators=(",", ":")).encode(
                "utf-8"
            )
        ).hexdigest()
        enriched.append(
            {
                **row,
                **authority,
                "scope_ast_sha256": scope_hash,
                "canonical_rule_key": f"scope_ast_path:{rule_key}",
                "training_admission": "not_granted_rule_census_only",
                "training_row_emitted": False,
            }
        )

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in enriched:
        grouped[row["canonical_rule_key"]].append(row)
    canonical: list[dict[str, Any]] = []
    for position, key in enumerate(sorted(grouped), start=1):
        group = grouped[key]
        representative = min(
            group,
            key=lambda row: (
                str(row.get("source_root_id") or ""),
                str(row.get("relative_path") or ""),
            ),
        )
        canonical.append(
            {
                **representative,
                "schema": "gis_recommend.qgis_conditional_path_canonical_authority.v1",
                "canonical_position": position,
                "duplicate_unit_count": len(group),
                "duplicate_sources": [
                    {
                        "source_root_id": row.get("source_root_id"),
                        "relative_path": row.get("relative_path"),
                        "content_sha256": row.get("content_sha256"),
                        "normalized_source_body_sha256": row.get(
                            "normalized_source_body_sha256"
                        ),
                    }
                    for row in group
                ],
                "review_status": "pending_human_rule_audit",
                "training_admission": "not_granted_human_audit_only",
                "training_row_emitted": False,
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
            }
        )
    summary = {
        "schema": "gis_recommend.qgis_conditional_path_dedup_summary.v1",
        "raw_units": len(rows),
        "content_sha256_authorities": len({row["content_sha256"] for row in rows}),
        "normalized_source_authorities": len(
            {row["normalized_source_body_sha256"] for row in enriched}
        ),
        "region_ast_authorities": len({row["scope_ast_sha256"] for row in enriched}),
        "canonical_rule_support": len(canonical),
        "duplicates_suppressed": len(rows) - len(canonical),
        "decision": {
            "support_threshold_met": len(canonical) >= 30,
            "human_rule_audit_required": True,
            "training_admission": "not_granted",
            "training_rows_emitted": 0,
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
        },
    }
    return canonical, enriched, summary


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def _jsonl(rows: list[dict[str, Any]]) -> str:
    return "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
        for row in rows
    )


def write_outputs(
    canonical: list[dict[str, Any]],
    enriched: list[dict[str, Any]],
    summary: dict[str, Any],
    *,
    input_path: Path,
    output_dir: Path,
) -> dict[str, Path]:
    canonical_path = output_dir / "canonical_authorities.jsonl"
    lineage_path = output_dir / "lineage_ledger.jsonl"
    summary_path = output_dir / "summary.json"
    report_path = output_dir / "README.md"
    hash_path = output_dir / "hash_manifest.json"
    _atomic_write(canonical_path, _jsonl(canonical))
    _atomic_write(lineage_path, _jsonl(enriched))
    _atomic_write(
        summary_path,
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    _atomic_write(
        report_path,
        "# QGIS Conditional Path Authority De-duplication v1\n\n"
        f"- Raw matched units: {summary['raw_units']}\n"
        f"- Normalized-source authorities: {summary['normalized_source_authorities']}\n"
        f"- Scope-AST authorities: {summary['region_ast_authorities']}\n"
        f"- Canonical rule support: {summary['canonical_rule_support']}\n"
        f"- Duplicates suppressed: {summary['duplicates_suppressed']}\n"
        "- Human audit: required\n"
        "- Training rows emitted: 0\n",
    )
    _atomic_write(
        hash_path,
        json.dumps(
            {
                "schema": "gis_recommend.qgis_conditional_path_dedup_hashes.v1",
                "inputs": {str(input_path): _sha256(input_path)},
                "outputs": {
                    path.name: _sha256(path)
                    for path in (canonical_path, lineage_path, summary_path, report_path)
                },
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
    return {
        "canonical": canonical_path,
        "lineage": lineage_path,
        "summary": summary_path,
        "report": report_path,
        "hash": hash_path,
    }


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)
    canonical, enriched, summary = dedup_conditional_path_units(
        _load_jsonl(args.input)
    )
    return write_outputs(
        canonical, enriched, summary, input_path=args.input, output_dir=args.output_dir
    )


if __name__ == "__main__":
    main()
