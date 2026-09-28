#!/usr/bin/env python3
"""Build a review-only stable128 proposal for strict WKT feature macros."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections.abc import Iterable
from pathlib import Path
from typing import Any

L3_CODE = "L3_01_01_07"
TOKEN_ID = 127
OPERATOR_ID = "pyqgis:create_features_from_wkt_geometry"
RULE_ID = "qgis-api-wkt-geometry-local-macro-v1"
MINIMUM_SUPPORT = 30


def _read_json(path: Path) -> dict[str, Any]:
    with path.open(encoding="utf-8") as handle:
        return json.load(handle)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", dir=path.parent, delete=False) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)


def _write_json(path: Path, value: Any) -> None:
    _atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    _atomic_write(path, "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows))


def build_proposal(
    complete_rows: list[dict[str, Any]], calibration_rows: list[dict[str, Any]], holdout_rows: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    complete = [row for row in complete_rows if row.get("macro_status") == "complete"]
    calibration = [row for row in calibration_rows if row.get("macro_status") == "complete"]
    holdout = [row for row in holdout_rows if row.get("macro_status") == "complete"]
    if not complete or not calibration or not holdout:
        raise ValueError("WKT proposal requires complete full, calibration, and holdout rows")
    if any(row.get("wkt_geometry_rule_id") != RULE_ID for row in complete):
        raise ValueError("WKT candidate rule mismatch")
    if any(row.get("source_verification") != "verified_sha256" for row in complete):
        raise ValueError("WKT candidate source verification mismatch")
    if {row.get("source_authority_key") for row in calibration} & {row.get("source_authority_key") for row in holdout}:
        raise ValueError("calibration/holdout authority leak")
    authority_count = len({row.get("source_authority_key") for row in complete})
    if authority_count < MINIMUM_SUPPORT:
        raise ValueError("WKT normalized-body support is below 30")
    candidates = [
        {
            **row,
            "schema": "gis_recommend.qgis_api_wkt_geometry_stable128_candidate.v1",
            "operator_sequence": [OPERATOR_ID],
            "candidate_l3_sequence": [L3_CODE],
            "mapping_status": "not_granted_taxonomy_proposal_only",
            "training_admission": "not_granted_taxonomy_proposal_only",
            "training_row_emitted": False,
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
            "llm_called": False,
        }
        for row in complete
    ]
    proposal = {
        "schema": "gis_recommend.qgis_api_stable128_taxonomy_proposal.v1",
        "base_taxonomy": "stable127",
        "proposed_taxonomy": "stable128",
        "operator_id": OPERATOR_ID,
        "candidate_units": len(complete),
        "normalized_body_authorities": authority_count,
        "source_disjoint_calibration_units": len(calibration),
        "source_disjoint_holdout_units": len(holdout),
        "contract": "QgsGeometry.fromWkt(any source-fact WKT expression) -> same feature setGeometry -> addFeature or literal addFeatures([feature])",
        "excludes": [
            "ambiguous_factory_or_setgeometry_relation",
            "nonliteral_or_ambiguous_sink",
            "accumulated_feature_list_sink",
            "geometry_reassigned_before_sink",
            "geometry_mutated_or_reassigned_before_setgeometry",
        ],
        "not_equivalent_to": {
            "l3_code": "L3_07_04_05",
            "name": "Raster File Format Conversion",
            "reason": "That class writes raster datasets; this verified macro parses a WKT geometry into one vector feature.",
        },
        "proposed_l3": {
            "code": L3_CODE,
            "token_id": TOKEN_ID,
            "name": "Create Features from WKT Geometry",
            "definition": "Parses a WKT geometry expression and writes the same geometry to a target feature or sink.",
            "l1_code": "L1_01",
            "l1_name": "Data Management",
            "l2_code": "L2_01_01",
            "l2_name": "Dataset Creation",
        },
        "mapping_admission": "not_granted_taxonomy_proposal_only",
        "taxonomy_admission": "pending_human_taxonomy_review",
        "training_admission": "not_granted_taxonomy_proposal_only",
        "llm_called": False,
    }
    return candidates, proposal


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--complete", type=Path, required=True)
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--holdout", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    candidates, proposal = build_proposal(
        _read_jsonl(args.complete), _read_jsonl(args.calibration), _read_jsonl(args.holdout)
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    candidate_path = args.output_dir / "stable128_wkt_geometry_candidates_v1.jsonl"
    proposal_path = args.output_dir / "stable128_wkt_geometry_proposal_v1.json"
    _write_jsonl(candidate_path, candidates)
    _write_json(proposal_path, proposal)
    _write_json(args.output_dir / "hash_ledger_v1.json", {
        "schema": "gis_recommend.hash_ledger.v1",
        "inputs": {str(index): {"path": str(path), "sha256": _sha256(path)} for index, path in enumerate((args.complete, args.calibration, args.holdout))},
        "artifacts": {path.name: {"bytes": path.stat().st_size, "sha256": _sha256(path)} for path in (candidate_path, proposal_path)},
    })
    print(json.dumps(proposal, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
