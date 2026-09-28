#!/usr/bin/env python3
"""Build a deterministic dedup ledger for accepted stable101 recovery units."""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
from difflib import SequenceMatcher
import hashlib
import io
import json
from pathlib import Path
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REVIEW_DIR = (
    ROOT
    / "docs/reports/qgis_mapping_high_impact_blockers_2026-07-24"
    / "stable101_source_review_50_v1/recovered_review_v1"
)
DEFAULT_REVIEW = DEFAULT_REVIEW_DIR / "recovery_review_29_v1.jsonl"
DEFAULT_ADJUDICATIONS = [
    DEFAULT_REVIEW_DIR / "recovery_adjudications_1_10_v1.jsonl",
    DEFAULT_REVIEW_DIR / "recovery_adjudications_11_20_v1.jsonl",
    DEFAULT_REVIEW_DIR / "recovery_adjudications_21_29_v1.jsonl",
]
DEFAULT_OUTPUT_DIR = DEFAULT_REVIEW_DIR.parent / "recovered_training_v1"
NEAR_DUPLICATE_THRESHOLD = 0.9


@dataclass(frozen=True)
class DedupResult:
    rows: list[dict[str, Any]]
    summary: dict[str, Any]


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _json_key(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"expected JSON object at {path}:{line_number}")
            rows.append(value)
    return rows


def _index_unique(rows: list[dict[str, Any]], field: str) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row[field])
        if key in indexed:
            raise ValueError(f"duplicate {field}: {key}")
        indexed[key] = row
    return indexed


def _normalized_source_segments(source_span: dict[str, Any]) -> list[dict[str, int]]:
    segments = source_span.get("segments") or [source_span]
    return [
        {"line_start": int(segment["line_start"]), "line_end": int(segment["line_end"])}
        for segment in segments
    ]


def _source_region_key(review: dict[str, Any]) -> str:
    return _json_key(
        {
            "source_sha256": review["source_sha256"],
            "segments": _normalized_source_segments(review["source_span"]),
        }
    )


def _call_graph_key(review: dict[str, Any]) -> str:
    source_calls = [
        {
            "owner": call.get("owner", ""),
            "operator_id": call["operator_id"],
            "line_start": int(call["line_start"]),
            "line_end": int(call["line_end"]),
            "expansion_call_line": call.get("expansion_call_line"),
        }
        for call in review.get("source_calls") or []
    ]
    return _json_key(
        {
            "source_sha256": review["source_sha256"],
            "entrypoint": review.get("entrypoint", ""),
            "call_graph_path": review.get("call_graph_path") or [],
            "source_calls": source_calls,
        }
    )


def _normalized_dag_key(review: dict[str, Any]) -> str:
    edges = sorted(
        (
            int(edge["producer_ordinal"]),
            int(edge["consumer_ordinal"]),
            str(edge.get("dependency_kind", "data")),
        )
        for edge in review.get("dependency_edges") or []
    )
    branch_groups = sorted(
        tuple(sorted(int(value) for value in group.get("member_ordinals") or []))
        for group in review.get("branch_groups") or []
    )
    return _json_key(
        {
            "operator_sequence": review["operator_sequence"],
            "dependency_edges": edges,
            "optional_operator_ordinals": sorted(
                int(value) for value in review.get("optional_operator_ordinals") or []
            ),
            "branch_groups": branch_groups,
        }
    )


def _normalize_task_text(value: str) -> str:
    return "".join(str(value).lower().split())


def _task_similarity(left: dict[str, Any], right: dict[str, Any]) -> float:
    left_text = _normalize_task_text(left.get("task_description", ""))
    right_text = _normalize_task_text(right.get("task_description", ""))
    return SequenceMatcher(None, left_text, right_text).ratio()


def _validate_source(review: dict[str, Any]) -> None:
    source_path = Path(review["source_path"])
    if not source_path.is_file():
        raise FileNotFoundError(source_path)
    if _sha256(source_path) != review["source_sha256"]:
        raise ValueError(f"source SHA256 mismatch: {review['unit_id']}")


