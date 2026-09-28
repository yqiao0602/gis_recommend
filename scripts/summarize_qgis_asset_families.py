#!/usr/bin/env python3
"""Summarize normalized QGIS assets into bounded, auditable families.

Families are observational clusters, not inferred workflows.  The command is
used to choose a next semantic-recovery lane; it never maps L3 or emits
training rows.  Processing and API assets are kept in separate clusters.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


SCHEMA = "gis_recommend.qgis_asset_family_summary.v1"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _family_key(row: dict[str, Any]) -> tuple[str, str, str]:
    asset_type = str(row.get("asset_type") or "unresolved")
    keys = row.get("dedup_keys") or {}
    if asset_type.startswith("processing_"):
        sequence = str(keys.get("operator_sequence") or "")
    else:
        sequence = str(keys.get("semantic_operation_sequence") or keys.get("api_method_sequence") or "")
    return asset_type, str(row.get("pool") or "unknown"), sequence or "<empty>"


def summarize(rows: list[dict[str, Any]], *, min_count: int = 1, top: int = 0) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[_family_key(row)].append(row)
    families: list[dict[str, Any]] = []
    for (asset_type, pool, sequence), members in groups.items():
        if len(members) < min_count:
            continue
        sources = sorted({str(item.get("source_sha256") or "") for item in members if item.get("source_sha256")})
        families.append(
            {
                "schema": SCHEMA,
                "family_id": hashlib.sha256(f"{asset_type}\0{pool}\0{sequence}".encode("utf-8")).hexdigest()[:16],
                "asset_type": asset_type,
                "pool": pool,
                "observed_sequence": [] if sequence == "<empty>" else sequence.split("|"),
                "observed_sequence_key": sequence,
                "support_rows": len(members),
                "unique_sources": len(sources),
                "example_record_ids": [item.get("record_id") for item in members[:5]],
                "example_source_sha256": sources[:3],
                "next_gate": str(members[0].get("next_gate") or "unrouted"),
                "candidate_only": True,
                "l3_mapping": "not_attempted_asset_family_summary_v1",
                "training_rows_emitted": 0,
            }
        )
    families.sort(key=lambda item: (-item["support_rows"], -item["unique_sources"], item["family_id"]))
    if top > 0:
        families = families[:top]
    summary = {
        "schema": f"{SCHEMA}.summary",
        "input_rows": len(rows),
        "family_count": len(families),
        "min_count": min_count,
        "top": top,
        "asset_type_counts": {},
        "training_rows_emitted": 0,
        "training_admission": "not_granted_asset_family_summary_v1",
        "l3_mapping": "unchanged",
    }
    for family in families:
        summary["asset_type_counts"][family["asset_type"]] = summary["asset_type_counts"].get(family["asset_type"], 0) + 1
    summary["asset_type_counts"] = dict(sorted(summary["asset_type_counts"].items()))
    return families, summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-ledger", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--min-count", type=int, default=1)
    parser.add_argument("--top", type=int, default=0)
    args = parser.parse_args()
    families, summary = summarize(read_jsonl(args.input_ledger), min_count=args.min_count, top=args.top)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    ledger = args.output_dir / "qgis_asset_families_v1.jsonl"
    ledger.write_text("".join(json.dumps(item, ensure_ascii=False, sort_keys=True) + "\n" for item in families), encoding="utf-8")
    summary_path = args.output_dir / "summary_v1.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    hashes = {ledger.name: hashlib.sha256(ledger.read_bytes()).hexdigest(), summary_path.name: hashlib.sha256(summary_path.read_bytes()).hexdigest()}
    (args.output_dir / "hash_ledger_v1.json").write_text(json.dumps(hashes, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
