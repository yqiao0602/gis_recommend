#!/usr/bin/env python3
"""Generate reviewable multi-solution workflow candidates from QG train data.

This is an offline candidate-mining tool. It does not create training labels,
mutate quality-gate data, start training, or write checkpoints.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gis_recommend.config.transformer_config import OUTPUT_DIR  # noqa: E402


SCHEMA_VERSION = "gis_recommend.v4_qg.multisolution_candidates.v1"
DEFAULT_QG_DIR = OUTPUT_DIR / "pipeline" / "step8_quality_gate"
DEFAULT_DATA_PATH = DEFAULT_QG_DIR / "labeled_workflows_l3_v4_quality_gate.json"
DEFAULT_SPLITS_PATH = DEFAULT_QG_DIR / "dataset_splits_v4_quality_gate.json"
DEFAULT_OUTPUT_DIR = OUTPUT_DIR / "v4_qg_multisolution_candidates"


@dataclass(frozen=True)
class CandidateGenerationResult:
    candidates: list[dict]
    summary: dict


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path) -> dict:
    with Path(path).open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return payload


def _load_workflows(path: Path) -> list[dict]:
    payload = _load_json(path)
    workflows = payload.get("labeled_workflows", [])
    if not isinstance(workflows, list):
        raise ValueError(f"Invalid labeled_workflows in {path}")
    return workflows


def _content_tokens(tokens: Sequence[int]) -> list[int]:
    return [int(token) for token in tokens if int(token) >= 0]


def _task_metadata(workflow: dict) -> dict:
    return workflow.get("task_metadata", {}) or {}


def _task_type(workflow: dict) -> str:
    return str(_task_metadata(workflow).get("task_type", "") or "Unknown")


def _task_text(workflow: dict) -> str:
    meta = _task_metadata(workflow)
    return " ".join(
        str(meta.get(key, "") or "")
        for key in ("task_type", "task_name", "task_description")
    ).strip()


def _word_set(text: str) -> set[str]:
    cleaned = (
        text.lower()
        .replace("_", " ")
        .replace("-", " ")
        .replace("/", " ")
        .replace(",", " ")
    )
    return {part for part in cleaned.split() if len(part) > 1}


def _jaccard_text(a: str, b: str) -> float:
    wa = _word_set(a)
    wb = _word_set(b)
    if not wa or not wb:
        return 0.0
    return len(wa & wb) / len(wa | wb)


def _set_f1(a: Sequence[int], b: Sequence[int]) -> float:
    ca = Counter(a)
    cb = Counter(b)
    if not ca or not cb:
        return 0.0
    overlap = sum(min(ca[token], cb[token]) for token in ca)
    precision = overlap / max(sum(ca.values()), 1)
    recall = overlap / max(sum(cb.values()), 1)
    return 2 * precision * recall / (precision + recall) if precision + recall else 0.0


def _lcs_ratio(a: Sequence[int], b: Sequence[int]) -> float:
    if not a or not b:
        return 0.0
    prev = [0] * (len(b) + 1)
    for x in a:
        curr = [0] * (len(b) + 1)
        for j, y in enumerate(b, 1):
            curr[j] = prev[j - 1] + 1 if x == y else max(prev[j], curr[j - 1])
        prev = curr
    return prev[-1] / max(len(a), len(b), 1)


def _canonical_pair_key(a: Sequence[int], b: Sequence[int]) -> tuple[tuple[int, ...], tuple[int, ...]]:
    left = tuple(a)
    right = tuple(b)
    return (left, right) if left <= right else (right, left)


def _candidate_row(
    *,
    left_train_pos: int,
    right_train_pos: int,
    left_index: int,
    right_index: int,
    left_workflow: dict,
    right_workflow: dict,
    min_set_f1: float,
    max_length_delta: int,
    min_text_jaccard: float,
    high_precision_set_f1: float,
    high_precision_lcs_ratio: float,
    high_precision_max_length_delta: int,
) -> dict:
    left_tokens = _content_tokens(left_workflow.get("l3_sequence", []))
    right_tokens = _content_tokens(right_workflow.get("l3_sequence", []))
    task_type = _task_type(left_workflow)
    set_f1 = _set_f1(left_tokens, right_tokens)
    lcs_ratio = _lcs_ratio(left_tokens, right_tokens)
    length_delta = abs(len(left_tokens) - len(right_tokens))
    text_jaccard = _jaccard_text(_task_text(left_workflow), _task_text(right_workflow))

    passed = ["same_task_type"]
    rejected = []
    if set_f1 >= min_set_f1:
        passed.append("set_overlap")
    else:
        rejected.append("set_overlap_below_threshold")
    if length_delta <= max_length_delta:
        passed.append("length_delta")
    else:
        rejected.append("length_delta_above_threshold")
    if text_jaccard >= min_text_jaccard:
        passed.append("text_similarity")
    else:
        rejected.append("text_similarity_below_threshold")

    auto_label = "review_candidate" if not rejected else "rejected"
    if auto_label == "review_candidate":
        review_bucket = (
            "high_precision_review_candidate"
            if set_f1 >= high_precision_set_f1
            and lcs_ratio >= high_precision_lcs_ratio
            and length_delta <= high_precision_max_length_delta
            else "boundary_review_candidate"
        )
    else:
        review_bucket = "auto_rejected_control"
    left_meta = _task_metadata(left_workflow)
    right_meta = _task_metadata(right_workflow)
    return {
        "candidate_id": f"train{left_train_pos}_train{right_train_pos}",
        "auto_label": auto_label,
        "task_type": task_type,
        "left_workflow_index": int(left_index),
        "right_workflow_index": int(right_index),
        "left_task_name": str(left_meta.get("task_name", "")),
        "right_task_name": str(right_meta.get("task_name", "")),
        "left_tokens": list(left_tokens),
        "right_tokens": list(right_tokens),
        "left_len": len(left_tokens),
        "right_len": len(right_tokens),
        "length_delta": int(length_delta),
        "set_f1": round(set_f1, 8),
        "lcs_ratio": round(lcs_ratio, 8),
        "text_jaccard": round(text_jaccard, 8),
        "passed_checks": passed,
        "rejection_reasons": rejected,
        "review_bucket": review_bucket,
        "human_label": "",
        "review_notes": "",
    }


def generate_candidates(
    workflows: Sequence[dict],
    splits: dict,
    *,
    max_pairs_per_task_type: int = 500,
    min_set_f1: float = 0.8,
    max_length_delta: int = 2,
    min_text_jaccard: float = 0.15,
    high_precision_set_f1: float = 0.95,
    high_precision_lcs_ratio: float = 0.7,
    high_precision_max_length_delta: int = 1,
) -> CandidateGenerationResult:
    """Generate same-task-type candidate pairs from train split only."""
    train_indices = [int(index) for index in splits.get("train_indices", [])]
    by_task: dict[str, list[tuple[int, int, dict]]] = defaultdict(list)
    for train_pos, index in enumerate(train_indices):
        if 0 <= index < len(workflows):
            workflow = workflows[index]
            by_task[_task_type(workflow)].append((train_pos, index, workflow))

    candidates: list[dict] = []
    seen_pairs: set[tuple[tuple[int, ...], tuple[int, ...]]] = set()
    for task_type in sorted(by_task):
        rows = by_task[task_type]
        generated_for_task = 0
        for i, (left_pos, left_index, left_workflow) in enumerate(rows):
            for right_pos, right_index, right_workflow in rows[i + 1:]:
                left_tokens = _content_tokens(left_workflow.get("l3_sequence", []))
                right_tokens = _content_tokens(right_workflow.get("l3_sequence", []))
                if not left_tokens or not right_tokens or left_tokens == right_tokens:
                    continue
                pair_key = _canonical_pair_key(left_tokens, right_tokens)
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)
                candidates.append(
                    _candidate_row(
                        left_train_pos=left_pos,
                        right_train_pos=right_pos,
                        left_index=left_index,
                        right_index=right_index,
                        left_workflow=left_workflow,
                        right_workflow=right_workflow,
                        min_set_f1=min_set_f1,
                        max_length_delta=max_length_delta,
                        min_text_jaccard=min_text_jaccard,
                        high_precision_set_f1=high_precision_set_f1,
                        high_precision_lcs_ratio=high_precision_lcs_ratio,
                        high_precision_max_length_delta=high_precision_max_length_delta,
                    )
                )
                generated_for_task += 1
                if generated_for_task >= max_pairs_per_task_type:
                    break
            if generated_for_task >= max_pairs_per_task_type:
                break

    counts = dict(Counter(row["auto_label"] for row in candidates))
    bucket_counts = dict(Counter(row["review_bucket"] for row in candidates))
    for key in ("review_candidate", "rejected"):
        counts.setdefault(key, 0)
    for key in ("high_precision_review_candidate", "boundary_review_candidate", "auto_rejected_control"):
        bucket_counts.setdefault(key, 0)
    return CandidateGenerationResult(
        candidates=candidates,
        summary={
            "schema_version": SCHEMA_VERSION,
            "counts": counts,
            "review_bucket_counts": bucket_counts,
            "total_candidates": len(candidates),
            "train_samples": len(train_indices),
            "task_type_count": len(by_task),
            "thresholds": {
                "min_set_f1": float(min_set_f1),
                "max_length_delta": int(max_length_delta),
                "min_text_jaccard": float(min_text_jaccard),
                "high_precision_set_f1": float(high_precision_set_f1),
                "high_precision_lcs_ratio": float(high_precision_lcs_ratio),
                "high_precision_max_length_delta": int(high_precision_max_length_delta),
            },
        },
    )


def build_human_review_packet(
    rows: Sequence[dict],
    *,
    max_review_rows: int,
    per_task_type_cap: int,
    control_review_rows: int = 0,
    seed: int,
) -> list[dict]:
    """Select capped, task-balanced review rows from auto review candidates."""
    rng = random.Random(int(seed))
    by_task: dict[str, list[dict]] = defaultdict(list)
    controls: list[dict] = []
    for row in rows:
        if row.get("auto_label") == "review_candidate":
            by_task[str(row.get("task_type", "Unknown"))].append(dict(row))
        elif row.get("review_bucket") == "auto_rejected_control":
            controls.append(dict(row))
    packet: list[dict] = []
    for task_type in sorted(by_task):
        bucket = by_task[task_type]
        bucket.sort(
            key=lambda row: (
                row.get("review_bucket") != "high_precision_review_candidate",
                -float(row.get("set_f1", 0.0) or 0.0),
                -float(row.get("lcs_ratio", 0.0) or 0.0),
                -float(row.get("text_jaccard", 0.0) or 0.0),
                str(row.get("candidate_id", "")),
            )
        )
        packet.extend(bucket[: max(int(per_task_type_cap), 1)])
    if control_review_rows > 0:
        rng.shuffle(controls)
        packet.extend(controls[: int(control_review_rows)])
    rng.shuffle(packet)
    packet = packet[: max(int(max_review_rows), 0)]
    for row in packet:
        row["human_label"] = ""
        row["review_notes"] = ""
    return packet


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")


def _json_cell(value: object) -> str:
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False)
    return "" if value is None else str(value)


def _write_csv(path: Path, rows: Sequence[dict]) -> None:
    fields = [
        "candidate_id",
        "auto_label",
        "review_bucket",
        "task_type",
        "left_workflow_index",
        "right_workflow_index",
        "left_task_name",
        "right_task_name",
        "left_tokens",
        "right_tokens",
        "left_len",
        "right_len",
        "length_delta",
        "set_f1",
        "lcs_ratio",
        "text_jaccard",
        "passed_checks",
        "rejection_reasons",
        "human_label",
        "review_notes",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _json_cell(row.get(field, "")) for field in fields})


def _write_markdown(path: Path, report: dict) -> None:
    summary = report["summary"]
    counts = summary["counts"]
    lines = [
        "# Multi-Solution Candidate Generation",
        "",
        "This is an offline candidate-mining artifact. It does not create training labels.",
        "",
        "## Counts",
        "",
        f"- Total candidates: {summary['total_candidates']}",
        f"- Review candidates: {counts.get('review_candidate', 0)}",
        f"- Rejected controls: {counts.get('rejected', 0)}",
        f"- Human review packet: {report['human_review_packet_count']}",
        "",
        "## Review Buckets",
        "",
        f"- High precision candidates: {summary.get('review_bucket_counts', {}).get('high_precision_review_candidate', 0)}",
        f"- Boundary candidates: {summary.get('review_bucket_counts', {}).get('boundary_review_candidate', 0)}",
        f"- Rejected controls: {summary.get('review_bucket_counts', {}).get('auto_rejected_control', 0)}",
        "",
        "## Boundary",
        "",
        "- Same task type is a recall condition, not an equivalence label.",
        "- Rows in `candidate_review_sheet.csv` require human confirmation before registry/training use.",
        "- Val/test splits are never mined as candidate sources.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_report(
    *,
    data_path: Path,
    splits_path: Path,
    result: CandidateGenerationResult,
    review_packet: Sequence[dict],
) -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "created_at": _now(),
        "governance": {
            "offline_only": True,
            "train_split_only": True,
            "no_training_labels_created": True,
            "manual_confirmation_required": True,
            "no_quality_gate_mutation": True,
        },
        "inputs": {
            "data_path": str(data_path),
            "splits_path": str(splits_path),
        },
        "summary": result.summary,
        "human_review_packet_count": len(review_packet),
    }


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA_PATH)
    parser.add_argument("--splits", type=Path, default=DEFAULT_SPLITS_PATH)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--max-pairs-per-task-type", type=int, default=500)
    parser.add_argument("--min-set-f1", type=float, default=0.8)
    parser.add_argument("--max-length-delta", type=int, default=2)
    parser.add_argument("--min-text-jaccard", type=float, default=0.15)
    parser.add_argument("--high-precision-set-f1", type=float, default=0.95)
    parser.add_argument("--high-precision-lcs-ratio", type=float, default=0.7)
    parser.add_argument("--high-precision-max-length-delta", type=int, default=1)
    parser.add_argument("--max-review-rows", type=int, default=500)
    parser.add_argument("--per-task-type-cap", type=int, default=25)
    parser.add_argument("--control-review-rows", type=int, default=0)
    parser.add_argument("--seed", type=int, default=42)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> dict:
    args = parse_args(argv)
    workflows = _load_workflows(args.data)
    splits = _load_json(args.splits)
    result = generate_candidates(
        workflows,
        splits,
        max_pairs_per_task_type=args.max_pairs_per_task_type,
        min_set_f1=args.min_set_f1,
        max_length_delta=args.max_length_delta,
        min_text_jaccard=args.min_text_jaccard,
        high_precision_set_f1=args.high_precision_set_f1,
        high_precision_lcs_ratio=args.high_precision_lcs_ratio,
        high_precision_max_length_delta=args.high_precision_max_length_delta,
    )
    review_packet = build_human_review_packet(
        result.candidates,
        max_review_rows=args.max_review_rows,
        per_task_type_cap=args.per_task_type_cap,
        control_review_rows=args.control_review_rows,
        seed=args.seed,
    )
    report = build_report(
        data_path=args.data,
        splits_path=args.splits,
        result=result,
        review_packet=review_packet,
    )
    args.out_dir.mkdir(parents=True, exist_ok=True)
    _write_jsonl(args.out_dir / "generated_candidates.jsonl", result.candidates)
    _write_csv(args.out_dir / "candidate_review_sheet.csv", review_packet)
    _write_json(args.out_dir / "multisolution_candidate_report.json", report)
    _write_markdown(args.out_dir / "multisolution_candidate_summary.md", report)
    print(json.dumps({"output_dir": str(args.out_dir), "summary": result.summary}, ensure_ascii=False, indent=2))
    return report


if __name__ == "__main__":
    main()