def build_recovered_dedup_ledger(
    *,
    review_jsonl_path: Path,
    adjudication_paths: list[Path],
) -> DedupResult:
    reviews = _index_unique(_load_jsonl(review_jsonl_path), "unit_id")
    adjudications = _index_unique(
        [row for path in adjudication_paths for row in _load_jsonl(path)], "unit_id"
    )
    if set(reviews) != set(adjudications):
        missing = sorted(set(reviews) - set(adjudications))
        extra = sorted(set(adjudications) - set(reviews))
        raise ValueError(f"review/adjudication coverage mismatch: missing={missing}, extra={extra}")

    accepted = sorted(
        (
            (adjudication, reviews[unit_id])
            for unit_id, adjudication in adjudications.items()
            if adjudication.get("final_decision") == "accept_recovered"
        ),
        key=lambda pair: int(pair[0]["batch_position"]),
    )
    rows: list[dict[str, Any]] = []
    for adjudication, review in accepted:
        if adjudication.get("source_sha256") != review.get("source_sha256"):
            raise ValueError(f"source identity mismatch: {review['unit_id']}")
        if adjudication.get("operator_sequence") != review.get("operator_sequence"):
            raise ValueError(f"operator sequence mismatch: {review['unit_id']}")
        if adjudication.get("l3_code_sequence") != review.get("l3_code_sequence"):
            raise ValueError(f"L3 sequence mismatch: {review['unit_id']}")
        _validate_source(review)
        rows.append(
            {
                "schema_version": "qgis_stable101_recovered_dedup_ledger_v1",
                "batch_position": int(adjudication["batch_position"]),
                "unit_id": review["unit_id"],
                "review_index": int(review["review_index"]),
                "record_id": review["record_id"],
                "source_root_id": review["source_root_id"],
                "source_path": review["source_path"],
                "relative_path": review["relative_path"],
                "source_sha256": review["source_sha256"],
                "source_span": review["source_span"],
                "entrypoint": review["entrypoint"],
                "call_graph_path": review.get("call_graph_path") or [],
                "operator_sequence": review["operator_sequence"],
                "l3_code_sequence": review["l3_code_sequence"],
                "l3_token_ids": review["l3_token_ids"],
                "dependency_edges": review.get("dependency_edges") or [],
                "dependency_status": review["dependency_status"],
                "optional_operator_ordinals": review.get("optional_operator_ordinals") or [],
                "branch_groups": review.get("branch_groups") or [],
                "task_name": adjudication["task_name"],
                "task_description": adjudication["task_description"],
                "evidence_snippet": review["evidence_snippet"],
                "expansion_evidence_snippet": review.get("expansion_evidence_snippet", ""),
                "recovery_method": review["recovery_method"],
                "workflow_scope": review["workflow_scope"],
                "known_omissions": review.get("known_omissions") or [],
                "source_region_key": _source_region_key(review),
                "call_graph_key": _call_graph_key(review),
                "normalized_dag_key": _normalized_dag_key(review),
                "task_text_key": _json_key(
                    _normalize_task_text(adjudication["task_description"])
                ),
                "dedup_decision": "canonical_keep",
                "canonical_unit_id": review["unit_id"],
                "near_duplicate_cluster_id": "",
                "task_text_similarity_to_canonical": 1.0,
                "dedup_reason": "unique source region or distinct task semantics",
                "training_admission": "not_granted_pending_recovered_export",
                "validation_eligible": False,
                "test_eligible": False,
            }
        )

    for index, row in enumerate(rows):
        for canonical in rows[:index]:
            same_source = row["source_sha256"] == canonical["source_sha256"]
            same_dag = row["normalized_dag_key"] == canonical["normalized_dag_key"]
            similarity = _task_similarity(row, canonical)
            if same_source and same_dag and similarity >= NEAR_DUPLICATE_THRESHOLD:
                cluster_id = "near_" + _json_key(
                    [canonical["unit_id"], row["unit_id"]]
                )[:16]
                canonical["near_duplicate_cluster_id"] = cluster_id
                row["near_duplicate_cluster_id"] = cluster_id
                row["task_text_similarity_to_canonical"] = round(similarity, 6)
                row["dedup_decision"] = "near_duplicate_suppressed"
                row["canonical_unit_id"] = canonical["unit_id"]
                row["dedup_reason"] = (
                    "same source, normalized DAG, control condition, and near-identical task text"
                )
                row["training_admission"] = "not_granted_near_duplicate"
                break

    final_counts = {
        "rows": len(adjudications),
        "accept_recovered": len(rows),
        "deferred": sum(
            1
            for row in adjudications.values()
            if str(row.get("final_decision", "")).startswith("defer")
        ),
        "rejected": sum(
            1
            for row in adjudications.values()
            if str(row.get("final_decision", "")).startswith("reject")
        ),
    }
    canonical_rows = [row for row in rows if row["dedup_decision"] == "canonical_keep"]
    summary = {
        "schema": "gis_recommend.qgis_stable101_recovered_dedup_summary.v1",
        "adjudication_counts": final_counts,
        "dedup_counts": {
            "candidate_rows": len(rows),
            "canonical_rows": len(canonical_rows),
            "suppressed_rows": len(rows) - len(canonical_rows),
            "unique_sources": len({row["source_sha256"] for row in rows}),
            "unique_source_regions": len({row["source_region_key"] for row in rows}),
            "unique_call_graphs": len({row["call_graph_key"] for row in rows}),
            "unique_normalized_dags": len({row["normalized_dag_key"] for row in rows}),
            "near_duplicate_clusters": len(
                {row["near_duplicate_cluster_id"] for row in rows if row["near_duplicate_cluster_id"]}
            ),
        },
        "policy": {
            "source_region_key": "source_sha256 + ordered source-span segments",
            "call_graph_key": "source_sha256 + entrypoint + call path + source call sites",
            "normalized_dag_key": "operator sequence + dependency edges + optional ordinals + branch groups",
            "near_duplicate_rule": (
                "same source_sha256 and normalized_dag_key with task-description similarity >= 0.9"
            ),
            "operator_sequence_only_dedup": False,
        },
        "decision": {
            "training_admission": "not_granted_pending_recovered_export",
            "validation_eligible": False,
            "test_eligible": False,
            "next_gate": "export canonical rows to isolated recovered-only training JSONL",
        },
    }
    return DedupResult(rows=rows, summary=summary)


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def _jsonl_text(rows: list[dict[str, Any]]) -> str:
    return "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for row in rows
    )


