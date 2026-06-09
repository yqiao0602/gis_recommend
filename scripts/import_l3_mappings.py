# -*- coding: utf-8 -*-
"""
导入算子到L3的映射关系
"""

import argparse
import json
import os
import sys
from pathlib import Path
from neo4j import GraphDatabase
from tqdm import tqdm

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
if SCRIPT_DIR not in sys.path:
    sys.path.append(SCRIPT_DIR)

from build_ontology_kg import (
    LEGACY_ID_MAPPINGS_CANDIDATES,
    V2_ID_MAPPINGS_CANDIDATES,
    load_platform_mapping_results,
    resolve_input_path,
    resolve_project_data_dir,
)


class L3MappingImporter:
    """L3映射关系导入器"""

    def __init__(self, neo4j_uri, neo4j_user, neo4j_password, database="neo4j"):
        self.driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        self.database = database
        print(f"已连接到Neo4j: {neo4j_uri}, 数据库: {database}")

        self.stats = {
            'gee_total': 0,
            'gee_success': 0,
            'gee_operator_not_found': 0,
            'gee_l3_not_found': 0,
            'qgis_total': 0,
            'qgis_success': 0,
            'qgis_operator_not_found': 0,
            'qgis_l3_not_found': 0,
        }

    def close(self):
        self.driver.close()

    def import_gee_mappings(self, gee_mapping_dir):
        """导入GEE算子到L3的映射"""
        print("\n" + "=" * 70)
        print("导入GEE算子到L3的映射")
        print("=" * 70)

        # 获取所有GEE映射文件
        mapping_files = [f for f in os.listdir(gee_mapping_dir) if f.endswith('.json')]
        mapping_files.sort()

        print(f"\n找到 {len(mapping_files)} 个GEE映射文件")

        for filename in mapping_files:
            filepath = os.path.join(gee_mapping_dir, filename)
            print(f"\n处理: {filename}")

            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            results = data.get('results', [])
            print(f"  包含 {len(results)} 个算子映射")

            # 导入每个映射
            for result in tqdm(results, desc=f"  导入{filename}"):
                operator_name = result.get('operator', '')
                status = result.get('status', '')
                mapped_l3s = result.get('mapped_l3s', [])

                # 只导入已映射的
                if status != 'MAPPED' or not mapped_l3s:
                    continue

                # 对每个映射的L3创建关系
                for l3_mapping in mapped_l3s:
                    l3_code = l3_mapping.get('l3_code', '')
                    confidence = l3_mapping.get('confidence', 1.0)

                    self.stats['gee_total'] += 1

                    success = self.create_mapping(
                        operator_name,
                        l3_code,
                        confidence,
                        platform='GEE'
                    )

                    if success == 'success':
                        self.stats['gee_success'] += 1
                    elif success == 'operator_not_found':
                        self.stats['gee_operator_not_found'] += 1
                    elif success == 'l3_not_found':
                        self.stats['gee_l3_not_found'] += 1

    def import_qgis_mappings(self, qgis_mapping_dir):
        """导入QGIS算子到L3的映射"""
        print("\n" + "=" * 70)
        print("导入QGIS算子到L3的映射")
        print("=" * 70)

        # 获取所有QGIS映射文件
        mapping_files = [f for f in os.listdir(qgis_mapping_dir) if f.endswith('.json')]
        mapping_files.sort()

        print(f"\n找到 {len(mapping_files)} 个QGIS映射文件")

        for filename in mapping_files:
            filepath = os.path.join(qgis_mapping_dir, filename)
            print(f"\n处理: {filename}")

            with open(filepath, 'r', encoding='utf-8') as f:
                data = json.load(f)

            results = data.get('results', [])
            print(f"  包含 {len(results)} 个算子映射")

            # 导入每个映射
            for result in tqdm(results, desc=f"  导入{filename}"):
                operator_name = result.get('operator', '')
                status = result.get('status', '')
                mapped_l3s = result.get('mapped_l3s', [])

                # 只导入已映射的
                if status != 'MAPPED' or not mapped_l3s:
                    continue

                # 对每个映射的L3创建关系
                for l3_mapping in mapped_l3s:
                    l3_code = l3_mapping.get('l3_code', '')
                    confidence = l3_mapping.get('confidence', 1.0)

                    self.stats['qgis_total'] += 1

                    success = self.create_mapping(
                        operator_name,
                        l3_code,
                        confidence,
                        platform='QGIS'
                    )

                    if success == 'success':
                        self.stats['qgis_success'] += 1
                    elif success == 'operator_not_found':
                        self.stats['qgis_operator_not_found'] += 1
                    elif success == 'l3_not_found':
                        self.stats['qgis_l3_not_found'] += 1

    def import_id_mappings(self, id_mappings_path):
        """从 v2 id_mappings 文件导入 GEE/QGIS → L3 映射。"""
        print("\n" + "=" * 70)
        print("导入v2 id_mappings中的GEE/QGIS到L3映射")
        print("=" * 70)

        self._import_platform_mapping_file(id_mappings_path, platform='gee')
        self._import_platform_mapping_file(id_mappings_path, platform='qgis')

    def _import_platform_mapping_file(self, mapping_path, platform):
        results = load_platform_mapping_results(mapping_path, platform)
        print(f"\n读取{platform.upper()}映射: {len(results)} 个")

        for result in tqdm(results, desc=f"  导入{platform.upper()}"):
            operator_name = result.get('operator', '')
            status = result.get('status', '')
            mapped_l3s = result.get('mapped_l3s', [])

            if status != 'MAPPED' or not mapped_l3s:
                continue

            for l3_mapping in mapped_l3s:
                l3_code = l3_mapping.get('l3_code', '')
                confidence = l3_mapping.get('confidence', 1.0)

                if platform == 'gee':
                    self.stats['gee_total'] += 1
                else:
                    self.stats['qgis_total'] += 1

                success = self.create_mapping(
                    operator_name,
                    l3_code,
                    confidence,
                    platform='GEE' if platform == 'gee' else 'QGIS'
                )

                if platform == 'gee':
                    if success == 'success':
                        self.stats['gee_success'] += 1
                    elif success == 'operator_not_found':
                        self.stats['gee_operator_not_found'] += 1
                    elif success == 'l3_not_found':
                        self.stats['gee_l3_not_found'] += 1
                else:
                    if success == 'success':
                        self.stats['qgis_success'] += 1
                    elif success == 'operator_not_found':
                        self.stats['qgis_operator_not_found'] += 1
                    elif success == 'l3_not_found':
                        self.stats['qgis_l3_not_found'] += 1


