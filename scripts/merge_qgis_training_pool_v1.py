#!/usr/bin/env python3
"""Final merged admission: audited 506 + 120 pattern candidates + 3 standalone.

This builds the official QGIS training pool the user asked for: one merge-level
admission with cross-pool dedup across the three sources, producing a single
versioned ledger with per-row provenance and a structure report (single/multi
step, unique L3 sequences, unique task semantics, workflow-structure keys,
length bands). The pattern candidates already passed the 508-pool cross-dedup in
their own consumption stage and the audited 506 already had its 2 duplicates
removed, so this stage re-checks everything jointly rather than trusting the
prior stages' arithmetic — including the 3 standalone rows which have never been
cross-checked against anything.

Dedup layers (all re-applied jointly here):
1. sample_id identity (same row twice),
2. source_sha256 + span overlap (same source evidence),
3. exact L3 sequence + identical task text (semantic twin).

Nothing is a training row: the pool is `admitted_train_only_candidate_v1`,
consumption into a training run is the user's next decision.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

SCHEMA = "gis_recommend.qgis_training_pool_merged_v1"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _span_key(row: dict[str, Any]) -> tuple:
    span = row.get("span") or row.get("source_span") or {}
    segs = span.get("segments") or ([span] if span.get("line_start") else [])
    lines = tuple(sorted((s.get("line_start"), s.get("line_end")) for s in segs))
    return (str(row.get("source_sha256") or ""), lines)


def merge(
    existing: list[dict[str, Any]],
    patterns: list[dict[str, Any]],
    standalone: list[dict[str, Any]],
    audit_verdicts: dict[str, dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    pool: list[dict[str, Any]] = []
    rejects: list[dict[str, Any]] = []
    seen_sample: dict[str, str] = {}
    seen_source_span: dict[tuple, str] = {}
    seen_seq_text: dict[tuple, str] = {}

    def admit(row: dict[str, Any], *, origin: str, weight: float, verdict: str) -> None:
        sid = str(row.get("sample_id") or row.get("record_id") or "")
        l3 = [c for c in (row.get("l3_codes") or row.get("l3_sequence_codes") or []) if str(c).startswith("L3")]
        if not l3:  # pattern/standalone rows carry l3_sequence as codes
            l3 = list(row.get("l3_sequence") or [])
        text = str(row.get("task_description") or row.get("task_text") or row.get("task") or "")
        entry = {
            "schema": SCHEMA,
            "sample_id": f"qgis_pool_v1_{sid}" if not sid.startswith("qgis_pool_v1_") else sid,
            "origin": origin,
            "source_record_id": row.get("record_id"),
            "source_sha256": row.get("source_sha256"),
            "l3_codes": ["<START>"] + l3 + ["<END>"],
            "n_steps": len(l3),
            "task_text": text,
            "sample_weight": weight,
            "audit_verdict": verdict,
            "training_admission": "admitted_train_only_candidate_v1",
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
            "training_rows_emitted": 0,
        }
        if sid in seen_sample:
            rejects.append({**entry, "reject_reason": f"sample_id_duplicate_of:{seen_sample[sid]}"})
            return
        span = _span_key(row)
        if span[0] and span in seen_source_span:
            rejects.append({**entry, "reject_reason": f"source_span_duplicate_of:{seen_source_span[span]}"})
            return
        seq_text = (tuple(l3), text)
        if seq_text in seen_seq_text:
            rejects.append({**entry, "reject_reason": f"l3_sequence_plus_text_duplicate_of:{seen_seq_text[seq_text]}"})
            return
        seen_sample[sid] = sid
        if span[0]:
            seen_source_span[span] = sid
        seen_seq_text[seq_text] = sid
        pool.append(entry)

    for row in existing:
        verdict = audit_verdicts.get(str(row["sample_id"]), {})
        if verdict.get("verdict") == "REJECT":
            continue  # the 2 audited duplicates stay out
        admit(row, origin="audited_existing_506", weight=float(row.get("_training_quality", {}).get("sample_weight") or 0.7), verdict=verdict.get("verdict", "SILVER"))
    for row in patterns:
        admit(row, origin="api_pattern_v2", weight=1.0, verdict="NEW_SILVER_PATTERN")
    for row in standalone:
        admit(row, origin="api_standalone_v2", weight=0.7, verdict="NEW_SILVER_STANDALONE")

    multi = [row for row in pool if row["n_steps"] >= 2]
    single = [row for row in pool if row["n_steps"] == 1]
    unique_l3 = {tuple(row["l3_codes"][1:-1]) for row in pool}
    unique_texts = {row["task_text"] for row in pool}
    summary = {
        "schema": f"{SCHEMA}.summary",
        "input": {"audited_existing": len(existing), "pattern_candidates": len(patterns), "standalone_candidates": len(standalone)},
        "cross_pool_rejects": len(rejects),
        "reject_reasons": dict(sorted(Counter(r["reject_reason"].split(":")[0] for r in rejects).items())),
        "final_pool_size": len(pool),
        "single_step": len(single),
        "multi_step": len(multi),
        "unique_l3_sequences": len(unique_l3),
        "unique_task_texts": len(unique_texts),
        "length_bands": {
            "1": len(single),
            "2-3": sum(1 for r in multi if r["n_steps"] <= 3),
            "4-7": sum(1 for r in multi if 4 <= r["n_steps"] <= 7),
            "8+": sum(1 for r in multi if r["n_steps"] >= 8),
        },
        "origin_counts": dict(sorted(Counter(row["origin"] for row in pool).items())),
        "weight_counts": dict(sorted(Counter(str(row["sample_weight"]) for row in pool).items())),
        "training_rows_emitted": 0,
        "training_admission": "admitted_train_only_candidate_v1",
        "formal_authority_modified": False,
    }
    return pool + [dict(r, in_pool=False) for r in rejects], summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--existing-508", type=Path, required=True)
    parser.add_argument("--pattern-candidates", type=Path, required=True)
    parser.add_argument("--standalone-candidates", type=Path, required=True)
    parser.add_argument("--audit-verdicts", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    audit = {str(entry["sample_id"]): entry for entry in json.loads(args.audit_verdicts.read_text(encoding="utf-8"))}
    pool, summary = merge(
        read_jsonl(args.existing_508),
        [r for r in read_jsonl(args.pattern_candidates) if r.get("stage") is None],
        json.loads(args.standalone_candidates.read_text(encoding="utf-8")),
        audit,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    pool_path = args.output_dir / "qgis_training_pool_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    pool_path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in pool), encoding="utf-8")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    hashes = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in (pool_path, summary_path)}
    for name, path in (("existing_508_input", args.existing_508), ("pattern_input", args.pattern_candidates), ("standalone_input", args.standalone_candidates), ("audit_input", args.audit_verdicts)):
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    (args.output_dir / "hash_ledger_v1.json").write_text(json.dumps(hashes, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
