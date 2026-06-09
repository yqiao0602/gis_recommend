# -*- coding: utf-8 -*-
"""Training data quality audit helpers for final V4 Step8 data."""

from __future__ import annotations

import hashlib
import csv
import json
import math
import statistics
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


SPLIT_KEYS = ("train_indices", "val_indices", "test_indices")


def _content_tokens(workflow: dict[str, Any]) -> list[int]:
    return [
        token for token in workflow.get("l3_sequence", [])
        if isinstance(token, int) and token >= 0
    ]


def _task_type(workflow: dict[str, Any]) -> str:
    meta = workflow.get("task_metadata", {}) or {}
    return meta.get("task_type", "Unknown") or "Unknown"


def _task_text(workflow: dict[str, Any]) -> str:
    meta = workflow.get("task_metadata", {}) or {}
    name = meta.get("task_name", "") or ""
    desc = meta.get("task_description", "") or ""
    return f"{name}\n{desc}".strip()


def _hash_json(value: Any) -> str:
    return hashlib.md5(
        json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _split_lookup(splits: dict[str, list[int]] | None) -> dict[int, str]:
    lookup: dict[int, str] = {}
    if not splits:
        return lookup
    for key in SPLIT_KEYS:
        split_name = key.replace("_indices", "")
        for index in splits.get(key, []):
            lookup[int(index)] = split_name
    return lookup


def _mapping_metadata_by_operator(id_mappings: dict[str, Any] | None) -> dict[str, dict]:
    if not id_mappings:
        return {}
    gee_to_l3 = id_mappings.get("mapping_metadata", {}).get("gee_to_l3", {})
    return {str(operator).lower().strip(): meta for operator, meta in gee_to_l3.items()}


def _id_to_l3_code(id_mappings: dict[str, Any] | None) -> dict[int, str]:
    if not id_mappings:
        return {}
    if "l3" in id_mappings:
        return {int(value): code for code, value in id_mappings["l3"].items()}
    if "id_to_l3" in id_mappings:
        return {int(key): value for key, value in id_mappings["id_to_l3"].items()}
    if "l3_to_id" in id_mappings:
        return {int(value): code for code, value in id_mappings["l3_to_id"].items()}
    return {}


def load_l3_names(hierarchy_path: Path | str | None) -> dict[str, str]:
    """Load L3 code -> display name from a classification hierarchy CSV."""
    if not hierarchy_path:
        return {}
    path = Path(hierarchy_path)
    if not path.exists():
        return {}
    with path.open(encoding="utf-8", newline="") as f:
        return {
            row.get("l3_code", ""): row.get("l3_name", "")
            for row in csv.DictReader(f)
            if row.get("l3_code")
        }


def _entropy(counter: Counter) -> float:
    total = sum(counter.values())
    if total <= 0:
        return 0.0
    return -sum((count / total) * math.log2(count / total)
                for count in counter.values() if count)


def _quantiles(values: list[float]) -> dict[str, float]:
    if not values:
        return {}
    ordered = sorted(values)

    def q(position: float) -> float:
        return ordered[int((len(ordered) - 1) * position)]

    return {
        "min": ordered[0],
        "p05": q(0.05),
        "p25": q(0.25),
        "median": q(0.5),
        "p75": q(0.75),
        "p95": q(0.95),
        "max": ordered[-1],
    }


def _top_l3(counter: Counter, id_to_code: dict[int, str], limit: int = 20) -> list[dict]:
    return [
        {"token_id": token_id, "l3_code": id_to_code.get(token_id), "count": count}
        for token_id, count in counter.most_common(limit)
    ]


def audit_training_data_quality(
    workflows: list[dict[str, Any]],
    splits: dict[str, list[int]] | None = None,
    *,
    id_mappings: dict[str, Any] | None = None,
    operator_hotlist_min_count: int = 100,
) -> dict[str, Any]:
    """Return a structured quality audit for final training workflows."""
    split_of = _split_lookup(splits)
    op_metadata = _mapping_metadata_by_operator(id_mappings)
    id_to_code = _id_to_l3_code(id_mappings)
    expected_vocab_size = len(id_to_code)

    schema = Counter()
    token_counts: Counter[int] = Counter()
    task_counts: Counter[str] = Counter()
    task_by_split: dict[str, Counter] = defaultdict(Counter)
    l3_by_split: dict[str, Counter] = defaultdict(Counter)
    content_lengths: list[int] = []
    unique_ratios: list[float] = []
    max_token_shares: list[float] = []
    max_runs: list[int] = []

    confidence_values: list[float] = []
    low_confidence_tokens = 0
    low_confidence_workflows = 0
    operator_quality: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "count": 0,
            "low_count": 0,
            "confidence_sum": 0.0,
            "source": Counter(),
            "mapping_type": Counter(),
            "l3": Counter(),
            "tasks": Counter(),
        }
    )
    source_counts: Counter[str] = Counter()
    source_conf: dict[str, list[float]] = defaultdict(list)
    missing_meta_tokens = 0

    seq_hash_counts: Counter[str] = Counter()
    seq_hash_splits: dict[str, set[str]] = defaultdict(set)
    text_hash_counts: Counter[str] = Counter()
    text_seq_hash_counts: Counter[str] = Counter()

    empty_name = empty_desc = empty_both = 0

    for index, workflow in enumerate(workflows):
        split = split_of.get(index, "unsplit")
        seq = workflow.get("l3_sequence", [])
        codes = workflow.get("l3_codes", [])
        ops = workflow.get("operator_sequence", [])
        confidences = workflow.get("confidences", [])
        ambiguity_flags = workflow.get("ambiguity_flags", [])
        task_type = _task_type(workflow)
        task_counts[task_type] += 1
        task_by_split[split][task_type] += 1

        if not isinstance(seq, list) or not isinstance(codes, list) or not isinstance(ops, list):
            schema["missing_or_bad_sequence_fields"] += 1
            continue
        if len(seq) != len(codes):
            schema["l3_sequence_code_len_mismatch"] += 1
        if len(seq) != len(ops) + 2:
            schema["seq_not_ops_plus_specials"] += 1
        if len(codes) != len(ops) + 2:
            schema["codes_not_ops_plus_specials"] += 1
        if len(confidences) != len(ops):
            schema["conf_not_ops_len"] += 1
        if len(ambiguity_flags) != len(ops):
            schema["amb_not_ops_len"] += 1
        if seq and seq[0] != -3:
            schema["bad_start_token"] += 1
        if seq and seq[-1] != -4:
            schema["bad_end_token"] += 1
        if any(not isinstance(token, int) for token in seq):
            schema["non_integer_token"] += 1
        if expected_vocab_size and any(
            isinstance(token, int) and token >= expected_vocab_size for token in seq
        ):
            schema["token_outside_l3_vocab"] += 1

        content = _content_tokens(workflow)
        content_lengths.append(len(content))
        token_counts.update(content)
        l3_by_split[split].update(content)
        if content:
            token_counter = Counter(content)
            unique_ratios.append(len(token_counter) / len(content))
            max_token_shares.append(token_counter.most_common(1)[0][1] / len(content))
            run = max_run = 1
            for previous, current in zip(content, content[1:]):
                if current == previous:
                    run += 1
                    max_run = max(max_run, run)
                else:
                    run = 1
            max_runs.append(max_run)

        low_in_workflow = 0
        for operator, token, confidence in zip(ops, content, confidences):
            meta = op_metadata.get(str(operator).lower().strip())
            if meta is None:
                source = "missing_meta"
                mapping_type = "missing_meta"
                missing_meta_tokens += 1
            else:
                source = meta.get("source", "unknown_source")
                mapping_type = meta.get("mapping_type", "unknown_type")
            source_counts[source] += 1
            op_quality = operator_quality[str(operator)]
            op_quality["count"] += 1
            op_quality["source"][source] += 1
            op_quality["mapping_type"][mapping_type] += 1
            op_quality["l3"][token] += 1
            op_quality["tasks"][task_type] += 1
            if isinstance(confidence, (int, float)):
                confidence_values.append(float(confidence))
                source_conf[source].append(float(confidence))
                op_quality["confidence_sum"] += float(confidence)
                if confidence < 0.9:
                    low_confidence_tokens += 1
                    low_in_workflow += 1
                    op_quality["low_count"] += 1
        if low_in_workflow:
            low_confidence_workflows += 1

        seq_hash = _hash_json(seq)
        seq_hash_counts[seq_hash] += 1
        seq_hash_splits[seq_hash].add(split)
        task_text = _task_text(workflow)
        text_hash = hashlib.md5(task_text.encode("utf-8")).hexdigest()
        text_hash_counts[text_hash] += 1
        text_seq_hash_counts[hashlib.md5((task_text + "\0" + seq_hash).encode("utf-8")).hexdigest()] += 1
        meta = workflow.get("task_metadata", {}) or {}
        name = (meta.get("task_name", "") or "").strip()
        desc = (meta.get("task_description", "") or "").strip()
        empty_name += int(not name)
        empty_desc += int(not desc)
        empty_both += int(not name and not desc)

    train_tasks = set(task_by_split.get("train", {}))
    val_tasks = set(task_by_split.get("val", {}))
    test_tasks = set(task_by_split.get("test", {}))
    all_l3 = set(token_counts)

    total_tokens = sum(token_counts.values())
    active_l3 = len(token_counts)
    max_entropy = math.log2(active_l3) if active_l3 > 1 else 1.0

    low_confidence_operators = []
    for operator, data in operator_quality.items():
        count = data["count"]
        if count < operator_hotlist_min_count:
            continue
        mean_conf = data["confidence_sum"] / count if count else 0.0
        low_ratio = data["low_count"] / count if count else 0.0
        if low_ratio >= 0.2 or mean_conf < 0.9:
            low_confidence_operators.append({
                "operator": operator,
                "count": count,
                "low_confidence_ratio": round(low_ratio, 4),
                "mean_confidence": round(mean_conf, 4),
                "top_sources": data["source"].most_common(3),
                "top_l3": _top_l3(data["l3"], id_to_code, limit=3),
                "top_tasks": data["tasks"].most_common(3),
            })
    low_confidence_operators.sort(
        key=lambda item: (-item["low_confidence_ratio"], -item["count"], item["operator"])
    )

    source_summary = {}
    for source, count in source_counts.items():
        values = source_conf[source]
        source_summary[source] = {
            "tokens": count,
            "token_share": round(count / max(total_tokens, 1), 4),
            "mean_confidence": round(statistics.mean(values), 4) if values else None,
            "low_confidence_tokens": sum(1 for value in values if value < 0.9),
        }

    duplicate_sequence_items = sum(count for count in seq_hash_counts.values() if count > 1)
    cross_split_sequence_hashes = sum(
        1 for splits_seen in seq_hash_splits.values()
        if len(splits_seen & {"train", "val", "test"}) > 1
    )

    warnings: list[str] = []
    if schema:
        warnings.append("schema_integrity_issues")
    if expected_vocab_size and active_l3 < expected_vocab_size:
        warnings.append("inactive_l3_tokens")
    if total_tokens and sum(count for _, count in token_counts.most_common(10)) / total_tokens > 0.6:
        warnings.append("l3_distribution_highly_skewed")
    if sum(1 for count in task_counts.values() if count < 10):
        warnings.append("many_sparse_task_types")
    if val_tasks - train_tasks:
        warnings.append("val_has_tasks_not_in_train")
    if test_tasks - train_tasks:
        warnings.append("test_has_tasks_not_in_train")
    if cross_split_sequence_hashes:
        warnings.append("cross_split_sequence_duplicates")
    if low_confidence_tokens:
        warnings.append("low_confidence_mapping_tokens")
    if missing_meta_tokens:
        warnings.append("missing_operator_mapping_metadata")

    return {
        "counts": {
            "workflows": len(workflows),
            "tokens": total_tokens,
            "active_l3": active_l3,
            "expected_l3_vocab": expected_vocab_size or None,
            "inactive_l3": max(expected_vocab_size - active_l3, 0) if expected_vocab_size else None,
            "task_types": len(task_counts),
        },
        "schema": dict(schema),
        "lengths": {
            "content_length_quantiles": _quantiles(content_lengths),
            "unique_ratio_quantiles": _quantiles(unique_ratios),
            "max_token_share_quantiles": _quantiles(max_token_shares),
            "max_run_quantiles": _quantiles(max_runs),
        },
        "l3_distribution": {
            "entropy_normalized": round(_entropy(token_counts) / max_entropy, 4),
            "top10_share": round(
                sum(count for _, count in token_counts.most_common(10)) / max(total_tokens, 1), 4
            ),
            "top20_share": round(
                sum(count for _, count in token_counts.most_common(20)) / max(total_tokens, 1), 4
            ),
            "top_l3": _top_l3(token_counts, id_to_code),
            "rare_l3_lt_100": sum(1 for count in token_counts.values() if count < 100),
            "rare_l3_lt_1000": sum(1 for count in token_counts.values() if count < 1000),
        },
        "task_distribution": {
            "top_tasks": task_counts.most_common(20),
            "tasks_lt_10": sum(1 for count in task_counts.values() if count < 10),
            "tasks_lt_50": sum(1 for count in task_counts.values() if count < 50),
            "tasks_lt_100": sum(1 for count in task_counts.values() if count < 100),
            "unknown_task_count": task_counts.get("Unknown", 0),
        },
        "split_quality": {
            "train_tasks": len(train_tasks),
            "val_tasks": len(val_tasks),
            "test_tasks": len(test_tasks),
            "val_tasks_not_in_train": sorted(val_tasks - train_tasks),
            "test_tasks_not_in_train": sorted(test_tasks - train_tasks),
            "missing_l3_by_split": {
                split: sorted(id_to_code.get(token, str(token)) for token in all_l3 - set(counter))
                for split, counter in l3_by_split.items()
                if split in {"train", "val", "test"}
            },
        },
        "confidence": {
            "mean": round(statistics.mean(confidence_values), 4) if confidence_values else None,
            "low_confidence_tokens": low_confidence_tokens,
            "low_confidence_workflows": low_confidence_workflows,
            "low_confidence_operators": low_confidence_operators[:50],
        },
        "mapping_source": {
            "source_counts": dict(source_counts),
            "source_summary": source_summary,
            "missing_meta_tokens": missing_meta_tokens,
        },
        "duplicates": {
            "unique_sequences": len(seq_hash_counts),
            "duplicate_sequence_items": duplicate_sequence_items,
            "cross_split_sequence_hashes": cross_split_sequence_hashes,
            "unique_texts": len(text_hash_counts),
            "duplicate_text_items": sum(count for count in text_hash_counts.values() if count > 1),
            "unique_text_sequences": len(text_seq_hash_counts),
            "duplicate_text_sequence_items": sum(
                count for count in text_seq_hash_counts.values() if count > 1
            ),
        },
        "text_metadata": {
            "empty_task_name": empty_name,
            "empty_task_description": empty_desc,
            "empty_name_and_description": empty_both,
        },
        "warnings": warnings,
    }
