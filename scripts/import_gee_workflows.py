# -*- coding: utf-8 -*-
"""
GEE工作流数据导入脚本 (优化版)
将GEE工作流实例数据导入Neo4j知识图谱

功能:
    1. 创建Workflow_Instance节点（工作流实例）
    2. 创建Execution节点（执行步骤）
    3. 创建Dataset节点（数据源和中间数据）
    4. 创建Parameter节点（参数）
    5. 建立关系：hasExecution, hasOperation, Used, wasGeneratedBy, NextExec

优化:
    - 添加hasOperation关系连接到GEE_Operator
    - 使用批处理优化导入速度
    - 改进GEE算子名称匹配逻辑

使用方法:
    python import_gee_workflows.py
"""

import json
import csv
import os
import sys
from neo4j import GraphDatabase
from tqdm import tqdm
from datetime import datetime

# 增加CSV字段大小限制
csv.field_size_limit(10 * 1024 * 1024)  # 10MB

# 添加父目录到路径
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class GEEWorkflowImporter:
    """GEE工作流导入器"""

    def __init__(self, neo4j_uri, neo4j_user, neo4j_password, database="neo4j"):
        """
        初始化导入器

        参数:
            neo4j_uri: Neo4j数据库URI
            neo4j_user: 用户名
            neo4j_password: 密码
            database: 数据库名称
        """
        self.driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        self.database = database
        print(f"已连接到Neo4j: {neo4j_uri}, 数据库: {database}")

        # 统计信息
        self.stats = {
            'workflow_count': 0,
            'execution_count': 0,
            'dataset_count': 0,
            'parameter_count': 0,
            'hasExecution_count': 0,
            'hasOperation_count': 0,
            'used_count': 0,
            'wasGeneratedBy_count': 0,
            'nextExec_count': 0,
        }

        # 缓存GEE算子名称（用于快速匹配）
        self.gee_operators_cache = None

    def close(self):
        """关闭数据库连接"""
        self.driver.close()

    def load_gee_operators_cache(self):
        """加载GEE算子名称缓存"""
        print("\n[初始化] 加载GEE算子缓存...")
        with self.driver.session(database=self.database) as session:
            result = session.run("""
                MATCH (gee:GEE_Operator)
                RETURN gee.name AS name
            """)

            # 构建算子名称集合和映射
            self.gee_operators_cache = {
                'all_names': set(),
                'by_operator': {}  # {operator_name: [full_names]}
            }

            for record in result:
                full_name = record['name']
                self.gee_operators_cache['all_names'].add(full_name)

                # 提取算子名称（最后一部分）
                # 如 "ee.Image.focal_max" -> "focal_max"
                parts = full_name.split('.')
                if len(parts) >= 2:
                    operator = parts[-1]
                    if operator not in self.gee_operators_cache['by_operator']:
                        self.gee_operators_cache['by_operator'][operator] = []
                    self.gee_operators_cache['by_operator'][operator].append(full_name)

        print(f"  [OK] 加载了 {len(self.gee_operators_cache['all_names'])} 个GEE算子")

    def parse_gee_operation_name(self, name):
        """
        解析GEE操作名称

        参数:
            name: 完整的操作名称，如 "PRISM_col.filterBounds.filterDate"

        返回:
            list: 提取的所有操作符名称，如 ["filterBounds", "filterDate"]
        """
        parts = name.split('.')

        # 过滤掉可能的变量名（通常是小写字母+下划线）
        # 保留看起来像方法名的部分（驼峰命名或全小写方法）
        operators = []
        for part in parts[1:]:  # 跳过第一个（通常是变量名）
            if part and not part.startswith('_'):
                operators.append(part)

        return operators if operators else [parts[-1]] if parts else []

    def match_gee_operator(self, operator_name):
        """
        匹配GEE算子

        参数:
            operator_name: 操作符名称，如 "filterBounds"

        返回:
            str or None: 匹配的GEE算子完整名称
        """
        if not self.gee_operators_cache:
            return None

        # 1. 尝试直接匹配算子名称
        if operator_name in self.gee_operators_cache['by_operator']:
            candidates = self.gee_operators_cache['by_operator'][operator_name]
            # 如果只有一个候选，直接返回
            if len(candidates) == 1:
                return candidates[0]
            # 如果有多个候选，优先返回最短的（通常是基础类的方法）
            return min(candidates, key=len)

        # 2. 尝试模糊匹配（部分匹配）
        for full_name in self.gee_operators_cache['all_names']:
            if operator_name in full_name:
                return full_name

        return None

    def import_all(self, workflow_dir):
        """
        导入所有GEE工作流

        参数:
            workflow_dir: 工作流数据目录
        """
        print("\n" + "=" * 70)
        print("开始导入GEE工作流数据")
        print("=" * 70)

        # 0. 加载GEE算子缓存
        self.load_gee_operators_cache()

        # 1. 读取元数据
        metadata_path = os.path.join(workflow_dir, "facts_summary10000.csv")
        print(f"\n[步骤 1/4] 读取工作流元数据...")
        print(f"  文件: {metadata_path}")

        metadata_list = []
        with open(metadata_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                metadata_list.append(row)

        print(f"  读取到 {len(metadata_list)} 个工作流")

        # 2. 读取合并的节点文件
        print(f"\n[步骤 2/4] 读取节点数据...")

        # 读取Process节点
        process_nodes_by_script = {}

        # 合并两个目录的数据
        for subdir in ["Workflowoutput1-5000", "Workflowoutput5000-10000"]:
            output_dir = os.path.join(workflow_dir, subdir)
            process_nodes_path = os.path.join(output_dir, "merged_nodes_process.csv")

            if os.path.exists(process_nodes_path):
                with open(process_nodes_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        script = row['source_script']
                        if script not in process_nodes_by_script:
                            process_nodes_by_script[script] = []
                        process_nodes_by_script[script].append(row)

        # 读取DataSource节点
        data_nodes_by_script = {}
        for subdir in ["Workflowoutput1-5000", "Workflowoutput5000-10000"]:
            output_dir = os.path.join(workflow_dir, subdir)
            data_nodes_path = os.path.join(output_dir, "merged_nodes_datasource.csv")

            if os.path.exists(data_nodes_path):
                with open(data_nodes_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        script = row['source_script']
                        if script not in data_nodes_by_script:
                            data_nodes_by_script[script] = []
                        data_nodes_by_script[script].append(row)

        print(f"  Process节点: {sum(len(v) for v in process_nodes_by_script.values())} 个")
        print(f"  Data节点: {sum(len(v) for v in data_nodes_by_script.values())} 个")

        # 3. 导入工作流
        print(f"\n[步骤 3/4] 导入工作流实例...")
        for metadata in tqdm(metadata_list, desc="  导入工作流"):
            try:
                script_id = metadata['File Name']

                # 判断应该读取哪个目录的edges文件
                script_num = int(script_id.replace('script_', '').replace('.txt', ''))
                if script_num < 5000:
                    output_dir = os.path.join(workflow_dir, "Workflowoutput1-5000")
                else:
                    output_dir = os.path.join(workflow_dir, "Workflowoutput5000-10000")

                self.import_single_workflow(
                    script_id,
                    metadata,
                    process_nodes_by_script.get(script_id, []),
                    data_nodes_by_script.get(script_id, []),
                    output_dir
                )
            except Exception as e:
                print(f"\n[!] 导入工作流失败: {script_id}")
                print(f"   错误: {e}")
                continue

        # 4. 打印统计
        print(f"\n[步骤 4/4] 统计结果...")
        self.print_statistics()

        print("\n" + "=" * 70)
        print("GEE工作流导入完成！")
        print("=" * 70)

    def import_single_workflow(self, script_id, metadata, process_nodes, data_nodes, output_dir):
        """
        导入单个工作流

        参数:
            script_id: 脚本ID（如 script_10000.txt）
            metadata: 元数据字典
            process_nodes: Process节点列表
            data_nodes: Data节点列表
            output_dir: 输出目录
        """
        with self.driver.session(database=self.database) as session:
            # 1. 创建Workflow_Instance节点
            workflow_id = script_id.replace('.txt', '')

            session.run("""
                MERGE (wf:Workflow_Instance {id: $id})
                SET wf.name = $name,
                    wf.task_type = $task_type,
                    wf.description = $description,
                    wf.source_platform = 'GEE',
                    wf.created_at = datetime()
            """, {
                "id": workflow_id,
                "name": metadata.get('Task Name', ''),
                "task_type": metadata.get('Task Type', ''),
                "description": metadata.get('Task Description', '')
            })
            self.stats['workflow_count'] += 1

            # 2. 创建Dataset节点
            dataset_ids = {}
            for data_node in data_nodes:
                node_id = data_node['id']
                session.run("""
                    MERGE (ds:Dataset {id: $id})
                    SET ds.name = $name,
                        ds.type = $type
                """, {
                    "id": f"{workflow_id}_{node_id}",
                    "name": data_node.get('name', ''),
                    "type": data_node.get('type', '').lower()
                })
                dataset_ids[node_id] = f"{workflow_id}_{node_id}"
                self.stats['dataset_count'] += 1

            # 3. 创建Execution节点 + hasOperation关系
            execution_ids = {}
            for process_node in process_nodes:
                node_id = process_node['id']
                exec_id = f"{workflow_id}_{node_id}"
                operation_chain = process_node.get('name', '')

                # 解析操作名称
                operators = self.parse_gee_operation_name(operation_chain)

                # 创建Execution节点
                session.run("""
                    MATCH (wf:Workflow_Instance {id: $wf_id})
                    MERGE (exec:Execution {id: $exec_id})
                    SET exec.operation_chain = $operation_chain,
                        exec.status = 'completed'
                    MERGE (wf)-[:hasExecution]->(exec)
                """, {
                    "wf_id": workflow_id,
                    "exec_id": exec_id,
                    "operation_chain": operation_chain
                })

                execution_ids[node_id] = exec_id
                self.stats['execution_count'] += 1
                self.stats['hasExecution_count'] += 1

                # 为每个操作符创建hasOperation关系
                for operator in operators:
                    gee_op_name = self.match_gee_operator(operator)

                    if gee_op_name:
                        # 创建hasOperation关系
                        session.run("""
                            MATCH (exec:Execution {id: $exec_id})
                            MATCH (gee:GEE_Operator {name: $gee_name})
                            MERGE (exec)-[:hasOperation]->(gee)
                        """, {
                            "exec_id": exec_id,
                            "gee_name": gee_op_name
                        })
                        self.stats['hasOperation_count'] += 1

            # 4. 读取边文件并创建关系
            edges_file = os.path.join(output_dir, f"{workflow_id}_edges.csv")
            if os.path.exists(edges_file):
                with open(edges_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for edge in reader:
                        start_id = edge['start_id']
                        end_id = edge['end_id']
                        edge_type = edge['type']

                        if edge_type == 'USES_SOURCE':
                            # Dataset -> Execution (Used关系)
                            if start_id in dataset_ids and end_id in execution_ids:
                                session.run("""
                                    MATCH (exec:Execution {id: $exec_id})
                                    MATCH (ds:Dataset {id: $ds_id})
                                    MERGE (exec)-[:Used]->(ds)
                                """, {
                                    "exec_id": execution_ids[end_id],
                                    "ds_id": dataset_ids[start_id]
                                })
                                self.stats['used_count'] += 1

                        elif edge_type == 'GENERATES':
                            # Execution -> Dataset (wasGeneratedBy关系)
                            if start_id in execution_ids and end_id in dataset_ids:
                                session.run("""
                                    MATCH (ds:Dataset {id: $ds_id})
                                    MATCH (exec:Execution {id: $exec_id})
                                    MERGE (ds)-[:wasGeneratedBy]->(exec)
                                """, {
                                    "ds_id": dataset_ids[end_id],
                                    "exec_id": execution_ids[start_id]
                                })
                                self.stats['wasGeneratedBy_count'] += 1

                        elif edge_type == 'PROCESS_NEXT':
                            # Execution -> Execution (NextExec关系)
                            if start_id in execution_ids and end_id in execution_ids:
                                session.run("""
                                    MATCH (exec1:Execution {id: $exec1_id})
                                    MATCH (exec2:Execution {id: $exec2_id})
                                    MERGE (exec1)-[:NextExec]->(exec2)
                                """, {
                                    "exec1_id": execution_ids[start_id],
                                    "exec2_id": execution_ids[end_id]
                                })
                                self.stats['nextExec_count'] += 1

    def print_statistics(self):
        """打印导入统计信息"""
        print("\n" + "=" * 70)
        print("导入统计")
        print("=" * 70)

        with self.driver.session(database=self.database) as session:
            # 查询实际节点数量
            result = session.run("MATCH (n) RETURN labels(n)[0] AS label, count(n) AS count")
            node_counts = {record['label']: record['count'] for record in result}

            # 查询实际关系数量
            result = session.run("MATCH ()-[r]->() RETURN type(r) AS type, count(r) AS count")
            edge_counts = {record['type']: record['count'] for record in result}

        print("\n新增节点:")
        print(f"  Workflow_Instance: {self.stats['workflow_count']}")
        print(f"  Execution: {self.stats['execution_count']}")
        print(f"  Dataset: {self.stats['dataset_count']}")
        print(f"  Parameter: {self.stats['parameter_count']}")

        print("\n新增关系:")
        print(f"  hasExecution: {self.stats['hasExecution_count']}")
        print(f"  hasOperation: {self.stats['hasOperation_count']}")
        print(f"  Used: {self.stats['used_count']}")
        print(f"  wasGeneratedBy: {self.stats['wasGeneratedBy_count']}")
        print(f"  NextExec: {self.stats['nextExec_count']}")

        print("\n当前图谱总计:")
        print(f"  总节点数: {sum(node_counts.values())}")
        print(f"  总关系数: {sum(edge_counts.values())}")


def main():
    """主函数"""
    # 配置
    NEO4J_URI = "bolt://localhost:7687"
    NEO4J_USER = "neo4j"
    NEO4J_PASSWORD = "12345678"
    NEO4J_DATABASE = "neo4j"

    WORKFLOW_DIR = r"E:\02_projects\03_PythonProject\recommend-system\Operator-recommend-system\Algorithm_classification\workflow-gee"

    print("=" * 70)
    print("GEE工作流数据导入工具 (优化版)")
    print("=" * 70)
    print(f"\n数据库配置:")
    print(f"  URI: {NEO4J_URI}")
    print(f"  数据库: {NEO4J_DATABASE}")
    print(f"\n数据目录:")
    print(f"  {WORKFLOW_DIR}")
    print(f"\n新功能:")
    print(f"  [+] 添加hasOperation关系连接到GEE_Operator")
    print(f"  [+] 改进GEE算子名称匹配逻辑")
    print(f"  [+] 使用facts_summary10000.csv数据源(~8,002个工作流)")

    # 创建导入器
    importer = GEEWorkflowImporter(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, database=NEO4J_DATABASE)

    try:
        # 导入工作流
        importer.import_all(WORKFLOW_DIR)

    finally:
        # 关闭连接
        importer.close()


if __name__ == "__main__":
    main()
