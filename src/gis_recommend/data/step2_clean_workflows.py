# -*- coding: utf-8 -*-
"""
Step 2: 清洗工作流

应用循环压缩、去重、过滤等清洗策略。
输入: outputs/pipeline/step1/raw_workflows.json
输出: outputs/pipeline/step2/cleaned_workflows.json
"""
import json
import argparse
from pathlib import Path
from collections import Counter

from gis_recommend.data import get_step_output_dir

# 辅助操作列表（GEE 的辅助类型）
AUXILIARY_OPS = {
    'ee.List', 'ee.Date', 'ee.Number', 'ee.String', 'ee.Dictionary',
    'ee.Array', 'ee.Geometry.Point', 'ee.Geometry.LineString',
    'ee.Geometry.Polygon', 'ee.Geometry.MultiPoint', 'ee.Geometry.MultiLineString',
    'ee.Geometry.MultiPolygon', 'ee.Geometry.Rectangle'
}


def is_auxiliary_op(op):
    return any(op.startswith(aux) for aux in AUXILIARY_OPS)


def compress_simple_cycles(sequence, keep_iterations=1):
    if not sequence:
        return sequence
    result = []
    i = 0
    while i < len(sequence):
        current = sequence[i]
        repeat_count = 1
        while i + repeat_count < len(sequence) and sequence[i + repeat_count] == current:
            repeat_count += 1
        if repeat_count >= 3:
            result.extend([current] * keep_iterations)
        else:
            result.extend([current] * repeat_count)
        i += repeat_count
    return result


