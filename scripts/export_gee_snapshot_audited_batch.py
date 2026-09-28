#!/usr/bin/env python3
"""Export a source-audited GEE snapshot batch through the existing hash-bound exporter.

The audit is deliberately fail-closed: only rows with verified source bytes, a
``pass`` decision, no critical failure, and six-dimensional fidelity ``pass``
are eligible.  The resulting package remains train-only and is not merged into
the cumulative authority by this command.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

import export_gee_complete_workflow_training_package as exporter  # noqa: E402


FIDELITY_FIELDS = (
    "human_dataset_fidelity",
    "human_temporal_fidelity",
    "human_spatial_fidelity",
    "human_transformation_fidelity",
    "human_output_fidelity",
    "human_task_text_fidelity",
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def canonical_jsonl(rows: list[dict[str, Any]]) -> bytes:
    return b"".join(
        (json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode(
            "utf-8"
        )
        for row in rows
    )


def main(argv: list[str] | None = None) -> dict[str, Any]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--risk-packet", type=Path, required=True)
    parser.add_argument("--fact-bundles", type=Path, required=True)
    parser.add_argument("--task-text-candidates", type=Path, required=True)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    output = args.output_dir.resolve()
    authority = output / "authority"
    authority.mkdir(parents=True, exist_ok=True)

    audit_rows = jsonl(args.audit)
    if not audit_rows:
        raise ValueError("audit package is empty")
    eligible: dict[tuple[str, str], dict[str, Any]] = {}
    for row in audit_rows:
        key = (str(row.get("source_sha256") or ""), str(row.get("workflow_id") or ""))
        if key in eligible:
            raise ValueError(f"duplicate audit identity: {key}")
        if row.get("human_decision") != "pass":
            raise ValueError(f"audit decision is not pass: {key}")
        if row.get("human_critical_failure") != "no":
            raise ValueError(f"audit critical failure is not no: {key}")
        if row.get("source_sha256_verified") is not True:
            raise ValueError(f"source SHA was not verified: {key}")
        if any(row.get(field) != "pass" for field in FIDELITY_FIELDS):
            raise ValueError(f"six-dimensional fidelity is not all pass: {key}")
        eligible[key] = row

    source_risk = jsonl(args.risk_packet)
    risk = []
    for row in source_risk:
        key = (str(row.get("source_sha256") or ""), str(row.get("workflow_id") or ""))
        if key in eligible:
            risk.append(row)
    if len(risk) != len(eligible):
        raise ValueError(f"audit/risk identity mismatch: audit={len(eligible)} risk={len(risk)}")
    risk_path = authority / "risk_packet_audited.jsonl"
    risk_path.write_bytes(canonical_jsonl(sorted(risk, key=lambda r: (r["source_sha256"], r["workflow_id"]))))

    review_path = args.audit.resolve()
    ledger = {
        "schema": exporter.ADJUDICATION_LEDGER_SCHEMA,
        "ledger_id": "gee_batch12_v8_9_9_snapshot_authority_exhaustive_41",
        "review_report_path": str(review_path),
        "review_report_sha256": sha256(review_path),
        "risk_packet_sha256": sha256(risk_path),
        "default_decision": "pass",
        "expected_counts": {
            "rows": len(risk),
            "pass": len(risk),
            "defer_source_ambiguity": 0,
        },
        "exceptions": [],
    }
    ledger_path = authority / "adjudication_ledger.json"
    ledger_path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    # Derive the frozen package counts from the joined deterministic records
    # before constructing the profile; the exporter then enforces these counts.
    risk_index = exporter._index(risk, "risk packet")
    fact_index = exporter._index(jsonl(args.fact_bundles), "fact bundle")
    text_index = exporter._index(jsonl(args.task_text_candidates), "task text")
    mapping = json.loads(args.mapping.read_text(encoding="utf-8"))
    l3_to_id = exporter.validate_stable_94_mapping(mapping.get("l3") or {})
    dedup_keys: set[tuple[str, str, tuple[str, ...]]] = set()
    semantic = []
    for key, audit in sorted(eligible.items()):
        if key not in fact_index or key not in text_index:
            continue
        fact = fact_index[key]
        text = text_index[key]
        exporter._validate_joined_authorities(
            key=key, risk=risk_index[key], fact=fact, text=text,
            adjudication={
                "source_sha256": key[0],
                "source_path": risk_index[key]["source_path"],
                "workflow_id": key[1],
                "workflow_key": [key[0], key[1]],
                "adjudication_row_sha256": "0" * 64,
            },
        )
        row = exporter._semantic_row(
            fact,
            text,
            {
                "source_sha256": key[0],
                "source_path": risk_index[key]["source_path"],
                "workflow_id": key[1],
                "workflow_key": [key[0], key[1]],
                "adjudication_row_sha256": "0" * 64,
            },
        )
        dedup_key = (
            exporter._normalized_text(row["task_name"]),
            exporter._normalized_text(row["task_description"]),
            tuple(row["l3_sequence"]),
        )
        if dedup_key not in dedup_keys:
            dedup_keys.add(dedup_key)
            semantic.append(row)
    loader = [exporter._loader_row(row, l3_to_id) for row in semantic]
    v4 = [row for row in loader if row["sequence_fit"]["fits_v4_100"]]
    counts = {
        "adjudication_rows": len(risk),
        "adjudication_pass": len(risk),
        "adjudication_defer": 0,
        "semantic_train_rows": len(semantic),
        "v4_100_rows": len(v4),
        "length_sidecar_rows": len(loader) - len(v4),
        "fail_closed_rows": 0,
        "duplicate_rows": len(eligible) - len(semantic),
    }
    profile = exporter.FrozenAuthorityProfile(
        name="gee_batch12_v8_9_9_snapshot_authority_exhaustive_41",
        risk_packet_sha256=sha256(risk_path),
        fact_bundles_sha256=sha256(args.fact_bundles),
        task_text_candidates_sha256=sha256(args.task_text_candidates),
        review_report_sha256=sha256(review_path),
        mapping_sha256=sha256(args.mapping),
        adjudication_ledger_sha256=sha256(ledger_path),
        expected_package_counts={
            "adjudication_rows": len(risk),
            "adjudication_pass": len(risk),
            "adjudication_defer": 0,
            **counts,
        },
    )
    result = exporter.build_training_package(
        risk_packet_path=risk_path,
        fact_bundles_path=args.fact_bundles,
        task_text_candidates_path=args.task_text_candidates,
        adjudication_ledger_path=ledger_path,
        review_report_path=review_path,
        id_mappings_path=args.mapping,
        profile=profile,
    )
    ledger_out = exporter.write_outputs(
        result,
        output_dir=output,
        authority_paths={
            "audit": review_path,
            "risk_packet": risk_path,
            "fact_bundles": args.fact_bundles,
            "task_text_candidates": args.task_text_candidates,
            "adjudication_ledger": ledger_path,
            "id_mappings": args.mapping,
        },
    )
    payload = {"summary": result.summary, "hash_ledger": ledger_out}
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return payload


if __name__ == "__main__":
    main()
