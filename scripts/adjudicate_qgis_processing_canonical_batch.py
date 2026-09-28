#!/usr/bin/env python3
"""Create a hash-bound per-row adjudication for a small canonical calibration batch."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.adjudicate_qgis_mapping_gap_capability_bridges import (  # noqa: E402
    _read_json,
    _sha256,
    _write_json,
    _write_jsonl,
)
from scripts.adjudicate_qgis_processing_signatures import (  # noqa: E402
    _audit_review_row,
    _rule_signature_hash,
)
from scripts.export_qgis_processing_reviewed_training import (  # noqa: E402
    PASS_FIELDS,
    _record_sha256,
)


def build_canonical_batch_adjudication(
    *,
    candidate_rows: list[dict[str, Any]],
    approved_candidate_ids: set[str],
    inherited_rule_authority: dict[str, Any],
    package_hashes: dict[str, str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if not approved_candidate_ids:
        raise ValueError("at least one approved candidate is required")
    canonical = {
        str(row.get("candidate_id") or ""): row
        for row in candidate_rows
        if row.get("dedup_status") == "canonical_candidate"
    }
    missing = approved_candidate_ids - set(canonical)
    if missing:
        raise ValueError("approved candidate is not canonical: " + ", ".join(sorted(missing)))

    review = []
    for candidate_id in sorted(canonical):
        row = dict(canonical[candidate_id])
        row["review_split"] = "canonical_batch"
        row["review_rule_signature"] = _rule_signature_hash(row)
        review.append(row)

    decisions = []
    for row in review:
        if row["candidate_id"] not in approved_candidate_ids:
            continue
        decision = {
            "candidate_id": row["candidate_id"],
            "record_id": row["record_id"],
            "source_sha256": row["source_sha256"],
            "source_authority_key": row["source_authority_key"],
            "unit_id": str(row.get("unit_id") or f"record:{row['record_id']}"),
            "candidate_payload_sha256": _record_sha256(row),
        }
        decision.update({field: "pass" for field in PASS_FIELDS})
        decisions.append(decision)

    adjudication = {
        "schema": "gis_recommend.qgis_processing_adjudication.v1",
        **package_hashes,
        "reviewer_kind": "codex_agent",
        "review_basis": "explicit_canonical_batch_source_replay",
        "review_scope": [
            "task_boundary",
            "operator_sequence",
            "l3_mapping",
            "description_fidelity",
            "parameter_provenance",
        ],
        "description_generation_llm_called": False,
        "decisions": decisions,
        "new_rule_signatures_granted": [],
        "rule_authority": dict(inherited_rule_authority),
    }
    return review, adjudication


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-report-dir", type=Path, required=True)
    parser.add_argument("--rule-adjudication", type=Path, required=True)
    parser.add_argument("--approve-candidate", action="append", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")

    source_candidate_path = args.candidate_report_dir / "candidate_batch_v1.jsonl"
    source_ledger = _read_json(args.candidate_report_dir / "hash_ledger_v1.json")
    expected = (source_ledger.get("artifacts") or {}).get(
        source_candidate_path.name, {}
    )
    expected_sha = expected if isinstance(expected, str) else expected.get("sha256")
    if not expected_sha or _sha256(source_candidate_path) != expected_sha:
        raise ValueError("candidate package SHA256 mismatch")

    rule_adjudication = _read_json(args.rule_adjudication)
    rule_authority = dict(rule_adjudication.get("rule_authority") or {})
    if rule_authority.get("status") != "granted_source_disjoint_zero_failure":
        raise ValueError("inherited rule authority is not granted")

    candidate_rows = _read_jsonl(source_candidate_path)
    approved = set(args.approve_candidate)
    canonical_rows = [
        row
        for row in candidate_rows
        if row.get("dedup_status") == "canonical_candidate"
        and row.get("candidate_id") in approved
    ]
    for row in canonical_rows:
        _audit_review_row(row)

    candidate_path = args.output_dir / "candidate_batch_v1.jsonl"
    review_path = args.output_dir / "source_disjoint_review_v1.jsonl"
    ledger_path = args.output_dir / "hash_ledger_v1.json"
    adjudication_path = args.output_dir / "adjudication_v1.json"
    _write_jsonl(candidate_path, candidate_rows)
    review, _ = build_canonical_batch_adjudication(
        candidate_rows=candidate_rows,
        approved_candidate_ids=approved,
        inherited_rule_authority=rule_authority,
        package_hashes={},
    )
    _write_jsonl(review_path, review)
    _write_json(
        ledger_path,
        {
            "schema": "gis_recommend.hash_ledger.v1",
            "source_inputs": {
                "candidate_report_hash_ledger": {
                    "path": str(args.candidate_report_dir / "hash_ledger_v1.json"),
                    "sha256": _sha256(args.candidate_report_dir / "hash_ledger_v1.json"),
                },
                "inherited_rule_adjudication": {
                    "path": str(args.rule_adjudication),
                    "sha256": _sha256(args.rule_adjudication),
                },
            },
            "artifacts": {
                path.name: {
                    "path": str(path),
                    "sha256": _sha256(path),
                    "bytes": path.stat().st_size,
                }
                for path in (candidate_path, review_path)
            },
        },
    )
    review, adjudication = build_canonical_batch_adjudication(
        candidate_rows=candidate_rows,
        approved_candidate_ids=approved,
        inherited_rule_authority=rule_authority,
        package_hashes={
            "package_hash_ledger_sha256": _sha256(ledger_path),
            "candidate_batch_sha256": _sha256(candidate_path),
            "review_packet_sha256": _sha256(review_path),
        },
    )
    _write_json(adjudication_path, adjudication)
    print(
        json.dumps(
            {
                "canonical_review_rows": len(review),
                "approved_rows": len(adjudication["decisions"]),
                "new_rule_signatures_granted": 0,
                "llm_called": False,
                "training_rows_emitted": 0,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
