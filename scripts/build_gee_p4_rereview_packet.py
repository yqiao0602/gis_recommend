#!/usr/bin/env python3
"""Build a P4 human rereview packet from GEE P3-B re-extraction candidates."""

from __future__ import annotations

import argparse
from collections import Counter
import csv
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.audit_gee_training_admission import _atomic_write_text  # noqa: E402


DEFAULT_REPORT_ROOT = ROOT / "docs/reports"
DEFAULT_REVIEW_DIR = DEFAULT_REPORT_ROOT / "gee_raster_core_v1_review_split_2026-07-24"
DEFAULT_P3B_JSONL = DEFAULT_REPORT_ROOT / "gee_extractor_v2_p3b_deferred_reextract_impact_2026-07-25.jsonl"
DEFAULT_SALVAGE_CSV = DEFAULT_REVIEW_DIR / "gee_salvage_50_v1.csv"
DEFAULT_SOURCE_SNIPPETS = DEFAULT_REVIEW_DIR / "source_evidence_snippets.jsonl"
OUTPUT_PREFIX = "gee_p4_rereview_packet_28_v1"


@dataclass(slots=True)
class P4RereviewPacketResult:
    report: dict[str, Any]
    rows: list[dict[str, Any]]


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path} line {line_number} must contain a JSON object")
            rows.append(value)
    if not rows:
        raise ValueError(f"{path} contains no rows")
    return rows


def _load_csv_by_review_id(path: Path) -> dict[str, dict[str, str]]:
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"{path} contains no rows")
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        review_id = row.get("review_id") or ""
        if not review_id:
            raise ValueError(f"missing review_id in {path}")
        if review_id in result:
            raise ValueError(f"duplicate review_id in {path}: {review_id}")
        result[review_id] = row
    return result


def _load_snippets(path: Path) -> dict[str, str]:
    snippets: dict[str, str] = {}
    for record in _load_jsonl(path):
        review_id = str(record.get("review_id") or "")
        evidence_lines = record.get("evidence_lines") or []
        if not review_id:
            raise ValueError(f"missing review_id in {path}")
        snippets[review_id] = "\n".join(
            f"{item.get('line')}: {item.get('text')}"
            for item in evidence_lines[:30]
            if isinstance(item, dict)
        ).strip()
    return snippets


def _json_list_from_csv(value: str, *, field: str, review_id: str) -> list[str]:
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid {field} JSON for {review_id}: {exc}") from exc
    if not isinstance(parsed, list) or any(not isinstance(item, str) for item in parsed):
        raise ValueError(f"{field} must be a JSON string list for {review_id}")
    return parsed


