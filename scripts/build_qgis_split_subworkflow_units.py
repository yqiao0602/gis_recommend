#!/usr/bin/env python3
"""Split every disconnected-scope QGIS route into source-backed local units."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

from gis_recommend.data.qgis_subworkflow_splitter import (
    literalize_processing_operator_ids,
    split_candidate_into_local_units,
)
from gis_recommend.data.qgis_task_description import (
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
DEFAULT_OUTPUT_DIR = ROOT / "docs/reports/qgis_split_subworkflow_units_v1"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_key(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _parent_indices(parent: dict[str, Any], unit: dict[str, Any]) -> list[int]:
    available = list(enumerate(parent.get("call_sites") or []))
    selected: list[int] = []
    used: set[int] = set()
    for site in unit["call_sites"]:
        matches = [
            index
            for index, candidate in available
            if index not in used
            and str(candidate.get("operator_id") or "").lower()
            == str(site.get("operator_id") or "").lower()
            and int(candidate.get("line_start") or 0) == int(site.get("line_start") or 0)
            and int(candidate.get("line_end") or candidate.get("line_start") or 0)
            == int(site.get("line_end") or site.get("line_start") or 0)
        ]
        if not matches:
            raise ValueError(f"cannot map split unit to parent calls: {parent['record_id']}")
        chosen = matches[0]
        used.add(chosen)
        selected.append(chosen)
    return selected


def build_split_units(
    manifest_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    parents = [
        row
        for row in manifest_rows
        if row.get("rule_id") == "split-disconnected-scopes-v1"
        and row.get("action") == "split_subworkflow"
    ]
    rows: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    for parent in parents:
        source_path = Path(parent["source_path"])
        if not source_path.is_file():
            failures.append({"record_id": parent["record_id"], "reason": "source_file_missing"})
            continue
        if _sha256(source_path) != parent["source_sha256"]:
            failures.append({"record_id": parent["record_id"], "reason": "source_sha256_mismatch"})
            continue
        source_text = source_path.read_text(encoding="utf-8-sig")
        analysis_source = source_text
        if (
            parent.get("resolution_status") == "fixed_chain_recovered"
            or parent.get("provider_migrations")
        ):
            try:
                analysis_source = literalize_processing_operator_ids(
                    source_text,
                    call_sites=parent.get("call_sites") or [],
                    require_full_coverage=not bool(parent.get("provider_migrations")),
                )
            except ValueError as exc:
                failures.append({"record_id": parent["record_id"], "reason": str(exc)})
                continue
        try:
            units = split_candidate_into_local_units(
                analysis_source, call_sites=parent.get("call_sites") or []
            )
        except ValueError as exc:
            failures.append({"record_id": parent["record_id"], "reason": str(exc)})
            continue
        for unit_ordinal, unit in enumerate(units, start=1):
            indices = _parent_indices(parent, unit)
            mapped_l3 = [parent["mapped_l3_chain"][index] for index in indices]
            parameter_facts = extract_literal_parameter_facts(
                analysis_source, call_sites=unit["call_sites"]
            )
            description_input = {
                "operator_ids": unit["operator_ids"],
                "dependency_edges": unit["dependency_edges"],
                "mapped_l3_chain": mapped_l3,
                "workflow_unit_scope": "local_subworkflow",
                "parameter_facts": parameter_facts,
            }
            generated = build_task_description(description_input)
            audit = audit_task_description(description_input, generated)
            row = dict(unit)
            row.update(generated)
            row.update(audit)
            row.update(
                {
                    "schema": "gis_recommend.qgis_split_subworkflow_candidate.v1",
                    "parent_record_id": parent["record_id"],
                    "parent_signature_hash": parent["signature_hash"],
                    "parent_source_root_id": parent["source_root_id"],
                    "source_path": parent["source_path"],
                    "source_sha256": parent["source_sha256"],
                    "unit_ordinal": unit_ordinal,
                    "parent_call_indices": indices,
                    "mapped_l3_chain": mapped_l3,
                    "parameter_facts": parameter_facts,
                    "normalized_dag_key": _json_key(
                        {
                            "operator_ids": unit["operator_ids"],
                            "dependency_edges": unit["dependency_edges"],
                        }
                    ),
                    "description_source": "frozen_local_dag_only",
                    "training_admission": "not_granted_pending_split_rule_audit",
                    "training_row_emitted": False,
                    "validation_eligible": False,
                    "test_eligible": False,
                    "production_merge": "not_granted",
                }
            )
            rows.append(row)

    split_counts = Counter(row["split_class"] for row in rows)
    multi = [row for row in rows if row["split_class"] == "multi_step_local_dag"]
    eligible_multi = [
        row for row in multi if row["local_structure_status"] == "eligible"
    ]
    structure_reasons = Counter(
        reason
        for row in multi
        for reason in row.get("local_structure_reasons") or []
    )
    summary = {
        "schema": "gis_recommend.qgis_split_subworkflow_summary.v1",
        "parent_rows": len(parents),
        "parent_rows_split": len({row["parent_record_id"] for row in rows}),
        "failed_parent_rows": len(failures),
        "failures": failures,
        "total_units": len(rows),
        "multi_step_units": split_counts["multi_step_local_dag"],
        "single_step_units": split_counts["single_step_local_unit"],
        "multi_step_structure_eligible": len(eligible_multi),
        "multi_step_structure_deferred": len(multi) - len(eligible_multi),
        "multi_step_structure_reason_counts": dict(sorted(structure_reasons.items())),
        "multi_step_description_fidelity_passed": sum(
            bool(row["description_fidelity_passed"]) for row in multi
        ),
        "multi_step_description_deferred": sum(
            not bool(row["description_fidelity_passed"]) for row in multi
        ),
        "unique_multi_step_dags": len({row["normalized_dag_key"] for row in multi}),
        "eligible_multi_step_description_fidelity_passed": sum(
            bool(row["description_fidelity_passed"]) for row in eligible_multi
        ),
        "eligible_multi_step_description_deferred": sum(
            not bool(row["description_fidelity_passed"]) for row in eligible_multi
        ),
        "decision": {
            "training_rows_emitted": 0,
            "training_admission": "not_granted_pending_split_rule_audit",
            "next_gate": "source-disjoint audit of multi-step local DAG units",
        },
    }
    return rows, summary


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def write_outputs(
    rows: list[dict[str, Any]], summary: dict[str, Any], *, manifest: Path, output_dir: Path
) -> dict[str, Path]:
    units_path = output_dir / "split_units_v1.jsonl"
    summary_path = output_dir / "summary_v1.json"
    hash_path = output_dir / "hash_ledger_v1.json"
    _atomic_write(
        units_path,
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for row in rows
        ),
    )
    _atomic_write(summary_path, json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    hashes = {
        "schema": "gis_recommend.hash_ledger.v1",
        "source_inputs": {manifest.name: {"path": str(manifest), "sha256": _sha256(manifest)}},
        "artifacts": {
            path.name: {"path": str(path), "sha256": _sha256(path), "bytes": path.stat().st_size}
            for path in (units_path, summary_path)
        },
    }
    _atomic_write(hash_path, json.dumps(hashes, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return {"units": units_path, "summary": summary_path, "hash_ledger": hash_path}


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)
    rows, summary = build_split_units(_load_jsonl(args.manifest))
    return write_outputs(rows, summary, manifest=args.manifest, output_dir=args.output_dir)


if __name__ == "__main__":
    main()
