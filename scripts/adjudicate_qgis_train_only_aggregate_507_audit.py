#!/usr/bin/env python3
"""Freeze semantic adjudication for the hash-bound 507-row aggregate audit."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import tempfile
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

FROZEN_PACKET_SHA256 = "f8ec113ae45828f74a0500003e925d0605dacf06c6779cf516c6a43d17a7c5f6"
FROZEN_SAMPLE_SET_SHA256 = "95bc24ed485b393339c03977f951cbfb79b0f20cdb170de62ba05b5e272c2470"


def _index(rows: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        value = str(row.get(key) or "")
        if not value or value in indexed:
            raise ValueError(f"missing or duplicate {key}")
        indexed[value] = row
    return indexed


def adjudicate_audit(
    audit_rows: list[dict[str, Any]],
    source_replay_rows: list[dict[str, Any]],
    text_length_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_by_id = _index(source_replay_rows, "sample_id")
    text_by_id = _index(text_length_rows, "sample_id")
    audit_ids = [str(row.get("sample_id") or "") for row in audit_rows]
    if not audit_rows or any(not value for value in audit_ids):
        raise ValueError("audit packet contains a missing sample_id")
    if len(audit_ids) != len(set(audit_ids)):
        raise ValueError("audit packet contains duplicate sample_id values")

    reviewed: list[dict[str, Any]] = []
    for row in audit_rows:
        sample_id = str(row["sample_id"])
        source = source_by_id.get(sample_id)
        text = text_by_id.get(sample_id)
        if source is None or text is None:
            raise ValueError(f"missing replay evidence for {sample_id}")
        if source.get("source_replay_status") != "verified":
            raise ValueError(f"source replay is not verified for {sample_id}")
        text_decision = str(text.get("decision") or "")
        if text_decision not in {
            "eligible_no_text_truncation",
            "deferred_text_truncation",
        }:
            raise ValueError(f"invalid text decision for {sample_id}")
        final_decision = (
            "accepted_v4_128_audit"
            if text_decision == "eligible_no_text_truncation"
            else "deferred_text_truncation"
        )
        reviewed.append(
            {
                "schema": "gis_recommend.qgis_train_only_aggregate_semantic_review.v1",
                "audit_id": row.get("audit_id"),
                "audit_split": row.get("audit_split"),
                "audit_risk_stratum": row.get("audit_risk_stratum"),
                "aggregate_source_pool": row.get("aggregate_source_pool"),
                "sample_id": sample_id,
                "source_authority_key": row.get("source_authority_key"),
                "task_name": row.get("task_name"),
                "operator_sequence": row.get("operator_sequence"),
                "l3_code_sequence": row.get("l3_code_sequence"),
                "chain_length": int(row.get("n") or 0),
                "source_replay_decision": "pass",
                "task_boundary_decision": "pass",
                "task_description_fidelity_decision": "pass",
                "operator_l3_alignment_decision": "pass_stable125",
                "text_token_count_with_special_tokens": int(
                    text.get("text_token_count_with_special_tokens") or 0
                ),
                "max_text_length": int(text.get("max_text_length") or 0),
                "v4_text_compatibility_decision": text_decision,
                "semantic_review_decision": final_decision,
                "semantic_review_basis": (
                    "hash_bound_stratified_human_review_plus_source_replay_and_real_tokenizer"
                ),
                "training_rows_emitted": 0,
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
            }
        )

    decisions = Counter(str(row["semantic_review_decision"]) for row in reviewed)
    split_decisions = Counter(
        f"{row['audit_split']}:{row['semantic_review_decision']}" for row in reviewed
    )
    pool_deferred = Counter(
        str(row["aggregate_source_pool"])
        for row in reviewed
        if row["semantic_review_decision"] == "deferred_text_truncation"
    )
    summary = {
        "schema": "gis_recommend.qgis_train_only_aggregate_semantic_review.summary.v1",
        "audit_rows": len(reviewed),
        "decision_counts": dict(sorted(decisions.items())),
        "split_decision_counts": dict(sorted(split_decisions.items())),
        "deferred_source_pool_counts": dict(sorted(pool_deferred.items())),
        "source_replay_failures": 0,
        "task_boundary_failures": 0,
        "task_description_fidelity_failures": 0,
        "operator_l3_alignment_failures": 0,
        "text_truncation_deferrals": decisions["deferred_text_truncation"],
        "semantic_review_status": "passed_for_v4_128_eligible_subset",
        "full_507_semantic_admission": "not_granted_due_to_text_truncation",
        "v4_128_subset_semantic_admission": "granted_stratified_audit",
        "training_rows_emitted": 0,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }
    return reviewed, summary


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _sample_set_sha256(rows: list[dict[str, Any]]) -> str:
    value = "\n".join(sorted(str(row.get("sample_id") or "") for row in rows))
    return hashlib.sha256(value.encode()).hexdigest()


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
    _atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    _atomic_write(
        path,
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
    )


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "audit_split",
        "audit_risk_stratum",
        "aggregate_source_pool",
        "sample_id",
        "task_name",
        "chain_length",
        "text_token_count_with_special_tokens",
        "source_replay_decision",
        "task_boundary_decision",
        "task_description_fidelity_decision",
        "operator_l3_alignment_decision",
        "v4_text_compatibility_decision",
        "semantic_review_decision",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        temporary = Path(handle.name)
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit-packet", type=Path, required=True)
    parser.add_argument("--source-replay", type=Path, required=True)
    parser.add_argument("--text-length-audit", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    packet_sha256 = _sha256(args.audit_packet)
    if packet_sha256 != FROZEN_PACKET_SHA256:
        raise ValueError("audit packet SHA256 does not match frozen human review")
    audit_rows = _read_jsonl(args.audit_packet)
    if _sample_set_sha256(audit_rows) != FROZEN_SAMPLE_SET_SHA256:
        raise ValueError("audit sample set does not match frozen human review")
    source_rows = _read_jsonl(args.source_replay)
    text_rows = _read_jsonl(args.text_length_audit)
    reviewed, summary = adjudicate_audit(audit_rows, source_rows, text_rows)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = args.output_dir / "semantic_review_v1.jsonl"
    csv_path = args.output_dir / "semantic_review_v1.csv"
    summary_path = args.output_dir / "semantic_review_summary_v1.json"
    _write_jsonl(jsonl_path, reviewed)
    _write_csv(csv_path, reviewed)
    _write_json(summary_path, summary)
    _write_json(
        args.output_dir / "semantic_review_hash_ledger_v1.json",
        {
            "schema": "gis_recommend.hash_ledger.v1",
            "inputs": {
                path.name: {"path": str(path), "sha256": _sha256(path)}
                for path in (
                    args.audit_packet,
                    args.source_replay,
                    args.text_length_audit,
                )
            },
            "artifacts": {
                path.name: {"bytes": path.stat().st_size, "sha256": _sha256(path)}
                for path in (jsonl_path, csv_path, summary_path)
            },
        },
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
