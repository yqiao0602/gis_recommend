# -*- coding: utf-8 -*-
"""
检查映射和算子问题
"""

from neo4j import GraphDatabase


def check_issues():
    """检查L3映射和GEE算子问题"""
    NEO4J_URI = "bolt://localhost:7687"
    NEO4J_USER = "neo4j"
    NEO4J_PASSWORD = "12345678"
    NEO4J_DATABASE = "neo4j"

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    try:
        with driver.session(database=NEO4J_DATABASE) as session:
            # 1. 检查L3_01_01_01是否真的没有映射
            print("=" * 70)
            print("[检查1] L3_01_01_01的映射情况")
            print("=" * 70)

            result = session.run("""
                MATCH (l3:L3_Primitive {code: "L3_01_01_01"})
                      <-[:maps_to_l3]-(op)
                RETURN labels(op)[0] AS platform, op.name AS operator
            """)

            mappings = list(result)
            if mappings:
                print(f"\n找到 {len(mappings)} 个映射:")
                for m in mappings:
                    print(f"  - [{m['platform']}] {m['operator']}")
            else:
                print("\n确实没有映射到L3_01_01_01")

            # 2. 查看有映射的L3示例
            print("\n" + "=" * 70)
            print("[检查2] 查看有映射的L3示例")
            print("=" * 70)

            result = session.run("""
                MATCH (l3:L3_Primitive)<-[:maps_to_l3]-(op)
                WITH l3, count(op) AS mapping_count
                WHERE mapping_count > 0
                RETURN l3.code AS l3_code,
                       l3.name AS l3_name,
                       mapping_count
                ORDER BY mapping_count DESC
                LIMIT 5
            """)

            print("\n映射最多的5个L3:")
            for record in result:
                print(f"  {record['l3_code']}: {record['l3_name']}")
                print(f"    映射数量: {record['mapping_count']}")

            # 3. 检查GEE算子名称格式
            print("\n" + "=" * 70)
            print("[检查3] GEE算子名称格式")
            print("=" * 70)

            # 查找包含focal的算子
            result = session.run("""
                MATCH (gee:GEE_Operator)
                WHERE gee.name CONTAINS "focal"
                RETURN gee.name AS name
                LIMIT 10
            """)

            print("\n包含'focal'的GEE算子:")
            focal_ops = list(result)
            if focal_ops:
                for op in focal_ops:
                    print(f"  - {op['name']}")
            else:
                print("  没有找到包含'focal'的算子")

            # 4. 查看实际的GEE算子名称样例
            result = session.run("""
                MATCH (gee:GEE_Operator)
                WHERE gee.name CONTAINS "Image"
                RETURN gee.name AS name
                LIMIT 20
            """)

            print("\n包含'Image'的GEE算子样例 (前20个):")
            for op in result:
                print(f"  - {op['name']}")

            # 5. 统计GEE算子名称格式
            result = session.run("""
                MATCH (gee:GEE_Operator)
                WITH gee.name AS name
                WHERE name STARTS WITH "ee."
                RETURN count(*) AS count_with_ee
            """)
            count_with_ee = result.single()['count_with_ee']

            result = session.run("""
                MATCH (gee:GEE_Operator)
                RETURN count(*) AS total
            """)
            total = result.single()['total']

            print(f"\n" + "=" * 70)
            print("[检查4] GEE算子名称格式统计")
            print("=" * 70)
            print(f"总GEE算子数: {total}")
            print(f"以'ee.'开头的: {count_with_ee}")
            print(f"不以'ee.'开头的: {total - count_with_ee}")

    finally:
        driver.close()


if __name__ == "__main__":
    check_issues()
