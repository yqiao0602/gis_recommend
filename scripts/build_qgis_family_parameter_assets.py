#!/usr/bin/env python3
"""Materialize parameter and parent-structure assets from family collapse evidence.

The workflow pool keeps strict normalized-DAG deduplication.  This companion
asset pool preserves source-backed parameter and parent-context variation from
the suppressed rows without granting L3, Gold, Silver, or training admission.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

SCHEMA = "gis_recommend.qgis_family_parameter_assets.v1"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _family(row: dict[str, Any]) -> str:
    return "|".join(str(value) for value in row.get("family") or row.get("operator_sequence") or [])


def build_assets(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    parameter_groups: defaultdict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    structure_groups: defaultdict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    operator_groups: defaultdict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    deferred_parameter_rows = 0

    for row in rows:
        family = _family(row)
        dag = str(row.get("normalized_dag_key") or "")
        params = row.get("parameters") or {}
        parameter_key = params.get("semantic_key")
        if parameter_key:
            parameter_groups[(family, dag, str(parameter_key))].append(row)
        else:
            deferred_parameter_rows += 1
        structure = row.get("source_structure") or {}
        structure_key = digest(structure)
        structure_groups[(family, structure_key)].append(row)
        l3 = row.get("l3") or []
        for index, operator in enumerate(row.get("family", "").split("|") if row.get("family") else row.get("operator_sequence") or []):
            operator_groups[(str(operator), str(l3[index]) if index < len(l3) else "")].append(row)

    parameter_assets: list[dict[str, Any]] = []
    for (family, dag, parameter_key), group in sorted(parameter_groups.items()):
        first = group[0]
        raw_keys = {str((row.get("parameters") or {}).get("key") or "") for row in group}
        source_shas = sorted({str(row.get("source_sha256") or "") for row in group if row.get("source_sha256")})
        parameter_assets.append(
            {
                "schema": SCHEMA,
                "asset_type": "processing_parameter_signature",
                "asset_id": f"parameter:{digest([family, dag, parameter_key])}",
                "family": family,
                "normalized_dag_key": dag,
                "parameter_semantic_key": parameter_key,
                "parameter_status": (first.get("parameters") or {}).get("status", "unavailable"),
                "parameter_items": (first.get("parameters") or {}).get("items", []),
                "raw_parameter_signature_count": len(raw_keys),
                "support_count": len(group),
                "source_sha_count": len(source_shas),
                "source_sha256": source_shas,
                "review_ids": sorted(str(row.get("record_id") or "") for row in group),
                "provenance": "normalized_dag_collapse_audit_v1",
                "qualification_status": "candidate_only_parameter_asset",
                "l3_mapping": "inherited_family_l3_not_requalified",
                "training_admission": "not_granted",
                "training_rows_emitted": 0,
            }
        )

    structure_assets: list[dict[str, Any]] = []
    for (family, structure_key), group in sorted(structure_groups.items()):
        first = group[0]
        source_shas = sorted({str(row.get("source_sha256") or "") for row in group if row.get("source_sha256")})
        structure_assets.append(
            {
                "schema": SCHEMA,
                "asset_type": "processing_parent_structure",
                "asset_id": f"parent_structure:{digest([family, structure_key])}",
                "family": family,
                "parent_structure_key": structure_key,
                "normalized_dag_keys": sorted({str(row.get("normalized_dag_key") or "") for row in group}),
                "source_structure": first.get("source_structure") or {},
                "support_count": len(group),
                "source_sha_count": len(source_shas),
                "source_sha256": source_shas,
                "review_ids": sorted(str(row.get("record_id") or "") for row in group),
                "provenance": "normalized_dag_collapse_audit_v1",
                "qualification_status": "candidate_only_parent_context_asset",
                "training_admission": "not_granted",
                "training_rows_emitted": 0,
            }
        )

    operator_assets: list[dict[str, Any]] = []
    for (operator, l3), group in sorted(operator_groups.items()):
        source_shas = sorted({str(row.get("source_sha256") or "") for row in group if row.get("source_sha256")})
        operator_assets.append(
            {
                "schema": SCHEMA,
                "asset_type": "processing_operator_observation",
                "asset_id": f"operator:{digest([operator, l3])}",
                "operator_id": operator,
                "l3_code": l3,
                "family_support": sorted({_family(row) for row in group}),
                "support_count": len(group),
                "source_sha_count": len(source_shas),
                "source_sha256": source_shas,
                "provenance": "normalized_dag_collapse_audit_v1",
                "qualification_status": "candidate_only_operator_observation",
                "training_admission": "not_granted",
                "training_rows_emitted": 0,
            }
        )

    summary = {
        "schema": f"{SCHEMA}.summary",
        "input_rows": len(rows),
        "parameter_assets": len(parameter_assets),
        "parent_structure_assets": len(structure_assets),
        "operator_assets": len(operator_assets),
        "parameter_deferred_rows": deferred_parameter_rows,
        "parameter_support": sum(asset["support_count"] for asset in parameter_assets),
        "parent_structure_support": sum(asset["support_count"] for asset in structure_assets),
        "training_rows_emitted": 0,
        "training_admission": "not_granted_candidate_only_asset_pool",
        "workflow_dedup_modified": False,
        "formal_authority_modified": False,
    }
    return parameter_assets, structure_assets, operator_assets, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--collapse-rows", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    parameters, structures, operators, summary = build_assets(read_jsonl(args.collapse_rows))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "parameters": args.output_dir / "processing_parameter_assets_v1.jsonl",
        "structures": args.output_dir / "processing_parent_structure_assets_v1.jsonl",
        "operators": args.output_dir / "processing_operator_observations_v1.jsonl",
        "summary": args.output_dir / "summary_v1.json",
    }
    for path, rows in ((paths["parameters"], parameters), (paths["structures"], structures), (paths["operators"], operators)):
        path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    paths["summary"].write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report = args.output_dir / "asset_pool_report_v1.md"
    report.write_text(
        "# QGIS family parameter and parent asset pool v1\n\n"
        "This candidate-only pool preserves source-backed variation suppressed by workflow-level normalized-DAG dedup.\n\n"
        f"- Input collapse rows: **{summary['input_rows']}**\n"
        f"- Parameter assets: **{summary['parameter_assets']}**\n"
        f"- Parent-structure assets: **{summary['parent_structure_assets']}**\n"
        f"- Operator observations: **{summary['operator_assets']}**\n"
        f"- Deferred parameter rows: **{summary['parameter_deferred_rows']}**\n"
        "- Workflow dedup modified: **false**\n"
        "- Training rows emitted: **0**\n\n"
        "Parameter and parent assets retain source SHA and audit provenance. They are not workflow survivors and require their own semantic/L3 qualification before any future training use.\n",
        encoding="utf-8",
    )
    hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in (*paths.values(), report)}
    hashes["input_collapse_rows"] = hashlib.sha256(args.collapse_rows.read_bytes()).hexdigest()
    (args.output_dir / "hash_ledger_v1.json").write_text(json.dumps(hashes, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
