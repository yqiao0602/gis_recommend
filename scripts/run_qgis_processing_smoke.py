#!/usr/bin/env python3
"""200-source runtime/memory smoke for the Processing conversion driver v2.

Two phases, one process:

- Phase 0 (prescan): read all 8,466 manifest sources, verify SHA256, parse
  AST, and collect helper-pattern features.  This is the resource/feasibility
  probe for the full-pool run (wall time, peak memory, parse failure rate).
  It emits scan_ledger_v1.jsonl (small, per-source one line) and the counts
  used by Phase 1 selection.

- Phase 1 (selection): pick 200 source-SHA-unique rows, favouring sources
  that contain an inline-able helper pattern, balanced with stratified random
  rows so the smoke covers the plain path too.

- Phase 2 (smoke): run the helper inline pass and the expanded adapter on the
  200 selected sources and emit smoke_ledger_v1.jsonl with per-source status,
  wall time, unit counts, deferred reasons, and adapter schema validation.

No training row is exported.  No authority file is modified.  Sources are read
from the read-only /home/yll tree.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import random
import resource
import time
from collections import Counter
from pathlib import Path
from typing import Any

SMOKE_SCHEMA = "gis_recommend.qgis_processing_conversion_smoke.v1"
PASS_FILE = Path(__file__).resolve().parents[1] / "src/gis_recommend/data/qgis_processing_helper_inline.py"
ADAPTER_FILE = Path(__file__).resolve().parents[1] / "src/gis_recommend/data/qgis_processing_expanded_adapter.py"


def _load_module(path: Path, name: str) -> Any:
    import importlib.util

    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _helper_features(source_text: str) -> dict[str, int]:
    """Cheap AST features for smoke selection; never authoritative decisions."""
    try:
        tree = ast.parse(source_text)
    except SyntaxError:
        return {"parse_ok": 0, "function_defs": 0, "processing_calls": 0, "helper_calls": 0}
    functions = [node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
    processing_calls = 0
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr in {"run", "runandloadresults", "runalg"}
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "processing"
        ):
            processing_calls += 1
    helper_calls = 0
    names = {node.name for node in functions}
    for node in ast.walk(tree):
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in names:
            helper_calls += 1
    return {
        "parse_ok": 1,
        "function_defs": len(functions),
        "processing_calls": processing_calls,
        "helper_calls": helper_calls,
    }


def _select_rows(
    scan: list[dict[str, Any]], size: int, seed: int, helper_bias: float
) -> list[dict[str, Any]]:
    rng = random.Random(seed)
    helper_rows = [
        row
        for row in scan
        if row["helper_calls"] > 0 and row["processing_calls"] > 0 and row["parse_ok"]
    ]
    helper_target = min(len(helper_rows), int(size * helper_bias))
    picked_helper = rng.sample(helper_rows, helper_target)
    picked_ids = {row["source_sha256"] for row in picked_helper}
    rest = [row for row in scan if row["source_sha256"] not in picked_ids]
    picked_rest = rng.sample(rest, size - helper_target)
    return picked_helper + picked_rest


def _adapter_schema_ok(adapted: dict[str, Any]) -> list[str]:
    errors = []
    required = (
        "record_id",
        "source_sha256",
        "canonical_operator_ids",
        "call_sites",
        "dependency_edges",
        "workflow_unit_scope",
        "source_snippet",
        "source_region_key",
        "call_graph_key",
        "normalized_dag_key",
        "parameter_binding_chain",
        "expansion_proof",
        "recovery_method",
        "call_span_verification",
    )
    for field in required:
        if not adapted.get(field):
            errors.append(f"missing:{field}")
    if len(adapted["canonical_operator_ids"]) != len(adapted["call_sites"]):
        errors.append("operator_call_site_mismatch")
    if "helper" not in (adapted.get("source_segments") or {}):
        errors.append("missing_helper_segment")
    if "caller" not in (adapted.get("source_segments") or {}):
        errors.append("missing_caller_segment")
    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, default=Path("/home/yll"))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=20260807)
    parser.add_argument("--smoke-size", type=int, default=200)
    parser.add_argument("--helper-bias", type=float, default=0.6)
    args = parser.parse_args(argv)

    started = time.monotonic()
    helper_inline = _load_module(PASS_FILE, "qgis_processing_helper_inline")
    expanded_adapter = _load_module(ADAPTER_FILE, "qgis_processing_expanded_adapter")
    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    catalog_ids = {row["operator_id"] for row in catalog["operators"]}

    manifest = [
        json.loads(line) for line in args.manifest.open(encoding="utf-8-sig") if line.strip()
    ]
    if len(manifest) != 8466 or len({row["source_sha256"] for row in manifest}) != 8466:
        raise ValueError("manifest is not the 8,466-row unique-SHA authority")

    scan: list[dict[str, Any]] = []
    scan_errors: Counter[str] = Counter()
    sha_start = time.monotonic()
    root = str(args.source_root).rstrip("/")
    for index, row in enumerate(manifest):
        raw_path = str(row["source_path"])
        path = Path(raw_path) if raw_path.startswith(root) else args.source_root / raw_path.lstrip("/")
        if not path.is_file():
            scan_errors["source_file_missing"] += 1
            continue
        if _sha256_file(path) != row["source_sha256"]:
            scan_errors["sha256_mismatch"] += 1
            continue
        features = _helper_features(path.read_text(encoding="utf-8-sig", errors="replace"))
        if not features["parse_ok"]:
            scan_errors["unparseable"] += 1
        scan.append({**row, **features})
    sha_elapsed = time.monotonic() - sha_start

    selected = _select_rows(scan, args.smoke_size, args.seed, args.helper_bias)
    smoke_start = time.monotonic()
    smoke_rows: list[dict[str, Any]] = []
    unit_count = 0
    deferred_reasons: Counter[str] = Counter()
    adapter_errors: Counter[str] = Counter()
    for row in selected:
        raw_path = str(row["source_path"])
        path = Path(raw_path) if raw_path.startswith(root) else args.source_root / raw_path.lstrip("/")
        per_start = time.monotonic()
        try:
            result = helper_inline.expand_cross_function_helpers(
                path.read_text(encoding="utf-8-sig", errors="replace"),
                record_id=str(row["record_id"]),
                source_sha256=str(row["source_sha256"]),
                catalog_operator_ids=catalog_ids,
            )
        except Exception as exc:  # noqa: BLE001 - smoke records and continues
            smoke_rows.append(
                {
                    "record_id": row["record_id"],
                    "source_sha256": row["source_sha256"],
                    "status": "pass_crash",
                    "error": f"{type(exc).__name__}: {exc}",
                    "wall_ms": int((time.monotonic() - per_start) * 1000),
                }
            )
            continue
        for deferred in result["deferred"]:
            deferred_reasons[str(deferred.get("reason") or "unknown")] += 1
        unit_ids = []
        for unit in result["units"]:
            try:
                adapted = expanded_adapter.adapt_expanded_unit(unit, source_path=str(path))
            except Exception as exc:  # noqa: BLE001
                adapter_errors[f"adapter:{type(exc).__name__}"] += 1
                continue
            schema_errors = _adapter_schema_ok(adapted)
            if schema_errors:
                adapter_errors[f"schema:{schema_errors[0]}"] += 1
                continue
            unit_ids.append(adapted["unit_id"])
            unit_count += 1
        smoke_rows.append(
            {
                "record_id": row["record_id"],
                "source_sha256": row["source_sha256"],
                "source_path": str(row["source_path"]),
                "status": "ok" if not adapter_errors else "ok_with_adapter_issues",
                "unit_ids": unit_ids,
                "deferred_count": len(result["deferred"]),
                "wall_ms": int((time.monotonic() - per_start) * 1000),
            }
        )
    smoke_elapsed = time.monotonic() - smoke_start
    peak_rss_kb = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss

    summary = {
        "schema": SMOKE_SCHEMA,
        "pass_version": helper_inline.PASS_VERSION,
        "adapter_version": expanded_adapter.ADAPTER_VERSION,
        "source_authority_rows": len(manifest),
        "prescan_ok_rows": len(scan),
        "prescan_errors": dict(scan_errors),
        "prescan_wall_seconds": round(sha_elapsed, 2),
        "selected_rows": len(selected),
        "selected_helper_rows": sum(1 for row in selected if row["helper_calls"] > 0),
        "smoke_wall_seconds": round(smoke_elapsed, 2),
        "total_wall_seconds": round(time.monotonic() - started, 2),
        "peak_rss_kb": peak_rss_kb,
        "units_emitted": unit_count,
        "deferred_reason_counts": dict(deferred_reasons.most_common()),
        "adapter_error_counts": dict(adapter_errors.most_common()),
        "extrapolated_prescan_minutes": round(sha_elapsed / 60, 2),
        "extrapolated_full_smoke_minutes": round(
            smoke_elapsed / len(selected) * len(scan) / 60, 2
        ),
        "training_row_emitted": False,
        "production_merge": "not_granted",
    }
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "scan_ledger_v1.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in scan),
        encoding="utf-8",
    )
    (args.output_dir / "smoke_ledger_v1.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in smoke_rows),
        encoding="utf-8",
    )
    (args.output_dir / "summary_v1.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
