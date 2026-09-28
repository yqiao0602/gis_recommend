#!/usr/bin/env python3
"""Build a review-only minimum taxonomy proposal for point-coordinate macros."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections.abc import Iterable
from pathlib import Path
from typing import Any

L3_CODE = "L3_01_01_05"
TOKEN_ID = 125
OPERATOR_ID = "pyqgis:create_point_features_from_coordinates"
MINIMUM_SUPPORT = 30
EXCLUDED_ORIGINS = {
    "not_a_direct_coordinate_constructor",
    "coordinate_component_count_not_pair",
}


def build_proposal(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    candidates = [
        row
        for row in rows
        if row.get("macro_status") == "complete"
        and row.get("coordinate_origin_kind") not in EXCLUDED_ORIGINS
    ]
    if any(row.get("source_verification") != "verified_sha256" for row in candidates):
        raise ValueError("taxonomy proposal candidates must be source-SHA verified")
    authorities = {str(row.get("source_authority_key") or "") for row in candidates}
    if "" in authorities or len(authorities) < MINIMUM_SUPPORT:
        raise ValueError("point-coordinate proposal lacks normalized-body support")
    calibration = [row for row in candidates if row.get("review_split") == "calibration"]
    holdout = [row for row in candidates if row.get("review_split") == "holdout"]
    if not calibration or not holdout:
        raise ValueError("proposal requires both calibration and holdout coverage")
    if {
        str(row["source_authority_key"]) for row in calibration
    } & {str(row["source_authority_key"]) for row in holdout}:
        raise ValueError("proposal calibration/holdout authority leakage")
    proposed = [
        {
            **row,
            "schema": "gis_recommend.qgis_api_point_geometry_stable126_candidate.v1",
            "proposed_operator_id": OPERATOR_ID,
            "proposed_l3_code": L3_CODE,
            "proposed_l3_token_id": TOKEN_ID,
            "taxonomy_admission": "pending_human_taxonomy_review",
            "mapping_admission": "not_granted_taxonomy_proposal_only",
            "candidate_l3_sequence": [],
            "training_admission": "not_granted_taxonomy_proposal_only",
            "training_row_emitted": False,
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
        }
        for row in candidates
    ]
    proposal = {
        "schema": "gis_recommend.qgis_api_stable126_taxonomy_proposal.v1",
        "base_taxonomy": "stable125",
        "proposed_taxonomy": "stable126",
        "operator_id": OPERATOR_ID,
        "proposed_l3": {
            "code": L3_CODE,
            "token_id": TOKEN_ID,
            "name": "Create Point Features from Coordinates",
            "definition": "Constructs point feature geometry from a coordinate pair and writes the same feature to a target layer or sink.",
            "l1_code": "L1_01",
            "l1_name": "Data Management",
            "l2_code": "L2_01_01",
            "l2_name": "Dataset Creation",
        },
        "contract": "QgsGeometry.fromPoint/fromPointXY(QgsPoint/QgsPointXY coordinate pair) -> same feature setGeometry -> addFeature or literal addFeatures([feature])",
        "excludes": sorted(EXCLUDED_ORIGINS),
        "not_equivalent_to": {
            "l3_code": "L3_01_01_04",
            "name": "Create Points from Table",
            "reason": "That class requires table-field coordinate provenance; this local macro accepts a proven coordinate pair from any source.",
        },
        "candidate_units": len(proposed),
        "normalized_body_authorities": len(authorities),
        "calibration_units": len(calibration),
        "holdout_units": len(holdout),
        "taxonomy_admission": "pending_human_taxonomy_review",
        "mapping_admission": "not_granted_taxonomy_proposal_only",
        "training_admission": "not_granted_taxonomy_proposal_only",
        "training_rows_emitted": 0,
        "llm_called": False,
    }
    return proposed, proposal


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


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--calibration", type=Path, required=True)
    parser.add_argument("--holdout", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    candidates, proposal = build_proposal(
        [*_read_jsonl(args.calibration), *_read_jsonl(args.holdout)]
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    candidates_path = args.output_dir / "stable126_point_geometry_candidates_v1.jsonl"
    proposal_path = args.output_dir / "stable126_point_geometry_proposal_v1.json"
    _write_jsonl(candidates_path, candidates)
    _write_json(proposal_path, proposal)
    _write_json(
        args.output_dir / "hash_ledger_v1.json",
        {
            "schema": "gis_recommend.hash_ledger.v1",
            "inputs": {
                "calibration": {"path": str(args.calibration), "sha256": _sha256(args.calibration)},
                "holdout": {"path": str(args.holdout), "sha256": _sha256(args.holdout)},
            },
            "artifacts": {
                path.name: {"bytes": path.stat().st_size, "sha256": _sha256(path)}
                for path in (candidates_path, proposal_path)
            },
        },
    )
    print(proposal_path.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
