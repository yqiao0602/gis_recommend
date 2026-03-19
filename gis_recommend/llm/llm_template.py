"""
llm_template.py
Phase 2: 结构化模板文本生成模块

功能：
1. 将LLM提取的结构化信息转换为模板文本
2. 支持版本化（TEMPLATE_VERSION）
3. 包含TASK_TYPE_HINTS（软提示）
4. 显式约束，让模型学到"哪些词是硬条件"

设计理念：
- 不要直接把用户原话或LLM自由文本喂给BERT
- 用稳定的结构化模板，减少歧义
- 可解释，知道模型看到了什么
"""

from typing import Dict, List, Optional
from dataclasses import asdict
from gis_recommend.llm.llm_extractor import TaskInfo


class StructuredTemplateGenerator:
    """结构化模板生成器"""

    def __init__(self, template_version: str = "v1"):
        """
        初始化模板生成器

        参数:
            template_version: 模板版本号
        """
        self.template_version = template_version

    def generate(
        self,
        task_info: TaskInfo,
        task_type_hints: Optional[List[str]] = None
    ) -> str:
        """
        生成结构化模板文本

        参数:
            task_info: 任务信息
            task_type_hints: 任务类型候选列表（可选）

        返回:
            结构化模板文本
        """
        # 构建模板各部分
        parts = []

        # 1. 模板版本
        parts.append(f"TEMPLATE_VERSION: {self.template_version}")

        # 2. 任务名称
        parts.append(f"TASK_NAME: {task_info.task_name}")

        # 3. 任务描述
        parts.append(f"TASK_DESC: {task_info.task_description}")

        # 4. 任务类型提示（如果有）
        if task_type_hints:
            hints_str = ", ".join(task_type_hints)
            parts.append(f"TASK_TYPE_HINTS: [{hints_str}]")

        # 5. 约束条件（核心）
        constraints_str = self._format_constraints(task_info.constraints)
        parts.append(f"CONSTRAINTS: {constraints_str}")

        # 6. 输入
        inputs_str = self._format_list_with_details(
            task_info.inputs,
            sensor=task_info.sensor,
            resolution=task_info.resolution
        )
        parts.append(f"INPUTS: {inputs_str}")

        # 7. 输出
        outputs_str = self._format_list(task_info.outputs)
        parts.append(f"OUTPUTS: {outputs_str}")

        # 8. ROI
        parts.append(f"ROI: {task_info.roi}")

        # 9. 平台偏好
        parts.append(f"PLATFORM: {task_info.platform_preference}")

        # 10. 可选字段（如果有值）
        if task_info.time_range:
            parts.append(f"TIME_RANGE: {task_info.time_range}")

        if task_info.cloud_threshold is not None:
            parts.append(f"CLOUD_THRESHOLD: {task_info.cloud_threshold}")

        if task_info.spatial_reference:
            parts.append(f"SPATIAL_REF: {task_info.spatial_reference}")

        if task_info.output_format:
            parts.append(f"OUTPUT_FORMAT: {task_info.output_format}")

        # 11. 元信息（可选，用于调试）
        # parts.append(f"CONFIDENCE: {task_info.confidence:.2f}")
        # if task_info.missing_fields:
        #     parts.append(f"MISSING_FIELDS: {', '.join(task_info.missing_fields)}")

        # 组合成最终模板
        template = "\n".join(parts)

        return template

    def _format_constraints(self, constraints: Dict[str, any]) -> str:
        """
        格式化约束条件（固定顺序 + 多值支持）

        参数:
            constraints: 约束字典，值可以是 str 或 List[str]

        返回:
            格式化的约束字符串
        """
        # 定义核心字段的固定顺序
        core_fields = [
            'index',
            'temporal',
            'roi',
            'aggregation',
            'cloud_mask',
            'statistics',
            'spatial_op',
            'sensor'
        ]

        items = []

        # 1. 先输出核心字段（按固定顺序）
        for field in core_fields:
            if field in constraints:
                value = constraints[field]
                # 处理多值：用逗号分隔
                if isinstance(value, list):
                    value_str = ",".join(value)
                else:
                    value_str = str(value)
                items.append(f"{field}={value_str}")

        # 2. 再输出其他字段（按字母顺序）
        other_fields = sorted([k for k in constraints.keys() if k not in core_fields])
        for field in other_fields:
            value = constraints[field]
            if isinstance(value, list):
                value_str = ",".join(value)
            else:
                value_str = str(value)
            items.append(f"{field}={value_str}")

        return "; ".join(items)

    def _format_list(self, items: List[str]) -> str:
        """格式化列表"""
        return ", ".join(items)

    def _format_list_with_details(
        self,
        items: List[str],
        **kwargs
    ) -> str:
        """格式化列表（带详细信息）"""
        result = ", ".join(items)

        # 添加额外信息
        details = []
        for key, value in kwargs.items():
            if value:
                details.append(f"{key}={value}")

        if details:
            result += "; " + "; ".join(details)

        return result


