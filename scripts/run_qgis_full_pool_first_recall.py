"""Roll up the first unified 47,852-source QGIS recall experiment.

This runner consumes source-level census rows plus optional candidate/review
ledgers. It never infers Gold/Silver from role tiers and never emits training
rows; missing stages are reported as ``not_available``.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any

SCHEMA = "gis_recommend.qgis_full_pool_first_recall.v1"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        value = json.loads(line)
        if not isinstance(value, dict):
            raise ValueError(f"{path}:{line_no} is not an object")
        rows.append(value)
    return rows


def _count(rows: list[dict[str, Any]], *keys: str) -> Counter[str]:
    result: Counter[str] = Counter()
    for row in rows:
        value = next((row.get(key) for key in keys if row.get(key) not in (None, "")), "unspecified")
        result[str(value)] += 1
    return result


def build_report(
    census_rows: list[dict[str, Any]],
    candidate_rows: list[dict[str, Any]] | None = None,
    review_rows: list[dict[str, Any]] | None = None,
    observed_curated_rows: int | None = None,
    candidate_scope: str = "unspecified",
) -> dict[str, Any]:
    source_ids = [str(row.get("source_sha256") or row.get("content_sha256") or "") for row in census_rows]
    nonempty_sources = [value for value in source_ids if value]
    if len(set(nonempty_sources)) != len(nonempty_sources):
        raise ValueError("census source identities are not unique")
    candidates = candidate_rows or []
    candidate_sources = {
        str(row.get("source_sha256") or row.get("manifest_source_sha256") or "")
        for row in candidates
        if row.get("source_sha256") or row.get("manifest_source_sha256")
    }
    census_sources = set(nonempty_sources)
    review = review_rows or []
    review_decisions = _count(review, "decision", "semantic_review_decision", "task_fidelity_decision") if review_rows is not None else None
    accepted = 0
    gold = 0
    silver = 0
    if review_rows is not None:
        for row in review:
            quality = row.get("_training_quality") or {}
            weight = quality.get("sample_weight")
            if weight == 1.0:
                gold += 1
            elif weight == 0.7:
                silver += 1
        accepted = gold + silver
    return {
        "schema": SCHEMA,
        "scope": "unified_first_recall_experiment",
        "training_rows_emitted": 0,
        "training_admission": "not_granted_recall_rollup",
        "census": {
            "source_rows": len(census_rows),
            "unique_source_sha256": len(census_sources),
            "role_counts": dict(_count(census_rows, "source_role")),
            "tier_counts": dict(_count(census_rows, "workflow_value_tier")),
        },
        "candidate_stage": {
            "status": "available" if candidate_rows is not None else "not_available",
            "candidate_rows": len(candidates) if candidate_rows is not None else None,
            "scope": candidate_scope,
            "candidate_unique_sources": len(candidate_sources) if candidate_rows is not None else None,
            "candidate_sources_in_census": len(candidate_sources & census_sources) if candidate_rows is not None else None,
            "candidate_source_recall": (
                round(len(candidate_sources & census_sources) / len(census_sources), 6)
                if candidate_rows is not None and census_sources and candidate_scope == "full_pool"
                else None
            ),
            "recall_interpretation": "Only valid when candidate ledger covers the same census population; otherwise this is a lower-bound coverage ratio.",
            "candidate_rate_over_census": (
                round(len(candidate_sources & census_sources) / len(census_sources), 6)
                if candidate_rows is not None and census_sources else None
            ),
            "candidate_kind_counts": dict(_count(candidates, "candidate_kind")) if candidate_rows is not None else None,
        },
        "review_stage": {
            "status": "available" if review_rows is not None else "not_available",
            "reviewed_rows": len(review) if review_rows is not None else None,
            "decision_counts": dict(review_decisions) if review_decisions is not None else None,
            "gold_rows": gold if review_rows is not None else None,
            "silver_rows": silver if review_rows is not None else None,
            "accepted_rows": accepted if review_rows is not None else None,
            "accepted_yield_over_census": round(accepted / len(census_rows), 6) if review_rows is not None and census_rows else None,
        },
        "observed_curated_stage": {
            "status": "available" if observed_curated_rows is not None else "not_available",
            "rows": observed_curated_rows,
            "yield_over_census": round(observed_curated_rows / len(census_rows), 6)
            if observed_curated_rows is not None and census_rows else None,
            "linkage": "not_asserted_against_candidate_stage",
        },
        "interpretation": "Counts are valid only for the supplied source-level ledgers; unavailable stages are not estimated.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--census", type=Path, required=True)
    parser.add_argument("--candidates", type=Path)
    parser.add_argument("--review", type=Path)
    parser.add_argument("--observed-curated-rows", type=int)
    parser.add_argument("--candidate-scope", default="unspecified", choices=("full_pool", "processing_only", "api_only", "unspecified"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    report = build_report(
        read_jsonl(args.census),
        read_jsonl(args.candidates) if args.candidates else None,
        read_jsonl(args.review) if args.review else None,
        args.observed_curated_rows,
        args.candidate_scope,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"source_rows": report["census"]["source_rows"], "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
