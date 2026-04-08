# -*- coding: utf-8 -*-
"""
Step 3: 去重和最终验证

输入: outputs/pipeline/step2/cleaned_workflows.json
输出: outputs/pipeline/step3/final_workflows.json
"""
import json
import argparse
from pathlib import Path
from collections import Counter

from gis_recommend.data import get_step_output_dir


def workflow_to_string(operations):
    return '|||'.join(operations)


def has_simple_cycle(sequence, threshold=3):
    for i in range(len(sequence) - threshold + 1):
        if sequence[i:i + threshold] == [sequence[i]] * threshold:
            return True
    return False


def main(args=None):
    if args is None:
        parser = argparse.ArgumentParser(description="Step 3: 去重和最终验证")
        parser.add_argument("--input-file", type=Path, default=None,
                            help="输入文件 (默认: outputs/pipeline/step2/cleaned_workflows.json)")
        parser.add_argument("--output-dir", type=Path, default=None,
                            help="输出目录 (默认: outputs/pipeline/step3/)")
        args = parser.parse_args()

    input_file = args.input_file or (get_step_output_dir(2) / "cleaned_workflows.json")
    output_dir = args.output_dir or get_step_output_dir(3)

    print("=" * 70)
    print("Step 3: 去重和最终验证")
    print("=" * 70)

    print(f"\n加载数据: {input_file}")
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    workflows = data['workflows']
    print(f"清洗后工作流数: {len(workflows)}")

    # 去重
    print("\n执行去重...")
    seen = set()
    unique_workflows = []
    duplicate_count = 0
    for wf in workflows:
        wf_str = workflow_to_string(wf['operations'])
        if wf_str not in seen:
            seen.add(wf_str)
            unique_workflows.append(wf)
        else:
            duplicate_count += 1

    print(f"去重后工作流数: {len(unique_workflows)}")
    print(f"重复工作流数: {duplicate_count}")

    # 验证
    print("\n" + "=" * 70)
    print("数据质量验证")
    print("=" * 70)
    cycles_found = sum(1 for wf in unique_workflows if has_simple_cycle(wf['operations']))
    print(f"仍有简单循环(3+连续重复): {cycles_found}/{len(unique_workflows)} "
          f"({cycles_found / len(unique_workflows) * 100:.1f}%)")

    lengths = [wf['length'] for wf in unique_workflows]
    print(f"\n长度统计:")
    print(f"  最小: {min(lengths)}")
    print(f"  最大: {max(lengths)}")
    print(f"  平均: {sum(lengths) / len(lengths):.1f}")
    print(f"  中位数: {sorted(lengths)[len(lengths) // 2]}")

    all_ops = []
    for wf in unique_workflows:
        all_ops.extend(wf['operations'])
    op_counter = Counter(all_ops)
    print(f"\n操作统计:")
    print(f"  总操作数: {len(all_ops)}")
    print(f"  唯一操作数: {len(op_counter)}")
    print(f"\n最常见的10个操作:")
    for op, count in op_counter.most_common(10):
        print(f"    {op}: {count}")

    # 保存
    output_data = {
        'config': data['config'],
        'stats': {
            'raw_count': data['stats']['raw_count'],
            'cleaned_count': data['stats']['cleaned_count'],
            'unique_count': len(unique_workflows),
            'duplicate_count': duplicate_count,
            'cycles_found': cycles_found
        },
        'workflows': unique_workflows
    }
    output_file = output_dir / "final_workflows.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, ensure_ascii=False, indent=2)

    print(f"\n保存到: {output_file}")

    print("\n" + "=" * 70)
    print("最终总结")
    print("=" * 70)
    print(f"原始工作流: {data['stats']['raw_count']}")
    print(f"清洗后: {data['stats']['cleaned_count']} "
          f"({data['stats']['cleaned_count'] / data['stats']['raw_count'] * 100:.1f}%)")
    print(f"去重后: {len(unique_workflows)} "
          f"({len(unique_workflows) / data['stats']['raw_count'] * 100:.1f}%)")
    print("=" * 70)


if __name__ == '__main__':
    main()
