"""
qgis_operator_qa.py

QGIS算子问答系统

功能：
1. 查询算子的详细信息（从Neo4j）
2. 基于RAG上下文（知识图谱）进行知识驱动问答
3. 解释算子的功能、参数
4. 使用LLM生成友好的回答
"""

import json
from typing import Dict, List, Optional
from neo4j import GraphDatabase
from gis_recommend.llm.llm_scorer import LLMScorer
from gis_recommend.knowledge_graph.rag_context_builder import RAGContextBuilder


class QGISOperatorQA:
    """
    QGIS算子问答系统

    支持两种问答模式：
    - answer_question: 传统模式（直接查询算子信息 + LLM 生成）
    - answer_with_rag: RAG 模式（知识图谱检索上下文 + LLM 生成）
    """

    def __init__(
        self,
        neo4j_uri: str = "bolt://localhost:7687",
        neo4j_username: str = "neo4j",
        neo4j_password: str = "12345678",
        llm_api_key: str = None,
        use_mock: bool = False,
        rag_builder: Optional[RAGContextBuilder] = None,
    ):
        """
        初始化问答系统

        参数:
            neo4j_uri: Neo4j连接URI
            neo4j_username: Neo4j用户名
            neo4j_password: Neo4j密码
            llm_api_key: LLM API密钥
            use_mock: 是否使用mock模式
            rag_builder: RAG上下文构建器（可选，若提供则启用RAG问答）
        """
        self.use_mock = use_mock
        self.rag_builder = rag_builder

        # 连接Neo4j
        if not use_mock:
            try:
                self.driver = GraphDatabase.driver(
                    neo4j_uri,
                    auth=(neo4j_username, neo4j_password)
                )
                print(f"[INFO] QGIS Operator QA System Initialized")
                print(f"  - Neo4j: Connected")
                if rag_builder:
                    print(f"  - RAG: Enabled")
            except Exception as e:
                print(f"[WARNING] Failed to connect to Neo4j: {e}")
                print(f"  - Falling back to mock mode")
                self.use_mock = True
                self.driver = None
        else:
            self.driver = None
            print(f"[INFO] QGIS Operator QA System Initialized (Mock Mode)")

        # 初始化LLM
        self.llm_scorer = LLMScorer(
            api_key=llm_api_key or "sk-6d6a3478844243979fd29431ce31a841",
            model="qwen-plus",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
            temperature=0.3,
            use_mock=use_mock
        )

    # ------------------------------------------------------------------
    # RAG 问答（核心新功能）
    # ------------------------------------------------------------------

    def answer_with_rag(
        self,
        question: str,
        operator_name: Optional[str] = None,
        operator_chain: Optional[List[str]] = None,
        l3_code: Optional[str] = None,
    ) -> str:
        """
        基于知识图谱的RAG问答

        从图谱检索相关上下文，构造带上下文的LLM提示，生成知识驱动的回答。

        参数:
            question: 用户问题
            operator_name: 相关算子名称
            operator_chain: 相关算子链
            l3_code: 相关L3原语代码

        返回:
            回答文本
        """
        if not self.rag_builder:
            # 回退到传统问答
            if operator_name:
                return self.answer_question(operator_name, question)
            return "RAG 上下文构建器未初始化，无法进行知识驱动问答。"

        # 1. 从图谱检索上下文
        context = self.rag_builder.build_qa_context(
            question=question,
            operator_name=operator_name,
            operator_chain=operator_chain,
            l3_code=l3_code,
        )

        # 2. 构造 RAG 提示
        prompt = f"""基于以下知识图谱中的信息回答用户问题。
只使用提供的信息，不要编造不存在的功能或参数。如果提供的信息不足以回答，请明确说明。

{context}

用户问题: {question}

回答要求:
1. 用中文回答
2. 简洁明了，重点突出
3. 如果问题涉及参数设置，给出具体的建议
4. 如果问题涉及算子链，分析数据流兼容性
"""

        # 3. 调用 LLM
        if self.use_mock:
            return self._mock_rag_answer(question, context)

        try:
            from openai import OpenAI

            client = OpenAI(
                api_key=self.llm_scorer.api_key,
                base_url=self.llm_scorer.base_url
            )

            response = client.chat.completions.create(
                model=self.llm_scorer.model,
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "You are a helpful GIS expert assistant. "
                            "Answer questions about QGIS operators based on "
                            "the provided knowledge graph context. "
                            "Always answer in Chinese."
                        ),
                    },
                    {"role": "user", "content": prompt},
                ],
                temperature=0.3,
                max_tokens=800,
            )

            return response.choices[0].message.content

        except Exception as e:
            print(f"[ERROR] LLM call failed: {e}")
            return self._mock_rag_answer(question, context)

    # ------------------------------------------------------------------
    # 传统问答（保留兼容性）
    # ------------------------------------------------------------------

    def get_operator_info(self, operator_name: str) -> Optional[Dict]:
        """
        从Neo4j获取算子的详细信息
        """
        if self.use_mock or self.driver is None:
            return self._mock_operator_info(operator_name)

        try:
            with self.driver.session() as session:
                query = """
                MATCH (qgis:QGIS_Operator {name: $operator_name})
                RETURN qgis.name AS name,
                       qgis.description AS description,
                       qgis.inputs AS inputs,
                       qgis.outputs AS outputs,
                       qgis.algorithm_id AS algorithm_id
                """

                result = session.run(query, operator_name=operator_name)
                record = result.single()

                if record:
                    try:
                        inputs = json.loads(record["inputs"]) if record["inputs"] else []
                    except (json.JSONDecodeError, TypeError):
                        inputs = []

                    try:
                        outputs = json.loads(record["outputs"]) if record["outputs"] else []
                    except (json.JSONDecodeError, TypeError):
                        outputs = []

                    return {
                        "name": record["name"],
                        "description": record["description"],
                        "inputs": inputs,
                        "outputs": outputs,
                        "algorithm_id": record["algorithm_id"]
                    }
                else:
                    return None

        except Exception as e:
            print(f"[ERROR] Failed to query operator info: {e}")
            return None

    def _mock_operator_info(self, operator_name: str) -> Dict:
        """Mock算子信息"""
        mock_data = {
            "Raster calculator": {
                "name": "Raster calculator",
                "description": "Performs raster calculations using mathematical expressions",
                "inputs": [
                    {
                        "name": "INPUT_A",
                        "description": "First input raster",
                        "type": "raster",
                        "optional": False
                    },
                    {
                        "name": "FORMULA",
                        "description": "Mathematical formula (e.g., A + B, NDVI = (NIR - Red) / (NIR + Red))",
                        "type": "string",
                        "optional": False
                    }
                ],
                "outputs": [
                    {
                        "name": "OUTPUT",
                        "description": "Output raster",
                        "type": "raster"
                    }
                ]
            }
        }

        return mock_data.get(operator_name, {
            "name": operator_name,
            "description": "No description available",
            "inputs": [],
            "outputs": []
        })

    def answer_question(
        self,
        operator_name: str,
        question: str,
        context: Optional[Dict] = None
    ) -> str:
        """
        回答关于算子的问题（传统模式）
        """
        # 1. 获取算子信息
        operator_info = self.get_operator_info(operator_name)

        if not operator_info:
            return f"抱歉，我找不到名为 '{operator_name}' 的QGIS算子信息。"

        # 2. 构建prompt
        prompt = self._build_qa_prompt(operator_name, operator_info, question, context)

        # 3. 调用LLM生成回答
        if self.use_mock:
            return self._mock_answer(operator_name, question, operator_info)
        else:
            try:
                from openai import OpenAI

                client = OpenAI(
                    api_key=self.llm_scorer.api_key,
                    base_url=self.llm_scorer.base_url
                )

                response = client.chat.completions.create(
                    model=self.llm_scorer.model,
                    messages=[
                        {"role": "system", "content": "You are a helpful GIS expert assistant. Answer questions about QGIS operators clearly and concisely in Chinese."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_tokens=800
                )

                answer = response.choices[0].message.content
                return answer

            except Exception as e:
                print(f"[ERROR] LLM call failed: {e}")
                return self._mock_answer(operator_name, question, operator_info)

    def _build_qa_prompt(
        self,
        operator_name: str,
        operator_info: Dict,
        question: str,
        context: Optional[Dict]
    ) -> str:
        """构建问答prompt"""

        # 格式化输入参数
        inputs_text = ""
        for i, inp in enumerate(operator_info.get("inputs", []), 1):
            inputs_text += f"{i}. {inp.get('name', 'N/A')}\n"
            inputs_text += f"   - 描述: {inp.get('description', 'N/A')}\n"
            inputs_text += f"   - 类型: {inp.get('type', 'N/A')}\n"
            inputs_text += f"   - 必需: {'是' if not inp.get('optional', False) else '否'}\n"

        # 格式化输出参数
        outputs_text = ""
        for i, out in enumerate(operator_info.get("outputs", []), 1):
            outputs_text += f"{i}. {out.get('name', 'N/A')}\n"
            outputs_text += f"   - 描述: {out.get('description', 'N/A')}\n"
            outputs_text += f"   - 类型: {out.get('type', 'N/A')}\n"

        # 上下文信息
        context_text = ""
        if context:
            if "operator_chain" in context:
                context_text = f"\n## 算子链上下文\n该算子在以下算子链中：\n{' -> '.join(context['operator_chain'])}\n"

        prompt = f"""你是一个GIS专家助手。请回答关于QGIS算子的问题。

## 算子信息
名称: {operator_name}
描述: {operator_info.get('description', 'N/A')}

## 输入参数
{inputs_text if inputs_text else '无输入参数信息'}

## 输出参数
{outputs_text if outputs_text else '无输出参数信息'}
{context_text}

## 用户问题
{question}

## 回答要求
1. 用中文回答
2. 简洁明了，重点突出
3. 如果问题涉及参数设置，给出具体的建议和示例
4. 如果问题涉及使用场景，结合实际应用说明
"""

        return prompt

    def _mock_answer(self, operator_name: str, question: str, operator_info: Dict) -> str:
        """Mock回答"""
        if "是什么" in question or "干什么" in question or "功能" in question:
            return f"{operator_name} 是一个QGIS算子，用于{operator_info.get('description', '执行特定的GIS操作')}。"

        elif "参数" in question:
            inputs = operator_info.get("inputs", [])
            if inputs:
                params_text = "\n".join([
                    f"- {inp.get('name')}: {inp.get('description', 'N/A')}"
                    for inp in inputs[:3]
                ])
                return f"{operator_name} 的主要参数包括：\n{params_text}"
            else:
                return f"{operator_name} 没有可用的参数信息。"

        elif "如何设置" in question or "怎么用" in question:
            return f"使用 {operator_name} 时，需要根据具体任务设置相应的参数。建议参考QGIS官方文档获取详细的参数设置指南。"

        else:
            return f"关于 {operator_name}，{operator_info.get('description', '这是一个QGIS算子')}。如果您有具体的问题，请告诉我。"

    def _mock_rag_answer(self, question: str, context: str) -> str:
        """基于RAG上下文的Mock回答"""
        # 取上下文的前500字符作为摘要返回
        summary = context[:500] if len(context) > 500 else context
        return f"[基于知识图谱的回答]\n\n{summary}\n\n（以上信息来自知识图谱检索结果）"

    def explain_operator_chain(
        self,
        operator_chain: List[str],
        task_description: Optional[str] = None
    ) -> str:
        """
        解释整个算子链
        """
        # 如果有 RAG builder，使用更丰富的上下文
        if self.rag_builder:
            context = self.rag_builder.build_chain_context(operator_chain)
            if not self.use_mock:
                try:
                    from openai import OpenAI
                    client = OpenAI(
                        api_key=self.llm_scorer.api_key,
                        base_url=self.llm_scorer.base_url
                    )
                    prompt = f"""请基于以下知识图谱中的算子链信息，生成一段简洁的中文解释。

{context}

{'任务描述: ' + task_description if task_description else ''}

要求: 用中文简洁说明每个步骤的作用，以及整条链的数据流逻辑。"""

                    response = client.chat.completions.create(
                        model=self.llm_scorer.model,
                        messages=[
                            {"role": "system", "content": "You are a GIS expert. Explain QGIS workflows clearly in Chinese."},
                            {"role": "user", "content": prompt},
                        ],
                        temperature=0.3,
                        max_tokens=800,
                    )
                    return response.choices[0].message.content
                except Exception as e:
                    print(f"[WARNING] LLM explanation failed: {e}")
                    # 回退到下方的静态生成

        # 静态生成（无 LLM 或回退）
        explanation = f"## QGIS算子链解释\n\n"

        if task_description:
            explanation += f"**任务**: {task_description}\n\n"

        explanation += f"**算子链** ({len(operator_chain)} 个步骤):\n\n"

        for i, operator_name in enumerate(operator_chain, 1):
            operator_info = self.get_operator_info(operator_name)

            if operator_info:
                explanation += f"{i}. **{operator_name}**\n"
                explanation += f"   - 功能: {operator_info.get('description', 'N/A')}\n"

                inputs = operator_info.get("inputs", [])
                if inputs:
                    main_inputs = [inp.get('name') for inp in inputs[:2]]
                    explanation += f"   - 主要输入: {', '.join(main_inputs)}\n"

                explanation += "\n"
            else:
                explanation += f"{i}. **{operator_name}** (无详细信息)\n\n"

        return explanation

    def close(self):
        """关闭连接"""
        if self.driver:
            self.driver.close()
            print("[INFO] Neo4j connection closed")


# 使用示例
if __name__ == "__main__":
    qa_system = QGISOperatorQA(use_mock=False)

    print("\n" + "="*80)
    print("QGIS Operator QA System Demo")
    print("="*80)

    # 示例1：询问算子功能
    print("\n--- Question 1: What does this operator do? ---")
    answer1 = qa_system.answer_question(
        operator_name="Raster calculator",
        question="Raster calculator is used for what?"
    )
    print(f"Answer: {answer1[:200]}...")

    # 示例2：RAG问答
    print("\n--- Question 2: RAG-based QA ---")
    if qa_system.rag_builder:
        answer2 = qa_system.answer_with_rag(
            question="Buffer vectors has what parameters?",
            operator_name="Buffer vectors"
        )
        print(f"Answer: {answer2[:200]}...")
    else:
        print("RAG builder not initialized, skipping RAG test")

    qa_system.close()

    print("\n" + "="*80)
    print("Demo Complete")
    print("="*80)
