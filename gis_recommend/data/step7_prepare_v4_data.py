# -*- coding: utf-8 -*-
"""
Step 7: V4 数据准备

将 facts_summary CSV 中的 task_metadata 合并到 labeled_workflows_l3.json，
生成 labeled_workflows_l3_v4.json。

输入: outputs/pipeline/step6/labeled_workflows_l3.json
输出: outputs/pipeline/step7/labeled_workflows_l3_v4.json
"""
import csv
import json
import argparse
import numpy as np
from pathlib import Path
from collections import Counter

from gis_recommend.data import get_project_root, get_step_output_dir

MIN_CONTENT_LENGTH = 3


def load_facts_summary(gee_dir: Path) -> dict:
    facts_map = {}
    csv_files = sorted(gee_dir.glob("facts_summary*.csv"))
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
    parts = script_id.rsplit("_script_", 1)
    if len(parts) == 2:
        return "script_" + parts[1]
    return script_id


def main(args=None):
    if args is None:
        parser = argparse.ArgumentParser(description="Step 7: V4 数据准备 — 合并 task_metadata")
        parser.add_argument("--facts-dir", type=Path,
                            default=Path("/home/yll/GEE/描述性知识抽取汇总"),
                            help="包含 facts_summary*.csv 的目录")
        parser.add_argument("--input-file", type=Path, default=None,
                            help="输入文件 (默认: outputs/pipeline/step6/labeled_workflows_l3.json)")
        parser.add_argument("--output-dir", type=Path, default=None,
                            help="输出目录 (默认: outputs/pipeline/step7/)")
        args = parser.parse_args()

    input_file = args.input_file or (get_step_output_dir(6) / "labeled_workflows_l3.json")
    output_dir = args.output_dir or get_step_output_dir(7)
    gee_dir = args.facts_dir

    print("=" * 70)
    print("Step 7: V4 数据准备 — 合并 task_metadata")
    print("=" * 70)

    # [1] 加载 facts_summary
    print(f"\n[1] 加载 facts_summary CSV (from {gee_dir})...")
    facts_map = load_facts_summary(gee_dir)

    # [2] 加载标注数据
    print(f"\n[2] 加载标注数据: {input_file}")
    with open(input_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    workflows = data["labeled_workflows"]
    print(f"  工作流数: {len(workflows)}")

    # [3] 合并 + 过滤
    print("\n[3] 合并 task_metadata 并过滤...")
    merged = []
    stats = {"total": len(workflows), "matched": 0, "unmatched": 0,
             "filtered_short": 0, "kept": 0}

    for wf in workflows:
        seq = wf["l3_sequence"]
        content_len = sum(1 for t in seq if t >= 0)
        if content_len < MIN_CONTENT_LENGTH:
            stats["filtered_short"] += 1
            continue
        sid = wf["metadata"]["script_id"]
        script_key = extract_script_key(sid)
        meta = facts_map.get(script_key)
        if meta and meta["task_type"]:
            wf["task_metadata"] = meta
            stats["matched"] += 1
        else:
            wf["task_metadata"] = {"task_type": "Unknown", "task_name": "", "task_description": ""}
            stats["unmatched"] += 1
        merged.append(wf)
        stats["kept"] += 1

    print(f"\n  总工作流: {stats['total']}")
    print(f"  过滤（过短 <{MIN_CONTENT_LENGTH}）: {stats['filtered_short']}")
    print(f"  保留: {stats['kept']}")
    print(f"  匹配元数据: {stats['matched']} ({stats['matched'] / stats['kept'] * 100:.1f}%)")
    print(f"  未匹配: {stats['unmatched']}")

    type_counter = Counter(wf["task_metadata"]["task_type"] for wf in merged)
    print(f"\n  任务类型数: {len(type_counter)}")
    print(f"  Top 15:")
    for tt, cnt in type_counter.most_common(15):
        print(f"    {tt:>45s}: {cnt:>5d} ({cnt / len(merged) * 100:.1f}%)")

    content_lengths = [sum(1 for t in wf["l3_sequence"] if t >= 0) for wf in merged]
    lengths = np.array(content_lengths)
    print(f"\n  序列长度: mean={lengths.mean():.1f}, median={np.median(lengths):.0f}")
    print(f"    min={lengths.min()}, max={lengths.max()}")

    # [4] 构建 task_type_vocabulary
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

    # [5] 保存
    print(f"\n[5] 保存结果...")
    output_data = {
        "num_workflows": len(merged),
        "labeled_workflows": merged,
        "statistics": stats,
    }
    output_file = output_dir / "labeled_workflows_l3_v4.json"
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, ensure_ascii=False)
    print(f"  数据: {output_file} ({len(merged)} 条)")

    vocab_path = output_dir / "task_type_vocabulary_v4.json"
    with open(vocab_path, "w", encoding="utf-8") as f:
        json.dump(task_vocab, f, indent=2, ensure_ascii=False)
    print(f"  词汇表: {vocab_path} ({task_vocab['num_types']} 类型)")

    print("\n" + "=" * 70)
    print("Step 7 完成！")
    print("=" * 70)


if __name__ == "__main__":
    main()
