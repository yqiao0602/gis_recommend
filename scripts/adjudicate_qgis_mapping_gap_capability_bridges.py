#!/usr/bin/env python3
"""Adjudicate the stable106 follow-up top-20 mapping-gap operators."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any, Iterable


DECISIONS = {
    "native:explodelines": (
        "defer_new_taxonomy_class",
        "",
        "Splitting every line at its vertices is narrower than multipart-to-singlepart and is not split-line-at-point.",
    ),
    "native:pointsalonglines": (
        "accept_existing_stable_l3_proposal",
        "L3_02_06_06",
        "Creates point samples at a specified interval along input geometries.",
    ),
    "gdal:contour": (
        "accept_existing_stable_l3_proposal",
        "L3_01_09_03",
        "Converts raster-band values at an interval into vector contour lines.",
    ),
    "native:splitwithlines": (
        "defer_new_taxonomy_class",
        "",
        "Splits line or polygon features using line features; existing split-line-at-point is not equivalent.",
    ),
    "native:pixelstopoints": (
        "accept_existing_stable_l3_proposal",
        "L3_01_09_03",
        "Converts raster cells into vector point features carrying pixel values.",
    ),
    "gdal:proximity": (
        "defer_new_taxonomy_class",
        "",
        "Produces a raster distance surface and has no exact stable raster-proximity class.",
    ),
    "qgis:exportaddgeometrycolumns": (
        "accept_existing_stable_l3_proposal",
        "L3_01_02_06",
        "Calculates geometry-derived attribute values and writes them as fields.",
    ),
}

TOP20_DECISIONS = {
    **{operator_id: (*decision, "stable" if decision[1] else "") for operator_id, decision in DECISIONS.items()},
    "native:splitvectorlayer": (
        "defer_new_taxonomy_class",
        "",
        "Splits one layer into multiple outputs by unique attribute value; this is not single-value extract-by-attribute.",
        "",
    ),
    "grass7:v.clean": (
        "defer_parameter_dependent",
        "",
        "The selected cleaning tool parameter changes the operation among break, snap, duplicate removal, and other semantics.",
        "",
    ),
    "native:rasterlayerstatistics": (
        "accept_existing_stable_l3_proposal",
        "L3_03_02_05",
        "Computes whole-raster summary statistics and therefore matches stable Global Statistics.",
        "stable",
    ),
    "native:package": (
        "route_support_export_sidecar",
        "",
        "Packages layers into a GeoPackage container and is an export/container boundary rather than a core analysis step.",
        "",
    ),
    "native:geometrybyexpression": (
        "defer_parameter_dependent",
        "",
        "An arbitrary geometry expression determines the actual transformation, so the operator ID has no single static L3 meaning.",
        "",
    ),
    "gdal:gdal2tiles": (
        "route_support_export_sidecar",
        "",
        "Exports a raster as a web-tile pyramid and belongs to presentation/export support, not the core target chain.",
        "",
    ),
    "qgis:randompointsalongline": (
        "accept_existing_stable_l3_proposal",
        "L3_02_06_06",
        "Generates random sample points constrained to input line geometries.",
        "stable",
    ),
    "native:pixelstopolygons": (
        "accept_existing_stable_l3_proposal",
        "L3_01_09_03",
        "Converts raster pixels to vector polygons and is covered by stable Raster-Vector Conversion.",
        "stable",
    ),
    "native:smoothgeometry": (
        "accept_new_taxonomy_class_proposal",
        "L3_02_05_02",
        "Smooths feature geometries; the exact legacy Smooth class exists only in the experimental taxonomy.",
        "experimental",
    ),
    "qgis:delaunaytriangulation": (
        "accept_new_taxonomy_class_proposal",
        "L3_06_01_02",
        "Constructs a Delaunay triangulation; the exact legacy class requires explicit stable-N parent-family admission.",
        "experimental",
    ),
    "qgis:eliminateselectedpolygons": (
        "defer_new_taxonomy_class",
        "",
        "Merges selected polygons into adjacent features using boundary or area rules; no stable class is exact.",
        "",
    ),
    "native:shortestpathpointtopoint": (
        "defer_new_taxonomy_class",
        "",
        "Solves a network shortest path between two points; stable101 has no network-routing class.",
        "",
    ),
    "native:createpointslayerfromtable": (
        "defer_new_taxonomy_class",
        "",
        "Creates spatial points from table coordinate fields; Feature to Point requires existing feature geometry and is not equivalent.",
        "",
    ),
}


def adjudicate_bridges(
    queue: list[dict[str, Any]], taxonomy: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    bridge_rows = {
        str(row.get("operator_id")): row
        for row in queue
        if row.get("review_route") == "existing_bridge_needs_taxonomy_review"
    }
    if set(bridge_rows) != set(DECISIONS):
        raise ValueError("capability bridge queue does not match the seven reviewed operators")

    families = {str(row.get("l3_code")): row for row in taxonomy.get("l3_families") or []}
    rows: list[dict[str, Any]] = []
    for operator_id, (decision, candidate_code, rationale) in DECISIONS.items():
        source = bridge_rows[operator_id]
        samples = source.get("samples") or []
        verified = [row for row in samples if row.get("source_verification") == "verified_sha256"]
        if len(verified) < 3 or len(verified) != len(samples):
            raise ValueError(f"fewer than three verified source samples for {operator_id}")
        family = families.get(candidate_code) if candidate_code else None
        if candidate_code and not family:
            raise ValueError(f"candidate L3 is absent from stable taxonomy: {candidate_code}")
        rows.append(
            {
                "schema": "gis_recommend.qgis_mapping_gap_capability_bridge_adjudication.v1",
                "operator_id": operator_id,
                "prior_capability_bridge": source.get("crosswalk_l3_code"),
                "decision": decision,
                "candidate_l3_code": candidate_code,
                "candidate_l3_name": family.get("l3_name") if family else "",
                "candidate_token_id": family.get("token_id") if family else None,
                "single_gap_records": int(source.get("single_gap_records") or 0),
                "source_sample_count": len(verified),
                "source_record_ids": [row.get("record_id") for row in verified],
                "source_sha256": [row.get("source_sha256") for row in verified],
                "rationale": rationale,
                "taxonomy_admission": "not_required_existing_l3" if candidate_code else "not_granted_gap_only",
                "mapping_admission": "proposal_only",
                "training_admission": "not_granted",
                "training_row_emitted": False,
                "production_merge": "not_granted",
            }
        )
    rows.sort(key=lambda row: row["operator_id"])
    accepted = [row for row in rows if row["candidate_l3_code"]]
    summary = {
        "schema": "gis_recommend.qgis_mapping_gap_capability_bridge_adjudication_summary.v1",
        "taxonomy_profile": taxonomy.get("taxonomy_id") or taxonomy.get("profile"),
        "reviewed_bridge_count": len(rows),
        "accepted_existing_l3_count": len(accepted),
        "accepted_single_gap_records": sum(row["single_gap_records"] for row in accepted),
        "deferred_taxonomy_gap_count": len(rows) - len(accepted),
        "mapping_admission": "proposal_only",
        "training_rows_emitted": 0,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }
    return rows, summary


def adjudicate_top20(
    queue: list[dict[str, Any]],
    stable_taxonomy: dict[str, Any],
    experimental_taxonomy: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_rows = {str(row.get("operator_id")): row for row in queue}
    if len(queue) != 20 or set(source_rows) != set(TOP20_DECISIONS):
        raise ValueError("mapping-gap queue does not match the reviewed top-20 operators")

    stable = {
        str(row.get("l3_code")): row for row in stable_taxonomy.get("l3_families") or []
    }
    experimental = {
        str(row.get("code")): row for row in experimental_taxonomy.get("added_classes") or []
    }
    rows: list[dict[str, Any]] = []
    for operator_id, (decision, candidate_code, rationale, authority) in TOP20_DECISIONS.items():
        source = source_rows[operator_id]
        samples = source.get("samples") or []
        verified = [row for row in samples if row.get("source_verification") == "verified_sha256"]
        if len(verified) < 3 or len(verified) != len(samples):
            raise ValueError(f"fewer than three verified source samples for {operator_id}")
        family = stable.get(candidate_code) if authority == "stable" else experimental.get(candidate_code)
        if candidate_code and not family:
            raise ValueError(f"candidate L3 is absent from {authority} taxonomy: {candidate_code}")
        rows.append(
            {
                "schema": "gis_recommend.qgis_mapping_gap_top20_adjudication_proposal.v1",
                "rank": int(source.get("rank") or 0),
                "operator_id": operator_id,
                "review_route": source.get("review_route"),
                "prior_capability_bridge": source.get("crosswalk_l3_code") or "",
                "prior_experimental_l3": source.get("experimental_114_candidate_l3") or "",
                "decision": decision,
                "candidate_l3_code": candidate_code,
                "candidate_l3_name": (family or {}).get("l3_name") or (family or {}).get("name") or "",
                "candidate_token_id": (family or {}).get("token_id") if authority == "stable" else None,
                "reference_experimental_token_id": (
                    (family or {}).get("token_id") if authority == "experimental" else None
                ),
                "candidate_authority": authority,
                "single_gap_records": int(source.get("single_gap_records") or 0),
                "source_sample_count": len(verified),
                "source_record_ids": [row.get("record_id") for row in verified],
                "source_sha256": [row.get("source_sha256") for row in verified],
                "rationale": rationale,
                "taxonomy_admission": (
                    "not_required_existing_l3"
                    if authority == "stable"
                    else "proposal_only_new_class"
                    if authority == "experimental"
                    else "not_granted_gap_or_boundary"
                ),
                "mapping_admission": "proposal_only",
                "training_admission": "not_granted",
                "training_row_emitted": False,
                "production_merge": "not_granted",
            }
        )
    rows.sort(key=lambda row: row["rank"])
    counts = {
        decision: sum(row["decision"] == decision for row in rows)
        for decision in {
            "accept_existing_stable_l3_proposal",
            "accept_new_taxonomy_class_proposal",
            "defer_new_taxonomy_class",
            "defer_parameter_dependent",
            "route_support_export_sidecar",
        }
    }
    existing = [row for row in rows if row["decision"] == "accept_existing_stable_l3_proposal"]
    summary = {
        "schema": "gis_recommend.qgis_mapping_gap_top20_adjudication_proposal_summary.v1",
        "stable_taxonomy_profile": stable_taxonomy.get("taxonomy_id") or stable_taxonomy.get("profile"),
        "experimental_taxonomy_profile": experimental_taxonomy.get("profile"),
        "reviewed_operator_count": len(rows),
        "reviewed_source_sample_count": sum(row["source_sample_count"] for row in rows),
        "queue_single_gap_records": sum(row["single_gap_records"] for row in rows),
        "accepted_existing_l3_count": counts["accept_existing_stable_l3_proposal"],
        "accepted_existing_l3_single_gap_records": sum(row["single_gap_records"] for row in existing),
        "new_taxonomy_proposal_count": counts["accept_new_taxonomy_class_proposal"],
        "deferred_new_taxonomy_count": counts["defer_new_taxonomy_class"],
        "parameter_dependent_count": counts["defer_parameter_dependent"],
        "support_export_sidecar_count": counts["route_support_export_sidecar"],
        "mapping_admission": "proposal_only",
        "training_rows_emitted": 0,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }
    return rows, summary


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", dir=path.parent, delete=False) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def _write_json(path: Path, value: Any) -> None:
    _atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    _atomic_write(
        path,
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--taxonomy", type=Path, required=True)
    parser.add_argument("--experimental-taxonomy", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    rows, summary = adjudicate_top20(
        _read_jsonl(args.queue),
        _read_json(args.taxonomy),
        _read_json(args.experimental_taxonomy),
    )
    rows_path = args.output_dir / "top20_adjudication_proposals_v1.jsonl"
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
