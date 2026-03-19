"""
llm_scorer.py

LLM候选评分模块

功能：
1. 使用LLM对候选QGIS算子进行语义评分
2. 考虑上下文、任务意图、约束条件
3. 生成可解释的选择理由
"""

import json
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import os


@dataclass
class LLMScoringResult:
    """LLM评分结果"""
    selected_operator: str
    score: float
    reasoning: str
    alternative_suggestions: List[Dict] = None


class LLMScorer:
    """
    LLM候选评分器

    使用大语言模型对候选QGIS算子进行语义评分和选择
    """

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "qwen-plus",
        temperature: float = 0.1,
        use_mock: bool = False,  # 默认使用真实API
        base_url: str = "https://dashscope.aliyuncs.com/compatible-mode/v1"
    ):
        """
        初始化LLM评分器

        参数:
            api_key: API密钥（阿里云千问或OpenAI）
            model: 使用的模型（默认qwen-plus）
            temperature: 温度参数（越低越确定）
            use_mock: 是否使用mock模式（用于测试）
            base_url: API基础URL（阿里云千问或OpenAI）
        """
        self.api_key = api_key or os.getenv("DASHSCOPE_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.model = model
        self.temperature = temperature
        self.use_mock = use_mock
        self.base_url = base_url

        if not self.use_mock and not self.api_key:
            print("[WARNING] No API key provided. Using mock mode.")
            self.use_mock = True

        print(f"[INFO] LLM Scorer Initialized")
        print(f"  - Model: {model}")
        print(f"  - Base URL: {base_url}")
        print(f"  - Temperature: {temperature}")
        print(f"  - Mode: {'Mock' if use_mock else 'Real API'}")

    def _build_prompt(
        self,
        l3_code: str,
        unknown_type: str,
        candidates: List[Dict],
        context: Dict,
        constraints: Dict
    ) -> str:
        """
        构建LLM评分的prompt

        参数:
            l3_code: L3代码
            unknown_type: Unknown类型
            candidates: 候选列表
            context: 上下文信息
            constraints: 约束条件

        返回:
            Prompt字符串
        """
        # 格式化候选列表
        candidates_text = ""
        for i, cand in enumerate(candidates, 1):
            candidates_text += f"{i}. {cand['operator_name']}\n"
            candidates_text += f"   - Confidence: {cand['confidence']:.3f}\n"
            candidates_text += f"   - Source: {cand['source']}\n"

        # 格式化上下文
        context_text = f"""
Previous Operator: {context.get('prev_operator', 'None')}
Next Operator: {context.get('next_operator', 'None')}
Previous L3: {context.get('prev_l3', 'None')}
Next L3: {context.get('next_l3', 'None')}
"""

        # 格式化约束
        constraints_text = f"""
Platform: {constraints.get('platform', 'QGIS')}
Output Type: {constraints.get('output_type', 'Any')}
Allow Plugin: {constraints.get('allow_plugin', False)}
Allow Custom Script: {constraints.get('allow_custom_script', False)}
Position Type: {constraints.get('position_type', 'middle')}
"""

        # 构建完整prompt
        prompt = f"""You are an expert in GIS (Geographic Information Systems) and QGIS tool selection.

Task: Select the best QGIS operator to replace an UNKNOWN placeholder in a GIS workflow.

## Unknown Placeholder Information
- L3 Code: {l3_code}
- Unknown Type: {unknown_type}
- Description: This is a placeholder for a missing operator in the workflow

## Context
{context_text}

## Candidate QGIS Operators
{candidates_text}

## Constraints
{constraints_text}

## Instructions
1. Analyze each candidate operator considering:
   - Semantic fit with the unknown type
   - Compatibility with previous and next operators
   - Satisfaction of constraints
   - Typical usage in GIS workflows

2. Select the BEST candidate operator

3. Provide your response in the following JSON format:
{{
    "selected_operator": "operator name",
    "score": 0.0-1.0,
    "reasoning": "Brief explanation (2-3 sentences) of why this operator is the best choice",
    "alternative_suggestions": [
        {{"operator": "alternative 1", "reason": "why it could work"}},
        {{"operator": "alternative 2", "reason": "why it could work"}}
    ]
}}

Important:
- Only select from the provided candidates
- Score should reflect your confidence (0.0-1.0)
- Reasoning should be concise and technical
- If no candidate is suitable, select the best available and explain limitations in reasoning
"""

        return prompt

    def _call_llm_api(self, prompt: str) -> Dict:
        """
        调用LLM API（支持阿里云千问和OpenAI）

        参数:
            prompt: Prompt字符串

        返回:
            LLM响应（JSON格式）
        """
        if self.use_mock:
            return self._mock_llm_response(prompt)

        try:
            from openai import OpenAI

            # 创建客户端（支持阿里云千问和OpenAI）
            client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )

            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a GIS expert specializing in QGIS tool selection."},
                    {"role": "user", "content": prompt}
                ],
                temperature=self.temperature,
                max_tokens=500
            )

            content = response.choices[0].message.content

            # 尝试解析JSON响应
            try:
                result = json.loads(content)
                return result
            except json.JSONDecodeError:
                # 如果不是JSON格式，尝试提取信息
                print(f"[WARNING] LLM response is not valid JSON, using fallback parsing")
                print(f"Response: {content[:200]}...")
                return self._parse_non_json_response(content, prompt)

        except Exception as e:
            print(f"[ERROR] LLM API call failed: {e}")
            print(f"[INFO] Falling back to mock mode")
            return self._mock_llm_response(prompt)

    def _parse_non_json_response(self, content: str, prompt: str) -> Dict:
        """
        解析非JSON格式的LLM响应

        参数:
            content: LLM响应内容
            prompt: 原始prompt

        返回:
            解析后的字典
        """
        # 简单的启发式解析
        # 尝试从响应中提取算子名称
        lines = content.split('\n')
        selected_operator = "Unknown"

        # 从prompt中提取候选列表
        candidates = []
        in_candidates = False
        for line in prompt.split('\n'):
            if "## Candidate QGIS Operators" in line:
                in_candidates = True
                continue
            if in_candidates and line.strip().startswith("##"):
                break
            if in_candidates and line.strip() and line.strip()[0].isdigit():
                parts = line.split('. ', 1)
                if len(parts) > 1:
                    op_name = parts[1].split('\n')[0].strip()
                    candidates.append(op_name)

        # 尝试在响应中找到候选算子
        for cand in candidates:
            if cand.lower() in content.lower():
                selected_operator = cand
                break

        return {
            "selected_operator": selected_operator,
            "score": 0.7,
            "reasoning": content[:200] if len(content) > 200 else content,
            "alternative_suggestions": []
        }

    def _mock_llm_response(self, prompt: str) -> Dict:
        """
        Mock LLM响应（用于测试）

        参数:
            prompt: Prompt字符串

        返回:
            Mock响应
        """
        # 从prompt中提取候选列表
        lines = prompt.split('\n')
        candidates = []
        in_candidates = False

        for line in lines:
            if "## Candidate QGIS Operators" in line:
                in_candidates = True
                continue
            if in_candidates and line.strip().startswith("##"):
                break
            if in_candidates and line.strip() and line.strip()[0].isdigit():
                # 提取算子名
                parts = line.split('. ', 1)
                if len(parts) > 1:
                    candidates.append(parts[1].strip())

        # 简单选择第一个候选（mock逻辑）
        if candidates:
            selected = candidates[0]
            alternatives = [
                {"operator": cand, "reason": "Alternative option with similar functionality"}
                for cand in candidates[1:3]
            ]

            return {
                "selected_operator": selected,
                "score": 0.75,
                "reasoning": f"Selected {selected} based on semantic similarity with the unknown type and compatibility with surrounding operators. This operator is commonly used in similar GIS workflows.",
                "alternative_suggestions": alternatives
            }
        else:
            return {
                "selected_operator": "Unknown",
                "score": 0.0,
                "reasoning": "No suitable candidates found",
                "alternative_suggestions": []
            }

    def score_candidates(
        self,
        l3_code: str,
        unknown_type: str,
        candidates: List[Dict],
        context: Dict,
        constraints: Dict
    ) -> LLMScoringResult:
        """
        使用LLM对候选进行评分和选择

        参数:
            l3_code: L3代码
            unknown_type: Unknown类型
            candidates: 候选列表（每个候选是dict，包含operator_name, confidence, source）
            context: 上下文信息
            constraints: 约束条件

        返回:
            LLMScoringResult对象
        """
        print(f"\n[LLM Scoring] L3: {l3_code}, Type: {unknown_type}")
        print(f"  Candidates: {len(candidates)}")

        # 构建prompt
        prompt = self._build_prompt(
            l3_code=l3_code,
            unknown_type=unknown_type,
            candidates=candidates,
            context=context,
            constraints=constraints
        )

        # 调用LLM API
        response = self._call_llm_api(prompt)

        # 解析响应
        selected_operator = response.get("selected_operator", "Unknown")
        score = response.get("score", 0.0)
        reasoning = response.get("reasoning", "No reasoning provided")
        alternatives = response.get("alternative_suggestions", [])

        print(f"  Selected: {selected_operator}")
        print(f"  Score: {score:.3f}")
        print(f"  Reasoning: {reasoning[:100]}...")

        return LLMScoringResult(
            selected_operator=selected_operator,
            score=score,
            reasoning=reasoning,
            alternative_suggestions=alternatives
        )

    def score_chain(
        self,
        user_task: str,
        qgis_chain: list,
        rag_context: str,
    ) -> dict:
        """
        Use LLM to score an entire QGIS operator chain against a user task.

        Args:
            user_task: User's natural language task description
            qgis_chain: List of QGIS operator names
            rag_context: Structured context from RAGContextBuilder.build_chain_context()

        Returns:
            {"score": float 0-10, "reasoning": str}
        """
        chain_text = " -> ".join(qgis_chain)
        prompt = f"""You are a GIS workflow evaluation expert.

## User Task
{user_task}

## Candidate QGIS Operator Chain
{chain_text}

## Knowledge Graph Context
{rag_context}

## Instructions
Evaluate how well this operator chain accomplishes the user's task.
Consider:
1. Does the chain contain the essential operations for this task?
2. Is the operator ordering logical (data flows correctly)?
3. Are there redundant or irrelevant operators?
4. Are there missing critical steps?

Respond in JSON:
{{
    "score": <0-10, where 10 is perfect>,
    "reasoning": "<2-3 sentences explaining your evaluation>"
}}
"""
        response = self._call_llm_api(prompt)
        score = response.get("score", 5.0)
        if isinstance(score, str):
            try:
                score = float(score)
            except ValueError:
                score = 5.0
        reasoning = response.get("reasoning", "No reasoning provided")
        return {"score": min(max(score, 0.0), 10.0), "reasoning": reasoning}


