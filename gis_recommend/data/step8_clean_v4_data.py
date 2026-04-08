# -*- coding: utf-8 -*-
"""
Step 8: 清洗 V4 训练数据中的脏序列

对 labeled_workflows_l3_v4.json 应用 enhanced_sequence_cleaner_final 清洗器，
同步更新 l3_sequence（数值 token 序列）。

输入: outputs/pipeline/step7/labeled_workflows_l3_v4.json
输出: outputs/pipeline/step8/labeled_workflows_l3_v4_cleaned.json
"""
import json
import argparse
from pathlib import Path
from collections import Counter

from gis_recommend.data import get_step_output_dir
from gis_recommend.data.enhanced_sequence_cleaner_final import EnhancedSequenceCleanerFinal
from gis_recommend.config.transformer_config import SPECIAL_TOKENS, VOCAB_SIZE

CLEAN_CONFIG = {
    'min_length': 3, 'max_cycle_len': 15, 'min_cycle_len': 2,
    'filter_auxiliary': True, 'aggressive': True, 'min_uniqueness': 0.1,
    'spaced_min_repeats': 4, 'spaced_min_gap': 2, 'spaced_max_gap': 10,
}
MAX_CONSECUTIVE = 2

SPECIAL_TOKEN_MAP = {v: VOCAB_SIZE + abs(v) - 1 for v in SPECIAL_TOKENS.values()}
START_ID = SPECIAL_TOKEN_MAP[-3]
END_ID = SPECIAL_TOKEN_MAP[-4]


def load_l3_code_to_id(data):
    code_to_id = {}
    for wf in data['labeled_workflows'][:1000]:
        codes = wf.get('l3_codes', [])
        seq = wf.get('l3_sequence', [])
        valid_codes = [c for c in codes if not (isinstance(c, str) and c.startswith('<'))]
        valid_ids = [t for t in seq if t >= 0]
        if len(valid_codes) == len(valid_ids):
            for code, tid in zip(valid_codes, valid_ids):
                if code not in code_to_id:
                    code_to_id[code] = tid
    return code_to_id


def rebuild_l3_sequence(cleaned_codes, code_to_id):
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
                seq.append(-2)
        elif isinstance(code, int):
            seq.append(code)
        else:
            seq.append(-2)
    return seq


def dedup_consecutive(l3_codes, l3_sequence, max_consecutive=2):
    if not l3_codes or not l3_sequence:
        return l3_codes, l3_sequence, 0
    prefix_codes, prefix_seq = [], []
    suffix_codes, suffix_seq = [], []

    idx = 0
    while idx < len(l3_codes):
        c = l3_codes[idx]
        if isinstance(c, str) and c.startswith('<START'):
            prefix_codes.append(c)
            prefix_seq.append(l3_sequence[idx] if idx < len(l3_sequence) else -3)
            idx += 1
        else:
            break

    end_idx = len(l3_codes) - 1
    while end_idx >= idx:
        c = l3_codes[end_idx]
        if isinstance(c, str) and c.startswith('<END'):
            suffix_codes.insert(0, c)
            suffix_seq.insert(0, l3_sequence[end_idx] if end_idx < len(l3_sequence) else -4)
            end_idx -= 1
        else:
            break

    content_codes = l3_codes[idx:end_idx + 1]
    content_seq = l3_sequence[idx:end_idx + 1]
    if len(content_codes) != len(content_seq):
        return l3_codes, l3_sequence, 0

    deduped_codes, deduped_seq = [], []
    num_removed = 0
    i = 0
    while i < len(content_codes):
        run_len = 1
        while (i + run_len < len(content_codes) and
               content_codes[i + run_len] == content_codes[i]):
            run_len += 1
        keep = min(run_len, max_consecutive)
        for j in range(keep):
            deduped_codes.append(content_codes[i + j])
            deduped_seq.append(content_seq[i + j])
        num_removed += run_len - keep
        i += run_len

    return (prefix_codes + deduped_codes + suffix_codes,
            prefix_seq + deduped_seq + suffix_seq,
            num_removed)


def analyze_quality(workflows, label=""):
    total = len(workflows)
    if total == 0:
        print(f"  [{label}] No workflows")
        return
    dirty_consec = 0
    length_sum = 0
    for wf in workflows:
        codes = [c for c in wf.get('l3_codes', [])
                 if not (isinstance(c, str) and c.startswith('<'))]
        length_sum += len(codes)
        max_consec = cur = 1
        for i in range(1, len(codes)):
            if codes[i] == codes[i - 1]:
                cur += 1
                max_consec = max(max_consec, cur)
            else:
                cur = 1
        if max_consec >= 3:
            dirty_consec += 1
    avg_len = length_sum / total
    print(f"  [{label}] Workflows: {total}, Avg content length: {avg_len:.1f}")
    print(f"  [{label}] Consecutive 3+ repeat: {dirty_consec} ({dirty_consec / total * 100:.1f}%)")


