# -*- coding: utf-8 -*-
"""
检查L3映射是否已导入到Neo4j
"""

from neo4j import GraphDatabase
import json
import os


def check_l3_mappings():
    """检查L3映射情况"""
    NEO4J_URI = "bolt://localhost:7687"
    NEO4J_USER = "neo4j"
    NEO4J_PASSWORD = "12345678"
    NEO4J_DATABASE = "neo4j"

    L3_DIR = r"E:\02_projects\03_PythonProject\recommend-system\Operator-recommend-system\Algorithm_classification\L3_classification"

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    try:
        with driver.session(database=NEO4J_DATABASE) as session:
            print("=" * 70)
            print("检查L3映射关系")
            print("=" * 70)

            # 1. 统计数据库中的映射关系
            print("\n[1] 数据库中的映射关系统计:")
            result = session.run("""
                MATCH (l3:L3)
                OPTIONAL MATCH (l3)<-[:mapsTo]-(gee:GEE_Operator)
                OPTIONAL MATCH (l3)<-[:mapsTo]-(qgis:QGIS_Operator)
                RETURN l3.code AS l3_code,
                       l3.name AS l3_name,
                       count(DISTINCT gee) AS gee_count,
                       count(DISTINCT qgis) AS qgis_count
                ORDER BY gee_count + qgis_count DESC
                LIMIT 10
            """)

            print("\n有映射的L3节点 (Top 10):")
            total_l3_with_mappings = 0
            for record in result:
                if record['gee_count'] > 0 or record['qgis_count'] > 0:
                    total_l3_with_mappings += 1
                    print(f"  {record['l3_code']:15s} - GEE: {record['gee_count']:3d}, QGIS: {record['qgis_count']:3d}")

            # 2. 统计总体情况
            result = session.run("""
                MATCH (l3:L3)
                OPTIONAL MATCH (l3)<-[:mapsTo]-(gee:GEE_Operator)
                OPTIONAL MATCH (l3)<-[:mapsTo]-(qgis:QGIS_Operator)
                WITH l3,
                     count(DISTINCT gee) AS gee_count,
                     count(DISTINCT qgis) AS qgis_count
                RETURN count(l3) AS total_l3,
                       sum(CASE WHEN gee_count > 0 THEN 1 ELSE 0 END) AS l3_with_gee,
                       sum(CASE WHEN qgis_count > 0 THEN 1 ELSE 0 END) AS l3_with_qgis,
                       sum(gee_count) AS total_gee_mappings,
                       sum(qgis_count) AS total_qgis_mappings
            """)

            record = result.single()
            print("\n数据库中的总体情况:")
            print(f"  总L3节点数: {record['total_l3']}")
            print(f"  有GEE映射的L3: {record['l3_with_gee']}")
            print(f"  有QGIS映射的L3: {record['l3_with_qgis']}")
            print(f"  GEE映射关系总数: {record['total_gee_mappings']}")
            print(f"  QGIS映射关系总数: {record['total_qgis_mappings']}")

            # 3. 读取映射文件统计
            print("\n[2] L3映射文件统计:")

            gee_mapping_files = []
            qgis_mapping_files = []

            gee_dir = os.path.join(L3_DIR, "GEE")
            qgis_dir = os.path.join(L3_DIR, "QGIS")

            if os.path.exists(gee_dir):
                gee_mapping_files = [f for f in os.listdir(gee_dir) if f.endswith('.json')]
            if os.path.exists(qgis_dir):
                qgis_mapping_files = [f for f in os.listdir(qgis_dir) if f.endswith('.json')]

            print(f"\nGEE映射文件: {len(gee_mapping_files)}个")
            print(f"QGIS映射文件: {len(qgis_mapping_files)}个")

            # 4. 读取映射文件详情
            total_gee_operators_in_files = 0
            total_qgis_operators_in_files = 0
            total_gee_mappings_in_files = 0
            total_qgis_mappings_in_files = 0

            print("\nGEE映射文件详情:")
            for filename in sorted(gee_mapping_files):
                filepath = os.path.join(gee_dir, filename)
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    stats = data.get('statistics', {})
                    total_ops = stats.get('total_operators', 0)
                    mapped = stats.get('mapped', 0)
                    mapping_rate = stats.get('mapping_rate', 0)

                    total_gee_operators_in_files += total_ops
                    total_gee_mappings_in_files += mapped

                    print(f"  {filename:40s}: {total_ops:3d}个算子, {mapped:3d}个映射, 映射率{mapping_rate:.1f}%")

            print("\nQGIS映射文件详情:")
            for filename in sorted(qgis_mapping_files):
                filepath = os.path.join(qgis_dir, filename)
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    stats = data.get('statistics', {})
                    total_ops = stats.get('total_operators', 0)
                    mapped = stats.get('mapped', 0)
                    mapping_rate = stats.get('mapping_rate', 0)

                    total_qgis_operators_in_files += total_ops
                    total_qgis_mappings_in_files += mapped

                    print(f"  {filename:40s}: {total_ops:3d}个算子, {mapped:3d}个映射, 映射率{mapping_rate:.1f}%")

            print("\n映射文件总计:")
            print(f"  GEE算子总数: {total_gee_operators_in_files}")
            print(f"  GEE映射总数: {total_gee_mappings_in_files}")
            print(f"  QGIS算子总数: {total_qgis_operators_in_files}")
            print(f"  QGIS映射总数: {total_qgis_mappings_in_files}")

            # 5. 对比结果
            print("\n[3] 对比结果:")
            print(f"  GEE映射:")
            print(f"    文件中: {total_gee_mappings_in_files}个")
            print(f"    数据库: {record['total_gee_mappings']}个")
            if record['total_gee_mappings'] < total_gee_mappings_in_files:
                print(f"    ❌ 缺少 {total_gee_mappings_in_files - record['total_gee_mappings']}个映射")
            elif record['total_gee_mappings'] == total_gee_mappings_in_files:
                print(f"    ✅ 已全部导入")
            else:
                print(f"    ⚠️ 数据库中多于文件")

            print(f"  QGIS映射:")
            print(f"    文件中: {total_qgis_mappings_in_files}个")
            print(f"    数据库: {record['total_qgis_mappings']}个")
            if record['total_qgis_mappings'] < total_qgis_mappings_in_files:
                print(f"    ❌ 缺少 {total_qgis_mappings_in_files - record['total_qgis_mappings']}个映射")
            elif record['total_qgis_mappings'] == total_qgis_mappings_in_files:
                print(f"    ✅ 已全部导入")
            else:
                print(f"    ⚠️ 数据库中多于文件")

            # 6. 检查具体案例
            print("\n[4] 检查具体案例:")

            # 读取第一个GEE映射文件
            if gee_mapping_files:
                filepath = os.path.join(gee_dir, gee_mapping_files[0])
                with open(filepath, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    results = data.get('results', [])
                    if results:
                        # 检查前3个算子的映射
                        print(f"\n检查 {gee_mapping_files[0]} 中的前3个算子:")
                        for i, mapping in enumerate(results[:3]):
                            operator = mapping.get('operator', '')
                            mapped_l3s = mapping.get('mapped_l3s', [])

                            print(f"\n  算子: {operator}")
                            print(f"  映射到 {len(mapped_l3s)} 个L3:")
                            for l3 in mapped_l3s:
                                l3_code = l3.get('l3_code', '')
                                l3_name = l3.get('l3_name', '')
                                print(f"    - {l3_code}: {l3_name}")

                                # 检查数据库中是否存在
                                result = session.run("""
                                    MATCH (gee:GEE_Operator {name: $op_name})
                                    MATCH (l3:L3 {code: $l3_code})
                                    OPTIONAL MATCH (gee)-[r:mapsTo]->(l3)
                                    RETURN gee.name AS gee_name,
                                           l3.code AS l3_code,
                                           r IS NOT NULL AS has_mapping
                                """, {"op_name": operator, "l3_code": l3_code})

                                record = result.single()
                                if record:
                                    if record['has_mapping']:
                                        print(f"      ✅ 映射已存在")
                                    else:
                                        print(f"      ❌ 映射不存在")
                                else:
                                    print(f"      ⚠️ GEE算子或L3节点不存在")

    finally:
        driver.close()


if __name__ == "__main__":
    check_l3_mappings()
