#!/usr/bin/env python3
"""Expand reviewed QGIS structural signatures into a row-level audit ledger."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path


def _read_jsonl(path: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _wilson_lower(successes: int, total: int, z: float = 1.96) -> float:
    if not total:
        return 0.0
    p = successes / total
    denominator = 1 + z * z / total
    centre = p + z * z / (2 * total)
    margin = z * math.sqrt((p * (1 - p) + z * z / (4 * total)) / total)
    return (centre - margin) / denominator


def adjudicate(
    packet_path: Path, decisions_path: Path, config_path: Path
) -> tuple[list[dict], dict]:
    packet = _read_jsonl(packet_path)
    decisions_document = json.loads(decisions_path.read_text(encoding="utf-8"))
    config = json.loads(config_path.read_text(encoding="utf-8"))
    rule_id = str(decisions_document.get("rule_id", ""))
    if not rule_id or any(str(row.get("rule_id", "")) != rule_id for row in packet):
        raise ValueError("packet and signature decisions must use one matching rule_id")

    identities = [
        (str(row.get("record_id", "")), str(row.get("source_sha256", "")))
        for row in packet
    ]
    if len(identities) != len(set(identities)):
        raise ValueError("packet record/source identities must be unique")

    signature_decisions: dict[str, dict] = {}
    for decision in decisions_document.get("signatures", []):
        signature_hash = str(decision.get("signature_hash", ""))
        if not signature_hash or signature_hash in signature_decisions:
            raise ValueError(f"duplicate or blank signature decision: {signature_hash!r}")
        if not isinstance(decision.get("structure_valid"), bool):
            raise ValueError(f"structure_valid must be boolean for {signature_hash}")
        signature_decisions[signature_hash] = decision

    packet_signatures = {str(row.get("signature_hash", "")) for row in packet}
    missing = sorted(packet_signatures - set(signature_decisions))
    extra = sorted(set(signature_decisions) - packet_signatures)
    if missing:
        raise ValueError(f"missing signature decisions: {missing}")
    if extra:
        raise ValueError(f"decisions contain signatures outside packet: {extra}")

    rows: list[dict] = []
    for packet_row in packet:
        decision = signature_decisions[str(packet_row["signature_hash"])]
        rows.append(
            {
                "schema": "gis_recommend.qgis_rule_structure_adjudication.v1",
                "review_position": packet_row.get("review_position"),
                "record_id": packet_row.get("record_id"),
                "source_sha256": packet_row.get("source_sha256"),
                "signature_hash": packet_row.get("signature_hash"),
                "rule_id": rule_id,
                "operator_ids": packet_row.get("operator_ids", []),
                "dependency_edges": packet_row.get("dependency_edges", []),
                "workflow_unit_scope": packet_row.get("workflow_unit_scope", "unknown"),
                "structure_valid": decision["structure_valid"],
                "review_basis": decision.get("review_basis", ""),
                "review_notes": decision.get("notes", ""),
                "task_text_admission": "not_granted_pending_description_fidelity",
                "training_admission": "not_granted_pending_description_fidelity",
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
                "training_row_emitted": False,
            }
        )

    support = len(rows)
    successes = sum(bool(row["structure_valid"]) for row in rows)
    precision = successes / support if support else 0.0
    wilson_lower = _wilson_lower(successes, support)
    gate = config["auto_accept_gate"]
    eligible = (
        precision >= float(gate["minimum_observed_precision"])
        and support >= int(gate["minimum_reviewed_support"])
        and wilson_lower >= float(gate["minimum_wilson_lower_bound"])
    )
    summary = {
        "schema": "gis_recommend.qgis_rule_structure_audit_summary.v1",
        "rule_id": rule_id,
        "reviewed_support": support,
        "unique_reviewed_signatures": len(packet_signatures),
        "structure_valid_rows": successes,
        "structure_invalid_rows": support - successes,
        "observed_structure_precision": precision,
        "wilson_lower_95": wilson_lower,
        "structure_auto_accept_eligible": eligible,
        "task_text_rows_admitted": 0,
        "training_rows_emitted": 0,
        "training_admission": "not_granted_pending_description_fidelity",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }
    return rows, summary


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--signature-decisions", type=Path, required=True)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    rows, summary = adjudicate(args.packet, args.signature_decisions, args.config)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = args.output_dir / "structure_adjudications_v1.jsonl"
    summary_path = args.output_dir / "structure_audit_summary_v1.json"
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
    return {"ledger": ledger_path, "summary": summary_path}


if __name__ == "__main__":
    main()
