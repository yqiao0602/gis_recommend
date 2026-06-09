# -*- coding: utf-8 -*-
"""
检查GEE算子库中是否包含被过滤的方法
"""

from neo4j import GraphDatabase


def check_filtered_methods_in_gee():
    """检查被过滤的方法是否在GEE算子库中"""
    NEO4J_URI = "bolt://localhost:7687"
    NEO4J_USER = "neo4j"
    NEO4J_PASSWORD = "12345678"
    NEO4J_DATABASE = "neo4j"

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    try:
        with driver.session(database=NEO4J_DATABASE) as session:
            print("=" * 70)
            print("检查被过滤的方法是否在GEE算子库中")
            print("=" * 70)

            # 1. 检查UI相关
            print("\n[1] 包含'ui'的GEE算子:")
            result = session.run("""
                MATCH (gee:GEE_Operator)
                WHERE toLower(gee.name) CONTAINS 'ui'
                RETURN gee.name AS name
                LIMIT 20
            """)
            count = 0
            for record in result:
                print(f"  - {record['name']}")
                count += 1
            if count == 0:
                print("  (无)")

            # 2. 检查Map相关
            print("\n[2] 包含'map'的GEE算子:")
            result = session.run("""
                MATCH (gee:GEE_Operator)
                WHERE toLower(gee.name) CONTAINS 'map'
                RETURN gee.name AS name
                LIMIT 20
            """)
            count = 0
            for record in result:
                print(f"  - {record['name']}")
                count += 1
            if count == 0:
                print("  (无)")

            # 3. 检查ImageCollection
            print("\n[3] ImageCollection相关的GEE算子:")
            result = session.run("""
                MATCH (gee:GEE_Operator)
                WHERE toLower(gee.name) CONTAINS 'imagecollection'
                RETURN gee.name AS name
                LIMIT 20
            """)
            count = 0
            for record in result:
                print(f"  - {record['name']}")
                count += 1
            if count == 0:
                print("  (无)")

            # 4. 检查addLayer
            print("\n[4] 包含'addlayer'的GEE算子:")
            result = session.run("""
                MATCH (gee:GEE_Operator)
                WHERE toLower(gee.name) CONTAINS 'addlayer'
                RETURN gee.name AS name
            """)
            count = 0
            for record in result:
                print(f"  - {record['name']}")
                count += 1
            if count == 0:
                print("  (无)")

            # 5. 统计以ee.map, ee.ui开头的算子
            print("\n[5] 以'ee.map'或'ee.ui'开头的GEE算子:")
            result = session.run("""
                MATCH (gee:GEE_Operator)
                WHERE toLower(gee.name) STARTS WITH 'ee.map'
                   OR toLower(gee.name) STARTS WITH 'ee.ui'
                RETURN gee.name AS name
            """)
            count = 0
            for record in result:
                print(f"  - {record['name']}")
                count += 1
            if count == 0:
                print("  (无)")

            # 6. 检查所有算子的前缀统计
            print("\n[6] GEE算子的前缀统计 (ee.XXX):")
            result = session.run("""
                MATCH (gee:GEE_Operator)
                WITH gee.name AS name,
                     split(toLower(gee.name), '.')[1] AS prefix
                WHERE prefix IS NOT NULL
                RETURN prefix, count(*) AS count
                ORDER BY count DESC
                LIMIT 15
            """)

            for record in result:
                print(f"  ee.{record['prefix']:20s}: {record['count']:4d}个")

    finally:
        driver.close()


if __name__ == "__main__":
    check_filtered_methods_in_gee()
