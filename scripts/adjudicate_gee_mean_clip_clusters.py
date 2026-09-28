#!/usr/bin/env python3
"""Validate and summarize the 35-cluster GEE mean/clip adjudications."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from scripts.build_gee_strict_candidate_source_audit import (
    _atomic_write,
    _json_text,
    _jsonl_text,
    _load_jsonl,
    _sha256,
)


ROOT = Path(__file__).resolve().parents[1]
BASE_DIR = (
    ROOT
    / "docs/reports/gee_raster_core_v1_review_split_2026-07-24"
    / "gee_raster_core_batch_training_package_v1/strict_candidate_v1"
    / "semantic_pattern_census_combined_11397_v1/authority_review_v1"
    / "mean_clip_cluster_review_v1"
)
DEFAULT_REVIEW_PACKET = BASE_DIR / "gee_mean_clip_cluster_review_35_v1.jsonl"
DEFAULT_ADJUDICATIONS = tuple(
    BASE_DIR
    / "adjudications"
    / f"gee_mean_clip_cluster_adjudications_{start}_{start + 4}_v1.jsonl"
    for start in range(1, 36, 5)
)
DEFAULT_OUTPUT_DIR = BASE_DIR
OUTPUT_PREFIX = "gee_mean_clip_cluster_adjudication_rollup_35_v1"
CALIBRATION_PREFIX = "gee_mean_clip_repaired_rule_calibration_35_v1"
REPAIRED_CENSUS_DIR = BASE_DIR.parents[2] / "semantic_pattern_census_repaired_v2_3_1"
DEFAULT_REPAIRED_CENSUS = (
    REPAIRED_CENSUS_DIR
    / "strict_3106/gee_semantic_pattern_census_strict_3106_repaired_v2_3_1.jsonl",
    REPAIRED_CENSUS_DIR
    / "remaining_8291/gee_semantic_pattern_census_remaining_8291_repaired_v2_3_1.jsonl",
)


def _wilson_lower(successes: int, total: int, z: float = 1.96) -> float:
    if total == 0:
        return 0.0
    p = successes / total
    denominator = 1 + z * z / total
    centre = p + z * z / (2 * total)
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total)
    return (centre - margin) / denominator


def summarize_adjudications(
    review_rows: list[dict[str, Any]],
    adjudications: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    review_by_index = {int(row["review_index"]): row for row in review_rows}
    if len(review_by_index) != len(review_rows):
        raise ValueError("review packet contains duplicate indices")
    expected_indices = list(range(1, len(review_rows) + 1))
    if sorted(review_by_index) != expected_indices:
        raise ValueError("review packet indices are not continuous")
    human_fields = (
        "human_completeness",
        "human_fidelity",
        "human_adjudication",
        "human_notes",
    )
    if any(row.get(field) for row in review_rows for field in human_fields):
        raise ValueError("original review packet human fields must remain blank")

    adjudication_by_index = {
        int(row["review_index"]): row for row in adjudications
    }
    if len(adjudication_by_index) != len(adjudications):
        raise ValueError("adjudications contain duplicate indices")
    if sorted(adjudication_by_index) != expected_indices:
        raise ValueError("adjudications do not cover every review index")

    rollup: list[dict[str, Any]] = []
    for review_index in expected_indices:
        review = review_by_index[review_index]
        decision = adjudication_by_index[review_index]
        identity = (
            decision.get("cluster_id") == review.get("cluster_id")
            and decision.get("source_sha256")
            == review.get("representative_source_sha256")
        )
        if not identity:
            raise ValueError(f"identity mismatch at review index {review_index}")
        adjudication = str(decision.get("human_adjudication") or "")
        if adjudication != "accept_core" and not adjudication.startswith("defer_"):
            raise ValueError(f"invalid adjudication at review index {review_index}")
        if decision.get("training_rows_emitted") != 0:
            raise ValueError("adjudication sidecars must not emit training rows")
        rollup.append(decision)

    accepted = sum(
        row["human_adjudication"] == "accept_core" for row in rollup
    )
    reviewed = len(rollup)
    precision = accepted / reviewed if reviewed else 0.0
    wilson_lower = _wilson_lower(accepted, reviewed)
    eligible = precision >= 0.95 and wilson_lower >= 0.80
    summary = {
        "schema": "gis_recommend.gee_mean_clip_cluster_adjudication_summary.v1",
        "pattern_scope": "mean_clip_core",
        "counts": {
            "reviewed_clusters": reviewed,
            "accept_core": accepted,
            "defer": reviewed - accepted,
        },
        "observed_precision": precision,
        "wilson_lower_95": wilson_lower,
        "gate": {
            "minimum_precision": 0.95,
            "minimum_wilson_lower_95": 0.80,
            "promotion_eligible": eligible,
            "status": "passed" if eligible else "failed_keep_proposal_only",
        },
        "training_admission": "not_granted_mean_clip_core_rule_gate",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "training_rows_emitted": 0,
        "next_gate": "repair transitive region and upstream collection provenance, replay, then recalibrate",
    }
    return rollup, summary


def calibrate_repaired_rule(
    review_rows: list[dict[str, Any]],
    adjudications: list[dict[str, Any]],
    repaired_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    decisions = {int(row["review_index"]): row for row in adjudications}
    if len(decisions) != len(adjudications):
        raise ValueError("adjudications contain duplicate indices")
    repaired_by_identity: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in repaired_rows:
        identity = (
            str(row.get("source_sha256") or ""),
            str(row.get("definition_id") or ""),
        )
        repaired_by_identity.setdefault(identity, []).append(row)

    rows: list[dict[str, Any]] = []
    for review in sorted(review_rows, key=lambda row: int(row["review_index"])):
        review_index = int(review["review_index"])
        decision = decisions.get(review_index)
        if decision is None:
            raise ValueError(f"missing adjudication at review index {review_index}")
        identity = (
            str(review.get("representative_source_sha256") or ""),
            str(review.get("representative_definition_id") or ""),
        )
        matches = repaired_by_identity.get(identity, [])
        if len(matches) != 1:
            raise ValueError(
                f"repaired census identity match count is {len(matches)} at review index {review_index}"
            )
        repaired = matches[0]
        semantic_status = str(repaired.get("semantic_status") or "")
        if semantic_status not in {"accepted_proposal", "fail_closed"}:
            raise ValueError(f"invalid repaired semantic status at review index {review_index}")
        human_accept = decision.get("human_adjudication") == "accept_core"
        rule_accept = semantic_status == "accepted_proposal"
        rows.append(
            {
                "schema": "gis_recommend.gee_mean_clip_repaired_rule_calibration.v1",
                "review_index": review_index,
                "cluster_id": review.get("cluster_id"),
                "source_sha256": identity[0],
                "definition_id": identity[1],
                "source_path": review.get("representative_source_path"),
                "sample_id": review.get("representative_sample_id"),
                "canonical_operator_sequence": list(
                    repaired.get("canonical_operator_sequence") or []
                ),
                "l3_code_sequence": list(repaired.get("l3_code_sequence") or []),
                "semantic_facts": dict(repaired.get("semantic_facts") or {}),
                "source_snippet": repaired.get("source_snippet"),
                "transitive_dependency_ids": list(
                    repaired.get("transitive_dependency_ids") or []
                ),
                "human_adjudication": decision.get("human_adjudication"),
                "human_notes": decision.get("human_notes"),
                "temporal_description_policy": decision.get(
                    "temporal_description_policy"
                ),
                "repaired_semantic_status": semantic_status,
                "semantic_reasons": list(repaired.get("semantic_reasons") or []),
                "human_rule_agreement": human_accept == rule_accept,
                "eligible_for_exporter_input": (
                    human_accept and rule_accept and human_accept == rule_accept
                ),
                "task_text_status": "not_generated",
                "training_admission": "not_granted_pending_chain_faithful_task_text",
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
                "training_rows_emitted": 0,
            }
        )

    tp = sum(
        row["human_adjudication"] == "accept_core"
        and row["repaired_semantic_status"] == "accepted_proposal"
        for row in rows
    )
    fp = sum(
        row["human_adjudication"] != "accept_core"
        and row["repaired_semantic_status"] == "accepted_proposal"
        for row in rows
    )
    tn = sum(
        row["human_adjudication"] != "accept_core"
        and row["repaired_semantic_status"] == "fail_closed"
        for row in rows
    )
    fn = len(rows) - tp - fp - tn
    predicted_accept = tp + fp
    human_accept = tp + fn
    precision = tp / predicted_accept if predicted_accept else 0.0
    recall = tp / human_accept if human_accept else 0.0
    wilson_lower = _wilson_lower(tp, predicted_accept)
    eligible = (
        fp == 0
        and fn == 0
        and precision >= 0.95
        and wilson_lower >= 0.80
    )
    summary = {
        "schema": "gis_recommend.gee_mean_clip_repaired_rule_calibration_summary.v1",
        "reviewed_clusters": len(rows),
        "confusion_matrix": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
        "predicted_accept": predicted_accept,
        "predicted_fail_closed": tn + fn,
        "exporter_input_candidates": sum(
            bool(row["eligible_for_exporter_input"]) for row in rows
        ),
        "observed_precision": precision,
        "observed_recall": recall,
        "wilson_lower_95": wilson_lower,
        "gate": {
            "minimum_precision": 0.95,
            "minimum_wilson_lower_95": 0.80,
            "requires_zero_calibration_mismatches": True,
            "promotion_eligible": eligible,
            "status": "passed_exporter_design_eligible" if eligible else "failed_keep_proposal_only",
        },
        "training_admission": "not_granted_repaired_rule_calibration",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "training_rows_emitted": 0,
    }
    return rows, summary


def _render_report(summary: dict[str, Any]) -> str:
    counts = summary["counts"]
    return (
        "# GEE Mean/Clip 35-Cluster Adjudication v1\n\n"
        f"- Reviewed: {counts['reviewed_clusters']}\n"
        f"- Accept core: {counts['accept_core']}\n"
        f"- Defer: {counts['defer']}\n"
        f"- Observed precision: {summary['observed_precision']:.4f}\n"
        f"- Wilson lower 95%: {summary['wilson_lower_95']:.4f}\n"
        f"- Rule gate: {summary['gate']['status']}\n"
        "- Training rows emitted: 0\n\n"
        "The original rule remains proposal-only. Repair transitive region and "
        "upstream ImageCollection provenance, replay the rule, and recalibrate "
        "before considering an exporter.\n"
    )


def write_outputs(
    rollup: list[dict[str, Any]],
    summary: dict[str, Any],
    review_packet: Path,
    adjudication_paths: list[Path],
    output_dir: Path,
    *,
    calibration_rows: list[dict[str, Any]],
    calibration_summary: dict[str, Any],
    repaired_census_paths: list[Path],
) -> dict[str, Path]:
    paths = {
        "rollup": output_dir / f"{OUTPUT_PREFIX}.jsonl",
        "summary": output_dir / f"{OUTPUT_PREFIX}_summary.json",
        "report": output_dir / f"{OUTPUT_PREFIX}_report.md",
        "hash_ledger": output_dir / f"{OUTPUT_PREFIX}_hash_ledger.json",
        "calibration": output_dir / f"{CALIBRATION_PREFIX}.jsonl",
        "calibration_summary": output_dir / f"{CALIBRATION_PREFIX}_summary.json",
        "calibration_report": output_dir / f"{CALIBRATION_PREFIX}_report.md",
        "exporter_input": output_dir / "gee_mean_clip_exporter_input_manifest_v1.jsonl",
        "exporter_input_summary": output_dir
        / "gee_mean_clip_exporter_input_manifest_v1_summary.json",
    }
    _atomic_write(paths["rollup"], _jsonl_text(rollup))
    _atomic_write(paths["summary"], _json_text(summary))
    _atomic_write(paths["report"], _render_report(summary))
    _atomic_write(paths["calibration"], _jsonl_text(calibration_rows))
    _atomic_write(paths["calibration_summary"], _json_text(calibration_summary))
    matrix = calibration_summary["confusion_matrix"]
    calibration_report = (
        "# GEE Mean/Clip Repaired Rule Calibration v1\n\n"
        f"- Reviewed clusters: {calibration_summary['reviewed_clusters']}\n"
        f"- TP/FP/TN/FN: {matrix['tp']}/{matrix['fp']}/{matrix['tn']}/{matrix['fn']}\n"
        f"- Observed precision: {calibration_summary['observed_precision']:.4f}\n"
        f"- Observed recall: {calibration_summary['observed_recall']:.4f}\n"
        f"- Wilson lower 95%: {calibration_summary['wilson_lower_95']:.4f}\n"
        f"- Gate: {calibration_summary['gate']['status']}\n"
        "- Training rows emitted: 0\n"
    )
    _atomic_write(paths["calibration_report"], calibration_report)
    exporter_input = [
        row for row in calibration_rows if row["eligible_for_exporter_input"]
    ]
    _atomic_write(paths["exporter_input"], _jsonl_text(exporter_input))
    _atomic_write(
        paths["exporter_input_summary"],
        _json_text(
            {
                "schema": "gis_recommend.gee_mean_clip_exporter_input_summary.v1",
                "candidate_rows": len(exporter_input),
                "unique_clusters": len(
                    {str(row["cluster_id"]) for row in exporter_input}
                ),
                "task_text_status": "not_generated",
                "training_admission": "not_granted_pending_chain_faithful_task_text",
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
                "training_rows_emitted": 0,
            }
        ),
    )
    ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "source_inputs": {
            str(review_packet): _sha256(review_packet),
            **{str(path): _sha256(path) for path in adjudication_paths},
            **{str(path): _sha256(path) for path in repaired_census_paths},
        },
        "artifacts": {
            path.name: {"path": str(path), "sha256": _sha256(path)}
            for key, path in paths.items()
            if key != "hash_ledger"
        },
    }
    _atomic_write(paths["hash_ledger"], _json_text(ledger))
    return paths


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-packet", type=Path, default=DEFAULT_REVIEW_PACKET)
    parser.add_argument(
        "--adjudication",
        type=Path,
        action="append",
        dest="adjudications",
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument(
        "--repaired-census",
        type=Path,
        action="append",
        dest="repaired_census",
    )
    args = parser.parse_args(argv)
    adjudication_paths = args.adjudications or list(DEFAULT_ADJUDICATIONS)
    review_rows = _load_jsonl(args.review_packet)
    decisions = [
        row for path in adjudication_paths for row in _load_jsonl(path)
    ]
    rollup, summary = summarize_adjudications(review_rows, decisions)
    repaired_census_paths = args.repaired_census or list(DEFAULT_REPAIRED_CENSUS)
    repaired_rows = [
        row for path in repaired_census_paths for row in _load_jsonl(path)
    ]
    calibration_rows, calibration_summary = calibrate_repaired_rule(
        review_rows, decisions, repaired_rows
    )
    return write_outputs(
        rollup,
        summary,
        args.review_packet,
        adjudication_paths,
        args.output_dir,
        calibration_rows=calibration_rows,
        calibration_summary=calibration_summary,
        repaired_census_paths=repaired_census_paths,
    )


if __name__ == "__main__":
    main()
