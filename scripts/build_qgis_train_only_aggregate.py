#!/usr/bin/env python3
"""Build a verified aggregate from mutually deduplicated QGIS train-only pools."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

ADMISSION = "granted_train_only_qgis_aggregate_507_v1"
SPLIT = "train_only_qgis_aggregate_507_v1"
SCHEMA = "qgis_train_only_aggregate_sample_v1"
ACCEPTED_SOURCE_VERIFICATIONS = {
    "verified_sha256",
    "source_reviewed_evidence",
    "carried_forward_verified_normalized_source_body",
}


def _json_key(value: Any) -> str:
    encoded = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _normalize_text(value: Any) -> str:
    return "".join(str(value or "").lower().split())


def _training_pair_key(row: dict[str, Any]) -> str:
    return _json_key(
        {
            "task_name": _normalize_text(row.get("task_name")),
            "task_description": _normalize_text(row.get("task_description")),
            "l3_sequence": list(row.get("l3_code_sequence") or []),
        }
    )


def build_aggregate(
    pools: list[tuple[str, list[dict[str, Any]]]],
    *,
    aggregate_schema: str = SCHEMA,
    aggregate_admission: str = ADMISSION,
    aggregate_split: str = SPLIT,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    aggregate: list[dict[str, Any]] = []
    ledger: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    seen_regions: set[str] = set()
    seen_graphs: set[str] = set()
    seen_pairs: set[str] = set()
    source_schema_counts: Counter[str] = Counter()
    source_admission_counts: Counter[str] = Counter()
    for pool_name, rows in pools:
        if not rows:
            raise ValueError(f"input pool is empty: {pool_name}")
        for row in rows:
            sample_id = str(row.get("sample_id") or "")
            region = str(row.get("source_region_key") or "")
            graph = str(row.get("call_graph_key") or "")
            source_admission = str(row.get("training_admission") or "")
            source_split = str(row.get("split") or "")
            source_schema = str(row.get("schema_version") or "")
            source_verification = str(row.get("source_verification") or "")
            if not sample_id or sample_id in seen_ids:
                raise ValueError(f"missing or duplicate sample ID: {sample_id}")
            if not region or region in seen_regions:
                raise ValueError(f"missing or duplicate source region: {sample_id}")
            if not graph or graph in seen_graphs:
                raise ValueError(f"missing or duplicate call graph: {sample_id}")
            if not source_admission.startswith("granted_train_only_"):
                raise ValueError(f"source row is not admitted train-only: {sample_id}")
            if not source_split.startswith("train_only_"):
                raise ValueError(f"source row is not on a train-only split: {sample_id}")
            if not source_schema:
                raise ValueError(f"source schema is missing: {sample_id}")
            if source_verification not in ACCEPTED_SOURCE_VERIFICATIONS:
                raise ValueError(f"source verification is not accepted: {sample_id}")
            if row.get("validation_eligible") or row.get("test_eligible"):
                raise ValueError(f"validation/test eligibility is open: {sample_id}")
            if row.get("production_merge") != "not_granted":
                raise ValueError(f"production merge is not closed: {sample_id}")
            operators = list(row.get("operator_sequence") or [])
            l3_codes = list(row.get("l3_code_sequence") or [])
            token_ids = [int(value) for value in row.get("l3_token_ids") or []]
            if not operators or len(operators) != len(l3_codes) or len(operators) != len(token_ids):
                raise ValueError(f"operator/L3 alignment failure: {sample_id}")
            if list(row.get("l3_sequence") or []) != [-3, *token_ids, -4]:
                raise ValueError(f"L3 token sequence mismatch: {sample_id}")
            pair = _training_pair_key(row)
            if pair in seen_pairs:
                raise ValueError(f"duplicate exact training pair: {sample_id}")
            seen_ids.add(sample_id)
            seen_regions.add(region)
            seen_graphs.add(graph)
            seen_pairs.add(pair)
            source_schema_counts[source_schema] += 1
            source_admission_counts[source_admission] += 1
            delivered = {
                **row,
                "schema_version": aggregate_schema,
                "aggregate_source_pool": pool_name,
                "source_schema_version": source_schema,
                "source_training_admission": source_admission,
                "source_split": source_split,
                "training_admission": aggregate_admission,
                "split": aggregate_split,
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
            }
            aggregate.append(delivered)
            ledger.append(
                {
                    "schema": "gis_recommend.qgis_train_only_aggregate_ledger.v1",
                    "sample_id": sample_id,
                    "aggregate_source_pool": pool_name,
                    "source_schema_version": source_schema,
                    "source_training_admission": source_admission,
                    "source_split": source_split,
                    "source_region_key": region,
                    "call_graph_key": graph,
                    "training_pair_key": pair,
                    "aggregate_decision": "canonical_keep",
                }
            )
    aggregate.sort(key=lambda row: (str(row["aggregate_source_pool"]), str(row["sample_id"])))
    ledger.sort(key=lambda row: (str(row["aggregate_source_pool"]), str(row["sample_id"])))
    summary = {
        "schema": "gis_recommend.qgis_train_only_aggregate_summary.v1",
        "aggregate_rows": len(aggregate),
        "source_pool_rows": {name: len(rows) for name, rows in pools},
        "source_pool_count": len(pools),
        "source_schema_counts": dict(sorted(source_schema_counts.items())),
        "source_admission_counts": dict(sorted(source_admission_counts.items())),
        "unique_sample_ids": len(seen_ids),
        "unique_source_regions": len(seen_regions),
        "unique_call_graphs": len(seen_graphs),
        "unique_training_pairs": len(seen_pairs),
        "unique_source_authorities": len(
            {str(row.get("source_authority_key") or "") for row in aggregate}
        ),
        "unique_l3_codes": len(
            {str(code) for row in aggregate for code in row.get("l3_code_sequence") or []}
        ),
        "max_l3_token_id": max(
            int(token) for row in aggregate for token in row.get("l3_token_ids") or []
        ),
        "training_admission": aggregate_admission,
        "split": aggregate_split,
        "training_rows_emitted": len(aggregate),
        "training_run": False,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }
    return aggregate, ledger, summary


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)


def _write_json(path: Path, value: Any) -> None:
    _atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    _atomic_write(
        path,
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-pool", type=Path, action="append", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-rows", type=int, required=True)
    parser.add_argument("--output-name", default="qgis_train_only_507_v1.jsonl")
    parser.add_argument("--aggregate-version", default="507")
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    pools = [(path.parent.name, _read_jsonl(path)) for path in args.input_pool]
    if len({name for name, _ in pools}) != len(pools):
        raise ValueError("input pool directory names must be unique")
    version = str(args.aggregate_version)
    if not version.isdigit() or int(version) < 1:
        raise ValueError("aggregate version must be a positive integer")
    aggregate, ledger, summary = build_aggregate(
        pools,
        aggregate_schema=f"qgis_train_only_aggregate_{version}_sample_v1",
        aggregate_admission=f"granted_train_only_qgis_aggregate_{version}_v1",
        aggregate_split=f"train_only_qgis_aggregate_{version}_v1",
    )
    if len(aggregate) != args.expected_rows:
        raise ValueError(
            f"aggregate rows {len(aggregate)} != expected {args.expected_rows}"
        )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    data_path = args.output_dir / args.output_name
    ledger_path = args.output_dir / "source_pool_ledger_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    _write_jsonl(data_path, aggregate)
    _write_jsonl(ledger_path, ledger)
    _write_json(summary_path, summary)
    _write_json(
        args.output_dir / "hash_ledger_v1.json",
        {
            "schema": "gis_recommend.hash_ledger.v1",
            "inputs": {
                str(index): {"path": str(path), "sha256": _sha256(path)}
                for index, path in enumerate(args.input_pool)
            },
            "artifacts": {
                path.name: {"bytes": path.stat().st_size, "sha256": _sha256(path)}
                for path in (data_path, ledger_path, summary_path)
            },
        },
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
