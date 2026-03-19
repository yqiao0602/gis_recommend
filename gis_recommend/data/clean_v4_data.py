# -*- coding: utf-8 -*-
"""
清洗 V4 训练数据中的脏序列

对 labeled_workflows_l3_v4.json 应用 enhanced_sequence_cleaner_final 清洗器:
- cycle_max_len=15 (检测长循环)
- 间隔重复检测 (A...A...A...)
- aggressive=True (激进压缩)
- filter_auxiliary=True (过滤辅助操作)
- min_length=3 (与训练一致)
- 同步更新 l3_sequence (数值token序列)

输出: labeled_workflows_l3_v4_cleaned.json
"""

import json
from pathlib import Path
from collections import Counter

from gis_recommend.data.enhanced_sequence_cleaner_final import EnhancedSequenceCleanerFinal
from gis_recommend.config.transformer_config import OUTPUT_DIR, SPECIAL_TOKENS, VOCAB_SIZE

# ===================== 配置 =====================
INPUT_FILE = OUTPUT_DIR / "labeled_workflows_l3_v4.json"
OUTPUT_FILE = OUTPUT_DIR / "labeled_workflows_l3_v4_cleaned.json"

CLEAN_CONFIG = {
    'min_length': 3,          # 最短保留长度 (content tokens, 不含START/END)
    'max_cycle_len': 15,      # 循环检测最大长度
    'min_cycle_len': 2,       # 循环检测最小长度
    'filter_auxiliary': True,  # 过滤辅助操作 (list, date, string等)
    'aggressive': True,       # 激进压缩: 保留1次循环迭代, 2次间隔出现
    'min_uniqueness': 0.1,    # 最低唯一token比例
    'spaced_min_repeats': 4,  # 间隔重复最少出现次数
    'spaced_min_gap': 2,      # 间隔重复最小间距
    'spaced_max_gap': 10,     # 间隔重复最大间距
}
MAX_CONSECUTIVE = 2  # 连续相同token最多保留2个

# ===================== 特殊Token映射 =====================
SPECIAL_TOKEN_MAP = {v: VOCAB_SIZE + abs(v) - 1 for v in SPECIAL_TOKENS.values()}
START_ID = SPECIAL_TOKEN_MAP[-3]  # 352
END_ID = SPECIAL_TOKEN_MAP[-4]    # 353

# l3_code -> numeric id 映射
def load_l3_code_to_id(data):
    """从数据中构建 l3_code -> numeric_id 映射"""
    code_to_id = {}
    for wf in data['labeled_workflows'][:1000]:  # 采样构建映射
        codes = wf.get('l3_codes', [])
        seq = wf.get('l3_sequence', [])
        # 找到非特殊token的对应关系
        valid_codes = [c for c in codes if not (isinstance(c, str) and c.startswith('<'))]
        valid_ids = [t for t in seq if t >= 0]
        if len(valid_codes) == len(valid_ids):
            for code, tid in zip(valid_codes, valid_ids):
                if code not in code_to_id:
                    code_to_id[code] = tid
    return code_to_id


def rebuild_l3_sequence(cleaned_codes, code_to_id):
    """从清洗后的 l3_codes 重建 l3_sequence (数值序列)"""
    seq = []
    for code in cleaned_codes:
        if isinstance(code, str):
            if code.startswith('<START'):
                seq.append(-3)
            elif code.startswith('<END'):
                seq.append(-4)
            elif code.startswith('<UNK'):
                seq.append(-2)
            elif code.startswith('<PAD'):
                seq.append(-1)
            elif code in code_to_id:
                seq.append(code_to_id[code])
            else:
                seq.append(-2)  # unknown -> UNK
        elif isinstance(code, int):
            seq.append(code)
        else:
            seq.append(-2)
    return seq


