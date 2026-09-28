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

from gis_recommend.data import (
    get_default_gee_skip_list_path,
    get_default_id_mappings_path,
    get_step_output_dir,
)
from gis_recommend.data.enhanced_sequence_cleaner_final import EnhancedSequenceCleanerFinal
from gis_recommend.data.pipeline_provenance import (
    build_pipeline_provenance,
    provenance_warnings,
)
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


def load_l3_code_to_id(id_mappings_path: Path) -> dict[str, int]:
    """Load the complete content-token authority from id_mappings_v2.json."""
    path = Path(id_mappings_path)
    with path.open('r', encoding='utf-8') as f:
        mappings = json.load(f)

    raw_l3 = mappings.get('l3') if isinstance(mappings, dict) else None
    if not isinstance(raw_l3, dict) or not raw_l3:
        raise ValueError(f"{path} must contain a non-empty 'l3' code-to-id mapping")

    code_to_id: dict[str, int] = {}
    seen_ids: dict[int, str] = {}
    for code, token_id in raw_l3.items():
        if not isinstance(code, str) or not code or code.startswith('<'):
            raise ValueError(f"Invalid L3 code in {path}: {code!r}")
        if isinstance(token_id, bool) or not isinstance(token_id, int) or token_id < 0:
            raise ValueError(f"Invalid token id for {code} in {path}: {token_id!r}")
        if token_id in seen_ids:
            raise ValueError(
                f"Duplicate token id {token_id} in {path}: {seen_ids[token_id]} and {code}"
            )
        code_to_id[code] = token_id
        seen_ids[token_id] = code

    expected_ids = set(range(len(code_to_id)))
    if set(seen_ids) != expected_ids:
        raise ValueError(
            f"L3 token ids in {path} must be contiguous 0..{len(code_to_id) - 1}"
        )
    metadata_size = (mappings.get('metadata') or {}).get('l3_vocab_size')
    if metadata_size is not None and metadata_size != len(code_to_id):
        raise ValueError(
            f"L3 mapping size mismatch in {path}: metadata={metadata_size}, actual={len(code_to_id)}"
        )
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
                raise ValueError(f"Unknown L3 code in cleaned workflow: {code}")
        elif isinstance(code, int):
            raise ValueError(f"Numeric l3_codes value bypasses code authority: {code}")
        else:
            raise ValueError(f"Invalid l3_codes value: {code!r}")
    return seq


