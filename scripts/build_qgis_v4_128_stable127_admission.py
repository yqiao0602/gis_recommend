#!/usr/bin/env python3
"""Bind the stable127 QGIS V4-128 package to its evidence and smoke gates."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _read_with_path(path: Path) -> dict[str, Any]:
    value = _read_json(path)
    value["_path"] = str(path)
    return value


def build_admission(
    *, dataset_path: Path, text_summary: dict[str, Any], smoke: dict[str, Any], increment_summary: dict[str, Any], taxonomy_summary: dict[str, Any]
) -> dict[str, Any]:
    rows = _read_jsonl(dataset_path)
    if not rows:
        raise ValueError("dataset must not be empty")
    if int(text_summary.get("input_rows") or -1) != len(rows) or int(text_summary.get("eligible_rows") or -1) != len(rows):
        raise ValueError("text gate row count mismatch")
    if int(text_summary.get("deferred_rows", -1)) != 0 or text_summary.get("text_truncation_gate") != "passed_for_eligible_rows":
        raise ValueError("text truncation gate failed")
    if int(smoke.get("rows_loaded") or -1) != len(rows) or int(smoke.get("rows_seen_by_loader") or -1) != len(rows):
        raise ValueError("loader coverage mismatch")
    if smoke.get("input_sha256") != _sha256(dataset_path) or not smoke.get("loss_finite") or not smoke.get("gradient_finite"):
        raise ValueError("loader/loss smoke failed")
    if smoke.get("checkpoint_written") or smoke.get("training_run"):
        raise ValueError("smoke must not train or write a checkpoint")
    if taxonomy_summary.get("taxonomy_admission") != "granted" or int(taxonomy_summary.get("content_token_count") or -1) != 127:
        raise ValueError("stable127 taxonomy authority failed")
    exported = increment_summary.get("export") or {}
    if int(exported.get("train_only_rows") or 0) < 1:
        raise ValueError("increment did not emit train-only rows")
    if any(row.get("validation_eligible") or row.get("test_eligible") or row.get("production_merge") != "not_granted" for row in rows):
        raise ValueError("dataset opens a forbidden split or production merge")
    return {
        "schema": "gis_recommend.qgis_train_only_v4_128_stable127_admission.v1",
        "dataset": {"path": str(dataset_path), "rows": len(rows), "sha256": _sha256(dataset_path)},
        "polyline_geometry_increment": {
            "input_candidate_rows": int(increment_summary["input_candidate_rows"]),
            "source_verified_complete_macros": int((increment_summary.get("dedup") or {}).get("description_fidelity_passed") or 0),
            "normalized_source_authorities": int((increment_summary.get("dedup") or {}).get("unique_source_authorities") or 0),
            "four_layer_suppressed": int((increment_summary.get("dedup") or {}).get("suppressed_exact_training_pairs") or 0),
            "cross_pool_suppressed": int(exported.get("cross_pool_suppressed") or 0),
            "train_only_rows": int(exported["train_only_rows"]),
            "delivery_summary_sha256": _sha256(Path(str(increment_summary["_path"]))),
        },
        "stable127_taxonomy": {"content_token_count": 127, "normalized_source_body_support": int(taxonomy_summary["normalized_source_body_support"]), "taxonomy_summary_sha256": _sha256(Path(str(taxonomy_summary["_path"])))},
        "text_length_gate": {"bert_model": text_summary.get("bert_model"), "max_text_length": int(text_summary["max_text_length"]), "eligible_rows": int(text_summary["eligible_rows"]), "deferred_rows": int(text_summary["deferred_rows"]), "eligible_max_text_tokens": int(text_summary["eligible_max_text_tokens"]), "summary_sha256": _sha256(Path(str(text_summary["_path"])))},
        "loader_loss_smoke": {"rows": int(smoke["rows_loaded"]), "batches": int(smoke["batches"]), "loss_finite": bool(smoke["loss_finite"]), "gradient_finite": bool(smoke["gradient_finite"]), "checkpoint_written": bool(smoke["checkpoint_written"]), "training_run": bool(smoke["training_run"]), "sha256": _sha256(Path(str(smoke["_path"])))},
        "training_admission": "granted_train_only_qgis_aggregate_v4_128_stable127_v1",
        "validation_eligible": False, "test_eligible": False, "production_merge": "not_granted",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--text-summary", type=Path, required=True)
    parser.add_argument("--smoke", type=Path, required=True)
    parser.add_argument("--increment-summary", type=Path, required=True)
    parser.add_argument("--taxonomy-summary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise ValueError(f"output already exists: {args.output}")
    admission = build_admission(dataset_path=args.dataset, text_summary=_read_with_path(args.text_summary), smoke=_read_with_path(args.smoke), increment_summary=_read_with_path(args.increment_summary), taxonomy_summary=_read_with_path(args.taxonomy_summary))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(admission, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(admission, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
