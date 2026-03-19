"""
unknown_completer.py

阶段2：Unknown占位符补全模块

功能：
1. 从知识库检索候选QGIS算子
2. 基于约束条件过滤候选
3. 评分和选择最佳匹配
4. 生成完整的QGIS工具链

设计理念：
- 检索驱动：只从知识库检索，不发明新算子
- 强约束：必须满足平台限制和兼容性要求
- 可解释：记录选择理由和置信度
"""

import json
from typing import List, Dict, Optional, Tuple
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
import re


def _resolve_project_root() -> Path:
    """Resolve the project root (system_redesign/) regardless of file depth."""
    p = Path(__file__).resolve()
    for parent in [p.parent, p.parent.parent, p.parent.parent.parent, p.parent.parent.parent.parent]:
        if (parent / "outputs").is_dir():
            return parent
    return p.parent


@dataclass
class CandidateOperator:
    """候选QGIS算子"""
    operator_name: str
    l3_code: str
    confidence: float
    source: str  # 来源（mapping_file, similar_l3, etc.）
    metadata: Dict = field(default_factory=dict)

    def __repr__(self):
        return f"{self.operator_name} (conf={self.confidence:.3f}, src={self.source})"


@dataclass
class CompletionResult:
    """补全结果"""
    position: int
    l3_code: str
    unknown_type: str
    selected_operator: Optional[str]
    confidence: float
    candidates: List[CandidateOperator]
    selection_reason: str
    is_completed: bool