def dedup_consecutive(l3_codes, l3_sequence, max_consecutive=2):
    """去除连续重复超过 max_consecutive 次的 token。

    同步处理 l3_codes 和 l3_sequence。
    只对 content token（非特殊token）去重。
    返回 (deduped_codes, deduped_seq, num_removed)
    """
    if not l3_codes or not l3_sequence:
        return l3_codes, l3_sequence, 0

    # 分离 START/END 和 content
    prefix_codes, prefix_seq = [], []
    suffix_codes, suffix_seq = [], []
    content_codes, content_seq = [], []

    # 提取 START
    idx = 0
    while idx < len(l3_codes):
        c = l3_codes[idx]
        if isinstance(c, str) and c.startswith('<START'):
            prefix_codes.append(c)
            prefix_seq.append(l3_sequence[idx] if idx < len(l3_sequence) else -3)
            idx += 1
        else:
            break

    # 提取 END (从尾部)
    end_idx = len(l3_codes) - 1
    while end_idx >= idx:
        c = l3_codes[end_idx]
        if isinstance(c, str) and c.startswith('<END'):
            suffix_codes.insert(0, c)
            suffix_seq.insert(0, l3_sequence[end_idx] if end_idx < len(l3_sequence) else -4)
            end_idx -= 1
        else:
            break

    # Content部分
    content_codes = l3_codes[idx:end_idx + 1]
    content_seq = l3_sequence[idx:end_idx + 1]

    if len(content_codes) != len(content_seq):
        return l3_codes, l3_sequence, 0

    # 连续去重
    deduped_codes = []
    deduped_seq = []
    num_removed = 0

    i = 0
    while i < len(content_codes):
        # 计算当前token的连续出现次数
        run_len = 1
        while (i + run_len < len(content_codes) and
               content_codes[i + run_len] == content_codes[i]):
            run_len += 1

        # 保留最多 max_consecutive 个
        keep = min(run_len, max_consecutive)
        for j in range(keep):
            deduped_codes.append(content_codes[i + j])
            deduped_seq.append(content_seq[i + j])
        num_removed += run_len - keep
        i += run_len

    # 重新组合
    final_codes = prefix_codes + deduped_codes + suffix_codes
    final_seq = prefix_seq + deduped_seq + suffix_seq

    return final_codes, final_seq, num_removed


def analyze_quality(workflows, label=""):
    """分析数据质量"""
    total = len(workflows)
    if total == 0:
        print(f"  [{label}] No workflows")
        return

    dirty_consec = 0
    total_content_tokens = 0
    length_sum = 0

    for wf in workflows:
        codes = [c for c in wf.get('l3_codes', [])
                 if not (isinstance(c, str) and c.startswith('<'))]
        total_content_tokens += len(codes)
        length_sum += len(codes)

        # 连续重复检测
        max_consec = 1
        cur = 1
        for i in range(1, len(codes)):
            if codes[i] == codes[i-1]:
                cur += 1
                max_consec = max(max_consec, cur)
            else:
                cur = 1
        if max_consec >= 3:
            dirty_consec += 1

    avg_len = length_sum / total if total > 0 else 0
    print(f"  [{label}] Workflows: {total}, Avg content length: {avg_len:.1f}")
    print(f"  [{label}] Consecutive 3+ repeat: {dirty_consec} ({dirty_consec/total*100:.1f}%)")


