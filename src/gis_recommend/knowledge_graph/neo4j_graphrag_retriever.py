"""
neo4j_graphrag_retriever.py

基于Neo4j的GraphRAG检索器

功能：
1. 连接Neo4j知识图谱
2. 执行Cypher查询（算子信息、L3原语、IO类型、兼容性等）
3. 多跳路径检索
4. 返回候选QGIS算子
"""

import json
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field


@dataclass
class GraphRetrievalResult:
    """图检索结果"""
    operator_name: str
    confidence: float
    path_info: Dict
    source: str = "neo4j_graph_retrieval"


class Neo4jGraphRAGRetriever:
    """
    基于Neo4j的GraphRAG检索器

    提供对知识图谱的完整查询能力：
    - 算子信息查询
    - L3原语查询
    - L3→QGIS映射
    - 同族算子发现
    - IO类型与数据流兼容性检查
    - 多跳路径检索
    """

    def __init__(
        self,
        uri: str = "bolt://localhost:7687",
        username: str = "neo4j",
        password: str = "12345678",
        use_mock: bool = False
    ):
        self.uri = uri
        self.username = username
        self.password = password
        self.use_mock = use_mock
        self.driver = None

        if not use_mock:
            try:
                from neo4j import GraphDatabase
                self.driver = GraphDatabase.driver(uri, auth=(username, password))
                with self.driver.session() as session:
                    result = session.run("RETURN 1 AS test")
                    result.single()
                print(f"[INFO] Neo4j GraphRAG Retriever Initialized")
                print(f"  - URI: {uri}")
                print(f"  - Mode: Real Neo4j")
            except Exception as e:
                print(f"[WARNING] Failed to connect to Neo4j: {e}")
                print(f"  - Falling back to mock mode")
                self.use_mock = True
        else:
            print(f"[INFO] Neo4j GraphRAG Retriever Initialized")
            print(f"  - Mode: Mock")

        # Mock数据（仅在use_mock时使用）
        self._mock_data = None

    # ------------------------------------------------------------------
    # 1. 算子信息查询
    # ------------------------------------------------------------------

    def get_operator_info(self, name: str) -> Optional[Dict]:
        """
        获取QGIS算子完整信息

        参数:
            name: QGIS算子名称

        返回:
            包含 name, description, algorithm_id, inputs, outputs 的字典，
            或 None（不存在）
        """
        if self.use_mock or self.driver is None:
            return self._mock_get_operator_info(name)

        try:
            with self.driver.session() as session:
                query = """
                MATCH (q:QGIS_Operator {name: $name})
                RETURN q.name AS name,
                       q.description AS description,
                       q.algorithm_id AS algorithm_id,
                       q.inputs AS inputs,
                       q.outputs AS outputs
                """
                record = session.run(query, name=name).single()
                if not record:
                    return None

                inputs = self._parse_json_field(record["inputs"])
                outputs = self._parse_json_field(record["outputs"])

                return {
                    "name": record["name"],
                    "description": record["description"],
                    "algorithm_id": record["algorithm_id"],
                    "inputs": inputs,
                    "outputs": outputs,
                }
        except Exception as e:
            print(f"[ERROR] get_operator_info failed: {e}")
            return None

    # ------------------------------------------------------------------
    # 2. L3 原语查询
    # ------------------------------------------------------------------

    def get_l3_info(self, code: str) -> Optional[Dict]:
        """
        获取L3原语信息

        参数:
            code: L3原语代码（如 "L3_01_01_01"）

        返回:
            包含 code, name, description, input_type, output_type 的字典
        """
        if self.use_mock or self.driver is None:
            return None

        try:
            with self.driver.session() as session:
                query = """
                MATCH (l:L3_Primitive {code: $code})
                RETURN l.code AS code,
                       l.name AS name,
                       l.description AS description,
                       l.input_type AS input_type,
                       l.output_type AS output_type
                """
                record = session.run(query, code=code).single()
                if not record:
                    return None
                return dict(record)
        except Exception as e:
            print(f"[ERROR] get_l3_info failed: {e}")
            return None

    # ------------------------------------------------------------------
    # 3. L3 → QGIS 映射
    # ------------------------------------------------------------------

    def get_operators_for_l3(
        self, code: str, top_k: int = 10
    ) -> List[Dict]:
        """
        获取映射到指定L3原语的QGIS算子（按置信度排序）

        参数:
            code: L3原语代码
            top_k: 返回数量上限

        返回:
            [{"name": ..., "confidence": ..., "algorithm_id": ...}, ...]
        """
        if self.use_mock or self.driver is None:
            return []

        try:
            with self.driver.session() as session:
                query = """
                MATCH (q:QGIS_Operator)-[r:maps_to_l3]->(l:L3_Primitive {code: $code})
                RETURN q.name AS name,
                       r.confidence AS confidence,
                       q.algorithm_id AS algorithm_id
                ORDER BY r.confidence DESC
                LIMIT $top_k
                """
                records = session.run(query, code=code, top_k=top_k)
                return [dict(r) for r in records]
        except Exception as e:
            print(f"[ERROR] get_operators_for_l3 failed: {e}")
            return []

    # ------------------------------------------------------------------
    # 4. 相关算子（同L2族）
    # ------------------------------------------------------------------

    def get_related_operators(
        self, name: str, top_k: int = 10
    ) -> List[Dict]:
        """
        获取与指定算子相关的算子（通过 L3 → L2 → 兄弟L3 → QGIS 路径）

        参数:
            name: QGIS算子名称
            top_k: 返回数量上限

        返回:
            [{"name": ..., "confidence": ..., "via_l3": ..., "l2_category": ...}, ...]
        """
        if self.use_mock or self.driver is None:
            return []

        try:
            with self.driver.session() as session:
                query = """
                MATCH (q:QGIS_Operator {name: $name})-[r1:maps_to_l3]->(l3:L3_Primitive)
                      -[:belongs_to_l2]->(l2:L2_Category)
                      <-[:belongs_to_l2]-(sibling_l3:L3_Primitive)
                      <-[r2:maps_to_l3]-(related:QGIS_Operator)
                WHERE related.name <> $name
                RETURN DISTINCT related.name AS name,
                       r2.confidence AS confidence,
                       sibling_l3.code AS via_l3,
                       l2.name AS l2_category
                ORDER BY r2.confidence DESC
                LIMIT $top_k
                """
                records = session.run(query, name=name, top_k=top_k)
                return [dict(r) for r in records]
        except Exception as e:
            print(f"[ERROR] get_related_operators failed: {e}")
            return []

    # ------------------------------------------------------------------
    # 5. 算子 IO 类型查询
    # ------------------------------------------------------------------

    def get_operator_io_types(self, name: str) -> Dict:
        """
        获取算子的输入/输出数据类型（通过 hasInput/hasOutput → links_to → DataType）

        参数:
            name: QGIS算子名称

        返回:
            {
                "inputs": [{"parameter_name": ..., "description": ..., "optional": ..., "data_type": ...}],
                "outputs": [{"parameter_name": ..., "description": ..., "data_type": ...}]
            }
        """
        if self.use_mock or self.driver is None:
            return {"inputs": [], "outputs": []}

        result = {"inputs": [], "outputs": []}
        try:
            with self.driver.session() as session:
                # 输入
                in_query = """
                MATCH (q:QGIS_Operator {name: $name})-[:hasInput]->(i:Input)
                OPTIONAL MATCH (i)-[:links_to]->(dt:DataType)
                RETURN i.parameter_name AS parameter_name,
                       i.description AS description,
                       i.optional AS optional,
                       collect(DISTINCT dt.name) AS data_types
                """
                for rec in session.run(in_query, name=name):
                    data_types = rec["data_types"] or []
                    result["inputs"].append({
                        "parameter_name": rec["parameter_name"],
                        "description": rec["description"],
                        "optional": rec["optional"],
                        "data_type": data_types[0] if data_types else None,
                    })

                # 输出
                out_query = """
                MATCH (q:QGIS_Operator {name: $name})-[:hasOutput]->(o:Output)
                OPTIONAL MATCH (o)-[:links_to]->(dt:DataType)
                RETURN o.parameter_name AS parameter_name,
                       o.description AS description,
                       collect(DISTINCT dt.name) AS data_types
                """
                for rec in session.run(out_query, name=name):
                    data_types = rec["data_types"] or []
                    result["outputs"].append({
                        "parameter_name": rec["parameter_name"],
                        "description": rec["description"],
                        "data_type": data_types[0] if data_types else None,
                    })

        except Exception as e:
            print(f"[ERROR] get_operator_io_types failed: {e}")

        return result

    # ------------------------------------------------------------------
    # 6. 数据类型兼容性检查
    # ------------------------------------------------------------------

    def check_datatype_compatibility(
        self, type_a: str, type_b: str
    ) -> bool:
        """
        检查两个数据类型是否兼容（通过 compatible_with 关系）

        参数:
            type_a: 源数据类型名称（如 "raster"）
            type_b: 目标数据类型名称（如 "raster"）

        返回:
            True 表示兼容
        """
        if self.use_mock or self.driver is None:
            return True  # mock 下默认兼容

        if type_a == type_b:
            return True

        try:
            with self.driver.session() as session:
                query = """
                MATCH (a:DataType {name: $type_a})-[:compatible_with]->(b:DataType {name: $type_b})
                RETURN count(*) > 0 AS compatible
                """
                record = session.run(
                    query, type_a=type_a, type_b=type_b
                ).single()
                return record["compatible"] if record else False
        except Exception as e:
            print(f"[ERROR] check_datatype_compatibility failed: {e}")
            return False

    # ------------------------------------------------------------------
    # 7. 相似 L3（同 L2 下的兄弟）
    # ------------------------------------------------------------------

    def find_similar_l3(
        self, code: str, top_k: int = 10
    ) -> List[Dict]:
        """
        找到与给定L3同属一个L2类别的兄弟L3

        参数:
            code: L3原语代码
            top_k: 返回数量上限

        返回:
            [{"code": ..., "name": ..., "description": ..., "l2_name": ...}, ...]
        """
        if self.use_mock or self.driver is None:
            return []

        try:
            with self.driver.session() as session:
                query = """
                MATCH (l:L3_Primitive {code: $code})-[:belongs_to_l2]->(l2:L2_Category)
                      <-[:belongs_to_l2]-(s:L3_Primitive)
                WHERE s.code <> $code
                RETURN s.code AS code,
                       s.name AS name,
                       s.description AS description,
                       l2.name AS l2_name
                LIMIT $top_k
                """
                records = session.run(query, code=code, top_k=top_k)
                return [dict(r) for r in records]
        except Exception as e:
            print(f"[ERROR] find_similar_l3 failed: {e}")
            return []

    # ------------------------------------------------------------------
    # 8. 核心 RAG 查询：多跳图路径检索
    # ------------------------------------------------------------------

    def retrieve_by_graph_path(
        self,
        l3_code: str,
        unknown_type: str = "",
        max_hops: int = 2,
        top_k: int = 5
    ) -> List[GraphRetrievalResult]:
        """
        通过图路径检索候选算子（L3 → L2 → 兄弟L3 → QGIS）

        参数:
            l3_code: 目标L3代码
            unknown_type: Unknown类型（用于日志）
            max_hops: 最大跳数（保留参数）
            top_k: 返回top-k个结果

        返回:
            GraphRetrievalResult列表
        """
        print(f"\n[Neo4j Graph Retrieval] L3: {l3_code}, Type: {unknown_type}")

        if self.use_mock or self.driver is None:
            return self._mock_retrieval(l3_code, unknown_type, max_hops, top_k)

        results = []
        try:
            with self.driver.session() as session:
                # 优先：直接映射（1 跳：L3 ← QGIS）
                direct_query = """
                MATCH (q:QGIS_Operator)-[r:maps_to_l3]->(l3:L3_Primitive {code: $l3_code})
                RETURN q.name AS operator_name,
                       r.confidence AS confidence,
                       l3.code AS via_l3,
                       'direct' AS l2_category
                ORDER BY r.confidence DESC
                LIMIT $top_k
                """
                for rec in session.run(direct_query, l3_code=l3_code, top_k=top_k):
                    results.append(GraphRetrievalResult(
                        operator_name=rec["operator_name"],
                        confidence=rec["confidence"],
                        path_info={
                            "path": f"{l3_code} -> {rec['operator_name']}",
                            "hop_count": 1,
                            "intermediate_l3": l3_code,
                            "original_confidence": rec["confidence"],
                            "decay_factor": 1.0,
                        },
                    ))

                # 补充：多跳路径（L3 → L2 → 兄弟L3 → QGIS）
                remaining = top_k - len(results)
                if remaining > 0:
                    multi_query = """
                    MATCH (l3:L3_Primitive {code: $l3_code})
                          -[:belongs_to_l2]->(l2:L2_Category)
                          <-[:belongs_to_l2]-(similar_l3:L3_Primitive)
                          <-[r:maps_to_l3]-(qgis:QGIS_Operator)
                    WHERE similar_l3.code <> $l3_code
                    RETURN qgis.name AS operator_name,
                           r.confidence AS confidence,
                           similar_l3.code AS via_l3,
                           l2.name AS l2_category
                    ORDER BY r.confidence DESC
                    LIMIT $remaining
                    """
                    existing_names = {r.operator_name for r in results}
                    for rec in session.run(
                        multi_query,
                        l3_code=l3_code,
                        remaining=remaining + 10,
                    ):
                        if rec["operator_name"] in existing_names:
                            continue
                        decay = 0.9 ** 2  # 2-hop decay
                        path_conf = rec["confidence"] * decay
                        results.append(GraphRetrievalResult(
                            operator_name=rec["operator_name"],
                            confidence=path_conf,
                            path_info={
                                "path": f"{l3_code} -> {rec['l2_category']} -> {rec['via_l3']} -> {rec['operator_name']}",
                                "hop_count": 2,
                                "intermediate_l3": rec["via_l3"],
                                "original_confidence": rec["confidence"],
                                "decay_factor": decay,
                            },
                        ))
                        existing_names.add(rec["operator_name"])
                        if len(results) >= top_k:
                            break

            # 按置信度排序
            results.sort(key=lambda x: x.confidence, reverse=True)
            results = results[:top_k]

            print(f"  Retrieved {len(results)} candidates from Neo4j")
            for i, r in enumerate(results[:3], 1):
                print(f"    {i}. {r.operator_name} (conf={r.confidence:.3f}, hops={r.path_info['hop_count']})")

        except Exception as e:
            print(f"[ERROR] Neo4j query failed: {e}")
            print(f"  Falling back to mock mode")
            return self._mock_retrieval(l3_code, unknown_type, max_hops, top_k)

        return results

    # ------------------------------------------------------------------
    # 9. 算子链中相邻两个算子的 IO 兼容性
    # ------------------------------------------------------------------

    def check_chain_io_compatibility(
        self, op_a: str, op_b: str
    ) -> Dict:
        """
        检查 op_a 的输出是否与 op_b 的输入兼容

        返回:
            {
                "compatible": bool,
                "output_types": [...],   # op_a 输出数据类型
                "input_types": [...],    # op_b 输入数据类型（必填）
                "matching_pairs": [...]  # 兼容的 (output, input) 对
            }
        """
        if self.use_mock or self.driver is None:
            return {"compatible": True, "output_types": [], "input_types": [], "matching_pairs": []}

        try:
            with self.driver.session() as session:
                query = """
                MATCH (a:QGIS_Operator {name: $op_a})-[:hasOutput]->(o:Output)-[:links_to]->(odt:DataType)
                WITH collect(DISTINCT odt.name) AS out_types
                MATCH (b:QGIS_Operator {name: $op_b})-[:hasInput]->(i:Input)-[:links_to]->(idt:DataType)
                WHERE i.optional = false OR i.optional IS NULL
                WITH out_types, collect(DISTINCT idt.name) AS in_types
                RETURN out_types, in_types
                """
                record = session.run(query, op_a=op_a, op_b=op_b).single()
                if not record:
                    return {"compatible": True, "output_types": [], "input_types": [], "matching_pairs": []}

                out_types = record["out_types"] or []
                in_types = record["in_types"] or []

                if not out_types or not in_types:
                    # 无法判断时默认兼容
                    return {"compatible": True, "output_types": out_types, "input_types": in_types, "matching_pairs": []}

                # 检查每一对是否兼容
                matching = []
                for ot in out_types:
                    for it in in_types:
                        if ot == it or self.check_datatype_compatibility(ot, it):
                            matching.append((ot, it))

                return {
                    "compatible": len(matching) > 0,
                    "output_types": out_types,
                    "input_types": in_types,
                    "matching_pairs": matching,
                }
        except Exception as e:
            print(f"[ERROR] check_chain_io_compatibility failed: {e}")
            return {"compatible": True, "output_types": [], "input_types": [], "matching_pairs": []}

    # ------------------------------------------------------------------
    # 10. 获取算子的 L3 映射信息
    # ------------------------------------------------------------------

    def get_l3_for_operator(self, name: str) -> List[Dict]:
        """
        获取算子映射到的L3原语列表

        返回:
            [{"l3_code": ..., "l3_name": ..., "confidence": ...}, ...]
        """
        if self.use_mock or self.driver is None:
            return []

        try:
            with self.driver.session() as session:
                query = """
                MATCH (q:QGIS_Operator {name: $name})-[r:maps_to_l3]->(l3:L3_Primitive)
                RETURN l3.code AS l3_code,
                       l3.name AS l3_name,
                       r.confidence AS confidence
                ORDER BY r.confidence DESC
                """
                return [dict(r) for r in session.run(query, name=name)]
        except Exception as e:
            print(f"[ERROR] get_l3_for_operator failed: {e}")
            return []

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_json_field(value) -> list:
        """安全解析可能为 JSON 字符串的字段"""
        if not value:
            return []
        if isinstance(value, list):
            return value
        try:
            return json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return []

    # ------------------------------------------------------------------
    # Mock 实现（回退用）
    # ------------------------------------------------------------------

    @property
    def _mock(self) -> Dict:
        if self._mock_data is None:
            self._mock_data = {
                "l3_to_l2": {
                    "L3_INDEX_CALC": "L2_01_05",
                    "L3_CLOUD_MASK": "L2_01_04",
                },
                "l2_to_l3": {
                    "L2_01_05": ["L3_01_05_01", "L3_01_05_02"],
                    "L2_01_04": ["L3_01_04_01", "L3_01_04_02"],
                },
                "l3_to_qgis": {
                    "L3_01_05_01": [
                        {"operator": "Raster calculator", "confidence": 0.85},
                        {"operator": "BandMath", "confidence": 0.80},
                    ],
                    "L3_01_04_01": [
                        {"operator": "Clip raster by mask layer", "confidence": 0.80},
                    ],
                },
            }
        return self._mock_data

    def _mock_get_operator_info(self, name: str) -> Optional[Dict]:
        """Mock算子信息"""
        mock_operators = {
            "Raster calculator": {
                "name": "Raster calculator",
                "description": "Performs raster calculations using mathematical expressions",
                "algorithm_id": "qgis:rastercalculator",
                "inputs": [
                    {"name": "INPUT_A", "description": "First input raster", "type": "raster", "optional": False},
                    {"name": "FORMULA", "description": "Mathematical formula", "type": "string", "optional": False},
                ],
                "outputs": [
                    {"name": "OUTPUT", "description": "Output raster", "type": "raster"},
                ],
            },
        }
        return mock_operators.get(name)

    def _mock_retrieval(
        self, l3_code: str, unknown_type: str, max_hops: int, top_k: int
    ) -> List[GraphRetrievalResult]:
        """Mock检索"""
        results = []
        l2_code = self._mock["l3_to_l2"].get(l3_code)
        if not l2_code:
            print(f"  [WARNING] L3 {l3_code} not found in mock data")
            return results

        for similar_l3 in self._mock["l2_to_l3"].get(l2_code, []):
            for m in self._mock["l3_to_qgis"].get(similar_l3, []):
                decay = 0.9 ** 2
                results.append(GraphRetrievalResult(
                    operator_name=m["operator"],
                    confidence=m["confidence"] * decay,
                    path_info={
                        "path": f"{l3_code} -> {l2_code} -> {similar_l3} -> {m['operator']}",
                        "hop_count": 2,
                        "intermediate_l3": similar_l3,
                        "original_confidence": m["confidence"],
                        "decay_factor": decay,
                    },
                ))

        results.sort(key=lambda x: x.confidence, reverse=True)
        results = results[:top_k]

        print(f"  Retrieved {len(results)} candidates (mock mode)")
        for i, r in enumerate(results[:3], 1):
            print(f"    {i}. {r.operator_name} (conf={r.confidence:.3f})")
        return results

    # ------------------------------------------------------------------
    # 连接管理
    # ------------------------------------------------------------------

    def close(self):
        """关闭Neo4j连接"""
        if self.driver:
            self.driver.close()
            print("[INFO] Neo4j connection closed")