def compress_pattern_cycles(sequence, max_pattern_len=15):
    if len(sequence) < 6:
        return sequence
    for pattern_len in range(1, min(max_pattern_len + 1, len(sequence) // 3 + 1)):
        i = 0
        result = []
        while i < len(sequence):
            pattern = sequence[i:i + pattern_len]
            repeat_count = 1
            while (i + repeat_count * pattern_len <= len(sequence) and
                   sequence[i + repeat_count * pattern_len:i + (repeat_count + 1) * pattern_len] == pattern):
                repeat_count += 1
            if repeat_count >= 3:
                result.extend(pattern)
                i += repeat_count * pattern_len
            else:
                result.append(sequence[i])
                i += 1
        if len(result) < len(sequence):
            return compress_pattern_cycles(result, max_pattern_len)
    return sequence


def compress_spaced_repeats(sequence, min_repeats=4, min_gap=2, max_gap=10):
    if len(sequence) < min_repeats * (1 + min_gap):
        return sequence
    op_positions = {}
    for i, op in enumerate(sequence):
        op_positions.setdefault(op, []).append(i)
    to_remove = set()
    for op, positions in op_positions.items():
        if len(positions) < min_repeats:
            continue
        gaps = [positions[i + 1] - positions[i] for i in range(len(positions) - 1)]
        if not gaps:
            continue
        avg_gap = sum(gaps) / len(gaps)
        if min_gap <= avg_gap <= max_gap:
            gap_std = (sum((g - avg_gap) ** 2 for g in gaps) / len(gaps)) ** 0.5
            if gap_std < avg_gap * 0.3:
                to_remove.update(positions[min_repeats:])
    return [op for i, op in enumerate(sequence) if i not in to_remove]


def clean_workflow(operations, config):
    if not operations:
        return None
    if config['filter_auxiliary']:
        operations = [op for op in operations if not is_auxiliary_op(op)]
    if not operations:
        return None
    keep_iterations = 1 if config['aggressive'] else 2
    operations = compress_simple_cycles(operations, keep_iterations)
    operations = compress_pattern_cycles(operations, config['max_cycle_len'])
    operations = compress_spaced_repeats(
        operations, min_repeats=config['spaced_min_repeats'],
        min_gap=config['spaced_min_gap'], max_gap=config['spaced_max_gap'])
    if len(operations) < config['min_length']:
        return None
    if len(operations) > config['max_length']:
        return None
    if len(set(operations)) / len(operations) < config['min_uniqueness']:
        return None
    return operations


def main(args=None):
    if args is None:
        parser = argparse.ArgumentParser(description="Step 2: 清洗工作流")
        parser.add_argument("--input-file", type=Path, default=None,
                            help="输入文件 (默认: outputs/pipeline/step1/raw_workflows.json)")
        parser.add_argument("--output-dir", type=Path, default=None,
                            help="输出目录 (默认: outputs/pipeline/step2/)")
        args = parser.parse_args()

    input_file = args.input_file or (get_step_output_dir(1) / "raw_workflows.json")
    output_dir = args.output_dir or get_step_output_dir(2)

    config = {
        'min_length': 2, 'max_length': 100, 'max_cycle_len': 15,
        'filter_auxiliary': True, 'aggressive': True, 'min_uniqueness': 0.1,
        'spaced_min_repeats': 4, 'spaced_min_gap': 2, 'spaced_max_gap': 10,
    }

    print("=" * 70)
    print("Step 2: 清洗工作流")
    print("=" * 70)
    print("\n清洗配置:")
    for key, value in config.items():
        print(f"  {key}: {value}")

    print(f"\n加载数据: {input_file}")
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    raw_workflows = data['workflows']
    print(f"原始工作流数: {len(raw_workflows)}")

    print("\n开始清洗...")
    cleaned_workflows = []
    stats = {'too_short': 0, 'too_long': 0, 'low_uniqueness': 0,
             'empty_after_filter': 0, 'success': 0}

    for i, wf in enumerate(raw_workflows):
        if (i + 1) % 10000 == 0:
            print(f"  处理进度: {i + 1}/{len(raw_workflows)}")
        original_ops = wf['operations']
        original_len = len(original_ops)
        cleaned_ops = clean_workflow(original_ops, config)
        if cleaned_ops is None:
            if not original_ops:
                stats['empty_after_filter'] += 1
            elif original_len < config['min_length']:
                stats['too_short'] += 1
            elif original_len > config['max_length']:
                stats['too_long'] += 1
            else:
                stats['low_uniqueness'] += 1
        else:
            cleaned_workflows.append({
                'script_id': wf['script_id'],
                'operations': cleaned_ops,
                'length': len(cleaned_ops),
                'original_length': original_len,
                'compression_ratio': len(cleaned_ops) / original_len if original_len > 0 else 0
            })
            stats['success'] += 1

    print("\n" + "=" * 70)
    print("清洗结果")
    print("=" * 70)
    print(f"原始工作流: {len(raw_workflows)}")
    print(f"保留工作流: {len(cleaned_workflows)} ({len(cleaned_workflows) / len(raw_workflows) * 100:.1f}%)")
    print(f"\n过滤原因:")
    print(f"  太短 (<{config['min_length']}): {stats['too_short']}")
    print(f"  太长 (>{config['max_length']}): {stats['too_long']}")
    print(f"  唯一性低 (<{config['min_uniqueness']}): {stats['low_uniqueness']}")
    print(f"  过滤后为空: {stats['empty_after_filter']}")

    lengths = [w['length'] for w in cleaned_workflows]
    print(f"\n长度统计:")
    print(f"  最小: {min(lengths)}")
    print(f"  最大: {max(lengths)}")
    print(f"  平均: {sum(lengths) / len(lengths):.1f}")

    compression_ratios = [w['compression_ratio'] for w in cleaned_workflows]
    print(f"\n压缩率统计:")
    print(f"  平均压缩率: {sum(compression_ratios) / len(compression_ratios):.2f}")
    print(f"  中位数压缩率: {sorted(compression_ratios)[len(compression_ratios) // 2]:.2f}")

    # 保存
    output_data = {
        'config': config,
        'stats': {'raw_count': len(raw_workflows), 'cleaned_count': len(cleaned_workflows),
                  'filter_stats': stats},
        'workflows': cleaned_workflows
    }
    output_file = output_dir / "cleaned_workflows.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"\n保存到: {output_file}")
    print("=" * 70)


if __name__ == '__main__':
    main()
