# -*- coding: utf-8 -*-
"""
L3 → 平台算子映射模块

功能：
1. 将L3序列映射到具体平台算子（QGIS/GDAL/GRASS/SAGA/OTB）
2. I/O类型约束检查
3. 平台可用性过滤
4. 返回可执行工具链

用法：
    from l3_to_platform_mapper import L3ToPlatformMapper

    mapper = L3ToPlatformMapper(platform='QGIS')
    tool_chain = mapper.map_sequence(l3_tokens=[5, 12, 23, 45])
"""

import json
import csv
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any, Tuple
from enum import Enum


def _resolve_project_root() -> Path:
    """Resolve the project root (system_redesign/) regardless of file depth."""
    p = Path(__file__).resolve()
    for parent in [p.parent, p.parent.parent, p.parent.parent.parent, p.parent.parent.parent.parent]:
        if (parent / "outputs").is_dir():
            return parent
    return p.parent


class Platform(Enum):
    """支持的GIS平台"""
    QGIS = "QGIS"
    GDAL = "GDAL"
    GRASS = "GRASS"
    SAGA = "SAGA"
    OTB = "OTB"
    ALL = "ALL"  # 返回所有平台的算子


class DataType(Enum):
    """数据类型枚举（用于I/O约束）"""
    RASTER = "Raster"
    VECTOR = "Vector"
    TABLE = "Table"
    POINT = "Point"
    LINE = "Line"
    POLYGON = "Polygon"
    MULTIBAND = "Multiband Raster"
    UNKNOWN = "Unknown"


@dataclass
class PlatformOperator:
    """平台算子"""
    identifier: str           # 如 "gdal:aspect", "saga:buffer"
    name: str                 # 显示名称
    platform: str             # 平台/来源 (GDAL/GRASS/SAGA/OTB/native)
    l3_code: str              # 对应的L3编码
    l3_name: str              # L3名称
    confidence: float         # 映射置信度
    input_types: List[str] = field(default_factory=list)   # 输入类型
    output_types: List[str] = field(default_factory=list)  # 输出类型
    description: str = ""     # 描述

    def to_dict(self) -> Dict[str, Any]:
        return {
            'identifier': self.identifier,
            'name': self.name,
            'platform': self.platform,
            'l3_code': self.l3_code,
            'l3_name': self.l3_name,
            'confidence': self.confidence,
            'input_types': self.input_types,
            'output_types': self.output_types,
            'description': self.description
        }


@dataclass
class MappingResult:
    """单个L3的映射结果"""
    l3_code: str
    l3_name: str
    l3_description: str
    operators: List[PlatformOperator]
    is_unknown: bool = False  # 是否为UNKNOWN（无映射）

    def to_dict(self) -> Dict[str, Any]:
        return {
            'l3_code': self.l3_code,
            'l3_name': self.l3_name,
            'l3_description': self.l3_description,
            'operators': [op.to_dict() for op in self.operators],
            'is_unknown': self.is_unknown
        }


@dataclass
class ToolChain:
    """工具链（L3序列的完整映射）"""
    l3_sequence: List[str]    # L3编码序列
    steps: List[MappingResult]  # 每步的映射结果
    platform: str
    io_compatible: bool       # 是否I/O兼容
    unknown_count: int        # UNKNOWN数量
    confidence_score: float   # 平均置信度

    def to_dict(self) -> Dict[str, Any]:
        return {
            'l3_sequence': self.l3_sequence,
            'steps': [step.to_dict() for step in self.steps],
            'platform': self.platform,
            'io_compatible': self.io_compatible,
            'unknown_count': self.unknown_count,
            'confidence_score': self.confidence_score
        }


