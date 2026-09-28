#!/usr/bin/env python3
"""Build a QGIS train-only package whose real BERT prompts fit V4-128."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gis_recommend.training.train_v4_2 import build_task_prompt

SCHEMA = "qgis_train_only_aggregate_v4_128_sample_v1"
SPLIT = "train_only_qgis_aggregate_v4_128_v1"
ADMISSION = "granted_train_only_qgis_aggregate_v4_128_v1"


def _token_ids(tokenizer: Any, prompt: str) -> list[int]:
    encoded = tokenizer(prompt, add_special_tokens=True, truncation=False)
    token_ids = encoded.get("input_ids")
    if not isinstance(token_ids, list) or any(
        not isinstance(token, int) for token in token_ids
    ):
        raise ValueError("tokenizer did not return a flat input_ids list")
    return token_ids


def build_no_truncation_package(
    rows: list[dict[str, Any]], tokenizer: Any, *, max_text_length: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    if max_text_length < 1:
        raise ValueError("max_text_length must be positive")
    sample_ids = [str(row.get("sample_id") or "") for row in rows]
    if not rows or any(not value for value in sample_ids):
        raise ValueError("input contains a missing sample_id")
    if len(sample_ids) != len(set(sample_ids)):
        raise ValueError("input contains duplicate sample_id values")

    eligible: list[dict[str, Any]] = []
    ledger: list[dict[str, Any]] = []
    for row in rows:
        metadata = row.get("task_metadata") or {}
        task_type = str(metadata.get("task_type") or "")
        task_name = str(metadata.get("task_name") or "")
        task_description = str(metadata.get("task_description") or "")
        if task_name != str(row.get("task_name") or "") or task_description != str(
            row.get("task_description") or ""
        ):
            raise ValueError(f"task metadata mismatch for {row['sample_id']}")
        prompt = build_task_prompt(task_type, task_name, task_description)
        token_count = len(_token_ids(tokenizer, prompt))
        no_truncation = token_count <= max_text_length
        decision = "eligible_no_text_truncation" if no_truncation else "deferred_text_truncation"
        ledger.append(
            {
                "schema": "gis_recommend.qgis_v4_text_length_audit.v1",
                "sample_id": row["sample_id"],
                "aggregate_source_pool": row.get("aggregate_source_pool"),
                "source_authority_key": row.get("source_authority_key"),
                "chain_length": int(row.get("n") or 0),
                "text_token_count_with_special_tokens": token_count,
                "max_text_length": max_text_length,
                "text_truncation_required": not no_truncation,
                "decision": decision,
                "training_rows_emitted": int(no_truncation),
                "production_merge": "not_granted",
            }
        )
        if no_truncation:
            output = dict(row)
            output.setdefault("prior_schema_version", output.get("schema_version"))
            output.setdefault("prior_split", output.get("split"))
            output.setdefault(
                "prior_training_admission", output.get("training_admission")
            )
            output["schema_version"] = SCHEMA
            output["split"] = SPLIT
            output["training_admission"] = ADMISSION
            output["text_length_verification"] = (
                "verified_bert_base_uncased_no_truncation_at_128"
            )
            output["text_token_count_with_special_tokens"] = token_count
            eligible.append(output)

    decisions = Counter(item["decision"] for item in ledger)
    deferred_pools = Counter(
        str(item["aggregate_source_pool"])
        for item in ledger
        if item["decision"] == "deferred_text_truncation"
    )
    summary = {
        "schema": "gis_recommend.qgis_v4_text_length_audit.summary.v1",
        "input_rows": len(rows),
        "eligible_rows": len(eligible),
        "deferred_rows": len(rows) - len(eligible),
        "decision_counts": dict(sorted(decisions.items())),
        "deferred_source_pool_counts": dict(sorted(deferred_pools.items())),
        "max_text_length": max_text_length,
        "max_observed_text_tokens": max(
            int(item["text_token_count_with_special_tokens"]) for item in ledger
        ),
        "eligible_max_text_tokens": max(
            (
                int(item["text_token_count_with_special_tokens"])
                for item in ledger
                if item["decision"] == "eligible_no_text_truncation"
            ),
            default=0,
        ),
        "output_schema": SCHEMA,
        "output_split": SPLIT,
        "output_training_admission": ADMISSION,
        "text_truncation_gate": "passed_for_eligible_rows",
        "semantic_audit_status": "pending",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }
    return eligible, ledger, summary


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


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


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    _atomic_write(
        path,
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, action="append", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--output-name", default="qgis_train_only_v4_128_454_v1.jsonl"
    )
    parser.add_argument("--expected-rows", type=int, default=507)
    parser.add_argument("--max-text-length", type=int, default=128)
    parser.add_argument("--bert-model", default="bert-base-uncased")
    parser.add_argument("--allow-bert-download", action="store_true")
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    rows = [row for path in args.input for row in _read_jsonl(path)]
    if len(rows) != args.expected_rows:
        raise ValueError("input row count mismatch")

    from transformers import BertTokenizer

    tokenizer = BertTokenizer.from_pretrained(
        args.bert_model, local_files_only=not args.allow_bert_download
    )
    eligible, ledger, summary = build_no_truncation_package(
        rows, tokenizer, max_text_length=args.max_text_length
    )
    summary["bert_model"] = args.bert_model
    summary["bert_local_files_only"] = not args.allow_bert_download
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output_path = args.output_dir / args.output_name
    ledger_path = args.output_dir / "text_length_audit_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    _write_jsonl(output_path, eligible)
    _write_jsonl(ledger_path, ledger)
    _write_json(summary_path, summary)
    _write_json(
        args.output_dir / "hash_ledger_v1.json",
        {
            "schema": "gis_recommend.hash_ledger.v1",
            "inputs": {
                f"{index}:{path.name}": {"path": str(path), "sha256": _sha256(path)}
                for index, path in enumerate(args.input)
            },
            "artifacts": {
                path.name: {"bytes": path.stat().st_size, "sha256": _sha256(path)}
                for path in (output_path, ledger_path, summary_path)
            },
        },
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