class TemplateValidator:
    """模板验证器（P2改进：实际tokenize验证）"""

    def __init__(self, bert_model_name: str = "bert-base-uncased", max_length: int = 128):
        """
        初始化验证器

        参数:
            bert_model_name: BERT模型名称
            max_length: 最大token长度
        """
        self.bert_model_name = bert_model_name
        self.max_length = max_length
        self.tokenizer = None

        # 尝试加载tokenizer（如果transformers可用）
        try:
            from transformers import BertTokenizer
            self.tokenizer = BertTokenizer.from_pretrained(bert_model_name)
        except ImportError:
            print("[WARNING] transformers未安装，将使用字符长度估算")
        except Exception as e:
            print(f"[WARNING] 加载tokenizer失败: {e}，将使用字符长度估算")

    def validate(self, template: str) -> Dict[str, any]:
        """
        验证模板格式（P2改进：实际tokenize验证）

        参数:
            template: 模板文本

        返回:
            {
                "valid": True/False,
                "errors": [...],
                "warnings": [...],
                "token_count": 100,  # P2: 实际token数量
                "char_count": 500    # 字符数量
            }
        """
        errors = []
        warnings = []

        # 必需字段
        required_fields = [
            "TEMPLATE_VERSION",
            "TASK_NAME",
            "TASK_DESC",
            "CONSTRAINTS",
            "INPUTS",
            "OUTPUTS",
            "ROI",
            "PLATFORM"
        ]

        for field in required_fields:
            if field not in template:
                errors.append(f"缺少必需字段: {field}")

        # 检查CONSTRAINTS格式
        if "CONSTRAINTS:" in template:
            constraints_line = [line for line in template.split("\n") if line.startswith("CONSTRAINTS:")][0]
            if "index=" not in constraints_line:
                warnings.append("CONSTRAINTS中缺少index字段")
            if "temporal=" not in constraints_line:
                warnings.append("CONSTRAINTS中缺少temporal字段")
            if "roi=" not in constraints_line:
                warnings.append("CONSTRAINTS中缺少roi字段")

        # P2改进：实际tokenize验证
        char_count = len(template)
        token_count = None

        if self.tokenizer:
            # 使用实际tokenizer
            try:
                encoded = self.tokenizer(
                    template,
                    add_special_tokens=True,
                    return_tensors=None
                )
                token_count = len(encoded['input_ids'])

                if token_count > self.max_length:
                    errors.append(
                        f"模板token数({token_count})超过max_length({self.max_length})"
                    )
                elif token_count > self.max_length * 0.9:
                    warnings.append(
                        f"模板token数({token_count})接近max_length({self.max_length})，建议简化"
                    )
            except Exception as e:
                warnings.append(f"tokenize失败: {e}")
        else:
            # 使用字符长度估算（英文约1.3字符/token，中文约1字符/token）
            estimated_tokens = int(char_count / 1.2)
            token_count = estimated_tokens

            if estimated_tokens > self.max_length:
                warnings.append(
                    f"模板字符数({char_count})估算token数({estimated_tokens})可能超过max_length({self.max_length})"
                )

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "token_count": token_count,
            "char_count": char_count
        }


# 使用示例
if __name__ == "__main__":
    from gis_recommend.llm.llm_extractor import TaskInfo

    print("=" * 80)
    print("结构化模板生成测试")
    print("=" * 80)

    # 创建测试TaskInfo
    task_info = TaskInfo(
        task_name="NDVI time-series analysis",
        task_description="compute NDVI and analyze temporal trend of vegetation",
        constraints={
            "index": "NDVI",
            "temporal": "timeseries",
            "trend": "yes",
            "aggregation": "monthly",
            "cloud_mask": "required"
        },
        inputs=["raster_time_series"],
        outputs=["ndvi_curve", "ndvi_stack"],
        platform_preference="QGIS",
        roi="required",
        sensor="Sentinel-2",
        resolution="10m",
        time_range="2020-2023",
        confidence=0.85,
        missing_fields=[]
    )

    # 生成模板
    generator = StructuredTemplateGenerator(template_version="v1")

    # 测试1：不带task_type_hints
    print("\n【测试1】不带task_type_hints:")
    print("-" * 80)
    template1 = generator.generate(task_info)
    print(template1)

    # 测试2：带task_type_hints
    print("\n\n【测试2】带task_type_hints:")
    print("-" * 80)
    task_type_hints = ["Vegetation index", "Land cover classification", "Temporal analysis"]
    template2 = generator.generate(task_info, task_type_hints=task_type_hints)
    print(template2)

    # 验证模板
    print("\n\n【验证】模板验证:")
    print("-" * 80)
    validator = TemplateValidator()
    validation_result = validator.validate(template2)
    print(f"有效: {validation_result['valid']}")
    if validation_result['errors']:
        print(f"错误: {validation_result['errors']}")
    if validation_result['warnings']:
        print(f"警告: {validation_result['warnings']}")

    print(f"\n模板长度: {validation_result['char_count']} 字符")
    print(f"Token数量: {validation_result['token_count']} tokens")