def build_p4_rereview_packet(
    *,
    p3b_jsonl_path: Path,
    salvage_csv_path: Path,
    source_snippets_path: Path,
) -> P4RereviewPacketResult:
    p3b_rows = _load_jsonl(p3b_jsonl_path)
    salvage_by_id = _load_csv_by_review_id(salvage_csv_path)
    snippets = _load_snippets(source_snippets_path)
    candidates = [row for row in p3b_rows if row.get("p4_rereview_candidate") is True]
    if not candidates:
        raise ValueError("P3-B contains no p4_rereview_candidate rows")

    rows: list[dict[str, Any]] = []
    category_counter: Counter[str] = Counter()
    quality_counter: Counter[str] = Counter()
    for p3b_row in sorted(candidates, key=lambda item: item["review_id"]):
        review_id = str(p3b_row["review_id"])
        if review_id not in salvage_by_id:
            raise ValueError(f"missing salvage row for {review_id}")
        if review_id not in snippets:
            raise ValueError(f"missing source evidence snippet for {review_id}")
        salvage = salvage_by_id[review_id]
        categories = list(p3b_row.get("recovered_signal_categories") or [])
        quality_flags = list(p3b_row.get("quality_flags") or [])
        category_counter.update(categories)
        quality_counter.update(quality_flags)
        rows.append(
            {
                "review_id": review_id,
                "script_id": p3b_row.get("script_id", ""),
                "review_split": salvage.get("split", ""),
                "source_sha256": p3b_row.get("source_sha256", ""),
                "source_path": p3b_row.get("source_path", ""),
                "task_type": salvage.get("task_type", ""),
                "task_name": salvage.get("task_name", ""),
                "task_description": salvage.get("task_description", ""),
                "old_l3_sequence": _json_list_from_csv(
                    salvage.get("l3_codes_json", "[]"),
                    field="l3_codes_json",
                    review_id=review_id,
                ),
                "old_operator_sequence": list(p3b_row.get("old_operator_sequence") or []),
                "new_core_operator_sequence": list(p3b_row.get("new_core_operator_sequence") or []),
                "added_core_operators": list(p3b_row.get("added_core_operators") or []),
                "removed_old_operators": list(p3b_row.get("removed_old_operators") or []),
                "recovered_signal_categories": categories,
                "quality_flags": quality_flags,
                "ordered_call_count": p3b_row.get("ordered_call_count", 0),
                "core_call_count": p3b_row.get("core_call_count", 0),
                "support_call_count": p3b_row.get("support_call_count", 0),
                "io_call_count": p3b_row.get("io_call_count", 0),
                "presentation_call_count": p3b_row.get("presentation_call_count", 0),
                "unresolved_call_count": p3b_row.get("unresolved_call_count", 0),
                "evidence_grade": p3b_row.get("evidence_grade", ""),
                "salvage_reason": p3b_row.get("salvage_reason", salvage.get("salvage_reason", "")),
                "evidence_snippet": snippets[review_id],
                "training_admission": "not_granted_pending_p4_human_review",
                "validation_eligible": False,
                "test_eligible": False,
                "human_task_text_faithful_to_new_chain": "",
                "human_new_chain_correct": "",
                "human_new_chain_complete_for_core_subworkflow": "",
                "human_should_enter_train_only": "",
                "human_known_omissions": "",
                "human_review_notes": "",
            }
        )

    report = {
        "schema": "gis_recommend.gee_p4_rereview_packet.v1",
        "inputs": {
            "p3b_jsonl": str(Path(p3b_jsonl_path)),
            "salvage_csv": str(Path(salvage_csv_path)),
            "source_snippets": str(Path(source_snippets_path)),
        },
        "counts": {
            "p4_candidate_rows": len(rows),
            "unique_sources": len({row["source_sha256"] for row in rows}),
            "category_counts": dict(sorted(category_counter.items())),
            "quality_flag_counts": dict(sorted(quality_counter.items())),
        },
        "decision": {
            "training_admission": "not_granted_pending_p4_human_review",
            "validation_eligible": False,
            "test_eligible": False,
            "next_gate": "human P4 rereview of new source-extracted chains",
        },
        "policy": {
            "llm_used": False,
            "training_rows_emitted": False,
            "operator_chain_source": "P3-B deterministic source re-extraction",
            "human_fields_blank": True,
        },
    }
    return P4RereviewPacketResult(report=report, rows=rows)


def _csv_value(value: Any) -> Any:
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError("cannot write empty P4 rereview CSV")
    fieldnames = [
        "review_id",
        "script_id",
        "review_split",
        "source_sha256",
        "source_path",
        "task_type",
        "task_name",
        "task_description",
        "old_l3_sequence",
        "old_operator_sequence",
        "new_core_operator_sequence",
        "added_core_operators",
        "removed_old_operators",
        "recovered_signal_categories",
        "quality_flags",
        "ordered_call_count",
        "core_call_count",
        "support_call_count",
        "io_call_count",
        "presentation_call_count",
        "unresolved_call_count",
        "evidence_grade",
        "salvage_reason",
        "evidence_snippet",
        "training_admission",
        "validation_eligible",
        "test_eligible",
        "human_task_text_faithful_to_new_chain",
        "human_new_chain_correct",
        "human_new_chain_complete_for_core_subworkflow",
        "human_should_enter_train_only",
        "human_known_omissions",
        "human_review_notes",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field, "")) for field in fieldnames})


