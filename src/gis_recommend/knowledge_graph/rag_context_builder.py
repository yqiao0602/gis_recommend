"""
rag_context_builder.py

知识图谱 → LLM 上下文桥梁

功能：
1. 从 Neo4j 检索事实数据
2. 格式化为 LLM 可理解的结构化上下文文本
3. 支持单算子上下文、算子链上下文、Q&A 上下文
"""

from typing import List, Optional

from gis_recommend.knowledge_graph.neo4j_graphrag_retriever import Neo4jGraphRAGRetriever


class RAGContextBuilder:
    """
    将知识图谱检索结果转化为 LLM 可消费的结构化上下文文本。
    """

    def __init__(self, retriever: Neo4jGraphRAGRetriever):
        self.retriever = retriever

    # ------------------------------------------------------------------
    # 1. 单个算子上下文
    # ------------------------------------------------------------------

    def build_operator_context(self, operator_name: str) -> str:
        """
        构建单个算子的完整知识上下文。

        包含：描述、输入输出参数、关联L3原语、同族算子。
        """
        info = self.retriever.get_operator_info(operator_name)
        if not info:
            return f"未找到算子 '{operator_name}' 的信息。"

        lines = [
            f"## 算子: {info['name']}",
            f"- 算法ID: {info.get('algorithm_id', 'N/A')}",
            f"- 描述: {info.get('description', 'N/A')}",
        ]

        # 输入输出（通过图谱 IO 类型查询获取更完整的信息）
        io = self.retriever.get_operator_io_types(operator_name)

        if io["inputs"]:
            lines.append("- 输入参数:")
            for inp in io["inputs"]:
                opt_str = "可选" if inp.get("optional") else "必填"
                dt = inp.get("data_type") or "未知"
                lines.append(f"  - {inp['parameter_name']}: {inp.get('description', '')} ({opt_str}, 类型: {dt})")

        if io["outputs"]:
            lines.append("- 输出参数:")
            for out in io["outputs"]:
                dt = out.get("data_type") or "未知"
                lines.append(f"  - {out['parameter_name']}: {out.get('description', '')} (类型: {dt})")

        # 关联 L3 原语
        l3_mappings = self.retriever.get_l3_for_operator(operator_name)
        if l3_mappings:
            lines.append("- 关联L3原语:")
            for m in l3_mappings[:5]:
                lines.append(f"  - {m['l3_code']} ({m['l3_name']}), 置信度: {m['confidence']:.2f}")

        # 同族算子（同 L2 类别）
        related = self.retriever.get_related_operators(operator_name, top_k=5)
        if related:
            # 按 L2 类别分组
            by_l2 = {}
            for r in related:
                by_l2.setdefault(r["l2_category"], []).append(r)
            for l2_name, ops in by_l2.items():
                lines.append(f"- 同族算子 (L2: {l2_name}):")
                for op in ops[:3]:
                    lines.append(f"  - \"{op['name']}\" (置信度 {op['confidence']:.2f})")

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 2. 算子链上下文
    # ------------------------------------------------------------------

    def build_chain_context(self, qgis_chain: List[str]) -> str:
        """
        构建算子链的知识上下文。

        包含每个算子的简介 + 相邻算子间的数据流兼容性分析。
        """
        if not qgis_chain:
            return "算子链为空。"

        lines = [f"## 算子链概览 ({len(qgis_chain)} 步)"]
        lines.append(f"链: {' -> '.join(qgis_chain)}")
        lines.append("")

        for i, op_name in enumerate(qgis_chain, 1):
            if op_name.startswith("UNKNOWN"):
                lines.append(f"### 步骤 {i}: {op_name} (待确定)")
                lines.append("")
                continue

            info = self.retriever.get_operator_info(op_name)
            if info:
                lines.append(f"### 步骤 {i}: {info['name']}")
                lines.append(f"- 描述: {info.get('description', 'N/A')}")
            else:
                lines.append(f"### 步骤 {i}: {op_name} (未在知识图谱中找到)")
                lines.append("")
                continue

            # IO 类型摘要
            io = self.retriever.get_operator_io_types(op_name)
            required_inputs = [
                inp for inp in io["inputs"] if not inp.get("optional")
            ]
            if required_inputs:
                in_names = [f"{inp['parameter_name']}({inp.get('data_type', '?')})" for inp in required_inputs[:3]]
                lines.append(f"- 必填输入: {', '.join(in_names)}")
            if io["outputs"]:
                out_names = [f"{o['parameter_name']}({o.get('data_type', '?')})" for o in io["outputs"][:2]]
                lines.append(f"- 输出: {', '.join(out_names)}")

            lines.append("")

        # 数据流兼容性分析
        lines.append("## 数据流兼容性分析")
        for i in range(len(qgis_chain) - 1):
            a, b = qgis_chain[i], qgis_chain[i + 1]
            if a.startswith("UNKNOWN") or b.startswith("UNKNOWN"):
                lines.append(f"- {a} -> {b}: 无法判断（含未知算子）")
                continue

            compat = self.retriever.check_chain_io_compatibility(a, b)
            if compat["compatible"]:
                if compat["matching_pairs"]:
                    pair = compat["matching_pairs"][0]
                    lines.append(f"- {a} -> {b}: 兼容 ({pair[0]} -> {pair[1]})")
                else:
                    lines.append(f"- {a} -> {b}: 兼容（类型信息不完整，默认通过）")
            else:
                lines.append(
                    f"- {a} -> {b}: 可能不兼容 "
                    f"(输出类型: {compat['output_types']}, "
                    f"需要输入类型: {compat['input_types']})"
                )

        return "\n".join(lines)

    # ------------------------------------------------------------------
    # 3. Q&A 上下文
    # ------------------------------------------------------------------

    def build_qa_context(
        self,
        question: str,
        operator_name: Optional[str] = None,
        operator_chain: Optional[List[str]] = None,
        l3_code: Optional[str] = None,
    ) -> str:
        """
        根据问题类型构建 Q&A 上下文。

        支持的问题类型（按关键词匹配策略选择）：
        - 算子功能 → get_operator_info
        - 参数 → get_operator_io_types
        - 相似算子 → find_similar_l3 + get_operators_for_l3
        - 算子链合理性 → chain_validator context
        - L3 原语 → get_l3_info
        """
        sections = []

        # 按问题关键词和已有参数选择检索策略
        q_lower = question.lower()

        # --- 算子级别上下文 ---
        if operator_name:
            info = self.retriever.get_operator_info(operator_name)

            # 功能类问题
            if any(kw in q_lower for kw in ["功能", "是什么", "干什么", "what", "describe", "用途"]):
                if info:
                    sections.append(self.build_operator_context(operator_name))

            # 参数类问题
            elif any(kw in q_lower for kw in ["参数", "parameter", "怎么设置", "如何设置", "input", "output", "怎么用"]):
                if info:
                    sections.append(self.build_operator_context(operator_name))

            # 相似算子类问题
            elif any(kw in q_lower for kw in ["类似", "similar", "替代", "alternative", "其他"]):
                sections.append(self.build_operator_context(operator_name))

            # 默认：给出算子完整上下文
            else:
                if info:
                    sections.append(self.build_operator_context(operator_name))

        # --- 算子链级别上下文 ---
        if operator_chain:
            if any(kw in q_lower for kw in ["链", "chain", "合理", "兼容", "流程", "能跑", "workflow"]):
                sections.append(self.build_chain_context(operator_chain))
            else:
                # 默认给出链概览
                sections.append(self.build_chain_context(operator_chain))

        # --- L3 级别上下文 ---
        if l3_code:
            l3_info = self.retriever.get_l3_info(l3_code)
            if l3_info:
                lines = [
                    f"## L3原语: {l3_info['code']}",
                    f"- 名称: {l3_info['name']}",
                    f"- 描述: {l3_info.get('description', 'N/A')}",
                    f"- 输入类型: {l3_info.get('input_type', 'N/A')}",
                    f"- 输出类型: {l3_info.get('output_type', 'N/A')}",
                ]

                # 映射到的 QGIS 算子
                ops = self.retriever.get_operators_for_l3(l3_code, top_k=5)
                if ops:
                    lines.append("- 对应QGIS算子:")
                    for op in ops:
                        lines.append(f"  - {op['name']} (置信度: {op['confidence']:.2f})")

                # 同族 L3
                siblings = self.retriever.find_similar_l3(l3_code, top_k=5)
                if siblings:
                    lines.append(f"- 同族L3 (L2: {siblings[0].get('l2_name', 'N/A')}):")
                    for s in siblings:
                        lines.append(f"  - {s['code']}: {s['name']}")

                sections.append("\n".join(lines))

        if not sections:
            return "未能从知识图谱检索到相关信息。"

        return "\n\n".join(sections)
