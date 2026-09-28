#!/usr/bin/env python3
"""Census untouched Processing sources for strictly static ID recovery.

This is a source-backed intake.  It excludes already delivered and previously
scanned source SHA256s, resolves only direct ``processing.run`` operator
expressions with one AST-provable static string, and replays the local splitter
in memory.  Its output is evidence only: structural similarity never creates a
task, L3 label, description, or training row.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(ROOT / "src") not in sys.path:
    sys.path.insert(0, str(ROOT / "src"))

from gis_recommend.data.qgis_subworkflow_splitter import (
    split_candidate_into_local_units,
)
from scripts.analyze_qgis_processing_resolution_census import analyze_source
from scripts.recover_qgis_dynamic_operator_ids import (
    _ordered_calls,
    build_literalized_analysis_source,
)
from scripts.recover_qgis_legacy_provider_ids import (
    canonicalize_operator_id,
    load_catalog_ids,
)
from scripts.replay_qgis_output_alias_strict import inspect_strict_output_alias

SCHEMA = "gis_recommend.qgis_processing_static_recovery_census.v1"
DEFAULT_STATUSES = {"deferred_operator", "deferred_mapping"}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_hashes(rows: list[dict[str, Any]]) -> set[str]:
    return {str(row["source_sha256"]) for row in rows if row.get("source_sha256")}


def _load_catalog_ids(path: Path) -> set[str]:
    """Load the frozen JSON authority or the legacy CSV catalog surface."""

    if path.suffix.lower() != ".json":
        return load_catalog_ids(path)
    payload = json.loads(path.read_text(encoding="utf-8"))
    operators = payload.get("operators") if isinstance(payload, dict) else None
    if not isinstance(operators, list):
        raise TypeError(f"catalog JSON does not contain an operators list: {path}")
    ids = {
        str(row.get("operator_id") or "").strip().lower()
        for row in operators
        if isinstance(row, dict) and ":" in str(row.get("operator_id") or "")
    }
    if not ids:
        raise ValueError(f"no provider-qualified operator IDs found in {path}")
    return ids


def _source_identity(row: dict[str, Any]) -> tuple[str, str, str]:
    return (
        str(row.get("source_sha256") or ""),
        str(row.get("record_id") or ""),
        str(row.get("source_path") or ""),
    )


def _static_call_sites(
    source_text: str, catalog_ids: set[str]
) -> tuple[str, list[dict[str, Any]], dict[str, Any]]:
    """Return a literalized source only when every direct call is exact."""

    _, calls, evidence = _ordered_calls(source_text)
    if not calls:
        return "deferred_no_direct_processing_call", [], {"calls": evidence}
    if not any(item["kind"] == "dynamic" for item in evidence):
        return "exclude_no_dynamic_operator", [], {"calls": evidence}
    if any(len(item["operator_ids"]) != 1 for item in evidence):
        return "deferred_non_single_static_operator", [], {"calls": evidence}
    raw_ids = [str(item["operator_ids"][0]).strip().lower() for item in evidence]
    resolutions = [
        canonicalize_operator_id(operator_id, catalog_ids) for operator_id in raw_ids
    ]
    if any(canonical is None for canonical, _ in resolutions):
        return (
            "deferred_catalog_miss",
            [],
            {
                "calls": evidence,
                "unresolved_operator_ids": [
                    raw
                    for raw, (canonical, _) in zip(raw_ids, resolutions)
                    if canonical is None
                ],
            },
        )
    canonical_ids = [str(canonical) for canonical, _ in resolutions]
    source, call_sites = build_literalized_analysis_source(source_text, catalog_ids)
    return (
        "recovered_static_direct_chain",
        call_sites,
        {
            "calls": evidence,
            "canonical_operator_ids": canonical_ids,
            "provider_migrations": [
                {"source": raw, "target": canonical, "rule": rule}
                for raw, (canonical, rule) in zip(raw_ids, resolutions)
                if rule == "qgis_to_native_same_slug"
            ],
            "literalized_source": source,
        },
    )


def census(
    ledger: list[dict[str, Any]],
    *,
    catalog_ids: set[str],
    excluded_source_sha256: set[str],
    statuses: set[str] = DEFAULT_STATUSES,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    selected: dict[str, dict[str, Any]] = {}
    exclusions: Counter[str] = Counter()
    for row in ledger:
        source_sha, record_id, source_path = _source_identity(row)
        if not source_sha or not record_id or not source_path:
            exclusions["missing_source_identity"] += 1
        elif str(row.get("status") or "") not in statuses:
            exclusions["not_requested_status"] += 1
        elif source_sha in excluded_source_sha256:
            exclusions["already_delivered_or_scanned_source"] += 1
        else:
            current = selected.get(source_sha)
            if current is None or record_id < str(current["record_id"]):
                selected[source_sha] = row

    rows: list[dict[str, Any]] = []
    for source_sha, ledger_row in sorted(selected.items()):
        source_path = Path(str(ledger_row["source_path"]))
        base = {
            "schema": SCHEMA,
            "record_id": str(ledger_row["record_id"]),
            "source_sha256": source_sha,
            "source_path": str(source_path),
            "source_root_id": str(ledger_row.get("source_root_id") or ""),
            "source_status": str(ledger_row.get("status") or ""),
            "training_admission": "not_granted_static_recovery_census_only",
            "training_row_emitted": False,
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
            "llm_called": False,
        }
        if not source_path.is_file():
            rows.append({**base, "recovery_status": "exclude_source_file_missing"})
            continue
        if _sha256(source_path) != source_sha:
            rows.append({**base, "recovery_status": "exclude_source_sha256_mismatch"})
            continue
        source_text = source_path.read_text(encoding="utf-8-sig", errors="replace")
        try:
            source_analysis = analyze_source(source_text)
            recovery_status, call_sites, recovery_evidence = _static_call_sites(
                source_text, catalog_ids
            )
        except SyntaxError:
            rows.append({**base, "recovery_status": "exclude_source_parse_failure"})
            continue

        if source_analysis["processing_call_count"] != len(recovery_evidence["calls"]):
            recovery_status = "deferred_non_direct_registry_or_wrapper_call"
        capabilities = []
        if recovery_status == "recovered_static_direct_chain":
            capabilities.append("static_operator_id")
        if source_analysis["helper_edge_count"]:
            capabilities.append("helper_callgraph_evidence")
        alias = {"status": "not_applicable", "reason": "not_recovered", "evidence": []}
        units: list[dict[str, Any]] = []
        boundary_status = "not_replayed"
        if recovery_status == "recovered_static_direct_chain":
            alias = inspect_strict_output_alias(source_text, call_sites=call_sites)
            if alias["status"] == "rule_candidate":
                capabilities.append("strict_output_alias_evidence")
            try:
                units = split_candidate_into_local_units(
                    str(recovery_evidence["literalized_source"]), call_sites=call_sites
                )
                boundary_status = "replayed"
            except (SyntaxError, ValueError):
                boundary_status = "deferred_splitter_failure"
        rows.append(
            {
                **base,
                "recovery_status": recovery_status,
                "capabilities": capabilities,
                "call_sites": call_sites,
                "static_recovery_evidence": {
                    key: value
                    for key, value in recovery_evidence.items()
                    if key != "literalized_source"
                },
                "helper_edges": source_analysis["helper_edges"],
                "strict_output_alias": alias,
                "boundary_replay_status": boundary_status,
                "local_unit_count": len(units),
                "complete_local_unit_count": sum(
                    unit.get("local_structure_status") == "eligible" for unit in units
                ),
                "local_unit_operator_sequences": [
                    unit.get("operator_ids") or [] for unit in units
                ],
            }
        )

    statuses_count = Counter(str(row["recovery_status"]) for row in rows)
    summary = {
        "schema": f"{SCHEMA}.summary",
        "input_ledger_rows": len(ledger),
        "excluded_source_sha256_count": len(excluded_source_sha256),
        "selected_uncovered_sources": len(selected),
        "exclusion_counts": dict(sorted(exclusions.items())),
        "recovery_status_counts": dict(sorted(statuses_count.items())),
        "static_recovered_sources": sum(
            row["recovery_status"] == "recovered_static_direct_chain" for row in rows
        ),
        "complete_local_units": sum(
            int(row.get("complete_local_unit_count") or 0) for row in rows
        ),
        "training_admission": "not_granted_static_recovery_census_only",
        "training_rows_emitted": 0,
        "next_gate": "source_disjoint_calibration_of_a_source_backed_helper_alias_or_dynamic_id_family",
    }
    return rows, summary


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        temporary = Path(handle.name)
    temporary.replace(path)


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--existing-authority", type=Path, required=True)
    parser.add_argument(
        "--exclude-source-manifest", type=Path, action="append", default=[]
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--status", action="append", default=sorted(DEFAULT_STATUSES))
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    exclusions = _source_hashes(_read_jsonl(args.existing_authority))
    for manifest in args.exclude_source_manifest:
        exclusions.update(_source_hashes(_read_jsonl(manifest)))
    rows, summary = census(
        _read_jsonl(args.ledger),
        catalog_ids=_load_catalog_ids(args.catalog),
        excluded_source_sha256=exclusions,
        statuses=set(args.status),
    )
    ledger_path = args.output_dir / "static_recovery_census_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    report_path = args.output_dir / "report_v1.md"
    _write_jsonl(ledger_path, rows)
    _write_json(summary_path, summary)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        "# QGIS Processing Static Recovery Census v1\n\n"
        "Source-backed evidence only. No L3 labels, descriptions, or training rows are emitted.\n",
        encoding="utf-8",
    )
    _write_json(
        args.output_dir / "hash_ledger_v1.json",
        {
            "schema": "gis_recommend.hash_ledger.v1",
            "inputs": {
                args.ledger.name: _sha256(args.ledger),
                args.catalog.name: _sha256(args.catalog),
                args.existing_authority.name: _sha256(args.existing_authority),
                **{path.name: _sha256(path) for path in args.exclude_source_manifest},
            },
            "artifacts": {
                path.name: _sha256(path)
                for path in (ledger_path, summary_path, report_path)
            },
        },
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
