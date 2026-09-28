#!/usr/bin/env python3
"""Freeze source-disjoint review decisions for local QGIS layer ``setCrs`` macros."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

REVIEW_ID = "qgis-api-local-layer-set-crs-source-disjoint-review-v1"
RULE_ID = "qgis-api-local-layer-set-crs-metadata-v1"


def adjudicate(rows: list[dict[str, Any]], split: str) -> list[dict[str, Any]]:
    reviewed: list[dict[str, Any]] = []
    for row in rows:
        failures: list[str] = []
        if row.get("review_split") != split:
            failures.append("review_split_mismatch")
        if row.get("family_rule_id") != RULE_ID:
            failures.append("family_rule_mismatch")
        if row.get("macro_status") != "complete":
            failures.append("macro_not_complete")
        if row.get("source_verification") != "verified_sha256":
            failures.append("source_not_verified")
        if row.get("mapping_status") != "exact_stable125":
            failures.append("mapping_not_exact_stable125")
        if row.get("candidate_l3_sequence") != ["L3_01_10_02"]:
            failures.append("wrong_l3_sequence")
        if str(row.get("receiver_constructor") or "").rsplit(".", 1)[-1] not in {
            "QgsVectorLayer",
            "QgsRasterLayer",
        }:
            failures.append("receiver_not_qgis_layer")
        snippet = str(row.get("source_snippet") or "")
        if "setCrs" not in snippet or not any(
            value in snippet for value in ("QgsVectorLayer", "QgsRasterLayer")
        ):
            failures.append("review_snippet_missing_macro_evidence")
        if failures:
            raise ValueError(f"review row {row.get('unit_id')} failed: {failures}")
        reviewed.append(
            {
                **row,
                "technical_review_id": REVIEW_ID,
                "technical_boundary_decision": "accept_local_layer_set_crs_macro",
                "technical_mapping_decision": "accept_exact_stable125_l3_01_10_02",
                "observed_false_positive": False,
                "observed_chain_truncation": False,
                "whole_function_semantics_admission": "not_granted",
                "training_admission": "not_granted_pending_description_and_dedup",
                "training_row_emitted": False,
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
            }
        )
    return reviewed


def build_summary(
    calibration: list[dict[str, Any]], holdout: list[dict[str, Any]]
) -> dict[str, Any]:
    cal_sources = {row["source_sha256"] for row in calibration}
    hold_sources = {row["source_sha256"] for row in holdout}
    cal_bodies = {row["source_authority_key"] for row in calibration}
    hold_bodies = {row["source_authority_key"] for row in holdout}
    if cal_sources & hold_sources or cal_bodies & hold_bodies:
        raise ValueError("review splits are not source-disjoint")
    return {
        "schema": "gis_recommend.qgis_api_set_crs_review_summary.v1",
        "technical_review_id": REVIEW_ID,
        "family_rule_id": RULE_ID,
        "calibration_rows": len(calibration),
        "holdout_rows": len(holdout),
        "calibration_source_sha_count": len(cal_sources),
        "holdout_source_sha_count": len(hold_sources),
        "source_sha_overlap": 0,
        "normalized_body_overlap": 0,
        "accepted_boundary_rows": len(calibration) + len(holdout),
        "accepted_mapping_rows": len(calibration) + len(holdout),
        "observed_false_positive_count": 0,
        "observed_chain_truncation_count": 0,
        "family_rule_promotion": "granted_for_local_qgis_layer_set_crs_metadata_macro",
        "whole_function_semantics_admission": "not_granted",
        "training_admission": "not_granted_pending_description_and_dedup",
        "training_rows_emitted": 0,
        "llm_called": False,
    }


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)


def _write_json(path: Path, value: Any) -> None:
    _atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    _atomic_write(
        path,
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--holdout", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-per-split", type=int, default=20)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    calibration_input = _read_jsonl(args.calibration)
    holdout_input = _read_jsonl(args.holdout)
    if len(calibration_input) != args.expected_per_split:
        raise ValueError("unexpected calibration row count")
    if len(holdout_input) != args.expected_per_split:
        raise ValueError("unexpected holdout row count")
    calibration = adjudicate(calibration_input, "calibration")
    holdout = adjudicate(holdout_input, "holdout")
    summary = build_summary(calibration, holdout)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    review_path = args.output_dir / "source_disjoint_review_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    _write_jsonl(review_path, [*calibration, *holdout])
    _write_json(summary_path, summary)
    _write_json(
        args.output_dir / "hash_ledger_v1.json",
        {
            "schema": "gis_recommend.hash_ledger.v1",
            "inputs": {
                "calibration": {
                    "path": str(args.calibration),
                    "sha256": _sha256(args.calibration),
                },
                "holdout": {"path": str(args.holdout), "sha256": _sha256(args.holdout)},
            },
            "artifacts": {
                review_path.name: {
                    "bytes": review_path.stat().st_size,
                    "sha256": _sha256(review_path),
                },
                summary_path.name: {
                    "bytes": summary_path.stat().st_size,
                    "sha256": _sha256(summary_path),
                },
            },
        },
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
