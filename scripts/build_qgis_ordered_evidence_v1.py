#!/usr/bin/env python3
"""Build path-qualified ordered QGIS evidence against the frozen 114 taxonomy."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gis_recommend.data.qgis_pilot import (  # noqa: E402
    PILOT_SCHEMA,
    assert_write_allowed,
    build_ordered_evidence,
    file_sha256,
    map_ordered_evidence_to_taxonomy,
    normalize_qgis_operation,
)

csv.field_size_limit(min(sys.maxsize, 2**31 - 1))

STANDARD_PROCESSING_NAMESPACES = {
    "native",
    "qgis",
    "gdal",
    "grass",
    "grass7",
    "saga",
    "otb",
    "pdal",
}
DIRECT_API_TYPES = {"qgis_api", "gdal_api", "qgis_cpp_api", "direct_api"}


def _write_json(path: Path, payload: Mapping[str, Any]) -> None:
    path.write_bytes((json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8"))


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _load_facts(path: Path) -> dict[str, dict[str, Any]]:
    facts: dict[str, dict[str, Any]] = {}
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            row = json.loads(line)
            script_id = str(row.get("script_id") or Path(row.get("source_script", "")).stem)
            if script_id:
                facts[script_id] = row
    return facts


def _artifact_hashes(fact: Mapping[str, Any], group: str) -> dict[str, Any]:
    candidates = fact.get("artifact_candidates", {}).get(group, {})
    result: dict[str, Any] = {}
    for kind in ("ast", "steps"):
        paths = [Path(path) for path in candidates.get(kind, [])]
        hashes = [file_sha256(path) for path in paths if path.is_file()]
        result[f"{kind}_paths"] = [str(path) for path in paths]
        result[f"{kind}_sha256"] = hashes[0] if len(hashes) == 1 else None
        result[f"{kind}_hashes"] = hashes
    return result


def _identity(hashes: Mapping[str, Any]) -> tuple[str, str]:
    return str(hashes.get("ast_sha256") or ""), str(hashes.get("steps_sha256") or "")


def _is_direct_api(row: Mapping[str, Any]) -> bool:
    source_type = str(row.get("api_source_type") or "").lower()
    family = str(row.get("platform_family") or "").lower()
    operation = str(row.get("normalized_api_name") or "").lower()
    return (
        source_type in DIRECT_API_TYPES
        or family in {"qgis", "gdal", "ogr", "pyqgis"}
        or operation.startswith(("qgs", "gdal.", "ogr."))
    )


def _evidence_row(row: Mapping[str, Any]) -> dict[str, Any] | None:
    source_type = str(row.get("api_source_type") or "").strip().lower()
    operation = str(row.get("normalized_api_name") or "").strip()
    if not operation:
        return None
    if source_type == "qgis_processing_algorithm":
        operation = normalize_qgis_operation(operation)
        namespace = operation.split(":", 1)[0] if ":" in operation else ""
        if namespace and namespace not in STANDARD_PROCESSING_NAMESPACES:
            source_type = "custom_processing_algorithm"
    elif source_type in {"custom_processing_algorithm", "qgis_custom_algorithm"}:
        pass
    elif not _is_direct_api(row):
        return None
    return {
        "id": row.get("id"),
        "statement_index": row.get("statement_index"),
        "scope": row.get("scope") or row.get("function_name"),
        "nesting_depth": row.get("nesting_depth"),
        "relation": row.get("relation") or row.get("process_relation"),
        "api_source_type": source_type,
        "normalized_api_name": operation,
    }


def _record_id(group: str, script_id: str, hashes: Mapping[str, Any]) -> str:
    material = json.dumps(
        {"group": group, "script_id": script_id, "identity": _identity(hashes)},
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(material).hexdigest()[:24]


def _initial_record(
    *,
    group: str,
    script_id: str,
    rows: list[dict[str, Any]],
    fact: Mapping[str, Any],
    taxonomy: Mapping[str, Any],
) -> dict[str, Any]:
    hashes = _artifact_hashes(fact, group)
    evidence = map_ordered_evidence_to_taxonomy(build_ordered_evidence(rows), taxonomy)
    deterministic = bool(evidence.get("processing_algorithms"))
    return {
        "schema": PILOT_SCHEMA,
        "kind": "ordered_qgis_evidence_v1",
        "record_id": _record_id(group, script_id, hashes),
        "facts_row_id": fact.get("facts_row_id"),
        "script_id": script_id,
        "source_script": fact.get("source_script"),
        "extraction_group": group,
        "source_aliases": [group],
        "task_type": fact.get("task_type"),
        "task_name": fact.get("task_name"),
        "task_description": fact.get("task_description"),
        "artifact_hashes": hashes,
        "candidate_group_count": fact.get("candidate_group_count", 0),
        "collision_state": "pending_resolution",
        "evidence_tier": "T3" if deterministic else "T2",
        "deterministic_evidence": deterministic,
        **evidence,
    }


def _resolve_collisions(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_fact: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        by_fact[str(record.get("facts_row_id") or record["script_id"])].append(record)
    resolved = []
    for rows in by_fact.values():
        expected_groups = int(rows[0].get("candidate_group_count") or 0)
        if expected_groups <= 1:
            row = rows[0]
            row["collision_state"] = "resolved"
            resolved.append(row)
            continue
        identities = {_identity(row["artifact_hashes"]) for row in rows}
        complete_identity = all(all(identity) for identity in identities)
        if len(rows) == expected_groups and len(identities) == 1 and complete_identity:
            canonical = min(rows, key=lambda row: (row["extraction_group"], row["record_id"]))
            canonical["collision_state"] = "equivalent_mirrors"
            canonical["source_aliases"] = sorted(row["extraction_group"] for row in rows)
            resolved.append(canonical)
            continue
        for row in rows:
            row["collision_state"] = "unresolved_collision"
            row["evidence_tier"] = "T0"
            resolved.append(row)
    return sorted(resolved, key=lambda row: row["record_id"])


def build_ordered_dataset(
    *,
    facts_candidates: Path,
    extraction_root: Path,
    taxonomy_path: Path,
    crosswalk_path: Path | None = None,
    output_dir: Path,
    allowed_write_roots: list[Path],
    max_tables: int | None = None,
    max_rows_per_table: int | None = None,
) -> dict[str, Any]:
    output_dir = assert_write_allowed(output_dir, allowed_write_roots)
    output_dir.mkdir(parents=True, exist_ok=True)
    taxonomy = json.loads(taxonomy_path.read_text(encoding="utf-8"))
    mapping_taxonomy = dict(taxonomy)
    if crosswalk_path is not None:
        crosswalk = json.loads(crosswalk_path.read_text(encoding="utf-8"))
        if crosswalk.get("profile") != taxonomy.get("profile"):
            raise ValueError("crosswalk profile does not match taxonomy profile")
        mapping_taxonomy["alias_to_code"] = crosswalk["alias_to_code"]
    facts = _load_facts(facts_candidates)
    tables = sorted(extraction_root.glob("*/merged_nodes_process.csv"))
    if max_tables is not None:
        tables = tables[:max_tables]

    raw_records = []
    rows_scanned = 0
    relevant_rows = 0
    for table in tables:
        group = table.parent.name
        per_script: dict[str, list[dict[str, Any]]] = defaultdict(list)
        with table.open(encoding="utf-8-sig", newline="") as handle:
            for table_row, row in enumerate(csv.DictReader(handle), start=1):
                if max_rows_per_table is not None and table_row > max_rows_per_table:
                    break
                rows_scanned += 1
                script_id = Path(str(row.get("source_script") or "")).stem
                fact = facts.get(script_id)
                if fact is None or group not in fact.get("artifact_candidates", {}):
                    continue
                evidence_row = _evidence_row(row)
                if evidence_row is None:
                    continue
                relevant_rows += 1
                per_script[script_id].append(evidence_row)
        for script_id, evidence_rows in per_script.items():
            raw_records.append(
                _initial_record(
                    group=group,
                    script_id=script_id,
                    rows=evidence_rows,
                    fact=facts[script_id],
                    taxonomy=mapping_taxonomy,
                )
            )

    records = _resolve_collisions(raw_records)
    tier_counts = Counter(row["evidence_tier"] for row in records)
    collision_counts = Counter(row["collision_state"] for row in records)
    ordering_counts = Counter(row["ordering_confidence"] for row in records)
    completeness_counts = Counter(row["chain_completeness"] for row in records)
    class_calls = Counter()
    class_scripts: dict[str, set[str]] = defaultdict(set)
    operation_calls = Counter()
    operation_scripts: dict[str, set[str]] = defaultdict(set)
    unmapped_calls = Counter()
    for row in records:
        for step in row["ordered_steps"]:
            operation = step["normalized_operation"]
            if step["mapping_status"] == "exact_alias":
                code = step["l3_code"]
                class_calls[code] += 1
                class_scripts[code].add(row["record_id"])
                operation_calls[operation] += 1
                operation_scripts[operation].add(row["record_id"])
            else:
                unmapped_calls[operation] += 1

    crosswalk_rows = [
        {
            "operation": operation,
            "l3_code": mapping_taxonomy["alias_to_code"][operation],
            "l3_token_id": taxonomy["code_to_token_id"][mapping_taxonomy["alias_to_code"][operation]],
            "calls": operation_calls[operation],
            "records": len(operation_scripts[operation]),
            "mapping_status": "exact_alias",
        }
        for operation in sorted(mapping_taxonomy.get("alias_to_code", {}))
    ]
    summary = {
        "schema": PILOT_SCHEMA,
        "kind": "ordered_qgis_evidence_summary_v1",
        "taxonomy_profile": taxonomy.get("profile"),
        "inputs": {
            "facts_candidates": str(facts_candidates.resolve()),
            "facts_candidates_sha256": file_sha256(facts_candidates),
            "taxonomy": str(taxonomy_path.resolve()),
            "taxonomy_sha256": file_sha256(taxonomy_path),
            "crosswalk": str(crosswalk_path.resolve()) if crosswalk_path else None,
            "crosswalk_sha256": file_sha256(crosswalk_path) if crosswalk_path else None,
            "extraction_root": str(extraction_root.resolve()),
            "merged_tables": [str(table.resolve()) for table in tables],
        },
        "rows_scanned": rows_scanned,
        "relevant_rows": relevant_rows,
        "records": len(records),
        "counts": {
            "evidence_tier": dict(sorted(tier_counts.items())),
            "collision_state": dict(sorted(collision_counts.items())),
            "ordering_confidence": dict(sorted(ordering_counts.items())),
            "chain_completeness": dict(sorted(completeness_counts.items())),
        },
        "class_coverage": [
            {
                "l3_code": code,
                "token_id": taxonomy["code_to_token_id"][code],
                "calls": class_calls[code],
                "records": len(class_scripts[code]),
            }
            for code in sorted(taxonomy["code_to_token_id"], key=taxonomy["code_to_token_id"].get)
        ],
        "top_unmapped_operations": [
            {"operation": operation, "calls": calls}
            for operation, calls in unmapped_calls.most_common(200)
        ],
        "policy": {
            "automatic_mapping": "exact_alias_only",
            "unresolved_collisions_enter_training": False,
            "unmapped_or_direct_api_forced_to_l3": False,
        },
    }

    evidence_path = output_dir / "ordered_evidence.jsonl"
    summary_path = output_dir / "ordered_evidence_summary.json"
    crosswalk_path = output_dir / "observed_exact_alias_crosswalk.json"
    ledger_path = output_dir / "write_ledger.json"
    _write_jsonl(evidence_path, records)
    _write_json(summary_path, summary)
    _write_json(
        crosswalk_path,
        {
            "schema": PILOT_SCHEMA,
            "kind": "observed_exact_alias_crosswalk_v1",
            "taxonomy_profile": taxonomy.get("profile"),
            "entries": crosswalk_rows,
        },
    )
    _write_json(
        ledger_path,
        {
            "schema": PILOT_SCHEMA,
            "allowed_write_roots": [str(Path(root).resolve()) for root in allowed_write_roots],
            "created_or_replaced": [
                {"path": str(path), "sha256": file_sha256(path), "size": path.stat().st_size}
                for path in (evidence_path, summary_path, crosswalk_path)
            ],
        },
    )
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--facts-candidates", type=Path, required=True)
    parser.add_argument("--extraction-root", type=Path, required=True)
    parser.add_argument("--taxonomy", type=Path, required=True)
    parser.add_argument("--crosswalk", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--allowed-write-root", type=Path, action="append", required=True)
    parser.add_argument("--max-tables", type=int)
    parser.add_argument("--max-rows-per-table", type=int)
    args = parser.parse_args(argv)
    summary = build_ordered_dataset(
        facts_candidates=args.facts_candidates,
        extraction_root=args.extraction_root,
        taxonomy_path=args.taxonomy,
        crosswalk_path=args.crosswalk,
        output_dir=args.output_dir,
        allowed_write_roots=args.allowed_write_root,
        max_tables=args.max_tables,
        max_rows_per_table=args.max_rows_per_table,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
