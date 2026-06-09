# -*- coding: utf-8 -*-
"""
本体知识图谱构建脚本
构建GEE→QGIS工作流推荐系统的本体层知识图谱

功能:
    1. 构建分类层次（L1 → L2 → L3）
    2. 构建平台算子节点（GEE_Operator, QGIS_Operator）
    3. 为GEE和QGIS算子构建Input/Output节点
    4. 构建平台映射关系（maps_to_l3）
    5. 构建DataType兼容性关系
    6. 加载L3嵌入向量（可选）

依赖:
    pip install neo4j torch tqdm

使用方法:
    python build_ontology_kg.py
"""

import json
import csv
import argparse
import torch
from neo4j import GraphDatabase
from tqdm import tqdm
import os
import sys
from pathlib import Path

# 添加父目录到路径以导入配置
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

PROJECT_ROOT = Path(__file__).resolve().parent.parent

V2_CLASSIFICATION_HIERARCHY_CANDIDATES = (
    "outputs_v2/classification_hierarchy_v2.csv",
    "system_redesign/outputs_v2/classification_hierarchy_v2.csv",
    "Algorithm_classification/system_redesign/outputs_v2/classification_hierarchy_v2.csv",
)

LEGACY_CLASSIFICATION_HIERARCHY_CANDIDATES = (
    "classification_hierarchy.csv",
    "../classification_hierarchy.csv",
    "Algorithm_classification/classification_hierarchy.csv",
)

CLASSIFICATION_HIERARCHY_CANDIDATES = (
    *V2_CLASSIFICATION_HIERARCHY_CANDIDATES,
    *LEGACY_CLASSIFICATION_HIERARCHY_CANDIDATES,
)

V2_ID_MAPPINGS_CANDIDATES = (
    "outputs_v2/id_mappings_v2.json",
    "system_redesign/outputs_v2/id_mappings_v2.json",
    "Algorithm_classification/system_redesign/outputs_v2/id_mappings_v2.json",
)

LEGACY_ID_MAPPINGS_CANDIDATES = (
    "outputs/id_mappings.json",
    "id_mappings.json",
    "system_redesign/outputs/id_mappings.json",
    "Algorithm_classification/system_redesign/outputs/id_mappings.json",
)

ID_MAPPINGS_CANDIDATES = (
    *V2_ID_MAPPINGS_CANDIDATES,
    *LEGACY_ID_MAPPINGS_CANDIDATES,
)

LEGACY_GEE_MAPPING_CANDIDATES = (
    "L3_classification/GEE/GEE_to_L3_03_Mapping_Full.json",
    "../L3_classification/GEE/GEE_to_L3_03_Mapping_Full.json",
    "Algorithm_classification/L3_classification/GEE/GEE_to_L3_03_Mapping_Full.json",
)

LEGACY_QGIS_MAPPING_CANDIDATES = (
    "L3_classification/QGIS/QGIS_to_L3_03_Mapping_Full.json",
    "../L3_classification/QGIS/QGIS_to_L3_03_Mapping_Full.json",
    "Algorithm_classification/L3_classification/QGIS/QGIS_to_L3_03_Mapping_Full.json",
)

L3_EMBEDDING_CANDIDATES = (
    "outputs_v2/l3_embeddings_v2.pt",
    "system_redesign/outputs_v2/l3_embeddings_v2.pt",
    "Algorithm_classification/system_redesign/outputs_v2/l3_embeddings_v2.pt",
    "outputs/l3_embeddings.pt",
    "system_redesign/outputs/l3_embeddings.pt",
    "Algorithm_classification/system_redesign/outputs/l3_embeddings.pt",
)

V2_L3_EMBEDDING_CANDIDATES = (
    "outputs_v2/l3_embeddings_v2.pt",
    "system_redesign/outputs_v2/l3_embeddings_v2.pt",
    "Algorithm_classification/system_redesign/outputs_v2/l3_embeddings_v2.pt",
)


def resolve_project_data_dir(explicit_dir=None):
    """Resolve the data root for graph construction.

    Priority:
      1. Explicit argument
      2. GIS_RECOMMEND_DATA_DIR environment variable
      3. Current project root (system_redesign/)
    """
    if explicit_dir:
        return Path(explicit_dir).expanduser()

    env_dir = os.environ.get("GIS_RECOMMEND_DATA_DIR")
    if env_dir:
        return Path(env_dir).expanduser()

    return PROJECT_ROOT


def resolve_input_path(data_dir, *relative_candidates, required=True):
    """Resolve an input file under multiple supported layouts."""
    base_dir = Path(data_dir).expanduser()
    tried = []

    for relative in relative_candidates:
        candidate = (base_dir / Path(relative)).resolve()
        tried.append(str(candidate))
        if candidate.exists():
            return candidate

    if required:
        raise FileNotFoundError(
            "Input file not found. Tried:\n  - " + "\n  - ".join(tried)
        )
    return None


