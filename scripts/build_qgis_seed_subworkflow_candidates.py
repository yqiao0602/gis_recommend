#!/usr/bin/env python3
"""Derive review-only subworkflow candidates from reviewed QGIS workflow seeds.

This intentionally does not concatenate unrelated operators. A candidate is a
contiguous path already present in a reviewed source workflow, whose adjacent
catalogue input/output types are compatible. The output is not training data.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

SCHEMA = "gis_recommend.qgis_seed_subworkflow_candidate.v1"
CONSTRAINT_PROFILE = "qgis_catalog_io_contiguous_source_path_v1"


def _hash(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _load_catalog(path: Path) -> dict[str, dict[str, Any]]:
    document = json.loads(path.read_text(encoding="utf-8"))
    return {str(row["operator_id"]): row for row in document["operators"]}


def _types_compatible(left: dict[str, Any], right: dict[str, Any]) -> bool:
    outputs = {str(value) for value in left.get("output_types", [])}
    inputs = {str(value) for value in right.get("input_types", [])}
    concrete_outputs = outputs - {"LiteralData"}
    concrete_inputs = inputs - {"LiteralData"}
    if not concrete_outputs or not concrete_inputs:
        return False
    if concrete_outputs & concrete_inputs:
        return True
    return "geographicData" in concrete_inputs and bool(concrete_outputs & {"raster", "vector"})


def _edge_paths(edges: Iterable[Iterable[int]], size: int, minimum_length: int, maximum_length: int) -> list[tuple[int, ...]]:
    successors: dict[int, set[int]] = {index: set() for index in range(size)}
    predecessors: dict[int, set[int]] = {index: set() for index in range(size)}
    for edge in edges:
        values = list(edge)
        if len(values) != 2:
            continue
        start, end = values
        if isinstance(start, int) and isinstance(end, int) and 0 <= start < size and 0 <= end < size and start < end:
            successors[start].add(end)
            predecessors[end].add(start)

    paths: set[tuple[int, ...]] = set()

    def visit(path: tuple[int, ...]) -> None:
        if len(path) >= minimum_length:
            paths.add(path)
        if len(path) == maximum_length:
            return
        for successor in sorted(successors[path[-1]]):
            visit((*path, successor))

    for start in range(size):
        visit((start,))
    return sorted(paths)


def build_candidates(
    rows: Iterable[dict[str, Any]],
    catalog: dict[str, dict[str, Any]],
    *,
    maximum_length: int = 4,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows = list(rows)
    candidates: list[dict[str, Any]] = []
    rejections: Counter[str] = Counter()
    for seed in rows:
        if seed.get("workflow_scope") != "whole_processing_scope":
            rejections["not_processing_workflow_seed"] += 1
            continue
        if seed.get("semantic_review_decision") not in {"gold", "retain_silver"}:
            rejections["not_reviewed_seed"] += 1
            continue
        operators = [str(value) for value in seed.get("operator_sequence", [])]
        l3_codes = [str(value) for value in seed.get("l3_code_sequence", [])]
        if len(operators) != len(l3_codes) or len(operators) < 2:
            rejections["not_multistep"] += 1
            continue
        if any(operator not in catalog for operator in operators):
            rejections["catalog_missing_operator"] += 1
            continue
        for path in _edge_paths(seed.get("dependency_edges") or [], len(operators), 2, maximum_length):
            path_operators = [operators[index] for index in path]
            if not all(
                _types_compatible(catalog[left], catalog[right])
                for left, right in zip(path_operators, path_operators[1:])
            ):
                rejections["catalog_io_incompatible"] += 1
                continue
            names = [str(catalog[operator].get("official_name") or operator) for operator in path_operators]
            candidate_id = _hash(
                {
                    "seed_sample_id": seed.get("sample_id"),
                    "source_sha256": seed.get("source_sha256"),
                    "path": path,
                    "operators": path_operators,
                }
            )
            parent_weight = float((seed.get("_training_quality") or {}).get("sample_weight", 0.7))
            candidates.append(
                {
                    "schema": SCHEMA,
                    "candidate_id": candidate_id,
                    "candidate_origin": "source_derived_contiguous_subworkflow",
                    "review_status": "pending_independent_semantic_review",
                    "review_decision_options": [
                        "independent_workflow",
                        "implementation_subworkflow",
                        "duplicate_or_parent_contained",
                    ],
                    "training_admission": "not_granted_candidate_only",
                    "validation_eligible": False,
                    "test_eligible": False,
                    "seed_sample_id": seed.get("sample_id"),
                    "seed_source_sha256": seed.get("source_sha256"),
                    "parent_workflow_id": seed.get("sample_id"),
                    "split_group_key": f"parent_source_sha256:{seed.get('source_sha256')}",
                    "cross_split_policy": "all_parent_subworkflows_must_share_one_split",
                    "seed_source_path": seed.get("source_path"),
                    "seed_source_span": seed.get("source_span"),
                    "seed_semantic_review_decision": seed.get("semantic_review_decision"),
                    "seed_task_name": seed.get("task_name"),
                    "seed_task_description": seed.get("task_description"),
                    "seed_operator_sequence": operators,
                    "seed_l3_code_sequence": l3_codes,
                    "seed_path_indices": list(path),
                    "operator_sequence": path_operators,
                    "l3_code_sequence": [l3_codes[index] for index in path],
                    "subworkflow_input_types": sorted(
                        set(catalog[path_operators[0]].get("input_types", [])) - {"LiteralData"}
                    ),
                    "subworkflow_output_types": sorted(
                        set(catalog[path_operators[-1]].get("output_types", [])) - {"LiteralData"}
                    ),
                    "constraint_profile": CONSTRAINT_PROFILE,
                    "catalog_io_checks": [
                        {
                            "from_operator": left,
                            "to_operator": right,
                            "compatible": True,
                        }
                        for left, right in zip(path_operators, path_operators[1:])
                    ],
                    "task_name": f"{seed.get('task_name') or 'QGIS workflow'} subworkflow",
                    "task_description": f"在已审核的 QGIS 工作流中，依次执行{'，再'.join(names)}。",
                    "proposed_sample_weight": round(parent_weight * 0.4, 2),
                }
            )
    candidates.sort(key=lambda row: row["candidate_id"])
    summary = {
        "schema": f"{SCHEMA}.summary",
        "input_seed_rows": len(rows),
        "candidate_rows": len(candidates),
        "candidate_training_rows": 0,
        "training_admission": "not_granted_candidate_only",
        "constraint_profile": CONSTRAINT_PROFILE,
        "parent_seed_rows": len({str(row["seed_sample_id"]) for row in candidates}),
        "parent_decision_counts": dict(
            sorted(Counter(str(row["seed_semantic_review_decision"]) for row in candidates).items())
        ),
        "path_length_counts": dict(sorted(Counter(len(row["operator_sequence"]) for row in candidates).items())),
        "rejections": dict(sorted(rejections.items())),
    }
    return candidates, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=Path, required=True)
    parser.add_argument("--catalog", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--maximum-length", type=int, default=4)
    args = parser.parse_args()
    if not 2 <= args.maximum_length <= 6:
        raise ValueError("--maximum-length must be between 2 and 6")
    rows = _read_jsonl(args.seeds)
    candidates, summary = build_candidates(rows, _load_catalog(args.catalog), maximum_length=args.maximum_length)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    candidate_path = args.output_dir / "review_candidates_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    candidate_path.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in candidates),
        encoding="utf-8",
    )
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in (candidate_path, summary_path)}
    (args.output_dir / "hash_ledger_v1.json").write_text(
        json.dumps(hashes, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
