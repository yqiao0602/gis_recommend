#!/usr/bin/env python3
"""Build the GEE P3-B deferred-row source re-extraction impact manifest.

This pass re-extracts only the P0 `extractor_repair_required` rows when
hash-verified source files and ESTree AST files are available locally. It does
not rewrite descriptions, does not export training rows, and does not grant
training/validation/test admission.
"""

from __future__ import annotations

import argparse
from collections import Counter
import csv
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path, PurePosixPath
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gis_recommend.data.gee_source_extractor import (  # noqa: E402
    EXTRACTOR_VERSION,
    extract_gee_source_evidence,
)
from scripts.audit_gee_training_admission import _atomic_write_text  # noqa: E402


DEFAULT_REVIEW_DIR = ROOT / "docs/reports/gee_raster_core_v1_review_split_2026-07-24"
DEFAULT_SALVAGE_CSV = DEFAULT_REVIEW_DIR / "gee_salvage_50_v1.csv"
DEFAULT_OUTPUT_DIR = ROOT / "docs/reports"
DEFAULT_SOURCE_DIR = ROOT / ".tmp_gee_p3b_sources_20260725"
DEFAULT_AST_DIR = ROOT / ".tmp_gee_p3b_ast_20260725"
OUTPUT_PREFIX = "gee_extractor_v2_p3b_deferred_reextract_impact_2026-07-25"
REPAIR_BUCKET = "extractor_repair_required"

FAIL_CLOSED_STATUSES = {
    "source_missing",
    "source_hash_mismatch",
    "ast_missing",
    "ast_invalid",
    "extractor_error",
}

FATAL_QUALITY_FLAGS = {
    "dynamic_callee",
    "recursive_helper",
}

CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "index_mask": (
        "normalizeddifference",
        "expression",
        "updatemask",
        ".mask",
        ".where",
        ".eq",
        ".neq",
        ".gt",
        ".gte",
        ".lt",
        ".lte",
        ".and",
        ".or",
        ".not",
        ".bitwiseand",
    ),
    "sampling_regional_statistics": (
        "sampleregions",
        ".sample",
        "reduceregion",
        "reduceregions",
        "pixelarea",
        "reducer.sum",
        "reducer.mean",
        "reducer.count",
        "reducer.frequencyhistogram",
        "reducecolumns",
    ),
    "ml_classification": (
        "classifier",
        ".train",
        ".classify",
        "confusionmatrix",
        "errormatrix",
        ".accuracy",
        ".kappa",
    ),
    "evaluation_vector_aggregation": (
        "reducetovectors",
        ".flatten",
        ".merge",
        ".union",
        ".area",
        "confusionmatrix",
        "errormatrix",
        ".accuracy",
        ".kappa",
    ),
}


@dataclass(slots=True)
class ReextractImpactResult:
    report: dict[str, Any]
    rows: list[dict[str, Any]]


def _load_csv(path: Path) -> list[dict[str, str]]:
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError(f"{path} contains no rows")
    return rows


def _json_list(value: str, *, field: str, review_id: str) -> list[str]:
    if value is None or value == "":
        return []
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid {field} JSON for {review_id}: {exc}") from exc
    if not isinstance(parsed, list) or any(not isinstance(item, str) for item in parsed):
        raise ValueError(f"{field} must be a JSON string list for {review_id}")
    return parsed


def _source_basename(source_path: str) -> str:
    return PurePosixPath(source_path).name


def _resolve_ast_path(ast_dir: Path, source_basename: str) -> Path | None:
    candidates = (
        ast_dir / f"{source_basename}.ast.json",
        ast_dir / f"{source_basename}.json",
        ast_dir / f"{Path(source_basename).stem}.ast.json",
        ast_dir / f"{Path(source_basename).stem}.json",
    )
    for candidate in candidates:
        if candidate.is_file():
            return candidate
    return None


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _normalized_operator_sequence(values: list[str]) -> list[str]:
    return [value.strip().lower() for value in values if value and value.strip()]


def _added_sequence_items(old: list[str], new: list[str]) -> list[str]:
    remaining = Counter(old)
    added: list[str] = []
    for item in new:
        if remaining[item] > 0:
            remaining[item] -= 1
        else:
            added.append(item)
    return added


def _categories_for_ops(operators: list[str]) -> list[str]:
    categories: list[str] = []
    for category, keywords in CATEGORY_KEYWORDS.items():
        if any(keyword in operator for operator in operators for keyword in keywords):
            categories.append(category)
    return categories


