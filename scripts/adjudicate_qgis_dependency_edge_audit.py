#!/usr/bin/env python3
"""Freeze row-level dependency and boundary audit decisions for QGIS DAGs."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from pathlib import Path


def _read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _identity(row: dict) -> tuple[str, str]:
    return str(row.get("record_id", "")), str(row.get("source_sha256", ""))


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


def adjudicate(
    packet_path: Path,
    decisions_path: Path,
    *,
    additional_decisions_path: Path | None = None,
) -> tuple[list[dict], dict]:
    packet = _read_jsonl(packet_path)
    prior_decisions = _read_jsonl(decisions_path)
    additional_decisions = (
        _read_jsonl(additional_decisions_path)
        if additional_decisions_path is not None
        else []
    )
    packet_ids = [_identity(row) for row in packet]
    prior_ids = [_identity(row) for row in prior_decisions]
    additional_ids = [_identity(row) for row in additional_decisions]
    if len(packet_ids) != len(set(packet_ids)):
        raise ValueError("packet identities must be unique")
    if len(prior_ids) != len(set(prior_ids)):
        raise ValueError("decision identities must be unique")
    if len(additional_ids) != len(set(additional_ids)):
        raise ValueError("additional decision identities must be unique")
    overlap = sorted(set(prior_ids) & set(additional_ids))
    if overlap:
        raise ValueError(f"additional decisions duplicate prior decisions: {overlap}")
    packet_id_set = set(packet_ids)
    carried = [row for row in prior_decisions if _identity(row) in packet_id_set]
    if additional_decisions_path is None:
        decisions = prior_decisions
        extra = sorted(set(prior_ids) - packet_id_set)
    else:
        decisions = carried + additional_decisions
        extra = sorted(set(additional_ids) - packet_id_set)
    decision_ids = [_identity(row) for row in decisions]
    missing = sorted(packet_id_set - set(decision_ids))
    if missing:
        raise ValueError(f"missing decisions: {missing}")
    if extra:
        raise ValueError(f"decisions outside packet: {extra}")
    decisions_by_id = {_identity(row): row for row in decisions}

    ledger: list[dict] = []
    for packet_row in packet:
        evidence_edges = [
            [item.get("producer_index"), item.get("consumer_index")]
            for item in packet_row.get("dependency_edge_evidence", [])
        ]
        if evidence_edges != packet_row.get("dependency_edges", []):
            raise ValueError(f"packet dependency evidence mismatch: {_identity(packet_row)}")
        decision = decisions_by_id[_identity(packet_row)]
        boolean_fields = (
            "dependency_correct",
            "boundary_correct",
            "operator_order_correct",
        )
        if any(not isinstance(decision.get(field), bool) for field in boolean_fields):
            raise ValueError(f"decision booleans are required: {_identity(packet_row)}")
        final_decision = str(decision.get("final_decision", ""))
        if final_decision not in {"valid", "defer", "invalid"}:
            raise ValueError(f"invalid final_decision: {_identity(packet_row)}")
        if final_decision == "valid" and not all(
            bool(decision[field]) for field in boolean_fields
        ):
            raise ValueError(f"valid decision has a failed check: {_identity(packet_row)}")
        notes = str(decision.get("notes", "")).strip()
        if not notes:
            raise ValueError(f"decision notes are required: {_identity(packet_row)}")
        ledger.append(
            {
                "schema": "gis_recommend.qgis_dependency_edge_adjudication.v1",
                "review_position": packet_row.get("review_position"),
                "record_id": packet_row.get("record_id"),
                "source_sha256": packet_row.get("source_sha256"),
                "source_path": packet_row.get("source_path"),
                "signature_hash": packet_row.get("signature_hash"),
                "rule_id": packet_row.get("rule_id"),
                "feature_extractor_version": packet_row.get(
                    "feature_extractor_version"
                ),
                "operator_ids": packet_row.get("operator_ids", []),
                "dependency_edges": packet_row.get("dependency_edges", []),
                "dependency_edge_evidence": packet_row.get(
                    "dependency_edge_evidence", []
                ),
                "dependency_review_focus": packet_row.get(
                    "dependency_review_focus"
                ),
                **{field: decision[field] for field in boolean_fields},
                "final_decision": final_decision,
                "review_notes": notes,
                "training_admission": "not_granted_rule_calibration_only",
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
                "training_row_emitted": False,
            }
        )

    support = len(ledger)
    dependency_successes = sum(row["dependency_correct"] for row in ledger)
    structure_successes = sum(row["final_decision"] == "valid" for row in ledger)
    dependency_precision = dependency_successes / support if support else 0.0
    structure_precision = structure_successes / support if support else 0.0
    dependency_lower = _wilson_lower(dependency_successes, support)
    structure_lower = _wilson_lower(structure_successes, support)
    gate = lambda precision, lower: (
        support >= 30 and precision >= 0.95 and lower >= 0.80
    )
    summary = {
        "schema": "gis_recommend.qgis_dependency_edge_audit_summary.v1",
        "reviewed_support": support,
        "carried_decision_rows": len(carried),
        "dropped_prior_decision_rows": len(prior_decisions) - len(carried),
        "new_decision_rows": len(additional_decisions),
        "decision_counts": dict(
            sorted(Counter(row["final_decision"] for row in ledger).items())
        ),
        "dependency_correct_rows": dependency_successes,
        "dependency_precision": dependency_precision,
        "dependency_wilson_lower_95": dependency_lower,
        "dependency_extractor_gate_passed": gate(
            dependency_precision, dependency_lower
        ),
        "boundary_correct_rows": sum(row["boundary_correct"] for row in ledger),
        "operator_order_correct_rows": sum(
            row["operator_order_correct"] for row in ledger
        ),
        "structure_valid_rows": structure_successes,
        "structure_precision": structure_precision,
        "structure_wilson_lower_95": structure_lower,
        "direct_rule_training_eligible": gate(structure_precision, structure_lower),
        "training_rows_emitted": 0,
        "training_admission": "not_granted_rule_calibration_only",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "llm_called": False,
    }
    return ledger, summary


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--additional-decisions", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    rows, summary = adjudicate(
        args.packet,
        args.decisions,
        additional_decisions_path=args.additional_decisions,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = args.output_dir / "adjudication_ledger.jsonl"
    summary_path = args.output_dir / "adjudication_summary.json"
    report_path = args.output_dir / "adjudication_report.md"
    ledger_path.write_text(
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
    report_path.write_text(
        "\n".join(
            (
                "# QGIS dependency-edge audit",
                "",
                f"- reviewed: {summary['reviewed_support']}",
                f"- dependency precision: {summary['dependency_precision']:.4f}",
                f"- dependency Wilson lower 95%: {summary['dependency_wilson_lower_95']:.4f}",
                f"- structure precision: {summary['structure_precision']:.4f}",
                f"- structure Wilson lower 95%: {summary['structure_wilson_lower_95']:.4f}",
                f"- direct rule training eligible: {summary['direct_rule_training_eligible']}",
                "- training rows emitted: 0",
                "",
            )
        ),
        encoding="utf-8",
    )
    manifest_path = args.output_dir / "hash_manifest.json"
    manifest_path.write_text(
        json.dumps(
            {
                "schema": "gis_recommend.qgis_dependency_edge_adjudication_hashes.v1",
                "inputs": {
                    str(args.packet): _sha256(args.packet),
                    str(args.decisions): _sha256(args.decisions),
                    **(
                        {
                            str(args.additional_decisions): _sha256(
                                args.additional_decisions
                            )
                        }
                        if args.additional_decisions is not None
                        else {}
                    ),
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
        "manifest": manifest_path,
    }


if __name__ == "__main__":
    main()
