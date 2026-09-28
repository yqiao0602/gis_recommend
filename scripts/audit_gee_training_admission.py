#!/usr/bin/env python3
"""Audit whether existing GEE rows are safe as unified L3 workflow training data.

This is a read-only admission audit. It does not regenerate GEE Step artifacts,
does not call an LLM, and does not grant training admission.
"""

from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import json
import os
from pathlib import Path
import re
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gis_recommend.data.quality_gate import (  # noqa: E402
    audit_description_alignment,
    extract_source_identities,
)


DEFAULT_CANDIDATE = (
    ROOT
    / "outputs_v2/pipeline/step8_quality_gate/labeled_workflows_l3_v4_quality_gate.json"
)
DEFAULT_QUARANTINE = (
    ROOT
    / "outputs_v2/pipeline/step8_quality_gate/quarantined_workflows_l3_v4_quality_gate.json"
)
DEFAULT_HIERARCHY = ROOT / "outputs_v2/classification_hierarchy_v2.csv"
DEFAULT_REPORT_JSON = ROOT / "docs/reports/gee_training_admission_audit_2026-07-24.json"
DEFAULT_REPORT_MD = ROOT / "docs/reports/gee_training_admission_audit_2026-07-24.md"

UNKNOWN_TEXT_VALUES = {"", "unknown", "none", "null", "n/a", "na"}
TIER_ORDER = ("gold", "silver_a", "silver_b", "rejected")
TIER_WEIGHTS = {
    "gold": 1.0,
    "silver_a": 0.5,
    "silver_b": 0.15,
    "rejected": 0.0,
}


def _load_workflows(path: Path) -> list[dict[str, Any]]:
    with Path(path).open(encoding="utf-8") as handle:
        payload = json.load(handle)
    workflows = payload.get("labeled_workflows", payload if isinstance(payload, list) else [])
    if not isinstance(workflows, list):
        raise ValueError(f"{path} does not contain a workflow list")
    if not all(isinstance(row, dict) for row in workflows):
        raise ValueError(f"{path} contains non-object workflow rows")
    return workflows


def _load_hierarchy(path: Path) -> dict[str, dict[str, str]]:
    rows: dict[str, dict[str, str]] = {}
    with Path(path).open(encoding="utf-8", newline="") as handle:
        reader = csv.DictReader(handle)
        required = {"l3_code", "l1_code", "l1_name"}
        if not reader.fieldnames or not required.issubset(reader.fieldnames):
            raise ValueError(f"{path} must contain columns {sorted(required)}")
        for row in reader:
            code = (row.get("l3_code") or "").strip()
            if code:
                rows[code] = {key: str(value or "") for key, value in row.items()}
    if not rows:
        raise ValueError(f"{path} contains no L3 rows")
    return rows


def _content_l3_codes(workflow: dict[str, Any]) -> list[str]:
    return [
        code
        for code in workflow.get("l3_codes", [])
        if isinstance(code, str) and not code.startswith("<")
    ]


