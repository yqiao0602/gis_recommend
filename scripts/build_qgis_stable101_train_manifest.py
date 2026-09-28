#!/usr/bin/env python3
"""Audit and combine the 19 ready-now and 24 recovered QGIS pilot rows."""

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
REVIEW_ROOT = (
    ROOT
    / "docs/reports/qgis_mapping_high_impact_blockers_2026-07-24"
    / "stable101_source_review_50_v1"
)
DEFAULT_READY_JSONL = (
    REVIEW_ROOT / "accepted_training_v1/stable101_accepted_training_19_v1.jsonl"
)
DEFAULT_RECOVERED_JSONL = (
    REVIEW_ROOT / "recovered_training_v1/stable101_recovered_training_24_v1.jsonl"
)
DEFAULT_OUTPUT_DIR = REVIEW_ROOT / "qgis43_manifest_v1"
DEFAULT_MANIFEST_JSONL = DEFAULT_OUTPUT_DIR / "qgis43_train_v1.jsonl"
DEFAULT_AUDIT_CSV = DEFAULT_OUTPUT_DIR / "qgis43_audit_v1.csv"
DEFAULT_SOURCE_GROUPS_JSONL = DEFAULT_OUTPUT_DIR / "qgis43_source_groups_v1.jsonl"
DEFAULT_SUMMARY = DEFAULT_OUTPUT_DIR / "qgis43_summary_v1.json"
DEFAULT_REPORT = DEFAULT_OUTPUT_DIR / "qgis43_report_v1.md"
DEFAULT_HASH_LEDGER = DEFAULT_OUTPUT_DIR / "qgis43_hashes_v1.json"
DEFAULT_ARTIFACT_PATHS = (
    DEFAULT_MANIFEST_JSONL,
    DEFAULT_AUDIT_CSV,
    DEFAULT_SOURCE_GROUPS_JSONL,
    DEFAULT_SUMMARY,
    DEFAULT_REPORT,
    DEFAULT_HASH_LEDGER,
)
NEAR_DUPLICATE_THRESHOLD = 0.9
MANIFEST_ADMISSION = "granted_train_only_qgis43_pilot"
MANIFEST_SPLIT = "train_only_qgis43_pilot"


@dataclass(frozen=True)
class ManifestResult:
    rows: list[dict[str, Any]]
    audit_rows: list[dict[str, Any]]
    source_groups: list[dict[str, Any]]
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


def _normalize_text(value: Any) -> str:
    return "".join(str(value or "").lower().split())


def _task_similarity(left: dict[str, Any], right: dict[str, Any]) -> float:
    return SequenceMatcher(
        None,
        _normalize_text(left.get("task_description")),
        _normalize_text(right.get("task_description")),
    ).ratio()


def _ordered_segments(row: dict[str, Any]) -> list[dict[str, int]]:
    span = row.get("source_span") or {}
    raw_segments = span.get("segments") or span.get("call_sites") or [span]
    return [
        {
            "line_start": int(segment["line_start"]),
            "line_end": int(segment["line_end"]),
        }
        for segment in raw_segments
    ]


def _source_region_key(row: dict[str, Any]) -> str:
    existing = str(row.get("source_region_key") or "")
    if existing:
        return existing
    return _json_key(
        {
            "source_sha256": row["source_sha256"],
            "segments": _ordered_segments(row),
        }
    )


def _call_graph_key(row: dict[str, Any]) -> str:
    existing = str(row.get("call_graph_key") or "")
    if existing:
        return existing
    return _json_key(
        {
            "source_sha256": row["source_sha256"],
            "entrypoint": row.get("entrypoint", ""),
            "segments": _ordered_segments(row),
            "operator_sequence": row["operator_sequence"],
        }
    )


def _normalized_dag_key(row: dict[str, Any]) -> str:
    existing = str(row.get("normalized_dag_key") or "")
    if existing:
        return existing
    edges = sorted(
        (
            int(edge["producer_ordinal"]),
            int(edge["consumer_ordinal"]),
            str(edge.get("dependency_kind", "data")),
        )
        for edge in row.get("dependency_edges") or []
    )
    branch_groups = sorted(
        tuple(sorted(int(value) for value in group.get("member_ordinals") or []))
        for group in row.get("branch_groups") or []
    )
    return _json_key(
        {
            "operator_sequence": row["operator_sequence"],
            "dependency_edges": edges,
            "optional_operator_ordinals": sorted(
                int(value) for value in row.get("optional_operator_ordinals") or []
            ),
            "branch_groups": branch_groups,
        }
    )