def extract_l3_embedding_tensor(payload):
    """Extract the actual embedding tensor from supported checkpoint layouts."""
    if isinstance(payload, torch.Tensor):
        return payload

    if isinstance(payload, dict):
        for key in ("embeddings", "weight"):
            value = payload.get(key)
            if isinstance(value, torch.Tensor):
                return value

    return None


def _is_real_l3_code(l3_code):
    return (
        isinstance(l3_code, str)
        and l3_code.startswith("L3_")
        and not l3_code.startswith("L3_UNKNOWN")
    )


def _mapping_items_from_id_mappings(payload, platform):
    """Return old-style mapping result entries from v2 id_mappings metadata."""
    if not isinstance(payload, dict):
        return []

    metadata = payload.get("mapping_metadata", {})
    mappings = metadata.get(f"{platform}_to_l3") or payload.get(f"{platform}_to_l3")
    if not isinstance(mappings, dict):
        return []

    results = []
    for operator, info in mappings.items():
        mapped_l3s = []

        if isinstance(info, dict):
            candidates = info.get("all_candidates") or []
            if candidates:
                for candidate in candidates:
                    if not isinstance(candidate, dict):
                        continue
                    l3_code = candidate.get("l3_code") or candidate.get("primary_l3")
                    if not _is_real_l3_code(l3_code):
                        continue
                    mapped_l3s.append({
                        "l3_code": l3_code,
                        "confidence": candidate.get("confidence", info.get("mapping_confidence", 1.0)),
                    })
            else:
                l3_code = info.get("primary_l3") or info.get("l3_code")
                if _is_real_l3_code(l3_code):
                    mapped_l3s.append({
                        "l3_code": l3_code,
                        "confidence": info.get("mapping_confidence", 1.0),
                    })
        elif _is_real_l3_code(info):
            mapped_l3s.append({"l3_code": info, "confidence": 1.0})

        if mapped_l3s:
            results.append({
                "operator": operator,
                "status": "MAPPED",
                "mapped_l3s": mapped_l3s,
            })

    return results


def load_platform_mapping_results(json_path, platform):
    """Load either legacy mapping JSON or v2 id_mappings metadata."""
    with open(json_path, 'r', encoding='utf-8') as f:
        payload = json.load(f)

    metadata_results = _mapping_items_from_id_mappings(payload, platform)
    if metadata_results:
        return metadata_results

    return payload.get("results", []) if isinstance(payload, dict) else []

# 构建L3编码映射（从classification_hierarchy.csv读取）
def build_l3_code_mappings(csv_path):
    """
    从classification_hierarchy.csv构建L3编码映射

    返回:
        L3_CODE_TO_ID: {l3_code: id} 如 {"L3_01_01_01": 0, ...}
        ID_TO_L3_CODE: {id: l3_code} 如 {0: "L3_01_01_01", ...}
    """
    l3_codes = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            l3_code = row['l3_code']
            if l3_code not in l3_codes:
                l3_codes.append(l3_code)

    # 按编码排序
    l3_codes.sort()

    # 构建双向映射
    L3_CODE_TO_ID = {code: idx for idx, code in enumerate(l3_codes)}
    ID_TO_L3_CODE = {idx: code for idx, code in enumerate(l3_codes)}

    return L3_CODE_TO_ID, ID_TO_L3_CODE

# 在模块加载时构建映射
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = resolve_project_data_dir()
CLASSIFICATION_CSV = resolve_input_path(
    DATA_DIR,
    *CLASSIFICATION_HIERARCHY_CANDIDATES,
    required=False,
)

if CLASSIFICATION_CSV is not None and os.path.exists(CLASSIFICATION_CSV):
    L3_CODE_TO_ID, ID_TO_L3_CODE = build_l3_code_mappings(CLASSIFICATION_CSV)
    print(f"已加载L3编码映射: {len(L3_CODE_TO_ID)} 个L3代码")
else:
    print(f"[!] 警告: 未找到分类层次文件: {CLASSIFICATION_CSV}")
    print("  将在运行时构建L3映射")
    L3_CODE_TO_ID = {}
    ID_TO_L3_CODE = {}


