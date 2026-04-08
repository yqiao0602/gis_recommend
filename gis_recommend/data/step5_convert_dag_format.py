# -*- coding: utf-8 -*-
"""
Step 5: 转换为 DAG 格式

将标准化工作流转换为 label_workflows_with_l3.py 所需的 DAG 格式。

输入: outputs/pipeline/step4/standardized_workflows.json
输出: outputs/pipeline/step5/workflow_sequences.json
"""
import json
import argparse
from pathlib import Path

from gis_recommend.data import get_step_output_dir


def convert_to_dag_format(input_path, output_path):
    print(f"Loading workflows from: {input_path}")
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    workflows = data['workflows']
    print(f"Total workflows: {len(workflows)}")

    workflow_dags = []
    for wf in workflows:
        dag = {
            'script_id': wf['script_id'],
            'nodes': [{'operator': op} for op in wf['operator_sequence']],
            'task_metadata': wf.get('task_metadata', {})
        }
        workflow_dags.append(dag)

    output_data = {
        'workflow_dags': workflow_dags,
        'num_workflows': len(workflow_dags)
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    print(f"Saving {len(workflow_dags)} workflows to: {output_path}")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print("Conversion completed!")
    print(f"  Input workflows: {data['num_workflows']}")
    print(f"  Output workflows: {len(workflow_dags)}")


def main(args=None):
    if args is None:
        parser = argparse.ArgumentParser(description="Step 5: 转换为 DAG 格式")
        parser.add_argument("--input-file", type=Path, default=None,
                            help="输入文件 (默认: outputs/pipeline/step4/standardized_workflows.json)")
        parser.add_argument("--output-dir", type=Path, default=None,
                            help="输出目录 (默认: outputs/pipeline/step5/)")
        args = parser.parse_args()

    input_file = args.input_file or (get_step_output_dir(4) / "standardized_workflows.json")
    output_dir = args.output_dir or get_step_output_dir(5)
    output_file = output_dir / "workflow_sequences.json"

    print("=" * 70)
    print("Step 5: 转换为 DAG 格式")
    print("=" * 70)

    convert_to_dag_format(input_file, output_file)

    print("=" * 70)


if __name__ == "__main__":
    main()
