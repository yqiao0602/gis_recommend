#!/usr/bin/env python3
"""Re-audit QGIS direct descriptions against the frozen routing manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

from gis_recommend.data.qgis_task_description import audit_task_description


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = (
    ROOT
    / "docs/reports/qgis_mapping_high_impact_blockers_2026-07-24"
    / "stable101_all1442_source_replay_v1/routing_v2/routing_manifest.jsonl"
)
DEFAULT_CANDIDATES = (
    ROOT / "docs/reports/qgis_direct_description_v1/direct_description_candidates_v1.jsonl"
)
DEFAULT_OUTPUT_DIR = ROOT / "docs/reports/qgis_direct_description_v1/fidelity_audit_v1"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _index_unique(rows: list[dict[str, Any]], field: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row.get(field) or "")
        if not key or key in result:
            raise ValueError(f"missing or duplicate {field}: {key!r}")
        result[key] = row
    return result


def audit_candidates(
    manifest_rows: list[dict[str, Any]], candidate_rows: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    direct = _index_unique(
        [row for row in manifest_rows if row.get("action") == "auto_accept_candidate"],
        "record_id",
    )
    candidates = _index_unique(candidate_rows, "record_id")
    if set(direct) != set(candidates):
        raise ValueError(
            "candidate coverage mismatch: "
            f"missing={sorted(set(direct) - set(candidates))}, "
            f"extra={sorted(set(candidates) - set(direct))}"
        )

    ledger: list[dict[str, Any]] = []
    for record_id, source in direct.items():
        candidate = candidates[record_id]
        audit_input = dict(source)
        audit_input["parameter_facts"] = candidate.get("parameter_facts") or []
        audit = audit_task_description(audit_input, candidate)
        reasons = list(audit["description_fidelity_reasons"])
        if candidate.get("source_sha256") != source.get("source_sha256"):
            reasons.append("source_identity_mismatch")
        if candidate.get("rule_id") != "direct-explicit-dag-v1":
            reasons.append("unexpected_structure_rule")
        if candidate.get("legacy_task_text_used") is not False:
            reasons.append("legacy_task_text_usage_not_denied")
        if candidate.get("task_description") == source.get("task_text"):
            reasons.append("legacy_task_text_copied")
        passed = not reasons
        ledger.append(
            {
                "schema": "gis_recommend.qgis_direct_description_fidelity_audit.v1",
                "record_id": record_id,
                "source_sha256": source["source_sha256"],
                "signature_hash": source["signature_hash"],
                "workflow_unit_scope": source["workflow_unit_scope"],
                "operator_ids": source["operator_ids"],
                "dependency_edges": source["dependency_edges"],
                "mapped_l3_chain": source["mapped_l3_chain"],
                "task_name": candidate.get("task_name", ""),
                "task_description": candidate.get("task_description", ""),
                "description_fidelity_passed": passed,
                "description_fidelity_reasons": reasons,
                "training_admission": (
                    "not_granted_pending_dedup_and_export_gate"
                    if passed
                    else "not_granted_description_fidelity_failed"
                ),
                "training_row_emitted": False,
                "validation_eligible": False,
                "test_eligible": False,
            }
        )

    status = Counter(row["description_fidelity_passed"] for row in ledger)
    summary = {
        "schema": "gis_recommend.qgis_direct_description_fidelity_audit_summary.v1",
        "rows": len(ledger),
        "passed": status[True],
        "deferred": status[False],
        "training_rows_emitted": 0,
        "llm_called": False,
        "training_admission": "not_granted_pending_dedup_and_export_gate",
        "next_gate": "four_layer_deduplication_then_train_only_export",
    }
    return ledger, summary


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def write_outputs(
    ledger: list[dict[str, Any]],
    summary: dict[str, Any],
    *,
    manifest: Path,
    candidates: Path,
    output_dir: Path,
) -> dict[str, Path]:
    ledger_path = output_dir / "fidelity_ledger_v1.jsonl"
    summary_path = output_dir / "fidelity_summary_v1.json"
    hash_path = output_dir / "fidelity_hashes_v1.json"
    _atomic_write(
        ledger_path,
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for row in ledger
        ),
    )
    _atomic_write(summary_path, json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    hashes = {
        "schema": "gis_recommend.hash_ledger.v1",
        "source_inputs": {
            manifest.name: {"path": str(manifest), "sha256": _sha256(manifest)},
            candidates.name: {"path": str(candidates), "sha256": _sha256(candidates)},
        },
        "artifacts": {
            path.name: {"path": str(path), "sha256": _sha256(path), "bytes": path.stat().st_size}
            for path in (ledger_path, summary_path)
        },
    }
    _atomic_write(hash_path, json.dumps(hashes, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return {"ledger": ledger_path, "summary": summary_path, "hash_ledger": hash_path}


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)
    ledger, summary = audit_candidates(_load_jsonl(args.manifest), _load_jsonl(args.candidates))
    return write_outputs(
        ledger,
        summary,
        manifest=args.manifest,
        candidates=args.candidates,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    main()