def _validate_input_row(
    row: dict[str, Any],
    *,
    pool: str,
    expected_admission: str,
    expected_split: str,
    expected_weight: float,
) -> None:
    sample_id = str(row.get("sample_id") or "")
    if not sample_id:
        raise ValueError(f"missing sample_id in {pool}")
    if row.get("schema_version") != "qgis_stable101_training_sample_v1":
        raise ValueError(f"unexpected schema: {sample_id}")
    if row.get("training_admission") != expected_admission:
        raise ValueError(f"unexpected source admission: {sample_id}")
    if row.get("split") != expected_split:
        raise ValueError(f"unexpected source split: {sample_id}")
    if row.get("validation_eligible") or row.get("test_eligible"):
        raise ValueError(f"validation/test eligible source row: {sample_id}")
    weight = float((row.get("_training_quality") or {}).get("sample_weight", 0))
    if weight != expected_weight:
        raise ValueError(f"unexpected source sample weight: {sample_id}")
    source_path = Path(row.get("source_path") or "")
    if not source_path.is_file() or _sha256(source_path) != row.get("source_sha256"):
        raise ValueError(f"source identity mismatch: {sample_id}")
    operators = row.get("operator_sequence") or []
    l3_codes = row.get("l3_code_sequence") or []
    tokens = [int(value) for value in row.get("l3_token_ids") or []]
    sequence = [int(value) for value in row.get("l3_sequence") or []]
    if not operators or len(operators) != len(l3_codes) or len(operators) != len(tokens):
        raise ValueError(f"operator/L3/token length mismatch: {sample_id}")
    if sequence != [-3, *tokens, -4] or min(tokens) < 0 or max(tokens) > 100:
        raise ValueError(f"invalid stable101 token sequence: {sample_id}")
    if not _normalize_text(row.get("task_name")) or not _normalize_text(
        row.get("task_description")
    ):
        raise ValueError(f"missing task text: {sample_id}")


def _source_group_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        grouped.setdefault(row["source_sha256"], []).append(row)
    groups: list[dict[str, Any]] = []
    for source_sha256, members in sorted(grouped.items()):
        ordered = sorted(members, key=lambda row: row["sample_id"])
        groups.append(
            {
                "schema_version": "qgis_stable101_source_group_v1",
                "source_group_id": f"sha256:{source_sha256}",
                "source_sha256": source_sha256,
                "source_paths": sorted({row["source_path"] for row in ordered}),
                "source_pools": sorted({row["manifest_source_pool"] for row in ordered}),
                "sample_ids": [row["sample_id"] for row in ordered],
                "review_indices": sorted({int(row["review_index"]) for row in ordered}),
                "row_count": len(ordered),
                "multirow_source_group": len(ordered) > 1,
                "split_constraint": "keep_all_rows_in_one_future_split",
                "validation_eligible": False,
                "test_eligible": False,
            }
        )
    return groups


