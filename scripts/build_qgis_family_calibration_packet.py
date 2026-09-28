#!/usr/bin/env python3
"""Build a source-disjoint calibration packet for a high-support family."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

try:
    from .expand_qgis_family_candidates import expand
except ImportError:
    from expand_qgis_family_candidates import expand


SCHEMA = "gis_recommend.qgis_family_calibration_packet.v1"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def build_packet(
    normalized_rows: list[dict[str, Any]],
    miner_rows: list[dict[str, Any]],
    *,
    target: list[str],
    calibration_sources: int = 20,
    holdout_sources: int = 20,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    candidates, expansion_summary = expand(normalized_rows, target=target)
    grouped: dict[str, list[dict[str, Any]]] = {}
    for candidate in candidates:
        grouped.setdefault(str(candidate.get("source_sha256") or ""), []).append(candidate)
    source_shas = sorted(sha for sha in grouped if len(sha) == 64)
    requested = calibration_sources + holdout_sources
    if len(source_shas) < requested:
        raise ValueError(f"family has {len(source_shas)} unique sources but {requested} requested")
    selected = source_shas[:requested]
    miner_by_id = {str(row.get("record_id")): row for row in miner_rows}
    packet: list[dict[str, Any]] = []
    for source_index, source_sha in enumerate(selected):
        split = "calibration" if source_index < calibration_sources else "holdout"
        for occurrence_index, candidate in enumerate(grouped[source_sha]):
            miner = miner_by_id.get(str(candidate.get("record_id")), {})
            packet.append({
                "schema": SCHEMA,
                "review_id": f"{split}_{source_index:03d}_{occurrence_index:02d}_{source_sha[:12]}",
                "split": split,
                "asset_type": "processing_family_calibration_candidate",
                "pool": candidate.get("pool"),
                "family_sequence": list(target),
                "family_sequence_key": "|".join(target),
                "matched_span": candidate.get("matched_span"),
                "full_parent_operator_sequence": candidate.get("full_parent_operator_sequence") or [],
                "record_id": candidate.get("record_id"),
                "source_sha256": source_sha,
                "parent_source_sha256": candidate.get("parent_source_sha256") or source_sha,
                "source_path": candidate.get("source_path"),
                "processing_operator_ids": candidate.get("full_parent_operator_sequence") or [],
                "processing_calls": miner.get("processing_calls") or [],
                "source_verified": bool(candidate.get("source_verified")),
                "candidate_only": True,
                "l3_mapping": "not_attempted_family_calibration_v1",
                "training_admission": "not_granted_family_calibration_v1",
                "training_rows_emitted": 0,
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
            })
    packet.sort(key=lambda row: (row["split"], row["source_sha256"], row["review_id"]))
    calibration = {row["source_sha256"] for row in packet if row["split"] == "calibration"}
    holdout = {row["source_sha256"] for row in packet if row["split"] == "holdout"}
    summary = {
        "schema": f"{SCHEMA}.summary",
        "target_family_sequence": target,
        "expansion_candidate_rows": expansion_summary["candidate_rows"],
        "expansion_unique_sources": expansion_summary["unique_source_sha256"],
        "packet_rows": len(packet),
        "packet_unique_sources": len({row["source_sha256"] for row in packet}),
        "calibration_source_count": len(calibration),
        "holdout_source_count": len(holdout),
        "calibration_rows": sum(row["split"] == "calibration" for row in packet),
        "holdout_rows": sum(row["split"] == "holdout" for row in packet),
        "source_sha_overlap": len(calibration & holdout),
        "all_source_verified": all(row["source_verified"] for row in packet),
        "parent_structure_count": len({tuple(row["full_parent_operator_sequence"]) for row in packet}),
        "training_rows_emitted": 0,
        "training_admission": "not_granted_family_calibration_v1",
        "l3_mapping": "unchanged",
    }
    return packet, summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--normalized-ledger", type=Path, required=True)
    parser.add_argument("--miner-ledger", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--target-sequence", required=True)
    parser.add_argument("--calibration-sources", type=int, default=20)
    parser.add_argument("--holdout-sources", type=int, default=20)
    args = parser.parse_args()
    target = [value.strip().lower() for value in args.target_sequence.replace(",", "|").split("|") if value.strip()]
    packet, summary = build_packet(read_jsonl(args.normalized_ledger), read_jsonl(args.miner_ledger), target=target, calibration_sources=args.calibration_sources, holdout_sources=args.holdout_sources)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    ledger = args.output_dir / "calibration_packet_v1.jsonl"
    ledger.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in packet), encoding="utf-8")
    summary_path = args.output_dir / "summary_v1.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    hashes = {ledger.name: hashlib.sha256(ledger.read_bytes()).hexdigest(), summary_path.name: hashlib.sha256(summary_path.read_bytes()).hexdigest()}
    (args.output_dir / "hash_ledger_v1.json").write_text(json.dumps(hashes, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
