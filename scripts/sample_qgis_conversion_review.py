#!/usr/bin/env python3
"""Deterministically sample rule-level QGIS routing matches for human audit."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path


HUMAN_FIELDS = (
    "human_boundary_correct",
    "human_dependency_correct",
    "human_operator_order_correct",
    "human_task_text_faithful",
    "human_final_decision",
    "human_notes",
)


def _rank(row: dict, seed: str) -> str:
    identity = "|".join(
        [
            seed,
            str(row.get("rule_id", "")),
            str(row.get("source_sha256", "")),
            str(row.get("record_id", "")),
            str(row.get("signature_hash", "")),
        ]
    )
    return hashlib.sha256(identity.encode()).hexdigest()


def sample(
    manifest_path: Path,
    *,
    rule_id: str,
    sample_size: int,
    seed: str,
    exclude_source_jsonl: Path | None = None,
    carry_forward_jsonl: Path | None = None,
) -> tuple[list[dict], dict]:
    rows = [
        json.loads(line)
        for line in manifest_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    excluded_source_sha: set[str] = set()
    if exclude_source_jsonl is not None:
        excluded_source_sha = {
            str(json.loads(line).get("source_sha256", ""))
            for line in exclude_source_jsonl.read_text(encoding="utf-8").splitlines()
            if line.strip()
        }
    rule_matches = [row for row in rows if row.get("rule_id") == rule_id]
    eligible = [
        row
        for row in rule_matches
        if str(row.get("source_sha256", "")) not in excluded_source_sha
    ]
    eligible_by_identity = {
        (str(row.get("record_id", "")), str(row.get("source_sha256", ""))): row
        for row in eligible
    }
    carried: list[dict] = []
    prior_rows = 0
    if carry_forward_jsonl is not None:
        seen_prior: set[tuple[str, str]] = set()
        for line in carry_forward_jsonl.read_text(encoding="utf-8").splitlines():
            if not line.strip():
                continue
            prior_rows += 1
            prior = json.loads(line)
            identity = (
                str(prior.get("record_id", "")),
                str(prior.get("source_sha256", "")),
            )
            if identity in seen_prior:
                raise ValueError(f"duplicate carry-forward identity: {identity}")
            seen_prior.add(identity)
            if identity in eligible_by_identity:
                carried.append(eligible_by_identity[identity])
    carried = carried[:sample_size]
    carried_identities = {
        (str(row.get("record_id", "")), str(row.get("source_sha256", "")))
        for row in carried
    }
    fill = sorted(
        [
            row
            for row in eligible
            if (
                str(row.get("record_id", "")),
                str(row.get("source_sha256", "")),
            )
            not in carried_identities
        ],
        key=lambda row: _rank(row, seed),
    )[: max(0, sample_size - len(carried))]
    selected = carried + fill
    packet = []
    for position, row in enumerate(selected, start=1):
        output = dict(row)
        output.update(
            {
                "review_position": position,
                "sampling_seed": seed,
                "sampling_rank": _rank(row, seed),
                "review_status": "pending",
                "training_admission": "not_granted_pending_rule_audit",
                **{field: "" for field in HUMAN_FIELDS},
            }
        )
        packet.append(output)
    summary = {
        "schema": "gis_recommend.qgis_conversion_rule_audit_sample.v1",
        "rule_id": rule_id,
        "eligible_rows": len(eligible),
        "rule_match_rows_before_exclusion": len(rule_matches),
        "excluded_source_overlap_rows": len(rule_matches) - len(eligible),
        "requested_sample_size": sample_size,
        "sampled_rows": len(packet),
        "carried_forward_rows": len(carried),
        "dropped_prior_rows": prior_rows - len(carried),
        "newly_sampled_rows": len(fill),
        "sampling_seed": seed,
        "unique_source_sha": len({row["source_sha256"] for row in packet}),
        "signature_counts": dict(
            sorted(Counter(row["signature_hash"] for row in packet).items())
        ),
        "review_status": "pending",
        "training_rows_emitted": 0,
        "training_admission": "not_granted_pending_rule_audit",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }
    return packet, summary


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--rule-id", default="direct-explicit-dag-v1")
    parser.add_argument("--sample-size", type=int, default=30)
    parser.add_argument("--seed", default="qgis-rule-audit-v1")
    parser.add_argument("--exclude-source-jsonl", type=Path)
    parser.add_argument("--carry-forward-jsonl", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    rows, summary = sample(
        args.manifest,
        rule_id=args.rule_id,
        sample_size=args.sample_size,
        seed=args.seed,
        exclude_source_jsonl=args.exclude_source_jsonl,
        carry_forward_jsonl=args.carry_forward_jsonl,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    packet = args.output_dir / "review_packet.jsonl"
    summary_path = args.output_dir / "review_summary.json"
    packet.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {"packet": packet, "summary": summary_path}


if __name__ == "__main__":
    main()
