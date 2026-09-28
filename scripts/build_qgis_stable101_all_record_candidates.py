#!/usr/bin/env python3
"""Adapt all stable101 newly-complete records for source provenance replay."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


def build(input_jsonl: Path) -> list[dict]:
    rows = [
        json.loads(line)
        for line in input_jsonl.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    indices = [int(row["record_index"]) for row in rows]
    if len(indices) != len(set(indices)):
        raise ValueError("record_index must be unique")
    candidates = []
    for review_index, row in enumerate(
        sorted(rows, key=lambda item: int(item["record_index"])), start=1
    ):
        candidate = dict(row)
        candidate.update(
            {
                "review_index": review_index,
                "representative_record_index": int(row["record_index"]),
                "representative_record_sha256": row["record_sha256"],
                "representative_source": row.get("source", ""),
                "selection_stratum": "all_stable101_newly_complete_records",
                "selection_rationale": [
                    "record-level provenance replay",
                    "no chain-level representative collapse",
                ],
                "training_admission": "not_granted_source_replay_only",
            }
        )
        candidates.append(candidate)
    return candidates


def main(argv: list[str] | None = None) -> Path:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input-jsonl", type=Path, required=True)
    parser.add_argument("--output-jsonl", type=Path, required=True)
    args = parser.parse_args(argv)
    rows = build(args.input_jsonl)
    args.output_jsonl.parent.mkdir(parents=True, exist_ok=True)
    args.output_jsonl.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )
    return args.output_jsonl


if __name__ == "__main__":
    main()
