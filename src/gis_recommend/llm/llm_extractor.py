"""
llm_extractor.py
Phase 1: LLM提取结构化信息模块

功能：
1. 使用LLM从归一化后的文本中提取结构化信息
2. 定义硬字段（必须有）和软字段（可选）
3. 返回带confidence和missing_fields的JSON

设计理念：
- 硬字段缺失时补默认值/unknown
- 软字段可选
- 带置信度和缺失字段信息，用于可解释和可回退
"""

import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
import os


@dataclass
class TaskInfo:
    """任务信息结构"""
    # 硬字段（必须有）
    task_name: str
    task_description: str
    constraints: Dict[str, Any]  # 核心约束（支持单值或多值列表）
    inputs: List[str]  # 输入类型
    outputs: List[str]  # 输出类型
    platform_preference: str  # QGIS/GEE/Any
    roi: str  # required/optional/unknown

    # 软字段（可选）
    sensor: Optional[str] = None
    resolution: Optional[str] = None
    time_range: Optional[str] = None
    cloud_threshold: Optional[float] = None
    spatial_reference: Optional[str] = None
    output_format: Optional[str] = None
    estimated_steps: Optional[int] = None  # LLM估计的处理步骤数

    # 元信息
    confidence: float = 0.0
    missing_fields: List[str] = None

    def __post_init__(self):
        if self.missing_fields is None:
            self.missing_fields = []


class LLMTaskExtractor:
    """使用LLM提取任务信息"""

    def __init__(
        self,
        llm_backend: str = "openai",
        api_key: Optional[str] = None,
        model_name: str = "gpt-4",
        base_url: Optional[str] = None  # 支持自定义base_url（如OpenRouter）
    ):
        """
        初始化LLM任务提取器

        参数:
            llm_backend: LLM后端类型 ("openai", "claude", "local")
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

        elif self.llm_backend == "claude":
            try:
                import anthropic
                self.client = anthropic.Anthropic(api_key=self.api_key)
            except ImportError:
                raise ImportError("请安装anthropic: pip install anthropic")

        elif self.llm_backend == "local":
            self.client = None
            print("[INFO] 使用本地LLM模型")

        else:
            raise ValueError(f"不支持的LLM后端: {self.llm_backend}")

    def _build_extraction_prompt(
        self,
        user_query: str,
        normalized_constraints: Dict[str, str]
    ) -> str:
        """
        构建提取任务信息的prompt

        参数:
            user_query: 用户原始查询
            normalized_constraints: 归一化后的约束

        返回:
            prompt字符串
        """
        constraints_str = json.dumps(normalized_constraints, ensure_ascii=False, indent=2)

        prompt = f"""你是一个GIS工作流分析专家。用户描述了一个GIS任务需求，我们已经通过规则提取了一些约束。
现在需要你提取完整的结构化任务信息。

用户原始输入：
"{user_query}"

已提取的约束（规则匹配）：
{constraints_str}

请提取以下信息，并以JSON格式返回：

**硬字段（必须有，缺失则填默认值）：**
1. task_name: 任务名称（简短标题，10-20字）
2. task_description: 任务描述（详细说明，50-100字，包含技术细节）
3. constraints: 核心约束（dict）
   - 必须包含：index（指标）, temporal（时间特征）, roi（是否需要ROI）
   - 可选：aggregation, cloud_mask, spatial_op, statistics等
   - 优先使用已提取的约束，必要时补充
4. inputs: 输入数据类型（list），如 ["raster", "vector", "time_series"]
5. outputs: 输出类型（list），如 ["raster", "curve", "statistics"]
6. platform_preference: 平台偏好（"QGIS" / "GEE" / "Any"）
7. roi: ROI需求（"required" / "optional" / "unknown"）

