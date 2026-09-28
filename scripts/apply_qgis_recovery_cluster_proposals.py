#!/usr/bin/env python3
"""Replay source-backed cluster proposals over the recovery census."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from gis_recommend.data.qgis_source_authority import source_authority


CHECK_FIELDS = (
    "dependency_correct",
    "operator_order_correct",
    "boundary_correct",
    "fanin_semantics_correct",
    "provider_types_compatible",
    "description_faithful",
)
FINAL_PROPOSALS = {"valid", "defer", "reject_current_recovery"}


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


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


def _source_authority(row: dict[str, Any]) -> dict[str, str]:
    path = Path(str(row.get("source_path") or ""))
    return source_authority(
        path, source_sha256=str(row.get("source_sha256") or "")
    )


def _metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        grouped[str(row["source_authority_key"])].append(row)
    support = len(grouped)
    group_decisions: list[str] = []
    for group_rows in grouped.values():
        decisions = {row["final_proposal"] for row in group_rows}
        if "reject_current_recovery" in decisions:
            group_decisions.append("reject_current_recovery")
        elif "defer" in decisions:
            group_decisions.append("defer")
        else:
            group_decisions.append("valid")
    valid = sum(decision == "valid" for decision in group_decisions)
    precision = valid / support if support else 0.0
    lower = _wilson_lower(valid, support)
    return {
        "raw_row_support": len(rows),
        "support": support,
        "valid": valid,
        "defer": sum(decision == "defer" for decision in group_decisions),
        "reject_current_recovery": sum(
            decision == "reject_current_recovery" for decision in group_decisions
        ),
        "observed_precision": precision,
        "wilson_lower_95": lower,
        "training_eligible": (
            support >= 30 and precision >= 0.95 and lower >= 0.80
        ),
    }


def apply_cluster_proposals(
    packet_path: Path, proposals_path: Path
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    packet = _load_jsonl(packet_path)
    proposals = _load_jsonl(proposals_path)
    packet_clusters = {str(row.get("normalized_dag_key") or "") for row in packet}
    if "" in packet_clusters:
        raise ValueError("packet rows require normalized_dag_key")
    proposal_keys = [str(row.get("normalized_dag_key") or "") for row in proposals]
    if not all(proposal_keys) or len(proposal_keys) != len(set(proposal_keys)):
        raise ValueError("cluster proposal keys must be non-empty and unique")
    missing = sorted(packet_clusters - set(proposal_keys))
    extra = sorted(set(proposal_keys) - packet_clusters)
    if missing:
        raise ValueError(f"missing cluster proposals: {missing}")
    if extra:
        raise ValueError(f"proposals outside packet: {extra}")

    by_cluster: dict[str, dict[str, Any]] = {}
    for proposal in proposals:
        key = str(proposal["normalized_dag_key"])
        if any(not isinstance(proposal.get(field), bool) for field in CHECK_FIELDS):
            raise ValueError(f"proposal booleans required for {key}")
        final = str(proposal.get("final_proposal") or "")
        if final not in FINAL_PROPOSALS:
            raise ValueError(f"invalid final proposal for {key}: {final}")
        if final == "valid" and not all(bool(proposal[field]) for field in CHECK_FIELDS):
            raise ValueError(f"valid proposal has failed checks for {key}")
        if not str(proposal.get("notes") or "").strip():
            raise ValueError(f"proposal notes required for {key}")
        if not str(proposal.get("automation_rule") or "").strip():
            raise ValueError(f"automation rule required for {key}")
        by_cluster[key] = proposal

    ledger: list[dict[str, Any]] = []
    for source in packet:
        proposal = by_cluster[str(source["normalized_dag_key"])]
        authority = _source_authority(source)
        ledger.append(
            {
                **source,
                **authority,
                "schema": "gis_recommend.qgis_recovery_cluster_proposal_replay.v1",
                **{field: proposal[field] for field in CHECK_FIELDS},
                "final_proposal": proposal["final_proposal"],
                "proposal_notes": str(proposal["notes"]).strip(),
                "automation_rule": str(proposal["automation_rule"]).strip(),
                "proposal_only": True,
                "human_adjudication": False,
                "review_status": "cluster_proposal_replayed_not_human_adjudication",
                "training_admission": "not_granted_recovery_cluster_proposal_only",
                "training_row_emitted": False,
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
            }
        )

    by_rule: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in ledger:
        by_rule[str(row.get("recovery_rule_id") or "unknown")].append(row)
    rule_metrics = {
        rule_id: _metrics(rows) for rule_id, rows in sorted(by_rule.items())
    }
    combined = _metrics(ledger)
    summary = {
        "schema": "gis_recommend.qgis_recovery_cluster_proposal_summary.v1",
        "reviewed_clusters": len(proposals),
        "replayed_rows": len(ledger),
        "raw_file_sha_support": len(
            {str(row.get("source_sha256") or "") for row in ledger}
        ),
        "source_disjoint_support": len(
            {str(row["source_authority_key"]) for row in ledger}
        ),
        "cluster_proposal_counts": dict(
            sorted(Counter(row["final_proposal"] for row in proposals).items())
        ),
        "row_proposal_counts": dict(
            sorted(Counter(row["final_proposal"] for row in ledger).items())
        ),
        "rule_metrics": rule_metrics,
        "combined_metrics": combined,
        "eligible_rule_ids": [
            rule_id
            for rule_id, metrics in rule_metrics.items()
            if metrics["training_eligible"]
        ],
        "rule_training_eligible": combined["training_eligible"],
        "proposal_only": True,
        "human_adjudication": False,
        "training_rows_emitted": 0,
        "training_admission": "not_granted_recovery_cluster_proposal_only",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "llm_called": False,
    }
    return ledger, summary


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _render_report(summary: dict[str, Any]) -> str:
    lines = [
        "# QGIS Recovery Cluster Proposal Replay",
        "",
        "This is a source-backed cluster proposal, not human adjudication and not training admission.",
        "",
        f"- Reviewed clusters: {summary['reviewed_clusters']}",
        f"- Replayed rows: {summary['replayed_rows']}",
        f"- Raw file SHA support: {summary['raw_file_sha_support']}",
        f"- Unique source authorities: {summary['source_disjoint_support']}",
        f"- Row proposals: `{json.dumps(summary['row_proposal_counts'], sort_keys=True)}`",
        f"- Combined observed precision: {summary['combined_metrics']['observed_precision']:.4f}",
        f"- Combined Wilson lower 95%: {summary['combined_metrics']['wilson_lower_95']:.4f}",
        f"- Rule training eligible: `{str(summary['rule_training_eligible']).lower()}`",
        "- Training rows emitted: `0`",
        "- Validation/test/production merge: `not_granted`",
        "",
        "## Rule Metrics",
        "",
        "| Rule | Support | Valid | Defer | Reject current | Precision | Wilson lower 95% | Eligible |",
        "|---|---:|---:|---:|---:|---:|---:|---|",
    ]
    for rule_id, metrics in summary["rule_metrics"].items():
        lines.append(
            "| "
            + " | ".join(
                [
                    rule_id,
                    str(metrics["support"]),
                    str(metrics["valid"]),
                    str(metrics["defer"]),
                    str(metrics["reject_current_recovery"]),
                    f"{metrics['observed_precision']:.4f}",
                    f"{metrics['wilson_lower_95']:.4f}",
                    str(metrics["training_eligible"]).lower(),
                ]
            )
            + " |"
        )
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--proposals", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    ledger, summary = apply_cluster_proposals(args.packet, args.proposals)
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
                "schema": "gis_recommend.qgis_recovery_cluster_proposal_hashes.v1",
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
