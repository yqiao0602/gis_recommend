"""
LLM入口完整流程示例

展示如何将Phase 0/1/2/3串联起来：
用户输入 → 归一化 → LLM提取 → task_type检索 → 模板生成 → 模型输入
"""

import torch
from transformers import BertTokenizer
from typing import Dict, Tuple, Optional, List  # 添加 List 导入

from gis_recommend.llm.llm_normalizer import QueryNormalizer
from gis_recommend.llm.llm_extractor import LLMTaskExtractor, TaskInfo
from gis_recommend.llm.llm_template import StructuredTemplateGenerator
from gis_recommend.llm.llm_task_type_retriever import TaskTypeHybridRetriever  # Phase 3


class LLMWorkflowPipeline:
    """LLM工作流完整流程（包含Phase 3）"""

    def __init__(
        self,
        task_vocab_path: str = "outputs/task_type_vocabulary.json",
        llm_backend: str = "openai",
        api_key: str = None,
        model_name: str = "gpt-4",  # 添加model_name参数
        base_url: Optional[str] = None,  # 添加base_url参数（支持OpenRouter）
        bert_model_name: str = "bert-base-uncased",
        max_text_length: int = 128,
        use_phase3: bool = True,  # 是否使用Phase 3
        use_llm_selection: bool = False  # Phase 3是否使用LLM选择
    ):
        """
        初始化LLM工作流流程

        参数:
            task_vocab_path: 任务类型词汇表路径
            llm_backend: LLM后端
            api_key: API密钥
            model_name: LLM模型名称（如 "gpt-4" 或 "openai/gpt-5-mini" for OpenRouter）
            base_url: 自定义API endpoint（如 "https://openrouter.ai/api/v1" for OpenRouter）
            bert_model_name: BERT模型名称
            max_text_length: 文本最大长度
            use_phase3: 是否使用Phase 3 task_type检索
            use_llm_selection: Phase 3是否使用LLM选择
        """
        # Phase 0: 归一化器
        self.normalizer = QueryNormalizer()

        # Phase 1: LLM提取器
        self.extractor = LLMTaskExtractor(
            llm_backend=llm_backend,
            api_key=api_key,
            model_name=model_name,
            base_url=base_url
        )

        # Phase 2: 模板生成器
        self.template_generator = StructuredTemplateGenerator(template_version="v1")

        # BERT tokenizer
        try:
            self.bert_tokenizer = BertTokenizer.from_pretrained(bert_model_name)
        except:
            print("[WARNING] 无法加载BERT tokenizer，某些功能可能不可用")
            self.bert_tokenizer = None

        self.max_text_length = max_text_length

        # Phase 3: task_type混合检索
        self.use_phase3 = use_phase3
        if use_phase3:
            try:
                self.task_type_retriever = TaskTypeHybridRetriever(
                    task_vocab_path=task_vocab_path,
                    llm_backend=llm_backend,
                    api_key=api_key,
                    model_name=model_name,
                    base_url=base_url,
                    top_k=10,
                    use_llm_selection=use_llm_selection
                )
                print("[INFO] Phase 3 task_type检索已启用")
            except Exception as e:
                print(f"[WARNING] Phase 3初始化失败: {e}")
                self.use_phase3 = False
                self.task_type_retriever = None
        else:
            self.task_type_retriever = None

    def process(
        self,
        user_query: str,
        device: torch.device = torch.device('cpu'),
        use_llm: bool = True
    ) -> Tuple[TaskInfo, str, Dict[str, torch.Tensor]]:
        """
        处理用户查询的完整流程

        参数:
            user_query: 用户自然语言输入
            device: 设备
            use_llm: 是否使用LLM（False时使用规则fallback）

        返回:
            (task_info, template_text, model_input)
        """
        print("=" * 80)
        print("LLM工作流完整流程")
        print("=" * 80)

        # Phase 0: 归一化
        print("\n[Phase 0] 归一化/纠错...")
        normalized_result = self.normalizer.normalize(user_query)
        print(f"  提取的约束: {normalized_result['structured_constraints']}")
        print(f"  置信度: {normalized_result['confidence']:.2f}")

        # Phase 1: LLM提取（或fallback）
        print("\n[Phase 1] LLM提取结构化信息...")
        if use_llm:
            try:
                task_info = self.extractor.extract(
                    user_query,
                    normalized_result['structured_constraints']
                )
                print(f"  任务名称: {task_info.task_name}")
                print(f"  置信度: {task_info.confidence:.2f}")
                if task_info.missing_fields:
                    print(f"  缺失字段: {task_info.missing_fields}")
            except Exception as e:
                print(f"  [WARNING] LLM提取失败，使用fallback: {e}")
                task_info = self._create_fallback_task_info(
                    user_query,
                    normalized_result['structured_constraints']
                )
        else:
            print("  [INFO] 跳过LLM，使用规则fallback")
            task_info = self._create_fallback_task_info(
                user_query,
                normalized_result['structured_constraints']
            )

        # Phase 3: task_type混合检索
        print("\n[Phase 3] task_type混合检索...")
        if self.use_phase3 and self.task_type_retriever:
            try:
                task_type, task_type_id, confidence, candidates = self.task_type_retriever.retrieve_and_select(
                    query=user_query,
                    task_description=task_info.task_description,
                    constraints=task_info.constraints
                )
                print(f"  选择的task_type: {task_type} (id: {task_type_id})")
                print(f"  置信度: {confidence:.3f}")

                # 使用top-5候选作为hints
                task_type_hints = [c.task_type for c in candidates[:5]]
            except Exception as e:
                print(f"  [WARNING] Phase 3失败: {e}")
                task_type_hints = ["Unknown"]
                task_type_id = 0
        else:
            print("  [INFO] Phase 3未启用，使用默认值")
            task_type_hints = ["Vegetation index", "Temporal analysis", "Land cover classification"]
            task_type_id = 0

        # Phase 2: 生成结构化模板
        print("\n[Phase 2] 生成结构化模板...")
        template_text = self.template_generator.generate(
            task_info,
            task_type_hints=task_type_hints
        )
        print(f"  模板长度: {len(template_text)} 字符")

        # 转换为模型输入
        print("\n[转换] 生成模型输入...")
        model_input = self._convert_to_model_input(
            task_type_id,
            template_text,
            device
        )
        print(f"  task_type_id: {model_input['task_type_id'].item()}")
        print(f"  text_input_ids shape: {model_input['text_input_ids'].shape}")

        print("\n" + "=" * 80)
        print("流程完成！")
        print("=" * 80)

        return task_info, template_text, model_input

    def _convert_to_model_input(
        self,
        task_type_id: int,
        template_text: str,
        device: torch.device
    ) -> Dict[str, torch.Tensor]:
        """转换为模型输入"""

        # BERT编码
        encoded = self.bert_tokenizer(
            template_text,
            max_length=self.max_text_length,
            padding='max_length',
            truncation=True,
            return_tensors='pt'
        )

        model_input = {
            "task_type_id": torch.tensor([task_type_id], dtype=torch.long).to(device),
            "text_input_ids": encoded['input_ids'].to(device),
            "text_attention_mask": encoded['attention_mask'].to(device)
        }

        return model_input

    def _create_fallback_task_info(
        self,
        user_query: str,
        normalized_constraints: Dict[str, List[str]]
    ) -> TaskInfo:
        """创建fallback TaskInfo"""
        # 辅助函数：从多值约束中获取第一个值
        def get_first_value(key: str, default: str = "unknown") -> str:
            values = normalized_constraints.get(key, [])
            return values[0] if values else default

        # 辅助函数：获取列表值
        def get_list_values(key: str, default: List[str] = None) -> List[str]:
            return normalized_constraints.get(key, default or ["unknown"])

        return TaskInfo(
            task_name=user_query[:50],
            task_description=user_query,
            constraints=normalized_constraints or {
                "index": ["unknown"],
                "temporal": ["unknown"],
                "roi": ["unknown"]
            },
            inputs=get_list_values("input_type"),
            outputs=get_list_values("output_type"),
            platform_preference="Any",
            roi=get_first_value("roi"),
            sensor=get_first_value("sensor", None),
            confidence=0.6,
            missing_fields=["task_name", "task_description"]
        )


# 使用示例
if __name__ == "__main__":
    # 初始化流程（不使用LLM，仅演示）
    pipeline = LLMWorkflowPipeline(
        llm_backend="openai",
        api_key=None  # 不设置API key，将使用fallback
    )

    # 测试查询
    test_queries = [
        "我想计算NDVI并进行时间序列分析，按月统计",
        "使用Sentinel-2数据计算植被指数，需要去云处理",
    ]

    for query in test_queries:
        print(f"\n\n{'='*80}")
        print(f"用户输入: {query}")
        print(f"{'='*80}")

        # 处理查询（不使用LLM）
        task_info, template_text, model_input = pipeline.process(
            query,
            use_llm=False  # 设为False以跳过LLM调用
        )

        # 显示结果
        print("\n【最终模板】")
        print("-" * 80)
        print(template_text)

        print("\n【模型输入】")
        print("-" * 80)
        print(f"task_type_id: {model_input['task_type_id']}")
        print(f"text_input_ids shape: {model_input['text_input_ids'].shape}")
        print(f"text_attention_mask shape: {model_input['text_attention_mask'].shape}")

        print("\n[INFO] 现在可以将model_input传递给Transformer模型进行推理")
