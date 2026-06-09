# -*- coding: utf-8 -*-
"""
快速更新平台映射关系脚本
只导入GEE和QGIS到L3的映射关系，不影响其他数据
"""

import json
import os
from neo4j import GraphDatabase
from tqdm import tqdm


def update_platform_mappings():
    """更新GEE和QGIS到L3的映射关系"""

    # 配置
    NEO4J_URI = "bolt://localhost:7687"
    NEO4J_USER = "neo4j"
    NEO4J_PASSWORD = "12345678"
    NEO4J_DATABASE = "neo4j"

    DATA_DIR = r"E:\02_projects\03_PythonProject\recommend-system\Operator-recommend-system"

    # 映射文件路径
    gee_mapping_path = os.path.join(
        DATA_DIR,
        "Algorithm_classification",
        "L3_classification",
        "GEE",
        "GEE_to_L3_03_Mapping_Full.json"
    )
    qgis_mapping_path = os.path.join(
        DATA_DIR,
        "Algorithm_classification",
        "L3_classification",
        "QGIS",
        "QGIS_to_L3_03_Mapping_Full.json"
    )

    print("=" * 70)
    print("更新平台映射关系")
    print("=" * 70)

    # 连接Neo4j
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))

    try:
        with driver.session(database=NEO4J_DATABASE) as session:
            gee_count = 0
            qgis_count = 0

            # 1. GEE → L3映射
            if os.path.exists(gee_mapping_path):
                print(f"\n[1/2] 导入GEE→L3映射...")
                print(f"  文件: {gee_mapping_path}")

                with open(gee_mapping_path, 'r', encoding='utf-8') as f:
                    gee_mapping = json.load(f)

                print(f"  读取GEE→L3映射: {len(gee_mapping.get('results', []))} 个")

                for item in tqdm(gee_mapping.get('results', []), desc="  GEE→L3"):
                    if item.get('status') == 'MAPPED':
                        gee_op = item['operator']
                        for l3_map in item.get('mapped_l3s', []):
                            l3_code = l3_map['l3_code']
                            confidence = l3_map.get('confidence', 1.0)

                            # 创建映射关系
                            session.run("""
                                MATCH (gee:GEE_Operator {name: $gee_op})
                                MATCH (l3:L3_Primitive {code: $l3_code})
                                MERGE (gee)-[r:maps_to_l3]->(l3)
                                SET r.confidence = $confidence,
                                    r.mapping_method = 'manual'
                            """, {
                                "gee_op": gee_op,
                                "l3_code": l3_code,
                                "confidence": confidence
                            })
                            gee_count += 1

                print(f"  [OK] GEE→L3映射完成: {gee_count} 条关系")
            else:
                print(f"\n[!] 未找到GEE映射文件: {gee_mapping_path}")

            # 2. QGIS → L3映射
            if os.path.exists(qgis_mapping_path):
                print(f"\n[2/2] 导入QGIS→L3映射...")
                print(f"  文件: {qgis_mapping_path}")

                with open(qgis_mapping_path, 'r', encoding='utf-8') as f:
                    qgis_mapping = json.load(f)

                print(f"  读取QGIS→L3映射: {len(qgis_mapping.get('results', []))} 个")

                for item in tqdm(qgis_mapping.get('results', []), desc="  QGIS→L3"):
                    if item.get('status') == 'MAPPED':
                        qgis_op_name = item['operator']
                        for l3_map in item.get('mapped_l3s', []):
                            l3_code = l3_map['l3_code']
                            confidence = l3_map.get('confidence', 1.0)

                            # 创建映射关系
                            session.run("""
                                MATCH (qgis:QGIS_Operator {name: $qgis_op})
                                MATCH (l3:L3_Primitive {code: $l3_code})
                                MERGE (qgis)-[r:maps_to_l3]->(l3)
                                SET r.confidence = $confidence,
                                    r.mapping_method = 'manual'
                            """, {
                                "qgis_op": qgis_op_name,
                                "l3_code": l3_code,
                                "confidence": confidence
                            })
                            qgis_count += 1

                print(f"  [OK] QGIS→L3映射完成: {qgis_count} 条关系")
            else:
                print(f"\n[!] 未找到QGIS映射文件: {qgis_mapping_path}")

            # 统计结果
            result = session.run("""
                MATCH ()-[r:maps_to_l3]->()
                RETURN count(r) AS total
            """)
            total_mappings = result.single()['total']

            print("\n" + "=" * 70)
            print("映射更新完成！")
            print("=" * 70)
            print(f"  GEE→L3: {gee_count} 条")
            print(f"  QGIS→L3: {qgis_count} 条")
            print(f"  总计: {total_mappings} 条maps_to_l3关系")
            print("=" * 70)

    finally:
        driver.close()


if __name__ == "__main__":
    update_platform_mappings()
