#!/usr/bin/env python3
"""Rank source-backed QGIS API task families and freeze a review packet."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable

SCHEMA = "gis_recommend.qgis_api_semantic_family_census.v1"
RULE_ID = "qgis-api-semantic-family-census-v1"
MAX_ADJACENT_CALL_GAP = 20
MAX_CALL_LINE_SPAN = 100


def _has_any(*names: str) -> Callable[[set[str]], bool]:
    expected = set(names)
    return lambda methods: bool(expected.intersection(methods))


def _has_all(*names: str) -> Callable[[set[str]], bool]:
    expected = set(names)
    return lambda methods: expected.issubset(methods)


FAMILY_RULES: tuple[dict[str, Any], ...] = (
    {
        "family_id": "field_schema_addition",
        "required": (
            _has_any("addattribute", "addattributes"),
            _has_all("updatefields"),
        ),
        "proposed_l3_code": "L3_01_02_01",
        "semantic_contract": "add one or more fields and commit the updated schema",
    },
    {
        "family_id": "field_value_calculation",
        "required": (
            _has_any("changeattributevalue", "changeattributevalues"),
            _has_any("qgsfield", "addattribute", "addattributes"),
        ),
        "proposed_l3_code": "L3_01_02_06",
        "semantic_contract": "populate a field through explicit feature attribute updates",
    },
    {
        "family_id": "crs_reprojection",
        "required": (
            _has_all("qgscoordinatetransform", "transform"),
        ),
        "proposed_l3_code": "L3_01_10_01",
        "semantic_contract": "transform coordinates through an explicit coordinate transform",
    },
    {
        "family_id": "spatial_index_intersection_query",
        "required": (
            _has_all("qgsspatialindex", "intersects"),
        ),
        "proposed_l3_code": None,
        "semantic_contract": "query spatial-index candidates by bounding-box intersection",
    },
    {
        "family_id": "spatial_index_nearest_query",
        "required": (
            _has_all("qgsspatialindex", "nearestneighbor"),
        ),
        "proposed_l3_code": None,
        "semantic_contract": "query nearest candidates through a spatial index",
    },
)


def _method_name(call_name: str) -> str:
    return call_name.rsplit(".", 1)[-1].lower()


def _boundary_status(row: dict[str, Any]) -> str:
    if int(row.get("explicit_gis_sink_step_count") or 0) <= 0:
        return "deferred_no_explicit_gis_sink"
    if (
        int(row.get("max_adjacent_call_gap") or 0) > MAX_ADJACENT_CALL_GAP
        or int(row.get("call_line_span") or 0) > MAX_CALL_LINE_SPAN
    ):
        return "deferred_wide_task_scope"
    return "strict_review_eligible"


def classify_authority(row: dict[str, Any]) -> dict[str, Any]:
    steps = list(row.get("steps") or [])
    methods = {_method_name(str(step.get("name") or "")) for step in steps}
    matches = []
    for rule in FAMILY_RULES:
        if not all(predicate(methods) for predicate in rule["required"]):
            continue
        proposed_l3 = rule["proposed_l3_code"]
        matches.append(
            {
                "family_id": rule["family_id"],
                "semantic_contract": rule["semantic_contract"],
                "boundary_status": _boundary_status(row),
                "mapping_status": (
                    "existing_l3_proposal"
                    if proposed_l3 is not None
                    else "taxonomy_review_required"
                ),
                "proposed_l3_code": proposed_l3,
            }
        )
    return {
        **row,
        "schema": SCHEMA,
        "family_rule_id": RULE_ID,
        "step_methods": sorted(methods),
        "semantic_family_matches": matches,
        "description_fidelity": "not_started",
        "deduplication": "not_started",
        "training_admission": "not_granted_family_census_only",
        "training_row_emitted": False,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }


def _match(row: dict[str, Any], family_id: str) -> dict[str, Any] | None:
    return next(
        (
            match
            for match in row.get("semantic_family_matches") or []
            if match.get("family_id") == family_id
        ),
        None,
    )


def _review_row(row: dict[str, Any], family_id: str, split: str) -> dict[str, Any]:
    match = _match(row, family_id)
    if match is None:
        raise ValueError(f"row does not match {family_id}")
    return {
        **row,
        "selected_family_id": family_id,
        "review_split": split,
        "proposed_l3_code": match["proposed_l3_code"],
        "mapping_status": match["mapping_status"],
        "boundary_status": match["boundary_status"],
        "human_boundary_decision": "",
        "human_mapping_decision": "",
        "human_description_fidelity": "",
        "human_notes": "",
        "training_admission": "not_granted_pending_source_review",
    }


def _rank(seed: int, family_id: str, key: str) -> str:
    return hashlib.sha256(f"{seed}:{family_id}:{key}".encode()).hexdigest()


def select_source_disjoint_review(
    rows: list[dict[str, Any]],
    *,
    family_id: str,
    per_split: int,
    seed: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    eligible = [
        row
        for row in rows
        if (match := _match(row, family_id)) is not None
        and match["boundary_status"] == "strict_review_eligible"
    ]
    by_source: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in eligible:
        source_sha = str(row.get("source_sha256") or "")
        if not source_sha:
            raise ValueError("eligible row is missing source_sha256")
        by_source[source_sha].append(row)
    groups = sorted(
        by_source.items(),
        key=lambda item: _rank(seed, family_id, item[0]),
    )
    calibration: list[dict[str, Any]] = []
    holdout: list[dict[str, Any]] = []
    for index, (_, source_rows) in enumerate(groups):
        target = calibration if index % 2 == 0 else holdout
        if len(target) >= per_split:
            target = holdout if target is calibration else calibration
        if len(target) >= per_split:
            continue
        representative = min(
            source_rows,
            key=lambda row: str(row.get("source_authority_key") or ""),
        )
        split = "calibration" if target is calibration else "holdout"
        target.append(_review_row(representative, family_id, split))
    if len(calibration) != per_split or len(holdout) != per_split:
        raise ValueError(
            f"insufficient source-disjoint rows for {family_id}: "
            f"calibration={len(calibration)}, holdout={len(holdout)}, "
            f"required={per_split}"
        )
    calibration_sources = {str(row["source_sha256"]) for row in calibration}
    holdout_sources = {str(row["source_sha256"]) for row in holdout}
    calibration_bodies = {
        str(row["normalized_source_body_sha256"]) for row in calibration
    }
    holdout_bodies = {str(row["normalized_source_body_sha256"]) for row in holdout}
    if calibration_sources.intersection(holdout_sources):
        raise ValueError("source SHA leakage between calibration and holdout")
    if calibration_bodies.intersection(holdout_bodies):
        raise ValueError("normalized-body leakage between calibration and holdout")
    return calibration, holdout


def build_census(
    rows: list[dict[str, Any]],
    *,
    excluded_authorities: set[str],
    minimum_support: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    classified = [
        classify_authority(row)
        for row in rows
        if str(row.get("source_authority_key") or "") not in excluded_authorities
    ]
    family_rows: list[dict[str, Any]] = []
    priority_population: list[dict[str, Any]] = []
    for rule in FAMILY_RULES:
        family_id = str(rule["family_id"])
        matches = [row for row in classified if _match(row, family_id) is not None]
        strict = [
            row
            for row in matches
            if _match(row, family_id)["boundary_status"]
            == "strict_review_eligible"
        ]
        status_counts = Counter(
            str(_match(row, family_id)["boundary_status"]) for row in matches
        )
        family_rows.append(
            {
                "schema": "gis_recommend.qgis_api_semantic_family_summary.v1",
                "family_rule_id": RULE_ID,
                "family_id": family_id,
                "semantic_contract": rule["semantic_contract"],
                "proposed_l3_code": rule["proposed_l3_code"],
                "mapping_status": (
                    "existing_l3_proposal"
                    if rule["proposed_l3_code"] is not None
                    else "taxonomy_review_required"
                ),
                "matched_authorities": len(matches),
                "strict_review_eligible_authorities": len(strict),
                "boundary_status_counts": dict(sorted(status_counts.items())),
                "support_gate": (
                    "eligible_for_source_disjoint_calibration"
                    if len(strict) >= minimum_support
                    else "deferred_support_below_threshold"
                ),
                "minimum_support": minimum_support,
                "training_admission": "not_granted_family_census_only",
                "training_rows_emitted": 0,
            }
        )
        if len(strict) >= minimum_support and rule["proposed_l3_code"] is not None:
            priority_population.extend(
                {
                    **row,
                    "selected_family_id": family_id,
                    "proposed_l3_code": rule["proposed_l3_code"],
                    "training_admission": "not_granted_pending_source_review",
                }
                for row in strict
            )
    family_rows.sort(
        key=lambda row: (
            -int(row["strict_review_eligible_authorities"]),
            str(row["family_id"]),
        )
    )
    summary = {
        "schema": "gis_recommend.qgis_api_semantic_family_census_summary.v1",
        "family_rule_id": RULE_ID,
        "input_candidate_authorities": len(rows),
        "excluded_previously_reviewed_authorities": len(excluded_authorities),
        "classified_authorities": len(classified),
        "family_count": len(family_rows),
        "priority_family_count": sum(
            row["support_gate"] == "eligible_for_source_disjoint_calibration"
            and row["mapping_status"] == "existing_l3_proposal"
            for row in family_rows
        ),
        "priority_population_rows": len(priority_population),
        "minimum_support": minimum_support,
        "training_admission": "not_granted_family_census_only",
        "training_rows_emitted": 0,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }
    return family_rows, priority_population, summary


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
        "selected_family_id",
        "record_id",
        "source_root_id",
        "source_path",
        "source_sha256",
        "normalized_source_body_sha256",
        "source_authority_key",
        "proposed_l3_code",
        "boundary_status",
        "mapping_status",
        "step_methods",
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
            writer.writerow({**row, "step_methods": json.dumps(row["step_methods"])})
        temporary = Path(handle.name)
    temporary.replace(path)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--exclude-jsonl", type=Path, action="append", default=[])
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-input-authorities", type=int, default=12949)
    parser.add_argument("--minimum-support", type=int, default=30)
    parser.add_argument("--review-family", default="field_schema_addition")
    parser.add_argument("--review-per-split", type=int, default=30)
    parser.add_argument("--seed", type=int, default=20260804)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    rows = _read_jsonl(args.candidates)
    if len(rows) != args.expected_input_authorities:
        raise ValueError(
            f"expected {args.expected_input_authorities} candidate authorities, got {len(rows)}"
        )
    excluded = {
        str(row.get("source_authority_key") or "")
        for path in args.exclude_jsonl
        for row in _read_jsonl(path)
        if row.get("source_authority_key")
    }
    family_rows, priority, summary = build_census(
        rows,
        excluded_authorities=excluded,
        minimum_support=args.minimum_support,
    )
    classified = [
        classify_authority(row)
        for row in rows
        if str(row.get("source_authority_key") or "") not in excluded
    ]
    calibration, holdout = select_source_disjoint_review(
        classified,
        family_id=args.review_family,
        per_split=args.review_per_split,
        seed=args.seed,
    )
    summary.update(
        {
            "review_family": args.review_family,
            "calibration_rows": len(calibration),
            "holdout_rows": len(holdout),
            "calibration_holdout_source_sha_overlap": 0,
            "calibration_holdout_normalized_body_overlap": 0,
            "review_seed": args.seed,
        }
    )
    artifacts = {
        "family_census_v1.jsonl": family_rows,
        "priority_family_population_v1.jsonl": priority,
        "calibration_review_v1.jsonl": calibration,
        "holdout_review_v1.jsonl": holdout,
    }
    paths: list[Path] = []
    for name, values in artifacts.items():
        path = args.output_dir / name
        _write_jsonl(path, values)
        paths.append(path)
    for name, values in (
        ("calibration_review_v1.csv", calibration),
        ("holdout_review_v1.csv", holdout),
    ):
        path = args.output_dir / name
        _write_review_csv(path, values)
        paths.append(path)
    summary_path = args.output_dir / "summary_v1.json"
    _write_json(summary_path, summary)
    paths.append(summary_path)
    ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "inputs": {
            args.candidates.name: {
                "path": str(args.candidates),
                "sha256": _sha256(args.candidates),
            },
            **{
                path.name: {"path": str(path), "sha256": _sha256(path)}
                for path in args.exclude_jsonl
            },
        },
        "artifacts": {
            path.name: {"bytes": path.stat().st_size, "sha256": _sha256(path)}
            for path in paths
        },
    }
    _write_json(args.output_dir / "hash_ledger_v1.json", ledger)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
