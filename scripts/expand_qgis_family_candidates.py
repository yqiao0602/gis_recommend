#!/usr/bin/env python3
"""Apply a calibrated contiguous Processing-family rule at scale.

The rule only selects already-discovered literal Processing call sequences
that contain a target subsequence.  It never invents calls, slices source into
new workflow rows, maps L3, or emits training data.  Each output retains the
full parent sequence and the exact matched span for later qualification.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any


SCHEMA = "gis_recommend.qgis_family_expansion.v1"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _sequence(row: dict[str, Any]) -> list[str]:
    return [str(value).strip().lower() for value in row.get("processing_operator_ids") or [] if str(value).strip()]


def _find_spans(sequence: list[str], target: list[str]) -> list[list[int]]:
    if not target or len(target) > len(sequence):
        return []
    return [[index, index + len(target)] for index in range(len(sequence) - len(target) + 1) if sequence[index:index + len(target)] == target]


def expand(rows: list[dict[str, Any]], *, target: list[str]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    workflows = [row for row in rows if row.get("asset_type") == "processing_workflow"]
    candidates: list[dict[str, Any]] = []
    for row in workflows:
        sequence = _sequence(row)
        spans = _find_spans(sequence, target)
        if not spans:
            continue
        source_sha = str(row.get("source_sha256") or "")
        parent = str(row.get("parent_source_sha256") or source_sha)
        for ordinal, span in enumerate(spans):
            candidate_id = hashlib.sha256(f"{source_sha}\0{target}\0{span[0]}\0{span[1]}".encode("utf-8")).hexdigest()[:24]
            candidates.append({
                "schema": SCHEMA,
                "candidate_id": candidate_id,
                "record_id": row.get("record_id"),
                "pool": row.get("pool"),
                "asset_type": "processing_family_candidate",
                "family_rule": "contiguous_literal_processing_subsequence_v1",
                "family_sequence": target,
                "family_sequence_key": "|".join(target),
                "match_ordinal": ordinal,
                "matched_span": {"start_index": span[0], "end_index_exclusive": span[1]},
                "full_parent_operator_sequence": sequence,
                "source_sha256": source_sha,
                "parent_source_sha256": parent,
                "source_path": row.get("source_path"),
                "source_verified": bool(row.get("source_verified")),
                "parent_record_id": row.get("record_id"),
                "parent_asset_type": row.get("source_asset_type") or row.get("asset_type"),
                "candidate_only": True,
                "l3_mapping": "not_attempted_family_expansion_v1",
                "training_admission": "not_granted_family_expansion_v1",
                "training_rows_emitted": 0,
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
            })
    candidates.sort(key=lambda row: (str(row.get("source_sha256") or ""), int(row["matched_span"]["start_index"]), row["candidate_id"]))
    counts = Counter(tuple(row["full_parent_operator_sequence"]) for row in candidates)
    summary = {
        "schema": f"{SCHEMA}.summary",
        "input_rows": len(rows),
        "processing_workflow_rows": len(workflows),
        "target_family_sequence": target,
        "matched_parent_rows": len({row["parent_source_sha256"] for row in candidates}),
        "candidate_rows": len(candidates),
        "unique_source_sha256": len({row["source_sha256"] for row in candidates if row["source_sha256"]}),
        "unique_parent_source_sha256": len({row["parent_source_sha256"] for row in candidates if row["parent_source_sha256"]}),
        "unique_full_parent_sequences": len(counts),
        "matched_multiple_spans": sum(value > 1 for value in Counter((row["source_sha256"], row["family_sequence_key"]) for row in candidates).values()),
        "all_source_verified": all(row["source_verified"] for row in candidates),
        "training_rows_emitted": 0,
        "training_admission": "not_granted_family_expansion_v1",
        "l3_mapping": "unchanged",
    }
    return candidates, summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--normalized-ledger", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--target-sequence", required=True, help="pipe-separated Processing IDs")
    args = parser.parse_args()
    target = [value.strip().lower() for value in args.target_sequence.split("|") if value.strip()]
    if not target:
        raise ValueError("target sequence cannot be empty")
    candidates, summary = expand(read_jsonl(args.normalized_ledger), target=target)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    ledger = args.output_dir / "family_candidates_v1.jsonl"
    ledger.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in candidates), encoding="utf-8")
    summary_path = args.output_dir / "summary_v1.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    hashes = {ledger.name: hashlib.sha256(ledger.read_bytes()).hexdigest(), summary_path.name: hashlib.sha256(summary_path.read_bytes()).hexdigest()}
    (args.output_dir / "hash_ledger_v1.json").write_text(json.dumps(hashes, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
