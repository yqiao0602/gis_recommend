#!/usr/bin/env python3
"""Recover low-risk connected local DAGs from QGIS recovery routes."""

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
    / "stable101_all1442_source_replay_v1/routing_v6/routing_manifest.jsonl"
)
DEFAULT_OUTPUT_DIR = ROOT / "docs/reports/qgis_recovery_local_dag_units_v1"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_key(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _parent_indices(parent: dict[str, Any], unit: dict[str, Any]) -> list[int]:
    selected: list[int] = []
    used: set[int] = set()
    for site in unit["call_sites"]:
        matches = [
            index
            for index, candidate in enumerate(parent.get("call_sites") or [])
            if index not in used
            and str(candidate.get("operator_id") or "").lower()
            == str(site.get("operator_id") or "").lower()
            and int(candidate.get("line_start") or 0)
            == int(site.get("line_start") or 0)
            and int(candidate.get("line_end") or candidate.get("line_start") or 0)
            == int(site.get("line_end") or site.get("line_start") or 0)
        ]
        if not matches:
            raise ValueError(
                f"cannot map recovery unit to parent calls: {parent['record_id']}"
            )
        chosen = matches[0]
        used.add(chosen)
        selected.append(chosen)
    return selected


def _source_snippet(source_text: str, call_sites: list[dict[str, Any]]) -> str:
    lines = source_text.splitlines()
    start = max(1, min(int(site["line_start"]) for site in call_sites) - 2)
    end = min(
        len(lines),
        max(int(site.get("line_end") or site["line_start"]) for site in call_sites)
        + 2,
    )
    return "\n".join(f"{line_number}: {lines[line_number - 1]}" for line_number in range(start, end + 1))

def classify_recovery_unit(
    unit: dict[str, Any], *, parent_rule_id: str
) -> dict[str, Any]:
    operators = unit.get("operator_ids") or []
    edges = [list(map(int, edge)) for edge in unit.get("dependency_edges") or []]
    node_indices = set(range(len(operators)))
    roots = sorted(node_indices - {target for _, target in edges})
    sinks = sorted(node_indices - {source for source, _ in edges})
    forward_edges = all(source < target for source, target in edges)
    fanin = any(
        sum(target == index for _, target in edges) > 1 for index in node_indices
    )
    result = {
        "recovery_structure_status": "deferred",
        "recovery_rule_id": "recovery-local-dag-deferred-v1",
        "root_indices": roots,
        "sink_indices": sinks,
        "forward_edges": forward_edges,
        "fanin": fanin,
    }
    if unit.get("split_class") != "multi_step_local_dag":
        return result
    if unit.get("local_structure_status") == "eligible":
        result.update(
            {
                "recovery_structure_status": "eligible",
                "recovery_rule_id": "recovery-connected-local-dag-v1",
            }
        )
        return result
    reasons = sorted(set(unit.get("local_structure_reasons") or []))
    if (
        parent_rule_id == "recover-missing-data-edges-v1"
        and reasons == ["missing_data_edges"]
        and len(roots) > 1
        and len(sinks) == 1
        and forward_edges
        and fanin
    ):
        result.update(
            {
                "recovery_structure_status": "eligible",
                "recovery_rule_id": "recovery-multi-root-fanin-dag-v1",
            }
        )
    return result


def build_recovery_units(
    manifest_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    parents = [
        row for row in manifest_rows if row.get("action") == "recover_call_graph"
    ]
    rows: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    total_units = 0
    multi_step_units = 0
    structurally_eligible = 0
    deferred_reasons: Counter[str] = Counter()

    for parent in parents:
        source_path = Path(parent["source_path"])
        if not source_path.is_file():
            failures.append(
                {"record_id": parent["record_id"], "reason": "source_file_missing"}
            )
            continue
        if _sha256(source_path) != parent["source_sha256"]:
            failures.append(
                {"record_id": parent["record_id"], "reason": "source_sha256_mismatch"}
            )
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
        total_units += len(units)
        for unit in units:
            if unit.get("split_class") != "multi_step_local_dag":
                continue
            multi_step_units += 1
            classification = classify_recovery_unit(
                unit, parent_rule_id=str(parent["rule_id"])
            )
            if classification["recovery_structure_status"] != "eligible":
                deferred_reasons.update(unit.get("local_structure_reasons") or [])
                continue
            structurally_eligible += 1
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
            row.update(classification)
            row.update(generated)
            row.update(audit)
            row.update(
                {
                    "schema": "gis_recommend.qgis_recovery_local_dag_candidate.v1",
                    "parent_record_id": parent["record_id"],
                    "parent_rule_id": parent["rule_id"],
                    "parent_signature_hash": parent.get("signature_hash", ""),
                    "source_root_id": parent.get("source_root_id"),
                    "source_path": parent["source_path"],
                    "source_sha256": parent["source_sha256"],
                    "source_snippet": _source_snippet(
                        source_text, unit["call_sites"]
                    ),
                    "parent_call_indices": indices,
                    "mapped_l3_chain": mapped_l3,
                    "parameter_facts": parameter_facts,
                    "normalized_dag_key": _json_key(
                        {
                            "operator_ids": unit["operator_ids"],
                            "dependency_edges": unit["dependency_edges"],
                        }
                    ),
                    "description_source": "frozen_recovered_local_dag_only",
                    "known_omissions": [
                        "outside_recovered_local_dag_not_described"
                    ],
                    "training_admission": "not_granted_pending_recovery_rule_audit",
                    "training_row_emitted": False,
                    "validation_eligible": False,
                    "test_eligible": False,
                    "production_merge": "not_granted",
                }
            )
            rows.append(row)

    eligible_sources = {row["source_sha256"] for row in rows}
    summary = {
        "schema": "gis_recommend.qgis_recovery_local_dag_summary.v1",
        "parent_rows": len(parents),
        "failed_parent_rows": len(failures),
        "failures": failures,
        "total_local_units": total_units,
        "multi_step_units": multi_step_units,
        "eligible_multi_step_units": len(rows),
        "structurally_eligible_before_description_gate": structurally_eligible,
        "eligible_source_disjoint_support": len(eligible_sources),
        "eligible_description_fidelity_passed": sum(
            bool(row.get("description_fidelity_passed")) for row in rows
        ),
        "eligible_description_deferred": sum(
            not bool(row.get("description_fidelity_passed")) for row in rows
        ),
        "eligible_recovery_rule_counts": dict(
            sorted(Counter(row["recovery_rule_id"] for row in rows).items())
        ),
        "eligible_parent_rule_counts": dict(
            sorted(Counter(row["parent_rule_id"] for row in rows).items())
        ),
        "eligible_unique_normalized_dags": len(
            {row["normalized_dag_key"] for row in rows}
        ),
        "deferred_structure_reason_counts": dict(sorted(deferred_reasons.items())),
        "decision": {
            "training_rows_emitted": 0,
            "training_admission": "not_granted_pending_recovery_rule_audit",
            "next_gate": "source-disjoint audit of recovery local DAG rule",
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
    rows: list[dict[str, Any]],
    summary: dict[str, Any],
    *,
    manifest: Path,
    output_dir: Path,
) -> dict[str, Path]:
    candidates_path = output_dir / "recovery_local_dag_candidates_v1.jsonl"
    summary_path = output_dir / "summary_v1.json"
    hash_path = output_dir / "hash_ledger_v1.json"
    _atomic_write(
        candidates_path,
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
            for row in rows
        ),
    )
    _atomic_write(
        summary_path,
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    hashes = {
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
            for path in (candidates_path, summary_path)
        },
    }
    _atomic_write(
        hash_path,
        json.dumps(hashes, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    return {
        "candidates": candidates_path,
        "summary": summary_path,
        "hash_ledger": hash_path,
    }


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)
    rows, summary = build_recovery_units(_load_jsonl(args.manifest))
    return write_outputs(
        rows, summary, manifest=args.manifest, output_dir=args.output_dir
    )


if __name__ == "__main__":
    main()
