"""Retry only failed QGIS LLM boundary requests with frozen prompt hashes."""

from __future__ import annotations

import argparse
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from run_qgis_llm_boundary_pilot import call_model, load_jsonl, prompt, validate, MODEL, SCHEMA


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--calibration-review", type=Path, required=True)
    parser.add_argument("--holdout-review", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=5)
    args = parser.parse_args()
    old = load_jsonl(args.ledger)
    failed = {str(row["source_sha256"]): row for row in old if row.get("status") == "deferred_request_failure"}
    source_rows = load_jsonl(args.calibration_review) + load_jsonl(args.holdout_review)
    for row in source_rows:
        if row.get("source_sha256") in failed:
            row["review_split"] = "calibration" if row in load_jsonl(args.calibration_review) else "holdout"
    retry_rows = [row for row in source_rows if str(row.get("source_sha256")) in failed]
    if len(retry_rows) != len(failed):
        raise ValueError("failed source rows could not be reconstructed")
    for row in retry_rows:
        expected = failed[str(row["source_sha256"])].get("input_sha256")
        actual = __import__("hashlib").sha256(prompt(row).encode()).hexdigest()
        if expected != actual:
            raise ValueError(f"prompt hash changed for {row['source_sha256']}")
    api_key = os.environ.get("TOKENRHYTHM_API_KEY") or os.environ.get("DEEPSEEK_API_KEY")
    if not api_key:
        raise RuntimeError("set TOKENRHYTHM_API_KEY or DEEPSEEK_API_KEY")

    def process(row: dict) -> dict:
        base = {"schema": SCHEMA, "model": MODEL, "source_sha256": row["source_sha256"], "record_id": row.get("record_id"), "review_split": row.get("review_split"), "input_sha256": failed[row["source_sha256"]]["input_sha256"], "training_rows_emitted": 0, "training_admission": "not_granted_llm_boundary_pilot"}
        try:
            proposal = call_model(api_key, prompt(row))
            valid, errors = validate(proposal, row)
            return {**base, "status": "validated_candidate" if valid else "deferred_invalid_proposal", "proposal": valid, "validation_errors": errors, "retry": True}
        except Exception as exc:
            return {**base, "status": "deferred_request_failure", "reason": type(exc).__name__, "retry": True}

    with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
        rows = list(executor.map(process, retry_rows))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "retry_ledger_v1.jsonl").write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    summary = {"schema": f"{SCHEMA}.retry_summary", "retry_rows": len(rows), "prompt_hash_preserved": True, "status_counts": {status: sum(row["status"] == status for row in rows) for status in sorted({row["status"] for row in rows})}, "training_rows_emitted": 0, "training_admission": "not_granted_llm_boundary_pilot"}
    (args.output_dir / "summary_v1.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
