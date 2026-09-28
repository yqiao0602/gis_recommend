#!/usr/bin/env python3
"""Freeze source-disjoint review for exact GeoTIFF writer contracts."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

SCHEMA = "gis_recommend.qgis_api_raster_file_export_review.v1"
REVIEW_ID = "raster-file-export-exact-geotiff-review-v1"
RULE_ID = "qgis-api-raster-file-export-contract-v1"
L3_CODE = "L3_07_04_05"


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def adjudicate(rows: Iterable[dict[str, Any]], split: str) -> list[dict[str, Any]]:
    reviewed: list[dict[str, Any]] = []
    for row in rows:
        failures: list[str] = []
        if row.get("review_split") != split:
            failures.append("review_split_mismatch")
        if row.get("contract_rule_id") != RULE_ID:
            failures.append("contract_rule_mismatch")
        if row.get("family_id") != "raster_file_export":
            failures.append("wrong_family")
        if row.get("macro_status") != "complete":
            failures.append("macro_not_complete")
        if row.get("source_verification") != "verified_sha256":
            failures.append("source_not_verified")
        if row.get("contract_class") != "geotiff":
            failures.append("not_geotiff")
        if row.get("contract_status") != "source_backed":
            failures.append("contract_not_source_backed")
        if row.get("mapping_status") != "exact_stable125_existing_l3":
            failures.append("mapping_not_exact_stable125")
        if row.get("candidate_l3_sequence") != [L3_CODE]:
            failures.append("wrong_l3_sequence")
        if row.get("contract_basis") not in {
            "explicit_output_format",
            "output_path_evidence",
        }:
            failures.append("unsupported_contract_basis")
        snippet = str(row.get("contract_evidence_snippet") or "")
        if "QgsRasterFileWriter" not in snippet or "writeRaster" not in snippet:
            failures.append("review_snippet_missing_writer_endpoints")
        if _sha256_bytes(snippet.encode("utf-8")) != row.get(
            "contract_evidence_sha256"
        ):
            failures.append("contract_evidence_hash_mismatch")
        if row.get("contract_basis") == "explicit_output_format":
            formats = {
                str(fact.get("value") or "").strip().lower()
                for fact in row.get("output_format_facts") or []
                if fact.get("status") == "literal"
            }
            if not formats.intersection({"gtiff", "geotiff", "cog"}):
                failures.append("explicit_geotiff_format_missing")
        else:
            fragments = " ".join(row.get("output_path_string_fragments") or []).lower()
            if ".tif" not in fragments and ".tiff" not in fragments:
                failures.append("geotiff_path_evidence_missing")
        if failures:
            raise ValueError(f"review row {row.get('unit_id')} failed: {failures}")
        reviewed.append(
            {
                **row,
                "schema": SCHEMA,
                "technical_review_id": REVIEW_ID,
                "technical_boundary_decision": "accept_complete_local_writer_macro",
                "technical_mapping_decision": "accept_exact_stable125_l3_07_04_05",
                "observed_false_positive": False,
                "observed_chain_truncation": False,
                "description_review_decision": "not_started",
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
    calibration_sources = {str(row["source_sha256"]) for row in calibration}
    holdout_sources = {str(row["source_sha256"]) for row in holdout}
    calibration_bodies = {str(row["source_authority_key"]) for row in calibration}
    holdout_bodies = {str(row["source_authority_key"]) for row in holdout}
    if calibration_sources & holdout_sources:
        raise ValueError("source SHA leakage between calibration and holdout")
    if calibration_bodies & holdout_bodies:
        raise ValueError("normalized-body leakage between calibration and holdout")
    all_rows = [*calibration, *holdout]
    return {
        "schema": "gis_recommend.qgis_api_raster_file_export_review_summary.v1",
        "technical_review_id": REVIEW_ID,
        "contract_rule_id": RULE_ID,
        "calibration_rows": len(calibration),
        "calibration_source_sha_count": len(calibration_sources),
        "holdout_rows": len(holdout),
        "holdout_source_sha_count": len(holdout_sources),
        "source_sha_overlap": 0,
        "normalized_body_overlap": 0,
        "accepted_boundary_rows": len(all_rows),
        "accepted_mapping_rows": len(all_rows),
        "observed_false_positive_count": 0,
        "observed_chain_truncation_count": 0,
        "contract_basis_counts": dict(
            sorted(Counter(str(row["contract_basis"]) for row in all_rows).items())
        ),
        "family_rule_promotion": "granted_exact_geotiff_local_writer_contract_only",
        "excluded_contracts": [
            "gpkg_raster",
            "display_image",
            "dynamic_or_unknown_format",
            "conflicting_path_formats",
            "conflicting_format_and_path",
        ],
        "description_fidelity": "not_started",
        "training_admission": "not_granted_pending_description_and_dedup",
        "training_rows_emitted": 0,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
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
    _atomic_write(
        path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    _atomic_write(
        path,
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--holdout", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-per-split", type=int, default=15)
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
