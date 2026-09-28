#!/usr/bin/env python3
"""Create deterministic task-description candidates for direct QGIS DAGs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

from gis_recommend.data.qgis_task_description import (
    DESCRIPTION_POLICY,
    audit_task_description,
    build_task_description,
    extract_literal_parameter_facts,
)


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = (
    ROOT
    / "docs/reports/qgis_mapping_high_impact_blockers_2026-07-24"
    / "stable101_all1442_source_replay_v1/routing_v2/routing_manifest.jsonl"
)
# Keep generated artifact paths below Windows' legacy path-length limit.
DEFAULT_OUTPUT_DIR = ROOT / "docs/reports/qgis_direct_description_v1"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def build_candidates(manifest_rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    direct_rows = [row for row in manifest_rows if row.get("action") == "auto_accept_candidate"]
    candidates: list[dict[str, Any]] = []
    for source in direct_rows:
        description_input = dict(source)
        source_path = Path(str(source.get("source_path") or ""))
        if not source_path.is_file():
            parameter_evidence_status = "source_file_missing"
            parameter_facts = [{} for _ in source.get("call_sites") or []]
        elif _sha256(source_path) != source.get("source_sha256"):
            parameter_evidence_status = "source_sha256_mismatch"
            parameter_facts = [{} for _ in source.get("call_sites") or []]
        else:
            parameter_evidence_status = "verified_source_ast"
            parameter_facts = extract_literal_parameter_facts(
                source_path.read_text(encoding="utf-8"),
                call_sites=source.get("call_sites") or [],
            )
        description_input["parameter_facts"] = parameter_facts
        generated = build_task_description(description_input)
        audit = audit_task_description(description_input, generated)
        passed = bool(audit["description_fidelity_passed"])
        candidate = dict(source)
        candidate.update(generated)
        candidate.update(audit)
        candidate.update(
            {
                "schema": "gis_recommend.qgis_direct_description_candidate.v1",
                "description_source": "frozen_operator_dag_only",
                "parameter_facts": parameter_facts,
                "parameter_evidence_status": parameter_evidence_status,
                "parameterized_step_count": sum(bool(value) for value in parameter_facts),
                "legacy_task_text_used": False,
                "task_text_admission": (
                    "granted_deterministic_fidelity_gate"
                    if passed
                    else "not_granted_pending_description_rewrite"
                ),
                "training_admission": (
                    "not_granted_pending_dedup_and_export_gate"
                    if passed
                    else "not_granted_description_fidelity_failed"
                ),
                "training_row_emitted": False,
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
            }
        )
        candidates.append(candidate)

    status = Counter(row["description_fidelity_status"] for row in candidates)
    audit_status = Counter(bool(row["description_fidelity_passed"]) for row in candidates)
    scope = Counter(str(row["workflow_unit_scope"]) for row in candidates)
    evidence_status = Counter(str(row["parameter_evidence_status"]) for row in candidates)
    summary = {
        "schema": "gis_recommend.qgis_direct_description_summary.v1",
        "input_rows": len(manifest_rows),
        "direct_rows": len(candidates),
        "description_policy": DESCRIPTION_POLICY,
        "description_status_counts": dict(sorted(status.items())),
        "fidelity_gate": {
            "passed": audit_status[True],
            "deferred": audit_status[False],
        },
        "scope_counts": dict(sorted(scope.items())),
        "parameter_evidence_status_counts": dict(sorted(evidence_status.items())),
        "rows_with_literal_parameter_facts": sum(
            int(row["parameterized_step_count"]) > 0 for row in candidates
        ),
        "parameterized_steps": sum(int(row["parameterized_step_count"]) for row in candidates),
        "decision": {
            "llm_called": False,
            "legacy_task_text_used": False,
            "training_rows_emitted": 0,
            "training_admission": "not_granted_pending_dedup_and_export_gate",
            "next_gate": "four_layer_deduplication_then_train_only_export",
        },
    }
    return candidates, summary


def _atomic_write(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding=encoding, newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def _csv_value(value: Any) -> Any:
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def write_outputs(
    candidates: list[dict[str, Any]], summary: dict[str, Any], *, manifest: Path, output_dir: Path
) -> dict[str, Path]:
    if not candidates:
        raise ValueError("no auto_accept_candidate rows found")
    output_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = output_dir / "direct_description_candidates_v1.jsonl"
    csv_path = output_dir / "direct_description_candidates_v1.csv"
    summary_path = output_dir / "direct_description_summary_v1.json"
    hash_path = output_dir / "direct_description_hashes_v1.json"
    _atomic_write(
        jsonl_path,
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for row in candidates
        ),
    )
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(candidates[0]))
    writer.writeheader()
    writer.writerows(
        {key: _csv_value(value) for key, value in row.items()} for row in candidates
    )
    _atomic_write(csv_path, buffer.getvalue(), encoding="utf-8-sig")
    _atomic_write(summary_path, json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "source_inputs": {
            manifest.name: {"path": str(manifest), "sha256": _sha256(manifest)}
        },
        "artifacts": {
            path.name: {
                "path": str(path),
                "sha256": _sha256(path),
                "bytes": path.stat().st_size,
            }
            for path in (jsonl_path, csv_path, summary_path)
        },
    }
    _atomic_write(hash_path, json.dumps(ledger, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return {"jsonl": jsonl_path, "csv": csv_path, "summary": summary_path, "hash_ledger": hash_path}


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)
    rows = _load_jsonl(args.manifest)
    candidates, summary = build_candidates(rows)
    return write_outputs(candidates, summary, manifest=args.manifest, output_dir=args.output_dir)


if __name__ == "__main__":
    main()
