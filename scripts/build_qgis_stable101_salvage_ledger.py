#!/usr/bin/env python3
"""Build a deterministic salvage ledger for the stable101 QGIS review pack.

This pass classifies review rows for follow-up work. It does not call an LLM,
modify the source review package, modify outputs_v2, or grant training admission.
"""

from __future__ import annotations

import argparse
from collections import Counter
import csv
import hashlib
import json
from pathlib import Path
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REVIEW_CSV = (
    ROOT
    / "docs/reports/qgis_mapping_high_impact_blockers_2026-07-24"
    / "stable101_source_review_50_v1/stable101_source_review_50_v1.csv"
)
DEFAULT_ADJUDICATIONS = (
    ROOT
    / "docs/reports/qgis_mapping_high_impact_blockers_2026-07-24"
    / "stable101_source_review_50_v1"
    / "stable101_source_review_50_adjudications_v1.jsonl"
)
DEFAULT_OUTPUT_DIR = DEFAULT_REVIEW_CSV.parent

CLASS_ORDER = (
    "ready_now",
    "recoverable_call_graph",
    "split_subworkflow",
    "api_pattern_deferred",
    "exclude",
)

ACCEPTED = {1, 8, 12, 15, 17, 19, 20, 22, 25, 26, 27, 31, 32, 35, 39, 43, 44, 46, 50}
DEFERRED = {3, 6, 42}
RECOVERABLE = {4, 5, 7, 18, 30}
API_PATTERN = {16, 21, 28, 33, 49}
EXCLUDE = {2, 14, 41, 45, 47}
SPLIT = set(range(1, 51)) - ACCEPTED - DEFERRED - RECOVERABLE - API_PATTERN - EXCLUDE

EXPECTED_DECISIONS = {
    "accepted": ACCEPTED,
    "deferred": DEFERRED,
    "rejected": set(range(1, 51)) - ACCEPTED - DEFERRED,
}

CLASS_DEFAULTS = {
    "ready_now": {
        "failure_scope": "candidate_chain",
        "recovery_action": "emit_canonical_row",
        "expected_rows": 1,
        "candidate_after_followup": True,
        "confidence": "high",
    },
    "recoverable_call_graph": {
        "failure_scope": "candidate_chain_and_call_graph",
        "recovery_action": "expand_entrypoint_call_graph_and_dag",
        "expected_rows": 1,
        "candidate_after_followup": True,
        "confidence": "medium",
    },
    "split_subworkflow": {
        "failure_scope": "candidate_chain_and_unit_boundary",
        "recovery_action": "split_by_entrypoint_or_local_subworkflow",
        "expected_rows": 1,
        "candidate_after_followup": True,
        "confidence": "medium",
    },
    "api_pattern_deferred": {
        "failure_scope": "candidate_chain_and_api_intermediate",
        "recovery_action": "model_low_level_api_or_custom_intermediate",
        "expected_rows": 0,
        "candidate_after_followup": True,
        "confidence": "low",
    },
    "exclude": {
        "failure_scope": "candidate_chain_only",
        "recovery_action": "exclude_current_chain_from_processing_gold",
        "expected_rows": 0,
        "candidate_after_followup": False,
        "confidence": "high",
    },
}

EXPECTED_ROWS = {
    9: 1,
    10: 1,
    11: 1,
    13: 2,
    23: 2,
    24: 2,
    29: 2,
    34: 4,
    36: 1,
    37: 2,
    38: 4,
    40: 2,
    48: 2,
}

FIELD_ORDER = [
    "review_index",
    "record_id",
    "final_decision",
    "source_root_id",
    "source_path",
    "relative_path",
    "source_sha256",
    "entrypoint_hint",
    "source_span_hint",
    "chain_key",
    "ordered_operator_ids",
    "mapped_l3_chain",
    "task_text",
    "unit_count",
    "salvage_class",
    "failure_scope",
    "recovery_action",
    "expected_rows",
    "candidate_after_followup",
    "confidence",
    "salvage_reason",
    "source_review_reason",
    "training_admission",
]


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _atomic_write_text(path: Path, text: str) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(text)
        temp_path = Path(handle.name)
    temp_path.replace(path)


def _load_csv(path: Path) -> list[dict[str, Any]]:
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if len(rows) != 50:
        raise ValueError(f"expected 50 review rows, got {len(rows)}")
    if {int(row["review_index"]) for row in rows} != set(range(1, 51)):
        raise ValueError("review CSV must contain review_index 1..50")
    return rows


