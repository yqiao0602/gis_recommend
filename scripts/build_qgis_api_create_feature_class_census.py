#!/usr/bin/env python3
"""Build a fail-closed Create Feature Class API macro-family review packet."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

SCHEMA = "gis_recommend.qgis_api_create_feature_class_candidate.v1"
SUMMARY_SCHEMA = "gis_recommend.qgis_api_create_feature_class_census_summary.v1"
RULE_ID = "create-feature-class-macro-census-v1"
FAMILY_ID = "create_feature_class"
L3_CODE = "L3_01_01_01"

SCHEMA_ADD_METHODS = {"addattribute", "addattributes"}
SCHEMA_COMMIT_METHODS = {"updatefields"}
VECTOR_SINK_METHODS = {"addfeature", "addfeatures"}
SPATIAL_HIGH_LEVEL_METHODS = {
    "buffer",
    "centroid",
    "difference",
    "intersection",
    "intersects",
    "simplify",
    "unaryunion",
}


def _method_set(row: dict[str, Any]) -> set[str]:
    return {str(method).lower() for method in row.get("scope_call_methods") or []}


def _has_vector_writer(methods: set[str]) -> bool:
    return any(method.startswith("writeasvectorformat") for method in methods)


def _crs_transform_present(methods: set[str]) -> bool:
    return "transform" in methods and "qgscoordinatetransform" in methods


def classify_create_feature_class(row: dict[str, Any]) -> dict[str, Any]:
    methods = _method_set(row)
    spatial_exclusions = sorted(methods & SPATIAL_HIGH_LEVEL_METHODS)
    crs_exclusions = ["transform"] if _crs_transform_present(methods) else []
    exclusions = sorted({*spatial_exclusions, *crs_exclusions})
    evidence = {
        "verified_same_scope": row.get("source_replay_status")
        == "verified_same_scope",
        "verified_source_sha256": row.get("source_verification")
        == "verified_sha256",
        "vector_layer": "qgsvectorlayer" in methods,
        "schema_add": bool(methods & SCHEMA_ADD_METHODS),
        "schema_commit": bool(methods & SCHEMA_COMMIT_METHODS),
        "vector_sink": bool(methods & VECTOR_SINK_METHODS),
        "vector_writer": _has_vector_writer(methods),
    }

    if not evidence["verified_same_scope"] or not evidence["verified_source_sha256"]:
        status = "deferred_unverified_source_scope"
    elif not evidence["vector_layer"]:
        status = "deferred_missing_vector_layer_constructor"
    elif not evidence["schema_add"] or not evidence["schema_commit"]:
        status = "deferred_missing_schema_contract"
    elif not evidence["vector_writer"]:
        status = "deferred_missing_vector_writer"
    elif exclusions:
        status = "deferred_additional_high_level_semantics"
    else:
        status = "strict_review_eligible"

    broad_contract = all(
        evidence[name]
        for name in (
            "verified_same_scope",
            "verified_source_sha256",
            "vector_layer",
            "schema_add",
            "schema_commit",
            "vector_writer",
        )
    )
    spatial_semantics_clean = broad_contract and not spatial_exclusions
    return {
        **row,
        "schema": SCHEMA,
        "macro_rule_id": RULE_ID,
        "selected_family_id": FAMILY_ID,
        "prior_proposed_l3_code": row.get("proposed_l3_code"),
        "proposed_l3_code": L3_CODE,
        "proposed_l3_name": "Create Feature Class",
        "semantic_contract": (
            "create a new vector feature class with an explicit schema and write it "
            "to a vector dataset"
        ),
        "required_method_evidence": evidence,
        "broad_macro_contract": broad_contract,
        "spatial_semantics_clean": spatial_semantics_clean,
        "excluded_spatial_methods": spatial_exclusions,
        "excluded_crs_methods": crs_exclusions,
        "excluded_high_level_methods": exclusions,
        "macro_boundary_status": status,
        "full_scope_call_sequence": list(row.get("scope_call_methods") or []),
        "constructor_alias_provenance": "pending_source_ast_replay",
        "schema_alias_provenance": "pending_source_ast_replay",
        "writer_alias_provenance": "pending_source_ast_replay",
        "mapping_status": "pending_source_disjoint_boundary_and_mapping_review",
        "description_fidelity": "not_started",
        "deduplication": "not_started",
        "human_boundary_decision": "",
        "human_mapping_decision": "",
        "human_description_fidelity": "",
        "human_notes": "",
        "training_admission": "not_granted_census_only",
        "training_row_emitted": False,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }


def _rank(row: dict[str, Any], seed: int) -> tuple[str, str]:
    authority = str(row.get("source_authority_key") or "")
    digest = hashlib.sha256(f"{seed}:{authority}".encode()).hexdigest()
    return digest, authority


def select_source_disjoint_review(
    rows: list[dict[str, Any]],
    *,
    per_split: int,
    seed: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    eligible = [
        row for row in rows if row.get("macro_boundary_status") == "strict_review_eligible"
    ]
    eligible.sort(key=lambda row: _rank(row, seed))
    selected: list[dict[str, Any]] = []
    used_sources: set[str] = set()
    used_bodies: set[str] = set()
    for row in eligible:
        source_sha = str(row.get("source_sha256") or "")
        body_sha = str(row.get("normalized_source_body_sha256") or "")
        if not source_sha or not body_sha:
            continue
        if source_sha in used_sources or body_sha in used_bodies:
            continue
        selected.append(row)
        used_sources.add(source_sha)
        used_bodies.add(body_sha)
        if len(selected) == per_split * 2:
            break
    if len(selected) < per_split * 2:
        raise ValueError(
            f"need {per_split * 2} source-disjoint rows, found {len(selected)}"
        )
    calibration = [
        {**row, "review_split": "calibration"} for row in selected[:per_split]
    ]
    holdout = [
        {**row, "review_split": "holdout"} for row in selected[per_split:]
    ]
    return calibration, holdout


def build_census(
    rows: list[dict[str, Any]],
    *,
    per_split: int,
    seed: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict]:
    classified = [classify_create_feature_class(row) for row in rows]
    calibration, holdout = select_source_disjoint_review(
        classified,
        per_split=per_split,
        seed=seed,
    )
    status_counts = Counter(row["macro_boundary_status"] for row in classified)
    calibration_sources = {row["source_sha256"] for row in calibration}
    holdout_sources = {row["source_sha256"] for row in holdout}
    calibration_bodies = {
        row["normalized_source_body_sha256"] for row in calibration
    }
    holdout_bodies = {row["normalized_source_body_sha256"] for row in holdout}
    summary = {
        "schema": SUMMARY_SCHEMA,
        "macro_rule_id": RULE_ID,
        "input_rows": len(rows),
        "source_verified_same_scope_rows": sum(
            row.get("source_replay_status") == "verified_same_scope" for row in rows
        ),
        "broad_macro_contract_rows": sum(
            bool(row["broad_macro_contract"]) for row in classified
        ),
        "spatial_semantics_clean_rows": sum(
            bool(row["spatial_semantics_clean"]) for row in classified
        ),
        "strict_review_eligible_rows": status_counts.get("strict_review_eligible", 0),
        "macro_boundary_status_counts": dict(sorted(status_counts.items())),
        "additional_semantics_counts": dict(
            sorted(
                Counter(
                    method
                    for row in classified
                    for method in row["excluded_high_level_methods"]
                ).items()
            )
        ),
        "proposed_l3_code": L3_CODE,
        "calibration_rows": len(calibration),
        "holdout_rows": len(holdout),
        "calibration_holdout_source_sha_overlap": len(
            calibration_sources & holdout_sources
        ),
        "calibration_holdout_normalized_body_overlap": len(
            calibration_bodies & holdout_bodies
        ),
        "review_seed": seed,
        "training_admission": "not_granted_census_only",
        "training_rows_emitted": 0,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }
    return classified, calibration, holdout, summary


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


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
        path,
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    _atomic_write(
        path,
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows
        ),
    )


def _write_review_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "review_split",
        "record_id",
        "source_root_id",
        "source_path",
        "source_sha256",
        "normalized_source_body_sha256",
        "source_authority_key",
        "lexical_scope",
        "proposed_l3_code",
        "macro_boundary_status",
        "excluded_high_level_methods",
        "full_scope_call_sequence",
        "source_snippet",
        "human_boundary_decision",
        "human_mapping_decision",
        "human_description_fidelity",
        "human_notes",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    **row,
                    "excluded_high_level_methods": json.dumps(
                        row["excluded_high_level_methods"]
                    ),
                    "full_scope_call_sequence": json.dumps(
                        row["full_scope_call_sequence"]
                    ),
                }
            )
        temporary = Path(handle.name)
    temporary.replace(path)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _report(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# QGIS API Create Feature Class Census v1",
            "",
            f"- Input replay rows: {summary['input_rows']}",
            f"- Broad macro contract: {summary['broad_macro_contract_rows']}",
            (
                "- Spatial-semantics-clean rows before CRS transform exclusion: "
                f"{summary['spatial_semantics_clean_rows']}"
            ),
            f"- Strict review eligible: {summary['strict_review_eligible_rows']}",
            f"- Calibration / holdout: {summary['calibration_rows']} / {summary['holdout_rows']}",
            "- Source SHA overlap: 0",
            "- Normalized body overlap: 0",
            "- Proposed L3: `L3_01_01_01 Create Feature Class`",
            "- Training admission: not granted",
            "",
            (
                "The former 72-row count is an intermediate spatial-semantics-clean "
                "count. Rows containing an explicit `QgsCoordinateTransform` plus "
                "`transform()` remain deferred so that reprojection tasks are not "
                "truncated into Create Feature Class samples."
            ),
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-replay", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-input-rows", type=int, default=102)
    parser.add_argument("--expected-strict-rows", type=int, default=67)
    parser.add_argument("--review-per-split", type=int, default=20)
    parser.add_argument("--seed", type=int, default=20260804)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    rows = _read_jsonl(args.source_replay)
    if len(rows) != args.expected_input_rows:
        raise ValueError(
            f"expected {args.expected_input_rows} source replay rows, got {len(rows)}"
        )
    population, calibration, holdout, summary = build_census(
        rows,
        per_split=args.review_per_split,
        seed=args.seed,
    )
    if summary["strict_review_eligible_rows"] != args.expected_strict_rows:
        raise ValueError(
            "expected "
            f"{args.expected_strict_rows} strict rows, got "
            f"{summary['strict_review_eligible_rows']}"
        )

    artifacts: list[Path] = []
    for name, values in (
        ("population_v1.jsonl", population),
        ("calibration_review_v1.jsonl", calibration),
        ("holdout_review_v1.jsonl", holdout),
    ):
        path = args.output_dir / name
        _write_jsonl(path, values)
        artifacts.append(path)
    for name, values in (
        ("calibration_review_v1.csv", calibration),
        ("holdout_review_v1.csv", holdout),
    ):
        path = args.output_dir / name
        _write_review_csv(path, values)
        artifacts.append(path)
    summary_path = args.output_dir / "summary_v1.json"
    _write_json(summary_path, summary)
    artifacts.append(summary_path)
    report_path = args.output_dir / "report_v1.md"
    _atomic_write(report_path, _report(summary))
    artifacts.append(report_path)
    ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "inputs": {
            args.source_replay.name: {
                "path": str(args.source_replay),
                "sha256": _sha256(args.source_replay),
            }
        },
        "artifacts": {
            path.name: {"bytes": path.stat().st_size, "sha256": _sha256(path)}
            for path in artifacts
        },
    }
    _write_json(args.output_dir / "hash_ledger_v1.json", ledger)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
