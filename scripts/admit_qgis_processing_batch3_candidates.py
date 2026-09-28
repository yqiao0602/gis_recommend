#!/usr/bin/env python3
"""Build an auditable admission/dedup ledger for Batch-3 Processing candidates.

This driver intentionally stops before train JSONL export.  It folds repeated
local units from the same normalized source body, records the four dedup keys,
checks overlap with the existing Processing pool, and emits a deterministic
source-disjoint audit manifest.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ALLOWED_RULES = {
    "recovery-connected-local-dag-v1",
    "recovery-multi-root-fanin-dag-v1",
    "split-local-structure-v9",
}


def _key(value: Any) -> str:
    raw = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _norm(value: Any) -> str:
    return "".join(str(value or "").lower().split())


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = ("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in value)
            if isinstance(value, list) else json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _keys(row: dict[str, Any]) -> dict[str, str]:
    calls = row.get("call_sites") or []
    operators = row.get("operator_ids") or []
    edges = row.get("dependency_edges") or []
    span = {"source_sha256": row.get("source_sha256"), "call_sites": calls}
    graph = {"source_sha256": row.get("source_sha256"), "operators": operators, "edges": edges, "call_sites": calls}
    dag = {
        "operators": operators,
        "l3": row.get("mapped_l3_chain") or [],
        "edges": edges,
        "scope": row.get("workflow_unit_scope"),
    }
    pair = {
        "task_name": _norm(row.get("task_name")),
        "task_description": _norm(row.get("task_description")),
        "l3": row.get("mapped_l3_chain") or [],
    }
    return {
        "source_region_key": _key(span),
        "call_graph_key": _key(graph),
        "normalized_dag_key": _key(dag),
        "training_pair_key": _key(pair),
    }


def _valid(row: dict[str, Any]) -> list[str]:
    reasons: list[str] = []
    if row.get("candidate_rule") not in ALLOWED_RULES:
        reasons.append("rule_not_calibrated")
    if row.get("description_fidelity_passed") is not True:
        reasons.append("description_fidelity_not_passed")
    if row.get("source_verification") not in (None, "verified_sha256"):
        reasons.append("source_sha256_not_verified")
    if not row.get("source_sha256") or not row.get("normalized_source_body_sha256"):
        reasons.append("source_identity_missing")
    operators = row.get("operator_ids") or []
    l3 = row.get("mapped_l3_chain") or []
    if not operators or len(operators) != len(l3):
        reasons.append("operator_l3_chain_incomplete")
    if not row.get("task_name") or not row.get("task_description"):
        reasons.append("task_text_missing")
    if row.get("workflow_unit_scope") != "local_subworkflow":
        reasons.append("workflow_scope_not_local_subworkflow")
    return reasons


def build_ledger(candidates: list[dict[str, Any]], existing: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    prepared: list[dict[str, Any]] = []
    for row in candidates:
        reasons = _valid(row)
        candidate_id = row.get("candidate_id") or _key(
            {
                "source_authority_key": row.get("source_authority_key"),
                "source_sha256": row.get("source_sha256"),
                "call_sites": row.get("call_sites") or [],
                "unit_id": row.get("unit_id"),
            }
        )
        prepared.append({**row, "candidate_id": candidate_id, **_keys(row), "admission_reasons": reasons})
    eligible = [r for r in prepared if not r["admission_reasons"]]
    # First authority fold: one representative per normalized source body.
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in eligible:
        groups[str(row["source_authority_key"])].append(row)
    authority_keep: dict[str, dict[str, Any]] = {}
    authority_suppressed: set[str] = set()
    for authority, rows in groups.items():
        winner = min(rows, key=lambda r: (-len(r.get("operator_ids") or []), str(r.get("candidate_id") or r.get("unit_id"))))
        authority_keep[authority] = winner
        authority_suppressed.update(str(r.get("candidate_id") or r.get("unit_id")) for r in rows if r is not winner)
    existing_pairs = {_existing_pair_key(row) for row in existing}
    existing_dags = {_existing_dag_key(row) for row in existing}
    seen_pairs: dict[str, dict[str, Any]] = {}
    seen_dags: dict[str, dict[str, Any]] = {}
    ledger: list[dict[str, Any]] = []
    for row in sorted(prepared, key=lambda r: str(r.get("candidate_id") or r.get("unit_id"))):
        cid = str(row.get("candidate_id") or row.get("unit_id"))
        decision = "canonical_keep"
        reason = "unique_candidate"
        if row["admission_reasons"]:
            decision, reason = "deferred", ";".join(row["admission_reasons"])
        elif cid in authority_suppressed or authority_keep.get(str(row["source_authority_key"])) is not row:
            decision, reason = "same_authority_suppressed", "same_normalized_source_authority"
        elif row["training_pair_key"] in seen_pairs:
            decision, reason = "exact_training_pair_suppressed", "duplicate_within_batch"
        elif row["training_pair_key"] in existing_pairs:
            decision, reason = "existing_training_pair_suppressed", "duplicate_with_existing_processing_pool"
        else:
            seen_pairs[row["training_pair_key"]] = row
            if row["normalized_dag_key"] in seen_dags or row["normalized_dag_key"] in existing_dags:
                reason = "normalized_dag_collision_review_required"
            else:
                seen_dags[row["normalized_dag_key"]] = row
        ledger.append({**row, "dedup_decision": decision, "dedup_reason": reason,
                       "training_admission": "not_granted_pending_source_disjoint_audit" if decision == "canonical_keep" else "not_granted_" + decision})
    canonical = [r for r in ledger if r["dedup_decision"] == "canonical_keep"]
    # Stratified, deterministic audit: calibration and holdout have disjoint bodies.
    audit: list[dict[str, Any]] = []
    for rule in sorted(ALLOWED_RULES):
        pool = [r for r in canonical if r.get("candidate_rule") == rule]
        pool.sort(key=lambda r: hashlib.sha256((str(r.get("source_sha256")) + rule).encode()).hexdigest())
        calibration = pool[: min(3, len(pool))]
        holdout = [r for r in pool[min(3, len(pool)):] if r.get("normalized_source_body_sha256") not in {x.get("normalized_source_body_sha256") for x in calibration}][:2]
        for split, rows in (("calibration", calibration), ("holdout", holdout)):
            for row in rows:
                audit.append({"audit_id": _key({"candidate_id": row.get("candidate_id"), "split": split}),
                              "candidate_id": row.get("candidate_id"), "candidate_rule": rule,
                              "split": split, "source_path": row.get("source_path"),
                              "source_sha256": row.get("source_sha256"),
                              "normalized_source_body_sha256": row.get("normalized_source_body_sha256"),
                              "operator_ids": row.get("operator_ids"), "mapped_l3_chain": row.get("mapped_l3_chain"),
                              "task_name": row.get("task_name"), "task_description": row.get("task_description"),
                              "audit_status": "pending_source_snippet_review", "training_admission": "not_granted"})
    summary = {
        "schema": "gis_recommend.qgis_processing_batch3_admission_summary.v1",
        "candidate_rows": len(candidates), "eligible_rows": len(eligible),
        "unique_source_authorities": len(groups), "authority_representatives": len(authority_keep),
        "canonical_rows_before_audit": len(canonical),
        "deferred_or_suppressed_rows": len(ledger) - len(canonical),
        "dedup_decision_counts": dict(Counter(r["dedup_decision"] for r in ledger)),
        "normalized_dag_collision_rows": sum(r["dedup_reason"] == "normalized_dag_collision_review_required" for r in canonical),
        "audit_rows": len(audit), "audit_source_body_overlap": len({r["normalized_source_body_sha256"] for r in audit if r["split"] == "calibration"} & {r["normalized_source_body_sha256"] for r in audit if r["split"] == "holdout"}),
        "training_rows_emitted": 0, "training_admission": "not_granted_pending_source_disjoint_audit",
        "validation_eligible": False, "test_eligible": False, "production_merge": "not_granted", "llm_called": False,
    }
    return ledger, summary, audit


def _existing_pair_key(row: dict[str, Any]) -> str:
    return _key({"task_name": _norm(row.get("task_name")), "task_description": _norm(row.get("task_description")), "l3": row.get("l3_code_sequence") or []})


def _existing_dag_key(row: dict[str, Any]) -> str:
    return _key({"operators": row.get("operator_sequence") or row.get("chain") or [], "l3": row.get("l3_code_sequence") or [], "edges": row.get("dependency_edges") or [], "scope": row.get("workflow_scope")})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--existing-pool", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    ledger, summary, audit = build_ledger(_read_jsonl(args.candidates), _read_jsonl(args.existing_pool))
    _write(args.output_dir / "candidate_admission_dedup_ledger_v1.jsonl", ledger)
    _write(args.output_dir / "canonical_candidates_pending_audit_v1.jsonl", [r for r in ledger if r["dedup_decision"] == "canonical_keep"])
    _write(args.output_dir / "source_disjoint_audit_manifest_v1.jsonl", audit)
    _write(args.output_dir / "summary_v1.json", summary)
    artifacts = [
        args.output_dir / "candidate_admission_dedup_ledger_v1.jsonl",
        args.output_dir / "canonical_candidates_pending_audit_v1.jsonl",
        args.output_dir / "source_disjoint_audit_manifest_v1.jsonl",
        args.output_dir / "summary_v1.json",
    ]
    _write(
        args.output_dir / "hash_ledger_v1.json",
        {
            "schema": "gis_recommend.hash_ledger.v1",
            "inputs": {
                "candidates": {"path": str(args.candidates), "sha256": _sha256(args.candidates)},
                "existing_pool": {"path": str(args.existing_pool), "sha256": _sha256(args.existing_pool)},
            },
            "artifacts": {path.name: {"bytes": path.stat().st_size, "sha256": _sha256(path)} for path in artifacts},
        },
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
