#!/usr/bin/env python3
"""Export the 12 canonical stable124-unlock candidates as an isolated
train-only package, then run the real V4 loader/loss/backward smoke.

No authority file is modified, nothing is trained, and production merge stays
not_granted.  The package mirrors the existing qgis_processing_aggregate row
schema so it can be merged later only by an explicit authority decision.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

SCHEMA = "gis_recommend.qgis_stable124_unlock_train_only.v1"
START_TOKEN, END_TOKEN = -3, -4


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _training_row(candidate: dict[str, Any], token_id: dict[str, int]) -> dict[str, Any]:
    operators = list(candidate.get("operator_ids") or [])
    l3_codes = list(candidate.get("frozen_l3_chain") or [])
    l3_tokens = [token_id[code] for code in l3_codes if code in token_id]
    if len(l3_tokens) != len(l3_codes):
        raise ValueError(f"missing token for L3 chain: {candidate.get('candidate_id')}")
    l3_sequence = [START_TOKEN, *l3_tokens, END_TOKEN]
    sample_id = f"qgis_stable124_unlock_{candidate.get('candidate_id', '')[-16:]}"
    return {
        "sample_id": sample_id,
        "candidate_id": candidate.get("candidate_id"),
        "record_id": candidate.get("record_id"),
        "source_sha256": candidate.get("source_sha256"),
        "source_path": candidate.get("source_path"),
        "source_root_id": candidate.get("source_root_id"),
        "source_authority_key": candidate.get("source_authority_key"),
        "source_authority_basis": candidate.get("source_authority_basis"),
        "source_verification": "verified_sha256",
        "task_name": candidate.get("task_name") or "QGIS验证Processing工作流",
        "task_description": candidate.get("task_description"),
        "task_type": "QGIS验证Processing工作流",
        "task_metadata": {
            "task_name": candidate.get("task_name") or "QGIS验证Processing工作流",
            "task_description": candidate.get("task_description"),
            "task_type": "QGIS验证Processing工作流",
        },
        "qgis_operator_chain": operators,
        "operator_sequence": operators,
        "l3_code_sequence": l3_codes,
        "l3_codes": [f"<START>", *l3_codes, "<END>"],
        "l3_sequence": l3_sequence,
        "l3_token_ids": l3_tokens,
        "n": len(operators),
        "workflow_scope": candidate.get("workflow_unit_scope") or "local_subworkflow",
        "workflow_unit_scope": candidate.get("workflow_unit_scope") or "local_subworkflow",
        "candidate_lane": candidate.get("candidate_lane"),
        "mapping_authority": "stable124_composed_v1",
        "mapping_complete": True,
        "recovery_method": candidate.get("rule_id") or candidate.get("structure_rule_id"),
        "dependency_edges": candidate.get("dependency_edges") or [],
        "call_sites": candidate.get("call_sites") or [],
        "source_span": {"call_sites": candidate.get("call_sites") or []},
        "evidence_snippet": (candidate.get("source_snippet") or "")[:2000],
        "parameter_facts": candidate.get("parameter_facts") or [{} for _ in operators],
        "frozen_parameter_facts": candidate.get("frozen_parameter_facts") or [],
        "frozen_parameter_resolution": candidate.get("frozen_parameter_resolution") or [],
        "normalized_dag_key": candidate.get("dedup_normalized_dag_key"),
        "call_graph_key": candidate.get("dedup_call_graph_key"),
        "source_region_key": candidate.get("dedup_source_region_key"),
        "unified_training_pair_key": candidate.get("dedup_training_pair_key"),
        "known_omissions": candidate.get("known_omissions") or [],
        "schema_version": "gis_recommend.qgis_train_only_row.v4_128",
        "training_admission": "granted_train_only_qgis_stable124_unlock_v1",
        "source_training_admission": "granted_train_only_qgis_stable124_unlock_v1",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "training_row_emitted": True,
        "llm_called": False,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--extension", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    extension = json.loads(args.extension.read_text(encoding="utf-8"))
    token_id = {**extension["existing_code_to_id"], **extension["proposed_code_to_id_additions"]}
    candidates = [
        json.loads(line)
        for line in args.candidates.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    canonical = [row for row in candidates if row.get("dedup_status") == "canonical_candidate"]
    if len(canonical) != 12:
        raise ValueError(f"expected 12 canonical candidates, got {len(canonical)}")
    rows = [_training_row(row, token_id) for row in canonical]

    args.output_dir.mkdir(parents=True, exist_ok=True)
    package = args.output_dir / "qgis_stable124_unlock_train_only_v1.jsonl"
    package.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    summary = {
        "schema": SCHEMA,
        "rows": len(rows),
        "source_sha256_unique": len({row["source_sha256"] for row in rows}),
        "unique_l3_sequences": len({tuple(row["l3_code_sequence"]) for row in rows}),
        "unique_operator_sequences": len({tuple(row["operator_sequence"]) for row in rows}),
        "lanes": sorted({row["candidate_lane"] for row in rows}),
        "package_sha256": _sha256(package),
        "training_admission": "granted_train_only_qgis_stable124_unlock_v1",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "training_run": False,
    }
    (args.output_dir / "summary_v1.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (args.output_dir / "hash_ledger_v1.json").write_text(
        json.dumps(
            {
                "schema": "gis_recommend.hash_ledger.v1",
                "inputs": {
                    "candidates": _sha256(args.candidates),
                    "extension": _sha256(args.extension),
                },
                "artifacts": {
                    package.name: _sha256(package),
                    "summary_v1.json": _sha256(args.output_dir / "summary_v1.json"),
                },
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
