#!/usr/bin/env python3
"""Rank source-backed stable101 mapping gaps by immediate unlock impact."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from gis_recommend.data.qgis_source_authority import source_authority
from scripts.build_qgis_taxonomy_v1 import ADDITIONS


DATABASE_SIDE_EFFECT_OPERATORS = {
    "gdal:importvectorintopostgisdatabaseavailableconnections",
    "native:importintopostgis",
    "native:postgisexecutesql",
}
SUPPORT_EXPORT_OPERATORS = {
    "native:createspatialindex",
    "native:exporttospreadsheet",
    "native:filedownloader",
    "native:saveselectedfeatures",
}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _experimental_aliases() -> dict[str, str]:
    return {
        str(alias).lower(): str(addition["code"])
        for addition in ADDITIONS
        for alias in addition.get("aliases") or []
    }


def build_admission_census(
    manifest_rows: list[dict[str, Any]],
    *,
    semantic_adjudications: dict[str, dict[str, Any]],
    effective_mapping: dict[str, str] | None = None,
    source_authority_rows: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if effective_mapping is not None:
        replayed_rows = replay_effective_mapping(manifest_rows, effective_mapping)
    else:
        replayed_rows = manifest_rows
    incomplete = [
        row
        for row in replayed_rows
        if row.get("normalization_status") == "fully_normalized"
        and not row.get("mapping_complete")
    ]
    eligible = [
        row
        for row in incomplete
        if row.get("structure_action") == "auto_accept_candidate"
    ]
    semantic_operators = {
        str(operator_id)
        for row in eligible
        if not (
            set(row.get("unmapped_operator_ids") or [])
            & (DATABASE_SIDE_EFFECT_OPERATORS | SUPPORT_EXPORT_OPERATORS)
        )
        for operator_id in row.get("unmapped_operator_ids") or []
    }
    missing = sorted(semantic_operators - set(semantic_adjudications))
    if missing:
        raise ValueError("missing semantic adjudications: " + ", ".join(missing))

    source_paths_by_sha: dict[str, list[Path]] = defaultdict(list)
    for source_row in source_authority_rows or []:
        sha = str(source_row.get("source_sha256") or "")
        path = Path(str(source_row.get("source_path") or ""))
        if sha and path not in source_paths_by_sha[sha]:
            source_paths_by_sha[sha].append(path)

    ledger: list[dict[str, Any]] = []
    for row in eligible:
        gaps = [str(value) for value in row.get("unmapped_operator_ids") or []]
        gap_set = set(gaps)
        declared_path = Path(str(row.get("source_path") or ""))
        path = declared_path
        declared_sha = str(row.get("source_sha256") or "")
        source_verified = path.is_file() and _sha256(path) == declared_sha
        source_path_resolution = (
            "declared_path_sha_match" if source_verified else "source_unresolved"
        )
        if not source_verified:
            for candidate in source_paths_by_sha.get(declared_sha, []):
                if candidate.is_file() and _sha256(candidate) == declared_sha:
                    path = candidate
                    source_verified = True
                    source_path_resolution = "source_manifest_sha_match"
                    break
        authority = source_authority(path, source_sha256=declared_sha)
        if gap_set & DATABASE_SIDE_EFFECT_OPERATORS:
            decision = "exclude_database_side_effect"
            reviews: list[dict[str, Any]] = []
        elif gap_set & SUPPORT_EXPORT_OPERATORS:
            decision = "exclude_support_export"
            reviews = []
        else:
            reviews = [semantic_adjudications[operator_id] for operator_id in gaps]
            allowed = {
                "admit_exact_stable110_mapping",
                "defer_no_exact_stable110_mapping",
            }
            invalid = sorted(
                {
                    str(review.get("decision") or "")
                    for review in reviews
                    if review.get("decision") not in allowed
                }
            )
            if invalid:
                raise ValueError("invalid semantic adjudication decisions: " + ", ".join(invalid))
            decision = (
                "existing_stable110_candidate"
                if all(
                    review.get("decision") == "admit_exact_stable110_mapping"
                    for review in reviews
                )
                else "defer_no_exact_stable110_mapping"
            )
        ledger.append(
            {
                "schema": "gis_recommend.qgis_processing_mapping_gap_admission.v1",
                "record_id": str(row.get("record_id") or ""),
                "source_root_id": str(row.get("source_root_id") or ""),
                "declared_source_path": str(declared_path),
                "source_path": str(path),
                "source_path_resolution": source_path_resolution,
                "source_sha256": declared_sha,
                "source_sha256_verified": source_verified,
                **authority,
                "feature_signature_hash": str(row.get("feature_signature_hash") or ""),
                "operator_ids": row.get("operator_ids") or [],
                "unmapped_operator_ids": gaps,
                "census_decision": decision,
                "semantic_adjudications": reviews,
                "training_admission": "not_granted_census_only",
                "training_row_emitted": False,
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
            }
        )
    ledger.sort(key=lambda row: row["record_id"])
    database_rows = [
        row for row in ledger if row["census_decision"] == "exclude_database_side_effect"
    ]
    support_rows = [
        row for row in ledger if row["census_decision"] == "exclude_support_export"
    ]
    semantic_rows = [
        row
        for row in ledger
        if row["census_decision"]
        in {"existing_stable110_candidate", "defer_no_exact_stable110_mapping"}
    ]
    candidates = [
        row
        for row in semantic_rows
        if row["census_decision"] == "existing_stable110_candidate"
    ]
    summary = {
        "schema": "gis_recommend.qgis_processing_mapping_gap_admission_summary.v1",
        "input_rows": len(replayed_rows),
        "fully_normalized_mapping_incomplete_rows": len(incomplete),
        "structure_eligible_rows": len(eligible),
        "structure_ineligible_rows": len(incomplete) - len(eligible),
        "database_side_effect_rows": len(database_rows),
        "support_export_rows": len(support_rows),
        "semantic_review_rows": len(semantic_rows),
        "semantic_unique_source_sha256": len(
            {row["source_sha256"] for row in semantic_rows}
        ),
        "semantic_unique_normalized_source_bodies": len(
            {
                row["normalized_source_body_sha256"]
                for row in semantic_rows
                if row["normalized_source_body_sha256"]
            }
        ),
        "semantic_unique_feature_signatures": len(
            {row["feature_signature_hash"] for row in semantic_rows}
        ),
        "source_sha256_verified_rows": sum(
            row["source_sha256_verified"] for row in ledger
        ),
        "source_manifest_resolved_rows": sum(
            row["source_path_resolution"] == "source_manifest_sha_match"
            for row in ledger
        ),
        "source_unverified_rows": sum(
            not row["source_sha256_verified"] for row in ledger
        ),
        "existing_stable110_candidate_rows": len(candidates),
        "training_admission": "not_granted_census_only",
        "training_rows_emitted": 0,
        "production_merge": "not_granted",
    }
    return ledger, summary


def replay_effective_mapping(
    manifest_rows: list[dict[str, Any]], effective_mapping: dict[str, str]
) -> list[dict[str, Any]]:
    mapping = {str(key).lower(): value for key, value in effective_mapping.items()}
    replayed = []
    for row in manifest_rows:
        operators = [
            str(value).lower() for value in row.get("canonical_operator_ids") or []
        ]
        gaps = list(dict.fromkeys(value for value in operators if value not in mapping))
        replayed.append(
            {
                **row,
                "mapping_complete": bool(operators) and not gaps,
                "unmapped_operator_ids": gaps,
            }
        )
    return replayed


def build_admission_clusters(ledger: list[dict[str, Any]]) -> dict[str, Any]:
    semantic = [
        row
        for row in ledger
        if row.get("census_decision")
        in {"existing_stable110_candidate", "defer_no_exact_stable110_mapping"}
    ]
    return {
        "schema": "gis_recommend.qgis_processing_mapping_gap_clusters.v1",
        "semantic_rows": len(semantic),
        "operator_clusters": dict(
            sorted(
                Counter(
                    operator
                    for row in semantic
                    for operator in row.get("unmapped_operator_ids") or []
                ).items()
            )
        ),
        "normalized_source_body_clusters": dict(
            sorted(
                Counter(
                    str(row["normalized_source_body_sha256"])
                    for row in semantic
                    if row.get("normalized_source_body_sha256")
                ).items()
            )
        ),
        "source_authority_clusters": dict(
            sorted(Counter(str(row["source_authority_key"]) for row in semantic).items())
        ),
        "feature_signature_clusters": dict(
            sorted(
                Counter(str(row.get("feature_signature_hash") or "") for row in semantic).items()
            )
        ),
        "training_rows_emitted": 0,
    }


def build_queue(
    manifest_rows: list[dict[str, Any]],
    crosswalk: dict[str, Any],
    *,
    top_n: int = 15,
    samples_per_operator: int = 3,
    verify_sources: bool = True,
    excluded_operator_ids: set[str] | None = None,
    allowed_operator_ids: set[str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    excluded = {value.lower() for value in excluded_operator_ids or set()}
    allowed = (
        {value.lower() for value in allowed_operator_ids}
        if allowed_operator_ids is not None
        else None
    )
    incomplete = [
        row
        for row in manifest_rows
        if row.get("normalization_status") == "fully_normalized"
        and not row.get("mapping_complete")
    ]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    single_gap: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in incomplete:
        gaps = list(dict.fromkeys(row.get("unmapped_operator_ids") or []))
        for operator_id in gaps:
            grouped[str(operator_id)].append(row)
        if len(gaps) == 1:
            single_gap[str(gaps[0])].append(row)

    for operator_id in list(grouped):
        if operator_id.lower() in excluded or (
            allowed is not None and operator_id.lower() not in allowed
        ):
            grouped.pop(operator_id)
            single_gap.pop(operator_id, None)

    ranked = sorted(
        grouped,
        key=lambda operator_id: (
            -len(single_gap[operator_id]),
            -len({tuple(row.get("operator_ids") or []) for row in single_gap[operator_id]}),
            -len(grouped[operator_id]),
            operator_id,
        ),
    )[:top_n]
    crosswalk_entries = crosswalk.get("entries") or {}
    experimental = _experimental_aliases()
    queue: list[dict[str, Any]] = []
    for rank, operator_id in enumerate(ranked, start=1):
        candidates = sorted(
            single_gap[operator_id] or grouped[operator_id],
            key=lambda row: (
                str(row.get("source_root_id") or ""),
                str(row.get("source_sha256") or ""),
                str(row.get("record_id") or ""),
            ),
        )
        samples: list[dict[str, Any]] = []
        source_verification_failures: list[str] = []
        seen_sha: set[str] = set()
        used_roots: set[str] = set()
        for prefer_new_root in (True, False):
            for row in candidates:
                sha = str(row.get("source_sha256") or "")
                root = str(row.get("source_root_id") or "")
                if not sha or sha in seen_sha or prefer_new_root and root in used_roots:
                    continue
                path = Path(str(row.get("source_path") or ""))
                verified = path.is_file() and _sha256(path) == sha
                if verify_sources and not verified:
                    source_verification_failures.append(str(row.get("record_id") or ""))
                    continue
                samples.append(
                    {
                        "record_id": row.get("record_id"),
                        "source_root_id": root,
                        "source_path": str(path),
                        "source_sha256": sha,
                        "source_verification": "verified_sha256" if verified else "not_checked",
                        "operator_ids": row.get("operator_ids") or [],
                        "source_snippet": row.get("source_snippet") or "",
                    }
                )
                seen_sha.add(sha)
                used_roots.add(root)
                if len(samples) == samples_per_operator:
                    break
            if len(samples) == samples_per_operator:
                break
        entry = crosswalk_entries.get(operator_id) or {}
        experimental_code = experimental.get(operator_id, "")
        queue.append(
            {
                "schema": "gis_recommend.qgis_processing_mapping_gap_queue.v1",
                "rank": rank,
                "operator_id": operator_id,
                "single_gap_records": len(single_gap[operator_id]),
                "single_gap_unique_chains": len(
                    {tuple(row.get("operator_ids") or []) for row in single_gap[operator_id]}
                ),
                "all_gap_records": len(grouped[operator_id]),
                "all_gap_unique_chains": len(
                    {tuple(row.get("operator_ids") or []) for row in grouped[operator_id]}
                ),
                "crosswalk_status": entry.get("status", ""),
                "crosswalk_bridge_type": entry.get("bridge_type", ""),
                "crosswalk_l3_code": entry.get("l3_code", ""),
                "experimental_114_candidate_l3": experimental_code,
                "review_route": (
                    "experimental_114_candidate_not_admitted"
                    if experimental_code
                    else "existing_bridge_needs_taxonomy_review"
                    if entry.get("status") == "accepted"
                    else "prior_rejected_recheck_only"
                    if entry.get("status") == "rejected"
                    else "pending_source_semantic_review"
                ),
                "samples": samples,
                "source_verification_failure_count": len(
                    set(source_verification_failures)
                ),
                "mapping_admission": "not_granted_review_queue_only",
                "training_admission": "not_granted_review_queue_only",
                "training_row_emitted": False,
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
            }
        )
    summary = {
        "schema": "gis_recommend.qgis_processing_mapping_gap_queue_summary.v1",
        "fully_normalized_mapping_incomplete_rows": len(incomplete),
        "unique_mapping_gap_operators": len(grouped),
        "excluded_adjudicated_operators": len(excluded),
        "operator_allowlist_applied": allowed is not None,
        "allowed_operator_count": len(allowed or ()),
        "queue_operators": len(queue),
        "queue_single_gap_records": sum(row["single_gap_records"] for row in queue),
        "queue_source_samples": sum(len(row["samples"]) for row in queue),
        "source_verification_failure_rows": sum(
            row["source_verification_failure_count"] for row in queue
        ),
        "mapping_admission": "not_granted_review_queue_only",
        "training_rows_emitted": 0,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }
    return queue, summary


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", dir=path.parent, delete=False) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--crosswalk", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--top", type=int, default=15)
    parser.add_argument("--samples-per-operator", type=int, default=3)
    parser.add_argument("--exclude-adjudications", type=Path)
    parser.add_argument("--operator-id", action="append", default=None)
    parser.add_argument("--effective-mapping", type=Path)
    parser.add_argument("--semantic-adjudications", type=Path)
    parser.add_argument("--source-authority-manifest", type=Path, action="append", default=[])
    args = parser.parse_args()
    if bool(args.effective_mapping) != bool(args.semantic_adjudications):
        parser.error(
            "--effective-mapping and --semantic-adjudications must be provided together"
        )
    manifest_rows = _load_jsonl(args.manifest)
    effective_mapping = None
    if args.effective_mapping:
        effective_mapping = json.loads(
            args.effective_mapping.read_text(encoding="utf-8")
        )
        if not isinstance(effective_mapping, dict):
            raise ValueError("effective mapping must be a JSON object")
    effective_manifest_rows = (
        replay_effective_mapping(manifest_rows, effective_mapping)
        if effective_mapping is not None
        else manifest_rows
    )
    excluded = {
        str(row.get("operator_id") or "")
        for row in _load_jsonl(args.exclude_adjudications)
    } if args.exclude_adjudications else set()
    queue, summary = build_queue(
        effective_manifest_rows,
        json.loads(args.crosswalk.read_text(encoding="utf-8")),
        top_n=args.top,
        samples_per_operator=args.samples_per_operator,
        excluded_operator_ids=excluded,
        allowed_operator_ids=set(args.operator_id) if args.operator_id else None,
    )
    queue_path = args.output_dir / "mapping_gap_queue_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    report = args.output_dir / "report_v1.md"
    hashes = args.output_dir / "hash_ledger_v1.json"
    _atomic_write(queue_path, "".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in queue))
    _atomic_write(summary_path, json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    lines = ["# QGIS Processing mapping-gap queue v1", "", "Review queue only; no mapping or training admission is granted.", "", "| Rank | Operator | Single-gap records | Unique chains | Route |", "|---:|---|---:|---:|---|"]
    lines.extend(f"| {row['rank']} | `{row['operator_id']}` | {row['single_gap_records']} | {row['single_gap_unique_chains']} | {row['review_route']} |" for row in queue)
    _atomic_write(report, "\n".join(lines) + "\n")
    admission_artifacts: list[Path] = []
    if args.effective_mapping and args.semantic_adjudications:
        adjudication_rows = _load_jsonl(args.semantic_adjudications)
        adjudications = {
            str(row.get("operator_id") or ""): row for row in adjudication_rows
        }
        if len(adjudications) != len(adjudication_rows) or "" in adjudications:
            raise ValueError("semantic adjudications contain blank or duplicate operator_id")
        admission, admission_summary = build_admission_census(
            effective_manifest_rows,
            source_authority_rows=[
                row
                for path in args.source_authority_manifest
                for row in _load_jsonl(path)
            ],
            semantic_adjudications=adjudications,
        )
        admission_path = args.output_dir / "admission_ledger_v1.jsonl"
        admission_summary_path = args.output_dir / "admission_summary_v1.json"
        admission_clusters_path = args.output_dir / "admission_clusters_v1.json"
        admission_report_path = args.output_dir / "admission_report_v1.md"
        _atomic_write(
            admission_path,
            "".join(
                json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                + "\n"
                for row in admission
            ),
        )
        _atomic_write(
            admission_summary_path,
            json.dumps(admission_summary, ensure_ascii=False, indent=2, sort_keys=True)
            + "\n",
        )
        _atomic_write(
            admission_clusters_path,
            json.dumps(
                build_admission_clusters(admission),
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
        )
        _atomic_write(
            admission_report_path,
            "# QGIS Processing corrected stable110 mapping-gap admission census v1\n\n"
            f"- Corrected fully-normalized mapping gaps: {admission_summary['fully_normalized_mapping_incomplete_rows']}\n"
            f"- Structurally eligible direct rows: {admission_summary['structure_eligible_rows']}\n"
            f"- Database-side-effect rows excluded: {admission_summary['database_side_effect_rows']}\n"
            f"- Support/export rows excluded: {admission_summary['support_export_rows']}\n"
            f"- Semantic rows reviewed: {admission_summary['semantic_review_rows']}\n"
            f"- Source SHA verified: {admission_summary['source_sha256_verified_rows']}\n"
            f"- Source-unverified sidecar rows: {admission_summary['source_unverified_rows']}\n"
            f"- Semantic normalized source bodies: {admission_summary['semantic_unique_normalized_source_bodies']}\n"
            f"- Exact existing-stable110 candidates: {admission_summary['existing_stable110_candidate_rows']}\n"
            "- Decision: frozen stable110 yields no additional Processing training candidate from this lane.\n"
            "- Training rows emitted: 0\n",
        )
        admission_artifacts = [
            admission_path,
            admission_summary_path,
            admission_clusters_path,
            admission_report_path,
        ]
    _atomic_write(hashes, json.dumps({
        "schema": "gis_recommend.hash_ledger.v1",
        "inputs": {
            str(args.manifest): _sha256(args.manifest),
            str(args.crosswalk): _sha256(args.crosswalk),
            **(
                {str(args.exclude_adjudications): _sha256(args.exclude_adjudications)}
                if args.exclude_adjudications
                else {}
            ),
            **(
                {
                    str(args.effective_mapping): _sha256(args.effective_mapping),
                    str(args.semantic_adjudications): _sha256(
                        args.semantic_adjudications
                    ),
                }
                if args.effective_mapping and args.semantic_adjudications
                else {}
            ),
            **{
                str(path): _sha256(path) for path in args.source_authority_manifest
            },
        },
        "artifacts": {
            path.name: _sha256(path)
            for path in (queue_path, summary_path, report, *admission_artifacts)
        },
    }, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
