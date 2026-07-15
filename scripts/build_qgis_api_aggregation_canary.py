#!/usr/bin/env python3
"""Select, run, and report a bounded QGIS provider canary."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
for path in (ROOT, SRC):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

from gis_recommend.data.qgis_pilot import PILOT_SCHEMA, assert_write_allowed, file_sha256
from scripts.run_qgis_api_aggregation_pilot import (
    DEFAULT_BASE_URL,
    DEFAULT_MODEL,
    AggregationContractError,
    aggregate_record,
    create_provider_client,
    load_operator_catalog,
    require_api_key,
    select_bounded_operator_catalog,
)


CANARY_SEED = 20260715
CANARY_SIZE = 24
_BALANCE_WEIGHTS = {
    "evidence_source_mode": 4.0,
    "modality_hint": 4.0,
    "trace_length_bucket": 2.0,
    "ordering_quality": 3.0,
    "extraction_group": 1.0,
}


def _canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _stable_key(seed: int, value: str) -> str:
    return hashlib.sha256(f"{seed}:{value}".encode("utf-8")).hexdigest()


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"JSONL row {line_number} in {path} is not an object")
            rows.append(row)
    return rows


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(_canonical_json(dict(row)) + "\n")


def _source_quotas(records: Sequence[Mapping[str, Any]], *, size: int, seed: int) -> dict[str, int]:
    available = Counter(str(record.get("evidence_source_mode") or "unknown") for record in records)
    modes = sorted(available, key=lambda mode: _stable_key(seed, mode))
    if not modes:
        return {}
    base, remainder = divmod(size, len(modes))
    quotas = {
        mode: min(available[mode], base + (index < remainder))
        for index, mode in enumerate(modes)
    }
    unassigned = size - sum(quotas.values())
    while unassigned:
        candidates = [mode for mode in modes if quotas[mode] < available[mode]]
        if not candidates:
            raise ValueError("source-mode quotas cannot satisfy requested canary size")
        mode = min(candidates, key=lambda item: (quotas[item], _stable_key(seed, item)))
        quotas[mode] += 1
        unassigned -= 1
    return quotas


def select_stratified_canary(
    records: Sequence[Mapping[str, Any]],
    *,
    ready_record_ids: set[str],
    exclude_record_ids: set[str],
    size: int,
    seed: int,
) -> list[dict[str, Any]]:
    if size <= 0:
        raise ValueError("canary size must be positive")
    eligible = [
        dict(record)
        for record in records
        if str(record.get("record_id") or "") in ready_record_ids
        and str(record.get("record_id") or "") not in exclude_record_ids
    ]
    deduplicated: dict[str, dict[str, Any]] = {}
    for record in sorted(
        eligible,
        key=lambda row: _stable_key(seed, str(row.get("record_id") or "")),
    ):
        source_identity = str(record.get("source_script") or record.get("record_id") or "")
        deduplicated.setdefault(source_identity, record)
    pool = list(deduplicated.values())
    if len(pool) < size:
        raise ValueError(
            f"requested {size} canary rows but only {len(pool)} eligible unique records remain"
        )

    source_quotas = _source_quotas(pool, size=size, seed=seed)
    dimension_values = {
        dimension: sorted({str(record.get(dimension) or "unknown") for record in pool})
        for dimension in _BALANCE_WEIGHTS
    }
    dimension_targets = {
        dimension: math.ceil(size / len(values))
        for dimension, values in dimension_values.items()
    }
    selected: list[dict[str, Any]] = []
    counts: Counter[tuple[str, str]] = Counter()
    family_counts: Counter[str] = Counter()
    remaining = list(pool)

    def score(record: Mapping[str, Any]) -> float:
        value = 0.0
        for dimension, weight in _BALANCE_WEIGHTS.items():
            category = str(record.get(dimension) or "unknown")
            target = dimension_targets[dimension]
            deficit = max(target - counts[(dimension, category)], 0)
            value += weight * deficit / target
        family = str(record.get("primary_semantic_family") or "unknown")
        value += 3.0 if not family_counts[family] else 0.25 / (family_counts[family] + 1)
        return value

    while len(selected) < size:
        allowed = [
            record
            for record in remaining
            if counts[
                ("evidence_source_mode", str(record.get("evidence_source_mode") or "unknown"))
            ]
            < source_quotas[str(record.get("evidence_source_mode") or "unknown")]
        ]
        if not allowed:
            raise ValueError("stratified selection exhausted before reaching requested size")
        chosen = min(
            allowed,
            key=lambda record: (
                -score(record),
                _stable_key(seed, str(record.get("record_id") or "")),
            ),
        )
        selected.append(chosen)
        remaining.remove(chosen)
        for dimension in _BALANCE_WEIGHTS:
            counts[(dimension, str(chosen.get(dimension) or "unknown"))] += 1
        family_counts[str(chosen.get("primary_semantic_family") or "unknown")] += 1
    return selected


def _distribution(records: Sequence[Mapping[str, Any]]) -> dict[str, dict[str, int]]:
    fields = [*_BALANCE_WEIGHTS, "primary_semantic_family"]
    return {
        field: dict(
            sorted(Counter(str(record.get(field) or "unknown") for record in records).items())
        )
        for field in fields
    }


def run_canary(
    selected: Sequence[Mapping[str, Any]],
    *,
    client: Any,
    full_catalog: Mapping[str, Mapping[str, Any]],
    taxonomy_codes: set[str],
    model: str,
    candidate_limit: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    proposals = []
    outcomes = []
    for record in selected:
        record_id = str(record.get("record_id") or "")
        bounded = select_bounded_operator_catalog(record, full_catalog, limit=candidate_limit)
        try:
            if not bounded:
                raise AggregationContractError("no_bounded_candidates")
            proposal = aggregate_record(
                client,
                record,
                operator_catalog=bounded,
                taxonomy_codes=taxonomy_codes,
                model=model,
            )
        except AggregationContractError as exc:
            outcome = exc.code
        except Exception as exc:  # Provider exceptions are deliberately reduced to bounded metadata.
            status = getattr(exc, "status_code", None)
            outcome = f"provider_http_{status}" if status else f"provider_error_{type(exc).__name__}"
        else:
            proposals.append(proposal)
            outcome = "validated_proposal"
        outcomes.append(
            {
                "schema": PILOT_SCHEMA,
                "kind": "qgis_api_canary_outcome_v1",
                "record_id": record_id,
                "outcome": outcome,
                "review_status": "pending",
                "training_admission": "forbidden_until_reviewed",
            }
        )
    return proposals, outcomes


def summarize_canary_run(
    *,
    selected_count: int,
    outcomes: Sequence[Mapping[str, Any]],
    raw_provider_responses_persisted: bool,
) -> dict[str, Any]:
    outcome_counts = Counter(str(row.get("outcome") or "unknown") for row in outcomes)
    validated = outcome_counts["validated_proposal"]
    attempted = len(outcomes)
    pass_rate = validated / attempted if attempted else 0.0
    failures = {key: value for key, value in outcome_counts.items() if key != "validated_proposal"}
    repeated_failure_share = max(failures.values(), default=0) / attempted if attempted else 0.0
    stop_conditions = {
        "pass_rate_below_0_70": pass_rate < 0.70,
        "repeated_failure_share_above_0_30": repeated_failure_share > 0.30,
        "reasoning_returned_or_raw_persisted": bool(
            raw_provider_responses_persisted or outcome_counts["provider_returned_reasoning"]
        ),
    }
    return {
        "schema": PILOT_SCHEMA,
        "kind": "qgis_api_aggregation_canary_summary_v1",
        "selected_records": selected_count,
        "attempted_records": attempted,
        "validated_proposals": validated,
        "contract_pass_rate": pass_rate,
        "outcomes": dict(sorted(outcome_counts.items())),
        "stop_conditions": stop_conditions,
        "raw_provider_responses_persisted": raw_provider_responses_persisted,
        "human_review_required": True,
        "training_admission": "forbidden_until_reviewed",
        "scaling_admission": (
            "blocked" if any(stop_conditions.values()) else "blocked_pending_human_review"
        ),
    }


def build_canary_review_rows(
    selected: Sequence[Mapping[str, Any]],
    *,
    proposals: Sequence[Mapping[str, Any]],
    outcomes: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    proposal_by_id = {str(row.get("record_id") or ""): row for row in proposals}
    outcome_by_id = {str(row.get("record_id") or ""): row for row in outcomes}
    rows = []
    for record in selected:
        record_id = str(record.get("record_id") or "")
        proposal_wrapper = proposal_by_id.get(record_id, {})
        proposal = proposal_wrapper.get("proposal") or {}
        rows.append(
            {
                "record_id": record_id,
                "source_script": record.get("source_script"),
                "task_name": record.get("task_name"),
                "task_description": record.get("task_description"),
                "evidence_source_mode": record.get("evidence_source_mode"),
                "modality_hint": record.get("modality_hint"),
                "trace_length_bucket": record.get("trace_length_bucket"),
                "ordering_quality": record.get("ordering_quality"),
                "extraction_group": record.get("extraction_group"),
                "primary_semantic_family": record.get("primary_semantic_family"),
                "compact_evidence_json": _canonical_json(record.get("compact_steps", [])),
                "provider_outcome": outcome_by_id.get(record_id, {}).get("outcome", "missing"),
                "provider_decision": proposal.get("decision"),
                "candidate_operators_json": _canonical_json(
                    proposal.get("candidate_operators", [])
                ),
                "rejected_infrastructure_json": _canonical_json(
                    proposal.get("rejected_infrastructure", [])
                ),
                "unsupported_evidence_ids_json": _canonical_json(
                    proposal.get("unsupported_evidence_ids", [])
                ),
                "conflict_flags_json": _canonical_json(proposal.get("conflict_flags", [])),
                "brief_rationale": proposal.get("rationale"),
                "reviewer_decision": None,
                "corrected_operator_sequence": None,
                "corrected_l3_chain": None,
                "failure_tags": None,
                "reviewer_notes": None,
                "review_status": "pending",
                "training_admission": "forbidden_until_reviewed",
            }
        )
    return rows


def _write_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    if not rows:
        raise ValueError("cannot write an empty review workbook")
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _write_ledger(output_dir: Path, paths: Sequence[Path]) -> Path:
    ledger_path = output_dir / "canary_write_ledger.json"
    ledger = {
        "schema": PILOT_SCHEMA,
        "created_or_replaced": [
            {"path": str(path), "sha256": file_sha256(path), "size": path.stat().st_size}
            for path in paths
        ],
    }
    ledger_path.write_text(
        json.dumps(ledger, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    return ledger_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--pilot-jsonl", type=Path, required=True)
    parser.add_argument("--preflight-jsonl", type=Path, required=True)
    parser.add_argument("--crosswalk", type=Path, required=True)
    parser.add_argument("--taxonomy", type=Path, required=True)
    parser.add_argument("--exclude-proposals", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--allowed-write-root", type=Path, action="append", required=True)
    parser.add_argument("--size", type=int, default=CANARY_SIZE)
    parser.add_argument("--seed", type=int, default=CANARY_SEED)
    parser.add_argument("--candidate-limit", type=int, default=30)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--model", default=DEFAULT_MODEL)
    parser.add_argument("--timeout", type=float, default=120.0)
    parser.add_argument("--selection-only", action="store_true")
    args = parser.parse_args(argv)

    output_dir = assert_write_allowed(args.output_dir, args.allowed_write_root)
    output_dir.mkdir(parents=True, exist_ok=True)
    records = _load_jsonl(args.pilot_jsonl)
    preflight = _load_jsonl(args.preflight_jsonl)
    ready_ids = {
        str(row.get("record_id") or "")
        for row in preflight
        if row.get("status") == "ready_for_provider"
    }
    excluded = set()
    if args.exclude_proposals and args.exclude_proposals.exists():
        excluded = {
            str(row.get("record_id") or "") for row in _load_jsonl(args.exclude_proposals)
        }
    selected = select_stratified_canary(
        records,
        ready_record_ids=ready_ids,
        exclude_record_ids=excluded,
        size=args.size,
        seed=args.seed,
    )
    selection_path = output_dir / "canary_selection.jsonl"
    _write_jsonl(selection_path, selected)
    selection_summary_path = output_dir / "canary_selection_summary.json"
    selection_summary = {
        "schema": PILOT_SCHEMA,
        "kind": "qgis_api_aggregation_canary_selection_summary_v1",
        "size": len(selected),
        "seed": args.seed,
        "excluded_prior_proposals": len(excluded),
        "unique_record_ids": len({str(row.get("record_id")) for row in selected}),
        "unique_source_scripts": len({str(row.get("source_script")) for row in selected}),
        "distribution": _distribution(selected),
        "training_admission": "forbidden_until_reviewed",
    }
    selection_summary_path.write_text(
        json.dumps(selection_summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    if args.selection_only:
        _write_ledger(output_dir, [selection_path, selection_summary_path])
        print(json.dumps(selection_summary, ensure_ascii=False, indent=2))
        return 0

    catalog, taxonomy_codes = load_operator_catalog(args.crosswalk, args.taxonomy)
    client = create_provider_client(
        api_key=require_api_key(),
        base_url=args.base_url,
        timeout=args.timeout,
    )
    proposals, outcomes = run_canary(
        selected,
        client=client,
        full_catalog=catalog,
        taxonomy_codes=taxonomy_codes,
        model=args.model,
        candidate_limit=args.candidate_limit,
    )
    proposals_path = output_dir / "canary_proposals.jsonl"
    outcomes_path = output_dir / "canary_outcomes.jsonl"
    review_path = output_dir / "canary_review.csv"
    summary_path = output_dir / "canary_summary.json"
    _write_jsonl(proposals_path, proposals)
    _write_jsonl(outcomes_path, outcomes)
    _write_csv(
        review_path,
        build_canary_review_rows(selected, proposals=proposals, outcomes=outcomes),
    )
    summary = summarize_canary_run(
        selected_count=len(selected),
        outcomes=outcomes,
        raw_provider_responses_persisted=False,
    )
    summary["selection_distribution"] = selection_summary["distribution"]
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    _write_ledger(
        output_dir,
        [
            selection_path,
            selection_summary_path,
            proposals_path,
            outcomes_path,
            review_path,
            summary_path,
        ],
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
