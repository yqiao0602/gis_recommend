#!/usr/bin/env python3
"""Build a candidate-only Processing operator asset census.

The input is the normalized Asset Miner ledger.  This lane aggregates static
operator observations by operator ID while preserving source provenance and
parameter/I-O evidence.  It deliberately does not infer L3, create workflow
rows, or admit training data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any

SCHEMA = "gis_recommend.qgis_processing_operator_assets.v1"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def digest(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def row_operator_ids(row: dict[str, Any]) -> list[str]:
    values = row.get("processing_operator_ids")
    if values is None:
        values = row.get("operator_sequence")
    if values is None:
        family = row.get("family")
        values = str(family).split("|") if family else []
    return [str(value).strip().lower() for value in values if str(value).strip()]


def row_resolution_kinds(row: dict[str, Any], operator_id: str) -> set[str]:
    """Read call-level evidence, with a fallback to normalized resolution metadata."""
    kinds = {
        str(call.get("resolution_kind") or "")
        for call in row.get("processing_calls") or []
        if isinstance(call, dict)
        and str(call.get("operator_id", call.get("operator")) or "").strip().lower() == operator_id
        and call.get("resolution_kind")
    }
    if kinds:
        return kinds
    resolution = row.get("resolution")
    if isinstance(resolution, dict) and resolution.get("processing") and operator_id in row_operator_ids(row):
        return {str(resolution["processing"])}
    return set()


def build_assets(
    rows: list[dict[str, Any]],
    *,
    expected_operator_rows: int | None = 591,
    asset_type: str = "processing_operator",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    scoped_rows = [row for row in rows if not asset_type or str(row.get("asset_type") or "") == asset_type]
    groups: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in scoped_rows:
        for operator_id in sorted(set(row_operator_ids(row))):
            groups[operator_id].append(row)

    assets: list[dict[str, Any]] = []
    for operator_id, members in sorted(groups.items()):
        sources = sorted({str(row.get("source_sha256") or "") for row in members if row.get("source_sha256")})
        pools = sorted({str(row.get("pool") or "unknown") for row in members})
        asset_types = sorted({str(row.get("asset_type") or row.get("source_asset_type") or "unknown") for row in members})
        resolution_kinds = sorted({kind for row in members for kind in row_resolution_kinds(row, operator_id)})
        parameter_evidence = sum(
            bool(row.get("parameter_evidence_status") == "verified_source_ast")
            or bool(row.get("parameters"))
            or any(isinstance(call, dict) and call.get("parameter_keys") for call in row.get("processing_calls") or [])
            for row in members
        )
        io_evidence = sum(bool(row.get("provider_io_contracts")) for row in members)
        processing_call_evidence = sum(int(row.get("processing_call_count") or 0) > 0 for row in members)
        assets.append(
            {
                "schema": SCHEMA,
                "asset_type": "processing_operator_asset",
                "asset_id": f"processing_operator:{digest(operator_id)}",
                "operator_id": operator_id,
                "support_rows": len(members),
                "unique_source_sha256": len(sources),
                "source_sha256": sources,
                "pool": pools,
                "observed_asset_types": asset_types,
                "resolution_kinds": resolution_kinds,
                "processing_call_evidence_rows": processing_call_evidence,
                "parameter_evidence_rows": parameter_evidence,
                "io_evidence_rows": io_evidence,
                "example_record_ids": [str(row.get("record_id") or row.get("review_id") or "") for row in members[:5]],
                "l3_mapping": "not_attempted_operator_asset_v1",
                "qualification_status": "candidate_only_operator_asset",
                "training_admission": "not_granted",
                "training_rows_emitted": 0,
                "provenance": {
                    "source_schema": sorted({str(row.get("schema") or "") for row in members}),
                    "candidate_only": True,
                },
            }
        )

    summary = {
        "schema": f"{SCHEMA}.summary",
        "input_rows": len(rows),
        "operator_input_rows": len(scoped_rows),
        "operator_assets": len(assets),
        "support_rows": sum(asset["support_rows"] for asset in assets),
        "unique_source_sha256": len({sha for asset in assets for sha in asset["source_sha256"]}),
        "parameter_evidence_rows": sum(asset["parameter_evidence_rows"] for asset in assets),
        "io_evidence_rows": sum(asset["io_evidence_rows"] for asset in assets),
        "processing_call_evidence_rows": sum(asset["processing_call_evidence_rows"] for asset in assets),
        "asset_type_filter": asset_type,
        "expected_operator_rows": expected_operator_rows,
        "expected_operator_rows_status": (
            "matched" if expected_operator_rows is not None and len(scoped_rows) == expected_operator_rows else "not_checked"
            if expected_operator_rows is None else "input_incomplete_or_count_mismatch"
        ),
        "l3_mapping": "unchanged",
        "training_admission": "not_granted_candidate_only_operator_asset_pool",
        "training_rows_emitted": 0,
        "formal_authority_modified": False,
        "parameter_evidence_availability": (
            "present" if any(
                row.get("parameter_evidence_status") is not None
                or row.get("parameters")
                or any(isinstance(call, dict) and call.get("parameter_keys") for call in row.get("processing_calls") or [])
                for row in scoped_rows
            ) else "not_carried_by_normalized_ledger"
        ),
        "io_evidence_availability": (
            "present" if any(row.get("provider_io_contracts") for row in scoped_rows) else "not_carried_by_normalized_ledger"
        ),
    }
    return assets, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-ledger", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-operator-rows", type=int, default=591)
    parser.add_argument("--asset-type", default="processing_operator")
    args = parser.parse_args()
    assets, summary = build_assets(
        read_jsonl(args.input_ledger),
        expected_operator_rows=args.expected_operator_rows,
        asset_type=args.asset_type,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    asset_path = args.output_dir / "processing_operator_assets_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    report_path = args.output_dir / "operator_asset_report_v1.md"
    asset_path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in assets), encoding="utf-8")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "# QGIS Processing operator asset census v1\n\n"
        "This is a candidate-only operator census over the normalized Asset Miner ledger. It does not infer L3 or emit training rows.\n\n"
        f"- Input rows: **{summary['input_rows']}**\n"
        f"- Operator input rows: **{summary['operator_input_rows']}**\n"
        f"- Unique operator IDs: **{summary['operator_assets']}**\n"
        f"- Unique source SHA across operators: **{summary['unique_source_sha256']}**\n"
        f"- Processing-call evidence rows: **{summary['processing_call_evidence_rows']}**\n"
        f"- Expected 591 operator-row check: **{summary['expected_operator_rows_status']}**\n"
        f"- Parameter-evidence rows: **{summary['parameter_evidence_rows']}**\n"
        f"- I/O-evidence rows: **{summary['io_evidence_rows']}**\n"
        f"- Parameter-evidence availability: **{summary['parameter_evidence_availability']}**\n"
        f"- I/O-evidence availability: **{summary['io_evidence_availability']}**\n"
        "- L3 mapping changed: **false**\n"
        "- Training rows emitted: **0**\n",
        encoding="utf-8",
    )
    hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in (asset_path, summary_path, report_path)}
    hashes["input_ledger"] = hashlib.sha256(args.input_ledger.read_bytes()).hexdigest()
    (args.output_dir / "hash_ledger_v1.json").write_text(json.dumps(hashes, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
