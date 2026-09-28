#!/usr/bin/env python3
"""Measure recovery blockers by independent QGIS source authority."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable

from gis_recommend.data.qgis_source_authority import source_authority
from gis_recommend.data.qgis_subworkflow_splitter import (
    split_candidate_into_local_units,
)
from scripts.build_qgis_recovery_local_dag_units import classify_recovery_unit


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = (
    ROOT
    / "docs/reports/qgis_mapping_high_impact_blockers_2026-07-24"
    / "stable101_all1442_source_replay_v1/routing_v6/routing_manifest.jsonl"
)
DEFAULT_OUTPUT_DIR = ROOT / "docs/reports/qgis_recovery_expansion_census_v1"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_hash(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _group_counts(
    rows: list[dict[str, Any]], key: Callable[[dict[str, Any]], str]
) -> dict[str, dict[str, int]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[key(row)].append(row)
    return {
        name: {
            "raw_units": len(group_rows),
            "source_authorities": len(
                {row["source_authority_key"] for row in group_rows}
            ),
        }
        for name, group_rows in sorted(groups.items())
    }


def _reason_counts(rows: list[dict[str, Any]]) -> dict[str, dict[str, int]]:
    expanded = [
        {**row, "counted_reason": reason}
        for row in rows
        for reason in row["local_structure_reasons"]
    ]
    return _group_counts(expanded, lambda row: str(row["counted_reason"]))


def build_expansion_census(
    manifest_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    parents = [
        row for row in manifest_rows if row.get("action") == "recover_call_graph"
    ]
    rows: list[dict[str, Any]] = []
    failures: list[dict[str, str]] = []
    parent_authorities: set[str] = set()
    for parent in parents:
        source_path = Path(str(parent.get("source_path") or ""))
        declared_sha = str(parent.get("source_sha256") or "")
        if not source_path.is_file():
            failures.append(
                {"record_id": str(parent.get("record_id")), "reason": "source_file_missing"}
            )
            continue
        if _sha256(source_path) != declared_sha:
            failures.append(
                {"record_id": str(parent.get("record_id")), "reason": "source_sha256_mismatch"}
            )
            continue
        authority = source_authority(source_path, source_sha256=declared_sha)
        parent_authorities.add(authority["source_authority_key"])
        source_text = source_path.read_text(encoding="utf-8")
        try:
            units = split_candidate_into_local_units(
                source_text, call_sites=parent.get("call_sites") or []
            )
        except ValueError as exc:
            failures.append(
                {"record_id": str(parent.get("record_id")), "reason": str(exc)}
            )
            continue
        for unit in units:
            if unit.get("split_class") != "multi_step_local_dag":
                continue
            reasons = sorted(set(unit.get("local_structure_reasons") or []))
            current = classify_recovery_unit(
                unit, parent_rule_id=str(parent.get("rule_id") or "")
            )
            if current["recovery_structure_status"] == "eligible":
                expansion_class = "already_recovered_current_rule"
            elif reasons == ["provider_input_type_conflict"]:
                expansion_class = "explicit_type_conflict_excluded"
            elif len(reasons) == 1:
                expansion_class = "single_blocker_candidate"
            else:
                expansion_class = "multi_blocker_deferred"
            risk = unit.get("local_risk_evidence") or {}
            rows.append(
                {
                    "schema": "gis_recommend.qgis_recovery_expansion_census_unit.v1",
                    "parent_record_id": parent.get("record_id"),
                    "parent_rule_id": parent.get("rule_id"),
                    "source_root_id": parent.get("source_root_id"),
                    "source_path": str(source_path),
                    "source_sha256": declared_sha,
                    **authority,
                    "unit_id": unit.get("unit_id"),
                    "operator_ids": unit.get("operator_ids") or [],
                    "call_sites": unit.get("call_sites") or [],
                    "dependency_edges": unit.get("dependency_edges") or [],
                    "local_structure_status": unit.get("local_structure_status"),
                    "local_structure_reasons": reasons,
                    "reason_set_key": "|".join(reasons) or "none",
                    "structure_signature": _json_hash(
                        {
                            "operator_ids": unit.get("operator_ids") or [],
                            "dependency_edges": unit.get("dependency_edges") or [],
                            "reasons": reasons,
                        }
                    ),
                    "current_recovery_rule_id": current["recovery_rule_id"],
                    "current_recovery_structure_status": current[
                        "recovery_structure_status"
                    ],
                    "expansion_class": expansion_class,
                    "provider_input_type_status": risk.get(
                        "provider_input_type_status", "not_applicable"
                    ),
                    "provider_input_type_checks": risk.get(
                        "provider_input_type_checks"
                    )
                    or [],
                    "provider_input_type_conflicts": risk.get(
                        "provider_input_type_conflicts"
                    )
                    or [],
                    "training_admission": "not_granted_expansion_census_only",
                    "training_row_emitted": False,
                    "validation_eligible": False,
                    "test_eligible": False,
                    "production_merge": "not_granted",
                }
            )

    single_candidates = [
        row for row in rows if row["expansion_class"] == "single_blocker_candidate"
    ]
    summary = {
        "schema": "gis_recommend.qgis_recovery_expansion_census_summary.v1",
        "raw_parent_rows": len(parents),
        "verified_parent_rows": len(parents) - len(failures),
        "unique_parent_authorities": len(parent_authorities),
        "multi_step_units": len(rows),
        "unique_multi_step_authorities": len(
            {row["source_authority_key"] for row in rows}
        ),
        "unique_structure_signatures": len(
            {row["structure_signature"] for row in rows}
        ),
        "parent_rule_populations": _group_counts(
            rows, lambda row: str(row["parent_rule_id"])
        ),
        "expansion_class_populations": _group_counts(
            rows, lambda row: str(row["expansion_class"])
        ),
        "reason_populations": _reason_counts(rows),
        "reason_set_populations": _group_counts(
            rows, lambda row: str(row["reason_set_key"])
        ),
        "single_reason_opportunities": _group_counts(
            single_candidates, lambda row: str(row["reason_set_key"])
        ),
        "provider_input_type_status_counts": dict(
            sorted(Counter(row["provider_input_type_status"] for row in rows).items())
        ),
        "failures": failures,
        "decision": {
            "training_admission": "not_granted_expansion_census_only",
            "training_rows_emitted": 0,
            "next_gate": "implement highest-support bounded recovery rule and audit source-disjoint support>=30",
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


def _render_report(summary: dict[str, Any]) -> str:
    lines = [
        "# QGIS Recovery Expansion Census v1",
        "",
        "This census measures independent source authorities; it emits no training rows.",
        "",
        f"- Recovery parents: {summary['raw_parent_rows']}",
        f"- Independent parent authorities: {summary['unique_parent_authorities']}",
        f"- Multi-step local units: {summary['multi_step_units']}",
        f"- Unique structure signatures: {summary['unique_structure_signatures']}",
        "- Training rows emitted: 0",
        "",
        "## Single-Reason Opportunities",
        "",
        "| Reason | Raw units | Source authorities |",
        "|---|---:|---:|",
    ]
    opportunities = summary["single_reason_opportunities"]
    for reason, counts in sorted(
        opportunities.items(),
        key=lambda item: (-item[1]["source_authorities"], item[0]),
    ):
        lines.append(
            f"| {reason} | {counts['raw_units']} | {counts['source_authorities']} |"
        )
    return "\n".join(lines) + "\n"


def write_outputs(
    rows: list[dict[str, Any]],
    summary: dict[str, Any],
    *,
    manifest_path: Path,
    output_dir: Path,
) -> dict[str, Path]:
    ledger_path = output_dir / "expansion_census_units_v1.jsonl"
    summary_path = output_dir / "summary_v1.json"
    report_path = output_dir / "report_v1.md"
    hash_path = output_dir / "hash_ledger_v1.json"
    _atomic_write(
        ledger_path,
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
    _atomic_write(report_path, _render_report(summary))
    hashes = {
        "schema": "gis_recommend.hash_ledger.v1",
        "source_inputs": {
            manifest_path.name: {
                "path": str(manifest_path),
                "sha256": _sha256(manifest_path),
            }
        },
        "artifacts": {
            path.name: {"path": str(path), "sha256": _sha256(path)}
            for path in (ledger_path, summary_path, report_path)
        },
    }
    _atomic_write(
        hash_path,
        json.dumps(hashes, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    return {
        "ledger": ledger_path,
        "summary": summary_path,
        "report": report_path,
        "hash_ledger": hash_path,
    }


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)
    rows, summary = build_expansion_census(_load_jsonl(args.manifest))
    return write_outputs(
        rows, summary, manifest_path=args.manifest, output_dir=args.output_dir
    )


if __name__ == "__main__":
    main()
