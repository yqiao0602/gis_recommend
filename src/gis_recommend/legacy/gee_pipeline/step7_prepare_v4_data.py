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


def _register_metadata(
    target: dict,
    sources: dict,
    key: str,
    metadata: dict,
    source: str,
) -> bool:
    """Register metadata and fail closed when the same key conflicts."""
    if key not in target:
        target[key] = metadata
        sources[key] = [source]
        return False
    if target[key] == metadata:
        sources[key].append(source)
        return True
    raise ValueError(
        f"Conflicting task metadata for {key}: {sources[key][0]} vs {source}"
    )


def _canonical_task_metadata(metadata: dict) -> dict:
    return {
        "task_type": (metadata.get("task_type") or "").strip(),
        "task_name": (metadata.get("task_name") or "").strip(),
        "task_description": (metadata.get("task_description") or "").strip(),
    }


def load_facts_summary_with_diagnostics(gee_dir: Path) -> tuple[dict, dict]:
    facts_map = {}
    sources = {}
    csv_files = sorted(gee_dir.glob("facts_summary*.csv"))
    print(f"  找到 {len(csv_files)} 个 facts_summary 文件")
    input_rows = 0
    identical_duplicates = 0
    for csv_file in csv_files:
        count = 0
        with open(csv_file, "r", encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for line_number, row in enumerate(reader, start=2):
                fname = (row.get("File Name") or "").strip()
                script_key = fname[:-4] if fname.lower().endswith(".txt") else fname
                if not script_key:
                    continue
                metadata = {
                    "task_type": (row.get("Task Type") or "").strip(),
                    "task_name": (row.get("Task Name") or "").strip(),
                    "task_description": (row.get("Task Description") or "").strip(),
                }
                input_rows += 1
                source = f"{csv_file.name}:{line_number}"
                if _register_metadata(facts_map, sources, script_key, metadata, source):
                    identical_duplicates += 1
                count += 1
        print(f"    {csv_file.name}: {count} 条")
    print(f"  总计: {len(facts_map)} 条元数据")
    diagnostics = {
        "lookup_mode": "simplified_script_key",
        "input_files": len(csv_files),
        "input_rows": input_rows,
        "unique_keys": len(facts_map),
        "identical_duplicate_rows": identical_duplicates,
        "conflicting_keys": 0,
        "_source_by_key": sources,
    }
    return facts_map, diagnostics


def load_facts_summary(gee_dir: Path) -> dict:
    facts_map, _ = load_facts_summary_with_diagnostics(gee_dir)
    return facts_map


def load_task_metadata_source(v4_file: Path) -> dict:
    """Load script_id -> task_metadata from an existing V4 labeled file."""
    meta_map, _ = load_task_metadata_source_with_diagnostics(v4_file)
    return meta_map


def load_task_metadata_source_with_diagnostics(v4_file: Path) -> tuple[dict, dict]:
    """Load full-script-id metadata and reject conflicting duplicate IDs."""
    with open(v4_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    meta_map = {}
    sources = {}
    text_authority_by_key = {}
    provenance_conflict_keys = set()
    input_rows = 0
    identical_duplicates = 0
    for index, wf in enumerate(data.get("labeled_workflows", [])):
        sid = wf.get("metadata", {}).get("script_id")
        meta = _canonical_task_metadata(wf.get("task_metadata", {}) or {})
        if not sid or not meta:
            continue
        if meta.get("task_type") and meta.get("task_type") != "Unknown":
            input_rows += 1
            if _register_metadata(meta_map, sources, sid, meta, f"workflow_index:{index}"):
                identical_duplicates += 1
            inherited = (wf.get("metadata", {}) or {}).get("task_metadata_join")
            text_authority = (
                inherited.get("text_provenance_authority", "legacy_unknown")
                if isinstance(inherited, dict) else "legacy_unknown"
            )
            if sid not in text_authority_by_key:
                text_authority_by_key[sid] = text_authority
            elif text_authority_by_key[sid] != text_authority:
                text_authority_by_key[sid] = "legacy_unknown"
                provenance_conflict_keys.add(sid)
    print(f"  从 {v4_file} 读取 task_metadata: {len(meta_map)} 条")
    diagnostics = {
        "lookup_mode": "full_script_id",
        "input_files": 1,
        "input_rows": input_rows,
        "unique_keys": len(meta_map),
        "identical_duplicate_rows": identical_duplicates,
        "conflicting_keys": 0,
        "_source_by_key": sources,
        "provenance_conflict_keys": len(provenance_conflict_keys),
        "_text_authority_by_key": text_authority_by_key,
    }
    return meta_map, diagnostics


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
        parser.add_argument("--metadata-source-file", type=Path, default=None,
                            help="从已有 V4 文件 graft task_metadata，优先于 facts_summary CSV")
        args = parser.parse_args()

    input_file = args.input_file or (get_step_output_dir(6) / "labeled_workflows_l3.json")
    output_dir = args.output_dir or get_step_output_dir(7)
    gee_dir = args.facts_dir
    metadata_source_file = getattr(args, "metadata_source_file", None)

    print("=" * 70)
    print("Step 7: V4 数据准备 — 合并 task_metadata")
    print("=" * 70)

    # [1] 加载 task_metadata
    if metadata_source_file:
        print(f"\n[1] 从已有 V4 文件 graft task_metadata...")
        facts_map, metadata_join = load_task_metadata_source_with_diagnostics(metadata_source_file)
        metadata_source = str(metadata_source_file)
        use_script_id_lookup = True
    else:
        print(f"\n[1] 加载 facts_summary CSV (from {gee_dir})...")
        facts_map, metadata_join = load_facts_summary_with_diagnostics(gee_dir)
        metadata_source = str(gee_dir)
        use_script_id_lookup = False
    source_by_key = metadata_join.pop("_source_by_key", {})
    text_authority_by_key = metadata_join.pop("_text_authority_by_key", {})

    # [2] 加载标注数据
    print(f"\n[2] 加载标注数据: {input_file}")
    with open(input_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    workflows = data["labeled_workflows"]
    provenance = data.get("provenance")
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
        script_key = sid if use_script_id_lookup else extract_script_key(sid)
        meta = facts_map.get(script_key)
        if meta and meta["task_type"]:
            wf["task_metadata"] = meta
            workflow_metadata = dict(wf.get("metadata", {}) or {})
            workflow_metadata["task_metadata_join"] = {
                "match_authority": (
                    "exact_full_script_id" if use_script_id_lookup
                    else "legacy_simplified_script_key"
                ),
                "text_provenance_authority": text_authority_by_key.get(
                    script_key, "legacy_unknown"
                ),
                "source_kind": (
                    "existing_v4_graft" if use_script_id_lookup else "facts_summary_csv"
                ),
                "source_key": script_key,
                "source_locations": source_by_key.get(script_key, []),
            }
            wf["metadata"] = workflow_metadata
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
        "statistics": {
            **stats,
            "metadata_source": metadata_source,
            "metadata_join": metadata_join,
        },
    }
    if provenance is not None:
        output_data["provenance"] = provenance
    output_dir.mkdir(parents=True, exist_ok=True)
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