def _empty_impact_row(
    salvage_row: dict[str, str],
    *,
    status: str,
    old_operator_sequence: list[str],
    reason: str,
) -> dict[str, Any]:
    return {
        "review_id": salvage_row["review_id"],
        "script_id": salvage_row.get("script_id", ""),
        "source_path": salvage_row.get("source_path", ""),
        "source_sha256": salvage_row.get("source_sha256", ""),
        "reextract_status": status,
        "fail_closed_reason": reason,
        "old_operator_sequence": old_operator_sequence,
        "new_core_operator_sequence": [],
        "added_core_operators": [],
        "removed_old_operators": old_operator_sequence,
        "core_chain_changed": False,
        "quality_flags": [],
        "recovered_signal_categories": [],
        "p4_rereview_candidate": False,
        "training_admission": "not_granted",
        "salvage_reason": salvage_row.get("salvage_reason", ""),
        "evidence_grade": "none",
    }


def _impact_row_from_extraction(
    salvage_row: dict[str, str],
    *,
    source_path: Path,
    ast_path: Path,
    old_operator_sequence: list[str],
) -> dict[str, Any]:
    ast = json.loads(ast_path.read_text(encoding="utf-8"))
    evidence = extract_gee_source_evidence(
        ast,
        source_path=str(source_path),
        source_sha256=salvage_row["source_sha256"],
    )
    calls_by_ordinal = {call.ordinal: call for call in evidence.ordered_calls}
    new_core_sequence = _normalized_operator_sequence(
        [
            calls_by_ordinal[ordinal].raw_callee or ""
            for ordinal in evidence.core_operator_chain
        ]
    )
    added = _added_sequence_items(old_operator_sequence, new_core_sequence)
    removed = _added_sequence_items(new_core_sequence, old_operator_sequence)
    recovered_categories = _categories_for_ops(added)
    core_chain_changed = new_core_sequence != old_operator_sequence
    has_fatal_quality_flag = bool(FATAL_QUALITY_FLAGS.intersection(evidence.quality_flags))
    return {
        "review_id": salvage_row["review_id"],
        "script_id": salvage_row.get("script_id", ""),
        "source_path": salvage_row.get("source_path", ""),
        "source_sha256": salvage_row.get("source_sha256", ""),
        "local_source_path": str(source_path),
        "local_ast_path": str(ast_path),
        "reextract_status": "ok",
        "fail_closed_reason": "",
        "old_operator_sequence": old_operator_sequence,
        "new_core_operator_sequence": new_core_sequence,
        "added_core_operators": added,
        "removed_old_operators": removed,
        "core_chain_changed": core_chain_changed,
        "quality_flags": list(evidence.quality_flags),
        "recovered_signal_categories": recovered_categories,
        "p4_rereview_candidate": bool(core_chain_changed and recovered_categories and not has_fatal_quality_flag),
        "training_admission": "not_granted",
        "salvage_reason": salvage_row.get("salvage_reason", ""),
        "evidence_grade": "hash_verified_full_source_ast",
        "ordered_call_count": len(evidence.ordered_calls),
        "core_call_count": len(new_core_sequence),
        "io_call_count": len(evidence.io_contract),
        "presentation_call_count": len(evidence.presentation_actions),
        "support_call_count": len(evidence.support_calls),
        "unresolved_call_count": len(evidence.unresolved_calls),
    }