# 使用示例
if __name__ == "__main__":
    # 初始化LLM评分器（mock模式）
    scorer = LLMScorer(use_mock=True)

    # 测试候选
    test_candidates = [
        {
            "operator_name": "Raster calculator",
            "confidence": 0.75,
            "source": "keyword_match"
        },
        {
            "operator_name": "BandMath",
            "confidence": 0.70,
            "source": "keyword_match"
        },
        {
            "operator_name": "Raster band math",
            "confidence": 0.65,
            "source": "similar_l3"
        }
    ]

    test_context = {
        "prev_operator": "Merge raster layers",
        "next_operator": "Raster to vector",
        "prev_l3": "L3_01_03_04",
        "next_l3": "L3_01_09_03"
    }

    test_constraints = {
        "platform": "QGIS",
        "output_type": "raster",
        "allow_plugin": False,
        "allow_custom_script": False,
        "position_type": "middle"
    }

    print("\n" + "="*80)
    print("Test: LLM Candidate Scoring")
    print("="*80)

    result = scorer.score_candidates(
        l3_code="L3_INDEX_CALC",
        unknown_type="index_compute",
        candidates=test_candidates,
        context=test_context,
        constraints=test_constraints
    )

    print("\n" + "="*80)
    print("LLM Scoring Result")
    print("="*80)
    print(f"Selected Operator: {result.selected_operator}")
    print(f"Score: {result.score:.3f}")
    print(f"Reasoning: {result.reasoning}")
    print(f"\nAlternative Suggestions:")
    for i, alt in enumerate(result.alternative_suggestions, 1):
        print(f"  {i}. {alt['operator']}")
        print(f"     Reason: {alt['reason']}")
