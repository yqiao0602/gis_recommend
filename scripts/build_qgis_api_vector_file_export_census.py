#!/usr/bin/env python3
"""Build a fail-closed QGIS API vector-file export family census."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

SCHEMA = "gis_recommend.qgis_api_vector_file_export_candidate.v1"
SUMMARY_SCHEMA = "gis_recommend.qgis_api_vector_file_export_census_summary.v1"
RULE_ID = "vector-file-export-census-v1"
FAMILY_ID = "vector_file_export"
L3_CODE = "L3_07_04_01"
MAX_ADJACENT_CALL_GAP = 20
MAX_CALL_LINE_SPAN = 100

WRITER_METHODS = {
    "writeasvectorformat",
    "writeasvectorformatv2",
    "writeasvectorformatv3",
}
ADDITIONAL_HIGH_LEVEL_METHODS = {
    "buffer",
    "centroid",
    "createspatialindex",
    "difference",
    "intersection",
    "intersects",
    "qgscoordinatetransform",
    "setcrs",
    "simplify",
    "transform",
    "unaryunion",
}


def _method_name(call_name: str) -> str:
    return call_name.rsplit(".", 1)[-1].lower()


def _method_set(row: dict[str, Any]) -> set[str]:
    return {
        _method_name(str(step.get("name") or ""))
        for step in row.get("steps") or []
    }


def _writer_steps(row: dict[str, Any]) -> list[dict[str, Any]]:
    return [
        step
        for step in row.get("steps") or []
        if _method_name(str(step.get("name") or "")) in WRITER_METHODS
    ]


def classify_vector_file_export(
    row: dict[str, Any],
    *,
    create_family_authorities: set[str],
) -> dict[str, Any] | None:
    writers = _writer_steps(row)
    if not writers:
        return None
    methods = _method_set(row)
    authority = str(row.get("source_authority_key") or "")
    additional_semantics = sorted(methods & ADDITIONAL_HIGH_LEVEL_METHODS)

    if authority in create_family_authorities:
        status = "excluded_create_feature_class_family"
    elif int(row.get("explicit_gis_sink_step_count") or 0) <= 0:
        status = "deferred_no_explicit_gis_sink"
    elif (
        int(row.get("max_adjacent_call_gap") or 0) > MAX_ADJACENT_CALL_GAP
        or int(row.get("call_line_span") or 0) > MAX_CALL_LINE_SPAN
    ):
        status = "deferred_wide_task_scope"
    elif additional_semantics:
        status = "deferred_additional_high_level_semantics"
    else:
        status = "strict_review_eligible"

    return {
        **row,
        "schema": SCHEMA,
        "family_rule_id": RULE_ID,
        "selected_family_id": FAMILY_ID,
        "proposed_l3_code": L3_CODE,
        "proposed_l3_name": "Save vector features to file",
        "semantic_contract": (
            "write a prepared vector layer to a vector dataset without adding "
            "another spatial transformation"
        ),
        "step_methods": sorted(methods),
        "writer_step_count": len(writers),
        "writer_methods": sorted(
            {_method_name(str(step.get("name") or "")) for step in writers}
        ),
        "writer_source_lines": sorted(
            {
                int(step.get("line_start") or 0)
                for step in writers
                if int(step.get("line_start") or 0) > 0
            }
        ),
        "excluded_high_level_methods": additional_semantics,
        "family_boundary_status": status,
        "mapping_status": "existing_stable125_l3_proposal",
        "writer_alias_provenance": "pending_source_ast_replay",
        "writer_option_provenance": "pending_source_ast_replay",
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
    return hashlib.sha256(f"{seed}:{authority}".encode()).hexdigest(), authority


def select_source_disjoint_review(
    rows: list[dict[str, Any]],
    *,
    per_split: int,
    seed: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    eligible = [
        row
        for row in rows
        if row.get("family_boundary_status") == "strict_review_eligible"
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
    if len(selected) != per_split * 2:
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
    excluded_authorities: set[str],
    create_family_authorities: set[str],
    per_split: int,
    seed: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict]:
    population = [
        classified
        for row in rows
        if str(row.get("source_authority_key") or "") not in excluded_authorities
        if (
            classified := classify_vector_file_export(
                row,
                create_family_authorities=create_family_authorities,
            )
        )
        is not None
    ]
    calibration, holdout = select_source_disjoint_review(
        population,
        per_split=per_split,
        seed=seed,
    )
    status_counts = Counter(row["family_boundary_status"] for row in population)
    summary = {
        "schema": SUMMARY_SCHEMA,
        "family_rule_id": RULE_ID,
        "input_candidate_authorities": len(rows),
        "excluded_previously_reviewed_authorities": len(excluded_authorities),
        "create_family_authorities": len(create_family_authorities),
        "writer_matched_authorities": len(population),
        "strict_review_eligible_authorities": status_counts.get(
            "strict_review_eligible", 0
        ),
        "family_boundary_status_counts": dict(sorted(status_counts.items())),
        "writer_method_counts": dict(
            sorted(
                Counter(
                    method for row in population for method in row["writer_methods"]
                ).items()
            )
        ),
        "additional_semantics_counts": dict(
            sorted(
                Counter(
                    method
                    for row in population
                    for method in row["excluded_high_level_methods"]
                ).items()
            )
        ),
        "proposed_l3_code": L3_CODE,
        "minimum_support": 30,
        "support_gate": (
            "eligible_for_source_disjoint_calibration"
            if status_counts.get("strict_review_eligible", 0) >= 30
            else "deferred_support_below_threshold"
        ),
        "calibration_rows": len(calibration),
        "holdout_rows": len(holdout),
        "calibration_holdout_source_sha_overlap": len(
            {row["source_sha256"] for row in calibration}
            & {row["source_sha256"] for row in holdout}
        ),
        "calibration_holdout_normalized_body_overlap": len(
            {row["normalized_source_body_sha256"] for row in calibration}
            & {row["normalized_source_body_sha256"] for row in holdout}
        ),
        "review_seed": seed,
        "training_admission": "not_granted_census_only",
        "training_rows_emitted": 0,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }
    return population, calibration, holdout, summary


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
        "proposed_l3_code",
        "family_boundary_status",
        "writer_methods",
        "writer_source_lines",
        "excluded_high_level_methods",
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
                    "writer_methods": json.dumps(row["writer_methods"]),
                    "writer_source_lines": json.dumps(row["writer_source_lines"]),
                    "excluded_high_level_methods": json.dumps(
                        row["excluded_high_level_methods"]
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
            "# QGIS API Vector File Export Census v1",
            "",
            f"- Input authorities: {summary['input_candidate_authorities']}",
            f"- Writer-matched authorities: {summary['writer_matched_authorities']}",
            f"- Strict review eligible: {summary['strict_review_eligible_authorities']}",
            f"- Calibration / holdout: {summary['calibration_rows']} / {summary['holdout_rows']}",
            "- Source SHA and normalized-body overlap: 0 / 0",
            "- Proposed existing L3: `L3_07_04_01 Save vector features to file`",
            "- Create Feature Class overlap and higher-level spatial/CRS semantics are excluded.",
            "- Training admission: not granted",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--exclude-jsonl", type=Path, action="append", default=[])
    parser.add_argument("--create-replay", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-input-authorities", type=int, default=12949)
    parser.add_argument("--expected-strict-authorities", type=int, default=211)
    parser.add_argument("--review-per-split", type=int, default=30)
    parser.add_argument("--seed", type=int, default=20260804)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    rows = _read_jsonl(args.candidates)
    if len(rows) != args.expected_input_authorities:
        raise ValueError(
            f"expected {args.expected_input_authorities} authorities, got {len(rows)}"
        )
    excluded_authorities = {
        str(row.get("source_authority_key") or "")
        for path in args.exclude_jsonl
        for row in _read_jsonl(path)
        if row.get("source_authority_key")
    }
    create_family_authorities = {
        str(row.get("source_authority_key") or "")
        for row in _read_jsonl(args.create_replay)
        if row.get("source_authority_key")
    }
    population, calibration, holdout, summary = build_census(
        rows,
        excluded_authorities=excluded_authorities,
        create_family_authorities=create_family_authorities,
        per_split=args.review_per_split,
        seed=args.seed,
    )
    if summary["strict_review_eligible_authorities"] != args.expected_strict_authorities:
        raise ValueError(
            f"expected {args.expected_strict_authorities} strict authorities, got "
            f"{summary['strict_review_eligible_authorities']}"
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
            str(args.candidates): _sha256(args.candidates),
            str(args.create_replay): _sha256(args.create_replay),
            **{str(path): _sha256(path) for path in args.exclude_jsonl},
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