def build_train_manifest(
    *,
    ready_jsonl_path: Path,
    recovered_jsonl_path: Path,
) -> ManifestResult:
    ready_rows = _load_jsonl(ready_jsonl_path)
    recovered_rows = _load_jsonl(recovered_jsonl_path)
    if len(ready_rows) != 19 or len(recovered_rows) != 24:
        raise ValueError(
            f"expected 19 ready and 24 recovered rows, got {len(ready_rows)}/{len(recovered_rows)}"
        )

    pool_specs = [
        (
            "ready_now",
            ready_rows,
            "granted_train_only_pilot",
            "train_only_pilot",
            1.0,
        ),
        (
            "recovered_canonical",
            recovered_rows,
            "granted_train_only_recovered_pilot",
            "train_only_recovered_pilot",
            0.8,
        ),
    ]
    rows: list[dict[str, Any]] = []
    audit_rows: list[dict[str, Any]] = []
    for pool, source_rows, admission, split, weight in pool_specs:
        for source_row in source_rows:
            _validate_input_row(
                source_row,
                pool=pool,
                expected_admission=admission,
                expected_split=split,
                expected_weight=weight,
            )
            row = dict(source_row)
            row["source_training_admission"] = admission
            row["source_split"] = split
            row["manifest_source_pool"] = pool
            row["manifest_id"] = "qgis_stable101_train43_v1"
            row["manifest_role"] = "train"
            row["source_group_id"] = f"sha256:{row['source_sha256']}"
            row["source_region_key"] = _source_region_key(row)
            row["call_graph_key"] = _call_graph_key(row)
            row["normalized_dag_key"] = _normalized_dag_key(row)
            row["training_admission"] = MANIFEST_ADMISSION
            row["split"] = MANIFEST_SPLIT
            row["validation_eligible"] = False
            row["test_eligible"] = False
            rows.append(row)

    if len({row["sample_id"] for row in rows}) != len(rows):
        raise ValueError("cross-pool sample_id collision")

    ready_sources = {row["source_sha256"] for row in ready_rows}
    recovered_sources = {row["source_sha256"] for row in recovered_rows}
    ready_records = {row["record_id"] for row in ready_rows}
    recovered_records = {row["record_id"] for row in recovered_rows}
    ready_sequences = {tuple(row["operator_sequence"]) for row in ready_rows}
    recovered_sequences = {tuple(row["operator_sequence"]) for row in recovered_rows}
    common_sequences = sorted(ready_sequences & recovered_sequences)

    similarities = [
        (_task_similarity(left, right), left["sample_id"], right["sample_id"])
        for left in ready_rows
        for right in recovered_rows
    ]
    max_similarity = max(value for value, _, _ in similarities)
    near_pairs = [pair for pair in similarities if pair[0] >= NEAR_DUPLICATE_THRESHOLD]

    sequence_pool_counts: dict[tuple[str, ...], set[str]] = {}
    for row in rows:
        sequence_pool_counts.setdefault(tuple(row["operator_sequence"]), set()).add(
            row["manifest_source_pool"]
        )
    for row in rows:
        sequence = tuple(row["operator_sequence"])
        cross_pool_sequence_duplicate = len(sequence_pool_counts[sequence]) > 1
        decision_reason = (
            "same operator sequence exists in both pools, but source identity and task semantics differ"
            if cross_pool_sequence_duplicate
            else "no cross-pool duplicate evidence"
        )
        audit_rows.append(
            {
                "sample_id": row["sample_id"],
                "manifest_source_pool": row["manifest_source_pool"],
                "source_training_admission": row["source_training_admission"],
                "manifest_training_admission": row["training_admission"],
                "source_sha256": row["source_sha256"],
                "source_group_id": row["source_group_id"],
                "source_region_key": row["source_region_key"],
                "call_graph_key": row["call_graph_key"],
                "normalized_dag_key": row["normalized_dag_key"],
                "operator_sequence": row["operator_sequence"],
                "l3_code_sequence": row["l3_code_sequence"],
                "task_name": row["task_name"],
                "cross_pool_sequence_duplicate": cross_pool_sequence_duplicate,
                "cross_pool_decision": "keep",
                "decision_reason": decision_reason,
                "validation_eligible": False,
                "test_eligible": False,
            }
        )

    source_groups = _source_group_rows(rows)
    operator_sequences = {tuple(row["operator_sequence"]) for row in rows}
    l3_sequences = {tuple(row["l3_code_sequence"]) for row in rows}
    summary = {
        "schema": "gis_recommend.qgis_stable101_train_manifest_summary.v1",
        "counts": {
            "ready_now_rows": len(ready_rows),
            "recovered_canonical_rows": len(recovered_rows),
            "input_rows": len(ready_rows) + len(recovered_rows),
            "manifest_rows": len(rows),
            "suppressed_rows": 0,
            "source_groups": len(source_groups),
            "multirow_source_groups": sum(
                1 for group in source_groups if group["multirow_source_group"]
            ),
            "unique_source_regions": len({row["source_region_key"] for row in rows}),
            "unique_call_graphs": len({row["call_graph_key"] for row in rows}),
            "unique_normalized_dags": len({row["normalized_dag_key"] for row in rows}),
            "unique_operator_sequences": len(operator_sequences),
            "unique_l3_sequences": len(l3_sequences),
            "min_chain_length": min(int(row["n"]) for row in rows),
            "max_chain_length": max(int(row["n"]) for row in rows),
        },
        "cross_pool_audit": {
            "common_source_sha256": len(ready_sources & recovered_sources),
            "common_record_ids": len(ready_records & recovered_records),
            "common_operator_sequences": len(common_sequences),
            "near_duplicate_pairs": len(near_pairs),
            "max_task_text_similarity": round(max_similarity, 6),
        },
        "common_operator_sequences": [list(sequence) for sequence in common_sequences],
        "source_group_policy": "all rows with one source_sha256 must remain in one future split",
        "decision": {
            "manifest_admission": MANIFEST_ADMISSION,
            "split": MANIFEST_SPLIT,
            "production_merge": "not_granted",
            "validation_eligible": False,
            "test_eligible": False,
            "llm_called": False,
            "training_run": False,
            "next_gate": "run real loader/loss smoke, then define the next source-conversion sample",
        },
    }
    return ManifestResult(
        rows=rows,
        audit_rows=audit_rows,
        source_groups=source_groups,
        summary=summary,
    )


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
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=list(rows[0]))
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


