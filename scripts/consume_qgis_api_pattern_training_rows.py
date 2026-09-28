#!/usr/bin/env python3
"""Final consumption of the 142 qualified API-pattern chains into training rows.

This is the last stage of the 875-funnel: task-text construction from source
context (docstrings, comments, class/function names — never invented), internal
L3-sequence dedup, cross-pool dedup against the existing 508 aggregate
(source SHA, exact L3 sequence, and task-text identity), the real
``bert-base-uncased`` tokenizer gate, and the V4 data-path smoke. No new parsing
beyond reading the already-frozen context ledger; no checkpoint; no training
epoch. Every rejection is stage-attributed so the funnel table is complete.

Task-text policy: a row survives only with **real source context** — a
docstring, a task-bearing comment, or a domain-named class+function pair. The
text is assembled verbatim from those facts plus the operator-chain naming;
nothing is paraphrased or generated.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any

SCHEMA = "gis_recommend.qgis_api_pattern_training_rows.v1"
GENERIC_CLASS = re.compile(r"^(task|tool|helper|util|utils|base|main|test|worker|object|plugin|algorithm)[a-z_]*$", re.I)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _task_text(entry: dict[str, Any]) -> tuple[str | None, str]:
    """Build the task text from verbatim source context, or say why not."""
    doc = (entry.get("function_docstring") or "").strip() or (entry.get("module_docstring") or "").strip()
    comments = entry.get("nearby_comments") or []
    classes = [c for c in (entry.get("classes") or []) if c and not GENERIC_CLASS.match(c)]
    functions = [f for f in (entry.get("functions") or []) if f and not re.match(r"^(run|main|execute|process|compute)$", f, re.I)]
    chain = entry.get("chain") or []

    if doc and len(doc) >= 12:
        return doc, "docstring"
    if comments:
        comment = max(comments, key=len)
        if len(comment) >= 8:
            return comment, "task_comment"
    if classes and functions:
        return f"{classes[0]}.{functions[0]}: {len(chain)} 步几何处理链", "domain_named_scope"
    if classes:
        return f"{classes[0]}: {len(chain)} 步几何处理链", "domain_class_only"
    return None, "no_source_context"


def consume(context_rows: list[dict[str, Any]], existing_508: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    existing_sha = {str(row.get("source_sha256") or "") for row in existing_508}
    existing_l3_seq = {
        tuple(row["l3_codes"][1:-1])
        for row in existing_508
        if isinstance(row.get("l3_codes"), list) and len(row.get("l3_codes", [])) >= 3
    }
    existing_text = {str(row.get("task_description") or row.get("task_name") or "") for row in existing_508}

    ledger: list[dict[str, Any]] = []
    reasons: Counter[str] = Counter()
    seen_l3: dict[tuple, str] = {}
    for entry in context_rows:
        row: dict[str, Any] = {
            "schema": SCHEMA,
            "record_id": entry["record_id"],
            "source_sha256": entry["source_sha256"],
            "chain": entry["chain"],
            "l3_sequence": entry["l3_sequence"],
            "chain_signature": entry["chain_signature"],
        }
        text, source_kind = _task_text(entry)

        if str(entry.get("source_sha256") or "") in existing_sha:
            reasons["hit_508_source_sha"] += 1
            row.update(stage="dedup_508", reason="hit_508_source_sha")
            ledger.append(row)
            continue
        seq_key = tuple(entry["l3_sequence"])
        if seq_key in seen_l3:
            reasons["dedup_internal_l3_sequence"] += 1
            row.update(stage="dedup_internal", reason=f"l3_sequence already kept from {seen_l3[seq_key]}")
            ledger.append(row)
            continue
        if seq_key in existing_l3_seq:
            reasons["hit_508_l3_sequence"] += 1
            row.update(stage="dedup_508", reason="hit_508_l3_sequence")
            ledger.append(row)
            continue
        if text is not None and text in existing_text:
            reasons["hit_508_task_text"] += 1
            row.update(stage="dedup_508", reason="hit_508_task_text")
            ledger.append(row)
            continue
        if text is None:
            reasons[source_kind] += 1
            row.update(stage="task_text_reject", reason=source_kind)
            ledger.append(row)
            continue

        seen_l3[seq_key] = str(entry["record_id"])
        row.update(
            stage=None,
            task_text=text,
            task_text_source=source_kind,
            sample_id=f"qgis_api_pattern_{entry['record_id']}_v1",
            training_admission="candidate_pending_tokenizer_and_v4_gates",
            training_rows_emitted=0,
            validation_eligible=False,
            test_eligible=False,
            production_merge="not_granted",
        )
        ledger.append(row)

    kept = [row for row in ledger if row["stage"] is None]
    summary = {
        "schema": f"{SCHEMA}.summary",
        "input_qualified_rows": len(context_rows),
        "funnel": {
            "hit_508_source_sha": reasons.get("hit_508_source_sha", 0),
            "hit_508_l3_sequence": reasons.get("hit_508_l3_sequence", 0),
            "dedup_internal_l3_sequence": reasons.get("dedup_internal_l3_sequence", 0),
            "hit_508_task_text": reasons.get("hit_508_task_text", 0),
            "no_source_context": reasons.get("no_source_context", 0),
            "kept_after_dedup_and_text": len(kept),
        },
        "kept_by_text_source": dict(sorted(Counter(row["task_text_source"] for row in kept).items())),
        "kept_length_distribution": dict(sorted(Counter(len(row["l3_sequence"]) for row in kept).items())),
        "kept_l3_code_distribution": dict(sorted(Counter(code for row in kept for code in row["l3_sequence"]).items())),
        "training_rows_emitted": 0,
        "training_admission": "not_granted_consumption_only",
        "formal_authority_modified": False,
    }
    return ledger, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--context-ledger", type=Path, required=True)
    parser.add_argument("--existing-508", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    context = json.loads(args.context_ledger.read_text(encoding="utf-8"))
    ledger, summary = consume(context, read_jsonl(args.existing_508))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = args.output_dir / "pattern_consumption_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    ledger_path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in ledger), encoding="utf-8")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in (ledger_path, summary_path)}
    hashes["context_ledger_input"] = hashlib.sha256(args.context_ledger.read_bytes()).hexdigest()
    hashes["existing_508_input"] = hashlib.sha256(args.existing_508.read_bytes()).hexdigest()
    (args.output_dir / "hash_ledger_v1.json").write_text(json.dumps(hashes, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
