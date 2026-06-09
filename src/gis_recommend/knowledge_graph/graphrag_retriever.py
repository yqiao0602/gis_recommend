"""
graphrag_retriever.py

GraphRAG检索模块

功能：
1. 从异构知识图谱检索候选QGIS算子
2. 支持多跳查询和路径推理
3. 基于图结构的相似度计算
"""

import json
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass
import pickle


def _resolve_project_root() -> Path:
    p = Path(__file__).resolve()
    for parent in [p.parent, p.parent.parent, p.parent.parent.parent, p.parent.parent.parent.parent]:
        if (parent / "outputs").is_dir():
            return parent
    return p.parent


@dataclass
class GraphRetrievalResult:
    """图检索结果"""
    operator_name: str
    confidence: float
    path_info: Dict  # 路径信息（如何从L3到达该算子）
    source: str = "graph_retrieval"


class GraphRAGRetriever:
    """
    GraphRAG检索器

    使用异构知识图谱进行复杂的算子检索
    """

    def __init__(
        self,
        graph_path: str = None,
        use_mock: bool = True  # 默认使用mock模式
    ):
        """
        初始化GraphRAG检索器

        参数:
            graph_path: 知识图谱文件路径
            use_mock: 是否使用mock模式（用于测试）
        """
        self.use_mock = use_mock

        if graph_path is None:
            base_dir = _resolve_project_root()
            graph_path = base_dir / "outputs" / "hetero_knowledge_graph.bin"

        self.graph_path = Path(graph_path)

        # 加载图
        if not use_mock and self.graph_path.exists():
            self.graph = self._load_graph()
            print(f"[INFO] GraphRAG Retriever Initialized")
            print(f"  - Graph Path: {graph_path}")
            print(f"  - Mode: Real Graph")
        else:
            self.graph = None
            print(f"[INFO] GraphRAG Retriever Initialized")
            print(f"  - Mode: Mock")

        # 构建mock数据（用于测试）
        self.mock_graph_data = self._build_mock_graph_data()

    def _load_graph(self):
        """
        加载异构知识图谱

        返回:
            DGL异构图对象
        """
        try:
            import dgl
            import torch

            # 加载图
            graphs, _ = dgl.load_graphs(str(self.graph_path))
            graph = graphs[0]

            print(f"  - Node Types: {graph.ntypes}")
            print(f"  - Edge Types: {graph.etypes}")

            return graph

        except Exception as e:
            print(f"[WARNING] Failed to load graph: {e}")
            print(f"  Using mock mode instead")
            self.use_mock = True
            return None

    def _build_mock_graph_data(self) -> Dict:
        """
        构建mock图数据（用于测试）

        返回:
            Mock图数据结构
        """
        # 模拟图结构：L3 -> L2 -> L3' -> QGIS
        mock_data = {
            # L3 -> L2 映射
            "l3_to_l2": {
                "L3_INDEX_CALC": "L2_01_05",
                "L3_CLOUD_MASK": "L2_01_04",
                "L3_01_01_01": "L2_01_01",
                "L3_01_10_02": "L2_01_10",
            },

            # L2 -> L3 映射（同一L2下的其他L3）
            "l2_to_l3": {
                "L2_01_05": ["L3_01_05_01", "L3_01_05_02", "L3_01_05_03"],
                "L2_01_04": ["L3_01_04_01", "L3_01_04_02", "L3_01_04_03"],
                "L2_01_01": ["L3_01_01_01", "L3_01_01_02", "L3_01_01_03"],
                "L2_01_10": ["L3_01_10_01", "L3_01_10_02", "L3_01_10_03"],
            },

            # L3 -> QGIS 映射
            "l3_to_qgis": {
                "L3_01_05_01": [
                    {"operator": "Raster calculator", "confidence": 0.85},
                    {"operator": "BandMath", "confidence": 0.80}
                ],
                "L3_01_05_02": [
                    {"operator": "Raster band math", "confidence": 0.75}
                ],
                "L3_01_04_01": [
                    {"operator": "Clip raster by mask layer", "confidence": 0.80},
                    {"operator": "Raster mask", "confidence": 0.75}
                ],
                "L3_01_04_02": [
                    {"operator": "Conditional filter", "confidence": 0.70}
                ],
            }
        }

        return mock_data

    def retrieve_by_graph_path(
        self,
        l3_code: str,
        unknown_type: str,
        max_hops: int = 2,
        top_k: int = 5
    ) -> List[GraphRetrievalResult]:
        """
        通过图路径检索候选算子

        策略：
        1. 从目标L3出发
        2. 通过L2找到相似L3
        3. 查询相似L3的QGIS映射
        4. 计算路径置信度

        参数:
            l3_code: 目标L3代码
            unknown_type: Unknown类型
            max_hops: 最大跳数
            top_k: 返回top-k个结果

        返回:
            检索结果列表
        """
        print(f"\n[Graph Retrieval] L3: {l3_code}, Type: {unknown_type}")
        print(f"  Max Hops: {max_hops}, Top-K: {top_k}")

        if self.use_mock:
            return self._mock_graph_retrieval(l3_code, unknown_type, max_hops, top_k)
        else:
            return self._real_graph_retrieval(l3_code, unknown_type, max_hops, top_k)

    def _mock_graph_retrieval(
        self,
        l3_code: str,
        unknown_type: str,
        max_hops: int,
        top_k: int
    ) -> List[GraphRetrievalResult]:
        """
        Mock图检索（用于测试）

        参数:
            l3_code: 目标L3代码
            unknown_type: Unknown类型
            max_hops: 最大跳数
            top_k: 返回top-k个结果

        返回:
            检索结果列表
        """
        results = []

        # 步骤1：L3 -> L2
        l2_code = self.mock_graph_data["l3_to_l2"].get(l3_code)

        if not l2_code:
            print(f"  [WARNING] L3 {l3_code} not found in mock graph")
            return results

        print(f"  Step 1: {l3_code} -> {l2_code}")

        # 步骤2：L2 -> 相似L3
        similar_l3s = self.mock_graph_data["l2_to_l3"].get(l2_code, [])
        print(f"  Step 2: {l2_code} -> {len(similar_l3s)} similar L3s")

        # 步骤3：相似L3 -> QGIS
        for similar_l3 in similar_l3s:
            qgis_mappings = self.mock_graph_data["l3_to_qgis"].get(similar_l3, [])

            for mapping in qgis_mappings:
                # 计算路径置信度（考虑跳数衰减）
                hop_count = 2  # L3 -> L2 -> L3' -> QGIS
                decay_factor = 0.9 ** hop_count
                path_confidence = mapping["confidence"] * decay_factor

                path_info = {
                    "path": f"{l3_code} -> {l2_code} -> {similar_l3} -> {mapping['operator']}",
                    "hop_count": hop_count,
                    "intermediate_l3": similar_l3,
                    "original_confidence": mapping["confidence"],
                    "decay_factor": decay_factor
                }

                result = GraphRetrievalResult(
                    operator_name=mapping["operator"],
                    confidence=path_confidence,
                    path_info=path_info,
                    source="graph_retrieval"
                )

                results.append(result)

        # 按置信度排序
        results.sort(key=lambda x: x.confidence, reverse=True)

        # 返回top-k
        top_results = results[:top_k]

        print(f"  Retrieved: {len(top_results)} candidates")
        for i, r in enumerate(top_results[:3], 1):
            print(f"    {i}. {r.operator_name} (conf={r.confidence:.3f}, hops={r.path_info['hop_count']})")

        return top_results

    def _real_graph_retrieval(
        self,
        l3_code: str,
        unknown_type: str,
        max_hops: int,
        top_k: int
    ) -> List[GraphRetrievalResult]:
        """
        真实图检索（使用DGL）

        参数:
            l3_code: 目标L3代码
            unknown_type: Unknown类型
            max_hops: 最大跳数
            top_k: 返回top-k个结果

        返回:
            检索结果列表
        """
        # TODO: 实现真实的DGL图查询
        # 这里需要：
        # 1. 找到L3节点的ID
        # 2. 执行多跳查询（L3 -> L2 -> L3' -> QGIS）
        # 3. 计算路径置信度
        # 4. 返回top-k结果

        print(f"  [INFO] Real graph retrieval not implemented yet")
        print(f"  [INFO] Falling back to mock mode")

        return self._mock_graph_retrieval(l3_code, unknown_type, max_hops, top_k)

    def retrieve_by_semantic_similarity(
        self,
        l3_code: str,
        unknown_type: str,
        top_k: int = 5
    ) -> List[GraphRetrievalResult]:
        """
        基于语义相似度检索

        使用图嵌入计算L3之间的语义相似度

        参数:
            l3_code: 目标L3代码
            unknown_type: Unknown类型
            top_k: 返回top-k个结果

        返回:
            检索结果列表
        """
        # TODO: 实现基于图嵌入的语义相似度检索
        # 这里需要：
        # 1. 加载预训练的图嵌入
        # 2. 计算L3嵌入之间的余弦相似度
        # 3. 找到最相似的L3
        # 4. 查询这些L3的QGIS映射

        print(f"\n[Semantic Retrieval] L3: {l3_code}, Type: {unknown_type}")
        print(f"  [INFO] Semantic similarity retrieval not implemented yet")
        print(f"  [INFO] Using graph path retrieval instead")

        return self.retrieve_by_graph_path(l3_code, unknown_type, max_hops=2, top_k=top_k)