def _jsonl_text(rows: list[dict[str, Any]]) -> str:
    return "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for row in rows
    )


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _render_markdown(report: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    lines = [
        "# GEE P4 Rereview Packet",
        "",
        "Human rereview packet for P3-B source-reextracted GEE deferred rows.",
        "This packet emits no training rows and grants no validation/test admission.",
        "",
        "## Summary",
        "",
        f"- Rows: {report['counts']['p4_candidate_rows']}",
        f"- Unique sources: {report['counts']['unique_sources']}",
        f"- Training admission: `{report['decision']['training_admission']}`",
        f"- Validation eligible: `{report['decision']['validation_eligible']}`",
        f"- Test eligible: `{report['decision']['test_eligible']}`",
        "",
        "## Category counts",
        "",
    ]
    for category, count in report["counts"]["category_counts"].items():
        lines.append(f"- `{category}`: {count}")
    lines.extend(["", "## Review fields", ""])
    lines.append(
        "Reviewers must fill `human_task_text_faithful_to_new_chain`, "
        "`human_new_chain_correct`, `human_new_chain_complete_for_core_subworkflow`, "
        "`human_should_enter_train_only`, `human_known_omissions`, and `human_review_notes`."
    )
    lines.extend(["", "## Rows", ""])
    for row in rows:
        lines.extend(
            [
                f"### {row['review_id']}",
                "",
                f"- Categories: {', '.join(row['recovered_signal_categories'])}",
                f"- Quality flags: {', '.join(row['quality_flags'])}",
                f"- Core calls: {row['core_call_count']} / ordered calls: {row['ordered_call_count']}",
                "",
            ]
        )
    return "\n".join(lines)


def write_outputs(
    result: P4RereviewPacketResult,
    output_dir: Path,
    *,
    output_prefix: str = OUTPUT_PREFIX,
) -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / f"{output_prefix}.csv"
    jsonl_path = output_dir / f"{output_prefix}.jsonl"
    summary_path = output_dir / f"{output_prefix}_summary.json"
    report_path = output_dir / f"{output_prefix}_report.md"
    hash_ledger_path = output_dir / f"{output_prefix}_hash_ledger.json"

    _write_csv(csv_path, result.rows)
    _atomic_write_text(jsonl_path, _jsonl_text(result.rows))
    _atomic_write_text(summary_path, json.dumps(result.report, ensure_ascii=False, indent=2, sort_keys=True))
    _atomic_write_text(report_path, _render_markdown(result.report, result.rows))
    ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "source_inputs": {
            "p3b_jsonl": {
                "path": result.report["inputs"]["p3b_jsonl"],
                "sha256": _sha256(Path(result.report["inputs"]["p3b_jsonl"])),
            },
            "salvage_csv": {
                "path": result.report["inputs"]["salvage_csv"],
                "sha256": _sha256(Path(result.report["inputs"]["salvage_csv"])),
            },
            "source_snippets": {
                "path": result.report["inputs"]["source_snippets"],
                "sha256": _sha256(Path(result.report["inputs"]["source_snippets"])),
            },
        },
        "artifacts": {
            csv_path.name: {"path": str(csv_path), "sha256": _sha256(csv_path), "bytes": csv_path.stat().st_size},
            jsonl_path.name: {"path": str(jsonl_path), "sha256": _sha256(jsonl_path), "bytes": jsonl_path.stat().st_size},
            summary_path.name: {"path": str(summary_path), "sha256": _sha256(summary_path), "bytes": summary_path.stat().st_size},
            report_path.name: {"path": str(report_path), "sha256": _sha256(report_path), "bytes": report_path.stat().st_size},
        },
    }
    _atomic_write_text(hash_ledger_path, json.dumps(ledger, ensure_ascii=False, indent=2, sort_keys=True))
    return {
        "csv": csv_path,
        "jsonl": jsonl_path,
        "summary": summary_path,
        "report": report_path,
        "hash_ledger": hash_ledger_path,
    }


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--p3b-jsonl", type=Path, default=DEFAULT_P3B_JSONL)
    parser.add_argument("--salvage-csv", type=Path, default=DEFAULT_SALVAGE_CSV)
    parser.add_argument("--source-snippets", type=Path, default=DEFAULT_SOURCE_SNIPPETS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_REVIEW_DIR)
    parser.add_argument("--output-prefix", default=OUTPUT_PREFIX)
    args = parser.parse_args(argv)
    result = build_p4_rereview_packet(
        p3b_jsonl_path=args.p3b_jsonl,
        salvage_csv_path=args.salvage_csv,
        source_snippets_path=args.source_snippets,
    )
    return write_outputs(result, args.output_dir, output_prefix=args.output_prefix)


if __name__ == "__main__":
    main()
