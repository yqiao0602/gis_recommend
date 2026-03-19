"""
llm_normalizer.py
Phase 0: 归一化/纠错模块

功能：
1. 标准化用户输入中的术语（规则+词典）
2. 把歧义表达转换为标准化约束
3. 为后续LLM提取提供更清晰的输入

设计理念：
- 先保证系统不胡说八道（规则/约束）
- 再让模型更聪明（LLM理解）
"""

import re
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass


@dataclass
class NormalizedTerm:
    """标准化后的术语"""
    original: str  # 原始文本
    normalized: str  # 标准化后的文本
    constraint_type: str  # 约束类型（index, temporal, aggregation等）
    constraint_value: str  # 约束值
    confidence: float  # 置信度
    evidence: str = ""  # 匹配证据（原始文本片段）
    start_pos: int = -1  # 匹配起始位置
    end_pos: int = -1  # 匹配结束位置


class TermNormalizer:
    """术语标准化器"""

    def __init__(self):
        """初始化标准化器，加载词典"""
        # 指数/指标词典
        self.index_dict = {
            # NDVI相关
            r'ndvi|归一化植被指数|植被指数': ('index', 'NDVI'),
            r'evi|增强植被指数': ('index', 'EVI'),
            r'savi|土壤调节植被指数': ('index', 'SAVI'),
            r'ndwi|归一化水体指数|水体指数': ('index', 'NDWI'),
            r'ndbi|归一化建筑指数|建筑指数': ('index', 'NDBI'),
            r'ndsi|归一化雪指数|雪指数': ('index', 'NDSI'),

            # 其他指标
            r'lst|地表温度': ('index', 'LST'),
            r'lai|叶面积指数': ('index', 'LAI'),
            r'fpar|光合有效辐射': ('index', 'FPAR'),
        }

        # 时间相关词典
        self.temporal_dict = {
            r'时间序列|时序|时间变化|temporal': ('temporal', 'timeseries'),
            r'趋势|trend': ('temporal', 'trend'),
            r'季节|seasonal': ('temporal', 'seasonal'),
            r'年际|interannual': ('temporal', 'interannual'),
            r'多年|multi[_-]?year': ('temporal', 'multiyear'),
        }

        # 聚合方式词典
        self.aggregation_dict = {
            r'按月|月度|monthly': ('aggregation', 'monthly'),
            r'按季|季度|quarterly': ('aggregation', 'quarterly'),
            r'按年|年度|yearly|annual': ('aggregation', 'yearly'),
            r'按周|weekly': ('aggregation', 'weekly'),
            r'按日|daily': ('aggregation', 'daily'),
            r'按旬|dekadal': ('aggregation', 'dekadal'),
        }

        # 云处理词典
        self.cloud_dict = {
            r'去云|云掩膜|cloud\s*mask|去除云': ('cloud_mask', 'required'),
            r'云检测|cloud\s*detection': ('cloud_mask', 'detection'),
            r'云过滤|cloud\s*filter': ('cloud_mask', 'filter'),
        }

        # 空间操作词典
        self.spatial_dict = {
            r'裁剪|clip': ('spatial_op', 'clip'),
            r'重采样|resample': ('spatial_op', 'resample'),
            r'镶嵌|mosaic': ('spatial_op', 'mosaic'),
            r'投影|project|重投影|reproject': ('spatial_op', 'reproject'),
            r'缓冲|buffer': ('spatial_op', 'buffer'),
        }

        # 统计方法词典
        self.statistics_dict = {
            r'平均|均值|mean|average': ('statistics', 'mean'),
            r'最大|max|maximum': ('statistics', 'max'),
            r'最小|min|minimum': ('statistics', 'min'),
            r'中位数|median': ('statistics', 'median'),
            r'标准差|std|standard\s*deviation': ('statistics', 'std'),
            r'求和|sum': ('statistics', 'sum'),
        }

        # 输入数据类型词典
        self.input_type_dict = {
            r'栅格|raster|影像|image': ('input_type', 'raster'),
            r'矢量|vector|要素|feature': ('input_type', 'vector'),
            # 注意：移除"时间序列"，避免与temporal混淆
            # 只有明确说"输入是时间序列数据"时才应该匹配input_type
            r'点云|point\s*cloud': ('input_type', 'point_cloud'),
            r'表格|table': ('input_type', 'table'),
        }

        # 输出类型词典
        self.output_type_dict = {
            r'曲线|curve|折线图': ('output_type', 'curve'),
            r'栈|stack|时间栈': ('output_type', 'stack'),
            r'地图|map': ('output_type', 'map'),
            r'统计表|statistics': ('output_type', 'statistics'),
            r'报告|report': ('output_type', 'report'),
        }

        # ROI相关词典
        self.roi_dict = {
            r'研究区|roi|感兴趣区|area\s*of\s*interest': ('roi', 'required'),
            r'全球|global': ('roi', 'global'),
            r'区域|regional': ('roi', 'regional'),
        }

        # 传感器词典
        self.sensor_dict = {
            r'sentinel[_-]?2|哨兵2': ('sensor', 'Sentinel-2'),
            r'sentinel[_-]?1|哨兵1': ('sensor', 'Sentinel-1'),
            r'landsat[_-]?8': ('sensor', 'Landsat-8'),
            r'landsat[_-]?9': ('sensor', 'Landsat-9'),
            r'modis': ('sensor', 'MODIS'),
        }

        # 合并所有词典
        self.all_dicts = {
            'index': self.index_dict,
            'temporal': self.temporal_dict,
            'aggregation': self.aggregation_dict,
            'cloud': self.cloud_dict,
            'spatial': self.spatial_dict,
            'statistics': self.statistics_dict,
            'input_type': self.input_type_dict,
            'output_type': self.output_type_dict,
            'roi': self.roi_dict,
            'sensor': self.sensor_dict,
        }

    def normalize_text(self, text: str) -> Tuple[str, List[NormalizedTerm]]:
        """
        标准化文本（真正的归一化：替换术语为标准形式）

        参数:
            text: 原始用户输入

        返回:
            (normalized_text, extracted_terms)
            - normalized_text: 标准化后的文本（术语被替换为标准形式）
            - extracted_terms: 提取的标准化术语列表
        """
        extracted_terms = []
        all_matches = []  # 收集所有匹配项

        # 遍历所有词典进行匹配（使用原文 + IGNORECASE，避免重复）
        for dict_name, term_dict in self.all_dicts.items():
            for pattern, (constraint_type, constraint_value) in term_dict.items():
                matches = list(re.finditer(pattern, text, re.IGNORECASE))

                for match in matches:
                    original = match.group(0)
                    start_pos = match.start()
                    end_pos = match.end()

                    # 提取证据（匹配前后各10个字符的上下文）
                    context_start = max(0, start_pos - 10)
                    context_end = min(len(text), end_pos + 10)
                    evidence = text[context_start:context_end]

                    # 创建标准化术语
                    term = NormalizedTerm(
                        original=original,
                        normalized=constraint_value,
                        constraint_type=constraint_type,
                        constraint_value=constraint_value,
                        confidence=0.9,  # 规则匹配的置信度较高
                        evidence=evidence,
                        start_pos=start_pos,
                        end_pos=end_pos
                    )
                    extracted_terms.append(term)
                    all_matches.append((start_pos, end_pos, constraint_value))

        # 去重（保留置信度最高的）
        unique_terms = {}
        for term in extracted_terms:
            key = (term.constraint_type, term.constraint_value)
            if key not in unique_terms or term.confidence > unique_terms[key].confidence:
                unique_terms[key] = term

        extracted_terms = list(unique_terms.values())

        # 文本归一化：替换匹配的术语为标准形式
        # 按位置从后往前替换，避免位置偏移
        normalized_text = text
        sorted_matches = sorted(all_matches, key=lambda x: x[0], reverse=True)

        # 去除重叠的匹配（保留最长的）
        non_overlapping_matches = []
        last_end = len(text) + 1
        for start, end, value in sorted_matches:
            if end <= last_end:
                non_overlapping_matches.append((start, end, value))
                last_end = start

        # 执行替换
        for start, end, value in non_overlapping_matches:
            normalized_text = normalized_text[:start] + value + normalized_text[end:]

        return normalized_text, extracted_terms

    def to_structured_constraints(self, terms: List[NormalizedTerm]) -> Dict[str, List[str]]:
        """
        将标准化术语转换为结构化约束（多值）

        参数:
            terms: 标准化术语列表

        返回:
            结构化约束字典（多值）
            例如：{"temporal": ["timeseries", "trend"], "index": ["NDVI"]}
        """
        constraints = {}

        for term in terms:
            if term.constraint_type not in constraints:
                constraints[term.constraint_type] = []

            # 避免重复值
            if term.constraint_value not in constraints[term.constraint_type]:
                constraints[term.constraint_type].append(term.constraint_value)

        return constraints


