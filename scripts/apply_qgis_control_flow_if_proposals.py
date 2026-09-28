#!/usr/bin/env python3
"""Replay source-backed conditional-recovery proposals by source authority."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


CHECK_FIELDS = (
    "dependency_correct",
    "operator_order_correct",
    "boundary_correct",
    "branch_semantics_recoverable",
    "description_scope_correct",
)
FINAL_PROPOSALS = {"valid_candidate", "defer", "reject_current"}
TYPE_DECISIONS = {"compatible", "unknown", "not_applicable", "conflict"}


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


def _metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    support = len({row["source_authority_key"] for row in rows})
    valid = len(
        {
            row["source_authority_key"]
            for row in rows
            if row["final_proposal"] == "valid_candidate"
        }
    )
    precision = valid / support if support else 0.0
    return {
        "support": support,
        "valid": valid,
        "defer": sum(row["final_proposal"] == "defer" for row in rows),
        "reject_current": sum(
            row["final_proposal"] == "reject_current" for row in rows
        ),
        "observed_precision": precision,
        "wilson_lower_95": _wilson_lower(valid, support),
        "training_eligible": (
            support >= 30
            and precision >= 0.95
            and _wilson_lower(valid, support) >= 0.80
        ),
    }


def apply_proposals(
    packet_path: Path, proposals_path: Path
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    packet = _load_jsonl(packet_path)
    proposals = _load_jsonl(proposals_path)
    packet_by_position = {int(row["review_position"]): row for row in packet}
    proposal_by_position = {int(row["review_position"]): row for row in proposals}
    if len(packet_by_position) != len(packet):
        raise ValueError("packet review positions must be unique")
    if len(proposal_by_position) != len(proposals):
        raise ValueError("proposal review positions must be unique")
    if set(packet_by_position) != set(proposal_by_position):
        raise ValueError("proposals must cover every packet position exactly once")
    if len({row["source_authority_key"] for row in packet}) != len(packet):
        raise ValueError("packet must contain one row per source authority")

    ledger: list[dict[str, Any]] = []
    for position in sorted(packet_by_position):
        source = packet_by_position[position]
        proposal = proposal_by_position[position]
        if source.get("human_final_decision"):
            raise ValueError(f"packet human decision must remain blank: {position}")
        if proposal.get("source_authority_key") != source.get(
            "source_authority_key"
        ):
            raise ValueError(f"source authority mismatch: {position}")
        if any(not isinstance(proposal.get(field), bool) for field in CHECK_FIELDS):
            raise ValueError(f"proposal booleans required: {position}")
        final = str(proposal.get("final_proposal") or "")
        if final not in FINAL_PROPOSALS:
            raise ValueError(f"invalid final proposal: {position}")
        type_decision = str(proposal.get("provider_type_decision") or "")
        if type_decision not in TYPE_DECISIONS:
            raise ValueError(f"invalid provider type decision: {position}")
        if final == "valid_candidate" and (
            not all(bool(proposal[field]) for field in CHECK_FIELDS)
            or type_decision == "conflict"
        ):
            raise ValueError(f"valid proposal has failed checks: {position}")
        if not str(proposal.get("proposal_reason") or "").strip():
            raise ValueError(f"proposal reason required: {position}")
        if not str(proposal.get("automation_rule") or "").strip():
            raise ValueError(f"automation rule required: {position}")
        ledger.append(
            {
                **source,
                **{field: proposal[field] for field in CHECK_FIELDS},
                "provider_type_decision": type_decision,
                "final_proposal": final,
                "proposal_reason": str(proposal["proposal_reason"]).strip(),
                "automation_rule": str(proposal["automation_rule"]).strip(),
                "schema": "gis_recommend.qgis_control_flow_if_proposal_replay.v1",
                "proposal_only": True,
                "human_adjudication": False,
                "review_status": "source_backed_proposal_replayed",
                "training_admission": "not_granted_rule_proposal_only",
                "training_row_emitted": False,
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
            }
        )

    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in ledger:
        grouped[row["automation_rule"]].append(row)
    rule_metrics = {
        rule: _metrics(rows) for rule, rows in sorted(grouped.items())
    }
    combined = _metrics(ledger)
    eligible_rules = [
        rule for rule, metrics in rule_metrics.items() if metrics["training_eligible"]
    ]
    summary = {
        "schema": "gis_recommend.qgis_control_flow_if_proposal_summary.v1",
        "replayed_rows": len(ledger),
        "source_authority_support": len(
            {row["source_authority_key"] for row in ledger}
        ),
        "proposal_counts": dict(
            sorted(Counter(row["final_proposal"] for row in ledger).items())
        ),
        "provider_type_decisions": dict(
            sorted(Counter(row["provider_type_decision"] for row in ledger).items())
        ),
        "combined_metrics": combined,
        "rule_metrics": rule_metrics,
        "eligible_rules": eligible_rules,
        "rule_training_eligible": bool(eligible_rules),
        "proposal_only": True,
        "human_adjudication": False,
        "training_admission": "not_granted_rule_proposal_only",
        "training_rows_emitted": 0,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }
    return ledger, summary


def _render_report(summary: dict[str, Any]) -> str:
    return (
        "# QGIS Conditional-Recovery Proposal Replay\n\n"
        "Source-backed proposal calibration only; no human adjudication or training admission.\n\n"
        f"- Source authorities: {summary['source_authority_support']}\n"
        f"- Proposal counts: `{json.dumps(summary['proposal_counts'], sort_keys=True)}`\n"
        f"- Combined precision: {summary['combined_metrics']['observed_precision']:.4f}\n"
        f"- Combined Wilson lower 95%: {summary['combined_metrics']['wilson_lower_95']:.4f}\n"
        f"- Eligible rules: `{json.dumps(summary['eligible_rules'])}`\n"
        "- Training rows emitted: 0\n"
    )


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--proposals", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    ledger, summary = apply_proposals(args.packet, args.proposals)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = args.output_dir / "proposal_replay_ledger.jsonl"
    summary_path = args.output_dir / "proposal_summary.json"
    report_path = args.output_dir / "proposal_report.md"
    hash_path = args.output_dir / "hash_manifest.json"
    ledger_path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
            for row in ledger
        ),
        encoding="utf-8",
    )
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    report_path.write_text(_render_report(summary), encoding="utf-8")
    hash_path.write_text(
        json.dumps(
            {
                "schema": "gis_recommend.qgis_control_flow_if_proposal_hashes.v1",
                "inputs": {
                    str(args.packet): _sha256(args.packet),
                    str(args.proposals): _sha256(args.proposals),
                },
                "outputs": {
                    ledger_path.name: _sha256(ledger_path),
                    summary_path.name: _sha256(summary_path),
                    report_path.name: _sha256(report_path),
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    return {
        "ledger": ledger_path,
        "summary": summary_path,
        "report": report_path,
        "hash": hash_path,
    }


if __name__ == "__main__":
    main()
