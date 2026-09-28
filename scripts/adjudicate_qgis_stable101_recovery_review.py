#!/usr/bin/env python3
"""Write confirmed adjudication sidecars for recovered stable101 review batches."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REVIEW = (
    ROOT
    / "docs/reports/qgis_mapping_high_impact_blockers_2026-07-24"
    / "stable101_source_review_50_v1/recovered_review_v1/recovery_review_29_v1.jsonl"
)
DEFAULT_OUTPUT_DIR = DEFAULT_REVIEW.parent

BATCH_1_DECISIONS = {
    "qgis_stable101_r3_chip_pair_dag": (
        "accept_recovered",
        "Source-backed call sites prove reprojection, mask rasterization, and separate image/mask clip branches.",
    ),
    "qgis_stable101_r6_processing_csv": (
        "accept_recovered",
        "One processAlgorithm path proves geometry repair, independent optional filtering/reprojection, two field refactors, and save.",
    ),
    "qgis_stable101_r42_cn_overlay_preprocess": (
        "accept_recovered",
        "Call sites prove three conditional reprojections followed by landuse-soil and subbasin intersections.",
    ),
    "qgis_stable101_r9_soil_fix_clip": (
        "accept_recovered",
        "The repaired soil layer is the direct input to clip; acquisition remains a declared prerequisite.",
    ),
    "qgis_stable101_r10_basin_overlay": (
        "accept_recovered",
        "The basin is conditionally reprojected to WGS84 and then used as the soil intersection overlay.",
    ),
    "qgis_stable101_r11_soil_postprocess": (
        "accept_recovered",
        "The source proves a direct fix, clip, reproject, and final-fix data path.",
    ),
    "qgis_stable101_r13_classification_polygonize": (
        "accept_recovered",
        "The selected reclassification branch feeds polygonize; low-level category updates remain omitted.",
    ),
    "qgis_stable101_r13_zonal_summary": (
        "accept_recovered",
        "The independent zonal-statistics unit and its four retained statistics are source-backed.",
    ),
    "qgis_stable101_r23_raster_preprocess": (
        "accept_recovered",
        "The warp output feeds fill-nodata and the entrypoint is called from the base execution loop.",
    ),
    "qgis_stable101_r23_vector_mask": (
        "defer_missing_call_graph",
        "The source defines _rasterize but has no call site; a concrete subclass is required to prove rasterize-to-mask dependency.",
    ),
}

BATCH_2_DECISIONS = {
    "qgis_stable101_r24_vector_mask": (
        "accept_recovered",
        "The entrypoint proves the point-only buffer branch and the shared clip-to-rasterize path.",
    ),
    "qgis_stable101_r24_raster_mask": (
        "accept_recovered",
        "The execution loop passes the warped raster into a calculator that creates the binary opportunity mask.",
    ),
    "qgis_stable101_r29_dem_baseline": (
        "accept_recovered",
        "The aligned DEM baseline is calculator input B for A-B before the target-mask clip.",
    ),
    "qgis_stable101_r29_polygon_baseline": (
        "accept_recovered",
        "The polygon baseline helper rasterizes source values into calculator input B before the same clip.",
    ),
    "qgis_stable101_r34_fix_geometries": (
        "accept_recovered",
        "The standalone utility directly maps its vector input to geometry-repair output.",
    ),
    "qgis_stable101_r34_singleparts": (
        "accept_recovered",
        "The standalone utility directly converts multipart input to singlepart output.",
    ),
    "qgis_stable101_r34_clip": (
        "accept_recovered",
        "The standalone utility directly clips an input vector by an overlay vector.",
    ),
    "qgis_stable101_r34_extract_expression": (
        "accept_recovered",
        "The function is an independent expression-extraction unit with unrelated dynamic helpers excluded.",
    ),
    "qgis_stable101_r36_watershed_outputs": (
        "defer_mapping_gap",
        "The source DAG and task text are accepted, but three GRASS operator IDs lack admitted stable101 mappings.",
    ),
    "qgis_stable101_r37_web_vector_fix": (
        "accept_recovered",
        "A successfully materialized non-empty Web vector is passed directly to geometry repair.",
    ),
}

BATCH_3_DECISIONS = {
    "qgis_stable101_r37_protected_sites_merge": (
        "defer_dynamic_loop_cardinality",
        "Geometry repair runs once per successful service response, so a fixed two-token chain cannot represent the runtime call count faithfully.",
    ),
    "qgis_stable101_r38_complete_measure": (
        "accept_recovered",
        "Selected parcel features are explicitly repaired before the omitted low-level simplification and measure-field calculation.",
    ),
    "qgis_stable101_r38_blocks_selection": (
        "accept_recovered",
        "Geometry repair is source-backed and explicitly optional when the selected-feature set is non-empty.",
    ),
    "qgis_stable101_r38_registered_selection": (
        "accept_recovered",
        "The independent registered-feature entrypoint conditionally repairs a non-empty selected-feature set.",
    ),
    "qgis_stable101_r38_owner_layers": (
        "accept_recovered",
        "Two explicit repair calls operate on independent owner and occupant inputs and remain parallel in the recovered dependency graph.",
    ),
    "qgis_stable101_r40_dissolve_overlap": (
        "accept_recovered",
        "The helper performs one attribute dissolve and returns that result, with the original input retained only as an empty-result fallback.",
    ),
    "qgis_stable101_r40_priority_stack": (
        "defer_dynamic_loop_cardinality",
        "Difference, repair, union, and cleanup calls repeat across a priority loop with branch-dependent skips, so the static call-site sequence is not a faithful fixed target.",
    ),
    "qgis_stable101_r48_protected_join": (
        "accept_recovered",
        "The protected-area layer is reprojected to EPSG:2154 and then used directly as the spatial-join layer for buildings.",
    ),
    "qgis_stable101_r48_overlap_groups": (
        "accept_recovered",
        "Multi-intersection is a valid intermediate building self-intersection step; downstream grouping and geometry merge remain declared omissions.",
    ),
}

BATCHES = {1: BATCH_1_DECISIONS, 2: BATCH_2_DECISIONS, 3: BATCH_3_DECISIONS}
BATCH_STARTS = {1: 1, 2: 11, 3: 21}


@dataclass(frozen=True)
class AdjudicationResult:
    rows: list[dict[str, Any]]
    summary: dict[str, Any]


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in Path(path).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def build_adjudications(review_jsonl: Path, *, batch_number: int) -> AdjudicationResult:
    if batch_number not in BATCHES:
        raise ValueError(f"unsupported adjudication batch: {batch_number}")
    reviews = _load_jsonl(review_jsonl)
    by_id = {row["unit_id"]: row for row in reviews}
    if len(by_id) != len(reviews):
        raise ValueError("review unit_id values must be unique")

    decisions = BATCHES[batch_number]
    rows: list[dict[str, Any]] = []
    for position, (unit_id, (decision, reason)) in enumerate(
        decisions.items(), start=BATCH_STARTS[batch_number]
    ):
        review = by_id[unit_id]
        accepted = decision == "accept_recovered"
        structure_accepted = accepted or decision in {
            "defer_mapping_gap",
            "defer_dynamic_loop_cardinality",
        }
        dynamic_cardinality = decision == "defer_dynamic_loop_cardinality"
        rows.append(
            {
                "schema_version": "qgis_stable101_recovery_adjudication_v1",
                "batch_number": batch_number,
                "batch_position": position,
                "unit_id": unit_id,
                "review_index": review["review_index"],
                "source_sha256": review["source_sha256"],
                "source_path": review["source_path"],
                "operator_sequence": review["operator_sequence"],
                "l3_code_sequence": review["l3_code_sequence"],
                "task_name": review["draft_task_name"],
                "task_description": review["draft_task_description"],
                "boundary_decision": "accepted" if structure_accepted else "deferred",
                "dependency_decision": (
                    "dynamic_cardinality_not_representable"
                    if dynamic_cardinality
                    else "accepted" if structure_accepted else "not_proven"
                ),
                "task_text_fidelity": "accepted" if structure_accepted else "not_adjudicated",
                "final_decision": decision,
                "decision_reason": reason,
                "confirmation_status": "jointly_confirmed",
                "adjudication_status": (
                    "accepted_pending_dedup_and_export"
                    if accepted
                    else (
                        "deferred_mapping_gap"
                        if decision == "defer_mapping_gap"
                        else (
                            "deferred_dynamic_loop_cardinality"
                            if dynamic_cardinality
                            else "deferred"
                        )
                    )
                ),
                "training_admission": (
                    "not_granted_pending_dedup_and_export" if accepted else "not_granted"
                ),
                "validation_eligible": False,
                "test_eligible": False,
            }
        )

    counts = Counter(row["final_decision"] for row in rows)
    summary = {
        "schema": "gis_recommend.qgis_stable101_recovery_adjudication_summary.v1",
        "batch_number": batch_number,
        "counts": {
            "rows": len(rows),
            "accept_recovered": counts["accept_recovered"],
            "deferred": sum(
                count for key, count in counts.items() if key.startswith("defer")
            ),
            "rejected": sum(
                count for key, count in counts.items() if key.startswith("reject")
            ),
        },
        "decision": {
            "confirmation_status": "jointly_confirmed",
            "source_review_fields_modified": False,
            "training_admission": "not_granted",
            "validation_eligible": False,
            "test_eligible": False,
            "next_gate": (
                "deduplicate accepted recovered rows before recovered-only export"
                if batch_number == 3
                else "review remaining recovered units, then deduplicate accepted rows before export"
            ),
        },
    }
    return AdjudicationResult(rows=rows, summary=summary)


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def write_outputs(
    result: AdjudicationResult, output_dir: Path, review_jsonl: Path
) -> dict[str, Path]:
    start = min(row["batch_position"] for row in result.rows)
    end = max(row["batch_position"] for row in result.rows)
    stem = f"recovery_adjudications_{start}_{end}_v1"
    output_dir = Path(output_dir)
    adjudications = output_dir / f"{stem}.jsonl"
    summary = output_dir / f"{stem}_summary.json"
    hash_ledger = output_dir / f"{stem}_hashes.json"

    _atomic_write(
        adjudications,
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
            for row in result.rows
        ),
    )
    _atomic_write(
        summary,
        json.dumps(result.summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "source_inputs": {
            review_jsonl.name: {"path": str(review_jsonl), "sha256": _sha256(review_jsonl)}
        },
        "artifacts": {
            path.name: {
                "path": str(path),
                "sha256": _sha256(path),
                "bytes": path.stat().st_size,
            }
            for path in (adjudications, summary)
        },
    }
    _atomic_write(
        hash_ledger,
        json.dumps(ledger, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    return {
        "adjudications": adjudications,
        "summary": summary,
        "hash_ledger": hash_ledger,
    }


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-jsonl", type=Path, default=DEFAULT_REVIEW)
    parser.add_argument("--batch-number", type=int, required=True)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)
    result = build_adjudications(args.review_jsonl, batch_number=args.batch_number)
    return write_outputs(result, args.output_dir, args.review_jsonl)


if __name__ == "__main__":
    main()