class L3ToPlatformMapper:
    """L3到平台算子映射器"""

    def __init__(
        self,
        platform: str = "QGIS",
        data_dir: Optional[Path] = None,
        min_confidence: float = 0.5
    ):
        """
        初始化映射器

        Args:
            platform: 目标平台 (QGIS/GDAL/GRASS/SAGA/OTB/ALL)
            data_dir: 数据目录（默认为项目目录）
            min_confidence: 最小置信度阈值
        """
        self.platform = Platform[platform.upper()] if isinstance(platform, str) else platform
        self.min_confidence = min_confidence

        # 设置数据目录
        if data_dir is None:
            self.data_dir = _resolve_project_root().parent
        else:
            self.data_dir = Path(data_dir)

        self.output_dir = _resolve_project_root() / "outputs"

        # 加载数据
        self._load_l3_hierarchy()
        self._load_platform_mappings()
        self._load_operator_details()

        print(f"[Mapper] 初始化完成")
        print(f"  平台: {self.platform.value}")
        print(f"  L3类别数: {len(self.l3_info)}")
        print(f"  已映射算子数: {len(self.l3_to_operators)}")

    def _load_l3_hierarchy(self):
        """加载L3分类层级"""
        hierarchy_path = self.data_dir / "classification_hierarchy.csv"
        self.l3_info = {}  # l3_code -> {name, description, input_type, output_type, ...}

        if hierarchy_path.exists():
            with open(hierarchy_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    l3_code = row.get('l3_code', '')
                    if l3_code:
                        self.l3_info[l3_code] = {
                            'name': row.get('l3_name', ''),
                            'description': row.get('l3_description', ''),
                            'input_type': row.get('input_type', ''),
                            'output_type': row.get('output_type', ''),
                            'l2_code': row.get('l2_code', ''),
                            'l2_name': row.get('l2_name', ''),
                            'l1_code': row.get('l1_code', ''),
                            'l1_name': row.get('l1_name', '')
                        }
            print(f"  L3层级: 加载 {len(self.l3_info)} 条")
        else:
            print(f"  [Warn] 未找到 classification_hierarchy.csv")

        # 加载ID映射（token ID -> L3 code）
        id_mappings_path = self.output_dir / "id_mappings.json"
        self.id_to_l3_code = {}
        self.l3_code_to_id = {}

        if id_mappings_path.exists():
            with open(id_mappings_path, 'r', encoding='utf-8') as f:
                id_mappings = json.load(f)
            l3_mapping = id_mappings.get('l3', {})
            self.l3_code_to_id = l3_mapping
            self.id_to_l3_code = {v: k for k, v in l3_mapping.items()}
            print(f"  ID映射: {len(self.id_to_l3_code)} 个L3 tokens")

    def _load_platform_mappings(self):
        """加载平台算子映射"""
        self.l3_to_operators = {}  # l3_code -> [PlatformOperator, ...]

        # 优先使用 L3_classification 目录下的高质量映射
        l3_classification_dir = self.data_dir / "L3_classification" / "QGIS"
        if l3_classification_dir.exists():
            self._parse_l3_classification_mappings(l3_classification_dir)
        else:
            # 回退到旧的映射文件
            qgis_mapping_path = self.data_dir / "L3" / "qgis_full_mapping_summary.csv"
            if qgis_mapping_path.exists():
                self._parse_qgis_mapping(qgis_mapping_path)

    def _parse_qgis_mapping(self, mapping_path: Path):
        """解析QGIS映射文件"""
        with open(mapping_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                identifier = row.get('identifier', '')
                l3_mappings_str = row.get('l3_mappings', '')
                status = row.get('status', '')
                overall_confidence = float(row.get('overall_confidence', 0))

                # 跳过OUT_OF_SCOPE或低置信度
                if status == 'OUT_OF_SCOPE' or overall_confidence < self.min_confidence:
                    continue

                # 解析平台来源
                platform_source = self._get_platform_source(identifier)

                # 解析L3映射（格式: L3_01_02_03:Name(0.85);L3_02_03_04:Name2(0.75)）
                if l3_mappings_str and l3_mappings_str != 'L3_UNKNOWN:Unknown(0.0)':
                    mappings = self._parse_l3_mappings_string(l3_mappings_str)
                    for l3_code, l3_name, confidence in mappings:
                        if confidence < self.min_confidence:
                            continue

                        operator = PlatformOperator(
                            identifier=identifier,
                            name=row.get('operator', ''),
                            platform=platform_source,
                            l3_code=l3_code,
                            l3_name=l3_name,
                            confidence=confidence,
                            description=""
                        )

                        if l3_code not in self.l3_to_operators:
                            self.l3_to_operators[l3_code] = []
                        self.l3_to_operators[l3_code].append(operator)

        print(f"  QGIS映射(CSV): {len(self.l3_to_operators)} 个L3有对应算子")

    def _parse_l3_classification_mappings(self, mapping_dir: Path):
        """解析L3_classification目录下的高质量映射文件"""
        # 首先建立 operator_name -> identifier 的映射
        name_to_identifier = {}
        operators_path = self.data_dir.parent / "operators-json" / "qgis_operators.json"
        if operators_path.exists():
            with open(operators_path, 'r', encoding='utf-8') as f:
                operators = json.load(f)
            for op in operators:
                name = op.get('name', '')
                identifier = op.get('identifier', '')
                source = op.get('source', '')
                if name and identifier:
                    name_to_identifier[name.lower()] = {
                        'identifier': identifier,
                        'source': source,
                        'description': op.get('description', '')
                    }

        # 加载所有 QGIS_to_L3_XX_Mapping_Full.json 文件
        total_mappings = 0
        for mapping_file in mapping_dir.glob("QGIS_to_L3_*_Mapping_Full.json"):
            with open(mapping_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            results = data.get('results', [])
            for item in results:
                operator_name = item.get('operator', '')
                status = item.get('status', '')
                mapped_l3s = item.get('mapped_l3s', [])

                if status != 'MAPPED' or not mapped_l3s:
                    continue

                # 查找 identifier
                op_info = name_to_identifier.get(operator_name.lower(), {})
                identifier = op_info.get('identifier', operator_name)
                source = op_info.get('source', 'QGIS')
                description = op_info.get('description', '')

                # 确定平台来源
                if identifier != operator_name:
                    platform_source = self._get_platform_source(identifier)
                else:
                    platform_source = source if source else 'QGIS'

                # 为每个L3创建映射（反向映射）
                for l3_info in mapped_l3s:
                    l3_code = l3_info.get('l3_code', '')
                    l3_name = l3_info.get('l3_name', '')
                    confidence = l3_info.get('confidence', 0.5)

                    if not l3_code or confidence < self.min_confidence:
                        continue

                    operator = PlatformOperator(
                        identifier=identifier,
                        name=operator_name,
                        platform=platform_source,
                        l3_code=l3_code,
                        l3_name=l3_name,
                        confidence=confidence,
                        description=description
                    )

                    if l3_code not in self.l3_to_operators:
                        self.l3_to_operators[l3_code] = []
                    self.l3_to_operators[l3_code].append(operator)
                    total_mappings += 1

        print(f"  L3_classification映射: {len(self.l3_to_operators)} 个L3有对应算子, 共 {total_mappings} 条映射")

    def _get_platform_source(self, identifier: str) -> str:
        """从identifier获取平台来源"""
        if identifier.startswith('gdal:'):
            return 'GDAL'
        elif identifier.startswith('grass') or identifier.startswith('grass7:'):
            return 'GRASS'
        elif identifier.startswith('saga:'):
            return 'SAGA'
        elif identifier.startswith('otb:'):
            return 'OTB'
        elif identifier.startswith('native:'):
            return 'QGIS'
        elif identifier.startswith('qgis:'):
            return 'QGIS'
        else:
            return 'QGIS'

    def _parse_l3_mappings_string(self, mapping_str: str) -> List[Tuple[str, str, float]]:
        """解析L3映射字符串

        格式: L3_01_02_03:Name(0.85);L3_02_03_04:Name2(0.75)
        返回: [(l3_code, l3_name, confidence), ...]
        """
        results = []
        if not mapping_str:
            return results

        parts = mapping_str.split(';')
        for part in parts:
            part = part.strip()
            if not part or part.startswith('L3_UNKNOWN'):
                continue

            # 解析 L3_xx_xx_xx:Name(confidence)
            try:
                if ':' in part and '(' in part:
                    code_name, conf_str = part.rsplit('(', 1)
                    confidence = float(conf_str.rstrip(')'))
                    l3_code, l3_name = code_name.split(':', 1)
                    results.append((l3_code.strip(), l3_name.strip(), confidence))
            except (ValueError, IndexError):
                continue

        return results

    def _load_operator_details(self):
        """加载算子详细信息（输入输出类型等）"""
        # 从qgis_operators.json加载详细信息
        operators_path = self.data_dir.parent / "operators-json" / "qgis_operators.json"
        self.operator_details = {}

        if operators_path.exists():
            with open(operators_path, 'r', encoding='utf-8') as f:
                operators = json.load(f)
            for op in operators:
                identifier = op.get('identifier', '')
                self.operator_details[identifier] = {
                    'inputs': op.get('inputs', []),
                    'outputs': op.get('outputs', []),
                    'description': op.get('description', '')
                }
            print(f"  算子详情: {len(self.operator_details)} 条")

    def get_l3_code(self, token_id: int) -> Optional[str]:
        """将token ID转换为L3 code"""
        return self.id_to_l3_code.get(token_id)

    def get_l3_info(self, l3_code: str) -> Dict[str, Any]:
        """获取L3详细信息"""
        return self.l3_info.get(l3_code, {
            'name': 'Unknown',
            'description': '',
            'input_type': '',
            'output_type': ''
        })

    def map_single_l3(
        self,
        l3_code: str,
        platform_filter: Optional[str] = None
    ) -> MappingResult:
        """
        映射单个L3到平台算子

        Args:
            l3_code: L3编码（如 "L3_01_02_03"）
            platform_filter: 平台过滤（GDAL/GRASS/SAGA/OTB/QGIS）

        Returns:
            MappingResult: 映射结果
        """
        l3_info = self.get_l3_info(l3_code)
        operators = self.l3_to_operators.get(l3_code, [])

        # 平台过滤
        if platform_filter and self.platform != Platform.ALL:
            operators = [op for op in operators if op.platform == platform_filter]
        elif self.platform != Platform.ALL:
            target_platform = self.platform.value
            operators = [op for op in operators if op.platform == target_platform]

        # 按置信度排序
        operators = sorted(operators, key=lambda x: x.confidence, reverse=True)

        # 补充算子详情
        for op in operators:
            if op.identifier in self.operator_details:
                details = self.operator_details[op.identifier]
                op.description = details.get('description', '')
                # 解析输入输出类型
                op.input_types = self._extract_io_types(details.get('inputs', []))
                op.output_types = self._extract_io_types(details.get('outputs', []))

        return MappingResult(
            l3_code=l3_code,
            l3_name=l3_info.get('name', 'Unknown'),
            l3_description=l3_info.get('description', ''),
            operators=operators,
            is_unknown=(len(operators) == 0)
        )

    def _extract_io_types(self, io_list: List[Dict]) -> List[str]:
        """从输入输出列表提取类型"""
        types = []
        for item in io_list:
            item_type = item.get('type', '')
            if item_type:
                types.append(item_type)
        return types

    def map_sequence(
        self,
        l3_tokens: List[int],
        check_io_compatibility: bool = True,
        top_k_operators: int = 3
    ) -> ToolChain:
        """
        映射L3 token序列到工具链

        Args:
            l3_tokens: L3 token ID列表
            check_io_compatibility: 是否检查I/O兼容性
            top_k_operators: 每个L3返回前K个算子

        Returns:
            ToolChain: 工具链结果
        """
        l3_codes = []
        steps = []
        unknown_count = 0
        total_confidence = 0.0

        for token_id in l3_tokens:
            l3_code = self.get_l3_code(token_id)
            if l3_code is None:
                l3_code = f"UNKNOWN_{token_id}"
                unknown_count += 1

            l3_codes.append(l3_code)
            mapping_result = self.map_single_l3(l3_code)

            # 限制算子数量
            if top_k_operators > 0:
                mapping_result.operators = mapping_result.operators[:top_k_operators]

            if mapping_result.is_unknown:
                unknown_count += 1
            elif mapping_result.operators:
                total_confidence += mapping_result.operators[0].confidence

            steps.append(mapping_result)

        # 计算平均置信度
        valid_steps = len(steps) - unknown_count
        avg_confidence = total_confidence / valid_steps if valid_steps > 0 else 0.0

        # I/O兼容性检查
        io_compatible = True
        if check_io_compatibility and len(steps) > 1:
            io_compatible = self._check_io_compatibility(steps)

        return ToolChain(
            l3_sequence=l3_codes,
            steps=steps,
            platform=self.platform.value,
            io_compatible=io_compatible,
            unknown_count=unknown_count,
            confidence_score=avg_confidence
        )

    def _check_io_compatibility(self, steps: List[MappingResult]) -> bool:
        """
        检查工具链的I/O兼容性

        简单规则：检查前一步的输出类型是否与下一步的输入类型兼容
        """
        for i in range(len(steps) - 1):
            current_step = steps[i]
            next_step = steps[i + 1]

            # 获取当前步的输出类型
            current_output = self._get_step_output_type(current_step)
            # 获取下一步的输入类型
            next_input = self._get_step_input_type(next_step)

            # 简单兼容性检查
            if current_output and next_input:
                if not self._types_compatible(current_output, next_input):
                    return False

        return True

    def _get_step_output_type(self, step: MappingResult) -> str:
        """获取步骤的输出类型"""
        # 优先从L3 hierarchy获取
        l3_info = self.get_l3_info(step.l3_code)
        output_type = l3_info.get('output_type', '')
        if output_type:
            return output_type

        # 从算子详情获取
        if step.operators and step.operators[0].output_types:
            return step.operators[0].output_types[0]

        return ''

    def _get_step_input_type(self, step: MappingResult) -> str:
        """获取步骤的输入类型"""
        l3_info = self.get_l3_info(step.l3_code)
        input_type = l3_info.get('input_type', '')
        if input_type:
            return input_type

        if step.operators and step.operators[0].input_types:
            return step.operators[0].input_types[0]

        return ''

    def _types_compatible(self, output_type: str, input_type: str) -> bool:
        """检查两个类型是否兼容"""
        # 简单的兼容性规则
        output_lower = output_type.lower()
        input_lower = input_type.lower()

        # 完全匹配
        if output_lower == input_lower:
            return True

        # Raster兼容性
        if 'raster' in output_lower and 'raster' in input_lower:
            return True

        # Vector兼容性
        if any(t in output_lower for t in ['vector', 'feature', 'polygon', 'point', 'line']):
            if any(t in input_lower for t in ['vector', 'feature', 'polygon', 'point', 'line']):
                return True

        # 通用Dataset兼容
        if 'dataset' in output_lower or 'dataset' in input_lower:
            return True

        # 如果无法判断，默认兼容
        if not output_lower or not input_lower:
            return True

        return False

    def print_tool_chain(self, tool_chain: ToolChain):
        """打印工具链"""
        print("\n" + "=" * 70)
        print(f"Tool Chain ({tool_chain.platform})")
        print("=" * 70)
        print(f"L3 Sequence: {' -> '.join(tool_chain.l3_sequence)}")
        print(f"I/O Compatible: {'Yes' if tool_chain.io_compatible else 'No'}")
        print(f"UNKNOWN Count: {tool_chain.unknown_count}")
        print(f"Avg Confidence: {tool_chain.confidence_score:.3f}")
        print("-" * 70)

        for i, step in enumerate(tool_chain.steps):
            print(f"\n[Step {i+1}] {step.l3_code}: {step.l3_name}")
            desc = step.l3_description
            if len(desc) > 80:
                print(f"  Desc: {desc[:80]}...")
            else:
                print(f"  Desc: {desc}")

            if step.is_unknown:
                print("  [!] No available mapping")
            else:
                print(f"  Available operators ({len(step.operators)}):")
                for j, op in enumerate(step.operators[:3]):  # 只显示前3个
                    print(f"    [{j+1}] {op.identifier} (conf={op.confidence:.2f})")
                    print(f"        Platform: {op.platform}")

        print("\n" + "=" * 70)


def main():
    """测试映射器"""
    print("=" * 70)
    print("L3 → 平台算子映射测试")
    print("=" * 70)

    # 创建映射器
    mapper = L3ToPlatformMapper(platform='QGIS')

    # 测试单个L3映射
    print("\n[测试1] 单个L3映射")
    result = mapper.map_single_l3("L3_02_01_01")  # Buffer
    print(f"L3: {result.l3_code} - {result.l3_name}")
    print(f"找到 {len(result.operators)} 个算子")
    for op in result.operators[:3]:
        print(f"  - {op.identifier} ({op.platform}, conf={op.confidence:.2f})")

    # 测试序列映射
    print("\n[测试2] L3序列映射")
    # 模拟一个L3 token序列（需要实际的token ID）
    # 先获取几个L3的ID
    test_l3_codes = ["L3_01_09_01", "L3_02_01_01", "L3_02_05_01"]  # 格式转换 → Buffer → Clip
    test_tokens = []
    for code in test_l3_codes:
        token_id = mapper.l3_code_to_id.get(code)
        if token_id is not None:
            test_tokens.append(token_id)
            print(f"  {code} -> token {token_id}")

    if test_tokens:
        tool_chain = mapper.map_sequence(test_tokens)
        mapper.print_tool_chain(tool_chain)

    print("\n映射测试完成！")


if __name__ == "__main__":
    main()
