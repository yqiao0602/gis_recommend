#!/usr/bin/env python3
"""Build a source-backed evidence report for a frozen GEE audit packet.

This is deliberately an audit aid, not an admission tool.  It validates the
mechanical facts an adjudicator must see before assigning a human verdict:
source identity, evidence spans, task-text claims, retained operators, and
the claimed output class.  The existing hash-bound evaluator remains the only
component that can evaluate an adjudication packet.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


def _jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def _canonical_operator_name(operator: str) -> str:
    return re.sub(r"[^a-z0-9]", "", operator.rsplit(".", 1)[-1].lower())


def _source_method_names(source: str) -> list[str]:
    names = [
        re.sub(r"[^a-z0-9]", "", name.lower())
        for name in re.findall(r"\.([A-Za-z][A-Za-z0-9_]*)\s*\(", source)
    ]
    # GEE exposes both collection.filterDate(...) and the equivalent
    # collection.filter(ee.Filter.date(...)); the latter must support the
    # retained canonical ``filterdate`` operator during source review.
    names.extend(
        "filterdate"
        for _ in re.finditer(r"\.filter\s*\(\s*ee\.Filter\.date\s*\(", source)
    )
    return names


def _line_span_is_valid(lines: list[str], location: dict[str, Any]) -> bool:
    start_line = location.get("start_line")
    end_line = location.get("end_line")
    start_column = location.get("start_column")
    end_column = location.get("end_column")
    if not all(isinstance(value, int) for value in (start_line, end_line, start_column, end_column)):
        return False
    if start_line < 1 or end_line < start_line or end_line > len(lines):
        return False
    if start_column < 0 or end_column < 0:
        return False
    if start_line == end_line:
        if end_column < start_column or end_column > len(lines[start_line - 1]):
            return False
    elif start_column > len(lines[start_line - 1]) or end_column > len(lines[end_line - 1]):
        return False
    return True


def _task_operators(description: str) -> list[str] | None:
    matched = re.search(r"operations in order: ([^.]+)\. Produce", description, flags=re.IGNORECASE)
    if not matched:
        return None
    return [part.strip().lower() for part in matched.group(1).split(";") if part.strip()]


def _task_output_class(name: str, description: str) -> str | None:
    matched = re.search(r"Create an? ([a-z]+) with an ordered", name, flags=re.IGNORECASE)
    if not matched:
        return None
    output = matched.group(1).lower()
    if f"resulting {output} as the workflow output" not in description.lower():
        return None
    return output


def _source_supports_output_class(source: str, output: str | None) -> bool:
    if output is None:
        return False
    if output == "image":
        return bool(re.search(r"\bExport\.image(?:\.\w+)?\s*\(", source) or re.search(r"\bMap\.addLayer\s*\(", source))
    if output == "video":
        return bool(re.search(r"\bExport\.video(?:\.\w+)?\s*\(", source))
    if output == "table":
        return bool(re.search(r"\bExport\.table(?:\.\w+)?\s*\(", source))
    return False


def _source_dataset_claims(description: str) -> list[str]:
    return re.findall(r"Use ([^.]*) as the source imagery\.", description)


def _source_temporal_claims(description: str) -> list[tuple[str, str]]:
    return re.findall(r"filterDate interval \[([^,]+), ([^)]+)\)", description)


def _source_supports_temporal_claim(source: str, start: str, end: str) -> bool:
    if start in source and end in source:
        return True
    literals = {
        name: value
        for name, value in re.findall(
            r"\b(?:var|let|const)\s+([A-Za-z_$][\w$]*)\s*=\s*['\"]([^'\"]+)['\"]\s*;",
            source,
        )
    }
    for name, base, suffix in re.findall(
        r"\b(?:var|let|const)\s+([A-Za-z_$][\w$]*)\s*=\s*"
        r"([A-Za-z_$][\w$]*)\s*\+\s*['\"]([^'\"]+)['\"]\s*;",
        source,
    ):
        if base in literals:
            literals[name] = literals[base] + suffix
    return start in literals.values() and end in literals.values()


def _review_row(row: dict[str, Any], source_root: Path) -> dict[str, Any]:
    relative = row.get("source_path")
    if not isinstance(relative, str):
        raise ValueError("audit row has no source_path")
    source_path = (source_root / relative).resolve()
    if source_root.resolve() not in source_path.parents:
        raise ValueError(f"source path escapes source root: {relative}")
    source_bytes = source_path.read_bytes()
    source = source_bytes.decode("utf-8", errors="replace")
    lines = source.splitlines()
    expected_sha = row.get("source_sha256")
    actual_sha = hashlib.sha256(source_bytes).hexdigest()
    evidence = row.get("evidence_locations") or []
    spans_valid = all(
        isinstance(item, dict)
        and isinstance(item.get("source_location"), dict)
        and _line_span_is_valid(lines, item["source_location"])
        for item in evidence
    )
    source_methods = _source_method_names(source)
    operators = row.get("operator_sequence") or []
    canonical_operators = [_canonical_operator_name(operator) for operator in operators]
    source_method_counts = Counter(source_methods)
    retained_counts = Counter(canonical_operators)
    operator_occurrences_present = all(
        source_method_counts[operator] >= count for operator, count in retained_counts.items()
    )
    description = str(row.get("task_description") or "")
    generated_operators = _task_operators(description)
    task_operator_match = generated_operators == canonical_operators
    datasets = _source_dataset_claims(description)
    dataset_claims_present = all(dataset in source for dataset in datasets)
    temporal_claims = _source_temporal_claims(description)
    temporal_claims_present = all(
        _source_supports_temporal_claim(source, start, end) for start, end in temporal_claims
    )
    output_class = _task_output_class(str(row.get("task_name") or ""), description)
    output_claim_supported = _source_supports_output_class(source, output_class)
    checks = {
        "source_sha256": actual_sha == expected_sha,
        "source_bytes": len(source_bytes) == row.get("source_bytes"),
        "source_evidence_spans": spans_valid,
        "retained_operator_occurrences": operator_occurrences_present,
        "task_operator_sequence": task_operator_match,
        "dataset_claims": dataset_claims_present,
        "temporal_claims": temporal_claims_present,
        "output_class": output_claim_supported,
    }
    return {
        "audit_index": row.get("audit_index"),
        "source_path": relative,
        "source_sha256": expected_sha,
        "workflow_id": row.get("workflow_id"),
        "risk_stratum": row.get("risk_stratum"),
        "risk_flags": row.get("risk_flags") or [],
        "operator_sequence": operators,
        "l3_sequence": row.get("l3_sequence") or [],
        "task_name": row.get("task_name"),
        "task_description": description,
        "output_class": output_class,
        "checks": checks,
        "passed_checks": all(checks.values()),
        "failed_checks": sorted(name for name, passed in checks.items() if not passed),
        "source_method_counts": {name: source_method_counts[name] for name in sorted(retained_counts)},
        "retained_method_counts": dict(sorted(retained_counts.items())),
        "evidence_fact_types": [item.get("fact_type") for item in evidence if isinstance(item, dict)],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--audit", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = _jsonl(args.audit)
    reviewed = [_review_row(row, args.source_root) for row in rows]
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in reviewed),
        encoding="utf-8",
    )
    print(
        json.dumps(
            {
                "audit_rows": len(reviewed),
                "mechanically_supported_rows": sum(row["passed_checks"] for row in reviewed),
                "rows_requiring_adjudicator_attention": [
                    row["audit_index"] for row in reviewed if not row["passed_checks"]
                ],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
