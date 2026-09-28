#!/usr/bin/env python3
"""Build a source-disjoint review packet for one normalized asset family.

The packet joins normalized semantic fields with Asset Miner call evidence and
creates a deterministic calibration/holdout split by source SHA.  It is
candidate-only: no L3 mapping, training export, or authority mutation occurs.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


SCHEMA = "gis_recommend.qgis_asset_family_review_packet.v1"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _key(row: dict[str, Any]) -> str:
    keys = row.get("dedup_keys") or {}
    return str(keys.get("operator_sequence") or keys.get("semantic_operation_sequence") or "")


def build_packet(
    normalized_rows: list[dict[str, Any]],
    miner_rows: list[dict[str, Any]],
    *,
    asset_type: str,
    pool: str,
    sequence: str,
    calibration_count: int,
    holdout_count: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    miner_by_id = {str(row.get("record_id")): row for row in miner_rows}
    selected = [
        row for row in normalized_rows
        if row.get("asset_type") == asset_type and row.get("pool") == pool and _key(row) == sequence
    ]
    selected.sort(key=lambda row: (str(row.get("source_sha256") or ""), str(row.get("record_id") or "")))
    requested = calibration_count + holdout_count
    if requested <= 0:
        raise ValueError("calibration_count + holdout_count must be positive")
    if len(selected) < requested:
        raise ValueError(f"family has {len(selected)} rows but {requested} requested")
    selected = selected[:requested]
    packet: list[dict[str, Any]] = []
    for index, row in enumerate(selected):
        split = "calibration" if index < calibration_count else "holdout"
        miner = miner_by_id.get(str(row.get("record_id")), {})
        source_sha = str(row.get("source_sha256") or "")
        packet.append({
            "schema": SCHEMA,
            "review_id": f"{split}_{index:03d}_{source_sha[:12]}",
            "split": split,
            "asset_type": asset_type,
            "pool": pool,
            "family_sequence": sequence.split("|") if sequence else [],
            "family_sequence_key": sequence,
            "record_id": row.get("record_id"),
            "source_sha256": source_sha,
            "parent_source_sha256": row.get("parent_source_sha256") or source_sha,
            "source_path": row.get("source_path"),
            "processing_operator_ids": row.get("processing_operator_ids") or [],
            "api_methods": row.get("api_methods") or [],
            "semantic_operations": row.get("semantic_operations") or [],
            "processing_calls": miner.get("processing_calls") or [],
            "semantic_calls": miner.get("semantic_calls") or [],
            "plumbing_calls": miner.get("plumbing_calls") or [],
            "source_verified": bool(row.get("source_verified")),
            "candidate_only": True,
            "l3_mapping": "not_attempted_asset_family_review_v1",
            "training_admission": "not_granted_asset_family_review_v1",
            "training_rows_emitted": 0,
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
        })
    source_shas = [str(row.get("source_sha256") or "") for row in packet]
    summary = {
        "schema": f"{SCHEMA}.summary",
        "asset_type": asset_type,
        "pool": pool,
        "family_sequence_key": sequence,
        "family_rows_available": len([row for row in normalized_rows if row.get("asset_type") == asset_type and row.get("pool") == pool and _key(row) == sequence]),
        "packet_rows": len(packet),
        "calibration_rows": sum(row["split"] == "calibration" for row in packet),
        "holdout_rows": sum(row["split"] == "holdout" for row in packet),
        "source_sha_overlap": len(set(source_shas[:calibration_count]) & set(source_shas[calibration_count:])),
        "source_sha_unique": len(set(source_shas)),
        "all_source_verified": all(row["source_verified"] for row in packet),
        "training_rows_emitted": 0,
        "training_admission": "not_granted_asset_family_review_v1",
        "l3_mapping": "unchanged",
    }
    return packet, summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--normalized-ledger", type=Path, required=True)
    parser.add_argument("--miner-ledger", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--asset-type", required=True)
    parser.add_argument("--pool", required=True)
    parser.add_argument("--sequence", required=True, help="pipe-separated observed sequence")
    parser.add_argument("--calibration-count", type=int, default=3)
    parser.add_argument("--holdout-count", type=int, default=4)
    args = parser.parse_args()
    packet, summary = build_packet(read_jsonl(args.normalized_ledger), read_jsonl(args.miner_ledger), asset_type=args.asset_type, pool=args.pool, sequence=args.sequence, calibration_count=args.calibration_count, holdout_count=args.holdout_count)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    ledger = args.output_dir / "review_packet_v1.jsonl"
    ledger.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in packet), encoding="utf-8")
    summary_path = args.output_dir / "summary_v1.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    hashes = {ledger.name: hashlib.sha256(ledger.read_bytes()).hexdigest(), summary_path.name: hashlib.sha256(summary_path.read_bytes()).hexdigest()}
    (args.output_dir / "hash_ledger_v1.json").write_text(json.dumps(hashes, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