# 使用示例
if __name__ == "__main__":
    retriever = Neo4jGraphRAGRetriever(
        uri="bolt://localhost:7687",
        username="neo4j",
        password="12345678",
        use_mock=False,
    )

    print("\n" + "=" * 80)
    print("Test: Neo4j GraphRAG Retrieval")
    print("=" * 80)

    # 测试 get_operator_info
    print("\n--- get_operator_info ---")
    info = retriever.get_operator_info("Buffer vectors")
    if info:
        print(f"  Name: {info['name']}")
        print(f"  Desc: {info['description'][:80]}")
    else:
        print("  Not found")

    # 测试 get_l3_info
    print("\n--- get_l3_info ---")
    l3 = retriever.get_l3_info("L3_01_01_01")
    if l3:
        print(f"  Code: {l3['code']}, Name: {l3['name']}")

    # 测试 get_operators_for_l3
    print("\n--- get_operators_for_l3 ---")
    ops = retriever.get_operators_for_l3("L3_01_01_01", top_k=3)
    for op in ops:
        print(f"  {op['name']} (conf={op['confidence']:.3f})")

    # 测试 retrieve_by_graph_path
    print("\n--- retrieve_by_graph_path ---")
    results = retriever.retrieve_by_graph_path(
        l3_code="L3_01_01_01", top_k=5
    )
    for i, r in enumerate(results, 1):
        print(f"  {i}. {r.operator_name} (conf={r.confidence:.3f})")
        print(f"     Path: {r.path_info['path']}")

    # 测试 get_operator_io_types
    print("\n--- get_operator_io_types ---")
    io = retriever.get_operator_io_types("Buffer vectors")
    print(f"  Inputs: {len(io['inputs'])}, Outputs: {len(io['outputs'])}")
    for inp in io["inputs"][:3]:
        print(f"    IN  {inp['parameter_name']}: {inp['data_type']} ({'optional' if inp['optional'] else 'required'})")
    for out in io["outputs"]:
        print(f"    OUT {out['parameter_name']}: {out['data_type']}")

    retriever.close()
