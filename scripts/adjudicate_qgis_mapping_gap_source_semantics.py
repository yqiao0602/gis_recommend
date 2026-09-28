#!/usr/bin/env python3
"""Adjudicate source-semantic QGIS mapping gaps without guessing L3 labels."""

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
    "native:splitvectorlayer": {
        "decision": "propose_new_taxonomy_class",
        "capability": "Split Features by Attribute",
        "rationale": "Partitions one layer into multiple outputs by unique field value; a single extract-by-attribute step loses the multi-output task.",
    },
    "grass7:v.clean": {
        "decision": "defer_parameter_conditioned_mapping",
        "capability": "GRASS Vector Topology Cleaning",
        "required_resolver": "literal_tool_enum",
        "rationale": "The selected cleaning tool determines the operation; reviewed source uses literal tool [0], which must be resolved against provider-version enums.",
    },
    "native:rasterlayerstatistics": {
        "decision": "accept_existing_stable_l3_proposal",
        "candidate_l3_code": "L3_03_02_05",
        "capability": "Global Raster Statistics",
        "rationale": "Computes whole-band summary statistics for a raster layer.",
    },
    "native:package": {
        "decision": "defer_support_export_boundary",
        "capability": "Package Layers to GeoPackage",
        "rationale": "Packages heterogeneous layers into one GeoPackage and is an output/container boundary rather than a fixed analysis transformation.",
    },
    "native:geometrybyexpression": {
        "decision": "defer_parameter_conditioned_mapping",
        "capability": "Geometry by Expression",
        "required_resolver": "qgis_expression_semantics",
        "rationale": "The expression determines the geometry operation; reviewed source includes a buffer expression, but the operator also supports unrelated transformations.",
    },
    "gdal:gdal2tiles": {
        "decision": "propose_new_taxonomy_class",
        "capability": "Raster Tile Pyramid Export",
        "rationale": "Generates an OSGeo tile pyramid, viewers, and metadata; no stable106 class represents tiled web-map publication.",
    },
    "qgis:randompointsalongline": {
        "decision": "accept_existing_stable_l3_proposal",
        "candidate_l3_code": "L3_02_06_06",
        "capability": "Random Point Sampling Along Lines",
        "rationale": "Creates point samples on input lines with count and minimum-distance controls.",
    },
    "qgis:eliminateselectedpolygons": {
        "decision": "propose_new_taxonomy_class",
        "capability": "Eliminate Sliver Polygons",
        "rationale": "Merges selected polygons into adjacent polygons using an area or shared-boundary rule; no stable106 class is equivalent.",
    },
    "native:shortestpathpointtopoint": {
        "decision": "propose_new_taxonomy_class",
        "capability": "Point-to-Point Network Shortest Path",
        "rationale": "Computes a shortest or fastest route on a network; stable106 has no network-routing class.",
    },
    "native:createpointslayerfromtable": {
        "decision": "propose_new_taxonomy_class",
        "capability": "XY Table to Point",
        "rationale": "Creates point geometry from X/Y table fields and a CRS; existing feature-to-point covers geometry-derived locations, not table coordinates.",
    },
}


def adjudicate_source_semantics(
    queue: list[dict[str, Any]], taxonomy: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_rows = {
        str(row.get("operator_id")): row
        for row in queue
        if row.get("review_route") == "pending_source_semantic_review"
    }
    if set(source_rows) != set(DECISIONS):
        raise ValueError("source-semantic queue does not match the ten reviewed operators")
    families = {str(row.get("l3_code")): row for row in taxonomy.get("l3_families") or []}

    rows: list[dict[str, Any]] = []
    for operator_id, adjudication in DECISIONS.items():
        source = source_rows[operator_id]
        samples = source.get("samples") or []
        verified = [row for row in samples if row.get("source_verification") == "verified_sha256"]
        if len(verified) < 3 or len(verified) != len(samples):
            raise ValueError(f"fewer than three verified source samples for {operator_id}")
        candidate_code = str(adjudication.get("candidate_l3_code") or "")
        family = families.get(candidate_code) if candidate_code else None
        if candidate_code and not family:
            raise ValueError(f"candidate L3 is absent from stable taxonomy: {candidate_code}")
        rows.append(
            {
                "schema": "gis_recommend.qgis_mapping_gap_source_semantic_adjudication.v1",
                "operator_id": operator_id,
                "decision": adjudication["decision"],
                "candidate_capability": adjudication["capability"],
                "candidate_l3_code": candidate_code,
                "candidate_l3_name": family.get("l3_name") if family else "",
                "candidate_token_id": family.get("token_id") if family else None,
                "required_resolver": adjudication.get("required_resolver", ""),
                "single_gap_records": int(source.get("single_gap_records") or 0),
                "source_sample_count": len(verified),
                "source_record_ids": [row.get("record_id") for row in verified],
                "source_sha256": [row.get("source_sha256") for row in verified],
                "rationale": adjudication["rationale"],
                "taxonomy_admission": "not_required_existing_l3" if candidate_code else "not_granted",
                "mapping_admission": "proposal_only" if candidate_code else "not_granted",
                "training_admission": "not_granted",
                "training_row_emitted": False,
                "production_merge": "not_granted",
            }
        )
    rows.sort(key=lambda row: row["operator_id"])

    def count(decision: str) -> int:
        return sum(row["decision"] == decision for row in rows)

    summary = {
        "schema": "gis_recommend.qgis_mapping_gap_source_semantic_adjudication_summary.v1",
        "reviewed_operator_count": len(rows),
        "reviewed_single_gap_records": sum(row["single_gap_records"] for row in rows),
        "accepted_existing_l3_count": count("accept_existing_stable_l3_proposal"),
        "new_class_gap_count": count("propose_new_taxonomy_class"),
        "parameter_conditioned_count": count("defer_parameter_conditioned_mapping"),
        "support_export_boundary_count": count("defer_support_export_boundary"),
        "training_rows_emitted": 0,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }
    return rows, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--taxonomy", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    rows, summary = adjudicate_source_semantics(_read_jsonl(args.queue), _read_json(args.taxonomy))
    rows_path = args.output_dir / "adjudications_v1.jsonl"
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
                "taxonomy": {"path": str(args.taxonomy), "sha256": _sha256(args.taxonomy)},
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