# 使用示例
if __name__ == "__main__":
    # 初始化GraphRAG检索器（mock模式）
    retriever = GraphRAGRetriever(use_mock=True)

    print("\n" + "="*80)
    print("Test: GraphRAG Retrieval")
    print("="*80)

    # 测试1：图路径检索
    results1 = retriever.retrieve_by_graph_path(
        l3_code="L3_INDEX_CALC",
        unknown_type="index_compute",
        max_hops=2,
        top_k=5
    )

    print("\n" + "="*80)
    print("Graph Path Retrieval Results")
    print("="*80)
    for i, result in enumerate(results1, 1):
        print(f"\n{i}. {result.operator_name}")
        print(f"   Confidence: {result.confidence:.3f}")
        print(f"   Path: {result.path_info['path']}")
        print(f"   Hop Count: {result.path_info['hop_count']}")

    # 测试2：语义相似度检索
    print("\n" + "="*80)
    print("Test: Semantic Similarity Retrieval")
    print("="*80)

    results2 = retriever.retrieve_by_semantic_similarity(
        l3_code="L3_CLOUD_MASK",
        unknown_type="cloud_mask",
        top_k=3
    )

    print("\n" + "="*80)
    print("Semantic Similarity Retrieval Results")
    print("="*80)
    for i, result in enumerate(results2, 1):
        print(f"\n{i}. {result.operator_name}")
        print(f"   Confidence: {result.confidence:.3f}")
        print(f"   Path: {result.path_info['path']}")