def dedup_consecutive(l3_codes, l3_sequence, operator_sequence,
                      confidences, ambiguity_flags, max_consecutive=2):
    """
    删除连续重复的 L3 token，同步删除对应的内容字段

    l3_codes/l3_sequence 含 <START>/<END>，operator_sequence/confidences/
    ambiguity_flags 是内容序列。这里必须按内容 token 对齐后删除。
    """
    if not l3_codes or not l3_sequence or not operator_sequence:
        return l3_codes, l3_sequence, operator_sequence, confidences, ambiguity_flags, 0

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
    content_ops = operator_sequence

    # 检查内容字段长度一致性
    if (len(content_codes) != len(content_seq) or
            len(content_codes) != len(content_ops) or
            len(content_codes) != len(confidences) or
            len(content_codes) != len(ambiguity_flags)):
        return l3_codes, l3_sequence, operator_sequence, confidences, ambiguity_flags, 0

    deduped_codes, deduped_seq, deduped_ops = [], [], []
    deduped_confidences, deduped_ambiguity = [], []
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
            deduped_ops.append(content_ops[i + j])
            deduped_confidences.append(confidences[i + j])
            deduped_ambiguity.append(ambiguity_flags[i + j])
        num_removed += run_len - keep
        i += run_len

    return (prefix_codes + deduped_codes + suffix_codes,
            prefix_seq + deduped_seq + suffix_seq,
            deduped_ops,
            deduped_confidences,
            deduped_ambiguity,
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
        parser.add_argument("--id-mappings", type=Path, default=get_default_id_mappings_path(),
                            help="当前 id_mappings 文件，用于 provenance 校验")
        parser.add_argument("--skip-list", type=Path, default=get_default_gee_skip_list_path(),
                            help="当前 GEE skip list，用于 provenance 校验")
        parser.add_argument("--provenance-policy", choices=("require", "report"), default="require",
                            help="require blocks stale/missing authority; report is legacy diagnostics only")
        args = parser.parse_args()

    input_file = args.input_file or (get_step_output_dir(7) / "labeled_workflows_l3_v4.json")
    output_dir = args.output_dir or get_step_output_dir(8)
    id_mappings = getattr(args, "id_mappings", None) or get_default_id_mappings_path()
    skip_list = getattr(args, "skip_list", None) or get_default_gee_skip_list_path()

    print("=" * 70)
    print("Step 8: Clean V4 Training Data")
    print("=" * 70)

    print(f"\n[1] Loading data: {input_file}")
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    provenance = data.get('provenance')
    provenance_issues = provenance_warnings(provenance, id_mappings, skip_list, require=True)
    provenance_policy = getattr(args, "provenance_policy", "require")
    if provenance_issues:
        if provenance_policy == "require":
            raise ValueError(
                "Step8 input provenance is not valid for the selected authority: "
                + ", ".join(provenance_issues)
            )
        print("  [WARN] Provenance issues recorded, continuing with report-only snapshot:")
        for issue in provenance_issues:
            print(f"    - {issue}")
    workflows = data['labeled_workflows']
    print(f"  Total workflows: {len(workflows)}")

    print("\n[2] Building l3_code -> id mapping...")
    code_to_id = load_l3_code_to_id(id_mappings)
    print(f"  Mapped {len(code_to_id)} L3 codes to numeric IDs")
    for wf in workflows:
        rebuild_l3_sequence(wf.get('l3_codes', []), code_to_id)

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
            deduped_codes, deduped_seq, deduped_ops, deduped_conf, deduped_amb, n_removed = dedup_consecutive(
                cleaned_wf['l3_codes'],
                new_l3_seq,
                cleaned_wf['operator_sequence'],
                cleaned_wf.get('confidences', []),
                cleaned_wf.get('ambiguity_flags', []),
                MAX_CONSECUTIVE,
            )
            total_consec_removed += n_removed
            if n_removed > 0:
                consec_dedup_workflows += 1
            cleaned_wf['l3_codes'] = deduped_codes
            cleaned_wf['l3_sequence'] = deduped_seq
            cleaned_wf['operator_sequence'] = deduped_ops
            cleaned_wf['confidences'] = deduped_conf
            cleaned_wf['ambiguity_flags'] = deduped_amb
            valid_codes = [c for c in cleaned_wf['l3_codes']
                           if not (isinstance(c, str) and c.startswith('<'))]
            valid_ids = [t for t in cleaned_wf['l3_sequence'] if t >= 0]
            if len(valid_codes) != len(valid_ids):
                skipped_quality += 1
                continue
            if (len(valid_codes) != len(cleaned_wf['operator_sequence']) or
                    len(valid_codes) != len(cleaned_wf['confidences']) or
                    len(valid_codes) != len(cleaned_wf['ambiguity_flags'])):
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
        share = cnt / len(content_lengths) * 100 if content_lengths else 0.0
        print(f"  {lo:3d}-{hi:3d}: {cnt:6d} ({share:.1f}%)")
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
    actual_provenance = build_pipeline_provenance(id_mappings, skip_list)
    output_data = {
        'num_workflows': len(cleaned_workflows),
        'labeled_workflows': cleaned_workflows,
        'provenance': actual_provenance,
        'input_provenance': provenance if provenance != actual_provenance else None,
        'authority_validation': {
            'policy': provenance_policy,
            'input_provenance_validated': not provenance_issues,
            'issues': provenance_issues,
            'training_admission': not provenance_issues,
        },
        'statistics': {
            'original_count': len(workflows),
            'cleaned_count': len(cleaned_workflows),
            'removal_rate': 1 - len(cleaned_workflows) / len(workflows),
            'cleaning_config': CLEAN_CONFIG,
            'cleaner_stats': cleaner.stats,
            'provenance_validated': not provenance_issues,
            'provenance_warnings': provenance_issues,
        }
    }
    output_dir.mkdir(parents=True, exist_ok=True)
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
