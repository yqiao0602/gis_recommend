#!/usr/bin/env python3
"""Select a deterministic, diverse QGIS train-only delivery batch."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any, Iterable


INPUT_ADMISSION = "granted_train_only_qgis_unified_pilot"
DELIVERY_ADMISSION = "granted_train_only_qgis_delivery_v1"
DELIVERY_SPLIT = "train_only_qgis_delivery_v1"
DELIVERY_SCHEMA = "qgis_train_delivery_sample_v1"


def _normalize_text(value: Any) -> str:
    return "".join(str(value or "").lower().split())


def _json_key(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _training_pair_key(row: dict[str, Any]) -> str:
    return _json_key(
        {
            "task_name": _normalize_text(row.get("task_name")),
            "task_description": _normalize_text(row.get("task_description")),
            "operator_sequence": list(row.get("operator_sequence") or []),
            "l3_code_sequence": list(row.get("l3_code_sequence") or []),
        }
    )


def _validate_input(rows: list[dict[str, Any]], batch_size: int) -> None:
    if batch_size < 1 or batch_size > len(rows):
        raise ValueError("batch size must be between one and the input row count")
    seen_ids: set[str] = set()
    seen_regions: set[str] = set()
    seen_graphs: set[str] = set()
    seen_pairs: set[str] = set()
    for row in rows:
        sample_id = str(row.get("sample_id") or "")
        if not sample_id or sample_id in seen_ids:
            raise ValueError(f"missing or duplicate sample id: {sample_id}")
        seen_ids.add(sample_id)
        if row.get("training_admission") != INPUT_ADMISSION:
            raise ValueError(f"input row is not unified train-only: {sample_id}")
        if not str(row.get("split") or "").startswith("train_only_"):
            raise ValueError(f"input row is not train-only: {sample_id}")
        if row.get("validation_eligible") or row.get("test_eligible"):
            raise ValueError(f"input row is validation/test eligible: {sample_id}")
        if row.get("production_merge") != "not_granted":
            raise ValueError(f"production merge is not closed: {sample_id}")
        operators = list(row.get("operator_sequence") or [])
        l3_codes = list(row.get("l3_code_sequence") or [])
        token_ids = list(row.get("l3_token_ids") or [])
        if not operators or len(operators) != len(l3_codes) or len(operators) != len(token_ids):
            raise ValueError(f"operator/L3 alignment failure: {sample_id}")
        if list(row.get("l3_sequence") or []) != [-3, *token_ids, -4]:
            raise ValueError(f"L3 token sequence mismatch: {sample_id}")
        region = str(row.get("source_region_key") or "")
        graph = str(row.get("call_graph_key") or "")
        if not region or region in seen_regions:
            raise ValueError(f"missing or duplicate source region: {sample_id}")
        if not graph or graph in seen_graphs:
            raise ValueError(f"missing or duplicate call graph: {sample_id}")
        seen_regions.add(region)
        seen_graphs.add(graph)
        pair = _training_pair_key(row)
        if pair in seen_pairs:
            raise ValueError(f"duplicate training pair: {sample_id}")
        seen_pairs.add(pair)


def select_delivery_batch(
    rows: list[dict[str, Any]], *, batch_size: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    _validate_input(rows, batch_size)
    remaining = sorted((dict(row) for row in rows), key=lambda row: str(row["sample_id"]))
    selected: list[dict[str, Any]] = []
    covered_pools: set[str] = set()
    covered_l3_sequences: set[tuple[str, ...]] = set()
    covered_l3_codes: set[str] = set()
    covered_operator_sequences: set[tuple[str, ...]] = set()

    while len(selected) < batch_size:
        def score(row: dict[str, Any]) -> tuple[int, int, int, int]:
            pool = str(row.get("manifest_source_pool") or "unknown")
            l3_sequence = tuple(str(code) for code in row["l3_code_sequence"])
            operators = tuple(str(operator) for operator in row["operator_sequence"])
            return (
                int(pool not in covered_pools),
                int(l3_sequence not in covered_l3_sequences),
                len(set(l3_sequence) - covered_l3_codes),
                int(operators not in covered_operator_sequences),
            )

        best_score = max(score(row) for row in remaining)
        chosen = next(row for row in remaining if score(row) == best_score)
        remaining.remove(chosen)
        selected.append(chosen)
        covered_pools.add(str(chosen.get("manifest_source_pool") or "unknown"))
        l3_sequence = tuple(str(code) for code in chosen["l3_code_sequence"])
        covered_l3_sequences.add(l3_sequence)
        covered_l3_codes.update(l3_sequence)
        covered_operator_sequences.add(tuple(str(op) for op in chosen["operator_sequence"]))

    ranks = {str(row["sample_id"]): index for index, row in enumerate(selected, start=1)}
    batch = []
    ledger = []
    for row in rows:
        sample_id = str(row["sample_id"])
        selected_rank = ranks.get(sample_id)
        ledger.append(
            {
                "schema": "gis_recommend.qgis_train_delivery_selection.v1",
                "sample_id": sample_id,
                "manifest_source_pool": row.get("manifest_source_pool"),
                "source_sha256": row["source_sha256"],
                "source_region_key": row["source_region_key"],
                "call_graph_key": row["call_graph_key"],
                "training_pair_key": _training_pair_key(row),
                "selected": selected_rank is not None,
                "selection_rank": selected_rank,
                "training_row_emitted": selected_rank is not None,
            }
        )
        if selected_rank is None:
            continue
        delivered = dict(row)
        delivered.update(
            {
                "delivery_schema": "gis_recommend.qgis_train_delivery.v1",
                "schema_version": DELIVERY_SCHEMA,
                "delivery_batch_id": "qgis_train_delivery_50_v1",
                "delivery_selection_rank": selected_rank,
                "source_training_admission": row["training_admission"],
                "source_split": row["split"],
                "training_admission": DELIVERY_ADMISSION,
                "split": DELIVERY_SPLIT,
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
            }
        )
        if not delivered.get("source_authority_key"):
            delivered["source_authority_key"] = (
                "source_sha256:" + str(delivered["source_sha256"])
            )
            delivered["source_authority_basis"] = "delivery_source_sha256"
        delivered["source_verification"] = (
            delivered.get("source_verification") or "source_reviewed_evidence"
        )
        batch.append(delivered)
    batch.sort(key=lambda row: int(row["delivery_selection_rank"]))
    summary = {
        "schema": "gis_recommend.qgis_train_delivery.summary.v1",
        "input_authority_rows": len(rows),
        "delivery_rows": len(batch),
        "source_pool_count": len({str(row.get("manifest_source_pool")) for row in batch}),
        "unique_source_sha256": len({str(row["source_sha256"]) for row in batch}),
        "unique_source_regions": len({str(row["source_region_key"]) for row in batch}),
        "unique_call_graphs": len({str(row["call_graph_key"]) for row in batch}),
        "unique_operator_sequences": len({tuple(row["operator_sequence"]) for row in batch}),
        "unique_l3_sequences": len({tuple(row["l3_code_sequence"]) for row in batch}),
        "unique_l3_codes": len({code for row in batch for code in row["l3_code_sequence"]}),
        "training_admission": DELIVERY_ADMISSION,
        "split": DELIVERY_SPLIT,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "training_rows_emitted": len(batch),
        "training_run": False,
    }
    return batch, ledger, summary


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


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    _atomic_write(
        path,
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authority", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--expected-authority-rows", type=int)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    rows = _read_jsonl(args.authority)
    if args.expected_authority_rows is not None and len(rows) != args.expected_authority_rows:
        raise ValueError(
            f"authority rows {len(rows)} != expected {args.expected_authority_rows}"
        )
    batch, ledger, summary = select_delivery_batch(rows, batch_size=args.batch_size)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    batch_path = args.output_dir / "qgis_train_delivery_50_v1.jsonl"
    ledger_path = args.output_dir / "selection_ledger_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    _write_jsonl(batch_path, batch)
    _write_jsonl(ledger_path, ledger)
    _atomic_write(summary_path, json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    ledger_data = {
        "schema": "gis_recommend.hash_ledger.v1",
        "inputs": {"authority": {"path": str(args.authority), "sha256": _sha256(args.authority)}},
        "artifacts": {
            path.name: {"sha256": _sha256(path), "bytes": path.stat().st_size}
            for path in (batch_path, ledger_path, summary_path)
        },
    }
    _atomic_write(
        args.output_dir / "hash_ledger_v1.json",
        json.dumps(ledger_data, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