def _report_text(summary: dict[str, Any]) -> str:
    counts = summary["counts"]
    audit = summary["cross_pool_audit"]
    return f"""# QGIS stable101 train-only manifest v1

## Result

- input rows: {counts['input_rows']} (19 ready-now + 24 recovered canonical)
- manifest rows: {counts['manifest_rows']}
- source groups: {counts['source_groups']} ({counts['multirow_source_groups']} multirow)
- unique operator sequences: {counts['unique_operator_sequences']}
- unique L3 sequences: {counts['unique_l3_sequences']}
- chain length: {counts['min_chain_length']}..{counts['max_chain_length']}

## Cross-pool audit

- common source SHA256: {audit['common_source_sha256']}
- common record IDs: {audit['common_record_ids']}
- common operator sequences: {audit['common_operator_sequences']}
- task-text near-duplicate pairs: {audit['near_duplicate_pairs']}
- max task-text similarity: {audit['max_task_text_similarity']}
- suppressed rows: {counts['suppressed_rows']}

Equal operator sequences are retained when source identity and task semantics differ.
All rows remain train-only; production merge and validation/test admission are not granted.
"""


def write_outputs(
    result: ManifestResult,
    output_dir: Path,
    ready_jsonl_path: Path,
    recovered_jsonl_path: Path,
) -> dict[str, Path]:
    output_dir = Path(output_dir)
    manifest_jsonl = output_dir / DEFAULT_MANIFEST_JSONL.name
    audit_csv = output_dir / DEFAULT_AUDIT_CSV.name
    source_groups_jsonl = output_dir / DEFAULT_SOURCE_GROUPS_JSONL.name
    summary = output_dir / DEFAULT_SUMMARY.name
    report = output_dir / DEFAULT_REPORT.name
    hash_ledger = output_dir / DEFAULT_HASH_LEDGER.name
    _atomic_write(manifest_jsonl, _jsonl_text(result.rows))
    _atomic_write(audit_csv, _csv_text(result.audit_rows))
    _atomic_write(source_groups_jsonl, _jsonl_text(result.source_groups))
    _atomic_write(summary, json.dumps(result.summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    _atomic_write(report, _report_text(result.summary))
    artifacts = (manifest_jsonl, audit_csv, source_groups_jsonl, summary, report)
    hashes = {
        "schema": "gis_recommend.hash_ledger.v1",
        "source_inputs": {
            "ready_jsonl": {"path": str(ready_jsonl_path), "sha256": _sha256(ready_jsonl_path)},
            "recovered_jsonl": {
                "path": str(recovered_jsonl_path),
                "sha256": _sha256(recovered_jsonl_path),
            },
        },
        "artifacts": {
            path.name: {
                "path": str(path),
                "sha256": _sha256(path),
                "bytes": path.stat().st_size,
            }
            for path in artifacts
        },
    }
    _atomic_write(hash_ledger, json.dumps(hashes, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return {
        "manifest_jsonl": manifest_jsonl,
        "audit_csv": audit_csv,
        "source_groups_jsonl": source_groups_jsonl,
        "summary": summary,
        "report": report,
        "hash_ledger": hash_ledger,
    }


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ready-jsonl", type=Path, default=DEFAULT_READY_JSONL)
    parser.add_argument("--recovered-jsonl", type=Path, default=DEFAULT_RECOVERED_JSONL)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)
    result = build_train_manifest(
        ready_jsonl_path=args.ready_jsonl,
        recovered_jsonl_path=args.recovered_jsonl,
    )
    return write_outputs(
        result,
        args.output_dir,
        args.ready_jsonl,
        args.recovered_jsonl,
    )


if __name__ == "__main__":
    main()
