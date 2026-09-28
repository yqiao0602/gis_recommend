#!/usr/bin/env python3
"""Validate and summarize the P0 QGIS operator-to-L3 mapping proposals.

The adjudication is deliberately not a taxonomy authority. This check keeps the
distinction executable: accepted rows remain proposals until an explicit
taxonomy decision grants admission.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


EXPECTED_ADJUDICATION_ROWS = 17
EXPECTED_ACCEPTED_ROWS = 9
EXPECTED_EVIDENCE_PER_OPERATOR = 3
ALLOWED_DECISIONS = {
    "accepted_mapping_proposal",
    "deferred_multi_candidate",
    "deferred_new_l3_design",
    "deferred_old350_boundary",
    "deferred_parameter_semantics",
}


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            text = line.strip()
            if not text:
                continue
            item = json.loads(text)
            if not isinstance(item, dict):
                raise ValueError(f"{path}:{line_number} must be a JSON object")
            rows.append(item)
    return rows


def _l3_codes(path: Path) -> set[str]:
    rows = _read_csv(path)
    if not rows:
        raise ValueError(f"hierarchy is empty: {path}")
    code_field = next(
        (field for field in ("l3_code", "L3_Code") if field in rows[0]),
        None,
    )
    if code_field is None:
        raise ValueError(f"hierarchy has no L3 code column: {path}")
    return {row[code_field].strip() for row in rows if row.get(code_field, "").strip()}


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate(
    adjudications: list[dict[str, Any]],
    review_rows: list[dict[str, str]],
    evidence_rows: list[dict[str, str]],
    stable94_codes: set[str],
    legacy350_codes: set[str],
) -> dict[str, Any]:
    errors: list[str] = []
    if len(adjudications) != EXPECTED_ADJUDICATION_ROWS:
        errors.append(
            f"expected {EXPECTED_ADJUDICATION_ROWS} adjudication rows, got {len(adjudications)}"
        )

    by_operator: dict[str, dict[str, Any]] = {}
    for row in adjudications:
        operator_id = str(row.get("operator_id", "")).strip().lower()
        if not operator_id:
            errors.append("adjudication has an empty operator_id")
            continue
        if operator_id in by_operator:
            errors.append(f"duplicate adjudication operator_id: {operator_id}")
            continue
        by_operator[operator_id] = row

        decision = row.get("review_decision")
        if decision not in ALLOWED_DECISIONS:
            errors.append(f"{operator_id}: unsupported review_decision {decision!r}")
        if row.get("taxonomy_admission") != "not_granted":
            errors.append(f"{operator_id}: taxonomy_admission must remain not_granted")
        if row.get("training_admission") != "not_granted":
            errors.append(f"{operator_id}: training_admission must remain not_granted")
        if row.get("evidence_count") != EXPECTED_EVIDENCE_PER_OPERATOR:
            errors.append(
                f"{operator_id}: evidence_count must be {EXPECTED_EVIDENCE_PER_OPERATOR}"
            )

    review_by_operator = {
        row["operator_id"].strip().lower(): row
        for row in review_rows
        if row.get("operator_id", "").strip()
    }
    if set(by_operator) != set(review_by_operator):
        errors.append("adjudication operator IDs do not exactly match p0_mapping_review.csv")
    for operator_id, row in by_operator.items():
        review = review_by_operator.get(operator_id)
        if review is None:
            continue
        if int(row.get("frequency", -1)) != int(review.get("frequency", -2)):
            errors.append(f"{operator_id}: frequency differs from p0_mapping_review.csv")
        if int(review.get("evidence_count", -1)) != EXPECTED_EVIDENCE_PER_OPERATOR:
            errors.append(f"{operator_id}: review evidence_count must be 3")

    evidence_by_operator: dict[str, list[dict[str, str]]] = defaultdict(list)
    for row in evidence_rows:
        operator_id = row.get("operator_id", "").strip().lower()
        if operator_id in by_operator:
            evidence_by_operator[operator_id].append(row)
    for operator_id in by_operator:
        samples = evidence_by_operator[operator_id]
        if len(samples) != EXPECTED_EVIDENCE_PER_OPERATOR:
            errors.append(f"{operator_id}: expected 3 source evidence rows, got {len(samples)}")
        if any(row.get("execution_status") != "active_call" for row in samples):
            errors.append(f"{operator_id}: all source evidence must be active_call")

    accepted = [
        row for row in adjudications
        if row.get("review_decision") == "accepted_mapping_proposal"
    ]
    if len(accepted) != EXPECTED_ACCEPTED_ROWS:
        errors.append(f"expected {EXPECTED_ACCEPTED_ROWS} accepted proposals, got {len(accepted)}")
    for row in accepted:
        operator_id = str(row["operator_id"]).lower()
        mapping_kind = row.get("mapping_kind")
        codes = row.get("candidate_l3_codes")
        if not isinstance(codes, list) or not codes:
            errors.append(f"{operator_id}: accepted proposal must contain candidate_l3_codes")
            continue
        if mapping_kind == "alias_existing_stable94":
            missing = [code for code in codes if code not in stable94_codes]
            if missing:
                errors.append(f"{operator_id}: stable-94 alias code(s) absent: {missing}")
        elif mapping_kind == "restore_old350_l3":
            missing_legacy = [code for code in codes if code not in legacy350_codes]
            present_stable = [code for code in codes if code in stable94_codes]
            if missing_legacy:
                errors.append(f"{operator_id}: legacy-350 code(s) absent: {missing_legacy}")
            if present_stable:
                errors.append(
                    f"{operator_id}: restored legacy code(s) already in stable-94: {present_stable}"
                )
        else:
            errors.append(f"{operator_id}: accepted proposal has invalid mapping_kind {mapping_kind!r}")

    if errors:
        raise ValueError("P0 mapping adjudication validation failed:\n- " + "\n- ".join(errors))

    return {
        "adjudication_rows": len(adjudications),
        "operator_ids": sorted(by_operator),
        "frequency_total": sum(int(row["frequency"]) for row in adjudications),
        "decision_counts": dict(sorted(Counter(row["review_decision"] for row in adjudications).items())),
        "mapping_kind_counts": dict(sorted(Counter(row["mapping_kind"] for row in adjudications).items())),
        "accepted_operator_ids": sorted(str(row["operator_id"]) for row in accepted),
        "deferred_operator_ids": sorted(
            str(row["operator_id"])
            for row in adjudications
            if row["review_decision"] != "accepted_mapping_proposal"
        ),
        "admission_state": {
            "taxonomy_admission": "not_granted",
            "training_admission": "not_granted",
        },
        "validation": "passed",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adjudications", required=True, type=Path)
    parser.add_argument("--review-csv", required=True, type=Path)
    parser.add_argument("--evidence-csv", required=True, type=Path)
    parser.add_argument("--stable94-hierarchy", required=True, type=Path)
    parser.add_argument("--legacy350-hierarchy", required=True, type=Path)
    parser.add_argument("--output-json", required=True, type=Path)
    args = parser.parse_args()

    summary = validate(
        _read_jsonl(args.adjudications),
        _read_csv(args.review_csv),
        _read_csv(args.evidence_csv),
        _l3_codes(args.stable94_hierarchy),
        _l3_codes(args.legacy350_hierarchy),
    )
    summary["input_sha256"] = {
        "adjudications": _sha256(args.adjudications),
        "review_csv": _sha256(args.review_csv),
        "evidence_csv": _sha256(args.evidence_csv),
        "stable94_hierarchy": _sha256(args.stable94_hierarchy),
        "legacy350_hierarchy": _sha256(args.legacy350_hierarchy),
    }
    args.output_json.parent.mkdir(parents=True, exist_ok=True)
    args.output_json.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    print(
        "validation=passed "
        f"rows={summary['adjudication_rows']} "
        f"accepted={len(summary['accepted_operator_ids'])} "
        f"deferred={len(summary['deferred_operator_ids'])}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
