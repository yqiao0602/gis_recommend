# -*- coding: utf-8 -*-
"""
诊断匹配失败的根本原因
"""

from neo4j import GraphDatabase


def diagnose_matching_failure():
    """诊断为什么存在的算子没匹配上"""
    NEO4J_URI = "bolt://localhost:7687"
    NEO4J_USER = "neo4j"
    NEO4J_PASSWORD = "12345678"
    NEO4J_DATABASE = "neo4j"

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    try:
        with driver.session(database=NEO4J_DATABASE) as session:
            print("=" * 70)
            print("诊断匹配失败原因")
            print("=" * 70)

            # 测试几个应该匹配但没匹配的算子
            test_methods = [
                'addbands',
                'filterdate',
                'filterbounds',
                'updatemask',
                'sampleregions'
            ]

            for method in test_methods:
                print(f"\n{'='*70}")
                print(f"测试方法: {method}")
                print(f"{'='*70}")

                # 1. 检查GEE算子库中是否存在
                result = session.run("""
                    MATCH (gee:GEE_Operator)
                    WHERE toLower(gee.name) CONTAINS $method
                    RETURN gee.name AS name
                    LIMIT 5
                """, {"method": method})

                gee_operators = [r['name'] for r in result]
                print(f"\nGEE算子库中的匹配 ({len(gee_operators)}个):")
                for op in gee_operators:
                    print(f"  - {op}")

                # 2. 查看工作流中包含该方法的操作链示例
                result = session.run("""
                    MATCH (exec:Execution)
                    WHERE NOT (exec)-[:hasOperation]->(:GEE_Operator)
                      AND toLower(exec.operation_chain) CONTAINS $method
                    RETURN exec.operation_chain AS op_chain
                    LIMIT 5
                """, {"method": method})

                unmatched_chains = [r['op_chain'] for r in result]
                print(f"\n未匹配的操作链示例 ({len(unmatched_chains)}个):")
                for chain in unmatched_chains:
                    print(f"  - {chain}")

                # 3. 查看已匹配的操作链示例
                result = session.run("""
                    MATCH (exec:Execution)-[:hasOperation]->(gee:GEE_Operator)
                    WHERE toLower(exec.operation_chain) CONTAINS $method
                    RETURN exec.operation_chain AS op_chain,
                           collect(gee.name)[0..2] AS matched_ops
                    LIMIT 3
                """, {"method": method})

                matched_cases = list(result)
                if matched_cases:
                    print(f"\n已匹配的操作链示例:")
                    for case in matched_cases:
                        print(f"  - {case['op_chain']}")
                        print(f"    -> 匹配到: {', '.join(case['matched_ops'])}")
                else:
                    print(f"\n没有已匹配的操作链包含 '{method}'")

            # 4. 深度分析一个具体案例
            print("\n" + "=" * 70)
            print("深度案例分析: filterdate")
            print("=" * 70)

            # 查看所有包含filterdate但未匹配的操作链
            result = session.run("""
                MATCH (exec:Execution)
                WHERE NOT (exec)-[:hasOperation]->(:GEE_Operator)
                  AND toLower(exec.operation_chain) CONTAINS 'filterdate'
                RETURN exec.operation_chain AS op_chain,
                       exec.id AS exec_id
                LIMIT 20
            """)

            print("\n未匹配的'filterdate'操作链 (前20个):")
            for i, record in enumerate(result, 1):
                print(f"{i:2d}. {record['op_chain']}")

            # 5. 检查匹配逻辑的实际行为
            print("\n" + "=" * 70)
            print("检查当前匹配逻辑")
            print("=" * 70)

            # 模拟当前的匹配逻辑
            print("\n当前匹配策略:")
            print("1. 从操作链中提取方法名")
            print("2. 在GEE算子缓存中查找")
            print("3. 如果找到多个候选，返回最短的")

            # 检查缓存构建
            result = session.run("""
                MATCH (gee:GEE_Operator)
                WHERE gee.name CONTAINS "filterdate"
                RETURN gee.name AS name
            """)

            print("\n包含'filterdate'的GEE算子:")
            for record in result:
                parts = record['name'].split('.')
                method_name = parts[-1] if parts else record['name']
                print(f"  {record['name']}")
                print(f"    -> 提取的方法名: '{method_name}'")

            # 6. 检查一个典型的未匹配案例
            print("\n" + "=" * 70)
            print("典型未匹配案例分析")
            print("=" * 70)

            result = session.run("""
                MATCH (exec:Execution)
                WHERE NOT (exec)-[:hasOperation]->(:GEE_Operator)
                  AND exec.operation_chain CONTAINS "filterDate"
                RETURN exec.operation_chain AS op_chain
                LIMIT 1
            """)

            record = result.single()
            if record:
                op_chain = record['op_chain']
                print(f"\n操作链: {op_chain}")

                # 模拟解析
                parts = op_chain.split('.')
                print(f"分割后: {parts}")

                operators = []
                for part in parts[1:]:
                    if part and not part.startswith('_'):
                        operators.append(part)

                print(f"提取的操作符: {operators}")

                # 检查这些操作符是否能匹配
                for op in operators:
                    result = session.run("""
                        MATCH (gee:GEE_Operator)
                        WHERE toLower(gee.name) = toLower($full_name)
                           OR gee.name ENDS WITH $op
                        RETURN gee.name AS name
                        LIMIT 3
                    """, {"op": f".{op}", "full_name": f"ee.{op}"})

                    matches = [r['name'] for r in result]
                    if matches:
                        print(f"  '{op}' 可能匹配: {matches}")
                    else:
                        print(f"  '{op}' 无法匹配")

    finally:
        driver.close()


if __name__ == "__main__":
    diagnose_matching_failure()