def resolve_id_mappings_path(data_dir, allow_legacy_inputs=False):
    """Resolve the mainline id_mappings path.

    Defaults to outputs_v2/id_mappings_v2.json and only falls back to legacy
    mappings when explicitly allowed.
    """
    data_dir = resolve_project_data_dir(data_dir)
    if allow_legacy_inputs:
        candidates = (*V2_ID_MAPPINGS_CANDIDATES, *LEGACY_ID_MAPPINGS_CANDIDATES)
    else:
        candidates = V2_ID_MAPPINGS_CANDIDATES
    return resolve_input_path(data_dir, *candidates)

    def create_mapping(self, operator_name, l3_code, confidence, platform='GEE'):
        """创建算子到L3的映射关系"""
        with self.driver.session(database=self.database) as session:
            if platform == 'GEE':
                # GEE算子名称是小写的
                result = session.run("""
                    MATCH (op:GEE_Operator)
                    WHERE toLower(op.name) = toLower($op_name)
                    MATCH (l3:L3_Primitive {code: $l3_code})
                    MERGE (op)-[r:maps_to_l3]->(l3)
                    SET r.confidence = $confidence,
                        r.created_at = datetime()
                    RETURN op.name AS op_name, l3.code AS l3_code
                """, {
                    "op_name": operator_name,
                    "l3_code": l3_code,
                    "confidence": confidence
                })
            else:  # QGIS
                result = session.run("""
                    MATCH (op:QGIS_Operator {name: $op_name})
                    MATCH (l3:L3_Primitive {code: $l3_code})
                    MERGE (op)-[r:maps_to_l3]->(l3)
                    SET r.confidence = $confidence,
                        r.created_at = datetime()
                    RETURN op.name AS op_name, l3.code AS l3_code
                """, {
                    "op_name": operator_name,
                    "l3_code": l3_code,
                    "confidence": confidence
                })

            record = result.single()
            if record:
                return 'success'
            else:
                # 检查是算子不存在还是L3不存在
                result = session.run(f"""
                    MATCH (op:{platform}_Operator {{name: $op_name}})
                    RETURN count(op) AS count
                """, {"op_name": operator_name})
                op_count = result.single()['count']

                result = session.run("""
                    MATCH (l3:L3_Primitive {code: $l3_code})
                    RETURN count(l3) AS count
                """, {"l3_code": l3_code})
                l3_count = result.single()['count']

                if op_count == 0:
                    return 'operator_not_found'
                elif l3_count == 0:
                    return 'l3_not_found'
                else:
                    return 'unknown_error'

    def print_statistics(self):
        """打印导入统计"""
        print("\n" + "=" * 70)
        print("导入统计")
        print("=" * 70)

        print("\nGEE映射:")
        print(f"  尝试导入: {self.stats['gee_total']}")
        print(f"  成功: {self.stats['gee_success']}")
        print(f"  算子未找到: {self.stats['gee_operator_not_found']}")
        print(f"  L3未找到: {self.stats['gee_l3_not_found']}")
        if self.stats['gee_total'] > 0:
            success_rate = self.stats['gee_success'] / self.stats['gee_total'] * 100
            print(f"  成功率: {success_rate:.2f}%")

        print("\nQGIS映射:")
        print(f"  尝试导入: {self.stats['qgis_total']}")
        print(f"  成功: {self.stats['qgis_success']}")
        print(f"  算子未找到: {self.stats['qgis_operator_not_found']}")
        print(f"  L3未找到: {self.stats['qgis_l3_not_found']}")
        if self.stats['qgis_total'] > 0:
            success_rate = self.stats['qgis_success'] / self.stats['qgis_total'] * 100
            print(f"  成功率: {success_rate:.2f}%")

        # 验证数据库中的映射关系
        with self.driver.session(database=self.database) as session:
            result = session.run("""
                MATCH (gee:GEE_Operator)-[:maps_to_l3]->(l3:L3_Primitive)
                RETURN count(*) AS count
            """)
            gee_count = result.single()['count']

            result = session.run("""
                MATCH (qgis:QGIS_Operator)-[:maps_to_l3]->(l3:L3_Primitive)
                RETURN count(*) AS count
            """)
            qgis_count = result.single()['count']

            print("\n数据库中的映射关系:")
            print(f"  GEE -> L3: {gee_count}")
            print(f"  QGIS -> L3: {qgis_count}")
            print(f"  总计: {gee_count + qgis_count}")


