# -*- coding: utf-8 -*-
"""
检查GEE算子匹配效果
分析工作流脚本中的操作名称与标准GEE算子的匹配情况
"""

from neo4j import GraphDatabase
import csv
import os
from collections import Counter


def check_operator_matching():
    """检查算子匹配效果"""
    NEO4J_URI = "bolt://localhost:7687"
    NEO4J_USER = "neo4j"
    NEO4J_PASSWORD = "12345678"
    NEO4J_DATABASE = "neo4j"

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    try:
        with driver.session(database=NEO4J_DATABASE) as session:
            # 1. 统计有hasOperation关系的Execution比例
            print("=" * 70)
            print("[检查1] Execution节点与GEE算子的连接情况")
            print("=" * 70)

            result = session.run("""
                MATCH (exec:Execution)
                RETURN count(exec) AS total_exec
            """)
            total_exec = result.single()['total_exec']

            result = session.run("""
                MATCH (exec:Execution)-[:hasOperation]->(gee:GEE_Operator)
                RETURN count(DISTINCT exec) AS exec_with_op
            """)
            exec_with_op = result.single()['exec_with_op']

            result = session.run("""
                MATCH (exec:Execution)-[:hasOperation]->(gee:GEE_Operator)
                RETURN count(*) AS total_relations
            """)
            total_relations = result.single()['total_relations']

            print(f"\n总Execution节点数: {total_exec}")
            print(f"有hasOperation关系的Execution: {exec_with_op}")
            print(f"匹配率: {exec_with_op/total_exec*100:.2f}%")
            print(f"总hasOperation关系数: {total_relations}")
            print(f"平均每个Execution匹配的算子数: {total_relations/exec_with_op:.2f}")

            # 2. 查看未匹配的操作链示例
            print("\n" + "=" * 70)
            print("[检查2] 未匹配到GEE算子的操作链示例 (前20个)")
            print("=" * 70)

            result = session.run("""
                MATCH (exec:Execution)
                WHERE NOT (exec)-[:hasOperation]->(:GEE_Operator)
                RETURN exec.operation_chain AS op_chain
                LIMIT 20
            """)

            print("\n未匹配的操作链:")
            unmatched_ops = []
            for record in result:
                op_chain = record['op_chain']
                print(f"  - {op_chain}")
                unmatched_ops.append(op_chain)

            # 3. 分析未匹配操作链的模式
            print("\n" + "=" * 70)
            print("[检查3] 未匹配操作链的常见模式")
            print("=" * 70)

            # 提取未匹配操作链中的方法名
            all_unmatched = session.run("""
                MATCH (exec:Execution)
                WHERE NOT (exec)-[:hasOperation]->(:GEE_Operator)
                RETURN exec.operation_chain AS op_chain
                LIMIT 1000
            """)

            method_names = []
            for record in all_unmatched:
                op_chain = record['op_chain']
                if '.' in op_chain:
                    parts = op_chain.split('.')
                    # 跳过第一个（可能是变量名）
                    for part in parts[1:]:
                        if part and not part.startswith('_'):
                            method_names.append(part.lower())

            method_counter = Counter(method_names)
            print("\n未匹配操作链中最常见的方法名 (Top 20):")
            for method, count in method_counter.most_common(20):
                print(f"  {method}: {count} 次")

            # 4. 检查这些方法在GEE算子中是否存在
            print("\n" + "=" * 70)
            print("[检查4] 常见未匹配方法在GEE算子库中的存在情况")
            print("=" * 70)

            for method, count in method_counter.most_common(10):
                result = session.run("""
                    MATCH (gee:GEE_Operator)
                    WHERE gee.name CONTAINS $method
                    RETURN gee.name AS name
                    LIMIT 3
                """, {"method": method})

                matches = list(result)
                if matches:
                    print(f"\n'{method}' (出现{count}次) -> 找到匹配:")
                    for m in matches:
                        print(f"    - {m['name']}")
                else:
                    print(f"\n'{method}' (出现{count}次) -> 未找到匹配 ❌")

            # 5. 查看成功匹配的示例
            print("\n" + "=" * 70)
            print("[检查5] 成功匹配的示例 (前10个)")
            print("=" * 70)

            result = session.run("""
                MATCH (exec:Execution)-[:hasOperation]->(gee:GEE_Operator)
                RETURN exec.operation_chain AS op_chain,
                       collect(gee.name) AS matched_operators
                LIMIT 10
            """)

            print("\n成功匹配的案例:")
            for record in result:
                print(f"\n操作链: {record['op_chain']}")
                print(f"  匹配到: {', '.join(record['matched_operators'])}")

            # 6. 统计最常用的GEE算子
            print("\n" + "=" * 70)
            print("[检查6] 工作流中最常用的GEE算子 (Top 20)")
            print("=" * 70)

            result = session.run("""
                MATCH (exec:Execution)-[:hasOperation]->(gee:GEE_Operator)
                RETURN gee.name AS operator,
                       count(*) AS usage_count
                ORDER BY usage_count DESC
                LIMIT 20
            """)

            print("\n最常用的GEE算子:")
            for record in result:
                print(f"  {record['operator']}: {record['usage_count']} 次")

    finally:
        driver.close()


def analyze_raw_workflow_data():
    """分析原始工作流数据中的操作名称"""
    print("\n" + "=" * 70)
    print("[额外分析] 原始工作流数据中的操作名称样本")
    print("=" * 70)

    WORKFLOW_DIR = r"E:\02_projects\03_PythonProject\recommend-system\Operator-recommend-system\Algorithm_classification\workflow-gee"

    # 读取一些process节点
    process_file = os.path.join(WORKFLOW_DIR, "Workflowoutput1-5000", "merged_nodes_process.csv")

    if os.path.exists(process_file):
        print(f"\n读取文件: {process_file}")
        print("\n操作名称样本 (前30个):")

        with open(process_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for i, row in enumerate(reader):
                if i >= 30:
                    break
                print(f"  {i+1}. {row.get('name', '')}")

        # 统计名称模式
        print("\n" + "=" * 70)
        print("操作名称统计分析")
        print("=" * 70)

        with open(process_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)

            has_dot = 0
            has_ee_prefix = 0
            total_count = 0

            for row in reader:
                name = row.get('name', '')
                total_count += 1

                if '.' in name:
                    has_dot += 1
                if name.startswith('ee.'):
                    has_ee_prefix += 1

                if total_count >= 10000:  # 采样10000个
                    break

        print(f"\n采样数量: {total_count}")
        print(f"包含'.'的操作: {has_dot} ({has_dot/total_count*100:.2f}%)")
        print(f"以'ee.'开头的操作: {has_ee_prefix} ({has_ee_prefix/total_count*100:.2f}%)")


if __name__ == "__main__":
    # 检查Neo4j中的匹配情况
    check_operator_matching()

    # 分析原始数据
    analyze_raw_workflow_data()