def _csv_text(rows: list[dict[str, Any]]) -> str:
    fieldnames = list(rows[0])
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fieldnames)
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                key: (
                    json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
                    if isinstance(value, (list, dict))
                    else value
                )
                for key, value in row.items()
            }
        )
    return output.getvalue()


def write_outputs(
    result: DedupResult,
    output_dir: Path,
    review_jsonl_path: Path,
    adjudication_paths: list[Path],
) -> dict[str, Path]:
    output_dir = Path(output_dir)
    ledger_jsonl = output_dir / "stable101_recovered_dedup_25_v1.jsonl"
    ledger_csv = output_dir / "stable101_recovered_dedup_25_v1.csv"
    summary = output_dir / "stable101_recovered_dedup_25_summary_v1.json"
    hash_ledger = output_dir / "stable101_recovered_dedup_25_hash_ledger_v1.json"
    _atomic_write(ledger_jsonl, _jsonl_text(result.rows))
    _atomic_write(ledger_csv, _csv_text(result.rows))
    _atomic_write(summary, json.dumps(result.summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    inputs = [review_jsonl_path, *adjudication_paths]
    hashes = {
        "schema": "gis_recommend.hash_ledger.v1",
        "source_inputs": {
            path.name: {"path": str(path), "sha256": _sha256(path)} for path in inputs
        },
        "artifacts": {
            path.name: {
                "path": str(path),
                "sha256": _sha256(path),
                "bytes": path.stat().st_size,
            }
            for path in (ledger_jsonl, ledger_csv, summary)
        },
    }
    _atomic_write(hash_ledger, json.dumps(hashes, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return {
        "ledger_jsonl": ledger_jsonl,
        "ledger_csv": ledger_csv,
        "summary": summary,
        "hash_ledger": hash_ledger,
    }


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-jsonl", type=Path, default=DEFAULT_REVIEW)
    parser.add_argument(
        "--adjudications", type=Path, nargs="+", default=DEFAULT_ADJUDICATIONS
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)
    result = build_recovered_dedup_ledger(
        review_jsonl_path=args.review_jsonl,
        adjudication_paths=list(args.adjudications),
    )
    return write_outputs(
        result,
        args.output_dir,
        args.review_jsonl,
        list(args.adjudications),
    )


if __name__ == "__main__":
    main()