def main(argv=None):
    """主函数"""
    parser = argparse.ArgumentParser(description="导入v2 id_mappings中的GEE/QGIS到L3映射")
    parser.add_argument("--neo4j-uri", default=os.environ.get("NEO4J_URI", "bolt://localhost:7687"))
    parser.add_argument("--neo4j-user", default=os.environ.get("NEO4J_USER", "neo4j"))
    parser.add_argument("--neo4j-password", default=os.environ.get("NEO4J_PASSWORD"))
    parser.add_argument("--neo4j-database", default=os.environ.get("NEO4J_DATABASE", "neo4j"))
    parser.add_argument("--data-dir", default=os.environ.get("GIS_RECOMMEND_DATA_DIR"))
    parser.add_argument("--id-mappings", default=None, help="Explicit id_mappings JSON path")
    parser.add_argument(
        "--allow-legacy-inputs",
        action="store_true",
        help="Allow legacy outputs/ fallback when outputs_v2/id_mappings_v2.json is missing.",
    )
    args = parser.parse_args(argv)

    if not args.neo4j_password:
        raise ValueError("Missing Neo4j password. Set --neo4j-password or NEO4J_PASSWORD.")

    data_dir = resolve_project_data_dir(args.data_dir)
    id_mappings_path = (
        Path(args.id_mappings).expanduser().resolve()
        if args.id_mappings
        else resolve_id_mappings_path(data_dir, allow_legacy_inputs=args.allow_legacy_inputs)
    )

    print("=" * 70)
    print("算子到L3映射关系导入工具")
    print("=" * 70)
    print(f"\n数据库配置:")
    print(f"  URI: {args.neo4j_uri}")
    print(f"  数据库: {args.neo4j_database}")
    print(f"  数据目录: {data_dir}")
    print(f"  id_mappings: {id_mappings_path}")

    importer = L3MappingImporter(args.neo4j_uri, args.neo4j_user, args.neo4j_password, database=args.neo4j_database)

    try:
        importer.import_id_mappings(id_mappings_path)

        # 打印统计
        importer.print_statistics()

        print("\n" + "=" * 70)
        print("导入完成！")
        print("=" * 70)

    finally:
        importer.close()


if __name__ == "__main__":
    main()