class OntologyKGBuilder:
    """本体知识图谱构建器"""

    def __init__(self, neo4j_uri, neo4j_user, neo4j_password, database="neo4j"):
        """
        初始化构建器

        参数:
            neo4j_uri: Neo4j数据库URI (如 "bolt://localhost:7687")
            neo4j_user: 用户名
            neo4j_password: 密码
            database: 数据库名称 (默认"neo4j"，推荐使用"geospatial_workflow_ontology")
        """
        self.driver = GraphDatabase.driver(neo4j_uri, auth=(neo4j_user, neo4j_password))
        self.database = database
        print(f"已连接到Neo4j: {neo4j_uri}, 数据库: {database}")

        # 统计信息
        self.stats = {
            'l1_count': 0,
            'l2_count': 0,
            'l3_count': 0,
            'gee_op_count': 0,
            'qgis_op_count': 0,
            'datatype_count': 0,
            'input_count': 0,
            'output_count': 0,
            'belongs_to_l1_count': 0,
            'belongs_to_l2_count': 0,
            'maps_to_l3_gee_count': 0,
            'maps_to_l3_qgis_count': 0,
            'hasInput_count': 0,
            'hasOutput_count': 0,
            'links_to_count': 0,
        }

    def close(self):
        """关闭数据库连接"""
        self.driver.close()

    def clear_all(self):
        """清空所有本体节点和关系"""
        print("\n[!] 警告: 即将删除所有本体节点和关系...")
        print("2秒后开始删除...")
        import time
        time.sleep(2)

        with self.driver.session(database=self.database) as session:
            # 删除所有节点和关系
            session.run("MATCH (n) DETACH DELETE n")
            print("已清空知识图谱")

    def build_all(self, data_dir, allow_legacy_inputs=False):
        """
        构建完整的本体知识图谱

        参数:
            data_dir: 数据目录根路径
            allow_legacy_inputs: 是否允许旧版输入回退
        """
        data_dir = resolve_project_data_dir(data_dir)
        print("\n" + "="*70)
        print("开始构建本体知识图谱")
        print("="*70)

        # 第1步: 构建分类层次（L1 → L2 → L3）
        print("\n[步骤 1/5] 构建分类层次...")
        classification_path = resolve_input_path(
            data_dir,
            *V2_CLASSIFICATION_HIERARCHY_CANDIDATES,
        )
        self.build_classification_hierarchy(classification_path)

        # 第2步: 构建GEE算子
        print("\n[步骤 2/5] 构建GEE算子...")
        gee_ops_path = resolve_input_path(
            data_dir,
            "operators-json/gee_operators.json",
            "../operators-json/gee_operators.json",
            "../../operators-json/gee_operators.json",
        )
        self.build_gee_operators(gee_ops_path)

        # 第3步: 构建QGIS算子
        print("\n[步骤 3/5] 构建QGIS算子...")
        qgis_ops_path = resolve_input_path(
            data_dir,
            "operators-json/qgis_operators.json",
            "../operators-json/qgis_operators.json",
            "../../operators-json/qgis_operators.json",
        )
        self.build_qgis_operators(qgis_ops_path)

        # 第4步: 为GEE算子构建Input/Output节点
        print("\n[步骤 4/7] 为GEE算子构建Input/Output...")
        self.build_gee_io(gee_ops_path)

        # 第5步: 构建QGIS的数据类型和I/O约束
        print("\n[步骤 5/7] 构建QGIS的Input/Output...")
        self.build_qgis_io(qgis_ops_path)

        # 第6步: 构建平台映射关系
        print("\n[步骤 6/7] 构建平台映射关系...")
        id_mappings_path = resolve_input_path(
            data_dir,
            *V2_ID_MAPPINGS_CANDIDATES,
            required=False,
        )
        if id_mappings_path is not None:
            gee_mapping_path = id_mappings_path
            qgis_mapping_path = id_mappings_path
        elif allow_legacy_inputs:
            gee_mapping_path = resolve_input_path(data_dir, *LEGACY_GEE_MAPPING_CANDIDATES)
            qgis_mapping_path = resolve_input_path(data_dir, *LEGACY_QGIS_MAPPING_CANDIDATES)
        else:
            raise FileNotFoundError(
                "Missing outputs_v2/id_mappings_v2.json. "
                "Legacy mapping fallback is disabled unless --allow-legacy-inputs is set."
            )
        self.build_platform_mappings(gee_mapping_path, qgis_mapping_path)

        # 第7步: 创建DataType兼容性关系
        print("\n[步骤 7/7] 创建DataType兼容性关系...")
        self.build_datatype_compatibility()

        # 打印统计信息
        self.print_statistics()

        print("\n" + "="*70)
        print("本体知识图谱构建完成！")
        print("="*70)

    def build_classification_hierarchy(self, csv_path):
        """
        构建分类层次（L1 → L2 → L3）

        参数:
            csv_path: classification_hierarchy.csv文件路径
        """
        # 读取CSV（使用纯Python csv模块）
        rows = []
        with open(csv_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                rows.append(row)

        print(f"  读取分类层次数据: {len(rows)} 行")

        with self.driver.session(database=self.database) as session:
            # 1. 提取并创建L1节点
            l1_seen = {}
            for row in rows:
                key = row['l1_code']
                if key not in l1_seen:
                    l1_seen[key] = {
                        'code': row['l1_code'],
                        'name': row['l1_name'],
                        'description': row.get('l1_description', '') or ''
                    }

            l1_list = list(l1_seen.values())
            print(f"  创建L1节点: {len(l1_list)} 个")

            for l1 in tqdm(l1_list, desc="  L1"):
                session.run("""
                    MERGE (l1:L1_Category {code: $code})
                    SET l1.name = $name,
                        l1.description = $description
                """, {
                    "code": l1['code'],
                    "name": l1['name'],
                    "description": l1['description']
                })
                self.stats['l1_count'] += 1

            # 2. 提取并创建L2节点 + belongs_to_l1关系
            l2_seen = {}
            for row in rows:
                key = row['l2_code']
                if key not in l2_seen:
                    l2_seen[key] = {
                        'code': row['l2_code'],
                        'name': row['l2_name'],
                        'description': row.get('l2_description', '') or '',
                        'l1_code': row['l1_code']
                    }

            l2_list = list(l2_seen.values())
            print(f"  创建L2节点: {len(l2_list)} 个")

            for l2 in tqdm(l2_list, desc="  L2"):
                session.run("""
                    MERGE (l2:L2_Category {code: $code})
                    SET l2.name = $name,
                        l2.description = $description
                    WITH l2
                    MATCH (l1:L1_Category {code: $l1_code})
                    MERGE (l2)-[:belongs_to_l1]->(l1)
                """, {
                    "code": l2['code'],
                    "name": l2['name'],
                    "description": l2['description'],
                    "l1_code": l2['l1_code']
                })
                self.stats['l2_count'] += 1
                self.stats['belongs_to_l1_count'] += 1

            # 3. 创建L3节点 + belongs_to_l2关系
            print(f"  创建L3节点: {len(rows)} 个")

            for row in tqdm(rows, desc="  L3"):
                # 获取L3的ID
                l3_id = L3_CODE_TO_ID.get(row['l3_code'], -1)

                session.run("""
                    MERGE (l3:L3_Primitive {code: $code})
                    SET l3.id = $id,
                        l3.name = $name,
                        l3.description = $description,
                        l3.input_type = $input_type,
                        l3.output_type = $output_type
                    WITH l3
                    MATCH (l2:L2_Category {code: $l2_code})
                    MERGE (l3)-[:belongs_to_l2]->(l2)
                """, {
                    "code": row['l3_code'],
                    "id": l3_id,
                    "name": row['l3_name'],
                    "description": row['l3_description'],
                    "input_type": row.get('input_type', 'unknown'),
                    "output_type": row.get('output_type', 'unknown'),
                    "l2_code": row['l2_code']
                })
                self.stats['l3_count'] += 1
                self.stats['belongs_to_l2_count'] += 1

        print(f"  [OK] 分类层次构建完成")

    def build_gee_operators(self, json_path):
        """
        构建GEE算子节点

        参数:
            json_path: gee_operators.json文件路径
        """
        # 读取JSON（GEE格式是嵌套字典）
        with open(json_path, 'r', encoding='utf-8') as f:
            gee_data = json.load(f)

        # 合并所有类别的算子
        all_gee_ops = []
        for category, ops in gee_data.items():
            if isinstance(ops, list):
                # 为每个算子添加类别信息
                for op in ops:
                    op['category'] = category
                    all_gee_ops.append(op)

        print(f"  读取GEE算子数据: {len(all_gee_ops)} 个（来自 {len(gee_data)} 个分类）")

        with self.driver.session(database=self.database) as session:
            for op in tqdm(all_gee_ops, desc="  GEE算子"):
                try:
                    # 确保name是字符串
                    name = str(op.get('name', ''))
                    if not name:
                        continue  # 跳过没有名称的算子

                    # 提取参数和返回值，确保是字符串类型
                    parameters = op.get('parameters', [])
                    if isinstance(parameters, list):
                        parameters = json.dumps(parameters, ensure_ascii=False)
                    elif not isinstance(parameters, str):
                        parameters = str(parameters)

                    returns = op.get('returns', '')
                    if isinstance(returns, (list, dict)):
                        returns = json.dumps(returns, ensure_ascii=False)
                    elif not isinstance(returns, str):
                        returns = str(returns)

                    # 确保所有字段都是字符串
                    url = str(op.get('url', ''))
                    description = str(op.get('description', ''))
                    category = str(op.get('category', ''))

                    session.run("""
                        MERGE (gee:GEE_Operator {name: $name})
                        SET gee.url = $url,
                            gee.description = $description,
                            gee.category = $category,
                            gee.parameters = $parameters,
                            gee.returns = $returns
                    """, {
                        "name": name,
                        "url": url,
                        "description": description,
                        "category": category,
                        "parameters": parameters,
                        "returns": returns
                    })
                    self.stats['gee_op_count'] += 1

                except Exception as e:
                    print(f"\n[!] 处理算子失败: {op.get('name', 'unknown')}")
                    print(f"   错误: {e}")
                    print(f"   算子数据: {json.dumps(op, ensure_ascii=False, indent=2)[:500]}")
                    # 继续处理下一个算子
                    continue

        print(f"  [OK] GEE算子构建完成")

    def build_qgis_operators(self, json_path):
        """
        构建QGIS算子节点

        参数:
            json_path: qgis_operators.json文件路径
        """
        # 读取JSON
        with open(json_path, 'r', encoding='utf-8') as f:
            qgis_ops = json.load(f)

        print(f"  读取QGIS算子数据: {len(qgis_ops)} 个")

        with self.driver.session(database=self.database) as session:
            for op_data in tqdm(qgis_ops, desc="  QGIS算子"):
                # 提取输入输出
                inputs = json.dumps(op_data.get('inputs', []), ensure_ascii=False)
                outputs = json.dumps(op_data.get('outputs', []), ensure_ascii=False)

                session.run("""
                    MERGE (qgis:QGIS_Operator {id: $id})
                    SET qgis.name = $name,
                        qgis.algorithm_id = $algorithm_id,
                        qgis.description = $description,
                        qgis.inputs = $inputs,
                        qgis.outputs = $outputs
                """, {
                    "id": op_data.get('id'),
                    "name": op_data.get('name', ''),
                    "algorithm_id": op_data.get('algorithm_id', ''),
                    "description": op_data.get('description', ''),
                    "inputs": inputs,
                    "outputs": outputs
                })
                self.stats['qgis_op_count'] += 1

        print(f"  [OK] QGIS算子构建完成")

    def build_gee_io(self, json_path):
        """
        为GEE算子构建Input/Output节点

        参数:
            json_path: gee_operators.json文件路径
        """
        # 读取JSON
        with open(json_path, 'r', encoding='utf-8') as f:
            gee_data = json.load(f)

        # 合并所有类别的算子
        all_gee_ops = []
        for category, ops in gee_data.items():
            if isinstance(ops, list):
                all_gee_ops.extend(ops)

        print(f"  处理 {len(all_gee_ops)} 个GEE算子的I/O...")

        with self.driver.session(database=self.database) as session:
            for op in tqdm(all_gee_ops, desc="  GEE I/O"):
                gee_name = op['name']

                # 1. 处理输入参数
                parameters = op.get('parameters', [])
                for i, param in enumerate(parameters):
                    param_name = param.get('name', f'param_{i}')
                    param_type = param.get('type', 'Unknown')
                    optional = param.get('optional', False)

                    # 创建Input节点
                    input_id = f"gee_input_{gee_name}_{param_name}"

                    # 先确保DataType存在
                    session.run("""
                        MERGE (dt:DataType {name: $datatype})
                        ON CREATE SET dt.category = 'gee_type',
                                      dt.mime_types = '[]'
                    """, {"datatype": param_type})

                    # 创建Input节点并建立关系
                    session.run("""
                        MATCH (gee:GEE_Operator {name: $gee_name})
                        MERGE (inp:Input {id: $input_id})
                        ON CREATE SET inp.parameter_name = $param_name,
                                      inp.description = $description,
                                      inp.optional = $optional,
                                      inp.required = $required
                        MERGE (gee)-[:hasInput]->(inp)
                        WITH inp
                        MATCH (dt:DataType {name: $datatype})
                        MERGE (inp)-[:links_to]->(dt)
                    """, {
                        "gee_name": gee_name,
                        "input_id": input_id,
                        "param_name": param_name,
                        "description": param.get('description', ''),
                        "optional": optional,
                        "required": not optional,
                        "datatype": param_type
                    })

                    self.stats['input_count'] += 1
                    self.stats['hasInput_count'] += 1
                    self.stats['links_to_count'] += 1

                # 2. 处理返回值（输出）
                returns = op.get('returns', '')
                if returns:
                    output_id = f"gee_output_{gee_name}_result"

                    # 先确保DataType存在
                    session.run("""
                        MERGE (dt:DataType {name: $datatype})
                        ON CREATE SET dt.category = 'gee_type',
                                      dt.mime_types = '[]'
                    """, {"datatype": returns})

                    # 创建Output节点并建立关系
                    session.run("""
                        MATCH (gee:GEE_Operator {name: $gee_name})
                        MERGE (out:Output {id: $output_id})
                        ON CREATE SET out.parameter_name = 'result',
                                      out.title = 'Return value'
                        MERGE (gee)-[:hasOutput]->(out)
                        WITH out
                        MATCH (dt:DataType {name: $datatype})
                        MERGE (out)-[:links_to]->(dt)
                    """, {
                        "gee_name": gee_name,
                        "output_id": output_id,
                        "datatype": returns
                    })

                    self.stats['output_count'] += 1
                    self.stats['hasOutput_count'] += 1
                    self.stats['links_to_count'] += 1

        print(f"  [OK] GEE Input/Output构建完成")

    def build_platform_mappings(self, gee_mapping_path, qgis_mapping_path):
        """
        构建平台映射关系（GEE/QGIS → L3）

        参数:
            gee_mapping_path: GEE_to_L3_03_Mapping_Full.json文件路径
            qgis_mapping_path: QGIS_to_L3_03_Mapping_Full.json文件路径
        """
        with self.driver.session(database=self.database) as session:
            # 1. GEE → L3映射
            if os.path.exists(gee_mapping_path):
                gee_results = load_platform_mapping_results(gee_mapping_path, "gee")

                print(f"  读取GEE→L3映射: {len(gee_results)} 个")

                for item in tqdm(gee_results, desc="  GEE→L3"):
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
                            self.stats['maps_to_l3_gee_count'] += 1

            # 2. QGIS → L3映射
            if os.path.exists(qgis_mapping_path):
                qgis_results = load_platform_mapping_results(qgis_mapping_path, "qgis")

                print(f"  读取QGIS→L3映射: {len(qgis_results)} 个")

                for item in tqdm(qgis_results, desc="  QGIS→L3"):
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
                            self.stats['maps_to_l3_qgis_count'] += 1

        print(f"  [OK] 平台映射关系构建完成")

    def build_qgis_io(self, json_path):
        """
        为QGIS算子构建Input/Output节点

        参数:
            json_path: qgis_operators.json文件路径
        """
        # 读取JSON
        with open(json_path, 'r', encoding='utf-8') as f:
            qgis_ops = json.load(f)

        print(f"  处理 {len(qgis_ops)} 个QGIS算子的I/O...")

        with self.driver.session(database=self.database) as session:
            for op in tqdm(qgis_ops, desc="  QGIS I/O"):
                qgis_id = op['id']
                qgis_name = op['name']

                # 1. 处理输入参数
                inputs = op.get('inputs', [])
                for inp in inputs:
                    param_name = inp.get('name', '')
                    param_type = inp.get('type', 'Unknown')
                    mime_types = inp.get('mimeTypes', [])
                    optional = inp.get('optional', False)
                    min_occurs = inp.get('minOccurs', 0)
                    max_occurs = inp.get('maxOccurs', 1)

                    # 创建Input节点
                    input_id = f"qgis_input_{qgis_id}_{param_name}"

                    # 先确保DataType存在
                    mime_types_json = json.dumps(mime_types, ensure_ascii=False)
                    session.run("""
                        MERGE (dt:DataType {name: $datatype})
                        ON CREATE SET dt.category = $category,
                                      dt.mime_types = $mime_types
                    """, {
                        "datatype": param_type,
                        "category": self._categorize_datatype(param_type),
                        "mime_types": mime_types_json
                    })

                    # 创建Input节点并建立关系
                    session.run("""
                        MATCH (qgis:QGIS_Operator {id: $qgis_id})
                        MERGE (inp:Input {id: $input_id})
                        ON CREATE SET inp.parameter_name = $param_name,
                                      inp.description = $description,
                                      inp.optional = $optional,
                                      inp.required = $required,
                                      inp.min_occurs = $min_occurs,
                                      inp.max_occurs = $max_occurs
                        MERGE (qgis)-[:hasInput]->(inp)
                        WITH inp
                        MATCH (dt:DataType {name: $datatype})
                        MERGE (inp)-[:links_to]->(dt)
                    """, {
                        "qgis_id": qgis_id,
                        "input_id": input_id,
                        "param_name": param_name,
                        "description": inp.get('description', ''),
                        "optional": optional,
                        "required": not optional,
                        "min_occurs": min_occurs,
                        "max_occurs": max_occurs,
                        "datatype": param_type
                    })

                    self.stats['input_count'] += 1
                    self.stats['hasInput_count'] += 1
                    self.stats['links_to_count'] += 1

                # 2. 处理输出
                outputs = op.get('outputs', [])
                for out in outputs:
                    param_name = out.get('name', '')
                    param_type = out.get('type', 'Unknown')
                    mime_types = out.get('mimeTypes', [])

                    # 创建Output节点
                    output_id = f"qgis_output_{qgis_id}_{param_name}"

                    # 先确保DataType存在
                    mime_types_json = json.dumps(mime_types, ensure_ascii=False)
                    session.run("""
                        MERGE (dt:DataType {name: $datatype})
                        ON CREATE SET dt.category = $category,
                                      dt.mime_types = $mime_types
                    """, {
                        "datatype": param_type,
                        "category": self._categorize_datatype(param_type),
                        "mime_types": mime_types_json
                    })

                    # 创建Output节点并建立关系
                    session.run("""
                        MATCH (qgis:QGIS_Operator {id: $qgis_id})
                        MERGE (out:Output {id: $output_id})
                        ON CREATE SET out.parameter_name = $param_name,
                                      out.description = $description
                        MERGE (qgis)-[:hasOutput]->(out)
                        WITH out
                        MATCH (dt:DataType {name: $datatype})
                        MERGE (out)-[:links_to]->(dt)
                    """, {
                        "qgis_id": qgis_id,
                        "output_id": output_id,
                        "param_name": param_name,
                        "description": out.get('description', ''),
                        "datatype": param_type
                    })

                    self.stats['output_count'] += 1
                    self.stats['hasOutput_count'] += 1
                    self.stats['links_to_count'] += 1

        print(f"  [OK] QGIS Input/Output构建完成")

    def build_datatype_compatibility(self):
        """
        创建DataType之间的兼容性关系

        定义常见的数据类型转换规则：
        - raster → raster (直接兼容)
        - vector → vector (直接兼容)
        - Image → raster (GEE Image可转为QGIS raster)
        - ImageCollection → raster (可导出为raster)
        - FeatureCollection → vector (可导出为vector)
        - Geometry → vector (几何对象可转为矢量)
        - Number/Float → LiteralData (数值可转为字面量)
        """
        print("  创建DataType兼容性关系...")

        # 定义兼容性规则
        compatibility_rules = [
            # 相同类型兼容
            ("raster", "raster"),
            ("vector", "vector"),
            ("LiteralData", "LiteralData"),
            ("Image", "Image"),
            ("ImageCollection", "ImageCollection"),

            # GEE → QGIS转换
            ("Image", "raster"),
            ("ImageCollection", "raster"),
            ("FeatureCollection", "vector"),
            ("Feature", "vector"),
            ("Geometry", "vector"),
            ("Number", "LiteralData"),
            ("Float", "LiteralData"),
            ("Integer", "LiteralData"),
            ("String", "LiteralData"),
            ("List", "LiteralData"),

            # QGIS → GEE转换（反向）
            ("raster", "Image"),
            ("vector", "FeatureCollection"),

            # 宽松兼容（栅格可统计为数值）
            ("raster", "LiteralData"),
            ("Image", "LiteralData"),
            ("vector", "LiteralData"),

            # 地理数据通用兼容
            ("geographicData", "raster"),
            ("geographicData", "vector"),
        ]

        compatible_count = 0
        with self.driver.session(database=self.database) as session:
            for type1, type2 in tqdm(compatibility_rules, desc="  兼容性"):
                # 检查两个DataType是否都存在
                result = session.run("""
                    MATCH (dt1:DataType {name: $type1})
                    MATCH (dt2:DataType {name: $type2})
                    RETURN dt1, dt2
                """, {"type1": type1, "type2": type2})

                if result.single():
                    # 创建兼容性关系
                    session.run("""
                        MATCH (dt1:DataType {name: $type1})
                        MATCH (dt2:DataType {name: $type2})
                        MERGE (dt1)-[:compatible_with]->(dt2)
                    """, {"type1": type1, "type2": type2})
                    compatible_count += 1

        print(f"  [OK] DataType兼容性关系构建完成 ({compatible_count} 条)")


    def load_l3_embeddings(self, embeddings_path):
        """
        加载L3嵌入向量到节点属性

        参数:
            embeddings_path: l3_embeddings.pt文件路径
        """
        print("\n[额外步骤] 加载L3嵌入向量...")

        raw_payload = torch.load(embeddings_path, map_location="cpu", weights_only=True)
        embeddings = extract_l3_embedding_tensor(raw_payload)
        if embeddings is None:
            print(f"  [!] 无法从 {embeddings_path} 解析L3嵌入向量，跳过该步骤")
            if isinstance(raw_payload, dict):
                print(f"  可用键: {list(raw_payload.keys())}")
            return False

        if isinstance(raw_payload, dict) and isinstance(raw_payload.get("l3_codes"), list):
            l3_codes = raw_payload["l3_codes"]
        else:
            l3_codes = [ID_TO_L3_CODE[idx] for idx in range(len(embeddings)) if idx in ID_TO_L3_CODE]

        print(f"  加载嵌入向量: {tuple(embeddings.shape)}")

        updated_count = 0
        with self.driver.session(database=self.database) as session:
            for idx, l3_code in enumerate(l3_codes):
                if not l3_code or idx >= len(embeddings):
                    continue

                embedding_vec = embeddings[idx].tolist()
                embedding_json = json.dumps(embedding_vec)

                session.run("""
                    MATCH (l3:L3_Primitive {code: $code})
                    SET l3.embedding = $embedding
                """, {
                    "code": l3_code,
                    "embedding": embedding_json
                })
                updated_count += 1

        print(f"  [OK] L3嵌入向量加载完成 ({updated_count} 个L3节点)")
        return True

    def print_statistics(self):
        """打印知识图谱统计信息"""
        print("\n" + "="*70)
        print("知识图谱统计")
        print("="*70)

        with self.driver.session(database=self.database) as session:
            # 查询实际节点和关系数量
            result = session.run("MATCH (n) RETURN labels(n)[0] AS label, count(n) AS count")
            node_counts = {record['label']: record['count'] for record in result}

            result = session.run("MATCH ()-[r]->() RETURN type(r) AS type, count(r) AS count")
            edge_counts = {record['type']: record['count'] for record in result}

        print("\n节点统计:")
        print(f"  L1_Category: {node_counts.get('L1_Category', 0)}")
        print(f"  L2_Category: {node_counts.get('L2_Category', 0)}")
        print(f"  L3_Primitive: {node_counts.get('L3_Primitive', 0)}")
        print(f"  GEE_Operator: {node_counts.get('GEE_Operator', 0)}")
        print(f"  QGIS_Operator: {node_counts.get('QGIS_Operator', 0)}")
        print(f"  DataType: {node_counts.get('DataType', 0)}")
        print(f"  Input: {node_counts.get('Input', 0)}")
        print(f"  Output: {node_counts.get('Output', 0)}")
        total_nodes = sum(node_counts.values())
        print(f"  总计: {total_nodes} 个节点")

        print("\n关系统计:")
        print(f"  belongs_to_l1: {edge_counts.get('belongs_to_l1', 0)}")
        print(f"  belongs_to_l2: {edge_counts.get('belongs_to_l2', 0)}")
        print(f"  maps_to_l3: {edge_counts.get('maps_to_l3', 0)}")
        print(f"  hasInput: {edge_counts.get('hasInput', 0)}")
        print(f"  hasOutput: {edge_counts.get('hasOutput', 0)}")
        print(f"  links_to: {edge_counts.get('links_to', 0)}")
        total_edges = sum(edge_counts.values())
        print(f"  总计: {total_edges} 条关系")

    @staticmethod
    def _categorize_datatype(datatype):
        """分类数据类型"""
        datatype_lower = datatype.lower()
        if 'raster' in datatype_lower or 'image' in datatype_lower:
            return 'spatial'
        elif 'vector' in datatype_lower or 'feature' in datatype_lower:
            return 'spatial'
        elif 'literal' in datatype_lower or 'number' in datatype_lower:
            return 'literal'
        else:
            return 'other'


def main(argv=None):
    """主函数"""
    parser = argparse.ArgumentParser(description="Build the Neo4j ontology KG for the v2/94-L3 mainline.")
    parser.add_argument("--neo4j-uri", default=os.environ.get("NEO4J_URI", "bolt://localhost:7687"))
    parser.add_argument("--neo4j-user", default=os.environ.get("NEO4J_USER", "neo4j"))
    parser.add_argument("--neo4j-password", default=os.environ.get("NEO4J_PASSWORD"))
    parser.add_argument("--neo4j-database", default=os.environ.get("NEO4J_DATABASE", "neo4j"))
    parser.add_argument("--data-dir", default=os.environ.get("GIS_RECOMMEND_DATA_DIR"))
    parser.add_argument(
        "--clear",
        action="store_true",
        help="Clear the target database before importing. Disabled by default.",
    )
    parser.add_argument(
        "--allow-legacy-inputs",
        action="store_true",
        help="Allow legacy outputs/ fallback for mappings and ontology inputs.",
    )
    parser.add_argument(
        "--skip-embeddings",
        action="store_true",
        help="Skip optional L3 embedding import.",
    )
    args = parser.parse_args(argv)

    if not args.neo4j_password:
        raise ValueError("Missing Neo4j password. Set --neo4j-password or NEO4J_PASSWORD.")

    data_dir = resolve_project_data_dir(args.data_dir)

    print("=" * 70)
    print("GEE→QGIS工作流推荐系统 - 本体知识图谱构建")
    print("=" * 70)
    print(f"\n数据库配置:")
    print(f"  URI: {args.neo4j_uri}")
    print(f"  数据库: {args.neo4j_database}")
    print(f"\n[!] 注意: 默认不会清空数据库。只有显式 --clear 才会执行 DETACH DELETE。")
    print(f"  新增节点标签: L1_Category, L2_Category, L3_Primitive, GEE_Operator, QGIS_Operator, DataType, Input, Output")
    print(f"  不会影响现有的 Algorithm, Operation 等节点")
    print(f"  数据目录: {data_dir}")
    print(f"\n开始构建知识图谱...")

    # 创建构建器
    builder = OntologyKGBuilder(args.neo4j_uri, args.neo4j_user, args.neo4j_password, database=args.neo4j_database)

    try:
        # 清空现有数据
        if args.clear:
            builder.clear_all()
        else:
            print("\n[INFO] Skipping database clear (use --clear to enable)")

        # 构建本体知识图谱
        builder.build_all(data_dir, allow_legacy_inputs=args.allow_legacy_inputs)

        # 可选: 加载L3嵌入向量
        embeddings_path = resolve_input_path(data_dir, *V2_L3_EMBEDDING_CANDIDATES, required=False)
        if args.skip_embeddings:
            print("\n[INFO] Skipping L3 embedding import (--skip-embeddings)")
        elif embeddings_path is not None and os.path.exists(embeddings_path):
            try:
                builder.load_l3_embeddings(embeddings_path)
            except Exception as exc:
                print(f"\n[!] L3嵌入向量加载失败，但该步骤是可选的: {exc}")
                print("  跳过嵌入向量写入，继续保留已构建的本体图谱")
        else:
            print(f"\n[!] 未找到L3嵌入向量文件: {embeddings_path}")
            print("  跳过嵌入向量加载")

    finally:
        # 关闭连接
        builder.close()


if __name__ == "__main__":
    main()
