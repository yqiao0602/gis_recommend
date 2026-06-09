# -*- coding: utf-8 -*-
"""
改进的GEE算子名称匹配分析
"""

from neo4j import GraphDatabase
import re
from collections import Counter


def analyze_matching_issues():
    """深度分析匹配问题"""
    NEO4J_URI = "bolt://localhost:7687"
    NEO4J_USER = "neo4j"
    NEO4J_PASSWORD = "12345678"
    NEO4J_DATABASE = "neo4j"

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    try:
        with driver.session(database=NEO4J_DATABASE) as session:
            print("=" * 70)
            print("GEE算子匹配问题深度分析")
            print("=" * 70)

            # 1. 基本统计
            result = session.run("MATCH (exec:Execution) RETURN count(exec) AS total")
            total_exec = result.single()['total']

            result = session.run("""
                MATCH (exec:Execution)-[:hasOperation]->(:GEE_Operator)
                RETURN count(DISTINCT exec) AS matched
            """)
            matched_exec = result.single()['matched']

            print(f"\nExecution节点总数: {total_exec}")
            print(f"已匹配: {matched_exec} ({matched_exec/total_exec*100:.2f}%)")
            print(f"未匹配: {total_exec - matched_exec} ({(total_exec-matched_exec)/total_exec*100:.2f}%)")

            # 2. 分析未匹配操作的类型
            print("\n" + "=" * 70)
            print("未匹配操作的分类统计")
            print("=" * 70)

            result = session.run("""
                MATCH (exec:Execution)
                WHERE NOT (exec)-[:hasOperation]->(:GEE_Operator)
                RETURN exec.operation_chain AS op_chain
                LIMIT 5000
            """)

            ui_operations = 0
            constructor_operations = 0
            js_statements = 0
            potential_operators = []

            for record in result:
                op_chain = record['op_chain']

                # 分类
                if 'ui.' in op_chain.lower():
                    ui_operations += 1
                elif op_chain in ['require', 'print', 'return', 'var', 'function']:
                    js_statements += 1
                elif op_chain.startswith('ee.') and not '.' in op_chain[3:]:
                    # ee.ImageCollection, ee.FeatureCollection等构造函数
                    constructor_operations += 1
                else:
                    # 可能是真正的算子
                    potential_operators.append(op_chain)

            print(f"\nUI元素 (ui.*): {ui_operations}")
            print(f"构造函数 (ee.ClassName): {constructor_operations}")
            print(f"JS语句 (require/print等): {js_statements}")
            print(f"潜在的真正算子: {len(potential_operators)}")

            # 3. 分析潜在算子
            print("\n" + "=" * 70)
            print("潜在算子的方法名统计 (Top 30)")
            print("=" * 70)

            method_names = []
            for op_chain in potential_operators:
                if '.' in op_chain:
                    parts = op_chain.split('.')
                    for part in parts[1:]:  # 跳过第一个（可能是变量名）
                        if part and not part.startswith('_'):
                            method_names.append(part.lower())
                else:
                    method_names.append(op_chain.lower())

            method_counter = Counter(method_names)

            print("\n最常见的未匹配方法:")
            for method, count in method_counter.most_common(30):
                # 检查是否在GEE算子库中存在
                result = session.run("""
                    MATCH (gee:GEE_Operator)
                    WHERE toLower(gee.name) CONTAINS $method
                    RETURN count(gee) AS found
                """, {"method": method})

                found = result.single()['found']
                status = "FOUND" if found > 0 else "MISSING"
                print(f"  {method:25s} {count:5d}次  [{status}]")

            # 4. 检查大小写问题
            print("\n" + "=" * 70)
            print("大小写匹配问题检查")
            print("=" * 70)

            # 检查几个已知的算子
            test_methods = ['filterbounds', 'filterdate', 'addlayer', 'select', 'map']

            for method in test_methods:
                result = session.run("""
                    MATCH (gee:GEE_Operator)
                    WHERE toLower(gee.name) CONTAINS $method
                    RETURN gee.name AS name
                    LIMIT 5
                """, {"method": method})

                matches = [r['name'] for r in result]
                if matches:
                    print(f"\n'{method}' 的GEE算子:")
                    for m in matches[:3]:
                        print(f"  - {m}")

            # 5. 查看成功匹配的案例
            print("\n" + "=" * 70)
            print("成功匹配的案例分析 (采样10个)")
            print("=" * 70)

            result = session.run("""
                MATCH (exec:Execution)-[:hasOperation]->(gee:GEE_Operator)
                RETURN exec.operation_chain AS op_chain,
                       collect(DISTINCT gee.name)[0..3] AS operators
                LIMIT 10
            """)

            for record in result:
                print(f"\n操作链: {record['op_chain']}")
                print(f"  -> 匹配: {', '.join(record['operators'])}")

            # 6. 统计GEE算子名称格式
            print("\n" + "=" * 70)
            print("GEE算子名称格式分析")
            print("=" * 70)

            result = session.run("""
                MATCH (gee:GEE_Operator)
                WHERE gee.name CONTAINS "filter"
                RETURN gee.name AS name
                LIMIT 20
            """)

            print("\n包含'filter'的GEE算子样本:")
            for record in result:
                print(f"  {record['name']}")

    finally:
        driver.close()


if __name__ == "__main__":
    analyze_matching_issues()
