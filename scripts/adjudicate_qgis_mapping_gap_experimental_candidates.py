#!/usr/bin/env python3
"""Review experimental114 mapping candidates against stable taxonomy authority."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.adjudicate_qgis_mapping_gap_capability_bridges import (
    _read_json,
    _read_jsonl,
    _sha256,
    _write_json,
    _write_jsonl,
)


DECISIONS = {
    "native:pixelstopolygons": (
        "L3_01_09_07",
        "accept_existing_stable_l3_proposal",
        "L3_01_09_03",
        "The stable raster-vector conversion class already covers raster cells converted to polygons.",
    ),
    "native:smoothgeometry": (
        "L3_02_05_02",
        "propose_new_taxonomy_class",
        "L3_02_05_02",
        "Iterative curve smoothing is distinct from simplification and has no stable106 equivalent.",
    ),
    "qgis:delaunaytriangulation": (
        "L3_06_01_02",
        "propose_new_taxonomy_class",
        "L3_06_01_02",
        "Delaunay triangle construction has no stable106 equivalent.",
    ),
}


def adjudicate_candidates(
    queue: list[dict[str, Any]],
    stable_taxonomy: dict[str, Any],
    experimental_taxonomy: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    candidates = {
        str(row.get("operator_id")): row
        for row in queue
        if row.get("review_route") == "experimental_114_candidate_not_admitted"
    }
    if set(candidates) != set(DECISIONS):
        raise ValueError("experimental candidate queue does not match the three reviewed operators")
    stable = {str(row.get("l3_code")): row for row in stable_taxonomy.get("l3_families") or []}
    experimental = {
        str(row.get("code")): row for row in experimental_taxonomy.get("added_classes") or []
    }

    rows: list[dict[str, Any]] = []
    for operator_id, (expected_experimental, decision, candidate_code, rationale) in DECISIONS.items():
        source = candidates[operator_id]
        if source.get("experimental_114_candidate_l3") != expected_experimental:
            raise ValueError(f"experimental candidate mismatch for {operator_id}")
        samples = source.get("samples") or []
        verified = [row for row in samples if row.get("source_verification") == "verified_sha256"]
        if len(verified) < 3 or len(verified) != len(samples):
            raise ValueError(f"fewer than three verified source samples for {operator_id}")
        family = stable.get(candidate_code) if decision.startswith("accept_existing") else experimental.get(candidate_code)
        if not family:
            raise ValueError(f"candidate L3 is absent from its taxonomy authority: {candidate_code}")
        rows.append(
            {
                "schema": "gis_recommend.qgis_mapping_gap_experimental_candidate_adjudication.v1",
                "operator_id": operator_id,
                "prior_experimental_l3": expected_experimental,
                "decision": decision,
                "candidate_l3_code": candidate_code,
                "candidate_l3_name": family.get("l3_name") or family.get("name"),
                "candidate_token_id": family.get("token_id"),
                "single_gap_records": int(source.get("single_gap_records") or 0),
                "source_sample_count": len(verified),
                "source_record_ids": [row.get("record_id") for row in verified],
                "source_sha256": [row.get("source_sha256") for row in verified],
                "rationale": rationale,
                "taxonomy_admission": (
                    "not_required_existing_l3"
                    if decision.startswith("accept_existing")
                    else "proposal_only"
                ),
                "mapping_admission": "proposal_only",
                "training_admission": "not_granted",
                "training_row_emitted": False,
                "production_merge": "not_granted",
            }
        )
    rows.sort(key=lambda row: row["operator_id"])
    existing = [row for row in rows if row["decision"].startswith("accept_existing")]
    summary = {
        "schema": "gis_recommend.qgis_mapping_gap_experimental_candidate_adjudication_summary.v1",
        "reviewed_candidate_count": len(rows),
        "accepted_existing_l3_count": len(existing),
        "accepted_existing_l3_single_gap_records": sum(row["single_gap_records"] for row in existing),
        "new_class_proposal_count": len(rows) - len(existing),
        "mapping_admission": "proposal_only",
        "training_rows_emitted": 0,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }
    return rows, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--stable-taxonomy", type=Path, required=True)
    parser.add_argument("--experimental-taxonomy", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    rows, summary = adjudicate_candidates(
        _read_jsonl(args.queue),
        _read_json(args.stable_taxonomy),
        _read_json(args.experimental_taxonomy),
    )
    rows_path = args.output_dir / "experimental_candidate_adjudications_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    hash_path = args.output_dir / "hash_ledger_v1.json"
    _write_jsonl(rows_path, rows)
    _write_json(summary_path, summary)
    _write_json(
        hash_path,
        {
            "schema": "gis_recommend.hash_ledger.v1",
            "inputs": {
                "queue": {"path": str(args.queue), "sha256": _sha256(args.queue)},
                "stable_taxonomy": {"path": str(args.stable_taxonomy), "sha256": _sha256(args.stable_taxonomy)},
                "experimental_taxonomy": {
                    "path": str(args.experimental_taxonomy),
                    "sha256": _sha256(args.experimental_taxonomy),
                },
            },
            "artifacts": {
                rows_path.name: _sha256(rows_path),
                summary_path.name: _sha256(summary_path),
            },
        },
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
