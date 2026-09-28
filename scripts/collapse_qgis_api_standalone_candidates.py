#!/usr/bin/env python3
"""Collapse the 137 adjudicated standalone API rows into training candidates.

This is the yield-consumption pipeline: no new source parsing, no pool widening.
Each stage records why a row left, so the final report distinguishes
dedup-existing, dedup-internal, no-independent-task-context, tokenizer, and
stable124/V4 rejections. Dedup is deliberately conservative-by-evidence: rows are
duplicate only on identical source SHA, identical semantic payload (L3 + method +
argument-literal shape), or an exact training-pair hit in the existing 508 pool.
Task-context survival requires an observable user-task semantic beyond the bare
API call: a literal distance/band operand, a named task-bearing scope, or a
caller-visible result with a domain-named binding.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

SCHEMA = "gis_recommend.qgis_api_standalone_training_candidates.v1"
BARE_VERB_SCOPE = re.compile(r"^(run|main|process|handle|execute|transform_geometry|apply|convert|do)_?$", re.I)
DOMAIN_TOKEN = re.compile(r"(road|river|build|water|lake|forest|land|parcel|zone|track|line|point|polygon|dem|elev|crs|wgs|epsg|utm|grid|region|area|site|buffer|clip|zone|address|plot|field)", re.I)


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _payload_key(fact: dict[str, Any], entry: dict[str, Any]) -> tuple:
    args = fact.get("argument_facts") or {}
    literals = tuple(
        (item.get("literal_value") if item.get("kind") == "literal" else "<expr>")
        for item in (args.get("positional") or [])
    )
    return (entry["l3_proposal"], fact.get("method"), fact.get("semantic_role"), literals)


def _task_context_score(fact: dict[str, Any], entry: dict[str, Any]) -> tuple[bool, str]:
    """Decide whether a real user-task semantic is observable, and say why not."""
    scope = fact.get("enclosing_scope") or {}
    function = str(scope.get("function") or "")
    args = fact.get("argument_facts") or {}
    literals = [item for item in (args.get("positional") or []) if item.get("kind") == "literal"]
    keywords = [k for k, v in (args.get("keyword") or {}).items() if v.get("kind") == "literal"]

    if scope.get("kind") == "module":
        return False, "module_level_snippet_no_task_owner"
    if BARE_VERB_SCOPE.match(function):
        return False, "generic_verb_scope_no_task_semantics"
    if literals or keywords:
        return True, "literal_operand_visible"
    if DOMAIN_TOKEN.search(function):
        return True, "domain_named_scope"
    target = str((fact.get("return_target") or {}).get("target") or "")
    if DOMAIN_TOKEN.search(target):
        return True, "domain_named_binding"
    return False, "no_observable_task_semantics"


def collapse(
    adjudicated: list[dict[str, Any]],
    facts: dict[str, dict[str, Any]],
    existing: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    standalone = [
        entry for entry in adjudicated
        if entry.get("decision") == "QUALIFIED" and entry.get("standalone") == "standalone_operation_result"
    ]
    existing_sha = {str(row.get("source_sha256") or "") for row in existing}
    existing_pairs = {
        (row["l3_codes"][1], str(row.get("task_description") or row.get("task_name") or ""))
        for row in existing
        if isinstance(row.get("l3_codes"), list) and len(row["l3_codes"]) == 3
    }

    pipeline: list[dict[str, Any]] = []
    reasons: Counter[str] = Counter()
    seen_payload: dict[tuple, str] = {}

    for entry in standalone:
        fact = facts.get(str(entry.get("record_id") or ""), {})
        row = {
            "schema": SCHEMA,
            "record_id": entry.get("record_id"),
            "source_sha256": entry.get("source_sha256"),
            "l3_proposal": entry["l3_proposal"],
            "l3_name": entry.get("l3_name"),
            "l3_token_id": entry.get("l3_token_id"),
            "method": fact.get("method"),
            "call_text": fact.get("call_text"),
            "call_span": fact.get("call_span"),
            "receiver": (fact.get("receiver") or {}).get("qgis_type"),
            "argument_facts": fact.get("argument_facts"),
            "enclosing_scope": fact.get("enclosing_scope"),
            "standalone_reason": entry.get("standalone_reason"),
        }

        if str(entry.get("source_sha256") or "") in existing_sha:
            reasons["dedup_existing_source_sha"] += 1
            row["rejection_stage"] = "dedup_existing"
            row["rejection_reason"] = "source_sha_already_in_508_pool"
            pipeline.append(row)
            continue

        payload = _payload_key(fact, entry)
        if payload in seen_payload:
            reasons["dedup_internal_payload"] += 1
            row["rejection_stage"] = "dedup_internal"
            row["rejection_reason"] = f"identical payload already kept from {seen_payload[payload]}"
            pipeline.append(row)
            continue

        survives, why = _task_context_score(fact, entry)
        if not survives:
            reasons[why] += 1
            row["rejection_stage"] = "task_context"
            row["rejection_reason"] = why
            pipeline.append(row)
            continue

        row["task_context_reason"] = why
        row["rejection_stage"] = None
        row["rejection_reason"] = None
        row["training_admission"] = "candidate_pending_tokenizer_and_v4_gates"
        seen_payload[payload] = str(entry.get("record_id") or "")
        pipeline.append(row)

    kept = [row for row in pipeline if row["rejection_stage"] is None]
    by_l3 = Counter(str(row["l3_proposal"]) for row in kept)
    summary = {
        "schema": f"{SCHEMA}.summary",
        "input_standalone_rows": len(standalone),
        "stage_rejections": dict(sorted(reasons.items())),
        "dedup_existing": reasons.get("dedup_existing_source_sha", 0),
        "dedup_internal": reasons.get("dedup_internal_payload", 0),
        "no_independent_task_context": sum(count for key, count in reasons.items() if key.startswith(("module_level", "generic_verb", "no_observable"))),
        "kept_after_context": len(kept),
        "kept_by_l3": dict(sorted(by_l3.items())),
        "kept_by_context_reason": dict(sorted(Counter(row["task_context_reason"] for row in kept).items())),
        "training_rows_emitted": 0,
        "training_admission": "not_granted_collapse_only",
        "formal_authority_modified": False,
    }
    return pipeline, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adjudicated-ledger", type=Path, required=True)
    parser.add_argument("--phase1-ledger", type=Path, required=True)
    parser.add_argument("--existing-508", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    facts = {
        str(row.get("record_id") or ""): row
        for row in read_jsonl(args.phase1_ledger)
    }
    pipeline, summary = collapse(read_jsonl(args.adjudicated_ledger), facts, read_jsonl(args.existing_508))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    pipeline_path = args.output_dir / "standalone_collapse_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    pipeline_path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in pipeline), encoding="utf-8")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in (pipeline_path, summary_path)}
    for name, path in (("adjudicated_input", args.adjudicated_ledger), ("phase1_input", args.phase1_ledger), ("existing_508_input", args.existing_508)):
        hashes[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    (args.output_dir / "hash_ledger_v1.json").write_text(json.dumps(hashes, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
