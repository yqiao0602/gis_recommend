#!/usr/bin/env python3
"""Compare fresh GEE extraction manifests with the preserved Step1 artifact."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
import hashlib
import json
import os
from pathlib import Path
import tempfile
from typing import Any


def _sequence_hash(operations: list[str]) -> str:
    payload = json.dumps(operations, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _canonical_script_id(record: dict[str, Any], manifest_path: Path) -> str:
    script_name = str(record.get("script_name") or "").strip()
    if not script_name:
        raise ValueError(f"{manifest_path} contains a row without script_name")
    batch_name = str(record.get("batch_name") or "").strip()
    if not batch_name:
        steps_path = str(record.get("steps_path") or "").strip()
        batch_name = Path(steps_path).parent.name if steps_path else manifest_path.stem
    if not batch_name:
        raise ValueError(f"Cannot determine batch name for {script_name} in {manifest_path}")
    return f"{batch_name}_{Path(script_name).stem}"


def _read_steps(path: Path) -> tuple[str, list[str] | None, str | None]:
    if not path.is_file():
        return "missing", None, "missing steps CSV"
    if path.stat().st_size == 0:
        return "zero_byte", None, "zero-byte steps CSV"
    try:
        with path.open("r", encoding="utf-8", newline="") as handle:
            reader = csv.DictReader(handle)
            if not reader.fieldnames or "name" not in reader.fieldnames:
                return "schema_error", None, "steps CSV must contain a name column"
            operations = []
            for row in reader:
                name = (row.get("name") or "").strip()
                if name and name != "print":
                    operations.append(name)
    except Exception as exc:
        return "parse_error", None, f"{type(exc).__name__}: {exc}"
    if not operations:
        return "empty", [], None
    return "nonempty", operations, None


def _load_fresh(fresh_root: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    manifest_dir = Path(fresh_root) / "manifests"
    if not manifest_dir.is_dir():
        raise ValueError(f"Fresh manifests directory does not exist: {manifest_dir}")
    manifest_paths = sorted(manifest_dir.glob("*.jsonl"))
    if not manifest_paths:
        raise ValueError(f"Fresh manifests directory contains no JSONL manifests: {manifest_dir}")
    for manifest_path in manifest_paths:
        with manifest_path.open("r", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                record = json.loads(line)
                if not isinstance(record, dict):
                    raise ValueError(f"{manifest_path}:{line_number} is not a JSON object")
                canonical_id = _canonical_script_id(record, manifest_path)
                runner_status = record.get("status")
                observed_status, operations, observation_error = _read_steps(
                    Path(str(record.get("steps_path") or ""))
                )
                records.append({
                    "canonical_script_id": canonical_id,
                    "manifest_path": str(manifest_path),
                    "script_name": record.get("script_name"),
                    "source_path": record.get("source_path"),
                    "source_sha256": record.get("source_sha256"),
                    "steps_path": record.get("steps_path"),
                    "runner_status": runner_status,
                    "runner_error": record.get("error"),
                    "observed_steps_status": observed_status,
                    "observation_error": observation_error,
                    "operations": operations,
                    "operations_sha256": _sequence_hash(operations) if operations is not None else None,
                })
    if not records:
        raise ValueError(f"Fresh JSONL manifests contain zero records: {manifest_dir}")
    return records


def _load_preserved(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("workflows"), list):
        raise ValueError(f"{path} must contain a workflows list")
    workflows = []
    for index, workflow in enumerate(payload["workflows"]):
        if not isinstance(workflow, dict) or not isinstance(workflow.get("script_id"), str):
            raise ValueError(f"{path} workflow {index} has no script_id")
        operations = workflow.get("operations")
        if not isinstance(operations, list) or not all(isinstance(item, str) for item in operations):
            raise ValueError(f"{path} workflow {index} has invalid operations")
        workflows.append({
            "script_id": workflow["script_id"],
            "operations": operations,
            "length": workflow.get("length"),
            "operations_sha256": _sequence_hash(operations),
        })
    return payload, workflows


def _edit_counts(left: list[str], right: list[str]) -> dict[str, int]:
    """Return minimum edits using O(len(right)) memory.

    Equal-distance paths prefer fewer insertions, then fewer deletions, then
    fewer substitutions because the state tuple is ordered that way.
    """
    cols = len(right) + 1
    previous = [(j, j, 0, 0) for j in range(cols)]
    for i in range(1, len(left) + 1):
        current = [(i, 0, i, 0)]
        for j in range(1, cols):
            if left[i - 1] == right[j - 1]:
                current.append(previous[j - 1])
                continue
            substitute = previous[j - 1]
            delete = previous[j]
            insert = current[j - 1]
            choices = [
                (substitute[0] + 1, substitute[1], substitute[2], substitute[3] + 1),
                (delete[0] + 1, delete[1], delete[2] + 1, delete[3]),
                (insert[0] + 1, insert[1] + 1, insert[2], insert[3]),
            ]
            current.append(min(choices))
        previous = current
    _, insertions, deletions, substitutions = previous[-1]
    return {
        "insertions": insertions,
        "deletions": deletions,
        "substitutions": substitutions,
    }


def _compare_operations(fresh: list[str], preserved: list[str]) -> tuple[str, dict[str, int]]:
    if fresh == preserved:
        return "exact_match", {"insertions": 0, "deletions": 0, "substitutions": 0}
    edits = _edit_counts(preserved, fresh)
    if Counter(fresh) == Counter(preserved):
        return "same_multiset_different_order", edits
    return "changed", edits


def build_comparison(
    fresh_root: Path,
    preserved_step1: Path,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    fresh_records = _load_fresh(Path(fresh_root))
    preserved_payload, preserved_records = _load_preserved(Path(preserved_step1))
    fresh_by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    preserved_by_id: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in fresh_records:
        fresh_by_id[record["canonical_script_id"]].append(record)
    for record in preserved_records:
        preserved_by_id[record["script_id"]].append(record)

    fresh_duplicate_ids = sum(len(records) > 1 for records in fresh_by_id.values())
    fresh_hash_conflicts = sum(
        len({record.get("source_sha256") for record in records if record.get("source_sha256")}) > 1
        for records in fresh_by_id.values()
    )
    preserved_duplicate_ids = sum(len(records) > 1 for records in preserved_by_id.values())
    preserved_operation_conflicts = sum(
        len({record["operations_sha256"] for record in records}) > 1
        for records in preserved_by_id.values()
    )

    hash_counts = Counter(
        str(record["source_sha256"])
        for record in fresh_records
        if record.get("source_sha256")
    )
    runner_status_counts = Counter(str(record["runner_status"] or "missing") for record in fresh_records)
    observed_status_counts = Counter(record["observed_steps_status"] for record in fresh_records)
    rows: list[dict[str, Any]] = []
    coverage = Counter()
    operation_counts = Counter({
        "eligible": 0,
        "exact_match": 0,
        "same_multiset_different_order": 0,
        "changed": 0,
        "insertions": 0,
        "deletions": 0,
        "substitutions": 0,
    })

    for script_id in sorted(set(fresh_by_id) | set(preserved_by_id)):
        fresh_group = fresh_by_id.get(script_id, [])
        preserved_group = preserved_by_id.get(script_id, [])
        fresh_variants = {
            (record.get("source_sha256"), record["observed_steps_status"], record["operations_sha256"])
            for record in fresh_group
        }
        preserved_variants = {record["operations_sha256"] for record in preserved_group}
        ambiguous = len(fresh_variants) > 1 or len(preserved_variants) > 1
        row: dict[str, Any] = {
            "canonical_script_id": script_id,
            "fresh_attempt_count": len(fresh_group),
            "preserved_row_count": len(preserved_group),
            "fresh_source_sha256": sorted({
                str(record["source_sha256"])
                for record in fresh_group if record.get("source_sha256")
            }),
            "fresh_runner_statuses": sorted({
                str(record["runner_status"] or "missing") for record in fresh_group
            }),
            "fresh_observed_steps_statuses": sorted({
                record["observed_steps_status"] for record in fresh_group
            }),
            "fresh_operations_sha256": sorted({
                record["operations_sha256"] for record in fresh_group
                if record["operations_sha256"] is not None
            }),
            "preserved_operations_sha256": sorted(preserved_variants),
        }
        if ambiguous:
            coverage["ambiguous"] += 1
            row["comparison"] = "ambiguous_id"
        elif fresh_group and preserved_group:
            coverage["both_unambiguous"] += 1
            fresh_operations = fresh_group[0]["operations"]
            if fresh_group[0]["observed_steps_status"] != "nonempty" or fresh_operations is None:
                row["comparison"] = f"fresh_{fresh_group[0]['observed_steps_status']}"
            else:
                comparison, edits = _compare_operations(
                    fresh_operations,
                    preserved_group[0]["operations"],
                )
                row["comparison"] = comparison
                row["edit_counts"] = edits
                operation_counts["eligible"] += 1
                operation_counts[comparison] += 1
                operation_counts.update(edits)
        elif fresh_group:
            coverage["fresh_only"] += 1
            row["comparison"] = "fresh_only"
        else:
            coverage["preserved_only"] += 1
            row["comparison"] = "preserved_only"
        rows.append(row)

    bad_lengths = sum(
        record["length"] != len(record["operations"])
        for record in preserved_records
    )
    hash_to_ids: dict[str, set[str]] = defaultdict(set)
    missing_hash_ids: set[str] = set()
    for record in fresh_records:
        source_hash = record.get("source_sha256")
        if source_hash:
            hash_to_ids[str(source_hash)].add(record["canonical_script_id"])
        else:
            missing_hash_ids.add(record["canonical_script_id"])
    multi_id_hashes = {
        source_hash: sorted(script_ids)
        for source_hash, script_ids in hash_to_ids.items()
        if len(script_ids) > 1
    }

    row_by_id = {row["canonical_script_id"]: row for row in rows}
    conflict_hashes = {
        source_hash: sorted(
            script_id
            for script_id in script_ids
            if row_by_id[script_id]["comparison"] == "ambiguous_id"
        )
        for source_hash, script_ids in hash_to_ids.items()
        if any(
            row_by_id[script_id]["comparison"] == "ambiguous_id"
            for script_id in script_ids
        )
    }
    source_representatives = {}
    for source_hash, script_ids in hash_to_ids.items():
        if source_hash in conflict_hashes:
            continue
        unambiguous_ids = sorted(
            script_id
            for script_id in script_ids
            if row_by_id[script_id]["comparison"] != "ambiguous_id"
        )
        if unambiguous_ids:
            source_representatives[source_hash] = unambiguous_ids[0]
    source_coverage = Counter()
    source_operation_counts = Counter({
        "eligible": 0,
        "exact_match": 0,
        "same_multiset_different_order": 0,
        "changed": 0,
        "insertions": 0,
        "deletions": 0,
        "substitutions": 0,
    })
    source_operation_representatives: dict[str, str] = {}
    for source_hash, script_id in sorted(source_representatives.items()):
        row = row_by_id[script_id]
        comparison = row["comparison"]
        if comparison == "ambiguous_id":
            source_coverage["ambiguous"] += 1
        elif row["fresh_attempt_count"] and row["preserved_row_count"]:
            source_coverage["both_unambiguous"] += 1
        elif row["fresh_attempt_count"]:
            source_coverage["fresh_only"] += 1
        else:
            source_coverage["preserved_only"] += 1
        if comparison in {"exact_match", "same_multiset_different_order", "changed"}:
            source_operation_representatives[source_hash] = script_id
            source_operation_counts["eligible"] += 1
            source_operation_counts[comparison] += 1
            source_operation_counts.update(row.get("edit_counts", {}))

    summary = {
        "schema": "gis_recommend.gee_fresh_preserved_step1_comparison.v1",
        "fresh_source": {
            "attempt_rows": len(fresh_records),
            "unique_source_sha256": len(hash_counts),
            "runner_status_counts": dict(sorted(runner_status_counts.items())),
            "observed_steps_status_counts": dict(sorted(observed_status_counts.items())),
            "duplicate_cluster_count": sum(count > 1 for count in hash_counts.values()),
            "duplicate_rows": sum(count for count in hash_counts.values() if count > 1),
        },
        "source_identity": {
            "missing_hash_attempts": sum(not record.get("source_sha256") for record in fresh_records),
            "missing_hash_canonical_ids": len(missing_hash_ids),
            "multi_id_hash_clusters": len(multi_id_hashes),
            "multi_id_hash_examples": [
                {"source_sha256": source_hash, "canonical_script_ids": script_ids}
                for source_hash, script_ids in sorted(multi_id_hashes.items())[:100]
            ],
        },
        "preserved_step1": {
            "declared_total_count": preserved_payload.get("total_count"),
            "actual_workflow_rows": len(preserved_records),
            "declared_empty_count": preserved_payload.get("empty_count"),
            "declared_error_count": preserved_payload.get("error_count"),
            "unique_script_ids": len(preserved_by_id),
            "unique_operation_sequences": len({record["operations_sha256"] for record in preserved_records}),
            "bad_length_rows": bad_lengths,
            "source_sha256_available": False,
        },
        "identity_conflicts": {
            "fresh_duplicate_id_clusters": fresh_duplicate_ids,
            "fresh_id_hash_conflicts": fresh_hash_conflicts,
            "preserved_duplicate_id_clusters": preserved_duplicate_ids,
            "preserved_id_operation_conflicts": preserved_operation_conflicts,
        },
        "coverage": {
            key: coverage[key]
            for key in ("both_unambiguous", "fresh_only", "preserved_only", "ambiguous")
        },
        "operations_comparison": {
            key: operation_counts[key]
            for key in (
                "eligible", "exact_match", "same_multiset_different_order", "changed",
                "insertions", "deletions", "substitutions",
            )
        },
        "source_level_coverage": {
            "representative_rule": "lexicographically_smallest_unambiguous_canonical_script_id",
            "missing_hash_excluded": len(missing_hash_ids),
            "conflict_hashes_excluded": len(conflict_hashes),
            "conflict_hash_examples": [
                {"source_sha256": source_hash, "canonical_script_ids": script_ids}
                for source_hash, script_ids in sorted(conflict_hashes.items())[:100]
            ],
            "representatives": source_representatives,
            **{
                key: source_coverage[key]
                for key in ("both_unambiguous", "fresh_only", "preserved_only", "ambiguous")
            },
        },
        "source_level_operations_comparison": {
            "representative_rule": "lexicographically_smallest_unambiguous_canonical_script_id",
            "missing_hash_excluded": len(missing_hash_ids),
            "conflict_hashes_excluded": len(conflict_hashes),
            "representatives": source_operation_representatives,
            **{
                key: source_operation_counts[key]
                for key in (
                    "eligible", "exact_match", "same_multiset_different_order", "changed",
                    "insertions", "deletions", "substitutions",
                )
            },
        },
    }
    return summary, rows


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            json.dump(payload, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temp_path.replace(path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def _atomic_write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            for row in rows:
                json.dump(row, handle, ensure_ascii=False, sort_keys=True)
                handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        temp_path.replace(path)
    finally:
        if temp_path.exists():
            temp_path.unlink()


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fresh-root", type=Path, required=True)
    parser.add_argument("--preserved-step1", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    summary, rows = build_comparison(args.fresh_root, args.preserved_step1)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    summary_path = args.output_dir / "comparison_summary.json"
    comparison_path = args.output_dir / "comparison.jsonl"
    _atomic_write_json(summary_path, summary)
    _atomic_write_jsonl(comparison_path, rows)
    return {"summary": summary_path, "comparison": comparison_path}


if __name__ == "__main__":
    main()
