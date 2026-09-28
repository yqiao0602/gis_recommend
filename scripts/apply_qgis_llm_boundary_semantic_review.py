"""Apply the independent semantic review for the 82 boundary proposals.

The review is intentionally an explicit, source-row keyed adjudication.  It
does not infer admission from mechanical flags and it never emits training
rows.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

WRONG_CHAIN: dict[int, str] = {
    1: "setAttributes calls are mutually exclusive gisOutput branches, but the proposal chains all six into one feature history.",
    6: "The two setGeometry calls are the if/else alternatives; both cannot occur in one execution path.",
    15: "The three setGeometry calls are alternative row/coordinate representations; chaining all alternatives is not one execution path.",
    21: "The proposal is empty (no selected steps, sink, or boundary), so it is not a semantic boundary.",
    22: "The source writes through provider.addFeatures and writer.addFeature; the proposal silently selects one of two sinks and omits the other.",
}

TRUNCATED_CHAIN: dict[int, str] = {
    8: "The proposal starts at intersection() but omits the source-visible intersects() guard that controls whether the operation executes.",
    23: "The selected addAttribute call is inside a fieldList loop; selecting one iteration followed by export does not represent the complete schema-building boundary.",
}

BRANCH_NOTES: dict[int, str] = {
    11: "Accepted as the first geometry-type branch; the second branch is an alternative terminal path, not a required predecessor.",
    16: "Accepted as one of four mutually exclusive output branches; omitted branches are not a truncation.",
    20: "Accepted as the first terminal branch; the other polygon cases are alternatives.",
    39: "Accepted as the second output branch; the earlier point sink is a separate output path.",
    43: "Accepted as the first hull-output branch; the later else branch is an alternative terminal path.",
    57: "Accepted as the write-point branch; the later delete-close-points loop is a separate mutation phase after the sink.",
    71: "Accepted as the per-feature convex-hull branch; the all-features branch is an alternative terminal path.",
}


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    rows = load_jsonl(args.input)
    if len(rows) != 82:
        raise ValueError(f"expected exactly 82 proposals, got {len(rows)}")

    reviewed: list[dict[str, Any]] = []
    for number, row in enumerate(rows, 1):
        wrong = number in WRONG_CHAIN
        truncated = number in TRUNCATED_CHAIN
        notes = WRONG_CHAIN.get(number) or TRUNCATED_CHAIN.get(number) or BRANCH_NOTES.get(number, "")
        reviewed.append(
            {
                **row,
                "human_wrong_chain": "yes" if wrong else "no",
                "human_chain_truncated": "yes" if truncated else "no",
                "human_boundary_correct": "no" if wrong or truncated else "yes",
                "human_notes": notes,
                "semantic_review_version": "qgis_api_llm_boundary_semantic_review_v1",
                "training_rows_emitted": 0,
                "training_admission": "not_granted_llm_boundary_audit",
            }
        )

    args.output_dir.mkdir(parents=True, exist_ok=True)
    reviewed_path = args.output_dir / "reviewed_audit_packet_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    report_path = args.output_dir / "report_v1.md"
    reviewed_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in reviewed),
        encoding="utf-8",
    )
    counts = Counter(row["review_split"] for row in reviewed)
    by_split: dict[str, dict[str, int]] = {}
    for split in sorted(counts):
        subset = [row for row in reviewed if row["review_split"] == split]
        by_split[split] = {
            "rows": len(subset),
            "boundary_correct": sum(row["human_boundary_correct"] == "yes" for row in subset),
            "wrong_chain": sum(row["human_wrong_chain"] == "yes" for row in subset),
            "chain_truncated": sum(row["human_chain_truncated"] == "yes" for row in subset),
        }
    summary = {
        "schema": "gis_recommend.qgis_api_llm_boundary_semantic_review_summary.v1",
        "input_sha256": sha256(args.input),
        "rows": len(reviewed),
        "boundary_correct": sum(row["human_boundary_correct"] == "yes" for row in reviewed),
        "wrong_chain": sum(row["human_wrong_chain"] == "yes" for row in reviewed),
        "chain_truncated": sum(row["human_chain_truncated"] == "yes" for row in reviewed),
        "training_rows_emitted": 0,
        "training_admission": "not_granted_llm_boundary_audit",
        "by_split": by_split,
        "wrong_chain_row_numbers": sorted(WRONG_CHAIN),
        "chain_truncated_row_numbers": sorted(TRUNCATED_CHAIN),
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    lines = [
        "# QGIS API LLM Boundary Semantic Review v1",
        "",
        f"Input SHA256: `{summary['input_sha256']}`",
        "",
        "This is an independent source-window review of proposal semantics. It is candidate-only; no L3, training, or authority admission is granted.",
        "",
        "| split | rows | boundary correct | wrong chain | chain truncated |",
        "|---|---:|---:|---:|---:|",
    ]
    for split, stats in by_split.items():
        lines.append(f"| {split} | {stats['rows']} | {stats['boundary_correct']} | {stats['wrong_chain']} | {stats['chain_truncated']} |")
    lines.extend([
        f"| total | {summary['rows']} | {summary['boundary_correct']} | {summary['wrong_chain']} | {summary['chain_truncated']} |",
        "",
        "## Non-passing rows",
        "",
        "| row | split | record_id | decision | reason |",
        "|---:|---|---|---|---|",
    ])
    for number, row in enumerate(reviewed, 1):
        if row["human_boundary_correct"] == "yes":
            continue
        decision = "wrong_chain" if row["human_wrong_chain"] == "yes" else "chain_truncated"
        lines.append(f"| {number} | {row['review_split']} | `{row['record_id']}` | {decision} | {row['human_notes']} |")
    lines.extend([
        "",
        "## Interpretation",
        "",
        "Mechanical edge differences are not automatically errors: source-backed branch selection is accepted when the selected branch is a complete single-sink path. The holdout contains semantic failures, so the LLM boundary rule is not promoted and remains isolated.",
    ])
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")

    ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "inputs": {args.input.name: {"sha256": sha256(args.input), "bytes": args.input.stat().st_size}},
        "artifacts": {path.name: {"sha256": sha256(path), "bytes": path.stat().st_size} for path in (reviewed_path, summary_path, report_path)},
    }
    (args.output_dir / "hash_ledger_v1.json").write_text(json.dumps(ledger, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