def _sequence_hash(values: Any) -> str:
    payload = json.dumps(values, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _task_text_fields(workflow: dict[str, Any]) -> tuple[str, str]:
    task_metadata = workflow.get("task_metadata", {}) or {}
    return (
        str(task_metadata.get("task_name", "") or "").strip(),
        str(task_metadata.get("task_description", "") or "").strip(),
    )


def _has_usable_text(workflow: dict[str, Any]) -> bool:
    return any(field.strip().lower() not in UNKNOWN_TEXT_VALUES for field in _task_text_fields(workflow))


def _schema_lengths(workflow: dict[str, Any]) -> dict[str, int]:
    content_ids = [
        token for token in workflow.get("l3_sequence", [])
        if isinstance(token, int) and token >= 0
    ]
    return {
        "operators": len(workflow.get("operator_sequence", []) or []),
        "confidences": len(workflow.get("confidences", []) or []),
        "ambiguity_flags": len(workflow.get("ambiguity_flags", []) or []),
        "l3_codes": len(_content_l3_codes(workflow)),
        "l3_ids": len(content_ids),
    }


def _schema_ok(workflow: dict[str, Any]) -> bool:
    lengths = _schema_lengths(workflow)
    return len(set(lengths.values())) == 1 and lengths["operators"] > 0


def _authoritative_source_identities(workflow: dict[str, Any]) -> list[str]:
    metadata = workflow.get("metadata", {}) or {}
    authority = metadata.get("source_identity_authority")
    identities = extract_source_identities(workflow)
    if authority == "source_content_sha256":
        return [
            identity for identity in identities
            if identity.startswith("content_hash:")
            and re.fullmatch(r"[0-9a-fA-F]{64}", identity.split(":", 1)[1])
        ]
    if authority in {"repository_manifest", "reviewed_manifest"}:
        return identities
    return []


def _workflow_scope(alignment: dict[str, Any]) -> str:
    return "io_or_presentation_declared_in_text" if alignment.get("claims") else "core_analysis"


def _classify_candidate(
    workflow: dict[str, Any],
    hierarchy: dict[str, dict[str, str]],
    *,
    min_chain_len: int,
    max_chain_len: int,
) -> tuple[str, list[str], dict[str, Any]]:
    reasons: list[str] = []
    codes = _content_l3_codes(workflow)
    unknown_codes = sorted({code for code in codes if code not in hierarchy})
    alignment = audit_description_alignment(workflow)
    flags = set(workflow.get("quality_gate", {}).get("flags", []) or [])

    if not _has_usable_text(workflow):
        reasons.append("missing_or_unknown_task_text")
    if not _schema_ok(workflow):
        reasons.append("schema_length_mismatch_or_empty_chain")
    if unknown_codes:
        reasons.append("unknown_l3_code")
    if len(codes) < min_chain_len or len(codes) > max_chain_len:
        reasons.append("chain_length_out_of_bounds")

    if reasons:
        return "rejected", reasons, alignment
    if alignment.get("has_issue"):
        return "silver_b", ["description_chain_alignment_issue"], alignment
    if "low_confidence_kept" in flags:
        return "silver_b", ["low_confidence_kept"], alignment
    if _authoritative_source_identities(workflow):
        return "gold", ["authoritative_source_identity"], alignment
    return "silver_a", ["missing_authoritative_source_identity"], alignment


def _top(counter: Counter[str], limit: int = 20) -> list[dict[str, Any]]:
    return [
        {"item": item, "count": count}
        for item, count in counter.most_common(limit)
    ]


def build_training_admission_audit(
    *,
    candidate_path: Path,
    quarantine_path: Path,
    hierarchy_path: Path,
    min_chain_len: int = 1,
    max_chain_len: int = 20,
) -> dict[str, Any]:
    candidates = _load_workflows(candidate_path)
    quarantined = _load_workflows(quarantine_path)
    hierarchy = _load_hierarchy(hierarchy_path)

    tier_counts: Counter[str] = Counter()
    tier_reason_counts: dict[str, Counter[str]] = {
        tier: Counter() for tier in TIER_ORDER
    }
    text_counts: Counter[str] = Counter()
    alignment_claims: Counter[str] = Counter()
    alignment_statuses: Counter[str] = Counter()
    alignment_issue_workflows = 0
    scope_counts: Counter[str] = Counter()
    candidate_declared_identity = 0
    candidate_authoritative_identity = 0
    identity_field_counts: Counter[str] = Counter()
    l3_counter: Counter[str] = Counter()
    l1_counter: Counter[str] = Counter()
    task_counter: Counter[str] = Counter()
    sequence_counter: Counter[str] = Counter()
    text_sequence_counter: Counter[str] = Counter()
    examples: dict[str, list[str]] = {tier: [] for tier in TIER_ORDER}

    for workflow in candidates:
        if _has_usable_text(workflow):
            text_counts["candidate_usable_text"] += 1
        else:
            text_counts["candidate_unknown_or_empty_text"] += 1

        declared_identities = extract_source_identities(workflow)
        authoritative_identities = _authoritative_source_identities(workflow)
        candidate_declared_identity += int(bool(declared_identities))
        candidate_authoritative_identity += int(bool(authoritative_identities))
        for identity in declared_identities:
            identity_field_counts[identity.split(":", 1)[0]] += 1

        tier, reasons, alignment = _classify_candidate(
            workflow,
            hierarchy,
            min_chain_len=min_chain_len,
            max_chain_len=max_chain_len,
        )
        tier_counts[tier] += 1
        tier_reason_counts[tier].update(reasons)
        if len(examples[tier]) < 10:
            script_id = (workflow.get("metadata", {}) or {}).get("script_id", "")
            examples[tier].append(str(script_id))

        if alignment.get("has_issue"):
            alignment_issue_workflows += 1
        for claim in alignment.get("claims", []):
            alignment_claims[str(claim.get("claim", "unknown"))] += 1
            alignment_statuses[str(claim.get("status", "unknown"))] += 1
        scope_counts[_workflow_scope(alignment)] += 1

        task_type = str((workflow.get("task_metadata", {}) or {}).get("task_type", "Unknown") or "Unknown")
        task_counter[task_type] += 1
        codes = _content_l3_codes(workflow)
        sequence_counter[_sequence_hash(codes)] += 1
        task_name, task_description = _task_text_fields(workflow)
        text_sequence_counter[_sequence_hash([task_name, task_description, codes])] += 1
        for code in codes:
            l3_counter[code] += 1
            row = hierarchy.get(code)
            if row:
                l1_counter[row.get("l1_code", "unknown")] += 1

    if quarantined:
        tier_counts["rejected"] += len(quarantined)
        tier_reason_counts["rejected"].update({"quality_gate_quarantine": len(quarantined)})
        for workflow in quarantined[:10]:
            script_id = (workflow.get("metadata", {}) or {}).get("script_id", "")
            examples["rejected"].append(str(script_id))

    duplicate_sequence_items = sum(count for count in sequence_counter.values() if count > 1)
    duplicate_text_sequence_items = sum(
        count for count in text_sequence_counter.values() if count > 1
    )
    total_rows = len(candidates) + len(quarantined)
    report = {
        "schema": "gis_recommend.gee_training_admission_audit.v1",
        "inputs": {
            "candidate": str(Path(candidate_path)),
            "quarantine": str(Path(quarantine_path)),
            "hierarchy": str(Path(hierarchy_path)),
            "min_chain_len": min_chain_len,
            "max_chain_len": max_chain_len,
        },
        "counts": {
            "candidate_workflows": len(candidates),
            "quarantined_workflows": len(quarantined),
            "total_rows_seen": total_rows,
        },
        "training_tiers": {
            "counts": {tier: tier_counts[tier] for tier in TIER_ORDER},
            "sample_weights": TIER_WEIGHTS,
            "reason_counts": {
                tier: dict(sorted(tier_reason_counts[tier].items()))
                for tier in TIER_ORDER
            },
            "example_script_ids": examples,
        },
        "text": {
            "candidate_usable_text": text_counts["candidate_usable_text"],
            "candidate_unknown_or_empty_text": text_counts["candidate_unknown_or_empty_text"],
        },
        "description_alignment": {
            "authority": "lexical_proxy",
            "candidate_workflows_with_issues": alignment_issue_workflows,
            "claims": dict(sorted(alignment_claims.items())),
            "statuses": dict(sorted(alignment_statuses.items())),
        },
        "source_identity": {
            "candidate_declared_workflows": candidate_declared_identity,
            "candidate_authoritative_workflows": candidate_authoritative_identity,
            "candidate_missing_authoritative_workflows": len(candidates) - candidate_authoritative_identity,
            "identity_field_occurrences": dict(sorted(identity_field_counts.items())),
            "source_disjoint_verified": (
                candidate_authoritative_identity == len(candidates)
                and len(candidates) > 0
            ),
        },
        "workflow_scope": {
            "candidate_scope_counts": dict(sorted(scope_counts.items())),
            "scope_authority": "description_lexical_proxy",
        },
        "modality": {
            "candidate_l1_counts": dict(sorted(l1_counter.items())),
            "top_l3": _top(l3_counter),
            "active_l3": len(l3_counter),
            "top10_l3_share": (
                sum(count for _, count in l3_counter.most_common(10)) / sum(l3_counter.values())
                if l3_counter else 0.0
            ),
            "top_task_types": _top(task_counter),
        },
        "duplicates": {
            "candidate_unique_l3_sequences": len(sequence_counter),
            "candidate_duplicate_l3_sequence_items": duplicate_sequence_items,
            "candidate_unique_text_chain_pairs": len(text_sequence_counter),
            "candidate_duplicate_text_chain_pair_items": duplicate_text_sequence_items,
        },
        "decision": {
            "training_admission": "not_granted",
            "large_dataset_overwrite_authorized": False,
            "llm_calls_used": False,
            "recommended_next_gate": (
                "review this audit, then build a bounded GEE_raster_core_v1 "
                "from gold/silver_a rows only"
            ),
        },
    }
    return report


def _render_markdown(report: dict[str, Any]) -> str:
    tiers = report["training_tiers"]["counts"]
    text = report["text"]
    alignment = report["description_alignment"]
    source = report["source_identity"]
    modality = report["modality"]
    duplicates = report["duplicates"]
    lines = [
        "# GEE Training Admission Audit",
        "",
        "This is a read-only audit for using existing GEE rows as unified L3 workflow training data.",
        "It does not grant training admission and does not regenerate data.",
        "",
        "## Summary",
        "",
        f"- Candidate workflows: {report['counts']['candidate_workflows']:,}",
        f"- Quarantined workflows: {report['counts']['quarantined_workflows']:,}",
        f"- Gold rows: {tiers['gold']:,}",
        f"- Silver-A rows: {tiers['silver_a']:,}",
        f"- Silver-B rows: {tiers['silver_b']:,}",
        f"- Rejected rows: {tiers['rejected']:,}",
        f"- Candidate unknown/empty text: {text['candidate_unknown_or_empty_text']:,}",
        f"- Candidate description-chain issues: {alignment['candidate_workflows_with_issues']:,}",
        f"- Candidate authoritative source identity: {source['candidate_authoritative_workflows']:,}",
        f"- Active candidate L3 codes: {modality['active_l3']:,}",
        f"- Candidate Top10 L3 share: {modality['top10_l3_share']:.2%}",
        f"- Duplicate L3-sequence candidate items: {duplicates['candidate_duplicate_l3_sequence_items']:,}",
        "",
        "## Training Decision",
        "",
        f"- Training admission: `{report['decision']['training_admission']}`",
        f"- Large dataset overwrite authorized: `{report['decision']['large_dataset_overwrite_authorized']}`",
        f"- Recommended next gate: {report['decision']['recommended_next_gate']}",
        "",
        "## Tier Definitions",
        "",
        "- `gold`: usable text, valid schema/L3 chain, no description-chain issue, authoritative source identity.",
        "- `silver_a`: usable text, valid schema/L3 chain, no description-chain issue, but missing authoritative source identity.",
        "- `silver_b`: usable text and valid schema/L3 chain, but has description-chain or low-confidence risk.",
        "- `rejected`: unknown/empty text, invalid schema/L3/length, or quality-gate quarantine.",
        "",
        "## Top L3 Codes",
        "",
    ]
    for item in modality["top_l3"][:20]:
        lines.append(f"- `{item['item']}`: {item['count']:,}")
    lines.append("")
    return "\n".join(lines)


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
            handle.write(text)
            if text and not text.endswith("\n"):
                handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", type=Path, default=DEFAULT_CANDIDATE)
    parser.add_argument("--quarantine", type=Path, default=DEFAULT_QUARANTINE)
    parser.add_argument("--hierarchy", type=Path, default=DEFAULT_HIERARCHY)
    parser.add_argument("--min-chain-len", type=int, default=1)
    parser.add_argument("--max-chain-len", type=int, default=20)
    parser.add_argument("--output", type=Path, default=DEFAULT_REPORT_JSON)
    parser.add_argument("--markdown-output", type=Path, default=DEFAULT_REPORT_MD)
    args = parser.parse_args(argv)

    report = build_training_admission_audit(
        candidate_path=args.candidate,
        quarantine_path=args.quarantine,
        hierarchy_path=args.hierarchy,
        min_chain_len=args.min_chain_len,
        max_chain_len=args.max_chain_len,
    )
    _atomic_write_text(
        args.output,
        json.dumps(report, ensure_ascii=False, indent=2),
    )
    _atomic_write_text(args.markdown_output, _render_markdown(report))
    return {"json": args.output, "markdown": args.markdown_output}


if __name__ == "__main__":
    main()