class UnknownCompleter:
    """
    Unknown占位符补全器

    使用检索驱动的方法补全unknown占位符
    """

    def __init__(
        self,
        mapping_dir: str = None,
        min_confidence: float = 0.3,
        top_k_candidates: int = 5
    ):
        """
        初始化补全器

        参数:
            mapping_dir: L3→QGIS映射文件目录
            min_confidence: 最小置信度阈值
            top_k_candidates: 检索候选数量
        """
        self.min_confidence = min_confidence
        self.top_k_candidates = top_k_candidates

        # 设置映射文件目录
        if mapping_dir is None:
            base_dir = _resolve_project_root().parent
            mapping_dir = base_dir / "L3_classification" / "QGIS"
        else:
            mapping_dir = Path(mapping_dir)

        self.mapping_dir = mapping_dir

        # 加载知识库
        self.qgis_to_l3_map = self._load_qgis_to_l3_mappings()
        self.l3_to_qgis_map = self._build_l3_to_qgis_index()

        # 构建L3相似度索引（基于L2分类）
        self.l3_similarity_index = self._build_l3_similarity_index()

        print(f"[INFO] Unknown Completer Initialized")
        print(f"  - Mapping Directory: {mapping_dir}")
        print(f"  - QGIS Operators: {len(self.qgis_to_l3_map)}")
        print(f"  - L3 Codes: {len(self.l3_to_qgis_map)}")
        print(f"  - Min Confidence: {min_confidence}")
        print(f"  - Top-K Candidates: {top_k_candidates}")

    def _load_qgis_to_l3_mappings(self) -> Dict:
        """
        加载QGIS→L3映射关系

        返回:
            {qgis_op: [{l3_code, confidence, l3_name}, ...]}
        """
        qgis_to_l3 = {}

        mapping_files = list(self.mapping_dir.glob("QGIS_to_L3_*_Mapping_Full.json"))

        for mapping_file in mapping_files:
            try:
                with open(mapping_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                for result in data.get('results', []):
                    qgis_op = result['operator']
                    mapped_l3s = result.get('mapped_l3s', [])

                    if qgis_op not in qgis_to_l3:
                        qgis_to_l3[qgis_op] = []

                    for l3_mapping in mapped_l3s:
                        qgis_to_l3[qgis_op].append({
                            'l3_code': l3_mapping['l3_code'],
                            'confidence': l3_mapping['confidence'],
                            'l3_name': l3_mapping.get('l3_name', '')
                        })

            except Exception as e:
                print(f"[WARNING] Failed to load {mapping_file}: {e}")

        return qgis_to_l3

    def _build_l3_to_qgis_index(self) -> Dict:
        """
        构建L3→QGIS反向索引

        返回:
            {l3_code: [{qgis_op, confidence}, ...]}
        """
        l3_to_qgis = {}

        for qgis_op, l3_mappings in self.qgis_to_l3_map.items():
            for mapping in l3_mappings:
                l3_code = mapping['l3_code']
                confidence = mapping['confidence']

                if confidence < self.min_confidence:
                    continue

                if l3_code not in l3_to_qgis:
                    l3_to_qgis[l3_code] = []

                l3_to_qgis[l3_code].append({
                    'qgis_op': qgis_op,
                    'confidence': confidence
                })

        # 按置信度排序
        for l3_code in l3_to_qgis:
            l3_to_qgis[l3_code].sort(key=lambda x: x['confidence'], reverse=True)

        return l3_to_qgis

    def _build_l3_similarity_index(self) -> Dict:
        """
        构建L3相似度索引（基于L2分类）

        返回:
            {l3_code: [similar_l3_codes]}
        """
        # 加载L3层次结构
        hierarchy_file = _resolve_project_root().parent / "classification_hierarchy.csv"

        if not hierarchy_file.exists():
            print(f"[WARNING] Hierarchy file not found: {hierarchy_file}")
            return {}

        import pandas as pd
        df = pd.read_csv(hierarchy_file)

        # 按L2分组
        l2_groups = df.groupby('l2_code')['l3_code'].apply(list).to_dict()

        # 构建相似度索引
        similarity_index = {}
        for l2_code, l3_codes in l2_groups.items():
            for l3_code in l3_codes:
                # 同一L2下的其他L3代码视为相似
                similarity_index[l3_code] = [
                    code for code in l3_codes if code != l3_code
                ]

        return similarity_index

    def retrieve_candidates(
        self,
        l3_code: str,
        unknown_type: str,
        context: Dict,
        constraints: Dict
    ) -> List[CandidateOperator]:
        """
        检索候选QGIS算子

        策略：
        1. 直接查询：查找该L3的QGIS映射
        2. 相似L3：查找相似L3的QGIS映射
        3. 类型匹配：基于unknown_type查找相关算子

        参数:
            l3_code: L3代码
            unknown_type: Unknown类型
            context: 上下文信息
            constraints: 约束条件

        返回:
            候选算子列表
        """
        candidates = []

        # 策略1：直接查询（虽然unknown通常没有直接映射，但可能有低置信度映射）
        if l3_code in self.l3_to_qgis_map:
            for mapping in self.l3_to_qgis_map[l3_code][:self.top_k_candidates]:
                candidates.append(CandidateOperator(
                    operator_name=mapping['qgis_op'],
                    l3_code=l3_code,
                    confidence=mapping['confidence'],
                    source='direct_mapping'
                ))

        # 策略2：相似L3查询
        similar_l3s = self.l3_similarity_index.get(l3_code, [])
        for similar_l3 in similar_l3s[:3]:  # 只取前3个相似L3
            if similar_l3 in self.l3_to_qgis_map:
                for mapping in self.l3_to_qgis_map[similar_l3][:2]:  # 每个相似L3取2个
                    # 降低置信度（因为是相似而非直接映射）
                    candidates.append(CandidateOperator(
                        operator_name=mapping['qgis_op'],
                        l3_code=similar_l3,
                        confidence=mapping['confidence'] * 0.7,  # 折扣因子
                        source=f'similar_l3:{similar_l3}'
                    ))

        # 策略3：基于unknown_type的关键词匹配
        type_keywords = self._get_type_keywords(unknown_type)
        for qgis_op in self.qgis_to_l3_map.keys():
            if any(keyword in qgis_op.lower() for keyword in type_keywords):
                # 计算基于关键词匹配的置信度
                match_score = sum(
                    1 for keyword in type_keywords
                    if keyword in qgis_op.lower()
                ) / len(type_keywords)

                candidates.append(CandidateOperator(
                    operator_name=qgis_op,
                    l3_code=l3_code,
                    confidence=match_score * 0.6,  # 关键词匹配置信度较低
                    source='keyword_match'
                ))

        # 去重（同一算子可能来自多个策略）
        unique_candidates = {}
        for cand in candidates:
            if cand.operator_name not in unique_candidates:
                unique_candidates[cand.operator_name] = cand
            else:
                # 保留置信度更高的
                if cand.confidence > unique_candidates[cand.operator_name].confidence:
                    unique_candidates[cand.operator_name] = cand

        # 按置信度排序
        sorted_candidates = sorted(
            unique_candidates.values(),
            key=lambda x: x.confidence,
            reverse=True
        )

        # 返回top-k
        return sorted_candidates[:self.top_k_candidates]

    def _get_type_keywords(self, unknown_type: str) -> List[str]:
        """
        获取unknown类型对应的关键词

        参数:
            unknown_type: Unknown类型

        返回:
            关键词列表
        """
        type_keyword_map = {
            'index_compute': ['calculator', 'raster calculator', 'band', 'math', 'expression'],
            'cloud_mask': ['mask', 'conditional', 'filter', 'select', 'clip'],
            'temporal_aggregate': ['aggregate', 'statistics', 'mean', 'sum', 'temporal'],
            'vector_overlay': ['overlay', 'intersect', 'union', 'clip', 'difference'],
            'export': ['export', 'save', 'write', 'output'],
            'reproject': ['reproject', 'transform', 'warp', 'crs', 'projection'],
            'filter': ['filter', 'select', 'extract', 'query'],
            'classification': ['classify', 'cluster', 'categorize', 'supervised'],
            'statistics': ['statistics', 'zonal', 'summary', 'histogram'],
            'morphology': ['morphology', 'dilate', 'erode', 'open', 'close'],
            'generic': []
        }

        return type_keyword_map.get(unknown_type, [])

    def filter_by_constraints(
        self,
        candidates: List[CandidateOperator],
        constraints: Dict
    ) -> List[CandidateOperator]:
        """
        根据约束条件过滤候选

        参数:
            candidates: 候选列表
            constraints: 约束条件

        返回:
            过滤后的候选列表
        """
        filtered = []

        for cand in candidates:
            # 检查平台约束
            if constraints.get('platform') == 'QGIS':
                # QGIS算子默认满足
                pass

            # 检查插件约束
            if not constraints.get('allow_plugin', False):
                # 简单检查：如果算子名包含特定插件标识，则跳过
                if any(plugin in cand.operator_name.lower() for plugin in ['saga', 'grass', 'orfeo']):
                    continue

            # 检查自定义脚本约束
            if not constraints.get('allow_custom_script', False):
                if 'script' in cand.operator_name.lower():
                    continue

            # 检查输出类型约束
            expected_output = constraints.get('output_type')
            if expected_output:
                # 简单启发式：基于算子名推断输出类型
                if expected_output == 'raster':
                    if 'vector' in cand.operator_name.lower() and 'raster' not in cand.operator_name.lower():
                        # 降低置信度而非完全过滤
                        cand.confidence *= 0.5
                elif expected_output == 'vector':
                    if 'raster' in cand.operator_name.lower() and 'vector' not in cand.operator_name.lower():
                        cand.confidence *= 0.5

            filtered.append(cand)

        # 重新排序
        filtered.sort(key=lambda x: x.confidence, reverse=True)

        return filtered

    def select_best_candidate(
        self,
        candidates: List[CandidateOperator],
        context: Dict,
        constraints: Dict
    ) -> Tuple[Optional[str], float, str]:
        """
        选择最佳候选

        参数:
            candidates: 候选列表
            context: 上下文信息
            constraints: 约束条件

        返回:
            (selected_operator, confidence, reason)
        """
        if not candidates:
            return None, 0.0, "No candidates found"

        # 简单策略：选择置信度最高的
        best_candidate = candidates[0]

        # 检查置信度是否足够高
        if best_candidate.confidence < self.min_confidence:
            return None, best_candidate.confidence, f"Best candidate confidence ({best_candidate.confidence:.3f}) below threshold ({self.min_confidence})"

        # 生成选择理由
        reason = f"Selected '{best_candidate.operator_name}' with confidence {best_candidate.confidence:.3f} from {best_candidate.source}"

        if len(candidates) > 1:
            second_best = candidates[1]
            confidence_gap = best_candidate.confidence - second_best.confidence
            reason += f" (gap to 2nd: {confidence_gap:.3f})"

        return best_candidate.operator_name, best_candidate.confidence, reason

    def complete_unknown(
        self,
        completion_task: Dict
    ) -> CompletionResult:
        """
        补全单个unknown占位符

        参数:
            completion_task: 补全任务（来自Stage A的completion_context）

        返回:
            CompletionResult对象
        """
        position = completion_task['position']
        l3_code = completion_task['l3_code']
        unknown_type = completion_task['unknown_type']
        context = completion_task['context']
        constraints = completion_task['constraints']

        print(f"\n[Completion] Position {position}: {l3_code} ({unknown_type})")

        # 1. Retrieve candidates
        candidates = self.retrieve_candidates(
            l3_code=l3_code,
            unknown_type=unknown_type,
            context=context,
            constraints=constraints
        )

        print(f"  Retrieved {len(candidates)} candidates")
        for i, cand in enumerate(candidates[:3], 1):
            print(f"    {i}. {cand}")

        # 2. Filter by constraints
        filtered_candidates = self.filter_by_constraints(candidates, constraints)

        if len(filtered_candidates) < len(candidates):
            print(f"  After filtering: {len(filtered_candidates)} candidates")

        # 3. 选择最佳候选
        selected_op, confidence, reason = self.select_best_candidate(
            filtered_candidates,
            context,
            constraints
        )

        if selected_op:
            print(f"  [OK] Selected: {selected_op} (confidence: {confidence:.3f})")
            print(f"  Reason: {reason}")
            is_completed = True
        else:
            print(f"  [FAIL] Cannot complete: {reason}")
            is_completed = False

        return CompletionResult(
            position=position,
            l3_code=l3_code,
            unknown_type=unknown_type,
            selected_operator=selected_op,
            confidence=confidence,
            candidates=filtered_candidates,
            selection_reason=reason,
            is_completed=is_completed
        )


# 使用示例
if __name__ == "__main__":
    # 初始化补全器
    completer = UnknownCompleter(
        min_confidence=0.3,
        top_k_candidates=5
    )

    # 测试补全任务
    test_task = {
        "position": 2,
        "l3_code": "L3_CLOUD_MASK",
        "unknown_type": "cloud_mask",
        "unknown_reason": "unmapped",
        "retrieval_query": "QGIS operator for cloud masking and filtering",
        "context": {
            "prev_operator": "Assign projection",
            "next_operator": "Merge vector layers",
            "prev_l3": "L3_01_10_02",
            "next_l3": "L3_01_03_04"
        },
        "constraints": {
            "platform": "QGIS",
            "must_be_compatible": True,
            "allow_plugin": False,
            "allow_custom_script": False,
            "position_type": "middle",
            "requires_conditional_operation": True,
            "output_type": "raster",
            "completion_strategy": "retrieve_from_knowledge_base"
        }
    }

    print("\n" + "="*80)
    print("Test: Unknown Placeholder Completion")
    print("="*80)

    result = completer.complete_unknown(test_task)

    print("\n" + "="*80)
    print("Completion Result")
    print("="*80)
    print(f"Position: {result.position}")
    print(f"L3 Code: {result.l3_code}")
    print(f"Unknown Type: {result.unknown_type}")
    print(f"Is Completed: {result.is_completed}")
    if result.is_completed:
        print(f"Selected Operator: {result.selected_operator}")
        print(f"Confidence: {result.confidence:.3f}")
    print(f"Reason: {result.selection_reason}")
    print(f"\nCandidate List (top-3):")
    for i, cand in enumerate(result.candidates[:3], 1):
        print(f"  {i}. {cand}")
