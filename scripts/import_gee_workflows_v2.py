# -*- coding: utf-8 -*-
"""
GEE工作流数据导入脚本 (改进版 v2)
基于全面评估，实现更准确的算子匹配

改进点:
1. 统一小写匹配 - 解决大小写问题
2. 过滤构造函数、UI元素、Map方法
3. 上下文感知匹配 - 考虑类型信息
4. 详细的匹配日志
"""

import json
import csv
import os
import sys
from neo4j import GraphDatabase
from tqdm import tqdm
from collections import Counter

# 增加CSV字段大小限制
csv.field_size_limit(10 * 1024 * 1024)

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class ImprovedGEEWorkflowImporter:
    """改进的GEE工作流导入器"""

    # GEE类名列表（用于识别构造函数）
    # 注意：这些类名大多也有对应的算子方法，不应该全部过滤
    # 只在特定上下文（如单独出现ee.ImageCollection）时才判断为构造函数
    GEE_CLASS_NAMES = {
        'algorithms', 'apply', 'array', 'blob', 'call', 'classifier',
        'clusterer', 'confusionmatrix', 'data', 'date', 'daterange',
        'dictionary', 'errormargin', 'feature', 'featurecollection',
        'filter', 'geometry', 'image', 'imagecollection', 'initialize',
        'join', 'kernel', 'list', 'map', 'model', 'number', 'pixeltype',
        'projection', 'reducer', 'reset', 'string', 'table', 'terrain',
        'video'
    }

    # 非数据处理操作（应该过滤）
    # 注意：只过滤确认不在GEE算子库中的操作
    NON_OPERATOR_METHODS = {
        # UI元素（确认不在GEE库中）
        'panel', 'button', 'label', 'textbox', 'slider', 'checkbox',
        'select', 'dateslider', 'chart', 'splitpanel', 'thumbnail',
        # Map类的显示方法（确认不在GEE库中）
        'addlayer', 'centerlayer', 'centerobject', 'setcenter', 'setzoom',
        'setoptions', 'setcontrolvisibility', 'drawingtools',
        # JS语句
        'require', 'print', 'return', 'var', 'function', 'console',
        # 注意：已移除 'map', 'get', 'set', 'tolist' 等，因为它们在GEE库中存在
    }

    def __init__(self, neo4j_uri, neo4j_user, neo4j_password, database="neo4j", progress_file=None):
        self.driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        self.database = database
        print(f"已连接到Neo4j: {neo4j_uri}, 数据库: {database}")

        # 进度日志文件
        self.progress_file = progress_file
        if self.progress_file:
            with open(self.progress_file, 'w', encoding='utf-8') as f:
                f.write(f"GEE工作流导入进度日志\n")
                f.write(f"开始时间: {os.popen('date /t & time /t').read().strip()}\n")
                f.write("=" * 70 + "\n\n")

        # 统计信息
        self.stats = {
            'workflow_count': 0,
            'execution_count': 0,
            'dataset_count': 0,
            'hasExecution_count': 0,
            'hasOperation_count': 0,
            'used_count': 0,
            'wasGeneratedBy_count': 0,
            'nextExec_count': 0,
            # 匹配统计
            'total_operations': 0,
            'matched_operations': 0,
            'filtered_ui': 0,
            'filtered_constructor': 0,
            'filtered_map': 0,
            'filtered_js': 0,
        }

        # 未匹配方法统计（用于后续分析）
        self.unmatched_methods = Counter()

        # GEE算子缓存
        self.gee_operators_cache = None

    def close(self):
        self.driver.close()

    def log_progress(self, message):
        """写入进度日志"""
        if self.progress_file:
            with open(self.progress_file, 'a', encoding='utf-8') as f:
                import datetime
                timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                f.write(f"[{timestamp}] {message}\n")

    def load_gee_operators_cache(self):
        """加载GEE算子名称缓存（改进版）"""
        print("\n[初始化] 加载GEE算子缓存...")
        with self.driver.session(database=self.database) as session:
            result = session.run("""
                MATCH (gee:GEE_Operator)
                RETURN gee.name AS name
            """)

            # 构建多级索引
            self.gee_operators_cache = {
                'all_names_lower': set(),                    # 所有算子名（小写）
                'by_method': {},                             # {method: [full_names]}
                'by_class_method': {},                       # {(class, method): [full_names]}
                'full_name_mapping': {}                      # {name_lower: original_name}
            }

            for record in result:
                full_name = record['name']
                full_name_lower = full_name.lower()

                self.gee_operators_cache['all_names_lower'].add(full_name_lower)
                self.gee_operators_cache['full_name_mapping'][full_name_lower] = full_name

                # 解析算子结构
                parts = full_name_lower.split('.')

                if len(parts) >= 3:
                    # ee.Class.method 或 ee.Algorithms.xxx
                    class_name = parts[1]  # Image, ImageCollection, Algorithms等
                    method = parts[-1]      # 最后的方法名

                    # 按方法名索引
                    if method not in self.gee_operators_cache['by_method']:
                        self.gee_operators_cache['by_method'][method] = []
                    self.gee_operators_cache['by_method'][method].append(full_name)

                    # 按(类, 方法)索引
                    key = (class_name, method)
                    if key not in self.gee_operators_cache['by_class_method']:
                        self.gee_operators_cache['by_class_method'][key] = []
                    self.gee_operators_cache['by_class_method'][key].append(full_name)

        print(f"  [OK] 加载了 {len(self.gee_operators_cache['all_names_lower'])} 个GEE算子")
        print(f"  [OK] 索引了 {len(self.gee_operators_cache['by_method'])} 个方法名")

    def parse_operation_chain(self, op_chain):
        """
        解析操作链，提取方法和上下文

        返回: [(method, context_class), ...]
        """
        if not op_chain:
            return []

        op_chain_lower = op_chain.lower()

        # 过滤UI操作
        if op_chain_lower.startswith('ui.'):
            self.stats['filtered_ui'] += 1
            return []

        # 过滤JS语句
        if op_chain in ['require', 'print', 'return', 'var', 'function', 'console']:
            self.stats['filtered_js'] += 1
            return []

        # 解析链式调用
        parts = op_chain_lower.split('.')

        if len(parts) == 1:
            # 单个词（如 'flatten', 'require'）
            if parts[0] in self.NON_OPERATOR_METHODS:
                return []
            return [(parts[0], None)]

        operations = []

        # 处理不同格式
        if parts[0] == 'ee':
            # ee.Class.method 或 ee.Algorithms.xxx
            if len(parts) == 2:
                # ee.ImageCollection (构造函数)
                # 但也尝试匹配，因为 ee.imagecollection 可能作为算子存在
                class_name = parts[1]
                operations.append((class_name, None))
            elif len(parts) >= 3:
                # ee.ImageCollection.filterDate 或 ee.Algorithms.Image.Segmentation.SNIC
                class_name = parts[1]

                for method in parts[2:]:
                    if method and method not in self.NON_OPERATOR_METHODS:
                        operations.append((method, class_name))
        else:
            # variable.method 或 variable.method.method
            # 跳过第一个（变量名）
            for i, method in enumerate(parts[1:], 1):
                if method and method not in self.NON_OPERATOR_METHODS:
                    # 尝试推断类型（如果前一个是类名）
                    context = None
                    if i == 1 and len(parts) > 1:
                        prev_part = parts[0]
                        # 检查是否是类名（如 ImageCollection.filterDate）
                        if prev_part in self.GEE_CLASS_NAMES:
                            context = prev_part

                    operations.append((method, context))

        # 过滤Map方法
        operations = [(m, c) for m, c in operations
                      if m not in {'addlayer', 'centerobject', 'setcenter'}]

        if len(operations) < len(parts) - 1:
            self.stats['filtered_map'] += len(parts) - 1 - len(operations)

        return operations

    def match_gee_operator(self, method, context_class=None):
        """
        匹配GEE算子（改进版）

        参数:
            method: 方法名（已小写）
            context_class: 上下文类名（可选，如 'imagecollection'）

        返回:
            str or None: 匹配的GEE算子完整名称
        """
        if not self.gee_operators_cache:
            return None

        # 策略1: 上下文感知匹配（优先级最高）
        if context_class:
            key = (context_class, method)
            if key in self.gee_operators_cache['by_class_method']:
                candidates = self.gee_operators_cache['by_class_method'][key]
                # 返回最短的（通常是基础方法）
                return min(candidates, key=len)

        # 策略2: 按方法名匹配
        if method in self.gee_operators_cache['by_method']:
            candidates = self.gee_operators_cache['by_method'][method]

            if len(candidates) == 1:
                return candidates[0]

            # 多个候选：优先选择非Algorithms的
            non_algo = [c for c in candidates if not c.startswith('ee.algorithms.')]
            if non_algo:
                return min(non_algo, key=len)

            return min(candidates, key=len)

        # 策略3: 部分匹配（最后手段）
        for full_name in self.gee_operators_cache['all_names_lower']:
            if method in full_name:
                return self.gee_operators_cache['full_name_mapping'][full_name]

        # 未匹配
        self.unmatched_methods[method] += 1
        return None

    def import_all(self, workflow_dir):
        """导入所有GEE工作流"""
        print("\n" + "=" * 70)
        print("开始导入GEE工作流数据 (改进版 v2)")
        print("=" * 70)

        self.log_progress("=" * 70)
        self.log_progress("开始导入GEE工作流数据")
        self.log_progress("=" * 70)

        # 0. 加载GEE算子缓存
        self.load_gee_operators_cache()
        self.log_progress(f"已加载 {len(self.gee_operators_cache['all_names_lower'])} 个GEE算子到缓存")

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
        self.log_progress(f"读取到 {len(metadata_list)} 个工作流元数据")

        # 2. 读取节点数据
        print(f"\n[步骤 2/4] 读取节点数据...")
        process_nodes_by_script = {}
        data_nodes_by_script = {}

        for subdir in ["Workflowoutput1-5000", "Workflowoutput5000-10000"]:
            output_dir = os.path.join(workflow_dir, subdir)

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

        print(f"  Process节点: {sum(len(v) for v in process_nodes_by_script.values())} 个")
        print(f"  Data节点: {sum(len(v) for v in data_nodes_by_script.values())} 个")

        self.log_progress(f"读取节点数据完成: Process={sum(len(v) for v in process_nodes_by_script.values())}个, Data={sum(len(v) for v in data_nodes_by_script.values())}个")

        # 3. 导入工作流
        print(f"\n[步骤 3/4] 导入工作流实例...")
        self.log_progress(f"开始导入 {len(metadata_list)} 个工作流实例...")

        for i, metadata in enumerate(tqdm(metadata_list, desc="  导入工作流"), 1):
            try:
                script_id = metadata['File Name']
                script_num = int(script_id.replace('script_', '').replace('.txt', ''))

                output_dir = os.path.join(
                    workflow_dir,
                    "Workflowoutput1-5000" if script_num < 5000 else "Workflowoutput5000-10000"
                )

                self.import_single_workflow(
                    script_id,
                    metadata,
                    process_nodes_by_script.get(script_id, []),
                    data_nodes_by_script.get(script_id, []),
                    output_dir
                )

                # 每100个工作流记录一次进度
                if i % 100 == 0:
                    progress_pct = (i / len(metadata_list)) * 100
                    self.log_progress(f"进度: {i}/{len(metadata_list)} ({progress_pct:.1f}%) - 已导入{self.stats['workflow_count']}个工作流, {self.stats['execution_count']}个Execution, {self.stats['hasOperation_count']}个hasOperation关系")

            except Exception as e:
                print(f"\n[!] 导入工作流失败: {script_id}")
                print(f"   错误: {e}")
                continue

        # 4. 打印统计
        print(f"\n[步骤 4/4] 统计结果...")
        self.print_statistics()

        self.log_progress("=" * 70)
        self.log_progress("导入完成！")
        self.log_progress(f"总工作流: {self.stats['workflow_count']}")
        self.log_progress(f"总Execution: {self.stats['execution_count']}")
        self.log_progress(f"总Dataset: {self.stats['dataset_count']}")
        self.log_progress(f"总hasOperation: {self.stats['hasOperation_count']}")
        self.log_progress(f"匹配率: {self.stats['matched_operations']/self.stats['total_operations']*100:.2f}%")
        self.log_progress("=" * 70)

        print("\n" + "=" * 70)
        print("GEE工作流导入完成！")
        print("=" * 70)

    def import_single_workflow(self, script_id, metadata, process_nodes, data_nodes, output_dir):
        """导入单个工作流"""
        with self.driver.session(database=self.database) as session:
            workflow_id = script_id.replace('.txt', '')

            # 1. 创建Workflow_Instance
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

            # 3. 创建Execution节点 + hasOperation关系（改进版）
            execution_ids = {}
            for process_node in process_nodes:
                node_id = process_node['id']
                exec_id = f"{workflow_id}_{node_id}"
                operation_chain = process_node.get('name', '')

                # 解析操作链
                operations = self.parse_operation_chain(operation_chain)
                self.stats['total_operations'] += len(operations)

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
                for method, context_class in operations:
                    gee_op_name = self.match_gee_operator(method, context_class)

                    if gee_op_name:
                        session.run("""
                            MATCH (exec:Execution {id: $exec_id})
                            MATCH (gee:GEE_Operator {name: $gee_name})
                            MERGE (exec)-[:hasOperation]->(gee)
                        """, {
                            "exec_id": exec_id,
                            "gee_name": gee_op_name
                        })
                        self.stats['hasOperation_count'] += 1
                        self.stats['matched_operations'] += 1

            # 4. 创建数据流关系
            edges_file = os.path.join(output_dir, f"{workflow_id}_edges.csv")
            if os.path.exists(edges_file):
                with open(edges_file, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for edge in reader:
                        start_id = edge['start_id']
                        end_id = edge['end_id']
                        edge_type = edge['type']

                        if edge_type == 'USES_SOURCE':
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
            result = session.run("MATCH (n) RETURN labels(n)[0] AS label, count(n) AS count")
            node_counts = {record['label']: record['count'] for record in result}

            result = session.run("MATCH ()-[r]->() RETURN type(r) AS type, count(r) AS count")
            edge_counts = {record['type']: record['count'] for record in result}

        print("\n新增节点:")
        print(f"  Workflow_Instance: {self.stats['workflow_count']}")
        print(f"  Execution: {self.stats['execution_count']}")
        print(f"  Dataset: {self.stats['dataset_count']}")

        print("\n新增关系:")
        print(f"  hasExecution: {self.stats['hasExecution_count']}")
        print(f"  hasOperation: {self.stats['hasOperation_count']}")
        print(f"  Used: {self.stats['used_count']}")
        print(f"  wasGeneratedBy: {self.stats['wasGeneratedBy_count']}")
        print(f"  NextExec: {self.stats['nextExec_count']}")

        print("\n匹配统计:")
        print(f"  总操作数: {self.stats['total_operations']}")
        print(f"  成功匹配: {self.stats['matched_operations']}")
        if self.stats['total_operations'] > 0:
            match_rate = self.stats['matched_operations'] / self.stats['total_operations'] * 100
            print(f"  匹配率: {match_rate:.2f}%")

        print("\n过滤统计:")
        print(f"  UI元素: {self.stats['filtered_ui']}")
        print(f"  构造函数: {self.stats['filtered_constructor']}")
        print(f"  Map方法: {self.stats['filtered_map']}")
        print(f"  JS语句: {self.stats['filtered_js']}")

        print("\n未匹配方法 (Top 20):")
        for method, count in self.unmatched_methods.most_common(20):
            print(f"  {method:25s}: {count:5d}次")

        print("\n当前图谱总计:")
        print(f"  总节点数: {sum(node_counts.values())}")
        print(f"  总关系数: {sum(edge_counts.values())}")


def main():
    """主函数"""
    NEO4J_URI = "bolt://localhost:7687"
    NEO4J_USER = "neo4j"
    NEO4J_PASSWORD = "12345678"
    NEO4J_DATABASE = "neo4j"

    WORKFLOW_DIR = r"E:\02_projects\03_PythonProject\recommend-system\Operator-recommend-system\Algorithm_classification\workflow-gee"
    PROGRESS_FILE = r"E:\02_projects\03_PythonProject\recommend-system\Operator-recommend-system\Algorithm_classification\system_redesign\scripts\import_progress.txt"

    print("=" * 70)
    print("GEE工作流数据导入工具 (改进版 v2)")
    print("=" * 70)
    print(f"\n数据库配置:")
    print(f"  URI: {NEO4J_URI}")
    print(f"  数据库: {NEO4J_DATABASE}")
    print(f"\n数据目录:")
    print(f"  {WORKFLOW_DIR}")
    print(f"\n进度文件:")
    print(f"  {PROGRESS_FILE}")
    print(f"\n改进:")
    print(f"  [+] 统一小写匹配")
    print(f"  [+] 上下文感知匹配")
    print(f"  [+] 智能过滤非算子操作")
    print(f"  [+] 详细匹配日志")
    print(f"  [+] 实时进度记录")

    importer = ImprovedGEEWorkflowImporter(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD, database=NEO4J_DATABASE, progress_file=PROGRESS_FILE)

    try:
        importer.import_all(WORKFLOW_DIR)
    finally:
        importer.close()


if __name__ == "__main__":
    main()
