#!/usr/bin/env python3
"""Replay bounded conditional-passthrough matching by QGIS source authority."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from gis_recommend.data.qgis_conditional_paths import (
    MATCHER_VERSION,
    match_conditional_passthrough_paths,
)
from gis_recommend.data.qgis_source_authority import source_authority


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = (
    ROOT
    / "docs/reports/qgis_mapping_high_impact_blockers_2026-07-24"
    / "stable101_all1442_source_replay_v1/routing_v6/routing_manifest.jsonl"
)
DEFAULT_CALIBRATION = (
    ROOT
    / "docs/reports/qgis_recovery_control_flow_if_audit_census_v1"
    / "proposal_v1/proposal_replay_ledger.jsonl"
)
DEFAULT_OUTPUT_DIR = ROOT / "docs/reports/qgis_conditional_path_census_v1"

HUMAN_FIELDS = (
    "human_dependency_correct",
    "human_operator_order_correct",
    "human_boundary_correct",
    "human_branch_semantics_recoverable",
    "human_final_decision",
    "human_notes",
)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _wilson_lower(successes: int, total: int, z: float = 1.96) -> float:
    if total == 0:
        return 0.0
    proportion = successes / total
    denominator = 1 + z * z / total
    centre = proportion + z * z / (2 * total)
    margin = z * math.sqrt(
        (proportion * (1 - proportion) + z * z / (4 * total)) / total
    )
    return (centre - margin) / denominator


def _source_snippet(path: Path, call_sites: list[dict[str, Any]]) -> str:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    if not call_sites:
        return ""
    start = max(1, min(int(site["line_start"]) for site in call_sites) - 5)
    end = min(
        len(lines),
        max(int(site.get("line_end") or site["line_start"]) for site in call_sites)
        + 5,
    )
    return "\n".join(
        f"{line_number}: {lines[line_number - 1]}"
        for line_number in range(start, end + 1)
    )


def _replay_row(row: dict[str, Any]) -> dict[str, Any]:
    source_path = Path(str(row.get("source_path") or ""))
    declared_sha = str(row.get("source_sha256") or "")
    if not source_path.is_file():
        return {"status": "failed", "reasons": ["source_file_missing"]}
    if _sha256(source_path) != declared_sha:
        return {"status": "failed", "reasons": ["source_sha256_mismatch"]}
    authority = source_authority(source_path, source_sha256=declared_sha)
    result = match_conditional_passthrough_paths(
        source_path.read_text(encoding="utf-8", errors="replace"),
        call_sites=row.get("call_sites") or [],
    )
    return {
        **result,
        **authority,
        "source_path": str(source_path),
        "source_sha256": declared_sha,
        "source_root_id": str(row.get("source_root_id") or ""),
        "record_id": str(row.get("record_id") or row.get("parent_record_id") or ""),
        "parent_rule_id": str(row.get("rule_id") or row.get("parent_rule_id") or ""),
        "action": str(row.get("action") or ""),
        "operator_ids": [
            str(site.get("operator_id") or "").strip().lower()
            for site in row.get("call_sites") or []
        ],
        "call_sites": row.get("call_sites") or [],
    }


def _representative(rows: list[dict[str, Any]]) -> dict[str, Any]:
    return max(
        rows,
        key=lambda row: (
            len(row.get("path_operator_ids") or []),
            len(row.get("operator_ids") or []),
            str(row.get("record_id") or ""),
        ),
    )


def _calibration_metrics(
    calibration_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    replayed = [_replay_row(row) for row in calibration_rows]
    labels_by_authority: dict[str, set[str]] = defaultdict(set)
    matched_authorities: set[str] = set()
    failed = 0
    for source, replay in zip(calibration_rows, replayed, strict=True):
        authority = str(replay.get("source_authority_key") or "")
        if not authority:
            failed += 1
            continue
        labels_by_authority[authority].add(str(source.get("final_proposal") or ""))
        if replay.get("status") == "matched":
            matched_authorities.add(authority)
    inconsistent = sorted(
        authority for authority, labels in labels_by_authority.items() if len(labels) != 1
    )
    if inconsistent:
        raise ValueError(f"inconsistent proposal labels by authority: {inconsistent}")
    positives = {
        authority
        for authority, labels in labels_by_authority.items()
        if labels == {"valid_candidate"}
    }
    true_positive = len(matched_authorities & positives)
    support = len(matched_authorities)
    precision = true_positive / support if support else 0.0
    recall = true_positive / len(positives) if positives else 0.0
    return {
        "label_authority": "proposal_only_not_human",
        "calibration_rows": len(calibration_rows),
        "calibration_source_authorities": len(labels_by_authority),
        "proposal_valid_authorities": len(positives),
        "matched_support": support,
        "matched_proposal_valid": true_positive,
        "proposal_precision": precision,
        "proposal_recall": recall,
        "proposal_wilson_lower_95": _wilson_lower(true_positive, support),
        "replay_failures": failed,
        "human_adjudication": False,
    }


def build_conditional_path_census(
    manifest_rows: list[dict[str, Any]],
    calibration_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    replayed = [_replay_row(row) for row in manifest_rows]
    matched = [row for row in replayed if row.get("status") == "matched"]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in matched:
        grouped[str(row["source_authority_key"])].append(row)

    authorities: list[dict[str, Any]] = []
    audit_packet: list[dict[str, Any]] = []
    for position, authority_key in enumerate(sorted(grouped), start=1):
        group = grouped[authority_key]
        source = _representative(group)
        authority_row = {
            **source,
            "schema": "gis_recommend.qgis_conditional_path_authority.v1",
            "authority_position": position,
            "raw_match_count": len(group),
            "matched_record_ids": sorted({row["record_id"] for row in group}),
            "proposal_only": True,
            "human_adjudication": False,
            "training_admission": "not_granted_rule_calibration_only",
            "training_row_emitted": False,
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
        }
        authorities.append(authority_row)
        audit_packet.append(
            {
                **authority_row,
                "schema": "gis_recommend.qgis_conditional_path_human_audit.v1",
                "source_snippet": _source_snippet(
                    Path(authority_row["source_path"]), authority_row["call_sites"]
                ),
                "review_status": "pending_human_rule_audit",
                "training_admission": "not_granted_human_audit_only",
                **{field: "" for field in HUMAN_FIELDS},
            }
        )

    calibration = _calibration_metrics(calibration_rows)
    support = len(authorities)
    proposal_gate = (
        support >= 30
        and calibration["matched_support"] >= 30
        and calibration["proposal_precision"] >= 0.95
        and calibration["proposal_wilson_lower_95"] >= 0.80
    )
    status_counts = Counter(str(row.get("status") or "failed") for row in replayed)
    reason_counts = Counter(
        reason
        for row in replayed
        if row.get("status") != "matched"
        for reason in row.get("reasons") or []
    )
    summary = {
        "schema": "gis_recommend.qgis_conditional_path_census_summary.v1",
        "matcher_version": MATCHER_VERSION,
        "population_raw_rows": len(manifest_rows),
        "population_source_authorities": len(
            {
                row["source_authority_key"]
                for row in replayed
                if row.get("source_authority_key")
            }
        ),
        "matched_raw_rows": len(matched),
        "matched_source_authorities": support,
        "status_counts": dict(sorted(status_counts.items())),
        "deferred_reason_counts": dict(sorted(reason_counts.items())),
        "provider_type_status_counts": dict(
            sorted(
                Counter(
                    str(row.get("provider_input_type_status") or "not_applicable")
                    for row in matched
                ).items()
            )
        ),
        "path_count_distribution": dict(
            sorted(Counter(len(row["path_operator_ids"]) for row in authorities).items())
        ),
        "calibration": calibration,
        "decision": {
            "proposal_gate_passed": proposal_gate,
            "human_rule_audit_required": True,
            "training_admission": "not_granted",
            "training_rows_emitted": 0,
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
            "thresholds": {
                "source_authority_support": 30,
                "calibration_support": 30,
                "precision": 0.95,
                "wilson_lower_95": 0.80,
            },
        },
    }
    return authorities, audit_packet, summary


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def _jsonl(rows: list[dict[str, Any]]) -> str:
    return "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
        for row in rows
    )


def _render_report(summary: dict[str, Any]) -> str:
    calibration = summary["calibration"]
    decision = summary["decision"]
    return (
        "# QGIS Conditional-Passthrough Path Census v1\n\n"
        "Authority-level rule census only. Proposal labels are not human adjudication.\n\n"
        f"- Raw routing rows: {summary['population_raw_rows']}\n"
        f"- Independent source authorities: {summary['population_source_authorities']}\n"
        f"- Matched raw rows: {summary['matched_raw_rows']}\n"
        f"- Matched source authorities: {summary['matched_source_authorities']}\n"
        f"- Proposal calibration support: {calibration['matched_support']}\n"
        f"- Proposal precision: {calibration['proposal_precision']:.4f}\n"
        f"- Proposal Wilson lower 95%: {calibration['proposal_wilson_lower_95']:.4f}\n"
        f"- Proposal gate passed: {str(decision['proposal_gate_passed']).lower()}\n"
        "- Human rule audit: required\n"
        "- Training rows emitted: 0\n"
    )


def write_outputs(
    authorities: list[dict[str, Any]],
    audit_packet: list[dict[str, Any]],
    summary: dict[str, Any],
    *,
    manifest_path: Path,
    calibration_path: Path,
    output_dir: Path,
) -> dict[str, Path]:
    authority_path = output_dir / "matched_authorities.jsonl"
    audit_path = output_dir / "human_audit_packet.jsonl"
    summary_path = output_dir / "summary.json"
    report_path = output_dir / "README.md"
    hash_path = output_dir / "hash_manifest.json"
    _atomic_write(authority_path, _jsonl(authorities))
    _atomic_write(audit_path, _jsonl(audit_packet))
    _atomic_write(
        summary_path,
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    _atomic_write(report_path, _render_report(summary))
    hashes = {
        "schema": "gis_recommend.qgis_conditional_path_census_hashes.v1",
        "inputs": {
            str(manifest_path): _sha256(manifest_path),
            str(calibration_path): _sha256(calibration_path),
        },
        "outputs": {
            path.name: _sha256(path)
            for path in (authority_path, audit_path, summary_path, report_path)
        },
    }
    _atomic_write(
        hash_path,
        json.dumps(hashes, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    return {
        "authorities": authority_path,
        "audit": audit_path,
        "summary": summary_path,
        "report": report_path,
        "hash": hash_path,
    }


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--calibration", type=Path, default=DEFAULT_CALIBRATION)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)
    authorities, audit_packet, summary = build_conditional_path_census(
        _load_jsonl(args.manifest), _load_jsonl(args.calibration)
    )
    return write_outputs(
        authorities,
        audit_packet,
        summary,
        manifest_path=args.manifest,
        calibration_path=args.calibration,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    main()