def build_deferred_reextract_impact(
    *,
    salvage_csv_path: Path,
    source_dir: Path,
    ast_dir: Path,
) -> ReextractImpactResult:
    salvage_rows = _load_csv(salvage_csv_path)
    repair_rows = [row for row in salvage_rows if row.get("salvage_bucket") == REPAIR_BUCKET]
    if not repair_rows:
        raise ValueError(f"no {REPAIR_BUCKET} rows in {salvage_csv_path}")

    rows: list[dict[str, Any]] = []
    status_counter: Counter[str] = Counter()
    category_counter: Counter[str] = Counter()
    source_dir = Path(source_dir)
    ast_dir = Path(ast_dir)

    for salvage_row in sorted(repair_rows, key=lambda item: item["review_id"]):
        review_id = salvage_row["review_id"]
        old_sequence = _normalized_operator_sequence(
            _json_list(salvage_row.get("operator_sequence_json", ""), field="operator_sequence_json", review_id=review_id)
        )
        source_basename = _source_basename(salvage_row.get("source_path", ""))
        local_source_path = source_dir / source_basename
        if not local_source_path.is_file():
            row = _empty_impact_row(
                salvage_row,
                status="source_missing",
                old_operator_sequence=old_sequence,
                reason=f"local source file not found: {local_source_path}",
            )
            rows.append(row)
            status_counter[row["reextract_status"]] += 1
            continue

        actual_hash = _sha256(local_source_path)
        if actual_hash != salvage_row.get("source_sha256"):
            row = _empty_impact_row(
                salvage_row,
                status="source_hash_mismatch",
                old_operator_sequence=old_sequence,
                reason=f"expected {salvage_row.get('source_sha256')}, got {actual_hash}",
            )
            row["local_source_path"] = str(local_source_path)
            rows.append(row)
            status_counter[row["reextract_status"]] += 1
            continue

        local_ast_path = _resolve_ast_path(ast_dir, source_basename)
        if local_ast_path is None:
            row = _empty_impact_row(
                salvage_row,
                status="ast_missing",
                old_operator_sequence=old_sequence,
                reason=f"AST file not found for {source_basename} in {ast_dir}",
            )
            row["local_source_path"] = str(local_source_path)
            row["evidence_grade"] = "hash_verified_source_only"
            rows.append(row)
            status_counter[row["reextract_status"]] += 1
            continue

        try:
            row = _impact_row_from_extraction(
                salvage_row,
                source_path=local_source_path,
                ast_path=local_ast_path,
                old_operator_sequence=old_sequence,
            )
        except json.JSONDecodeError as exc:
            row = _empty_impact_row(
                salvage_row,
                status="ast_invalid",
                old_operator_sequence=old_sequence,
                reason=str(exc),
            )
            row["local_source_path"] = str(local_source_path)
            row["local_ast_path"] = str(local_ast_path)
            row["evidence_grade"] = "hash_verified_source_invalid_ast"
        except Exception as exc:  # fail closed: this report is diagnostic, not training authority.
            row = _empty_impact_row(
                salvage_row,
                status="extractor_error",
                old_operator_sequence=old_sequence,
                reason=f"{type(exc).__name__}: {exc}",
            )
            row["local_source_path"] = str(local_source_path)
            row["local_ast_path"] = str(local_ast_path)
            row["evidence_grade"] = "hash_verified_source_ast_extractor_failed"

        rows.append(row)
        status_counter[row["reextract_status"]] += 1
        category_counter.update(row["recovered_signal_categories"])

    p4_candidate_count = sum(bool(row["p4_rereview_candidate"]) for row in rows)
    fail_closed_count = sum(status_counter[status] for status in FAIL_CLOSED_STATUSES)
    extraction_ok_count = status_counter["ok"]
    if p4_candidate_count:
        next_gate = "P4 human rereview of p4_rereview_candidate rows; no automatic admission"
    elif fail_closed_count and not extraction_ok_count:
        next_gate = "resolve fail-closed source/AST inputs and rerun P3-B before P4"
    elif extraction_ok_count:
        next_gate = "inspect non-candidate extraction output before P4; no automatic admission"
    else:
        next_gate = "rerun P3-B with valid repair rows"

    report = {
        "schema": "gis_recommend.gee_p3b_deferred_reextract_impact.v1",
        "date": "2026-07-25",
        "extractor_version": EXTRACTOR_VERSION,
        "inputs": {
            "salvage_csv": str(Path(salvage_csv_path)),
            "source_dir": str(source_dir),
            "ast_dir": str(ast_dir),
        },
        "counts": {
            "repair_rows": len(rows),
            "hash_verified_rows": sum(row["evidence_grade"].startswith("hash_verified") for row in rows),
            "extraction_ok_rows": extraction_ok_count,
            "fail_closed_rows": fail_closed_count,
            "core_chain_changed_rows": sum(bool(row["core_chain_changed"]) for row in rows),
            "p4_rereview_candidates": p4_candidate_count,
        },
        "statuses": dict(sorted(status_counter.items())),
        "recovered_signal_categories": dict(sorted(category_counter.items())),
        "decision": {
            "training_admission": "not_granted",
            "validation_eligible": False,
            "test_eligible": False,
            "next_gate": next_gate,
        },
        "policy": {
            "llm_used": False,
            "operator_chain_source": "v2.0.3 deterministic extractor over hash-verified full source AST",
            "fail_closed_on_missing_source_or_ast": True,
            "p4_candidate_is_not_training_admission": True,
        },
    }
    return ReextractImpactResult(report=report, rows=rows)


def _jsonl_text(rows: list[dict[str, Any]]) -> str:
    return "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for row in rows
    )


