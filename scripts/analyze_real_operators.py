# -*- coding: utf-8 -*-
"""
精确分析真正的GEE算子未匹配情况
"""

from neo4j import GraphDatabase


def analyze_real_operator_matching():
    """分析真正的GEE算子匹配情况"""
    NEO4J_URI = "bolt://localhost:7687"
    NEO4J_USER = "neo4j"
    NEO4J_PASSWORD = "12345678"
    NEO4J_DATABASE = "neo4j"

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    # 定义应该被过滤的非算子操作
    NON_OPERATORS = {
        # UI元素
        'ui.panel', 'ui.button', 'ui.label', 'ui.textbox', 'ui.slider',
        'ui.checkbox', 'ui.select', 'ui.dateslider', 'ui.chart',
        # Map方法
        'addlayer', 'centerlayer', 'centerobject', 'setcenter',
        # 构造函数（单独的类名，不带方法）
        'ee.imagecollection', 'ee.featurecollection', 'ee.image', 'ee.feature',
        'ee.geometry', 'ee.date', 'ee.number', 'ee.string', 'ee.list', 'ee.dictionary',
        # JS语句
        'require', 'print', 'return', 'var', 'function', 'console',
    }

    try:
        with driver.session(database=NEO4J_DATABASE) as session:
            print("=" * 70)
            print("真正的GEE算子匹配情况分析")
            print("=" * 70)

            # 1. 获取所有未匹配的Execution
            result = session.run("""
                MATCH (exec:Execution)
                WHERE NOT (exec)-[:hasOperation]->(:GEE_Operator)
                RETURN exec.operation_chain AS op_chain
            """)

            unmatched_operations = [r['op_chain'] for r in result]
            total_unmatched = len(unmatched_operations)

            print(f"\n总未匹配Execution: {total_unmatched}")

            # 2. 分类统计
            ui_count = 0
            map_count = 0
            constructor_count = 0
            js_count = 0
            potential_real_operators = []

            for op_chain in unmatched_operations:
                op_lower = op_chain.lower()

                # 检查是否是非算子操作
                is_non_operator = False

                # UI元素
                if op_lower.startswith('ui.'):
                    ui_count += 1
                    is_non_operator = True
                # Map方法
                elif any(map_method in op_lower for map_method in ['addlayer', 'centerobject', 'setcenter']):
                    map_count += 1
                    is_non_operator = True
                # JS语句
                elif op_chain in ['require', 'print', 'return', 'var', 'function', 'console']:
                    js_count += 1
                    is_non_operator = True
                # 构造函数（单独的ee.ClassName，没有方法调用）
                elif op_chain.startswith('ee.') and '.' not in op_chain[3:]:
                    constructor_count += 1
                    is_non_operator = True

                if not is_non_operator:
                    potential_real_operators.append(op_chain)

            print(f"\n非算子操作统计:")
            print(f"  UI元素: {ui_count}")
            print(f"  Map方法: {map_count}")
            print(f"  构造函数: {constructor_count}")
            print(f"  JS语句: {js_count}")
            print(f"  小计: {ui_count + map_count + constructor_count + js_count}")

            print(f"\n潜在的真正算子（未匹配）: {len(potential_real_operators)}")

            # 3. 分析潜在真正算子
            print("\n" + "=" * 70)
            print("未匹配的潜在真正算子分析")
            print("=" * 70)

            from collections import Counter

            # 提取方法名
            method_names = []
            for op_chain in potential_real_operators:
                if '.' in op_chain:
                    parts = op_chain.split('.')
                    # 提取最后的方法名
                    last_part = parts[-1]
                    if last_part and not last_part.startswith('_'):
                        method_names.append(last_part.lower())

            method_counter = Counter(method_names)

            print("\n最常见的未匹配方法 (Top 30):")
            for method, count in method_counter.most_common(30):
                # 检查是否在GEE算子库中
                result = session.run("""
                    MATCH (gee:GEE_Operator)
                    WHERE toLower(gee.name) CONTAINS $method
                    RETURN count(gee) AS found
                """, {"method": method})

                found = result.single()['found']

                if found > 0:
                    # 在库中找到了，但没匹配上
                    print(f"  {method:30s} {count:5d}次  [在库中但未匹配] <-- 问题！")
                else:
                    # 不在库中（可能是自定义函数或新API）
                    print(f"  {method:30s} {count:5d}次  [不在GEE算子库]")

            # 4. 计算真正的问题算子数量
            print("\n" + "=" * 70)
            print("核心问题总结")
            print("=" * 70)

            # 统计在库中但未匹配的方法
            in_lib_but_unmatched = 0
            not_in_lib = 0

            for method, count in method_counter.items():
                result = session.run("""
                    MATCH (gee:GEE_Operator)
                    WHERE toLower(gee.name) CONTAINS $method
                    RETURN count(gee) AS found
                """, {"method": method})

                found = result.single()['found']

                if found > 0:
                    in_lib_but_unmatched += count
                else:
                    not_in_lib += count

            print(f"\n真正的GEE算子（应该匹配但没匹配）: ~{in_lib_but_unmatched} 个")
            print(f"不在GEE算子库的操作（自定义函数/新API）: ~{not_in_lib} 个")
            print(f"非算子操作（UI/Map/JS等）: {ui_count + map_count + constructor_count + js_count} 个")

            # 5. 计算实际匹配率
            total_exec = session.run("MATCH (e:Execution) RETURN count(e) AS c").single()['c']
            matched_exec = session.run("""
                MATCH (e:Execution)-[:hasOperation]->(:GEE_Operator)
                RETURN count(DISTINCT e) AS c
            """).single()['c']

            # 应该匹配的Execution = 总数 - 非算子操作
            should_match = total_exec - (ui_count + map_count + constructor_count + js_count)

            print(f"\n" + "=" * 70)
            print("实际匹配率计算")
            print("=" * 70)
            print(f"总Execution节点: {total_exec}")
            print(f"非算子操作（应排除）: {ui_count + map_count + constructor_count + js_count}")
            print(f"真正的算子操作: {should_match}")
            print(f"已匹配: {matched_exec}")
            print(f"实际匹配率: {matched_exec/should_match*100:.2f}%")

    finally:
        driver.close()


if __name__ == "__main__":
    analyze_real_operator_matching()
