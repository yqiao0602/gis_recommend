#!/usr/bin/env python3
"""Scan de-duplicated QGIS sources for bounded conditional Processing paths."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from gis_recommend.data.qgis_conditional_paths import (
    MATCHER_VERSION,
    discover_conditional_passthrough_units,
)


HUMAN_FIELDS = (
    "human_dependency_correct",
    "human_operator_order_correct",
    "human_boundary_correct",
    "human_branch_semantics_recoverable",
    "human_final_decision",
    "human_notes",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _unit_id(content_sha: str, unit: dict[str, Any]) -> str:
    payload = {
        "content_sha256": content_sha,
        "lexical_scope": unit["lexical_scope"],
        "call_sites": unit["call_sites"],
        "paths": unit["paths"],
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return "conditional_" + hashlib.sha256(encoded.encode("utf-8")).hexdigest()[:20]


def _source_snippet(path: Path, call_sites: list[dict[str, Any]]) -> str:
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    start = max(1, min(int(site["line_start"]) for site in call_sites) - 5)
    end = min(
        len(lines),
        max(int(site.get("line_end") or site["line_start"]) for site in call_sites)
        + 5,
    )
    return "\n".join(
        f"{line_number}: {lines[line_number - 1]}"
        for line_number in range(start, end + 1)
    )


def scan_authority_rows(
    manifest_rows: Iterable[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    seen_content: set[str] = set()
    manifest_count = 0
    candidate_count = 0
    verified_count = 0
    failures: Counter[str] = Counter()
    matched: list[dict[str, Any]] = []

    for row in manifest_rows:
        manifest_count += 1
        content_sha = str(row.get("content_sha256") or "")
        if not content_sha or content_sha in seen_content:
            continue
        seen_content.add(content_sha)
        literal_ids = [
            str(operator_id).strip().lower()
            for operator_id in row.get("literal_operator_ids") or []
            if str(operator_id).strip()
        ]
        if row.get("parse_status") != "parsed" or len(literal_ids) < 2:
            continue
        candidate_count += 1
        source_path = Path(str(row.get("source_path") or ""))
        if not source_path.is_file():
            failures["source_file_missing"] += 1
            continue
        if _sha256(source_path) != content_sha:
            failures["source_sha256_mismatch"] += 1
            continue
        verified_count += 1
        source_text = source_path.read_text(encoding="utf-8", errors="replace")
        units = discover_conditional_passthrough_units(source_text)
        for unit in units:
            matched.append(
                {
                    **unit,
                    "schema": "gis_recommend.qgis_conditional_path_source_census.v1",
                    "unit_id": _unit_id(content_sha, unit),
                    "content_sha256": content_sha,
                    "source_path": str(source_path),
                    "source_root_id": str(row.get("source_root_id") or ""),
                    "relative_path": str(row.get("relative_path") or ""),
                    "source_snippet": _source_snippet(source_path, unit["call_sites"]),
                    "proposal_only": True,
                    "human_adjudication": False,
                    "review_status": "pending_human_rule_audit",
                    "training_admission": "not_granted_rule_census_only",
                    "training_row_emitted": False,
                    "validation_eligible": False,
                    "test_eligible": False,
                    "production_merge": "not_granted",
                    **{field: "" for field in HUMAN_FIELDS},
                }
            )

    source_support = len({row["content_sha256"] for row in matched})
    summary = {
        "schema": "gis_recommend.qgis_conditional_path_source_census_summary.v1",
        "matcher_version": MATCHER_VERSION,
        "manifest_rows": manifest_count,
        "unique_content_rows": len(seen_content),
        "candidate_source_authorities": candidate_count,
        "verified_candidate_source_authorities": verified_count,
        "matched_source_authorities": source_support,
        "matched_units": len(matched),
        "matched_source_roots": dict(
            sorted(Counter(row["source_root_id"] for row in matched).items())
        ),
        "provider_type_status_counts": dict(
            sorted(
                Counter(
                    str(row.get("provider_input_type_status") or "not_applicable")
                    for row in matched
                ).items()
            )
        ),
        "path_count_distribution": dict(
            sorted(Counter(len(row["paths"]) for row in matched).items())
        ),
        "failures": dict(sorted(failures.items())),
        "decision": {
            "source_support_threshold_met": source_support >= 30,
            "human_rule_audit_required": True,
            "training_admission": "not_granted",
            "training_rows_emitted": 0,
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
        },
    }
    return matched, summary


def _load_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def write_outputs(
    units: list[dict[str, Any]],
    summary: dict[str, Any],
    *,
    manifest_path: Path,
    output_dir: Path,
) -> dict[str, Path]:
    units_path = output_dir / "matched_units.jsonl"
    summary_path = output_dir / "summary.json"
    report_path = output_dir / "README.md"
    hash_path = output_dir / "hash_manifest.json"
    _atomic_write(
        units_path,
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
            for row in units
        ),
    )
    _atomic_write(
        summary_path,
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    _atomic_write(
        report_path,
        "# QGIS Full-Source Conditional Path Census\n\n"
        f"- Manifest rows: {summary['manifest_rows']}\n"
        f"- Unique content rows: {summary['unique_content_rows']}\n"
        f"- Multi-call candidate authorities: {summary['candidate_source_authorities']}\n"
        f"- Matched source authorities: {summary['matched_source_authorities']}\n"
        f"- Matched units: {summary['matched_units']}\n"
        "- Human audit: required\n"
        "- Training rows emitted: 0\n",
    )
    _atomic_write(
        hash_path,
        json.dumps(
            {
                "schema": "gis_recommend.qgis_conditional_path_source_census_hashes.v1",
                "inputs": {str(manifest_path): _sha256(manifest_path)},
                "outputs": {
                    path.name: _sha256(path)
                    for path in (units_path, summary_path, report_path)
                },
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
    return {
        "units": units_path,
        "summary": summary_path,
        "report": report_path,
        "hash": hash_path,
    }


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    units, summary = scan_authority_rows(_load_jsonl(args.manifest))
    return write_outputs(
        units, summary, manifest_path=args.manifest, output_dir=args.output_dir
    )


if __name__ == "__main__":
    main()