def _csv_value(value: Any) -> Any:
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError("cannot write empty P3-B impact CSV")
    fieldnames = [
        "review_id",
        "script_id",
        "reextract_status",
        "evidence_grade",
        "p4_rereview_candidate",
        "core_chain_changed",
        "recovered_signal_categories",
        "old_operator_sequence",
        "new_core_operator_sequence",
        "added_core_operators",
        "removed_old_operators",
        "quality_flags",
        "ordered_call_count",
        "core_call_count",
        "io_call_count",
        "presentation_call_count",
        "support_call_count",
        "unresolved_call_count",
        "fail_closed_reason",
        "source_sha256",
        "source_path",
        "local_source_path",
        "local_ast_path",
        "training_admission",
        "salvage_reason",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field, "")) for field in fieldnames})


def _render_markdown(report: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    lines = [
        "# GEE P3-B Deferred Re-extraction Impact",
        "",
        "This report re-extracts the 28 P0 rows marked `extractor_repair_required`",
        "with the deterministic GEE source extractor. It is an impact manifest only:",
        "P4 human rereview is still required, and no row receives training admission here.",
        "",
        "## Summary",
        "",
        f"- Extractor version: `{report['extractor_version']}`",
        f"- Repair rows: {report['counts']['repair_rows']}",
        f"- Hash-verified rows: {report['counts']['hash_verified_rows']}",
        f"- Extraction OK rows: {report['counts']['extraction_ok_rows']}",
        f"- Fail-closed rows: {report['counts']['fail_closed_rows']}",
        f"- Core-chain changed rows: {report['counts']['core_chain_changed_rows']}",
        f"- P4 rereview candidates: {report['counts']['p4_rereview_candidates']}",
        f"- Training admission: `{report['decision']['training_admission']}`",
        f"- Next gate: {report['decision']['next_gate']}",
        "",
        "## Re-extraction statuses",
        "",
    ]
    for status, count in report["statuses"].items():
        lines.append(f"- `{status}`: {count}")
    lines.extend([
        "",
        "## Recovered signal categories",
        "",
    ])
    if report["recovered_signal_categories"]:
        for category, count in report["recovered_signal_categories"].items():
            lines.append(f"- `{category}`: {count}")
    else:
        lines.append("- None")
    lines.extend(["", "## P4 rereview candidates", ""])
    candidates = [row for row in rows if row["p4_rereview_candidate"]]
    if not candidates:
        lines.append("- None")
        lines.append("")
    for row in candidates:
        lines.extend(
            [
                f"### {row['review_id']}",
                "",
                f"- Categories: {', '.join(row['recovered_signal_categories'])}",
                f"- Added operators: `{ ' > '.join(row['added_core_operators'][:20]) }`",
                f"- Quality flags: `{ ', '.join(row['quality_flags']) }`",
                "",
            ]
        )
    lines.extend(
        [
            "## Guardrail",
            "",
            "`p4_rereview_candidate=true` only means the deterministic extractor now",
            "recovers additional source-grounded core calls. It does not mean the row is",
            "complete, task-text faithful, mapped to L3, or eligible for train/val/test.",
            "",
        ]
    )
    return "\n".join(lines)


def write_outputs(
    result: ReextractImpactResult,
    output_dir: Path,
    *,
    output_prefix: str = OUTPUT_PREFIX,
) -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / f"{output_prefix}.csv"
    jsonl_path = output_dir / f"{output_prefix}.jsonl"
    summary_path = output_dir / f"{output_prefix}.json"
    report_path = output_dir / f"{output_prefix}.md"
    hash_ledger_path = output_dir / f"{output_prefix}_hash_ledger.json"

    _write_csv(csv_path, result.rows)
    _atomic_write_text(jsonl_path, _jsonl_text(result.rows))
    _atomic_write_text(summary_path, json.dumps(result.report, ensure_ascii=False, indent=2, sort_keys=True))
    _atomic_write_text(report_path, _render_markdown(result.report, result.rows))

    ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "source_inputs": {
            "salvage_csv": {
                "path": result.report["inputs"]["salvage_csv"],
                "sha256": _sha256(Path(result.report["inputs"]["salvage_csv"])),
            },
            "source_dir": result.report["inputs"]["source_dir"],
            "ast_dir": result.report["inputs"]["ast_dir"],
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
    parser.add_argument("--salvage-csv", type=Path, default=DEFAULT_SALVAGE_CSV)
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--ast-dir", type=Path, default=DEFAULT_AST_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--output-prefix", default=OUTPUT_PREFIX)
    args = parser.parse_args(argv)
    result = build_deferred_reextract_impact(
        salvage_csv_path=args.salvage_csv,
        source_dir=args.source_dir,
        ast_dir=args.ast_dir,
    )
    return write_outputs(result, args.output_dir, output_prefix=args.output_prefix)


if __name__ == "__main__":
    main()
