# -*- coding: utf-8 -*-
"""
Step 4: 链式调用拆分 / 标准化

将 GEE 链式调用拆分为独立算子，统一大小写，压缩标准化后的重复。

输入: outputs/pipeline/step3/final_workflows.json
输出: outputs/pipeline/step4/standardized_workflows.json
"""
import json
import argparse
from pathlib import Path
from collections import Counter
from typing import List, Optional, Tuple, Set

from gis_recommend.data import get_step_output_dir


# ===================== GEE 标准算子库 =====================
def _default_gee_ops_file() -> Path:
    p = Path(__file__).resolve().parent
    for _ in range(6):
        candidate = p / "gee-operators" / "gee_operators_full_20251108_201454.json"
        if candidate.exists():
            return candidate
        p = p.parent
    return Path(__file__).resolve().parent.parent.parent.parent.parent / \
        "gee-operators" / "gee_operators_full_20251108_201454.json"


def load_gee_standard_ops(gee_ops_file: Path) -> Set[str]:
    with open(gee_ops_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    ops = set()
    items = data if isinstance(data, list) else data.get('operators', [])
    for op in items:
        name = op.get('name', '').lower().strip()
        if name:
            ops.add(name)
    return ops


# ===================== METHOD_TO_CLASS =====================
METHOD_TO_CLASS = {
    'merge': 'ee.imagecollection', 'filter': 'ee.imagecollection',
    'filterdate': 'ee.imagecollection', 'filterbounds': 'ee.imagecollection',
    'filtermetadata': 'ee.imagecollection', 'map': 'ee.imagecollection',
    'first': 'ee.imagecollection', 'min': 'ee.imagecollection',
    'max': 'ee.imagecollection', 'sum': 'ee.imagecollection',
    'reduce': 'ee.imagecollection', 'iterate': 'ee.imagecollection',
    'sort': 'ee.imagecollection', 'limit': 'ee.imagecollection',
    'distinct': 'ee.imagecollection',
    'median': 'ee.imagecollection->image', 'mean': 'ee.imagecollection->image',
    'mosaic': 'ee.imagecollection->image', 'mode': 'ee.imagecollection->image',
    'qualitymosaic': 'ee.imagecollection->image',
    'select': 'ee.image', 'clip': 'ee.image', 'mask': 'ee.image',
    'addbands': 'ee.image', 'rename': 'ee.image', 'add': 'ee.image',
    'subtract': 'ee.image', 'multiply': 'ee.image', 'divide': 'ee.image',
    'normalizedifference': 'ee.image', 'expression': 'ee.image',
    'updatemask': 'ee.image', 'unmask': 'ee.image', 'blend': 'ee.image',
    'paint': 'ee.image', 'reproject': 'ee.image', 'resample': 'ee.image',
    'convolve': 'ee.image', 'focal_mean': 'ee.image', 'focal_median': 'ee.image',
    'focal_mode': 'ee.image', 'focal_min': 'ee.image', 'focal_max': 'ee.image',
    'glcmtexture': 'ee.image', 'tofloat': 'ee.image', 'toint': 'ee.image',
    'toint8': 'ee.image', 'toint16': 'ee.image', 'toint32': 'ee.image',
    'touint8': 'ee.image', 'touint16': 'ee.image', 'touint32': 'ee.image',
    'toarray': 'ee.image', 'arrayflatten': 'ee.image', 'arrayproject': 'ee.image',
    'matrixmultiply': 'ee.image', 'classify': 'ee.image', 'cluster': 'ee.image',
    'cat': 'ee.image', 'bandnames': 'ee.image', 'projection': 'ee.image',
    'metadata': 'ee.image', 'get': 'ee.image', 'set': 'ee.image',
    'copyproperties': 'ee.image',
    'flatten': 'ee.featurecollection', 'aggregate_array': 'ee.featurecollection',
    'aggregate_count': 'ee.featurecollection', 'aggregate_sum': 'ee.featurecollection',
    'aggregate_mean': 'ee.featurecollection',
    'buffer': 'ee.geometry', 'centroid': 'ee.geometry', 'bounds': 'ee.geometry',
    'area': 'ee.geometry', 'perimeter': 'ee.geometry',
    'intersection': 'ee.geometry', 'union': 'ee.geometry', 'difference': 'ee.geometry',
}


def split_gee_chain(op: str, gee_standard_ops: Set[str]) -> List[str]:
    parts = op.split('.')
    if len(parts) <= 3:
        return [op.lower()]
    base = f"{parts[0]}.{parts[1]}".lower()
    return [f"{base}.{m.lower()}" for m in parts[2:]]


def split_variable_chain(op: str, gee_standard_ops: Set[str]) -> List[Tuple[str, str]]:
    parts = op.split('.')
    methods = parts[1:]
    result = []
    current_class = None
    for method in methods:
        method_lower = method.lower()
        if method_lower in METHOD_TO_CLASS:
            class_info = METHOD_TO_CLASS[method_lower]
            if '->' in class_info:
                from_class, to_class = class_info.split('->')
                inferred_class = f'ee.{from_class.split(".")[-1]}'
                result.append((method_lower, inferred_class))
                current_class = f'ee.{to_class}'
            else:
                result.append((method_lower, class_info))
                current_class = class_info
        else:
            if current_class is None:
                current_class = 'ee.image'
            result.append((method_lower, current_class))
    return result


def standardize_operation(op: str, gee_standard_ops: Set[str]) -> Tuple[List[str], str]:
    if not op or not isinstance(op, str):
        return [], 'invalid'
    op = op.strip()
    infrastructure_keywords = [
        'ee.imagecollection', 'ee.image', 'ee.featurecollection',
        'ee.feature', 'ee.geometry', 'ee.date', 'ee.list',
        'ee.dictionary', 'ee.number', 'ee.string', 'ee.array'
    ]
    if op.lower() in infrastructure_keywords:
        return [], 'infrastructure'
    op_lower = op.lower()
    special_ops = [
        'flatten', 'map.addlayer', 'map.centerobject',
        'export.image.todrive', 'export.table.todrive',
        'print', 'chart.image.series'
    ]
    if op_lower in special_ops:
        return [op_lower], 'special'
    if op_lower.startswith('ee.'):
        ops = split_gee_chain(op, gee_standard_ops)
        valid_ops = [o for o in ops if o in gee_standard_ops]
        if valid_ops:
            return ops, 'standard' if len(valid_ops) == len(ops) else 'mixed_gee'
        return ops, 'unknown_gee'
    if '.' in op:
        method_class_pairs = split_variable_chain(op, gee_standard_ops)
        ops = [f"{cls}.{method}" for method, cls in method_class_pairs]
        valid_ops = [o for o in ops if o in gee_standard_ops]
        if valid_ops:
            return ops, 'standard' if len(valid_ops) == len(ops) else 'mixed_inferred'
        return ops, 'inferred'
    if op_lower in gee_standard_ops:
        return [op_lower], 'standard'
    return [op_lower], 'unknown'


def compress_standardized_sequence(sequence: List[str], keep_iterations: int = 1) -> List[str]:
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


def compress_pattern_cycles(sequence: List[str], max_pattern_len: int = 10,
                            min_repeats: int = 2) -> List[str]:
    if len(sequence) < max(2 * min_repeats, 4):
        return sequence
    for pattern_len in range(1, min(max_pattern_len + 1, len(sequence) // min_repeats + 1)):
        i = 0
        result = []
        while i < len(sequence):
            pattern = sequence[i:i + pattern_len]
            repeat_count = 1
            while (i + repeat_count * pattern_len <= len(sequence) and
                   sequence[i + repeat_count * pattern_len:
                            i + (repeat_count + 1) * pattern_len] == pattern):
                repeat_count += 1
            if repeat_count >= min_repeats:
                result.extend(pattern)
                i += repeat_count * pattern_len
            else:
                result.append(sequence[i])
                i += 1
        if len(result) < len(sequence):
            return compress_pattern_cycles(result, max_pattern_len, min_repeats)
    return sequence


def _parse_chain(op: str) -> Tuple[str, List[str]]:
    parts = op.split('.')
    if len(parts) <= 1:
        return op.lower(), []
    if op.lower().startswith('ee.') and len(parts) >= 3:
        head = f"{parts[0]}.{parts[1]}".lower()
        return head, [p.lower() for p in parts[2:]]
    return parts[0].lower(), [p.lower() for p in parts[1:]]


def collapse_progressive_chains_raw(operations: List[str]) -> List[str]:
    if not operations:
        return operations
    result = []
    i = 0
    while i < len(operations):
        current = operations[i]
        curr_head, curr_methods = _parse_chain(current)
        j = i + 1
        last = current
        last_methods = curr_methods
        while j < len(operations):
            next_op = operations[j]
            next_head, next_methods = _parse_chain(next_op)
            if next_head != curr_head:
                break
            if len(next_methods) <= len(last_methods):
                break
            if next_methods[:len(last_methods)] != last_methods:
                break
            last = next_op
            last_methods = next_methods
            j += 1
        result.append(last)
        i = j if j > i + 1 else i + 1
    return result


def main(args=None):
    if args is None:
        parser = argparse.ArgumentParser(description="Step 4: 链式调用拆分和标准化")
        parser.add_argument("--input-file", type=Path, default=None,
                            help="输入文件 (默认: outputs/pipeline/step3/final_workflows.json)")
        parser.add_argument("--output-dir", type=Path, default=None,
                            help="输出目录 (默认: outputs/pipeline/step4/)")
        parser.add_argument("--gee-ops", type=Path, default=None,
                            help="GEE 标准算子库 JSON 路径 (默认: 自动查找)")
        args = parser.parse_args()

    input_file = args.input_file or (get_step_output_dir(3) / "final_workflows.json")
    output_dir = args.output_dir or get_step_output_dir(4)
    gee_ops_file = args.gee_ops or _default_gee_ops_file()

    print("=" * 70)
    print("Step 4: 链式调用拆分和标准化")
    print("=" * 70)

    # 1. 加载 GEE 标准算子库
    print("\n[1] 加载 GEE 标准算子库")
    print(f"  路径: {gee_ops_file}")
    gee_standard_ops = load_gee_standard_ops(gee_ops_file)
    print(f"  标准算子数: {len(gee_standard_ops)}")

    # 2. 加载清洗后的工作流
    print(f"\n[2] 加载工作流: {input_file}")
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    workflows = data['workflows']
    print(f"  工作流数: {len(workflows)}")

    # 3. 标准化
    print("\n[3] 标准化操作")
    standardized_workflows = []
    stats = {
        'total_workflows': len(workflows), 'kept_workflows': 0, 'empty_workflows': 0,
        'total_ops_before': 0, 'total_ops_after': 0, 'gee_chains_split': 0,
        'variable_chains_split': 0, 'standard_ops': 0, 'special_ops': 0,
        'unknown_ops': 0, 'inferred_ops': 0,
    }
    status_counter = Counter()

    for i, wf in enumerate(workflows):
        if (i + 1) % 5000 == 0:
            print(f"  处理进度: {i + 1}/{len(workflows)}")
        full_script_id = wf['script_id']
        original_ops = wf['operations']
        stats['total_ops_before'] += len(original_ops)

        original_ops = collapse_progressive_chains_raw(original_ops)

        standardized_ops = []
        for op in original_ops:
            ops, status = standardize_operation(op, gee_standard_ops)
            if ops:
                standardized_ops.extend(ops)
                status_counter[status] += len(ops)
                if status == 'standard':
                    stats['standard_ops'] += len(ops)
                elif status == 'special':
                    stats['special_ops'] += len(ops)
                elif status in ('unknown', 'unknown_gee'):
                    stats['unknown_ops'] += len(ops)
                elif status in ('inferred', 'mixed_inferred', 'mixed_gee'):
                    stats['inferred_ops'] += len(ops)
                if len(ops) > 1:
                    if op.lower().startswith('ee.'):
                        stats['gee_chains_split'] += 1
                    else:
                        stats['variable_chains_split'] += 1

        if not standardized_ops:
            stats['empty_workflows'] += 1
            continue

        standardized_ops = compress_standardized_sequence(standardized_ops, keep_iterations=1)
        standardized_ops = compress_pattern_cycles(standardized_ops, max_pattern_len=10, min_repeats=2)
        stats['total_ops_after'] += len(standardized_ops)

        standardized_workflows.append({
            'script_id': full_script_id,
            'operator_sequence': standardized_ops,
            'num_operators': len(standardized_ops),
            'task_metadata': wf.get('task_metadata', {}),
        })
        stats['kept_workflows'] += 1

    # 4. 统计
    print(f"\n[4] 统计:")
    print(f"  保留工作流: {stats['kept_workflows']}/{stats['total_workflows']}")
    print(f"  空工作流: {stats['empty_workflows']}")
    print(f"  操作数变化: {stats['total_ops_before']} -> {stats['total_ops_after']}")
    print(f"  GEE链式拆分: {stats['gee_chains_split']}")
    print(f"  变量链式拆分: {stats['variable_chains_split']}")

    all_ops = []
    for wf in standardized_workflows:
        all_ops.extend(wf['operator_sequence'])
    unique_ops = set(all_ops)
    print(f"\n  唯一操作数: {len(unique_ops)}")

    # 5. 保存
    output_data = {
        'num_workflows': len(standardized_workflows),
        'workflows': standardized_workflows,
        'stats': stats,
        'status_distribution': dict(status_counter),
        'unique_operations': sorted(list(unique_ops))
    }
    output_file = output_dir / "standardized_workflows.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print(f"\n  保存到: {output_file}")
    print("=" * 70)


if __name__ == "__main__":
    main()
