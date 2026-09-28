#!/usr/bin/env python3
"""Build a strict split and 50-row review pack for grafted GEE raster-core rows.

This script creates report sidecars only. It does not modify the original
proposal, does not write outputs_v2, does not train, and does not grant
validation/test admission.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


DEFAULT_GRAFTED_ROWS = (
    ROOT
    / "docs/reports/gee_raster_core_v1_source_identity_graft_2026-07-24/grafted_selected_rows.jsonl"
)
DEFAULT_OUTPUT_DIR = (
    ROOT / "docs/reports/gee_raster_core_v1_review_split_2026-07-24"
)
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
SPLITS = ("train", "val", "test")
SPLIT_RATIOS = {"train": 0.8, "val": 0.1, "test": 0.1}
HUMAN_FIELDS = [
    "human_task_text_faithful_to_core_chain",
    "human_l3_chain_correct",
    "human_chain_complete_for_task",
    "human_should_enter_training",
    "human_reviewer_notes",
]
REVIEW_FIELDS = [
    "review_id",
    "split",
    "script_id",
    "source_sha256",
    "source_path",
    "task_type",
    "task_name",
    "task_description",
    "l3_length",
    "l3_sequence_hash",
    "l3_codes_json",
    "operator_sequence_json",
    "sample_weight",
    *HUMAN_FIELDS,
]


@dataclass(slots=True)
class ReviewSplitResult:
    report: dict[str, Any]
    assignments: list[dict[str, Any]]
    review_rows: list[dict[str, Any]]
    excluded_rows: list[dict[str, Any]]


class _UnionFind:
    def __init__(self, size: int) -> None:
        self.parent = list(range(size))
        self.rank = [0] * size

    def find(self, item: int) -> int:
        parent = self.parent[item]
        if parent != item:
            self.parent[item] = self.find(parent)
        return self.parent[item]

    def union(self, left: int, right: int) -> None:
        left_root = self.find(left)
        right_root = self.find(right)
        if left_root == right_root:
            return
        if self.rank[left_root] < self.rank[right_root]:
            left_root, right_root = right_root, left_root
        self.parent[right_root] = left_root
        if self.rank[left_root] == self.rank[right_root]:
            self.rank[left_root] += 1


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_number} must contain a JSON object")
        rows.append(value)
    return rows


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            if text and not text.endswith("\n"):
                handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise


def _jsonl_text(rows: Iterable[dict[str, Any]]) -> str:
    return "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for row in rows
    )


def _sequence_hash(l3_codes: Any) -> str:
    values = l3_codes if isinstance(l3_codes, list) else []
    payload = json.dumps(values, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _stable_hash(*parts: Any) -> str:
    payload = json.dumps(parts, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _eligibility(row: dict[str, Any]) -> tuple[bool, str]:
    source_sha256 = row.get("source_sha256")
    if row.get("source_identity_status") != "authoritative_grafted":
        return False, "not_authoritative_grafted"
    if not isinstance(source_sha256, str) or not SHA256_RE.fullmatch(source_sha256):
        return False, "missing_or_invalid_source_sha256"
    if row.get("source_identity_authority") != "source_content_sha256":
        return False, "missing_source_content_authority"
    if row.get("source_platform") != "GEE" or row.get("target_platform") != "L3":
        return False, "wrong_platform_boundary"
    if row.get("training_tier") != "silver_a":
        return False, "not_silver_a"
    if row.get("workflow_scope") != "core_analysis":
        return False, "not_core_analysis"
    if not isinstance(row.get("l3_codes"), list) or not row.get("l3_codes"):
        return False, "missing_l3_codes"
    return True, "eligible"


def _components(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    uf = _UnionFind(len(rows))
    first_by_source: dict[str, int] = {}
    first_by_sequence: dict[str, int] = {}
    sequence_hashes: list[str] = []
    for index, row in enumerate(rows):
        source = str(row["source_sha256"]).lower()
        seq_hash = _sequence_hash(row.get("l3_codes"))
        sequence_hashes.append(seq_hash)
        if source in first_by_source:
            uf.union(index, first_by_source[source])
        else:
            first_by_source[source] = index
        if seq_hash in first_by_sequence:
            uf.union(index, first_by_sequence[seq_hash])
        else:
            first_by_sequence[seq_hash] = index

    members: dict[int, list[int]] = defaultdict(list)
    for index in range(len(rows)):
        members[uf.find(index)].append(index)

    components = []
    for indexes in members.values():
        script_ids = sorted(str(rows[index].get("script_id", "")) for index in indexes)
        sources = sorted({str(rows[index]["source_sha256"]).lower() for index in indexes})
        sequences = sorted({sequence_hashes[index] for index in indexes})
        components.append(
            {
                "indexes": sorted(indexes),
                "size": len(indexes),
                "sources": sources,
                "sequence_hashes": sequences,
                "sort_hash": _stable_hash(script_ids, sources, sequences),
            }
        )
    return components


def _assign_components(
    components: list[dict[str, Any]],
    *,
    total_rows: int,
) -> dict[int, str]:
    targets = {split: total_rows * SPLIT_RATIOS[split] for split in SPLITS}
    current = {split: 0 for split in SPLITS}
    assignment: dict[int, str] = {}
    for component in sorted(components, key=lambda item: (-item["size"], item["sort_hash"])):
        split = max(
            SPLITS,
            key=lambda candidate: (targets[candidate] - current[candidate], -SPLITS.index(candidate)),
        )
        for index in component["indexes"]:
            assignment[index] = split
        current[split] += int(component["size"])
    return assignment


def _assignment_row(row: dict[str, Any], *, split: str, source_index: int) -> dict[str, Any]:
    l3_codes = list(row.get("l3_codes") or [])
    seq_hash = _sequence_hash(l3_codes)
    return {
        "source_index": source_index,
        "split": split,
        "proposal_id": row.get("proposal_id", ""),
        "script_id": row.get("script_id", ""),
        "source_sha256": str(row.get("source_sha256", "")).lower(),
        "source_path": row.get("source_path", ""),
        "task_type": row.get("task_type", ""),
        "task_name": row.get("task_name", ""),
        "task_description": row.get("task_description", ""),
        "l3_codes": l3_codes,
        "operator_sequence": list(row.get("operator_sequence") or []),
        "l3_length": len(l3_codes),
        "l3_sequence_hash": seq_hash,
        "sample_weight": row.get("sample_weight", 0.5),
        "source_identity_status": row.get("source_identity_status", ""),
        "validation_eligible": False,
        "test_eligible": False,
        "review_required_before_promotion": True,
    }


def _verify_disjoint(assignments: list[dict[str, Any]], field: str) -> tuple[bool, list[dict[str, Any]]]:
    splits_by_value: dict[str, set[str]] = defaultdict(set)
    for row in assignments:
        value = str(row.get(field, ""))
        if value:
            splits_by_value[value].add(str(row["split"]))
    leaks = [
        {"value": value, "splits": sorted(splits)}
        for value, splits in sorted(splits_by_value.items())
        if len(splits) > 1
    ]
    return not leaks, leaks[:20]


def _review_quotas(assignments: list[dict[str, Any]], review_size: int) -> dict[str, int]:
    split_counts = Counter(str(row["split"]) for row in assignments)
    nonempty = [split for split in SPLITS if split_counts[split] > 0]
    if review_size <= 0 or not nonempty:
        return {split: 0 for split in SPLITS}
    size = min(review_size, len(assignments))
    raw = {split: size * split_counts[split] / len(assignments) for split in SPLITS}
    quotas = {split: int(raw[split]) for split in SPLITS}
    if size >= len(nonempty):
        for split in nonempty:
            quotas[split] = max(1, quotas[split])
    while sum(quotas.values()) > size:
        candidates = [split for split in SPLITS if quotas[split] > (1 if size >= len(nonempty) and split in nonempty else 0)]
        split = max(candidates, key=lambda item: (quotas[item] - raw[item], quotas[item]))
        quotas[split] -= 1
    while sum(quotas.values()) < size:
        split = max(SPLITS, key=lambda item: (raw[item] - quotas[item], split_counts[item]))
        quotas[split] += 1
    return quotas


def _select_for_review(assignments: list[dict[str, Any]], *, review_size: int, seed: str) -> list[dict[str, Any]]:
    quotas = _review_quotas(assignments, review_size)
    selected: list[dict[str, Any]] = []
    selected_keys: set[str] = set()
    for split in SPLITS:
        split_rows = [row for row in assignments if row["split"] == split]
        ordered = sorted(
            split_rows,
            key=lambda row: _stable_hash(seed, split, row["task_type"], row["l3_sequence_hash"], row["script_id"]),
        )
        seen_sequences: set[str] = set()
        for row in ordered:
            if len([item for item in selected if item["split"] == split]) >= quotas[split]:
                break
            if row["l3_sequence_hash"] in seen_sequences:
                continue
            selected.append(row)
            selected_keys.add(str(row["proposal_id"]))
            seen_sequences.add(str(row["l3_sequence_hash"]))
        for row in ordered:
            if len([item for item in selected if item["split"] == split]) >= quotas[split]:
                break
            if str(row["proposal_id"]) in selected_keys:
                continue
            selected.append(row)
            selected_keys.add(str(row["proposal_id"]))

    if len(selected) < min(review_size, len(assignments)):
        ordered = sorted(
            assignments,
            key=lambda row: _stable_hash(seed, "fill", row["split"], row["script_id"]),
        )
        for row in ordered:
            if len(selected) >= min(review_size, len(assignments)):
                break
            if str(row["proposal_id"]) not in selected_keys:
                selected.append(row)
                selected_keys.add(str(row["proposal_id"]))

    review_rows: list[dict[str, Any]] = []
    for index, row in enumerate(selected, start=1):
        review = {
            "review_id": f"gee_raster_core_review_{index:03d}",
            "split": row["split"],
            "script_id": row["script_id"],
            "source_sha256": row["source_sha256"],
            "source_path": row["source_path"],
            "task_type": row["task_type"],
            "task_name": row["task_name"],
            "task_description": row["task_description"],
            "l3_length": row["l3_length"],
            "l3_sequence_hash": row["l3_sequence_hash"],
            "l3_codes_json": json.dumps(row["l3_codes"], ensure_ascii=False, separators=(",", ":")),
            "operator_sequence_json": json.dumps(row["operator_sequence"], ensure_ascii=False, separators=(",", ":")),
            "sample_weight": row["sample_weight"],
        }
        review.update({field: "" for field in HUMAN_FIELDS})
        review_rows.append(review)
    return review_rows


def build_review_split(
    *,
    grafted_rows_path: Path,
    output_dir: Path,
    review_size: int = 50,
    seed: str = "gee_raster_core_v1_review_2026-07-24",
) -> ReviewSplitResult:
    input_rows = _load_jsonl(grafted_rows_path)
    eligible_rows: list[dict[str, Any]] = []
    excluded_rows: list[dict[str, Any]] = []
    exclusion_reasons: Counter[str] = Counter()
    for source_index, row in enumerate(input_rows):
        ok, reason = _eligibility(row)
        if ok:
            eligible_rows.append({**row, "_source_index": source_index})
        else:
            excluded = {
                "source_index": source_index,
                "script_id": row.get("script_id", ""),
                "source_identity_status": row.get("source_identity_status", ""),
                "exclusion_reason": reason,
            }
            excluded_rows.append(excluded)
            exclusion_reasons[reason] += 1

    components = _components(eligible_rows)
    split_by_index = _assign_components(components, total_rows=len(eligible_rows))
    assignments = [
        _assignment_row(row, split=split_by_index[index], source_index=int(row["_source_index"]))
        for index, row in enumerate(eligible_rows)
    ]
    assignments.sort(key=lambda row: (row["split"], row["script_id"]))
    review_rows = _select_for_review(assignments, review_size=review_size, seed=seed)

    source_ok, source_leaks = _verify_disjoint(assignments, "source_sha256")
    sequence_ok, sequence_leaks = _verify_disjoint(assignments, "l3_sequence_hash")
    split_counts = Counter(row["split"] for row in assignments)
    task_counts = Counter(str(row.get("task_type", "")) for row in assignments)
    review_split_counts = Counter(row["split"] for row in review_rows)
    report = {
        "schema": "gis_recommend.gee_raster_core_review_split.v1",
        "inputs": {
            "grafted_rows": str(Path(grafted_rows_path)),
            "review_size_requested": review_size,
            "seed": seed,
        },
        "outputs": {
            "output_dir": str(Path(output_dir)),
        },
        "policy": {
            "eligible_status": "authoritative_grafted",
            "grouping": "source_sha256_plus_exact_l3_sequence_connected_components",
            "split_ratios": SPLIT_RATIOS,
            "review_selection": "deterministic_split_stratified_unique_l3_sequence_first",
            "validation_eligible": False,
            "test_eligible": False,
            "training_admission": "not_granted",
        },
        "counts": {
            "input_rows": len(input_rows),
            "eligible_rows": len(eligible_rows),
            "excluded_rows": len(excluded_rows),
            "components": len(components),
            "unique_sources": len({row["source_sha256"] for row in assignments}),
            "unique_l3_sequences": len({row["l3_sequence_hash"] for row in assignments}),
            "review_rows": len(review_rows),
            "split_counts": dict(sorted(split_counts.items())),
            "review_split_counts": dict(sorted(review_split_counts.items())),
            "exclusion_reasons": dict(sorted(exclusion_reasons.items())),
        },
        "leakage_checks": {
            "source_disjoint_verified": source_ok,
            "source_leak_examples": source_leaks,
            "sequence_disjoint_verified": sequence_ok,
            "sequence_leak_examples": sequence_leaks,
        },
        "top_task_types": [
            {"task_type": task_type, "count": count}
            for task_type, count in task_counts.most_common(20)
        ],
        "decision": {
            "training_admission": "not_granted",
            "validation_eligible": False,
            "test_eligible": False,
            "next_gate": "human review of 50-row task text and core-chain fidelity",
        },
    }
    return ReviewSplitResult(
        report=report,
        assignments=assignments,
        review_rows=review_rows,
        excluded_rows=excluded_rows,
    )


def _render_markdown(report: dict[str, Any]) -> str:
    counts = report["counts"]
    leaks = report["leakage_checks"]
    lines = [
        "# GEE Raster Core Review Split",
        "",
        "Strict source/sequence-disjoint split and 50-row human review package for grafted GEE raster-core rows.",
        "This remains a review sidecar and does not grant training, validation, or test admission.",
        "",
        "## Summary",
        "",
        f"- Input rows: {counts['input_rows']:,}",
        f"- Eligible grafted rows: {counts['eligible_rows']:,}",
        f"- Excluded rows: {counts['excluded_rows']:,}",
        f"- Connected components: {counts['components']:,}",
        f"- Unique sources: {counts['unique_sources']:,}",
        f"- Unique L3 sequences: {counts['unique_l3_sequences']:,}",
        f"- Review rows: {counts['review_rows']:,}",
        f"- Split counts: {counts['split_counts']}",
        f"- Review split counts: {counts['review_split_counts']}",
        "",
        "## Leakage Checks",
        "",
        f"- Source-disjoint verified: `{leaks['source_disjoint_verified']}`",
        f"- Exact L3-sequence-disjoint verified: `{leaks['sequence_disjoint_verified']}`",
        "",
        "## Decision",
        "",
        f"- Training admission: `{report['decision']['training_admission']}`",
        f"- Validation eligible: `{report['decision']['validation_eligible']}`",
        f"- Test eligible: `{report['decision']['test_eligible']}`",
        f"- Next gate: {report['decision']['next_gate']}",
        "",
    ]
    return "\n".join(lines)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=REVIEW_FIELDS)
            writer.writeheader()
            for row in rows:
                writer.writerow({field: row.get(field, "") for field in REVIEW_FIELDS})
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise


def write_outputs(result: ReviewSplitResult, output_dir: Path) -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    report_json = output_dir / "review_split_report.json"
    report_md = output_dir / "review_split_report.md"
    splits_json = output_dir / "source_disjoint_splits.json"
    assignments_jsonl = output_dir / "split_assignments.jsonl"
    excluded_jsonl = output_dir / "excluded_rows.jsonl"
    review_jsonl = output_dir / "review_50.jsonl"
    review_csv = output_dir / "review_50.csv"
    splits_payload = {
        "schema": "gis_recommend.gee_raster_core_source_disjoint_splits.v1",
        "policy": result.report["policy"],
        "leakage_checks": result.report["leakage_checks"],
    }
    for split in SPLITS:
        split_rows = [row for row in result.assignments if row["split"] == split]
        splits_payload[f"{split}_source_indices"] = [row["source_index"] for row in split_rows]
        splits_payload[f"{split}_proposal_ids"] = [row["proposal_id"] for row in split_rows]
        splits_payload[f"{split}_source_sha256"] = [row["source_sha256"] for row in split_rows]
    _atomic_write_text(report_json, json.dumps(result.report, ensure_ascii=False, indent=2, sort_keys=True))
    _atomic_write_text(report_md, _render_markdown(result.report))
    _atomic_write_text(splits_json, json.dumps(splits_payload, ensure_ascii=False, indent=2, sort_keys=True))
    _atomic_write_text(assignments_jsonl, _jsonl_text(result.assignments))
    _atomic_write_text(excluded_jsonl, _jsonl_text(result.excluded_rows))
    _atomic_write_text(review_jsonl, _jsonl_text(result.review_rows))
    _write_csv(review_csv, result.review_rows)
    return {
        "report_json": report_json,
        "report_md": report_md,
        "splits_json": splits_json,
        "assignments_jsonl": assignments_jsonl,
        "excluded_jsonl": excluded_jsonl,
        "review_jsonl": review_jsonl,
        "review_csv": review_csv,
    }


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--grafted-rows", type=Path, default=DEFAULT_GRAFTED_ROWS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--review-size", type=int, default=50)
    parser.add_argument("--seed", default="gee_raster_core_v1_review_2026-07-24")
    args = parser.parse_args(argv)
    result = build_review_split(
        grafted_rows_path=args.grafted_rows,
        output_dir=args.output_dir,
        review_size=args.review_size,
        seed=args.seed,
    )
    return write_outputs(result, args.output_dir)


if __name__ == "__main__":
    main()
