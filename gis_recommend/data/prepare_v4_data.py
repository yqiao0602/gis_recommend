# -*- coding: utf-8 -*-
"""
V4 数据准备脚本

将 facts_summary CSV 中的 task_metadata 合并到新的 labeled_workflows_l3.json 中，
生成 labeled_workflows_l3_v4.json。

新数据优势：
- 64,724 条工作流（比旧数据多 64%）
- 0% UNK token（旧数据有 12.2%）
- 更干净的序列

合并后新增：
- task_type, task_name, task_description（从 facts_summary CSV 匹配）
- 过滤掉过短序列（内容长度 < 3）
"""

import csv
import json
import numpy as np
from pathlib import Path
from collections import Counter

# ===================== Paths =====================
def _resolve_project_root() -> Path:
    """Find the project root (directory containing 'outputs/')."""
    p = Path(__file__).resolve()
    for parent in [p.parent, p.parent.parent, p.parent.parent.parent,
                   p.parent.parent.parent.parent]:
        if (parent / "outputs").is_dir():
            return parent
    return p.parent

SYSTEM_REDESIGN_DIR = _resolve_project_root()
OUTPUT_DIR = SYSTEM_REDESIGN_DIR / "outputs"
GEE_DIR = SYSTEM_REDESIGN_DIR.parent / "workflow-gee"

INPUT_FILE = OUTPUT_DIR / "labeled_workflows_l3.json"
OUTPUT_FILE = OUTPUT_DIR / "labeled_workflows_l3_v4.json"

MIN_CONTENT_LENGTH = 3  # 最小内容长度（不含 START/END）


def load_facts_summary() -> dict:
    """加载所有 facts_summary CSV 文件，构建 script_key -> metadata 映射"""
    facts_map = {}
    csv_files = sorted(GEE_DIR.glob("facts_summary*.csv"))
    print(f"  找到 {len(csv_files)} 个 facts_summary 文件")

    for csv_file in csv_files:
        count = 0
        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                fname = (row.get("File Name") or "").strip()
                script_key = fname.replace(".txt", "")
                if not script_key:
                    continue
                facts_map[script_key] = {
                    "task_type": (row.get("Task Type") or "").strip(),
                    "task_name": (row.get("Task Name") or "").strip(),
                    "task_description": (row.get("Task Description") or "").strip(),
                }
                count += 1
        print(f"    {csv_file.name}: {count} 条")

    print(f"  总计: {len(facts_map)} 条元数据")
    return facts_map


def extract_script_key(script_id: str) -> str:
    """从 script_id 提取 facts_summary 的 key
    'Workflowoutput1-5000_script_1000' -> 'script_1000'
    """
    parts = script_id.rsplit("_script_", 1)
    if len(parts) == 2:
        return "script_" + parts[1]
    return script_id


