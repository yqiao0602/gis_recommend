#!/usr/bin/env python3
"""Deterministically compact overlong QGIS task descriptions from source facts."""

from __future__ import annotations

import argparse
import json
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

OPERATOR_LABELS = {
    "gdal:rastercalculator": "栅格计算",
    "gdal:translate": "转换栅格",
    "gdal:warpreproject": "重投影栅格",
    "native:addautoincrementalfield": "添加自增字段",
    "native:addxyfields": "添加坐标字段",
    "native:assignprojection": "指定坐标系",
    "native:aspect": "计算坡向",
    "native:buffer": "创建缓冲区",
    "native:centroids": "提取质心",
    "native:clip": "裁剪图层",
    "native:creategrid": "创建矢量网格",
    "native:deletecolumn": "删除字段",
    "native:deleteduplicategeometries": "删除重复几何",
    "native:difference": "计算差异",
    "native:dissolve": "融合要素",
    "native:extractbyattribute": "按属性筛选",
    "native:extractbyexpression": "按表达式筛选",
    "native:extractbylocation": "按空间关系筛选",
    "native:extractwithindistance": "按距离筛选",
    "native:extractvertices": "提取顶点",
    "native:fieldcalculator": "计算字段",
    "native:fixgeometries": "修复几何",
    "native:intersection": "计算相交",
    "native:joinattributesbylocation": "按空间连接属性",
    "native:joinattributestable": "连接属性表",
    "native:lineintersections": "计算线交点",
    "native:mergevectorlayers": "合并矢量图层",
    "native:multiparttosingleparts": "拆分多部件",
    "native:polygonize": "栅格转面",
    "native:polygonstolines": "面转线",
    "native:reprojectlayer": "重投影图层",
    "native:renametablefield": "重命名字段",
    "native:retainfields": "保留字段",
    "native:selectbylocation": "按空间位置选择",
    "native:setzfromraster": "按栅格设置高程",
    "native:simplifygeometries": "简化几何",
    "native:slope": "计算坡度",
    "native:snapgeometries": "捕捉几何",
    "native:splitlinesbylength": "按长度切分线",
    "native:union": "计算联合",
    "qgis:basicstatisticsforfields": "字段统计",
    "qgis:joinbylocationsummary": "空间连接统计",
    "qgis:variabledistancebuffer": "可变距离缓冲",
    "saga:splitrgbbands": "拆分 RGB 波段",
}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in value) if isinstance(value, list) else json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)


def _run_length_labels(operators: list[str]) -> list[str]:
    labels: list[str] = []
    index = 0
    while index < len(operators):
        end = index + 1
        while end < len(operators) and operators[end] == operators[index]:
            end += 1
        label = OPERATOR_LABELS.get(operators[index], operators[index].split(":", 1)[-1])
        count = end - index
        labels.append(f"{label}×{count}" if count > 1 else label)
        index = end
    return labels


def compact_description(row: dict[str, Any]) -> str:
    labels = _run_length_labels(list(row.get("operator_sequence") or row.get("chain") or []))
    name = str(row.get("task_name") or "QGIS 处理任务").strip()
    return f"{name}：按顺序执行{'、'.join(labels)}，输出处理结果。"


def repair(rows: list[dict[str, Any]], tokenizer: Any, max_text_length: int) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    from gis_recommend.training.train_v4_2 import build_task_prompt

    def prompt_count(row: dict[str, Any], description: str) -> int:
        metadata = row.get("task_metadata") or {}
        task_type = str(metadata.get("task_type") or row.get("task_type") or "")
        task_name = str(row.get("task_name") or metadata.get("task_name") or "")
        return len(tokenizer(build_task_prompt(task_type, task_name, description), add_special_tokens=True)["input_ids"])

    repaired: list[dict[str, Any]] = []
    ledger: list[dict[str, Any]] = []
    for row in rows:
        text = str(row.get("task_description") or "")
        token_count = prompt_count(row, text)
        if token_count <= max_text_length:
            decision = "unchanged_within_gate"
            updated = row
            compact = text
        else:
            compact = compact_description(row)
            compact_count = prompt_count(row, compact)
            if compact_count <= max_text_length:
                decision = "compacted_source_facts"
                metadata = dict(row.get("task_metadata") or {})
                metadata["task_description"] = compact
                updated = {**row, "original_task_description": text, "task_description": compact, "task_metadata": metadata, "description_compaction_status": "passed", "description_compaction_method": "ordered_operator_run_length_v1", "description_compaction_token_count": compact_count, "llm_called": False}
            else:
                decision = "deferred_compact_text_still_over_limit"
                updated = {**row, "description_compaction_status": "deferred", "description_compaction_method": "ordered_operator_run_length_v1", "description_compaction_token_count": compact_count, "llm_called": False}
        repaired.append(updated)
        ledger.append({"sample_id": row.get("sample_id"), "decision": decision, "original_token_count": token_count, "compact_token_count": prompt_count(row, compact), "training_admission": "not_granted_text_repair_sidecar"})
    summary = {"schema": "gis_recommend.qgis_processing_text_repair.summary.v1", "input_rows": len(rows), "decision_counts": dict(Counter(row["decision"] for row in ledger)), "repaired_rows": sum(row["decision"] == "compacted_source_facts" for row in ledger), "deferred_rows": sum(row["decision"] == "deferred_compact_text_still_over_limit" for row in ledger), "max_text_length": max_text_length, "llm_called": False, "training_rows_emitted": 0, "validation_eligible": False, "test_eligible": False, "production_merge": "not_granted"}
    return repaired, ledger, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, action="append", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--max-text-length", type=int, default=128)
    parser.add_argument("--bert-model", default="bert-base-uncased")
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    from transformers import BertTokenizer

    tokenizer = BertTokenizer.from_pretrained(args.bert_model, local_files_only=True)
    rows = [row for path in args.input for row in _read_jsonl(path)]
    repaired, ledger, summary = repair(rows, tokenizer, args.max_text_length)
    _write(args.output_dir / "qgis_processing_text_repaired_v1.jsonl", repaired)
    _write(args.output_dir / "text_repair_ledger_v1.jsonl", ledger)
    _write(args.output_dir / "summary_v1.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