class QueryNormalizer:
    """查询标准化器（完整流程）"""

    def __init__(self):
        """初始化查询标准化器"""
        self.term_normalizer = TermNormalizer()

    def normalize(self, user_query: str) -> Dict:
        """
        标准化用户查询

        参数:
            user_query: 用户原始输入

        返回:
            {
                "original_query": "原始查询",
                "normalized_query": "标准化后的查询",
                "extracted_terms": [...],
                "structured_constraints": {...},
                "confidence": 0.85,
                "coverage": 0.75  # P2: 规则覆盖率
            }
        """
        # 1. 文本标准化
        normalized_text, extracted_terms = self.term_normalizer.normalize_text(user_query)

        # 2. 转换为结构化约束
        structured_constraints = self.term_normalizer.to_structured_constraints(extracted_terms)

        # 3. 计算整体置信度（P2改进：结合规则覆盖率）
        if extracted_terms:
            avg_confidence = sum(t.confidence for t in extracted_terms) / len(extracted_terms)
        else:
            avg_confidence = 0.0

        # P2: 计算规则覆盖率（匹配的字符数 / 总字符数）
        matched_chars = sum(t.end_pos - t.start_pos for t in extracted_terms)
        total_chars = len(user_query)
        coverage = matched_chars / total_chars if total_chars > 0 else 0.0

        # P2: 结合覆盖率调整置信度
        # 如果覆盖率高，说明用户输入大部分都是标准术语，置信度应该更高
        adjusted_confidence = avg_confidence * 0.7 + coverage * 0.3

        # 4. 构建返回结果
        result = {
            "original_query": user_query,
            "normalized_query": normalized_text,
            "extracted_terms": [
                {
                    "original": t.original,
                    "normalized": t.normalized,
                    "constraint_type": t.constraint_type,
                    "constraint_value": t.constraint_value,
                    "confidence": t.confidence,
                    "evidence": t.evidence,  # P1: 添加evidence字段
                    "position": f"{t.start_pos}-{t.end_pos}"  # P1: 添加位置信息
                }
                for t in extracted_terms
            ],
            "structured_constraints": structured_constraints,
            "confidence": adjusted_confidence,  # P2: 使用调整后的置信度
            "coverage": coverage  # P2: 添加覆盖率信息
        }

        return result


# 使用示例
if __name__ == "__main__":
    normalizer = QueryNormalizer()

    # 测试用例
    test_queries = [
        "我想计算NDVI并进行时间序列分析，按月统计",
        "使用Sentinel-2数据计算植被指数，需要去云处理",
        "对研究区进行栅格裁剪和重采样",
        "计算地表温度的年际变化趋势",
    ]

    print("=" * 80)
    print("归一化测试")
    print("=" * 80)

    for query in test_queries:
        print(f"\n原始查询: {query}")
        result = normalizer.normalize(query)

        print(f"提取的术语:")
        for term in result['extracted_terms']:
            print(f"  - {term['original']} → {term['constraint_type']}={term['constraint_value']}")

        print(f"结构化约束: {result['structured_constraints']}")
        print(f"置信度: {result['confidence']:.2f}")