def main():
    print("=" * 70)
    print("Clean V4 Training Data — Apply Sequence Cleaner")
    print("=" * 70)

    # [1] 加载数据
    print(f"\n[1] Loading data: {INPUT_FILE}")
    with open(INPUT_FILE, 'r', encoding='utf-8') as f:
        data = json.load(f)

    workflows = data['labeled_workflows']
    print(f"  Total workflows: {len(workflows)}")

    # [2] 构建 code -> id 映射
    print("\n[2] Building l3_code -> id mapping...")
    code_to_id = load_l3_code_to_id(data)
    print(f"  Mapped {len(code_to_id)} L3 codes to numeric IDs")

    # [3] 清洗前质量分析
    print("\n[3] Pre-cleaning quality:")
    analyze_quality(workflows, "BEFORE")

    # [4] 执行清洗
    print(f"\n[4] Cleaning with config:")
    for k, v in CLEAN_CONFIG.items():
        print(f"  {k}: {v}")

    cleaner = EnhancedSequenceCleanerFinal()
    cleaned_workflows = []
    skipped_no_codes = 0
    skipped_quality = 0
    skipped_short = 0
    total_consec_removed = 0
    consec_dedup_workflows = 0

    for wf in workflows:
        l3_codes = wf.get('l3_codes', [])
        operator_seq = wf.get('operator_sequence', [])

        if not l3_codes or not operator_seq:
            skipped_no_codes += 1
            continue

        cleaned_wf, should_keep, metadata = cleaner.clean_workflow(wf, CLEAN_CONFIG)

        if should_keep:
            # 重建 l3_sequence 与清洗后的 l3_codes 同步
            new_l3_seq = rebuild_l3_sequence(cleaned_wf['l3_codes'], code_to_id)
            cleaned_wf['l3_sequence'] = new_l3_seq

            # 第二步：连续去重 (AAA -> AA)
            deduped_codes, deduped_seq, n_removed = dedup_consecutive(
                cleaned_wf['l3_codes'], new_l3_seq, MAX_CONSECUTIVE
            )
            total_consec_removed += n_removed
            if n_removed > 0:
                consec_dedup_workflows += 1
            cleaned_wf['l3_codes'] = deduped_codes
            cleaned_wf['l3_sequence'] = deduped_seq

            # 验证一致性
            valid_codes = [c for c in cleaned_wf['l3_codes']
                          if not (isinstance(c, str) and c.startswith('<'))]
            valid_ids = [t for t in cleaned_wf['l3_sequence'] if t >= 0]
            if len(valid_codes) != len(valid_ids):
                # 长度不一致，跳过
                skipped_quality += 1
                continue

            # 检查content长度
            content_len = sum(1 for t in cleaned_wf['l3_sequence'] if t >= 0)
            if content_len < CLEAN_CONFIG['min_length']:
                skipped_short += 1
                continue

            cleaned_workflows.append(cleaned_wf)
        else:
            skipped_quality += 1

    # [5] 结果统计
    print(f"\n[5] Cleaning results:")
    print(f"  Input:   {len(workflows)}")
    print(f"  Kept:    {len(cleaned_workflows)} ({len(cleaned_workflows)/len(workflows)*100:.1f}%)")
    print(f"  Removed: {len(workflows) - len(cleaned_workflows)}")
    print(f"    - No codes/ops:    {skipped_no_codes}")
    print(f"    - Quality filter:  {skipped_quality}")
    print(f"    - Too short:       {skipped_short}")

    print(f"\n  Cleaner stats:")
    for k, v in cleaner.stats.items():
        print(f"    {k}: {v}")

    print(f"\n  Consecutive dedup (max={MAX_CONSECUTIVE}):")
    print(f"    Workflows affected: {consec_dedup_workflows}")
    print(f"    Tokens removed:     {total_consec_removed}")

    # [6] 清洗后质量分析
    print(f"\n[6] Post-cleaning quality:")
    analyze_quality(cleaned_workflows, "AFTER")

    # [7] 长度分布
    content_lengths = []
    for wf in cleaned_workflows:
        cl = sum(1 for t in wf['l3_sequence'] if t >= 0)
        content_lengths.append(cl)

    print(f"\n[7] Content length distribution:")
    bins = [(1, 5), (6, 10), (11, 15), (16, 20), (21, 30), (31, 50), (51, 100)]
    for lo, hi in bins:
        cnt = sum(1 for l in content_lengths if lo <= l <= hi)
        print(f"  {lo:3d}-{hi:3d}: {cnt:6d} ({cnt/len(content_lengths)*100:.1f}%)")
    avg = sum(content_lengths) / len(content_lengths) if content_lengths else 0
    print(f"  Average: {avg:.1f}")

    # [8] Task type 分布确认
    task_types = Counter()
    for wf in cleaned_workflows:
        meta = wf.get('task_metadata', {}) or {}
        tt = meta.get('task_type', 'Unknown')
        task_types[tt] += 1
    print(f"\n[8] Task types: {len(task_types)} types")
    for tt, cnt in task_types.most_common(10):
        print(f"  {tt}: {cnt}")
    print(f"  ...")

    # [9] 保存
    print(f"\n[9] Saving: {OUTPUT_FILE}")
    output_data = {
        'num_workflows': len(cleaned_workflows),
        'labeled_workflows': cleaned_workflows,
        'statistics': {
            'original_count': len(workflows),
            'cleaned_count': len(cleaned_workflows),
            'removal_rate': 1 - len(cleaned_workflows) / len(workflows),
            'cleaning_config': CLEAN_CONFIG,
            'cleaner_stats': cleaner.stats,
        }
    }

    with open(OUTPUT_FILE, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False)

    file_size = OUTPUT_FILE.stat().st_size / 1024 / 1024
    print(f"  Saved: {file_size:.1f} MB")

    # [10] 更新提示
    print(f"\n{'=' * 70}")
    print(f"DONE! Cleaned data: {OUTPUT_FILE}")
    print(f"  {len(workflows)} -> {len(cleaned_workflows)} workflows")
    print(f"\nNext steps:")
    print(f"  1. Update transformer_config.py:")
    print(f"     V4_LABELED_WORKFLOWS_PATH = OUTPUT_DIR / 'labeled_workflows_l3_v4_cleaned.json'")
    print(f"  2. Delete old dataset_splits_v4.json to force re-split")
    print(f"  3. Re-run: python train_task_conditioned_transformer_v4_2.py")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
