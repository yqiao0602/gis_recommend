#!/usr/bin/env python3
"""Build a review-only minimum taxonomy proposal for strict polyline macros."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections.abc import Iterable
from pathlib import Path
from typing import Any

L3_CODE = "L3_01_01_06"
TOKEN_ID = 126
OPERATOR_ID = "pyqgis:create_polyline_features_from_vertices"
MINIMUM_SUPPORT = 30
RULE_ID = "qgis-api-polyline-geometry-local-macro-v1"


def _complete(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    selected = [row for row in rows if row.get("macro_status") == "complete"]
    if any(row.get("source_verification") != "verified_sha256" for row in selected):
        raise ValueError("taxonomy proposal candidates must be source-SHA verified")
    if any(row.get("polyline_geometry_rule_id") != RULE_ID for row in selected):
        raise ValueError("taxonomy proposal macro rule mismatch")
    return selected


def build_proposal(
    calibration_rows: list[dict[str, Any]],
    holdout_rows: list[dict[str, Any]],
    population_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    calibration = _complete(calibration_rows)
    holdout = _complete(holdout_rows)
    candidates = _complete(population_rows)
    if not calibration or not holdout:
        raise ValueError("proposal requires complete calibration and holdout evidence")
    calibration_sha = {str(row.get("source_sha256") or "") for row in calibration}
    holdout_sha = {str(row.get("source_sha256") or "") for row in holdout}
    if "" in calibration_sha or "" in holdout_sha or calibration_sha & holdout_sha:
        raise ValueError("proposal calibration/holdout source SHA leakage")
    authorities = {str(row.get("source_authority_key") or "") for row in candidates}
    if "" in authorities or len(authorities) < MINIMUM_SUPPORT:
        raise ValueError("polyline proposal lacks normalized-body support")
    proposed = [
        {
            **row,
            "schema": "gis_recommend.qgis_api_polyline_geometry_stable127_candidate.v1",
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
        "schema": "gis_recommend.qgis_api_stable127_taxonomy_proposal.v1",
        "base_taxonomy": "stable126",
        "proposed_taxonomy": "stable127",
        "operator_id": OPERATOR_ID,
        "proposed_l3": {
            "code": L3_CODE,
            "token_id": TOKEN_ID,
            "name": "Create Polyline Features from Vertices",
            "definition": "Constructs polyline feature geometry from two or more explicit vertices and writes the same feature to a target layer or sink.",
            "l1_code": "L1_01",
            "l1_name": "Data Management",
            "l2_code": "L2_01_01",
            "l2_name": "Dataset Creation",
        },
        "contract": "QgsGeometry.fromPolyline/fromPolylineXY(literal or unique same-control-path literal QgsPoint/QgsPointXY sequence with >=2 vertices) -> same feature setGeometry -> addFeature or literal addFeatures([feature])",
        "excludes": [
            "dynamic_or_nonliteral_vertex_sequence",
            "ambiguous_factory_or_setgeometry_relation",
            "nonliteral_or_ambiguous_sink",
            "geometry_reassigned_before_sink",
        ],
        "not_equivalent_to": {
            "l3_code": "L3_01_01_01",
            "name": "Create Feature Class",
            "reason": "That class creates a dataset container; this local macro constructs and writes one polyline feature into an already selected target.",
        },
        "candidate_units": len(proposed),
        "normalized_body_authorities": len(authorities),
        "source_disjoint_calibration_units": len(calibration),
        "source_disjoint_holdout_units": len(holdout),
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
    parser.add_argument("--population", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    candidates, proposal = build_proposal(
        _read_jsonl(args.calibration), _read_jsonl(args.holdout), _read_jsonl(args.population)
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    candidates_path = args.output_dir / "stable127_polyline_geometry_candidates_v1.jsonl"
    proposal_path = args.output_dir / "stable127_polyline_geometry_proposal_v1.json"
    _write_jsonl(candidates_path, candidates)
    _write_json(proposal_path, proposal)
    _write_json(
        args.output_dir / "hash_ledger_v1.json",
        {
            "schema": "gis_recommend.hash_ledger.v1",
            "inputs": {
                "calibration": {"path": str(args.calibration), "sha256": _sha256(args.calibration)},
                "holdout": {"path": str(args.holdout), "sha256": _sha256(args.holdout)},
                "population": {"path": str(args.population), "sha256": _sha256(args.population)},
            },
            "artifacts": {
                path.name: {"bytes": path.stat().st_size, "sha256": _sha256(path)}
                for path in (candidates_path, proposal_path)
            },
        },
    )
    print(json.dumps(proposal, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
