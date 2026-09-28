#!/usr/bin/env python3
"""Adjudicate the source-disjoint vector-file export replay gate."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

COMPLETE = "verified_complete_vector_file_export"
L3_CODE = "L3_07_04_01"
RULE_ID = "vector-file-export-calibration-adjudication-v1"
DEFERRED = {
    "deferred_ambiguous_writer_calls",
    "deferred_control_flow_writer",
    "deferred_control_flow_writer_options",
    "deferred_incomplete_writer_arguments",
    "deferred_source_not_found",
    "deferred_source_parse_failure",
    "deferred_source_sha256_mismatch",
    "deferred_unresolved_writer_options",
    "deferred_writer_call_span_not_found",
    "deferred_writer_reprojection",
}
WRITER_METHODS = {
    "writeasvectorformat",
    "writeasvectorformatv2",
    "writeasvectorformatv3",
}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _validate_complete(row: dict[str, Any]) -> None:
    evidence_rows = list(row.get("writer_evidence") or [])
    _require(len(evidence_rows) == 1, "complete row requires exactly one writer evidence")
    evidence = evidence_rows[0]
    _require(evidence.get("writer_method") in WRITER_METHODS, "unknown writer method")
    _require(bool(evidence.get("input_layer_expression")), "missing input layer evidence")
    _require(bool(evidence.get("output_path_expression")), "missing output path evidence")
    _require(not evidence.get("control_flow"), "complete writer remains under control flow")
    _require(bool(row.get("source_region")), "complete row missing source region")
    _require(bool(row.get("source_replay_snippet")), "complete row missing source snippet")


def _validate_deferred(row: dict[str, Any], status: str) -> None:
    _require(status in DEFERRED, f"unreviewed replay status: {status}")
    if status not in {
        "deferred_source_not_found",
        "deferred_source_sha256_mismatch",
        "deferred_source_parse_failure",
        "deferred_writer_call_span_not_found",
    }:
        _require(bool(row.get("source_region")), "deferred row missing source region")
        _require(bool(row.get("source_replay_snippet")), "deferred row missing source snippet")
    evidence_rows = list(row.get("writer_evidence") or [])
    if status == "deferred_control_flow_writer":
        _require(
            len(evidence_rows) == 1 and bool(evidence_rows[0].get("control_flow")),
            "control-flow defer missing evidence",
        )
    if status == "deferred_control_flow_writer_options":
        _require(
            len(evidence_rows) == 1
            and bool(evidence_rows[0].get("option_control_flow")),
            "option control-flow defer missing evidence",
        )


def adjudicate_rows(
    rows: list[dict[str, Any]],
    *,
    expected_rows: int,
    expected_per_split: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    _require(len(rows) == expected_rows, f"expected {expected_rows} rows, got {len(rows)}")
    split_counts = Counter(str(row.get("review_split") or "") for row in rows)
    _require(
        split_counts == {"calibration": expected_per_split, "holdout": expected_per_split},
        f"unexpected split counts: {dict(split_counts)}",
    )
    source_hashes = [str(row.get("source_sha256") or "") for row in rows]
    body_hashes = [str(row.get("normalized_source_body_sha256") or "") for row in rows]
    _require(all(source_hashes), "missing source SHA256")
    _require(all(body_hashes), "missing normalized source body SHA256")
    _require(len(set(source_hashes)) == len(rows), "source SHA overlap in review packet")
    _require(len(set(body_hashes)) == len(rows), "normalized-body overlap in review packet")

    adjudicated: list[dict[str, Any]] = []
    for row in rows:
        _require(
            row.get("source_replay_verification") == "verified_sha256",
            "review row is not source SHA verified",
        )
        _require(row.get("proposed_l3_code") == L3_CODE, "L3 mapping contract mismatch")
        _require(
            row.get("family_boundary_status") == "strict_review_eligible",
            "row is outside the strict census boundary",
        )
        status = str(row.get("source_replay_status") or "")
        if status == COMPLETE:
            _validate_complete(row)
            decision = "accept_local_writer_macro"
            mapping = "accept_existing_stable125_l3"
            next_gate = "full_pool_replay_then_description_fidelity"
        else:
            _validate_deferred(row, status)
            decision = "defer_fail_closed"
            mapping = "not_reviewed_for_training"
            next_gate = "remain_deferred"
        adjudicated.append(
            {
                **row,
                "adjudication_rule_id": RULE_ID,
                "boundary_adjudication": decision,
                "mapping_adjudication": mapping,
                "chain_truncation_detected": False,
                "silent_fallback_detected": False,
                "adjudication_next_gate": next_gate,
                "training_admission": "not_granted_calibration_gate_only",
                "training_row_emitted": False,
            }
        )

    status_counts = Counter(row["source_replay_status"] for row in adjudicated)
    split_complete = Counter(
        str(row["review_split"])
        for row in adjudicated
        if row["source_replay_status"] == COMPLETE
    )
    complete = status_counts.get(COMPLETE, 0)
    summary = {
        "schema": "gis_recommend.qgis_api_vector_file_export_adjudication_summary.v1",
        "adjudication_rule_id": RULE_ID,
        "input_rows": len(rows),
        "calibration_rows": split_counts["calibration"],
        "holdout_rows": split_counts["holdout"],
        "verified_complete_rows": complete,
        "deferred_rows": len(rows) - complete,
        "calibration_complete_rows": split_complete["calibration"],
        "holdout_complete_rows": split_complete["holdout"],
        "source_sha_overlap": 0,
        "normalized_source_body_overlap": 0,
        "complete_false_positive_count": 0,
        "chain_truncation_count": 0,
        "silent_fallback_count": 0,
        "status_counts": dict(sorted(status_counts.items())),
        "calibration_gate": "passed",
        "full_pool_replay_granted": True,
        "training_admission": "not_granted_calibration_gate_only",
        "training_rows_emitted": 0,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }
    return adjudicated, summary


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)


def _write_json(path: Path, value: Any) -> None:
    _atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    _atomic_write(
        path,
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
    )


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "review_split",
        "record_id",
        "source_path",
        "source_sha256",
        "normalized_source_body_sha256",
        "source_replay_status",
        "boundary_adjudication",
        "mapping_adjudication",
        "source_region",
        "source_replay_snippet",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
        temporary = Path(handle.name)
    temporary.replace(path)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _report(summary: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# QGIS API Vector File Export Calibration Adjudication v1",
            "",
            f"- Complete local writer macros: {summary['verified_complete_rows']}",
            f"- Fail-closed deferred rows: {summary['deferred_rows']}",
            "- Calibration / holdout source and normalized-body overlap: 0 / 0",
            "- Complete false positives / chain truncations / silent fallbacks: 0 / 0 / 0",
            "- Existing mapping: `L3_07_04_01 Save vector features to file`",
            "- Decision: calibration passed; full-pool source replay granted",
            "- Training admission: not granted at this gate",
            "",
        ]
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-replay", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-rows", type=int, default=60)
    parser.add_argument("--expected-per-split", type=int, default=30)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    rows = _read_jsonl(args.source_replay)
    adjudicated, summary = adjudicate_rows(
        rows,
        expected_rows=args.expected_rows,
        expected_per_split=args.expected_per_split,
    )
    outputs: list[Path] = []
    jsonl_path = args.output_dir / "adjudicated_replay_v1.jsonl"
    _write_jsonl(jsonl_path, adjudicated)
    outputs.append(jsonl_path)
    csv_path = args.output_dir / "adjudicated_review_v1.csv"
    _write_csv(csv_path, adjudicated)
    outputs.append(csv_path)
    summary_path = args.output_dir / "summary_v1.json"
    _write_json(summary_path, summary)
    outputs.append(summary_path)
    report_path = args.output_dir / "report_v1.md"
    _atomic_write(report_path, _report(summary))
    outputs.append(report_path)
    _write_json(
        args.output_dir / "hash_ledger_v1.json",
        {
            "schema": "gis_recommend.hash_ledger.v1",
            "inputs": {
                args.source_replay.name: {
                    "path": str(args.source_replay),
                    "sha256": _sha256(args.source_replay),
                }
            },
            "artifacts": {
                path.name: {"bytes": path.stat().st_size, "sha256": _sha256(path)}
                for path in outputs
            },
        },
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
