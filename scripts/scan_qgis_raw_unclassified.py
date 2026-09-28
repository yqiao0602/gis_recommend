#!/usr/bin/env python3
"""Scan raw QGIS authorities for high-recall, candidate-only evidence.

This command deliberately does not emit L3 labels or training rows.  It reads
the original Processing/API manifests, resolves source files through explicit
read-only source-root mappings, verifies raw-byte SHA256, and then reports
structural signatures for sources that the existing role classifier leaves
``unclassified``.
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
except ImportError:  # direct ``python scripts/scan_...py`` execution
    from census_qgis_source_roles import classify_source, read_jsonl


SCHEMA = "gis_recommend.qgis_raw_unclassified_scan.v1"
PROCESSING_NAMES = {"run", "runalg", "runandloadresults"}
SEMANTIC_METHODS = {
    "buffer", "centroid", "combine", "convexhull", "difference", "intersection",
    "interpolate", "makevalid", "offsetcurve", "simplify", "smooth",
    "symdifference", "transform", "unaryunion", "distance", "nearestneighbor",
    "intersects", "within", "contains", "touches", "overlaps", "splitgeometry",
}
PLUMBING_METHODS = {
    "dataprovider", "setgeometry", "setattributes", "setattribute", "addfeature",
    "addfeatures", "getfeatures", "updatefields", "updateextents", "changeattributevalues",
    "startediting", "commitediting", "writervectorformat", "writeasvectorformat",
    "writeasvectorformatv2", "writeasvectorformatv3",
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def source_path(row: dict[str, Any], roots: dict[str, Path]) -> Path | None:
    root_id = str(row.get("source_root_id") or "")
    raw_path = str(row.get("source_path") or "")
    root = roots.get(root_id)
    if root is None:
        # Some historical API manifests omitted source_root_id.  Resolve such
        # rows only when an explicitly supplied root is an ancestor of the
        # absolute manifest path; never guess from a basename.
        absolute = Path(raw_path).expanduser().resolve()
        matches = [(candidate, candidate.resolve()) for candidate in roots.values() if absolute.is_relative_to(candidate.resolve())]
        if len(matches) == 1:
            return absolute
        return None
    if root is None:
        return None
    path = Path(raw_path)
    resolved_raw = path.expanduser().resolve()
    resolved_root = root.resolve()
    if resolved_raw.is_file() and resolved_raw.is_relative_to(resolved_root):
        return resolved_raw
    # Manifests may contain an absolute server path.  Resolve it relative to
    # the declared root using the manifest's source-root-relative suffix.
    marker = f"{root_id}/"
    relative = raw_path.split(marker, 1)[1] if marker in raw_path else path.name
    candidate = (root / relative).resolve()
    if not candidate.is_file() or not candidate.is_relative_to(resolved_root):
        return None
    return candidate


def call_evidence(tree: ast.AST) -> dict[str, Any]:
    imported_processing_names = {
        alias.asname or alias.name
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module == "processing"
        for alias in node.names
        if alias.name in PROCESSING_NAMES
    }
    processing: list[dict[str, Any]] = []
    semantic: list[dict[str, Any]] = []
    plumbing: list[dict[str, Any]] = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        method = node.func.attr.lower() if isinstance(node.func, ast.Attribute) else None
        is_processing = (
            isinstance(node.func, ast.Name) and node.func.id in imported_processing_names
        ) or (
            isinstance(node.func, ast.Attribute)
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id.lower() == "processing"
            and method in PROCESSING_NAMES
        )
        if is_processing:
            first = node.args[0] if node.args else None
            operator_id = first.value.strip().lower() if isinstance(first, ast.Constant) and isinstance(first.value, str) else None
            processing.append({"line": node.lineno, "method": method or getattr(node.func, "id", "run"), "operator_id": operator_id, "argument_kind": type(first).__name__ if first is not None else "missing"})
        elif method in SEMANTIC_METHODS:
            semantic.append({"line": node.lineno, "method": method})
        elif method in PLUMBING_METHODS:
            plumbing.append({"line": node.lineno, "method": method})
    return {
        "processing_calls": sorted(processing, key=lambda item: item["line"]),
        "semantic_calls": sorted(semantic, key=lambda item: item["line"]),
        "plumbing_calls": sorted(plumbing, key=lambda item: item["line"]),
    }


def scan_row(row: dict[str, Any], roots: dict[str, Path]) -> dict[str, Any]:
    path = source_path(row, roots)
    base = {
        "schema": SCHEMA,
        "record_id": row.get("record_id"),
        "pool": row.get("pool"),
        "source_root_id": row.get("source_root_id"),
        "source_path": row.get("source_path"),
        "manifest_source_sha256": row.get("source_sha256"),
        "training_rows_emitted": 0,
        "training_admission": "not_granted_raw_candidate_scan",
        "validation_eligible": False,
        "test_eligible": False,
        "candidate_only": True,
    }
    if path is None:
        return {**base, "status": "source_unresolved", "candidate_kind": "deferred"}
    raw = path.read_bytes()
    actual_sha = sha256_bytes(raw)
    if actual_sha != str(row.get("source_sha256") or ""):
        return {**base, "status": "sha_mismatch", "actual_source_sha256": actual_sha, "candidate_kind": "deferred"}
    source = raw.decode("utf-8-sig", errors="strict")
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return {**base, "status": "syntax_error", "error": str(exc), "candidate_kind": "deferred"}
    role = classify_source(row, source)
    if role["source_role"] != "unclassified":
        return {**base, "status": "already_classified", "source_role": role["source_role"], "candidate_kind": "not_target"}
    evidence = call_evidence(tree)
    processing = evidence["processing_calls"]
    semantic = evidence["semantic_calls"]
    plumbing = evidence["plumbing_calls"]
    if processing:
        kind = "processing_workflow_candidate" if len(processing) >= 2 else "processing_operator_candidate"
    elif semantic:
        kind = "api_operator_candidate"
    elif plumbing:
        kind = "api_plumbing_candidate"
    else:
        kind = "no_known_qgis_signature"
    return {**base, "status": "scanned", "source_role": "unclassified", "candidate_kind": kind, "source_sha256": actual_sha, "source_line_count": len(source.splitlines()), "processing_calls": processing, "semantic_calls": semantic, "plumbing_calls": plumbing, "signal_counts": {"processing": len(processing), "semantic": len(semantic), "plumbing": len(plumbing)}}


def parse_root(value: str) -> tuple[str, Path]:
    if "=" not in value:
        raise argparse.ArgumentTypeError("source root must be ROOT_ID=PATH")
    root_id, path = value.split("=", 1)
    if not root_id or not path:
        raise argparse.ArgumentTypeError("source root must be ROOT_ID=PATH")
    return root_id, Path(path).expanduser().resolve()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--processing-manifest", type=Path, required=True)
    parser.add_argument("--api-manifest", type=Path, required=True)
    parser.add_argument("--source-root", action="append", type=parse_root, required=True, metavar="ID=PATH")
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    roots = dict(args.source_root)
    rows = [("processing", row) for row in read_jsonl(args.processing_manifest)] + [("api", row) for row in read_jsonl(args.api_manifest)]
    scanned = [scan_row({**row, "pool": pool}, roots) for pool, row in rows]
    summary = {"schema": f"{SCHEMA}.summary", "input_rows": len(rows), "target_unclassified_rows": sum(item.get("source_role") == "unclassified" for item in scanned), "status_counts": dict(sorted(Counter(item["status"] for item in scanned).items())), "candidate_kind_counts": dict(sorted(Counter(item["candidate_kind"] for item in scanned).items())), "training_rows_emitted": 0, "training_admission": "not_granted_raw_candidate_scan"}
    args.output_dir.mkdir(parents=True, exist_ok=True)
    ledger = args.output_dir / "raw_unclassified_scan_v1.jsonl"
    ledger.write_text("".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in scanned), encoding="utf-8")
    summary_path = args.output_dir / "summary_v1.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    hashes = {ledger.name: sha256_bytes(ledger.read_bytes()), summary_path.name: sha256_bytes(summary_path.read_bytes())}
    (args.output_dir / "hash_ledger_v1.json").write_text(json.dumps(hashes, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
