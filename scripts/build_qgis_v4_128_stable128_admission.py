#!/usr/bin/env python3
"""Bind the stable128 QGIS V4-128 package to its evidence and smoke gates."""

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


def _with_path(path: Path) -> dict[str, Any]:
    value = _read_json(path)
    value["_path"] = str(path)
    return value


def build_admission(*, dataset: Path, text: dict[str, Any], smoke: dict[str, Any], increment: dict[str, Any], taxonomy: dict[str, Any]) -> dict[str, Any]:
    rows = _read_jsonl(dataset)
    if not rows or int(text.get("input_rows", -1)) != len(rows) or int(text.get("eligible_rows", -1)) != len(rows) or int(text.get("deferred_rows", -1)) != 0:
        raise ValueError("BERT text gate row count mismatch")
    if text.get("text_truncation_gate") != "passed_for_eligible_rows":
        raise ValueError("BERT text gate failed")
    if int(smoke.get("rows_loaded") or -1) != len(rows) or int(smoke.get("rows_seen_by_loader") or -1) != len(rows) or smoke.get("input_sha256") != _sha256(dataset):
        raise ValueError("loader smoke coverage mismatch")
    if not smoke.get("loss_finite") or not smoke.get("gradient_finite") or smoke.get("checkpoint_written") or smoke.get("training_run"):
        raise ValueError("loader smoke failed")
    if taxonomy.get("taxonomy_admission") != "granted" or int(taxonomy.get("content_token_count") or -1) != 128:
        raise ValueError("stable128 taxonomy authority failed")
    exported = increment.get("export") or {}
    if int(exported.get("train_only_rows") or 0) < 1:
        raise ValueError("WKT increment emitted no train-only rows")
    if any(row.get("validation_eligible") or row.get("test_eligible") or row.get("production_merge") != "not_granted" for row in rows):
        raise ValueError("forbidden split or production merge")
    return {
        "schema": "gis_recommend.qgis_train_only_v4_128_stable128_admission.v1",
        "dataset": {"path": str(dataset), "rows": len(rows), "sha256": _sha256(dataset)},
        "stable128_taxonomy": {"content_token_count": 128, "normalized_source_body_support": int(taxonomy["normalized_source_body_support"]), "summary_sha256": _sha256(Path(taxonomy["_path"]))},
        "wkt_geometry_increment": {"input_candidate_rows": int(increment["input_candidate_rows"]), "source_verified_complete_macros": int((increment.get("dedup") or {}).get("description_fidelity_passed") or 0), "normalized_source_authorities": int((increment.get("dedup") or {}).get("unique_source_authorities") or 0), "four_layer_suppressed": int((increment.get("dedup") or {}).get("suppressed_exact_training_pairs") or 0), "cross_pool_suppressed": int(exported.get("cross_pool_suppressed") or 0), "train_only_rows": int(exported["train_only_rows"]), "summary_sha256": _sha256(Path(increment["_path"]))},
        "text_length_gate": {"bert_model": text.get("bert_model"), "max_text_length": int(text["max_text_length"]), "eligible_rows": int(text["eligible_rows"]), "eligible_max_text_tokens": int(text["eligible_max_text_tokens"]), "summary_sha256": _sha256(Path(text["_path"]))},
        "loader_loss_smoke": {"rows": int(smoke["rows_loaded"]), "batches": int(smoke["batches"]), "loss_finite": bool(smoke["loss_finite"]), "gradient_finite": bool(smoke["gradient_finite"]), "checkpoint_written": False, "training_run": False, "summary_sha256": _sha256(Path(smoke["_path"]))},
        "training_admission": "granted_train_only_qgis_aggregate_v4_128_stable128_v1", "validation_eligible": False, "test_eligible": False, "production_merge": "not_granted",
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
    admission = build_admission(dataset=args.dataset, text=_with_path(args.text_summary), smoke=_with_path(args.smoke), increment=_with_path(args.increment_summary), taxonomy=_with_path(args.taxonomy_summary))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(admission, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(admission, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
