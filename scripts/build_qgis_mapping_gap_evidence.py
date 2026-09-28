#!/usr/bin/env python3
"""Collect deterministic source snippets for P0 QGIS mapping-gap review."""

from __future__ import annotations

import argparse
import csv
import hashlib
import re
from collections import defaultdict
from pathlib import Path


DEFAULT_SOURCE_DIRS = (
    "QGIS_standard_multi_operator_workflows_v2/downloaded_scripts",
    "github_qgis_workflow/downloaded_scripts",
    "github_qgis_workflow_A类/downloaded_scripts",
)


def _load_p0_operators(path: Path) -> list[str]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = csv.DictReader(handle)
        operators = [
            str(row.get("operator_id") or "").strip().lower()
            for row in rows
            if row.get("priority") == "P0_frequency_ge_20"
        ]
    if not operators or len(operators) != len(set(operators)):
        raise ValueError("P0 operator review rows are missing or duplicated")
    return sorted(operators)


def _line_snippet(lines: list[str], index: int) -> str:
    start = max(index - 1, 0)
    end = min(index + 2, len(lines))
    return "\n".join(f"{line_number + 1}: {lines[line_number]}" for line_number in range(start, end))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-csv", required=True, type=Path)
    parser.add_argument("--source-root", required=True, type=Path)
    parser.add_argument("--output-csv", required=True, type=Path)
    parser.add_argument("--samples-per-operator", default=3, type=int)
    args = parser.parse_args()
    if args.samples_per_operator < 1:
        raise ValueError("samples-per-operator must be positive")

    operators = _load_p0_operators(args.review_csv)
    patterns = {
        operator: re.compile(
            r"(?:processing\.run|processing\.runalg)\s*\(\s*['\"]"
            + re.escape(operator)
            + r"['\"]",
            re.IGNORECASE,
        )
        for operator in operators
    }
    evidence: dict[str, list[dict[str, object]]] = defaultdict(list)
    commented_hits: dict[str, int] = defaultdict(int)

    for relative_dir in DEFAULT_SOURCE_DIRS:
        source_dir = args.source_root / relative_dir
        if not source_dir.is_dir():
            continue
        for path in sorted(source_dir.glob("*.py")):
            required = [
                operator
                for operator in operators
                if len(evidence[operator]) < args.samples_per_operator
            ]
            if not required:
                break
            raw = path.read_bytes()
            text = raw.decode("utf-8", errors="replace")
            lines = text.splitlines()
            lowered = text.lower()
            for operator in required:
                match = patterns[operator].search(lowered)
                if not match:
                    continue
                line_number = lowered[: match.start()].count("\n") + 1
                source_line = lines[line_number - 1] if line_number <= len(lines) else ""
                if source_line.lstrip().startswith("#"):
                    commented_hits[operator] += 1
                    continue
                evidence[operator].append(
                    {
                        "priority": "P0_frequency_ge_20",
                        "operator_id": operator,
                        "sample_rank": len(evidence[operator]) + 1,
                        "source_relative_path": path.relative_to(args.source_root).as_posix(),
                        "source_sha256": hashlib.sha256(raw).hexdigest(),
                        "line_number": line_number,
                        "source_snippet": _line_snippet(lines, line_number - 1),
                        "execution_status": "active_call",
                    }
                )

    rows = [item for operator in operators for item in evidence[operator]]
    missing = [operator for operator in operators if not evidence[operator]]
    args.output_csv.parent.mkdir(parents=True, exist_ok=True)
    fields = (
        "priority",
        "operator_id",
        "sample_rank",
        "source_relative_path",
        "source_sha256",
        "line_number",
        "source_snippet",
        "execution_status",
    )
    with args.output_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, lineterminator="\n")
        writer.writeheader()
        writer.writerows(rows)
    print(
        f"operators={len(operators)} evidence_rows={len(rows)} "
        f"missing_operators={len(missing)} commented_hits={sum(commented_hits.values())}"
    )
    if missing:
        print("missing=" + ",".join(missing))
    if commented_hits:
        print("commented=" + ",".join(f"{key}:{value}" for key, value in sorted(commented_hits.items())))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