def main():
    print("=" * 70)
    print("V4 数据准备：合并 task_metadata")
    print("=" * 70)

    # [1] 加载 facts_summary
    print("\n[1] 加载 facts_summary CSV...")
    facts_map = load_facts_summary()

    # [2] 加载新数据
    print(f"\n[2] 加载新数据: {INPUT_FILE}")
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    workflows = data["labeled_workflows"]
    print(f"  工作流数: {len(workflows)}")

    # [3] 合并 task_metadata + 过滤
    print("\n[3] 合并 task_metadata 并过滤...")
    merged = []
    stats = {
        "total": len(workflows),
        "matched": 0,
        "unmatched": 0,
        "filtered_short": 0,
        "kept": 0,
    }

    for wf in workflows:
        # 计算内容长度（不含 START/END）
        seq = wf["l3_sequence"]
        content_len = sum(1 for t in seq if t >= 0)
        if content_len < MIN_CONTENT_LENGTH:
            stats["filtered_short"] += 1
            continue

        # 匹配 task_metadata
        sid = wf["metadata"]["script_id"]
        script_key = extract_script_key(sid)
        meta = facts_map.get(script_key)

        if meta and meta["task_type"]:
            wf["task_metadata"] = meta
            stats["matched"] += 1
        else:
            wf["task_metadata"] = {
                "task_type": "Unknown",
                "task_name": "",
                "task_description": "",
            }
            stats["unmatched"] += 1

        merged.append(wf)
        stats["kept"] += 1

    # [4] 统计
    print(f"\n  总工作流: {stats['total']}")
    print(f"  过滤（过短 <{MIN_CONTENT_LENGTH}）: {stats['filtered_short']}")
    print(f"  保留: {stats['kept']}")
    print(f"  匹配元数据: {stats['matched']} ({stats['matched']/stats['kept']*100:.1f}%)")
    print(f"  未匹配: {stats['unmatched']}")

    # 任务类型分布
    type_counter = Counter(wf["task_metadata"]["task_type"] for wf in merged)
    print(f"\n  任务类型数: {len(type_counter)}")
    print(f"  Top 15 任务类型:")
    for tt, cnt in type_counter.most_common(15):
        print(f"    {tt:>45s}: {cnt:>5d} ({cnt/len(merged)*100:.1f}%)")

    # 序列长度分布
    content_lengths = []
    for wf in merged:
        cl = sum(1 for t in wf["l3_sequence"] if t >= 0)
        content_lengths.append(cl)
    lengths = np.array(content_lengths)
    print(f"\n  序列长度（内容）: mean={lengths.mean():.1f}, median={np.median(lengths):.0f}")
    print(f"    min={lengths.min()}, max={lengths.max()}")
    print(f"    P25={np.percentile(lengths, 25):.0f}, P75={np.percentile(lengths, 75):.0f}")

    # Token 分布
    all_tokens = Counter()
    for wf in merged:
        for t in wf["l3_sequence"]:
            if t >= 0:
                all_tokens[t] += 1
    total_tokens = sum(all_tokens.values())
    unique_tokens = len(all_tokens)
    top5_pct = sum(c for _, c in all_tokens.most_common(5)) / total_tokens * 100
    print(f"\n  Token 统计: {total_tokens} total, {unique_tokens} unique")
    print(f"  Top 5 占比: {top5_pct:.1f}%")

    # [5] 构建新的 task_type_vocabulary
    print("\n[4] 构建 V4 任务类型词汇表...")
    task_types = sorted(set(
        wf["task_metadata"]["task_type"] for wf in merged
        if wf["task_metadata"]["task_type"] != "Unknown"
    ))
    task_type_to_id = {"Unknown": 0}
    id_to_task_type = {0: "Unknown"}
    for idx, tt in enumerate(task_types, start=1):
        task_type_to_id[tt] = idx
        id_to_task_type[idx] = tt

    task_vocab = {
        "task_type_to_id": task_type_to_id,
        "id_to_task_type": {str(k): v for k, v in id_to_task_type.items()},
        "num_types": len(task_type_to_id),
    }
    print(f"  任务类型数: {task_vocab['num_types']}")

    # [6] 保存
    print(f"\n[5] 保存结果...")

    # 保存合并后的数据
    output_data = {
        "num_workflows": len(merged),
        "labeled_workflows": merged,
        "statistics": stats,
    }
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False)
    print(f"  数据: {OUTPUT_FILE} ({len(merged)} 条)")

    # 保存 V4 任务类型词汇表
    vocab_path = OUTPUT_DIR / "task_type_vocabulary_v4.json"
    with open(vocab_path, "w", encoding="utf-8") as f:
        json.dump(task_vocab, f, indent=2, ensure_ascii=False)
    print(f"  词汇表: {vocab_path} ({task_vocab['num_types']} 类型)")

    print("\n" + "=" * 70)
    print("V4 数据准备完成！")
    print("=" * 70)


if __name__ == "__main__":
    main()
