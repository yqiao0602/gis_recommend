# -*- coding: utf-8 -*-
"""
Step 1: 从源数据提取工作流序列

从 Workflowoutput* 目录的所有 steps.csv 文件中提取操作序列。
输出: outputs/pipeline/step1/raw_workflows.json
"""
import os
import csv
import json
import argparse
from pathlib import Path

from gis_recommend.data import get_step_output_dir


def extract_workflow_from_steps(steps_file):
    """从 steps.csv 文件提取操作序列"""
    try:
        with open(steps_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            operations = []
            for row in reader:
                name = row['name'].strip()
                if name and name != 'print':
                    operations.append(name)
            return operations
    except Exception:
        return None


def main(args=None):
    if args is None:
        parser = argparse.ArgumentParser(description="Step 1: 从源数据提取工作流序列")
        parser.add_argument("--source-dir", default="/home/yll/GEE/工作流抽取结果",
                            help="包含 Workflowoutput* 子目录的源数据根目录")
        parser.add_argument("--output-dir", type=Path, default=None,
                            help="输出目录 (默认: outputs/pipeline/step1/)")
        args = parser.parse_args()

    source_dir = args.source_dir
    output_dir = Path(args.output_dir) if args.output_dir else get_step_output_dir(1)

    print("=" * 70)
    print("Step 1: 从源数据提取工作流序列")
    print("=" * 70)

    # 找到所有 Workflowoutput 目录
    workflow_dirs = []
    for item in os.listdir(source_dir):
        if item.startswith('Workflowoutput'):
            workflow_dirs.append(os.path.join(source_dir, item))

    workflow_dirs.sort()
    print(f"\n找到 {len(workflow_dirs)} 个工作流目录")

    # 提取所有工作流
    all_workflows = []
    empty_count = 0
    error_count = 0

    for dir_path in workflow_dirs:
        dir_name = os.path.basename(dir_path)
        print(f"\n处理目录: {dir_name}")

        steps_files = [f for f in os.listdir(dir_path) if f.endswith('_steps.csv')]
        print(f"  找到 {len(steps_files)} 个steps文件")

        for steps_file in steps_files:
            steps_path = os.path.join(dir_path, steps_file)
            workflow = extract_workflow_from_steps(steps_path)

            if workflow is None:
                error_count += 1
            elif len(workflow) == 0:
                empty_count += 1
            else:
                script_id = steps_file.replace('_steps.csv', '')
                all_workflows.append({
                    'script_id': f"{dir_name}_{script_id}",
                    'operations': workflow,
                    'length': len(workflow)
                })

    print(f"\n" + "=" * 70)
    print("提取统计")
    print("=" * 70)
    print(f"总工作流数: {len(all_workflows)}")
    print(f"空工作流数: {empty_count}")
    print(f"错误数: {error_count}")

    lengths = [w['length'] for w in all_workflows]
    print(f"\n长度统计:")
    print(f"  最小长度: {min(lengths)}")
    print(f"  最大长度: {max(lengths)}")
    print(f"  平均长度: {sum(lengths) / len(lengths):.1f}")

    length_ranges = [
        (1, 2, "1-2步"), (3, 5, "3-5步"), (6, 10, "6-10步"),
        (11, 20, "11-20步"), (21, 50, "21-50步"), (51, float('inf'), "50+步"),
    ]
    print(f"\n长度分布:")
    for min_len, max_len, label in length_ranges:
        count = sum(1 for l in lengths if min_len <= l <= max_len)
        pct = count / len(lengths) * 100
        print(f"  {label}: {count} ({pct:.1f}%)")

    # 保存
    output_dir.mkdir(parents=True, exist_ok=True)
    output_file = output_dir / 'raw_workflows.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump({
            'total_count': len(all_workflows),
            'empty_count': empty_count,
            'error_count': error_count,
            'workflows': all_workflows
        }, f, ensure_ascii=False, indent=2)

    print(f"\n保存到: {output_file}")
    print("=" * 70)


if __name__ == '__main__':
    main()
