#!/usr/bin/env python3
"""Classify QGIS source authorities by workflow value.

This is a structural census only. It never calls an LLM, maps L3, emits
training rows, or changes authority. The four primary roles are
``user_workflow``, ``processing_implementation``, ``api_semantic_operation``
and ``api_plumbing``; unparseable/unsupported files remain explicitly deferred.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

SCHEMA = "gis_recommend.qgis_source_role_census.v1"
SEMANTIC_METHODS = {
    "buffer", "centroid", "combine", "convexhull", "difference", "intersection",
    "interpolate", "makevalid", "offsetcurve", "simplify", "smooth", "symdifference",
    "transform", "unaryunion", "distance", "nearestneighbor", "intersects", "within",
    "contains", "touches", "overlaps", "splitgeometry", "convertto geos", "aspoint",
}
PLUMBING_METHODS = {
    "dataprovider", "setgeometry", "setattributes", "setattribute", "addfeature",
    "addfeatures", "getfeatures", "updatefields", "updateextents", "changeattributevalues",
    "startediting", "commitediting", "writervectorformat", "writeasvectorformat",
    "writeasvectorformatv2", "writeasvectorformatv3",
}
TASK_TERMS = re.compile(
    r"\b(buffer|clip|dissolve|intersect|intersection|centroid|reproject|raster|polygon|"
    r"polyline|point|distance|slope|aspect|watershed|stream|classification|extract|overlay)\b",
    re.IGNORECASE,
)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def source_payload(row: dict[str, Any], replacements: Iterable[tuple[str, str]] = ()) -> tuple[str, str] | None:
    value = row.get("source_text")
    if isinstance(value, str):
        raw = value.encode("utf-8")
        return value, hashlib.sha256(raw).hexdigest()
    raw = str(row.get("source_path") or "")
    for old, new in replacements:
        if raw.startswith(old):
            raw = new + raw[len(old):]
            break
    path = Path(raw)
    if not path.is_file():
        return None
    raw = path.read_bytes()
    return raw.decode("utf-8-sig"), hashlib.sha256(raw).hexdigest()


def _call_method(node: ast.Call) -> str | None:
    if isinstance(node.func, ast.Attribute):
        return node.func.attr.lower()
    return None


def _processing_call(node: ast.Call) -> bool:
    if isinstance(node.func, ast.Name):
        return node.func.id.lower() in {"run", "runalg"}
    return isinstance(node.func, ast.Attribute) and isinstance(node.func.value, ast.Name) and node.func.value.id.lower() == "processing" and node.func.attr.lower() in {"run", "runalg", "runandloadresults"}


def _call_ids(tree: ast.AST) -> list[str]:
    values = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call) or not _processing_call(node) or not node.args:
            continue
        first = node.args[0]
        if isinstance(first, ast.Constant) and isinstance(first.value, str):
            values.append(first.value.strip().lower())
    return values


def _processing_assignments(tree: ast.AST) -> tuple[int, int]:
    assigned = 0
    consumed = 0
    produced_names: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.Assign) or not isinstance(node.value, ast.Call) or not _processing_call(node.value):
            continue
        names = [target.id for target in node.targets if isinstance(target, ast.Name)]
        if names:
            assigned += 1
            produced_names.update(names)
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and _processing_call(node):
            for child in ast.walk(node):
                if isinstance(child, ast.Name) and child.id in produced_names:
                    consumed += 1
                    break
    return assigned, consumed


def _is_processing_implementation(tree: ast.AST, source: str) -> bool:
    class_names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ClassDef):
            class_names.add(node.name.lower())
            if any("qgsprocessingalgorithm" in (ast.unparse(base).lower()) for base in node.bases):
                return True
    return bool("processalgorithm" in source.lower() and ("qgsprocessingalgorithm" in source.lower() or class_names))


def classify_source(row: dict[str, Any], source: str) -> dict[str, Any]:
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return {"source_role": "deferred_unparseable", "parse_status": "syntax_error", "parse_error": str(exc)}
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]
    methods = [_call_method(node) for node in calls]
    methods = [method for method in methods if method]
    semantic = sorted({method for method in methods if method in SEMANTIC_METHODS})
    plumbing = sorted({method for method in methods if method in PLUMBING_METHODS})
    processing_ids = _call_ids(tree)
    assigned, consumed = _processing_assignments(tree)
    path = str(row.get("source_path") or "").lower()
    source_markers = " ".join((path, str(row.get("source_root_id") or ""), source[:3000])).lower()
    model_marker = path.endswith(".model3") or "processing model" in source_markers or "model exported as python" in source_markers
    processing_impl = _is_processing_implementation(tree, source)
    if model_marker:
        role, basis = "user_workflow", "model_or_history_marker"
    elif processing_ids and processing_impl:
        role, basis = "processing_implementation", "qgsprocessingalgorithm_processalgorithm"
    elif processing_ids:
        role, basis = "user_workflow", "standalone_processing_run_script"
    elif semantic:
        role, basis = "api_semantic_operation", "semantic_qgis_method_calls"
    elif plumbing:
        role, basis = "api_plumbing", "feature_layer_io_method_calls"
    else:
        role, basis = "unclassified", "no_supported_processing_or_api_signature"
    task_text = " ".join(ast.get_docstring(node) or "" for node in ast.walk(tree) if isinstance(node, (ast.Module, ast.FunctionDef, ast.ClassDef)))
    task_signal = bool(TASK_TERMS.search(source) or TASK_TERMS.search(task_text))
    return {
        "source_role": role,
        "classification_basis": basis,
        "parse_status": "parsed",
        "processing_run_count": len(processing_ids),
        "processing_operator_ids": processing_ids,
        "processing_assigned_results": assigned,
        "processing_consumed_results": consumed,
        "data_dependency_signal": bool(consumed),
        "api_semantic_methods": semantic,
        "api_plumbing_methods": plumbing,
        "task_semantic_signal": task_signal,
        "input_output_signal": any(token in source for token in ("INPUT", "OUTPUT", "parameterAs", "addFeature", "addFeatures", "writeAsVectorFormat")),
        "source_chars": len(source),
        "source_line_count": len(source.splitlines()),
    }


def census(manifests: Iterable[tuple[str, Path]], replacements: Iterable[tuple[str, str]] = ()) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    for pool, manifest in manifests:
        for authority in read_jsonl(manifest):
            payload = source_payload(authority, replacements)
            base = {"record_id": authority.get("record_id"), "source_sha256": authority.get("source_sha256"), "source_path": authority.get("source_path"), "pool": pool, "training_rows_emitted": 0, "training_admission": "not_granted_source_role_census"}
            if payload is None:
                result = {"source_role": "deferred_source_missing", "parse_status": "source_missing"}
            else:
                source, actual_sha = payload
                if actual_sha != str(authority.get("source_sha256") or ""):
                    result = {"source_role": "deferred_source_integrity", "parse_status": "sha_mismatch"}
                else:
                    result = classify_source(authority, source)
            row = {**base, **result}
            rows.append(row)
            status_counts[row["source_role"]] += 1
    summary = {"schema": f"{SCHEMA}.summary", "source_rows": len(rows), "role_counts": dict(sorted(status_counts.items())), "training_rows_emitted": 0, "training_admission": "not_granted_source_role_census"}
    return rows, summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--processing-manifest", type=Path, required=True)
    parser.add_argument("--api-manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    rows, summary = census([("processing", args.processing_manifest), ("api", args.api_manifest)])
    args.output_dir.mkdir(parents=True, exist_ok=True)
    ledger = args.output_dir / "source_role_census_v1.jsonl"
    ledger.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    (args.output_dir / "summary_v1.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    hashes = {ledger.name: hashlib.sha256(ledger.read_bytes()).hexdigest(), "summary_v1.json": hashlib.sha256((args.output_dir / "summary_v1.json").read_bytes()).hexdigest()}
    (args.output_dir / "hash_ledger_v1.json").write_text(json.dumps(hashes, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
