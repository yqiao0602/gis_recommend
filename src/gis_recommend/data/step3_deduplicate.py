# -*- coding: utf-8 -*-
"""
Step 3: 重复簇审计和最终验证

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
    print("Step 3: 重复簇审计和最终验证")
    print("=" * 70)

    print(f"\n加载数据: {input_file}")
    with open(input_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    workflows = data['workflows']
    print(f"清洗后工作流数: {len(workflows)}")

    # 重复簇只做审计，不删除样本。
    #
    # GEE 中同一算子骨架经常对应不同数据集、区域、指标和 task_metadata。
    # task_metadata 在 Step7 才合并，因此这里按 operations 硬去重会提前删掉
    # 真实不同任务。后续如需限量采样，应在 Step7 之后按任务元数据分层处理。
    print("\n审计重复算子序列...")
    sequence_counts = Counter(workflow_to_string(wf['operations']) for wf in workflows)
    duplicate_group_count = sum(1 for count in sequence_counts.values() if count > 1)
    duplicate_count = sum(count - 1 for count in sequence_counts.values() if count > 1)
    final_workflows = workflows

    print(f"保留工作流数: {len(final_workflows)}")
    print(f"唯一算子序列数: {len(sequence_counts)}")
    print(f"重复算子序列簇数: {duplicate_group_count}")
    print(f"重复额外样本数(仅审计，不删除): {duplicate_count}")

    # 验证
    print("\n" + "=" * 70)
    print("数据质量验证")
    print("=" * 70)
    cycles_found = sum(1 for wf in final_workflows if has_simple_cycle(wf['operations']))
    print(f"仍有简单循环(3+连续重复): {cycles_found}/{len(final_workflows)} "
          f"({cycles_found / len(final_workflows) * 100:.1f}%)")

    lengths = [wf['length'] for wf in final_workflows]
    print(f"\n长度统计:")
    print(f"  最小: {min(lengths)}")
    print(f"  最大: {max(lengths)}")
    print(f"  平均: {sum(lengths) / len(lengths):.1f}")
    print(f"  中位数: {sorted(lengths)[len(lengths) // 2]}")

    all_ops = []
    for wf in final_workflows:
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
            'unique_count': len(final_workflows),
            'unique_sequence_count': len(sequence_counts),
            'duplicate_group_count': duplicate_group_count,
            'duplicate_count': duplicate_count,
            'cycles_found': cycles_found
        },
        'workflows': final_workflows
    }
    output_dir.mkdir(parents=True, exist_ok=True)
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
    print(f"Step3保留: {len(final_workflows)} "
          f"({len(final_workflows) / data['stats']['raw_count'] * 100:.1f}%)")
    print(f"唯一算子序列: {len(sequence_counts)}")
    print("=" * 70)


if __name__ == '__main__':
    main()
