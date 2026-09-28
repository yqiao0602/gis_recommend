#!/usr/bin/env python3
"""Publish the jointly confirmed final ten stable101 adjudications."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIR = ROOT / "docs/reports/qgis_mapping_high_impact_blockers_2026-07-24/stable101_second_source_review_50_v1"
FINAL = {
    7: ("rejected_current_chain", "注释/文档字符串调用，不构成可执行链；源码保留待独立复核。"),
    9: ("rejected_current_chain", "源码不可解析，无法证明候选调用的可执行顺序；源码保留待独立复核。"),
    14: ("rejected_current_chain", "候选调用混入文档字符串/注释且存在不完整调用，不能作为执行链。"),
    36: ("rejected_current_chain", "Processing 调用位于代码生成模板字符串，不能证明为实际执行工作流。"),
    39: ("deferred_api_pattern", "点/面分支、循环和条件保存路径决定实际 Processing 链，需恢复条件 DAG 与 API sidecar。"),
    40: ("deferred_api_pattern", "显式 Processing 链之外存在 QgsVectorLayer 与字段/几何编辑数据变换。"),
    43: ("deferred_api_pattern", "union 结果通过 provider 字段编辑和循环/条件逻辑继续变换，固定序列不完整。"),
    44: ("deferred_api_pattern", "rastercalculator 与 CRS 条件分支改变栅格数据流，不能从固定 Processing 序列省略。"),
    46: ("rejected_current_chain", "Processing 调用位于含占位符的代码生成模板，不能证明为实际执行链。"),
    48: ("deferred_api_pattern", "重投影后存在 edit/provider 字段变更，retainfields 受条件控制，需 API sidecar 规则。"),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(proposal_jsonl: Path, review_jsonl: Path) -> list[dict]:
    proposals = {
        int(row["review_index"]): row
        for line in proposal_jsonl.read_text(encoding="utf-8").splitlines()
        if line.strip()
        for row in [json.loads(line)]
    }
    reviews = {
        int(row["review_index"]): row
        for line in review_jsonl.read_text(encoding="utf-8").splitlines()
        if line.strip()
        for row in [json.loads(line)]
    }
    if set(proposals) != set(FINAL):
        raise ValueError("proposal indices do not match the final ten")
    rows = []
    for index in sorted(FINAL):
        decision, reason = FINAL[index]
        proposal, review = proposals[index], reviews[index]
        if proposal["source_sha256"] != review["source_sha256"]:
            raise ValueError(f"source SHA mismatch for #{index}")
        rows.append({
            "schema": "gis_recommend.qgis_stable101_second_adjudication.v1",
            "review_index": index,
            "record_id": review["record_id"],
            "source_sha256": review["source_sha256"],
            "source_path": review["source_path"],
            "ordered_operator_ids": review["ordered_operator_ids"],
            "final_decision": decision,
            "decision_reason": reason,
            "confirmation_status": "jointly_confirmed_batch5",
            "human_source_retrieval_ready": "pass",
            "human_training_candidate_ready": "fail" if decision.startswith("rejected") else "uncertain",
            "training_admission": "not_granted",
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
            "training_rows_emitted": 0,
            "llm_called": False,
        })
    return rows


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser()
    parser.add_argument("--proposal-jsonl", type=Path, default=DEFAULT_DIR / "second_priority_review_batch5_proposals_v1.jsonl")
    parser.add_argument("--review-jsonl", type=Path, default=DEFAULT_DIR / "stable101_source_review_50_v1.jsonl")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_DIR)
    args = parser.parse_args(argv)
    rows = build(args.proposal_jsonl, args.review_jsonl)
    counts = {"rows": len(rows), "accepted": 0, "deferred": 0, "rejected": 0, "pending": 0}
    for row in rows:
        if row["final_decision"].startswith("rejected"):
            counts["rejected"] += 1
        elif row["final_decision"].startswith("deferred"):
            counts["deferred"] += 1
        elif row["final_decision"] == "accepted":
            counts["accepted"] += 1
        else:
            counts["pending"] += 1
    args.output_dir.mkdir(parents=True, exist_ok=True)
    jsonl = args.output_dir / "second_adjudications_batch5_v1.jsonl"
    summary = args.output_dir / "second_adjudications_batch5_summary_v1.json"
    report = args.output_dir / "second_adjudications_batch5_report_v1.md"
    ledger = args.output_dir / "second_adjudications_batch5_hash_v1.json"
    jsonl.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows), encoding="utf-8")
    summary.write_text(json.dumps({"schema": "gis_recommend.qgis_stable101_second_adjudication_batch.v1", "batch_id": "priority_batch5", "counts": counts, "training_admission": "not_granted", "validation_eligible": False, "test_eligible": False, "production_merge": "not_granted", "training_rows_emitted": 0, "llm_called": False}, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report.write_text("# stable101 第二批优先审核 batch 5 正式裁定\n\n" + "\n".join(f"- #{row['review_index']}: `{row['final_decision']}`；{row['decision_reason']}" for row in rows) + "\n\n训练行=0，未调用 LLM，validation/test 与 production merge 禁入。\n", encoding="utf-8")
    ledger.write_text(json.dumps({"schema": "gis_recommend.hash_ledger.v1", "source_inputs": {args.proposal_jsonl.name: {"sha256": sha256(args.proposal_jsonl), "bytes": args.proposal_jsonl.stat().st_size}, args.review_jsonl.name: {"sha256": sha256(args.review_jsonl), "bytes": args.review_jsonl.stat().st_size}}, "artifacts": {jsonl.name: {"sha256": sha256(jsonl), "bytes": jsonl.stat().st_size}, summary.name: {"sha256": sha256(summary), "bytes": summary.stat().st_size}, report.name: {"sha256": sha256(report), "bytes": report.stat().st_size}}}, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return {"jsonl": jsonl, "summary": summary, "report": report, "hash_ledger": ledger}


if __name__ == "__main__":
    main()