**软字段（可选）：**
- sensor: 传感器（如 "Sentinel-2", "Landsat-8"）
- resolution: 分辨率（如 "10m", "30m"）
- time_range: 时间范围（如 "2020-2023", "last_year"）
- cloud_threshold: 云量阈值（如 0.2）
- spatial_reference: 空间参考（如 "EPSG:4326"）
- output_format: 输出格式（如 "GeoTIFF", "Shapefile"）
- estimated_steps: 预估处理步骤数（整数，如 3, 5, 8）。根据任务复杂度估计需要多少个独立的处理步骤。简单任务（如"算坡度"）约2-3步，中等任务（如"算坡度并分类"）约4-6步，复杂流程（如"多源数据融合分析"）约7-12步。

**元信息：**
- confidence: 整体置信度（0-1），基于信息完整度和明确性
- missing_fields: 缺失或不确定的字段列表

**输出格式（纯JSON）：**
{{
  "task_name": "...",
  "task_description": "...",
  "constraints": {{
    "index": "...",
    "temporal": "...",
    "roi": "...",
    ...
  }},
  "inputs": ["..."],
  "outputs": ["..."],
  "platform_preference": "...",
  "roi": "...",
  "sensor": "...",
  "resolution": null,
  "time_range": null,
  "cloud_threshold": null,
  "spatial_reference": null,
  "output_format": null,
  "estimated_steps": 5,
  "confidence": 0.85,
  "missing_fields": ["resolution", "time_range"]
}}

**重要提示：**
1. 硬字段不能为null，缺失时填"unknown"或空列表
2. 软字段可以为null
3. constraints必须包含index, temporal, roi三个核心字段
4. confidence基于：信息完整度、明确性、是否有歧义
5. missing_fields列出用户未明确提供的重要信息

