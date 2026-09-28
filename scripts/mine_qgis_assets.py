#!/usr/bin/env python3
"""High-recall, candidate-only miner for raw QGIS training assets.

The miner answers ``what can be extracted?`` rather than ``what is admitted?``.
It preserves source identity and call evidence, classifies Processing/API
assets, and records unresolved dynamic calls without guessing operator IDs.
No L3 labels, training rows, authority updates, or model artifacts are emitted.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from .census_qgis_source_roles import classify_source, read_jsonl
    from .scan_qgis_raw_unclassified import (
        PLUMBING_METHODS,
        PROCESSING_NAMES,
        SEMANTIC_METHODS,
        source_path,
    )
except ImportError:
    from census_qgis_source_roles import classify_source, read_jsonl
    from scan_qgis_raw_unclassified import (
        PLUMBING_METHODS,
        PROCESSING_NAMES,
        SEMANTIC_METHODS,
        source_path,
    )


SCHEMA = "gis_recommend.qgis_asset_miner.v1"


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _call_evidence(tree: ast.AST) -> dict[str, list[dict[str, Any]]]:
    imported = {
        alias.asname or alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom)
        and node.module == "processing"
        for alias in node.names
        if alias.name.lower() in PROCESSING_NAMES
    }
    processing: list[dict[str, Any]] = []
    semantic: list[dict[str, Any]] = []
    plumbing: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        method = node.func.attr.lower() if isinstance(node.func, ast.Attribute) else ""
        is_processing = (
            isinstance(node.func, ast.Name) and node.func.id in imported
        ) or (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id.lower() == "processing"
            and method in PROCESSING_NAMES
        )
        if is_processing:
            first = node.args[0] if node.args else None
            operator_id = (
                first.value.strip().lower()
                if isinstance(first, ast.Constant) and isinstance(first.value, str)
                else None
            )
            processing.append(
                {
                    "line_start": int(node.lineno),
                    "line_end": int(getattr(node, "end_lineno", node.lineno)),
                    "entrypoint": method or (node.func.id if isinstance(node.func, ast.Name) else "run"),
                    "operator_id": operator_id,
                    "resolution_kind": "literal" if operator_id else "dynamic_or_missing",
                    "expression": ast.unparse(first) if first is not None else "",
                }
            )
        elif method in SEMANTIC_METHODS:
            semantic.append({"line_start": int(node.lineno), "method": method})
        elif method in PLUMBING_METHODS:
            plumbing.append({"line_start": int(node.lineno), "method": method})
    for values in (processing, semantic, plumbing):
        values.sort(key=lambda item: item["line_start"])
    return {"processing": processing, "semantic": semantic, "plumbing": plumbing}


def _has_processing_algorithm_class(tree: ast.AST) -> bool:
    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        methods = {
            child.name
            for child in node.body
            if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
        }
        if "processAlgorithm" in methods and "name" in methods:
            return True
    return False


def _asset_type(evidence: dict[str, list[dict[str, Any]]], *, has_custom: bool) -> str:
    processing = evidence["processing"]
    semantic = evidence["semantic"]
    plumbing = evidence["plumbing"]
    if processing:
        if any(item["operator_id"] is None for item in processing):
            return "dynamic_recovery_candidate"
        if has_custom:
            return "processing_implementation_candidate"
        return "processing_workflow_candidate" if len(processing) >= 2 else "processing_operator_candidate"
    if semantic and plumbing:
        return "api_pattern_candidate"
    if semantic:
        return "api_semantic_unit_candidate"
    if plumbing:
        return "api_plumbing_evidence"
    return "unresolved_source"


def mine_row(row: dict[str, Any], roots: dict[str, Path], *, classify_roles: bool = True) -> dict[str, Any]:
    raw_manifest_path = Path(str(row.get("source_path") or "")).expanduser()
    # Fast path for server manifests containing an absolute raw path.  This
    # avoids repeatedly resolving every declared root on large NFS trees.
    path = raw_manifest_path if raw_manifest_path.is_absolute() and raw_manifest_path.is_file() else source_path(row, roots)
    # API manifests historically omit source_root_id.  Multiple declared
    # roots can be nested under ``/home/yll``; choose the most-specific
    # ancestor instead of treating that legitimate overlap as ambiguous.
    if path is None and not str(row.get("source_root_id") or ""):
        raw_path = Path(str(row.get("source_path") or "")).expanduser().resolve()
        ancestors = [root.resolve() for root in roots.values() if raw_path.is_relative_to(root.resolve())]
        if ancestors:
            path = raw_path
    base = {
        "schema": SCHEMA,
        "record_id": row.get("record_id"),
        "pool": row.get("pool"),
        "source_root_id": row.get("source_root_id"),
        "manifest_source_sha256": row.get("source_sha256"),
        "manifest_source_path": row.get("source_path"),
        "candidate_only": True,
        "l3_mapping": "not_attempted_asset_miner_v1",
        "training_admission": "not_granted_asset_miner_v1",
        "training_rows_emitted": 0,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }
    if path is None:
        return {**base, "status": "source_unresolved", "asset_type": "unresolved_source"}
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        return {**base, "status": "source_unresolved", "asset_type": "unresolved_source"}
    actual_sha = sha256_bytes(raw)
    if actual_sha != str(row.get("source_sha256") or ""):
        return {**base, "status": "sha_mismatch", "asset_type": "unresolved_source", "source_sha256": actual_sha}
    try:
        source = raw.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError as exc:
        return {**base, "status": "decode_error", "asset_type": "unresolved_source", "source_sha256": actual_sha, "error": str(exc)}
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return {**base, "status": "syntax_error", "asset_type": "unresolved_source", "error": str(exc), "source_sha256": actual_sha}
    evidence = _call_evidence(tree)
    asset_type = _asset_type(evidence, has_custom=_has_processing_algorithm_class(tree))
    dynamic_count = sum(item["operator_id"] is None for item in evidence["processing"])
    return {
        **base,
        "status": "parsed",
        "asset_type": asset_type,
        "source_sha256": actual_sha,
        "source_path": str(path),
        "source_line_count": len(source.splitlines()),
        "source_role": classify_source(row, source)["source_role"] if classify_roles else "not_classified_asset_miner_v1",
        "processing_calls": evidence["processing"],
        "semantic_calls": evidence["semantic"],
        "plumbing_calls": evidence["plumbing"],
        "signal_counts": {key: len(value) for key, value in evidence.items()},
        "dynamic_processing_call_count": dynamic_count,
        "static_processing_call_count": len(evidence["processing"]) - dynamic_count,
    }


def parse_root(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("source root must be ROOT_ID=PATH")
    root_id, raw_path = value.split("=", 1)
    if not root_id or not raw_path:
        raise argparse.ArgumentTypeError("source root must be ROOT_ID=PATH")
    return root_id, Path(raw_path).expanduser().resolve()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--processing-manifest", type=Path, required=True)
    parser.add_argument("--api-manifest", type=Path, required=True)
    parser.add_argument("--source-root", action="append", type=parse_root, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-per-pool", type=int, default=0, help="Deterministic prefix limit per manifest pool (0 = all)")
    parser.add_argument("--skip-role-classification", action="store_true", help="Skip expensive historical source-role classifier")
    args = parser.parse_args()
    roots = dict(args.source_root)
    rows = [("processing", row) for row in read_jsonl(args.processing_manifest)]
    rows += [("api", row) for row in read_jsonl(args.api_manifest)]
    if args.max_per_pool > 0:
        rows = [
            item
            for pool in ("processing", "api")
            for item in [row for row in rows if row[0] == pool][: args.max_per_pool]
        ]
    mined = [mine_row({**row, "pool": pool}, roots, classify_roles=not args.skip_role_classification) for pool, row in rows]
    summary = {
        "schema": f"{SCHEMA}.summary",
        "input_rows": len(mined),
        "status_counts": dict(sorted(Counter(row["status"] for row in mined).items())),
        "asset_type_counts": dict(sorted(Counter(row["asset_type"] for row in mined).items())),
        "pool_asset_type_counts": {
            pool: dict(sorted(Counter(row["asset_type"] for row in mined if row["pool"] == pool).items()))
            for pool in sorted({row["pool"] for row in mined})
        },
        "parsed_rows": sum(row["status"] == "parsed" for row in mined),
        "dynamic_processing_calls": sum(row.get("dynamic_processing_call_count", 0) for row in mined),
        "training_rows_emitted": 0,
        "training_admission": "not_granted_asset_miner_v1",
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    ledger = args.output_dir / "qgis_asset_miner_v1.jsonl"
    ledger.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in mined), encoding="utf-8")
    summary_path = args.output_dir / "summary_v1.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    hashes = {name: sha256_bytes(path.read_bytes()) for name, path in ((ledger.name, ledger), (summary_path.name, summary_path))}
    (args.output_dir / "hash_ledger_v1.json").write_text(json.dumps(hashes, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