def _load_jsonl(path: Path) -> dict[int, dict[str, Any]]:
    records: dict[int, dict[str, Any]] = {}
    with Path(path).open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                record = json.loads(line)
                index = int(record["review_index"])
                if index in records:
                    raise ValueError(f"duplicate adjudication review_index: {index}")
                records[index] = record
    if set(records) != set(range(1, 51)):
        raise ValueError("adjudications must contain review_index 1..50")
    return records


def _class_for(index: int) -> str:
    if index in ACCEPTED:
        return "ready_now"
    if index in DEFERRED or index in RECOVERABLE:
        return "recoverable_call_graph"
    if index in API_PATTERN:
        return "api_pattern_deferred"
    if index in EXCLUDE:
        return "exclude"
    if index in SPLIT:
        return "split_subworkflow"
    raise ValueError(f"review_index is not classified: {index}")


def _reason_for(index: int, decision: str, salvage_class: str) -> str:
    if salvage_class == "ready_now":
        return "源码边界、调用顺序和 retained operator chain 已通过人工审核，可先生成 canonical training row。"
    if salvage_class == "recoverable_call_graph":
        return "当前候选链未准入，但源码仍有可恢复的入口、重复调用、分支或显式算子证据；需先展开调用图/DAG。"
    if salvage_class == "split_subworkflow":
        return "当前文件级候选链不能作为单条训练样本，但源码可按入口函数、示例或局部子流程拆分后再评估。"
    if salvage_class == "api_pattern_deferred":
        return "任务依赖低层 PyQGIS/API、NumPy/GDAL 或自定义中间步骤；先进入 API-pattern 解析，不进入首批 Processing gold。"
    if decision == "rejected":
        return "当前候选链没有可证明的 Processing 训练边界，暂排除；不代表源码永久删除。"
    return "需要人工复核该 salvage 分类。"


def _classify_row(
    review_row: dict[str, Any], adjudication: dict[str, Any]
) -> dict[str, Any]:
    index = int(review_row["review_index"])
    if int(adjudication["review_index"]) != index:
        raise ValueError(f"review/adjudication index mismatch: {index}")
    if review_row["record_id"] != adjudication["record_id"]:
        raise ValueError(f"record_id mismatch at review_index {index}")
    decision = str(adjudication["final_decision"])
    expected_indices = EXPECTED_DECISIONS.get(decision)
    if expected_indices is None or index not in expected_indices:
        raise ValueError(f"unexpected decision/index pair: {decision}/{index}")

    salvage_class = _class_for(index)
    defaults = CLASS_DEFAULTS[salvage_class]
    expected_rows = (
        EXPECTED_ROWS.get(index, defaults["expected_rows"])
        if salvage_class == "split_subworkflow"
        else defaults["expected_rows"]
    )
    entrypoint_hint = {
        "ready_now": "source_review_scope",
        "exclude": "none_for_current_candidate",
    }.get(salvage_class, "pending_entrypoint_recovery")
    return {
        "review_index": index,
        "record_id": review_row["record_id"],
        "final_decision": decision,
        "source_root_id": review_row.get("source_root_id", ""),
        "source_path": review_row.get("source_path", ""),
        "relative_path": review_row.get("relative_path", ""),
        "source_sha256": review_row.get("source_sha256", ""),
        "entrypoint_hint": entrypoint_hint,
        "source_span_hint": review_row.get("call_sites", ""),
        "chain_key": review_row.get("chain_key", ""),
        "ordered_operator_ids": review_row.get("ordered_operator_ids", ""),
        "mapped_l3_chain": review_row.get("mapped_l3_chain", ""),
        "task_text": review_row.get("task_text", ""),
        "unit_count": expected_rows,
        "salvage_class": salvage_class,
        "failure_scope": defaults["failure_scope"],
        "recovery_action": defaults["recovery_action"],
        "expected_rows": expected_rows,
        "candidate_after_followup": defaults["candidate_after_followup"],
        "confidence": defaults["confidence"],
        "salvage_reason": _reason_for(index, decision, salvage_class),
        "source_review_reason": adjudication.get("decision_reason", ""),
        "training_admission": "not_granted",
    }