请直接输出JSON，不要有其他文字。"""

        return prompt

    def extract(
        self,
        user_query: str,
        normalized_constraints: Dict[str, str]
    ) -> TaskInfo:
        """
        提取任务信息

        参数:
            user_query: 用户原始查询
            normalized_constraints: 归一化后的约束

        返回:
            TaskInfo对象
        """
        prompt = self._build_extraction_prompt(user_query, normalized_constraints)

        # 调用LLM
        try:
            if self.llm_backend == "openai":
                response = self.client.chat.completions.create(
                    model=self.model_name,
                    messages=[
                        {
                            "role": "system",
                            "content": "你是一个GIS工作流分析专家，擅长从用户需求中提取结构化信息。"
                        },
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.3,
                    max_tokens=1000
                )
                llm_output = response.choices[0].message.content

            elif self.llm_backend == "claude":
                response = self.client.messages.create(
                    model=self.model_name,
                    max_tokens=1000,
                    temperature=0.3,
                    messages=[
                        {"role": "user", "content": prompt}
                    ]
                )
                llm_output = response.content[0].text

            elif self.llm_backend == "local":
                llm_output = self._call_local_llm(prompt)

            # 解析LLM输出
            task_data = self._parse_llm_output(llm_output)

            # 验证和补全
            task_data = self._validate_and_complete(task_data, normalized_constraints)

            # 创建TaskInfo对象
            task_info = TaskInfo(**task_data)

            return task_info

        except Exception as e:
            print(f"[ERROR] LLM提取失败: {e}")
            # 返回默认TaskInfo
            return self._create_fallback_task_info(user_query, normalized_constraints)

    def _parse_llm_output(self, llm_output: str) -> Dict:
        """解析LLM输出"""
        try:
            # 提取JSON（处理可能的markdown代码块）
            if "```json" in llm_output:
                json_str = llm_output.split("```json")[1].split("```")[0].strip()
            elif "```" in llm_output:
                json_str = llm_output.split("```")[1].split("```")[0].strip()
            else:
                json_str = llm_output.strip()

            task_data = json.loads(json_str)
            return task_data

        except (json.JSONDecodeError, IndexError) as e:
            raise ValueError(f"解析LLM输出失败: {e}\nLLM输出: {llm_output}")

    def _validate_and_complete(
        self,
        task_data: Dict,
        normalized_constraints: Dict[str, List[str]]
    ) -> Dict:
        """验证和补全任务数据"""

        # 确保硬字段存在
        if "task_name" not in task_data or not task_data["task_name"]:
            task_data["task_name"] = "Unknown Task"

        if "task_description" not in task_data or not task_data["task_description"]:
            task_data["task_description"] = "No description provided"

        if "constraints" not in task_data:
            task_data["constraints"] = {}

        # 确保核心约束存在
        core_constraints = ["index", "temporal", "roi"]
        for key in core_constraints:
            if key not in task_data["constraints"]:
                # 尝试从normalized_constraints获取
                if key in normalized_constraints:
                    # normalized_constraints 现在是 List[str]
                    task_data["constraints"][key] = normalized_constraints[key][0] if normalized_constraints[key] else "unknown"
                else:
                    task_data["constraints"][key] = "unknown"

        # 确保inputs和outputs是列表
        if "inputs" not in task_data or not isinstance(task_data["inputs"], list):
            task_data["inputs"] = ["unknown"]

        if "outputs" not in task_data or not isinstance(task_data["outputs"], list):
            task_data["outputs"] = ["unknown"]

        # 确保platform_preference存在
        if "platform_preference" not in task_data:
            task_data["platform_preference"] = "Any"

        # 确保roi存在
        if "roi" not in task_data:
            roi_values = task_data["constraints"].get("roi", "unknown")
            if isinstance(roi_values, list):
                task_data["roi"] = roi_values[0]
            else:
                task_data["roi"] = roi_values

        # 确保confidence存在
        if "confidence" not in task_data:
            task_data["confidence"] = 0.5

        # 确保missing_fields存在
        if "missing_fields" not in task_data:
            task_data["missing_fields"] = []

        return task_data

    def _create_fallback_task_info(
        self,
        user_query: str,
        normalized_constraints: Dict[str, List[str]]
    ) -> TaskInfo:
        """创建fallback TaskInfo（LLM失败时使用）"""
        # 辅助函数：从多值约束中获取第一个值
        def get_first_value(key: str, default: str = "unknown") -> str:
            values = normalized_constraints.get(key, [])
            return values[0] if values else default

        return TaskInfo(
            task_name=user_query[:50],
            task_description=user_query,
            constraints=normalized_constraints or {
                "index": ["unknown"],
                "temporal": ["unknown"],
                "roi": ["unknown"]
            },
            inputs=["unknown"],
            outputs=["unknown"],
            platform_preference="Any",
            roi=get_first_value("roi"),
            confidence=0.3,
            missing_fields=["all"]
        )

    def _call_local_llm(self, prompt: str) -> str:
        """调用本地LLM"""
        raise NotImplementedError("本地LLM调用尚未实现")


# 使用示例
if __name__ == "__main__":
    # 注意：需要设置OPENAI_API_KEY环境变量
    # 或者在初始化时传入api_key参数

    # 模拟测试（不实际调用LLM）
    print("=" * 80)
    print("LLM提取模块测试")
    print("=" * 80)

    # 创建一个模拟的TaskInfo
    task_info = TaskInfo(
        task_name="NDVI时间序列分析",
        task_description="计算NDVI并进行时间序列分析，识别植被变化趋势，按月统计",
        constraints={
            "index": "NDVI",
            "temporal": "timeseries",
            "aggregation": "monthly",
            "roi": "required"
        },
        inputs=["raster_time_series"],
        outputs=["ndvi_curve", "ndvi_stack"],
        platform_preference="GEE",
        roi="required",
        sensor="Sentinel-2",
        confidence=0.85,
        missing_fields=["resolution", "time_range"]
    )

    print("\n提取的任务信息:")
    print(json.dumps(asdict(task_info), ensure_ascii=False, indent=2))

    print("\n[INFO] 实际使用时需要设置OPENAI_API_KEY环境变量")
    print("[INFO] 或在初始化时传入api_key参数")
