#!/usr/bin/env python3
"""Grant exact QGIS Processing rule signatures after source-disjoint review."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from gis_recommend.data.qgis_task_description import (
    DESCRIPTION_POLICY,
    audit_task_description,
    extract_literal_parameter_facts,
)
from gis_recommend.data.qgis_subworkflow_splitter import (
    literalize_processing_operator_ids,
)
from scripts.export_qgis_processing_reviewed_training import (
    PASS_FIELDS,
    RULE_SIGNATURE_FIELDS,
    _record_sha256,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rule_signature_hash(row: dict[str, Any]) -> str:
    payload = [str(row.get(field) or "") for field in RULE_SIGNATURE_FIELDS]
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _resolution_payload(facts: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "status": str(getattr(fact, "resolution_status", "resolved")),
            "reasons": list(getattr(fact, "resolution_reasons", [])),
        }
        for fact in facts
    ]


def _audit_review_row(row: dict[str, Any]) -> None:
    source_path = Path(str(row.get("source_path") or ""))
    if not source_path.is_file() or _sha256(source_path) != row.get("source_sha256"):
        raise ValueError(f"source verification failed: {row.get('candidate_id')}")
    if row.get("description_policy") != DESCRIPTION_POLICY:
        raise ValueError(f"description policy mismatch: {row.get('candidate_id')}")
    operators = list(row.get("operator_ids") or [])
    if not operators or not (
        len(operators)
        == len(row.get("mapped_l3_chain") or [])
        == len(row.get("call_sites") or [])
    ):
        raise ValueError(f"operator/L3/call alignment failed: {row.get('candidate_id')}")

    source_text = source_path.read_text(encoding="utf-8")
    if any(
        site.get("resolution_kind") == "dynamic" for site in row["call_sites"]
    ):
        source_text = literalize_processing_operator_ids(
            source_text,
            call_sites=row["call_sites"],
            require_full_coverage=False,
        )
    facts = extract_literal_parameter_facts(
        source_text, call_sites=row["call_sites"]
    )
    if [dict(fact) for fact in facts] != list(row.get("parameter_facts") or []):
        raise ValueError(f"parameter facts mismatch: {row.get('candidate_id')}")
    if _resolution_payload(facts) != list(row.get("frozen_parameter_resolution") or []):
        raise ValueError(f"parameter resolution mismatch: {row.get('candidate_id')}")

    audit = audit_task_description(row, row)
    if not audit["description_fidelity_passed"] or audit["description_fidelity_reasons"]:
        raise ValueError(f"description audit failed: {row.get('candidate_id')}")
    risk = row.get("local_risk_evidence") or {}
    for field in (
        "provider_input_type_conflicts",
        "unresolved_output_references",
        "unused_temporary_terminal_indices",
    ):
        if risk.get(field):
            raise ValueError(f"unresolved structural risk {field}: {row.get('candidate_id')}")


def build_signature_adjudication(
    *,
    review_rows: list[dict[str, Any]],
    candidate_rows: list[dict[str, Any]],
    approved_signatures: set[str],
    minimum_population: int,
    package_hashes: dict[str, str],
) -> dict[str, Any]:
    if minimum_population < 1 or not approved_signatures:
        raise ValueError("minimum population and approved signatures are required")

    calibration = [row for row in review_rows if row.get("review_split") == "calibration"]
    holdout = [row for row in review_rows if row.get("review_split") == "holdout"]
    for field in (
        "source_sha256",
        "source_authority_key",
        "normalized_source_body_sha256",
    ):
        if {str(row.get(field) or "") for row in calibration} & {
            str(row.get(field) or "") for row in holdout
        }:
            raise ValueError(f"source-disjoint overlap: {field}")

    for row in review_rows:
        signature = _rule_signature_hash(row)
        if row.get("review_rule_signature") != signature:
            raise ValueError(f"review signature mismatch: {row.get('candidate_id')}")
        _audit_review_row(row)

    population_counts = Counter(_rule_signature_hash(row) for row in candidate_rows)
    reviewed: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in review_rows:
        reviewed[str(row["review_rule_signature"])].append(row)

    signature_audit: dict[str, dict[str, Any]] = {}
    for signature in sorted(set(population_counts) | set(reviewed)):
        rows = reviewed.get(signature, [])
        canonical = [row for row in rows if row.get("dedup_status") == "canonical_candidate"]
        signature_audit[signature] = {
            "population_rows": population_counts[signature],
            "review_rows": len(rows),
            "review_splits": sorted({str(row.get("review_split") or "") for row in rows}),
            "canonical_review_rows": len(canonical),
            "canonical_review_splits": sorted(
                {str(row.get("review_split") or "") for row in canonical}
            ),
            "approved": signature in approved_signatures,
        }

    for signature in approved_signatures:
        audit = signature_audit.get(signature)
        if not audit:
            raise ValueError(f"approved signature is absent: {signature}")
        if audit["population_rows"] < minimum_population:
            raise ValueError(f"population support below gate: {signature}")
        if audit["canonical_review_splits"] != ["calibration", "holdout"]:
            raise ValueError(f"canonical dual-split coverage missing: {signature}")

    decisions = []
    for row in review_rows:
        if (
            row.get("dedup_status") != "canonical_candidate"
            or row.get("review_rule_signature") not in approved_signatures
        ):
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

    return {
        "schema": "gis_recommend.qgis_processing_adjudication.v1",
        **package_hashes,
        "reviewer_kind": "codex_agent",
        "review_basis": "source_replay_rule_signature_family_review",
        "review_scope": [
            "task_boundary",
            "operator_sequence",
            "stable120_l3_mapping",
            "description_fidelity",
            "parameter_provenance",
        ],
        "description_generation_llm_called": False,
        "minimum_population": minimum_population,
        "signature_audit": signature_audit,
        "decisions": decisions,
        "rule_authority": {
            "schema": "gis_recommend.qgis_processing_rule_authority.v1",
            "status": "granted_source_disjoint_zero_failure",
            "signature_fields": list(RULE_SIGNATURE_FIELDS),
            "approved_signatures": sorted(approved_signatures),
            "generalization_policy": "exact_signature_dual_split_support_gated_only",
            "unseen_signature_policy": "defer",
            "minimum_population": minimum_population,
            "source_authority_overlap": 0,
        },
    }


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _atomic_write(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-dir", type=Path, required=True)
    parser.add_argument("--approved-signature", action="append", required=True)
    parser.add_argument("--minimum-population", type=int, default=30)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    ledger_path = args.report_dir / "hash_ledger_v1.json"
    ledger = json.loads(ledger_path.read_text(encoding="utf-8"))
    for name, evidence in (ledger.get("artifacts") or {}).items():
        path = args.report_dir / name
        if not path.is_file() or _sha256(path) != evidence.get("sha256"):
            raise ValueError(f"package artifact SHA256 mismatch: {name}")
    candidate_path = args.report_dir / "candidate_batch_v1.jsonl"
    review_path = args.report_dir / "source_disjoint_review_v1.jsonl"
    adjudication = build_signature_adjudication(
        review_rows=_read_jsonl(review_path),
        candidate_rows=_read_jsonl(candidate_path),
        approved_signatures=set(args.approved_signature),
        minimum_population=args.minimum_population,
        package_hashes={
            "package_hash_ledger_sha256": _sha256(ledger_path),
            "candidate_batch_sha256": _sha256(candidate_path),
            "review_packet_sha256": _sha256(review_path),
        },
    )
    output = args.output or args.report_dir / "adjudication_v1.json"
    _atomic_write(output, adjudication)
    print(
        json.dumps(
            {
                "approved_signatures": sorted(set(args.approved_signature)),
                "decisions": len(adjudication["decisions"]),
                "review_rows": len(_read_jsonl(review_path)),
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )


if __name__ == "__main__":
    main()
