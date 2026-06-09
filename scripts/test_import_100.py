# -*- coding: utf-8 -*-
"""
测试改进版导入脚本 - 只导入100个工作流
"""

import sys
import os

# 添加路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 导入改进版的导入器
from import_gee_workflows_v2 import ImprovedGEEWorkflowImporter
import csv


def test_import():
    """测试导入100个工作流"""
    NEO4J_URI = "bolt://localhost:7687"
    NEO4J_USER = "neo4j"
    NEO4J_PASSWORD = "12345678"
    NEO4J_DATABASE = "neo4j"

    WORKFLOW_DIR = r"E:\02_projects\03_PythonProject\recommend-system\Operator-recommend-system\Algorithm_classification\workflow-gee"

    print("=" * 70)
    print("测试导入 (100个工作流)")
    print("=" * 70)

    importer = ImprovedGEEWorkflowImporter(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, database=NEO4J_DATABASE)

    try:
        # 加载缓存
        importer.load_gee_operators_cache()

        # 读取元数据（只取前100个）
        metadata_path = os.path.join(WORKFLOW_DIR, "facts_summary10000.csv")
        metadata_list = []
        with open(metadata_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if i >= 100:
                    break
                metadata_list.append(row)

        print(f"\n将导入 {len(metadata_list)} 个工作流...")

        # 读取节点数据
        process_nodes_by_script = {}
        data_nodes_by_script = {}

        for subdir in ["Workflowoutput1-5000", "Workflowoutput5000-10000"]:
            output_dir = os.path.join(WORKFLOW_DIR, subdir)

            process_path = os.path.join(output_dir, "merged_nodes_process.csv")
            if os.path.exists(process_path):
                with open(process_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        script = row['source_script']
                        if script not in process_nodes_by_script:
                            process_nodes_by_script[script] = []
                        process_nodes_by_script[script].append(row)

            data_path = os.path.join(output_dir, "merged_nodes_datasource.csv")
            if os.path.exists(data_path):
                with open(data_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        script = row['source_script']
                        if script not in data_nodes_by_script:
                            data_nodes_by_script[script] = []
                        data_nodes_by_script[script].append(row)

        # 导入
        from tqdm import tqdm
        for metadata in tqdm(metadata_list, desc="导入中"):
            try:
                script_id = metadata['File Name']
                script_num = int(script_id.replace('script_', '').replace('.txt', ''))

                output_dir = os.path.join(
                    WORKFLOW_DIR,
                    "Workflowoutput1-5000" if script_num < 5000 else "Workflowoutput5000-10000"
                )

                importer.import_single_workflow(
                    script_id,
                    metadata,
                    process_nodes_by_script.get(script_id, []),
                    data_nodes_by_script.get(script_id, []),
                    output_dir
                )
            except Exception as e:
                print(f"\n[!] 导入失败: {script_id} - {e}")
                continue

        # 打印统计
        importer.print_statistics()

        print("\n" + "=" * 70)
        print("测试完成！")
        print("=" * 70)

    finally:
        importer.close()


if __name__ == "__main__":
    test_import()
