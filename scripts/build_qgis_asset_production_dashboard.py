#!/usr/bin/env python3
"""Build a compact read-only dashboard for QGIS asset-production lanes."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

SCHEMA = "gis_recommend.qgis_asset_production_dashboard.v1"


def load(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def build_dashboard(normalization: dict[str, Any], lanes: list[dict[str, Any]], admission: dict[str, Any]) -> dict[str, Any]:
    counts = normalization.get("asset_type_counts") or {}
    pool_status = [
        {"pool": "processing_workflow", "rows": counts.get("processing_workflow", 0), "status": "family_production", "next": "calibration -> qualification -> dedup"},
        {"pool": "processing_operator", "rows": counts.get("processing_operator", 0), "status": "queued", "next": "operator grounding"},
        {"pool": "processing_implementation", "rows": counts.get("processing_implementation", 0), "status": "queued", "next": "semantic recovery"},
        {"pool": "processing_dynamic_candidate", "rows": counts.get("processing_dynamic_candidate", 0), "status": "deferred", "next": "bounded dynamic recovery"},
        {"pool": "api_semantic_unit", "rows": counts.get("api_semantic_unit", 0), "status": "queued", "next": "API -> GIS semantic -> L3"},
        {"pool": "api_pattern", "rows": counts.get("api_pattern", 0), "status": "queued", "next": "pattern qualification"},
        {"pool": "api_implementation_evidence", "rows": counts.get("api_implementation_evidence", 0), "status": "evidence_only", "next": "support other pools"},
        {"pool": "unresolved", "rows": counts.get("unresolved", 0), "status": "deferred", "next": "do not process yet"},
    ]
    return {
        "schema": SCHEMA,
        "raw_sources": normalization.get("input_rows", 0),
        "source_verified_rows": normalization.get("source_verified_rows", 0),
        "asset_pools": pool_status,
        "family_lanes": lanes,
        "family_candidate_rows": sum(int(lane.get("reviewed_rows", 0)) for lane in lanes),
        "family_silver_candidates_before_dedup": sum(int(lane.get("silver_candidates", 0)) for lane in lanes),
        "dedup_unique_silver_candidates": admission.get("silver_candidates", 0),
        "dedup_reject_rows": admission.get("quality_counts", {}).get("reject", 0),
        "gold_candidates": admission.get("gold_candidates", 0),
        "training_rows_emitted": admission.get("training_rows_emitted", 0),
        "authority_modified": admission.get("formal_authority_modified", False),
        "next_decision": "start independent intent review for the two dedup survivors; launch operator/API asset lanes in parallel",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--normalization", type=Path, required=True)
    parser.add_argument("--lane", type=Path, action="append", required=True)
    parser.add_argument("--admission", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    dashboard = build_dashboard(load(args.normalization), [load(path) for path in args.lane], load(args.admission))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.output_dir / "dashboard_v1.json"
    md_path = args.output_dir / "dashboard_v1.md"
    json_path.write_text(json.dumps(dashboard, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    lines = ["# QGIS asset production dashboard v1", "", f"- Raw sources: {dashboard['raw_sources']}", f"- SHA-verified rows: {dashboard['source_verified_rows']}", f"- Family candidates reviewed: {dashboard['family_candidate_rows']}", f"- Silver candidates before dedup: {dashboard['family_silver_candidates_before_dedup']}", f"- Unique Silver candidates after four-layer dedup: {dashboard['dedup_unique_silver_candidates']}", f"- Gold candidates: {dashboard['gold_candidates']}", f"- Training rows emitted: {dashboard['training_rows_emitted']}", "", "| Asset pool | Rows | Status | Next |", "|---|---:|---|---|"]
    lines.extend(f"| {row['pool']} | {row['rows']} | {row['status']} | {row['next']} |" for row in dashboard["asset_pools"])
    lines.extend(["", "| Family lane | Structural passed | Semantic Silver | Dedup unique |", "|---|---:|---:|---:|"])
    lines.extend(f"| {row['family']} | {row['structural_passed']} | {row['silver_candidates']} | {row['dedup_unique']} |" for row in dashboard["family_lanes"])
    md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    (args.output_dir / "hash_ledger_v1.json").write_text(json.dumps({path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in (json_path, md_path)}, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(dashboard, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
