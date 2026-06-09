"""
chain_validator.py

算子链校验器

功能：
1. 检查算子链中每个算子是否存在于知识图谱
2. 检查相邻算子间数据流兼容性（输出类型 → 输入类型）
3. 计算链整体置信度
4. 给出修复建议
"""

from typing import List, Dict, Optional
from dataclasses import dataclass, field

from gis_recommend.knowledge_graph.neo4j_graphrag_retriever import Neo4jGraphRAGRetriever


@dataclass
class ChainValidationResult:
    """链校验结果"""
    is_valid: bool
    issues: List[str] = field(default_factory=list)
    suggestions: List[str] = field(default_factory=list)
    confidence: float = 1.0
    step_details: List[Dict] = field(default_factory=list)


class ChainValidator:
    """
    算子链校验器

    利用知识图谱中的算子信息和数据类型关系校验一条 QGIS 算子链：
    - 存在性：每个算子是否在图谱中
    - 数据流兼容性：op_i 输出 → op_{i+1} 输入
    - 整体置信度
    """

    def __init__(self, retriever: Neo4jGraphRAGRetriever):
        self.retriever = retriever

    def validate_chain(self, qgis_chain: List[str]) -> ChainValidationResult:
        """
        校验算子链的合理性

        参数:
            qgis_chain: QGIS算子名称列表

        返回:
            ChainValidationResult
        """
        if not qgis_chain:
            return ChainValidationResult(
                is_valid=False,
                issues=["算子链为空"],
                confidence=0.0,
            )

        issues = []
        suggestions = []
        step_details = []
        known_count = 0

        for i, op_name in enumerate(qgis_chain):
            step = {"index": i, "operator": op_name}

            # --- 跳过 UNKNOWN 占位符 ---
            if op_name.startswith("UNKNOWN"):
                step["status"] = "unknown"
                step["message"] = "待确定算子"
                step_details.append(step)
                continue

            # --- 1. 存在性检查 ---
            info = self.retriever.get_operator_info(op_name)
            if info is None:
                issues.append(f"步骤 {i + 1}: 算子 '{op_name}' 不存在于知识图谱")
                step["status"] = "not_found"
                step_details.append(step)
                continue

            step["status"] = "found"
            step["description"] = info.get("description", "")
            known_count += 1

            # --- 2. 数据流兼容性检查（与下一个算子） ---
            if i < len(qgis_chain) - 1:
                next_op = qgis_chain[i + 1]
                if next_op.startswith("UNKNOWN"):
                    step["io_check"] = "skipped_next_unknown"
                    step_details.append(step)
                    continue

                compat = self.retriever.check_chain_io_compatibility(op_name, next_op)
                step["io_check"] = compat

                if not compat["compatible"]:
                    issues.append(
                        f"步骤 {i + 1}->{i + 2}: '{op_name}' 的输出类型 "
                        f"{compat['output_types']} 与 '{next_op}' 的输入类型 "
                        f"{compat['input_types']} 可能不兼容"
                    )
                    # 尝试推荐替代
                    alt = self._find_compatible_alternative(op_name, next_op)
                    if alt:
                        suggestions.append(
                            f"步骤 {i + 2}: 可用 '{alt}' 替代 '{next_op}'"
                        )

            step_details.append(step)

        confidence = self._compute_chain_confidence(
            qgis_chain, known_count, len(issues)
        )

        return ChainValidationResult(
            is_valid=len(issues) == 0,
            issues=issues,
            suggestions=suggestions,
            confidence=confidence,
            step_details=step_details,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _find_compatible_alternative(
        self, prev_op: str, current_op: str
    ) -> Optional[str]:
        """
        如果 prev_op → current_op 不兼容，在同族算子中查找
        能接受 prev_op 输出类型的替代。
        """
        # 获取 prev_op 的输出类型
        io_prev = self.retriever.get_operator_io_types(prev_op)
        out_types = [
            o.get("data_type") for o in io_prev["outputs"] if o.get("data_type")
        ]
        if not out_types:
            return None

        # 获取 current_op 的同族算子
        related = self.retriever.get_related_operators(current_op, top_k=10)
        for r in related:
            alt_name = r["name"]
            compat = self.retriever.check_chain_io_compatibility(prev_op, alt_name)
            if compat["compatible"]:
                return alt_name

        return None

    @staticmethod
    def _compute_chain_confidence(
        chain: List[str], known_count: int, issue_count: int
    ) -> float:
        """
        计算链整体置信度

        因子：
        - 已知算子比例
        - 无问题的比例
        """
        total = len(chain)
        if total == 0:
            return 0.0

        unknown_count = sum(1 for op in chain if op.startswith("UNKNOWN"))
        non_unknown = total - unknown_count

        # 已知比例（在非 UNKNOWN 中）
        known_ratio = known_count / non_unknown if non_unknown > 0 else 0.0

        # 问题惩罚
        issue_penalty = min(issue_count * 0.15, 0.6)

        # UNKNOWN 惩罚
        unknown_penalty = (unknown_count / total) * 0.3

        confidence = max(0.0, known_ratio - issue_penalty - unknown_penalty)
        return round(confidence, 4)
