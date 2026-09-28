#!/usr/bin/env python3
"""Adjudicate targeted QGIS mapping gaps against existing stable L3 classes."""

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
    "native:rasterize": ("L3_01_09_03", "Rasterizes vector features into cells."),
    "native:calculatevectoroverlaps": ("", "Computes overlay metrics; Calculate Field is not an exact task contract."),
    "native:extractwithindistance": ("L3_02_06_03", "Extracts features by a within-distance spatial relation."),
    "native:sumlinelengths": ("", "Aggregates line lengths by polygon; no exact stable vector-summary class exists."),
    "saga:polygonclipping": ("L3_02_02_06", "Clips polygon features by polygon geometry."),
    "qgis:variabledistancebuffer": ("L3_02_01_01", "Creates buffers with feature-specific distances."),
    "native:convexhull": ("L3_02_05_12", "Creates convex-hull minimum bounding geometry."),
    "qgis:generatepointspixelcentroidsalongline": ("L3_02_06_06", "Creates sample points at raster-pixel centroids along lines."),
    "qgis:randompointsinlayerbounds": ("L3_02_06_06", "Creates random sample points inside layer bounds."),
    "native:rasterlayerzonalstats": ("L3_03_02_01", "Computes raster statistics for vector zones."),
    "native:boundary": ("", "Boundary output type depends on input geometry and has no exact stable class."),
    "native:randompointsinpolygons": ("L3_02_06_06", "Creates random sample points inside polygons."),
    "native:extractzvalues": ("L3_01_02_06", "Calculates fields from feature Z values."),
    "native:pointonsurface": ("L3_02_05_11", "Converts each feature to an interior point."),
    "native:randompointsinextent": ("L3_02_06_06", "Creates random sample points inside an extent."),
    "native:generatepointspixelcentroidsinsidepolygons": ("L3_02_06_06", "Creates sample points at raster-pixel centroids inside polygons."),
    "native:randompointsonlines": ("L3_02_06_06", "Creates random sample points on line features."),
}


def adjudicate_exact_existing_l3(
    queue: list[dict[str, Any]],
    taxonomy: dict[str, Any],
    *,
    decisions: dict[str, tuple[str, str]] = DECISIONS,
    minimum_verified_sources: int = 3,
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any]]:
    by_operator = {str(row.get("operator_id") or ""): row for row in queue}
    if set(by_operator) != set(decisions):
        raise ValueError("targeted queue does not match the frozen operator decisions")
    families = {
        str(row.get("l3_code") or ""): row
        for row in taxonomy.get("l3_families") or []
    }

    rows: list[dict[str, Any]] = []
    mappings: dict[str, str] = {}
    for operator_id, (candidate_code, rationale) in decisions.items():
        source = by_operator[operator_id]
        verified = {
            str(sample.get("source_sha256") or "")
            for sample in source.get("samples") or []
            if sample.get("source_verification") == "verified_sha256"
            and str(sample.get("source_sha256") or "")
        }
        if not candidate_code:
            decision = "defer_no_exact_stable_l3"
        elif len(verified) < minimum_verified_sources:
            decision = "defer_insufficient_verified_support"
        elif candidate_code not in families:
            raise ValueError(f"candidate L3 is absent from stable taxonomy: {candidate_code}")
        else:
            decision = "accept_existing_stable_l3_proposal"
            mappings[operator_id] = candidate_code
        family = families.get(candidate_code) or {}
        rows.append(
            {
                "schema": "gis_recommend.qgis_mapping_gap_exact_existing_l3_adjudication.v1",
                "operator_id": operator_id,
                "decision": decision,
                "candidate_l3_code": candidate_code,
                "candidate_l3_name": family.get("l3_name", ""),
                "candidate_token_id": family.get("token_id"),
                "verified_source_count": len(verified),
                "source_sample_count": len(verified),
                "source_sha256": sorted(verified),
                "single_gap_records": int(source.get("single_gap_records") or 0),
                "all_gap_records": int(source.get("all_gap_records") or 0),
                "rationale": rationale,
                "taxonomy_admission": (
                    "not_required_existing_l3"
                    if candidate_code
                    else "not_granted_no_exact_class"
                ),
                "mapping_admission": (
                    "proposal_only"
                    if decision == "accept_existing_stable_l3_proposal"
                    else "not_granted"
                ),
                "training_admission": "not_granted",
                "training_row_emitted": False,
                "production_merge": "not_granted",
            }
        )
    rows.sort(key=lambda row: row["operator_id"])
    delta = {
        "schema": "gis_recommend.qgis_mapping_gap_exact_existing_l3_delta_proposal.v1",
        "status": "source_reviewed_proposal",
        "alias_mappings": dict(sorted(mappings.items())),
        "restored_l3_mappings": {},
        "operator_count": len(mappings),
        "taxonomy_admission": "not_required_existing_l3",
        "mapping_admission": "proposal_only",
        "training_admission": "not_granted",
        "production_merge": "not_granted",
    }
    summary = {
        "schema": "gis_recommend.qgis_mapping_gap_exact_existing_l3_summary.v1",
        "reviewed_operator_count": len(rows),
        "accepted_operator_count": len(mappings),
        "deferred_operator_count": len(rows) - len(mappings),
        "accepted_single_gap_records": sum(
            row["single_gap_records"]
            for row in rows
            if row["decision"] == "accept_existing_stable_l3_proposal"
        ),
        "minimum_verified_sources": minimum_verified_sources,
        "mapping_admission": "proposal_only",
        "training_rows_emitted": 0,
        "production_merge": "not_granted",
    }
    return rows, delta, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--taxonomy", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    rows, delta, summary = adjudicate_exact_existing_l3(
        _read_jsonl(args.queue), _read_json(args.taxonomy)
    )
    rows_path = args.output_dir / "adjudications_v1.jsonl"
    delta_path = args.output_dir / "mapping_delta_proposal_v1.json"
    summary_path = args.output_dir / "summary_v1.json"
    _write_jsonl(rows_path, rows)
    _write_json(delta_path, delta)
    _write_json(summary_path, summary)
    _write_json(
        args.output_dir / "hash_ledger_v1.json",
        {
            "schema": "gis_recommend.hash_ledger.v1",
            "inputs": {
                "queue": {"path": str(args.queue), "sha256": _sha256(args.queue)},
                "taxonomy": {
                    "path": str(args.taxonomy),
                    "sha256": _sha256(args.taxonomy),
                },
            },
            "artifacts": {
                rows_path.name: _sha256(rows_path),
                delta_path.name: _sha256(delta_path),
                summary_path.name: _sha256(summary_path),
            },
        },
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
