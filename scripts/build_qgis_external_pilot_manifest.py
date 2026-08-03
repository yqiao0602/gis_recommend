#!/usr/bin/env python3
"""Build the frozen 100+100 QGIS external-analysis pilot manifests."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT / "src"))

from gis_recommend.data.qgis_external_pilot_manifest import (  # noqa: E402
    build_regression_baseline,
    build_target_manifest,
    write_pilot_artifacts,
)


TARGET_PROCESSING_PATHS = (
    "docs/reports/qgis_processing_boundary_families_v2_condition_evidence/blocker_source_replay_v1.jsonl",
    "docs/reports/mapped_recovery_split_family_census_v2/family_census_v1.jsonl",
)
TARGET_API_PATH = (
    "docs/reports/qgis_api_mutation_upstream_census_v6/mutation_upstream_census_v1.jsonl"
)
TARGET_API_FAMILY_PATH = (
    "docs/reports/qgis_api_remaining_mutation_export_census_v4/upstream_family_census_v1.jsonl"
)

BASELINE_ACCEPTED_PATH = (
    "docs/reports/qgis_processing_delivery_283_v1_source_verified/qgis_unified_train_v1.jsonl"
)
BASELINE_SAME_IF_PATHS = (
    "docs/reports/qgis_processing_same_if_calibration_v1/calibration_v1.jsonl",
    "docs/reports/qgis_processing_same_if_calibration_v1/holdout_v1.jsonl",
)
BASELINE_DOWNSTREAM_PATH = (
    "docs/reports/qgis_processing_downstream_transform_census_v1/downstream_units_v1.jsonl"
)
BASELINE_API_V2_PROPOSAL_PATHS = (
    "docs/reports/qgis_api_boundary_v2_calibration/proposals_1_50_v1.jsonl",
    "docs/reports/qgis_api_boundary_v2_calibration/proposal_51_100_v1.jsonl",
)
BASELINE_API_V2_REVIEW_PATH = (
    "docs/reports/qgis_api_boundary_v2_calibration/calibration_review_100_v1.jsonl"
)
BASELINE_API_V2_EVALUATION_PATH = (
    "docs/reports/qgis_api_boundary_v2_calibration/proposal_evaluation_v1.json"
)
BASELINE_API_V3_PROPOSAL_PATHS = (
    "docs/reports/qgis_api_boundary_v3_calibration/carried_proposals_v1.jsonl",
    "docs/reports/qgis_api_boundary_v3_calibration/pending_proposals_v1.jsonl",
)
BASELINE_API_V3_REVIEW_PATH = (
    "docs/reports/qgis_api_boundary_v3_calibration/calibration_review_100_v1.jsonl"
)
BASELINE_API_V3_EVALUATION_PATH = (
    "docs/reports/qgis_api_boundary_v3_calibration/proposal_evaluation_v1.json"
)
BASELINE_API_POSTFILTER_PATH = (
    "docs/reports/qgis_api_boundary_v6_post_filter_v1/excluded_candidate_units_v1.jsonl"
)


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSONL at {path}:{line_number}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"JSONL row is not an object at {path}:{line_number}")
            rows.append(row)
    return rows


def _read_many(root: Path, paths: Iterable[str]) -> list[dict[str, Any]]:
    return [row for relative in paths for row in _read_jsonl(root / relative)]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _review_index(rows: Iterable[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    index: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        candidate_ids = [str(row.get("candidate_id") or "")]
        candidate_ids.extend(str(value) for value in row.get("authority_candidate_ids", []))
        for candidate_id in dict.fromkeys(candidate_ids):
            if not candidate_id:
                continue
            if candidate_id in index:
                raise ValueError(f"duplicate review evidence for candidate {candidate_id}")
            index[candidate_id] = row
    return index


def _merge_api_verdict_evidence(
    proposals: Iterable[Mapping[str, Any]], reviews: Iterable[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    index = _review_index(reviews)
    merged: list[dict[str, Any]] = []
    evidence_fields = (
        "unit_id",
        "normalized_source_body_sha256",
        "steps",
        "dependency_edges",
        "source_span",
        "terminal_evidence_count",
        "boundary_status",
        "boundary_rule_id",
    )
    for proposal in proposals:
        candidate_id = str(proposal.get("candidate_id") or "")
        evidence = index.get(candidate_id)
        if evidence is None:
            raise ValueError(f"missing item-level review evidence for {candidate_id}")
        for key in ("source_sha256", "source_authority_key"):
            if str(proposal.get(key) or "") != str(evidence.get(key) or ""):
                raise ValueError(f"proposal/review {key} mismatch for {candidate_id}")
        row = dict(proposal)
        for key in evidence_fields:
            if key in evidence:
                row[key] = evidence[key]
        merged.append(row)
    return merged


def _validate_api_evaluation(
    root: Path,
    rows: Iterable[Mapping[str, Any]],
    evaluation_path: str,
) -> None:
    evaluation = json.loads((root / evaluation_path).read_text(encoding="utf-8"))
    expected = evaluation["overall"]["decision_counts"]
    actual = Counter(str(row.get("proposal_decision") or "") for row in rows)
    if dict(sorted(actual.items())) != dict(sorted(expected.items())):
        raise ValueError(
            f"item verdicts do not reproduce aggregate evaluation {evaluation_path}: "
            f"{dict(actual)} != {expected}"
        )


def _enrich_api_family_support(
    rows: Iterable[Mapping[str, Any]], family_rows: Iterable[Mapping[str, Any]]
) -> list[dict[str, Any]]:
    by_authority: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for family in family_rows:
        for authority in family.get("source_authority_keys", []):
            by_authority[str(authority)].append(family)

    enriched: list[dict[str, Any]] = []
    for original in rows:
        row = dict(original)
        families = by_authority.get(str(row.get("source_authority_key") or ""), [])
        if families:
            row["family_support_max"] = max(
                int(family.get("source_authority_count") or 0) for family in families
            )
            row["family_signatures"] = sorted(
                {
                    json.dumps(
                        family.get("normalized_signature", []),
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    )
                    for family in families
                }
            )
        enriched.append(row)
    return enriched


def _baseline_inputs(root: Path) -> tuple[list[dict[str, Any]], list[str]]:
    accepted = _read_jsonl(root / BASELINE_ACCEPTED_PATH)
    same_if = _read_many(root, BASELINE_SAME_IF_PATHS)
    downstream_all = _read_jsonl(root / BASELINE_DOWNSTREAM_PATH)
    downstream = [
        row
        for row in downstream_all
        if str(row.get("downstream_role_status") or "")
        in {"semantic_continuation", "unknown_or_custom"}
        or bool(row.get("downstream_low_level_roles"))
    ]

    v2_proposals = _read_many(root, BASELINE_API_V2_PROPOSAL_PATHS)
    v2 = _merge_api_verdict_evidence(
        v2_proposals, _read_jsonl(root / BASELINE_API_V2_REVIEW_PATH)
    )
    _validate_api_evaluation(root, v2, BASELINE_API_V2_EVALUATION_PATH)
    v3_proposals = _read_many(root, BASELINE_API_V3_PROPOSAL_PATHS)
    v3 = _merge_api_verdict_evidence(
        v3_proposals, _read_jsonl(root / BASELINE_API_V3_REVIEW_PATH)
    )
    _validate_api_evaluation(root, v3, BASELINE_API_V3_EVALUATION_PATH)
    postfilter = _read_jsonl(root / BASELINE_API_POSTFILTER_PATH)

    baseline = build_regression_baseline(
        processing_accepted=accepted,
        same_if_deferred=same_if,
        downstream_negatives=downstream,
        api_reviewed=v2 + v3,
        api_postfilter_negatives=postfilter,
    )
    paths = [
        BASELINE_ACCEPTED_PATH,
        *BASELINE_SAME_IF_PATHS,
        BASELINE_DOWNSTREAM_PATH,
        *BASELINE_API_V2_PROPOSAL_PATHS,
        BASELINE_API_V2_REVIEW_PATH,
        BASELINE_API_V2_EVALUATION_PATH,
        *BASELINE_API_V3_PROPOSAL_PATHS,
        BASELINE_API_V3_REVIEW_PATH,
        BASELINE_API_V3_EVALUATION_PATH,
        BASELINE_API_POSTFILTER_PATH,
    ]
    return baseline, paths


def build(root: Path) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[str]]:
    baseline, baseline_paths = _baseline_inputs(root)
    excluded_bodies = {
        str(row["normalized_source_body_sha256"])
        for row in baseline
        if row.get("normalized_source_body_sha256")
    }
    excluded_source_shas = {
        str(row["source_sha256"])
        for row in baseline
        if row.get("source_sha256")
    }
    for row in baseline:
        excluded_source_shas.update(str(value) for value in row.get("source_sha256s", []))

    processing = _read_many(root, TARGET_PROCESSING_PATHS)
    api = _enrich_api_family_support(
        _read_jsonl(root / TARGET_API_PATH),
        _read_jsonl(root / TARGET_API_FAMILY_PATH),
    )
    targets = build_target_manifest(
        processing,
        api,
        excluded_bodies=excluded_bodies,
        excluded_source_shas=excluded_source_shas,
    )
    if any(not str(row["source_path"]).startswith("/home/yll/") for row in targets):
        raise ValueError("pilot target source must remain under read-only /home/yll")
    target_bodies = {str(row["normalized_source_body_sha256"]) for row in targets}
    if target_bodies & excluded_bodies:
        raise ValueError("target manifest overlaps regression baseline normalized bodies")
    return targets, baseline, [
        *TARGET_PROCESSING_PATHS,
        TARGET_API_PATH,
        TARGET_API_FAMILY_PATH,
        *baseline_paths,
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path("docs/reports/qgis_external_analysis_pilot_v1/inputs"),
    )
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()
    root = args.repo_root.resolve()
    output_dir = args.output_dir
    if not output_dir.is_absolute():
        output_dir = root / output_dir

    targets, baseline, input_paths = build(root)
    input_hashes = {relative: _sha256(root / relative) for relative in input_paths}
    summary = {
        "target_rows": len(targets),
        "processing_targets": sum(row["corpus_kind"] == "processing" for row in targets),
        "api_targets": sum(row["corpus_kind"] == "api" for row in targets),
        "target_unique_normalized_bodies": len(
            {row["normalized_source_body_sha256"] for row in targets}
        ),
        "baseline_rows": len(baseline),
        "baseline_roles": dict(sorted(Counter(row["baseline_role"] for row in baseline).items())),
        "target_strata": dict(sorted(Counter(row["primary_stratum"] for row in targets).items())),
        "holdout_overlap": 0,
        "training_rows_emitted": 0,
    }
    if not args.dry_run:
        write_pilot_artifacts(
            output_dir,
            targets,
            baseline,
            input_hashes=input_hashes,
        )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
