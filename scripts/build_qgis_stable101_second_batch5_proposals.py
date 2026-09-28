#!/usr/bin/env python3
"""Build the final ten proposal-only decisions for stable101 calibration."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DIR = ROOT / "docs/reports/qgis_mapping_high_impact_blockers_2026-07-24/stable101_second_source_review_50_v1"
DECISIONS = {
    7: ("exclude_current_chain", "注释/文档字符串中的调用不构成可执行链；保留源码，排除当前候选链。"),
    9: ("exclude_current_chain", "源码不可解析，无法证明候选调用的可执行顺序；保留源码，排除当前候选链。"),
    14: ("exclude_current_chain", "候选调用混入文档字符串/注释且存在不完整调用，不能作为执行链。"),
    36: ("exclude_current_chain", "文件是代码生成模板，Processing 调用位于模板字符串，不能作为已执行工作流。"),
    39: ("defer_api_pattern", "点/面分支与循环决定 rastersampling 或 zonalstatisticsfb，且结果重投影/保存受条件控制。"),
    40: ("defer_api_pattern", "显式 Processing 链之外包含 QgsVectorLayer、字段/几何编辑等真实数据变换 sidecar。"),
    43: ("defer_api_pattern", "union 结果随后通过 provider 字段编辑和循环/条件逻辑修改，固定序列不能覆盖真实数据流。"),
    44: ("defer_api_pattern", "rastercalculator 与条件 CRS 分支共同决定输出，低层栅格变换不能从固定 Processing 序列中省略。"),
    46: ("exclude_current_chain", "Processing 调用位于代码生成模板，参数含占位符，不能证明为实际执行链。"),
    48: ("defer_api_pattern", "重投影后存在 edit/provider 字段变更，retainfields 受条件控制，需 API sidecar 规则。"),
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def build(review_path: Path, preclass_path: Path) -> tuple[list[dict], dict]:
    reviews = {
        int(row["review_index"]): row
        for line in review_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
        for row in [json.loads(line)]
    }
    preclass = {
        int(row["review_index"]): row
        for line in preclass_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
        for row in [json.loads(line)]
    }
    if set(reviews) != set(range(1, 51)):
        raise ValueError("review pack must contain exactly indices 1..50")
    prior_dir = review_path.parent
    prior_done: set[int] = set()
    for batch_number in range(1, 5):
        path = prior_dir / f"second_adjudications_batch{batch_number}_v1.jsonl"
        if not path.is_file():
            raise ValueError(f"missing prior adjudication sidecar: {path.name}")
        prior_done.update(
            int(row["review_index"])
            for line in path.read_text(encoding="utf-8").splitlines()
            if line.strip()
            for row in [json.loads(line)]
        )
    if set(DECISIONS) != set(reviews) - prior_done or len(prior_done) != 40:
        raise ValueError("final ten decision set must equal the exact remainder after batches 1..4")
    rows = []
    for index in sorted(DECISIONS):
        decision, reason = DECISIONS[index]
        review, classified = reviews[index], preclass[index]
        rows.append({
            "schema": "gis_recommend.qgis_stable101_second_proposal.v1",
            "review_index": index,
            "record_id": review["record_id"],
            "source_sha256": review["source_sha256"],
            "source_path": review["source_path"],
            "salvage_class": classified["salvage_class"],
            "ordered_operator_ids": review["ordered_operator_ids"],
            "proposed_decision": decision,
            "decision_reason": reason,
            "source_evidence": {
                "ast_parse_status": classified.get("ast_parse_status"),
                "ast_chain_alignment_status": classified.get("ast_chain_alignment_status"),
                "lexical_scopes": classified.get("lexical_scopes"),
                "control_flow_kinds": classified.get("control_flow_kinds"),
                "api_pattern_calls": classified.get("api_pattern_calls"),
            },
            "proposal_status": "proposal_only",
            "training_admission": "not_granted",
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
            "llm_called": False,
        })
    summary = {
        "schema": "gis_recommend.qgis_stable101_second_proposal_summary.v1",
        "rows": len(rows),
        "decision_counts": {
            "exclude_current_chain": sum(r["proposed_decision"] == "exclude_current_chain" for r in rows),
            "defer_api_pattern": sum(r["proposed_decision"] == "defer_api_pattern" for r in rows),
        },
        "proposal_status": "proposal_only",
        "training_rows_emitted": 0,
        "training_admission": "not_granted_proposal_only",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "llm_called": False,
    }
    return rows, summary


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser()
    parser.add_argument("--review-jsonl", type=Path, default=DEFAULT_DIR / "stable101_source_review_50_v1.jsonl")
    parser.add_argument("--preclass-jsonl", type=Path, default=DEFAULT_DIR / "second_salvage_preclass_v1.jsonl")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_DIR)
    args = parser.parse_args(argv)
    rows, summary = build(args.review_jsonl, args.preclass_jsonl)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    jsonl = args.output_dir / "second_priority_review_batch5_proposals_v1.jsonl"
    summary_path = args.output_dir / "second_priority_review_batch5_proposals_v1_summary.json"
    report = args.output_dir / "second_priority_review_batch5_proposals_v1.md"
    jsonl.write_text("".join(json.dumps(r, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for r in rows), encoding="utf-8")
    summary_path.write_text(json.dumps({**summary, "input_review_sha256": sha256(args.review_jsonl), "input_preclass_sha256": sha256(args.preclass_jsonl)}, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report.write_text("# stable101 第二批优先审核 batch 5 proposal\n\n状态：`proposal_only`。\n\n" + "\n".join(f"- #{r['review_index']}: `{r['proposed_decision']}`；{r['decision_reason']}" for r in rows) + "\n\n训练行=0，未调用 LLM，validation/test 与 production merge 禁入。\n", encoding="utf-8")
    return {"jsonl": jsonl, "summary": summary_path, "report": report}


if __name__ == "__main__":
    main()
