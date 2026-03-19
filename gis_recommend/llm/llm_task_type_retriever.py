"""
llm_task_type_retriever.py
Phase 3: task_type混合检索模块

功能：
1. Embedding检索：使用向量相似度快速筛选候选
2. LLM选择：从候选列表中选择最合适的task_type（带约束输出）
3. 结合知识图谱：利用Neo4j中的层级关系

设计理念：
- 先用embedding快速筛选（效率）
- 再用LLM精确选择（准确性）
- 带约束输出避免幻觉（可靠性）
"""

import json
import os
from typing import List, Dict, Tuple, Optional
from dataclasses import dataclass
import numpy as np


@dataclass
class TaskTypeCandidate:
    """task_type候选"""
    task_type: str
    task_type_id: int
    score: float  # 相似度分数
    rank: int  # 排名


class TaskTypeEmbeddingRetriever:
    """基于Embedding的task_type检索器"""

    def __init__(
        self,
        task_vocab_path: str,
        embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2",
        top_k: int = 10
    ):
        """
        初始化Embedding检索器

        参数:
            task_vocab_path: task_type词汇表路径
            embedding_model: embedding模型名称
            top_k: 返回top-k候选
        """
        self.task_vocab_path = task_vocab_path
        self.embedding_model_name = embedding_model
        self.top_k = top_k

        # 加载task_type词汇表
        self.task_type_to_id, self.id_to_task_type = self._load_vocabulary()

        # 初始化embedding模型
        self.embedding_model = None
        self.task_type_embeddings = None
        self._init_embedding_model()

    def _load_vocabulary(self) -> Tuple[Dict[str, int], Dict[int, str]]:
        """加载task_type词汇表"""
        with open(self.task_vocab_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        task_type_to_id = data['task_type_to_id']
        id_to_task_type = {v: k for k, v in task_type_to_id.items()}

        print(f"[INFO] 加载了 {len(task_type_to_id)} 个task_type")
        return task_type_to_id, id_to_task_type

    def _init_embedding_model(self):
        """初始化embedding模型"""
        try:
            from sentence_transformers import SentenceTransformer
            print(f"[INFO] 加载embedding模型: {self.embedding_model_name}")
            self.embedding_model = SentenceTransformer(self.embedding_model_name)

            # 预计算所有task_type的embedding
            task_types = list(self.task_type_to_id.keys())
            print(f"[INFO] 预计算 {len(task_types)} 个task_type的embedding...")
            self.task_type_embeddings = self.embedding_model.encode(
                task_types,
                show_progress_bar=True,
                convert_to_numpy=True
            )
            print(f"[INFO] Embedding shape: {self.task_type_embeddings.shape}")

        except ImportError:
            print("[WARNING] sentence-transformers未安装，将使用fallback方法")
            print("[WARNING] 安装: pip install sentence-transformers")
            self.embedding_model = None

    def retrieve(
        self,
        query: str,
        task_description: str = None,
        constraints: Dict = None
    ) -> List[TaskTypeCandidate]:
        """
        检索task_type候选

        参数:
            query: 用户查询
            task_description: 任务描述（可选）
            constraints: 约束条件（可选）

        返回:
            候选列表
        """
        if self.embedding_model is None:
            # Fallback: 返回所有task_type
            return self._fallback_retrieve()

        # 构建检索文本
        search_text = query
        if task_description:
            search_text += " " + task_description

        # 计算query embedding
        query_embedding = self.embedding_model.encode(
            search_text,
            convert_to_numpy=True
        )

        # 计算余弦相似度
        similarities = self._cosine_similarity(
            query_embedding,
            self.task_type_embeddings
        )

        # 获取top-k
        top_k_indices = np.argsort(similarities)[::-1][:self.top_k]

        # 构建候选列表
        candidates = []
        task_types = list(self.task_type_to_id.keys())

        for rank, idx in enumerate(top_k_indices, 1):
            task_type = task_types[idx]
            task_type_id = self.task_type_to_id[task_type]
            score = float(similarities[idx])

            candidate = TaskTypeCandidate(
                task_type=task_type,
                task_type_id=task_type_id,
                score=score,
                rank=rank
            )
            candidates.append(candidate)

        return candidates

    def _cosine_similarity(
        self,
        query_embedding: np.ndarray,
        task_embeddings: np.ndarray
    ) -> np.ndarray:
        """计算余弦相似度"""
        # 归一化
        query_norm = query_embedding / np.linalg.norm(query_embedding)
        task_norms = task_embeddings / np.linalg.norm(
            task_embeddings,
            axis=1,
            keepdims=True
        )

        # 计算余弦相似度
        similarities = np.dot(task_norms, query_norm)
        return similarities

    def _fallback_retrieve(self) -> List[TaskTypeCandidate]:
        """Fallback方法：返回前10个task_type"""
        print("[WARNING] 使用fallback检索方法")
        candidates = []
        task_types = list(self.task_type_to_id.keys())[:self.top_k]

        for rank, task_type in enumerate(task_types, 1):
            task_type_id = self.task_type_to_id[task_type]
            candidate = TaskTypeCandidate(
                task_type=task_type,
                task_type_id=task_type_id,
                score=0.5,  # 默认分数
                rank=rank
            )
            candidates.append(candidate)

        return candidates


class TaskTypeLLMSelector:
    """基于LLM的task_type选择器（带约束输出）"""

    def __init__(
        self,
        llm_backend: str = "openai",
        api_key: Optional[str] = None,
        model_name: str = "gpt-4",
        base_url: Optional[str] = None  # 支持自定义base_url（如OpenRouter）
    ):
        """
        初始化LLM选择器

        参数:
            llm_backend: LLM后端类型
            api_key: API密钥
            model_name: 模型名称（如 "gpt-4" 或 "openai/gpt-5-mini" for OpenRouter）
            base_url: 自定义API endpoint（如 "https://openrouter.ai/api/v1" for OpenRouter）
        """
        self.llm_backend = llm_backend
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model_name = model_name
        self.base_url = base_url

        # 初始化LLM客户端
        self._init_llm_client()

    def _init_llm_client(self):
        """初始化LLM客户端"""
        if self.llm_backend == "openai":
            try:
                import openai
                # 支持自定义base_url（如OpenRouter）
                if self.base_url:
                    self.client = openai.OpenAI(
                        api_key=self.api_key,
                        base_url=self.base_url
                    )
                    print(f"[INFO] 使用自定义OpenAI兼容API: {self.base_url}")
                else:
                    self.client = openai.OpenAI(api_key=self.api_key)
            except ImportError:
                raise ImportError("请安装openai: pip install openai")
                self.client = openai.OpenAI(api_key=self.api_key)
            except ImportError:
                raise ImportError("请安装openai: pip install openai")

        elif self.llm_backend == "claude":
            try:
                import anthropic
                self.client = anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                raise ImportError("请安装anthropic: pip install anthropic")

        else:
            raise ValueError(f"不支持的LLM后端: {self.llm_backend}")

    def select(
        self,
        query: str,
        task_description: str,
        constraints: Dict,
        candidates: List[TaskTypeCandidate]
    ) -> Tuple[str, int, float]:
        """
        从候选中选择最合适的task_type（带约束输出）

        参数:
            query: 用户查询
            task_description: 任务描述
            constraints: 约束条件
            candidates: 候选列表

        返回:
            (task_type, task_type_id, confidence)
        """
        # 构建prompt
        prompt = self._build_selection_prompt(
            query,
            task_description,
            constraints,
            candidates
        )

        # 调用LLM
        try:
            if self.llm_backend == "openai":
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {
                            "role": "system",
                            "content": "你是一个GIS任务分类专家。从给定的候选列表中选择最合适的task_type。"
                        },
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_tokens=200
                )
                llm_output = response.choices[0].message.content

            elif self.llm_backend == "claude":
                response = self.client.messages.create(
                    model=self.model_name,
                    max_tokens=200,
                    temperature=0.3,
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
                llm_output = response.content[0].text

            # 解析LLM输出
            selected_task_type, confidence = self._parse_llm_output(
                llm_output,
                candidates
            )

            # 获取task_type_id
            task_type_id = candidates[0].task_type_id
            for candidate in candidates:
                if candidate.task_type == selected_task_type:
                    task_type_id = candidate.task_type_id
                    break

            return selected_task_type, task_type_id, confidence

        except Exception as e:
            print(f"[ERROR] LLM选择失败: {e}")
            # Fallback: 返回第一个候选
            return (
                candidates[0].task_type,
                candidates[0].task_type_id,
                candidates[0].score
            )

    def _build_selection_prompt(
        self,
        query: str,
        task_description: str,
        constraints: Dict,
        candidates: List[TaskTypeCandidate]
    ) -> str:
        """构建选择prompt"""
        # 格式化候选列表
        candidates_str = "\n".join([
            f"{i+1}. {c.task_type} (相似度: {c.score:.3f})"
            for i, c in enumerate(candidates)
        ])

        # 格式化约束
        constraints_str = json.dumps(constraints, ensure_ascii=False, indent=2)

        prompt = f"""你是一个GIS任务分类专家。请从以下候选列表中选择最合适的task_type。

**用户查询**:
"{query}"

**任务描述**:
"{task_description}"

**约束条件**:
{constraints_str}

**候选task_type列表**（按相似度排序）:
{candidates_str}

**要求**:
1. 你必须从上述候选列表中选择一个task_type，不能选择列表之外的
2. 考虑用户查询、任务描述和约束条件
3. 返回格式：选择的task_type名称 | 置信度(0-1)

**示例输出**:
Land use/land cover | 0.85

**你的选择**:"""

        return prompt

    def _parse_llm_output(
        self,
        llm_output: str,
        candidates: List[TaskTypeCandidate]
    ) -> Tuple[str, float]:
        """解析LLM输出"""
        try:
            # 解析格式: "task_type | confidence"
            parts = llm_output.strip().split("|")
            selected_task_type = parts[0].strip()
            confidence = float(parts[1].strip()) if len(parts) > 1 else 0.8

            # 验证是否在候选列表中
            candidate_names = [c.task_type for c in candidates]
            if selected_task_type not in candidate_names:
                print(f"[WARNING] LLM选择的task_type不在候选列表中: {selected_task_type}")
                print(f"[WARNING] 使用第一个候选: {candidates[0].task_type}")
                return candidates[0].task_type, candidates[0].score

            return selected_task_type, confidence

        except Exception as e:
            print(f"[ERROR] 解析LLM输出失败: {e}")
            print(f"[ERROR] LLM输出: {llm_output}")
            return candidates[0].task_type, candidates[0].score


class TaskTypeHybridRetriever:
    """混合task_type检索器（Embedding + LLM）"""

    def __init__(
        self,
        task_vocab_path: str,
        embedding_model: str = "sentence-transformers/all-MiniLM-L6-v2",
        llm_backend: str = "openai",
        api_key: Optional[str] = None,
        model_name: str = "gpt-4",  # 添加model_name参数
        base_url: Optional[str] = None,  # 添加base_url参数
        top_k: int = 10,
        use_llm_selection: bool = True
    ):
        """
        初始化混合检索器

        参数:
            task_vocab_path: task_type词汇表路径
            embedding_model: embedding模型名称
            llm_backend: LLM后端类型
            api_key: API密钥
            model_name: LLM模型名称（如 "gpt-4" 或 "openai/gpt-5-mini" for OpenRouter）
            base_url: 自定义API endpoint（如 "https://openrouter.ai/api/v1" for OpenRouter）
            top_k: embedding检索返回top-k候选
            use_llm_selection: 是否使用LLM选择（False则直接返回top-1）
        """
        self.use_llm_selection = use_llm_selection

        # 初始化embedding检索器
        self.embedding_retriever = TaskTypeEmbeddingRetriever(
            task_vocab_path=task_vocab_path,
            embedding_model=embedding_model,
            top_k=top_k
        )

        # 初始化LLM选择器
        if use_llm_selection:
            self.llm_selector = TaskTypeLLMSelector(
                llm_backend=llm_backend,
                api_key=api_key,
                model_name=model_name,
                base_url=base_url
            )
        else:
            self.llm_selector = None

    def retrieve_and_select(
        self,
        query: str,
        task_description: str,
        constraints: Dict
    ) -> Tuple[str, int, float, List[TaskTypeCandidate]]:
        """
        检索并选择task_type

        参数:
            query: 用户查询
            task_description: 任务描述
            constraints: 约束条件

        返回:
            (task_type, task_type_id, confidence, candidates)
        """
        print("\n[Phase 3] task_type混合检索...")

        # Step 1: Embedding检索
        print(f"[Step 1] Embedding检索 (top-{self.embedding_retriever.top_k})...")
        candidates = self.embedding_retriever.retrieve(
            query=query,
            task_description=task_description,
            constraints=constraints
        )

        print(f"  检索到 {len(candidates)} 个候选:")
        for i, c in enumerate(candidates[:5], 1):
            print(f"    {i}. {c.task_type} (score: {c.score:.3f})")

        # Step 2: LLM选择（可选）
        if self.use_llm_selection and self.llm_selector:
            print(f"\n[Step 2] LLM选择（带约束输出）...")
            task_type, task_type_id, confidence = self.llm_selector.select(
                query=query,
                task_description=task_description,
                constraints=constraints,
                candidates=candidates
            )
            print(f"  选择: {task_type} (id: {task_type_id}, confidence: {confidence:.3f})")
        else:
            # 直接返回top-1
            print(f"\n[Step 2] 跳过LLM选择，使用top-1候选")
            task_type = candidates[0].task_type
            task_type_id = candidates[0].task_type_id
            confidence = candidates[0].score

        return task_type, task_type_id, confidence, candidates


# 使用示例
if __name__ == "__main__":
    # 初始化混合检索器
    retriever = TaskTypeHybridRetriever(
        task_vocab_path="outputs/task_type_vocabulary.json",
        embedding_model="sentence-transformers/all-MiniLM-L6-v2",
        llm_backend="openai",
        top_k=10,
        use_llm_selection=False  # 设为False以跳过LLM调用（测试时）
    )

    # 测试查询
    test_cases = [
        {
            "query": "我想计算NDVI并进行时间序列分析",
            "task_description": "Calculate NDVI and analyze temporal trend",
            "constraints": {"index": ["NDVI"], "temporal": ["timeseries"]}
        },
        {
            "query": "分析土地利用变化",
            "task_description": "Analyze land use change over time",
            "constraints": {"temporal": ["trend"]}
        },
    ]

    for i, test in enumerate(test_cases, 1):
        print(f"\n{'='*80}")
        print(f"测试用例 {i}")
        print(f"{'='*80}")

        task_type, task_type_id, confidence, candidates = retriever.retrieve_and_select(
            query=test["query"],
            task_description=test["task_description"],
            constraints=test["constraints"]
        )

        print(f"\n最终结果:")
        print(f"  task_type: {task_type}")
        print(f"  task_type_id: {task_type_id}")
        print(f"  confidence: {confidence:.3f}")