def main(args=None):
    if args is None:
        parser = argparse.ArgumentParser(description="Step 8: 清洗 V4 训练数据")
        parser.add_argument("--input-file", type=Path, default=None,
                            help="输入文件 (默认: outputs/pipeline/step7/labeled_workflows_l3_v4.json)")
        parser.add_argument("--output-dir", type=Path, default=None,
                            help="输出目录 (默认: outputs/pipeline/step8/)")
        args = parser.parse_args()

    input_file = args.input_file or (get_step_output_dir(7) / "labeled_workflows_l3_v4.json")
    output_dir = args.output_dir or get_step_output_dir(8)

    print("=" * 70)
    print("Step 8: Clean V4 Training Data")
    print("=" * 70)

    print(f"\n[1] Loading data: {input_file}")
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    workflows = data['labeled_workflows']
    print(f"  Total workflows: {len(workflows)}")

    print("\n[2] Building l3_code -> id mapping...")
    code_to_id = load_l3_code_to_id(data)
    print(f"  Mapped {len(code_to_id)} L3 codes to numeric IDs")

    print("\n[3] Pre-cleaning quality:")
    analyze_quality(workflows, "BEFORE")

    print(f"\n[4] Cleaning with config:")
    for k, v in CLEAN_CONFIG.items():
        print(f"  {k}: {v}")

    cleaner = EnhancedSequenceCleanerFinal()
    cleaned_workflows = []
    skipped_no_codes = skipped_quality = skipped_short = 0
    total_consec_removed = consec_dedup_workflows = 0

    for wf in workflows:
        l3_codes = wf.get('l3_codes', [])
        operator_seq = wf.get('operator_sequence', [])
        if not l3_codes or not operator_seq:
            skipped_no_codes += 1
            continue
        cleaned_wf, should_keep, metadata = cleaner.clean_workflow(wf, CLEAN_CONFIG)
        if should_keep:
            new_l3_seq = rebuild_l3_sequence(cleaned_wf['l3_codes'], code_to_id)
            cleaned_wf['l3_sequence'] = new_l3_seq
            deduped_codes, deduped_seq, n_removed = dedup_consecutive(
                cleaned_wf['l3_codes'], new_l3_seq, MAX_CONSECUTIVE)
            total_consec_removed += n_removed
            if n_removed > 0:
                consec_dedup_workflows += 1
            cleaned_wf['l3_codes'] = deduped_codes
            cleaned_wf['l3_sequence'] = deduped_seq
            valid_codes = [c for c in cleaned_wf['l3_codes']
                           if not (isinstance(c, str) and c.startswith('<'))]
            valid_ids = [t for t in cleaned_wf['l3_sequence'] if t >= 0]
            if len(valid_codes) != len(valid_ids):
                skipped_quality += 1
                continue
            content_len = sum(1 for t in cleaned_wf['l3_sequence'] if t >= 0)
            if content_len < CLEAN_CONFIG['min_length']:
                skipped_short += 1
                continue
            cleaned_workflows.append(cleaned_wf)
        else:
            skipped_quality += 1

    print(f"\n[5] Cleaning results:")
    print(f"  Input:   {len(workflows)}")
    print(f"  Kept:    {len(cleaned_workflows)} ({len(cleaned_workflows) / len(workflows) * 100:.1f}%)")
    print(f"  Removed: {len(workflows) - len(cleaned_workflows)}")
    print(f"    - No codes/ops:    {skipped_no_codes}")
    print(f"    - Quality filter:  {skipped_quality}")
    print(f"    - Too short:       {skipped_short}")
    print(f"\n  Consecutive dedup (max={MAX_CONSECUTIVE}):")
    print(f"    Workflows affected: {consec_dedup_workflows}")
    print(f"    Tokens removed:     {total_consec_removed}")

    print(f"\n[6] Post-cleaning quality:")
    analyze_quality(cleaned_workflows, "AFTER")

    content_lengths = [sum(1 for t in wf['l3_sequence'] if t >= 0) for wf in cleaned_workflows]
    print(f"\n[7] Content length distribution:")
    bins = [(1, 5), (6, 10), (11, 15), (16, 20), (21, 30), (31, 50), (51, 100)]
    for lo, hi in bins:
        cnt = sum(1 for l in content_lengths if lo <= l <= hi)
        print(f"  {lo:3d}-{hi:3d}: {cnt:6d} ({cnt / len(content_lengths) * 100:.1f}%)")
    avg = sum(content_lengths) / len(content_lengths) if content_lengths else 0
    print(f"  Average: {avg:.1f}")

    task_types = Counter()
    for wf in cleaned_workflows:
        meta = wf.get('task_metadata', {}) or {}
        task_types[meta.get('task_type', 'Unknown')] += 1
    print(f"\n[8] Task types: {len(task_types)} types")
    for tt, cnt in task_types.most_common(10):
        print(f"  {tt}: {cnt}")

    print(f"\n[9] Saving: {output_dir}")
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
    output_file = output_dir / "labeled_workflows_l3_v4_cleaned.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False)

    file_size = output_file.stat().st_size / 1024 / 1024
    print(f"  Saved: {file_size:.1f} MB")

    print(f"\n{'=' * 70}")
    print(f"DONE! Cleaned data: {output_file}")
    print(f"  {len(workflows)} -> {len(cleaned_workflows)} workflows")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