def build_salvage_ledger(
    *,
    review_csv_path: Path,
    adjudications_path: Path,
    output_dir: Path,
) -> Any:
    review_rows = _load_csv(review_csv_path)
    adjudications = _load_jsonl(adjudications_path)
    rows = [
        _classify_row(row, adjudications[int(row["review_index"])])
        for row in review_rows
    ]
    classes = Counter(row["salvage_class"] for row in rows)
    decisions = Counter(row["final_decision"] for row in rows)
    report = {
        "schema": "gis_recommend.qgis_stable101_salvage_ledger.v1",
        "inputs": {
            "review_csv": str(Path(review_csv_path)),
            "review_csv_sha256": _sha256(Path(review_csv_path)),
            "adjudications": str(Path(adjudications_path)),
            "adjudications_sha256": _sha256(Path(adjudications_path)),
        },
        "counts": {
            "rows": len(rows),
            "decision_counts": dict(sorted(decisions.items())),
            "salvage_classes": {name: classes[name] for name in CLASS_ORDER},
            "expected_rows_total": sum(int(row["expected_rows"]) for row in rows),
            "candidate_after_followup": sum(
                bool(row["candidate_after_followup"]) for row in rows
            ),
        },
        "salvage_classes": {name: classes[name] for name in CLASS_ORDER},
        "class_review_indices": {
            name: [row["review_index"] for row in rows if row["salvage_class"] == name]
            for name in CLASS_ORDER
        },
        "decision": {
            "training_admission": "not_granted",
            "validation_eligible": False,
            "test_eligible": False,
            "next_gate": "recover deferred/split rows and validate accepted-only export",
        },
    }

    class Result:
        pass

    result = Result()
    result.report = report
    result.rows = rows
    return result


def _jsonl_text(rows: list[dict[str, Any]]) -> str:
    return "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for row in rows
    )


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with Path(path).open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELD_ORDER)
        writer.writeheader()
        writer.writerows(
            {field: row.get(field, "") for field in FIELD_ORDER} for row in rows
        )


def _render_markdown(report: dict[str, Any]) -> str:
    lines = [
        "# stable101 QGIS Salvage Ledger",
        "",
        "Deterministic salvage classification for the 50-row source-backed review.",
        "No LLM was called. This report does not grant training admission.",
        "",
        "## Summary",
        "",
        f"- Rows: {report['counts']['rows']}",
        f"- Decision counts: {report['counts']['decision_counts']}",
        f"- Salvage classes: {report['counts']['salvage_classes']}",
        f"- Expected rows after follow-up: {report['counts']['expected_rows_total']}",
        f"- Candidate after follow-up: {report['counts']['candidate_after_followup']}",
        "",
        "## Class Definitions",
        "",
        "- ready_now: accepted source-backed chain; eligible for the first export gate.",
        "- recoverable_call_graph: recover entrypoint, repeated calls, branches, or DAG.",
        "- split_subworkflow: split independent functions/examples into local units.",
        "- api_pattern_deferred: model low-level API/custom intermediates before admission.",
        "- exclude: exclude the current file-level candidate from Processing gold.",
        "",
        "## Class Review Indices",
        "",
    ]
    for name in CLASS_ORDER:
        lines.append(f"- {name}: {report['class_review_indices'][name]}")
    return "\n".join(lines) + "\n"


def write_outputs(result: Any, output_dir: Path) -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / "stable101_salvage_ledger_v1.csv"
    jsonl_path = output_dir / "stable101_salvage_ledger_v1.jsonl"
    report_json = output_dir / "stable101_salvage_summary_v1.json"
    report_md = output_dir / "stable101_salvage_report_v1.md"
    hash_ledger = output_dir / "stable101_salvage_hash_ledger_v1.json"

    _write_csv(csv_path, result.rows)
    _atomic_write_text(jsonl_path, _jsonl_text(result.rows))
    _atomic_write_text(
        report_json, json.dumps(result.report, ensure_ascii=False, indent=2, sort_keys=True)
    )
    _atomic_write_text(report_md, _render_markdown(result.report))
    ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "source_inputs": {
            "review_csv": {
                "path": result.report["inputs"]["review_csv"],
                "sha256": result.report["inputs"]["review_csv_sha256"],
            },
            "adjudications": {
                "path": result.report["inputs"]["adjudications"],
                "sha256": result.report["inputs"]["adjudications_sha256"],
            },
        },
        "artifacts": {
            path.name: {"path": str(path), "sha256": _sha256(path), "bytes": path.stat().st_size}
            for path in (csv_path, jsonl_path, report_json, report_md)
        },
    }
    _atomic_write_text(
        hash_ledger, json.dumps(ledger, ensure_ascii=False, indent=2, sort_keys=True)
    )
    return {
        "csv": csv_path,
        "jsonl": jsonl_path,
        "report_json": report_json,
        "report_md": report_md,
        "hash_ledger": hash_ledger,
    }


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-csv", type=Path, default=DEFAULT_REVIEW_CSV)
    parser.add_argument("--adjudications", type=Path, default=DEFAULT_ADJUDICATIONS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)
    result = build_salvage_ledger(
        review_csv_path=args.review_csv,
        adjudications_path=args.adjudications,
        output_dir=args.output_dir,
    )
    return write_outputs(result, args.output_dir)


if __name__ == "__main__":
    main()
