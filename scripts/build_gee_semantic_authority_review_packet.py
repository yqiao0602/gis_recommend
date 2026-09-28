"""Build an authority-level review packet from accepted GEE semantic proposals.

This is a deterministic review artifact only.  Multiple local units from one
source SHA are grouped into one authority so proposal-row counts cannot be
mistaken for independent support.  No training rows or human approvals are
created.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_gee_strict_candidate_source_audit import (  # noqa: E402
    _atomic_write,
    _csv_text,
    _filesystem_path,
    _json_text,
    _jsonl_text,
    _load_jsonl,
    _sha256,
)


DEFAULT_INPUT = (
    ROOT
    / "docs/reports/gee_raster_core_v1_review_split_2026-07-24"
    / "gee_raster_core_batch_training_package_v1/strict_candidate_v1"
    / "semantic_pattern_census_3106_v1"
    / "gee_semantic_pattern_census_3106_v1.jsonl"
)
DEFAULT_OUTPUT_DIR = DEFAULT_INPUT.parent / "authority_review_v1"
OUTPUT_PREFIX = "gee_semantic_authority_review_3106_v1"


def _row_sort_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        int(row.get("start_line") or 0),
        int(row.get("end_line") or 0),
        str(row.get("definition_id") or ""),
    )


def _proposal_evidence(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "sample_id": row.get("sample_id"),
        "definition_id": row.get("definition_id"),
        "pattern": row.get("pattern"),
        "canonical_operator_sequence": row.get("canonical_operator_sequence", []),
        "l3_code_sequence": row.get("l3_code_sequence", []),
        "dependency_ids": row.get("dependency_ids", []),
        "semantic_facts": row.get("semantic_facts", {}),
        "source_snippet": row.get("source_snippet", ""),
    }


def build_authority_review_packet(
    rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    accepted = [
        row
        for row in rows
        if row.get("semantic_status") == "accepted_proposal"
        and str(row.get("source_sha256") or "")
    ]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in accepted:
        grouped[str(row["source_sha256"])].append(row)

    packet: list[dict[str, Any]] = []
    pattern_rows: Counter[str] = Counter()
    pattern_authorities: dict[str, set[str]] = defaultdict(set)
    representative_count = 0
    for source_sha in sorted(grouped):
        source_rows = sorted(grouped[source_sha], key=_row_sort_key)
        patterns = Counter(str(row.get("pattern") or "") for row in source_rows)
        representatives: list[dict[str, Any]] = []
        seen_patterns: set[str] = set()
        for row in source_rows:
            pattern = str(row.get("pattern") or "")
            if pattern not in seen_patterns:
                representatives.append(row)
                seen_patterns.add(pattern)
        representative_count += len(representatives)
        for pattern in patterns:
            pattern_rows[pattern] += patterns[pattern]
            pattern_authorities[pattern].add(source_sha)
        packet.append(
            {
                "schema": "gis_recommend.gee_semantic_authority_review_3106.v1",
                "authority_id": source_sha,
                "source_sha256": source_sha,
                "source_path": str(source_rows[0].get("source_path") or ""),
                "script_ids": sorted(
                    {
                        str(row.get("script_id") or "")
                        for row in source_rows
                        if str(row.get("script_id") or "")
                    }
                ),
                "proposal_count": len(source_rows),
                "pattern_counts": dict(sorted(patterns.items())),
                "patterns": sorted(patterns),
                "proposal_definition_ids": [
                    str(row.get("definition_id") or "") for row in source_rows
                ],
                "proposal_evidence": [_proposal_evidence(row) for row in source_rows],
                "representative_definition_ids": [
                    str(row.get("definition_id") or "") for row in representatives
                ],
                "representative_proposal_evidence": [
                    _proposal_evidence(row) for row in representatives
                ],
                "human_adjudication": "",
                "human_notes": "",
                "completeness_status": "",
                "training_admission": "not_granted_gee_semantic_authority_review",
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
                "training_rows_emitted": 0,
            }
        )

    summary = {
        "schema": "gis_recommend.gee_semantic_authority_review_summary.v1",
        "counts": {
            "input_rows": len(rows),
            "accepted_proposal_rows": len(accepted),
            "excluded_nonaccepted_rows": len(rows) - len(accepted),
            "independent_source_authorities": len(packet),
            "authority_pattern_representatives": representative_count,
            "training_rows_emitted": 0,
        },
        "pattern_row_counts": dict(sorted(pattern_rows.items())),
        "pattern_authority_counts": {
            key: len(values) for key, values in sorted(pattern_authorities.items())
        },
        "authority_proposal_count_distribution": dict(
            sorted(Counter(row["proposal_count"] for row in packet).items())
        ),
        "decision": {
            "status": "authority_review_packet_only",
            "human_adjudication": "not_granted",
            "training_admission": "not_granted_gee_semantic_authority_review",
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
            "next_gate": "human completeness review by independent source authority",
        },
    }
    return packet, summary


def flatten_representatives(packet: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for authority in packet:
        for evidence in authority["representative_proposal_evidence"]:
            rows.append(
                {
                    "schema": "gis_recommend.gee_semantic_authority_representative_review.v1",
                    "source_sha256": authority["source_sha256"],
                    "source_path": authority["source_path"],
                    "authority_proposal_count": authority["proposal_count"],
                    **evidence,
                    "human_completeness": "",
                    "human_fidelity": "",
                    "human_notes": "",
                    "training_admission": "not_granted_gee_semantic_authority_review",
                    "validation_eligible": False,
                    "test_eligible": False,
                    "production_merge": "not_granted",
                    "training_rows_emitted": 0,
                }
            )
    return rows


def _render_report(summary: dict[str, Any]) -> str:
    counts = summary["counts"]
    lines = [
        "# GEE Semantic Authority Review Packet 3106 v1",
        "",
        f"- Input proposal rows: {counts['input_rows']}",
        f"- Accepted proposal rows: {counts['accepted_proposal_rows']}",
        f"- Excluded non-accepted rows: {counts['excluded_nonaccepted_rows']}",
        f"- Independent source authorities: {counts['independent_source_authorities']}",
        f"- Authority-pattern representatives: {counts['authority_pattern_representatives']}",
        f"- Pattern row counts: {summary['pattern_row_counts']}",
        f"- Pattern authority counts: {summary['pattern_authority_counts']}",
        f"- Authority proposal-count distribution: {summary['authority_proposal_count_distribution']}",
        "- Human adjudication: not granted",
        "- Training rows emitted: 0",
        "",
        "Rows are grouped by source SHA. Multiple local units from one source are not independent authorities.",
    ]
    return "\n".join(lines) + "\n"


def write_outputs(
    packet: list[dict[str, Any]],
    summary: dict[str, Any],
    input_path: Path,
    output_dir: Path,
    *,
    output_prefix: str = OUTPUT_PREFIX,
) -> dict[str, Path]:
    output_dir = Path(output_dir)
    paths = {
        "jsonl": output_dir / f"{output_prefix}.jsonl",
        "representatives_jsonl": output_dir / f"{output_prefix}_representatives.jsonl",
        "representatives_csv": output_dir / f"{output_prefix}_representatives.csv",
        "summary": output_dir / f"{output_prefix}_summary.json",
        "report": output_dir / f"{output_prefix}_report.md",
        "hash_ledger": output_dir / f"{output_prefix}_hash_ledger.json",
    }
    summary = {
        **summary,
        "inputs": {
            "source_jsonl": str(input_path),
            "source_jsonl_sha256": _sha256(input_path),
        },
    }
    _atomic_write(paths["jsonl"], _jsonl_text(packet))
    representatives = flatten_representatives(packet)
    _atomic_write(paths["representatives_jsonl"], _jsonl_text(representatives))
    _atomic_write(paths["representatives_csv"], _csv_text(representatives))
    _atomic_write(paths["summary"], _json_text(summary))
    _atomic_write(paths["report"], _render_report(summary))
    ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "source_inputs": summary["inputs"],
        "artifacts": {
            path.name: {"path": str(path), "sha256": _sha256(path)}
            for key, path in paths.items()
            if key != "hash_ledger"
        },
    }
    _atomic_write(paths["hash_ledger"], _json_text(ledger))
    return paths


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-jsonl", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--output-prefix", default=OUTPUT_PREFIX)
    args = parser.parse_args(argv)
    input_path = Path(args.input_jsonl)
    rows = _load_jsonl(input_path)
    packet, summary = build_authority_review_packet(rows)
    return write_outputs(
        packet,
        summary,
        input_path,
        Path(args.output_dir),
        output_prefix=args.output_prefix,
    )


if __name__ == "__main__":
    main()
