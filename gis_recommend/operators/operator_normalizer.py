# system_redesign/operator_normalizer.py
"""
Enhanced GEE Operator Normalizer - 统一标准化GEE操作符

解决的问题：
1. 基础设施节点过滤（ee.ImageCollection, ee.Image等数据结构）
2. 链式调用拆分（ee.ImageCollection.filterDate.filterBounds → 多个独立操作）
3. 大小写统一（ee.ImageCollection.filterDate → ee.imagecollection.filterdate）
4. 标准词汇表匹配

使用示例：
    normalizer = OperatorNormalizer(standard_vocab)
    normalized_ops, is_infra, chain_parts = normalizer.normalize("ee.ImageCollection.filterDate.filterBounds")
    # normalized_ops: ['ee.imagecollection.filterdate', 'ee.imagecollection.filterbounds']
    # is_infra: False
    # chain_parts: ['ee.ImageCollection.filterDate', 'ee.ImageCollection.filterBounds']
"""
from typing import List, Tuple, Optional, Set
from pathlib import Path
import re


class OperatorNormalizer:
    """统一标准化GEE操作符"""

    # 基础设施关键词（数据结构，非GIS操作）
    INFRASTRUCTURE_KEYWORDS = [
        'ee.ImageCollection',
        'ee.Image',
        'ee.FeatureCollection',
        'ee.Feature',
        'ee.Geometry',
        'ee.Date',
        'ee.List',
        'ee.Dictionary',
        'ee.Number',
        'ee.String',
        'ee.Array',
        'ee.Filter',
        'ee.Reducer',
        'ee.Kernel',
        'ee.Projection',
        'ee.Terrain',
    ]

    # 特殊处理：这些虽然是数据结构，但有具体方法的保留
    ALLOWED_METHODS_FOR_INFRASTRUCTURE = {
        'ee.Filter': True,      # ee.Filter.eq, ee.Filter.calendarRange等是操作
        'ee.Reducer': True,     # ee.Reducer.mean, ee.Reducer.sum等是操作
        'ee.Geometry': True,    # ee.Geometry.Point, ee.Geometry.Polygon等是操作
        'ee.Kernel': True,      # ee.Kernel.circle等是操作
        'ee.Terrain': True,     # ee.Terrain.aspect等是操作
    }

    def __init__(self, standard_vocab: Set[str]):
        """
        初始化标准化器

        Args:
            standard_vocab: 标准GEE操作符词汇表（来自映射文件）
        """
        # 创建小写映射表：lowercase -> original_case
        self.standard_vocab_lower = {}
        for op in standard_vocab:
            self.standard_vocab_lower[op.lower()] = op

        # 保存原始词汇表用于检查
        self.standard_vocab = set(standard_vocab)

        # 统计信息
        self.stats = {
            'total': 0,
            'infrastructure_filtered': 0,
            'chained_split': 0,
            'case_normalized': 0,
            'standard_matched': 0,
            'unknown': 0,
        }

    def normalize(self, operator: str) -> Tuple[Optional[List[str]], bool, List[str]]:
        """
        标准化操作符

        Args:
            operator: 原始操作符名称（如 ee.ImageCollection.filterDate.filterBounds）

        Returns:
            Tuple of:
            - normalized_ops: 标准化后的操作符列表（None如果是基础设施）
            - is_infrastructure: 是否是基础设施节点
            - chain_parts: 拆分的链式调用部分（原始格式）

        Examples:
            >>> normalizer.normalize("ee.ImageCollection")
            (None, True, [])

            >>> normalizer.normalize("ee.ImageCollection.filterDate.filterBounds")
            (['ee.imagecollection.filterdate', 'ee.imagecollection.filterbounds'],
             False,
             ['ee.ImageCollection.filterDate', 'ee.ImageCollection.filterBounds'])

            >>> normalizer.normalize("ee.Image.select")
            (['ee.image.select'], False, ['ee.Image.select'])
        """
        self.stats['total'] += 1

        if not operator or not isinstance(operator, str):
            return None, False, []

        # 清理空格
        operator = operator.strip()

        # 1. 检查是否是基础设施节点
        if self._is_infrastructure(operator):
            self.stats['infrastructure_filtered'] += 1
            return None, True, []

        # 2. 拆分链式调用
        chain_parts = self._split_chain(operator)

        if len(chain_parts) > 1:
            self.stats['chained_split'] += 1

        # 3. 标准化每个部分（统一大小写 + 匹配词汇表）
        normalized_ops = []
        for part in chain_parts:
            normalized = self._normalize_single_operator(part)
            if normalized:
                normalized_ops.append(normalized)
                if normalized in self.standard_vocab:
                    self.stats['standard_matched'] += 1
                elif normalized.lower() in self.standard_vocab_lower:
                    self.stats['case_normalized'] += 1
                else:
                    self.stats['unknown'] += 1

        # 如果所有部分都无法标准化，返回None
        if not normalized_ops:
            return None, False, chain_parts

        return normalized_ops, False, chain_parts

    def _is_infrastructure(self, operator: str) -> bool:
        """
        判断是否是基础设施节点（数据结构构造器）

        规则：
        - 完全匹配基础设施关键词（纯构造器）→ True
        - 有具体方法的操作 → False（保留）

        Examples:
            ee.ImageCollection → True (纯数据结构)
            ee.Image → True (纯数据结构)
            ee.ImageCollection.filterDate → False (有方法，是GIS操作)
            ee.Image.select → False (有方法，是GIS操作)
            ee.Filter.eq → False (有具体方法，保留)
            ee.Reducer.mean → False (有具体方法，保留)
        """
        # 完全匹配基础设施关键词（没有方法）
        if operator in self.INFRASTRUCTURE_KEYWORDS:
            return True

        # 如果有方法（超过2个部分），都是具体操作，保留
        parts = operator.split('.')
        if len(parts) > 2:
            return False

        return False

    def _split_chain(self, operator: str) -> List[str]:
        """
        拆分链式调用

        规则：
        - ee.ClassName.method1.method2... → [ee.ClassName.method1, ee.ClassName.method2, ...]
        - ee.ClassName.method → [ee.ClassName.method]
        - ee.ClassName → [ee.ClassName]

        Examples:
            "ee.ImageCollection.filterDate.filterBounds"
            → ["ee.ImageCollection.filterDate", "ee.ImageCollection.filterBounds"]

            "ee.Classifier.smileRandomForest.train"
            → ["ee.Classifier.smileRandomForest", "ee.Classifier.train"]

            "ee.Image.select.clip.mask"
            → ["ee.Image.select", "ee.Image.clip", "ee.Image.mask"]
        """
        parts = operator.split('.')

        # 如果不是链式调用（<=2个部分），直接返回
        if len(parts) <= 2:
            return [operator]

        # 如果是 ee.ClassName.method 格式（标准格式），直接返回
        if len(parts) == 3:
            return [operator]

        # 链式调用：ee.ClassName.method1.method2...
        base = f"{parts[0]}.{parts[1]}"  # ee.ImageCollection
        methods = parts[2:]  # [filterDate, filterBounds]

        # 特殊处理：某些方法名可能是多个单词连接的
        # 例如 ee.Classifier.smileRandomForest.train
        # → [ee.Classifier.smileRandomForest, ee.Classifier.train]
        # 而不是 [ee.Classifier.smile, ee.Classifier.Random, ...]

        result = []
        for method in methods:
            full_op = f"{base}.{method}"
            result.append(full_op)

        return result

    def _normalize_single_operator(self, operator: str) -> Optional[str]:
        """
        标准化单个操作符（统一大小写 + 匹配词汇表）

        策略：
        1. 直接匹配标准词汇表（精确匹配）
        2. 小写匹配标准词汇表
        3. 无法匹配则返回小写版本

        Args:
            operator: 单个操作符（不含链式调用）

        Returns:
            标准化后的操作符，或None如果无法标准化
        """
        # 策略1: 精确匹配
        if operator in self.standard_vocab:
            return operator

        # 策略2: 小写匹配
        op_lower = operator.lower()
        if op_lower in self.standard_vocab_lower:
            # 返回标准词汇表中的原始格式（可能是小写）
            return self.standard_vocab_lower[op_lower]

        # 策略3: 无法匹配，返回小写版本
        # 这样至少保证格式统一，即使不在词汇表中
        return op_lower

    def get_statistics(self) -> dict:
        """获取标准化统计信息"""
        return self.stats.copy()

    def print_statistics(self):
        """打印标准化统计信息"""
        print("=== Operator Normalization Statistics ===")
        print(f"Total operators processed: {self.stats['total']}")
        print(f"  Infrastructure filtered: {self.stats['infrastructure_filtered']} ({100*self.stats['infrastructure_filtered']/max(self.stats['total'],1):.1f}%)")
        print(f"  Chained operators split: {self.stats['chained_split']} ({100*self.stats['chained_split']/max(self.stats['total'],1):.1f}%)")
        print(f"  Case normalized: {self.stats['case_normalized']} ({100*self.stats['case_normalized']/max(self.stats['total'],1):.1f}%)")
        print(f"  Standard matched: {self.stats['standard_matched']} ({100*self.stats['standard_matched']/max(self.stats['total'],1):.1f}%)")
        print(f"  Unknown operators: {self.stats['unknown']} ({100*self.stats['unknown']/max(self.stats['total'],1):.1f}%)")


def _resolve_project_root() -> Path:
    """Resolve the project root (system_redesign/) regardless of file depth."""
    p = Path(__file__).resolve()
    for parent in [p.parent, p.parent.parent, p.parent.parent.parent, p.parent.parent.parent.parent]:
        if (parent / "outputs").is_dir():
            return parent
    return p.parent


def load_standard_vocabulary() -> Set[str]:
    """
    从GEE映射文件加载标准词汇表

    Returns:
        Set of standard GEE operator names
    """
    import json
    import glob
    from pathlib import Path

    vocab = set()

    # GEE映射文件路径
    base_dir = _resolve_project_root().parent / "L3_classification" / "GEE"
    mapping_files = glob.glob(str(base_dir / "GEE_to_L3_*_Mapping_Full.json"))

    for file_path in mapping_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                for record in data.get('results', []):
                    operator = record.get('operator', '').strip()
                    if operator:
                        vocab.add(operator)
        except Exception as e:
            print(f"Warning: Failed to load {file_path}: {e}")

    return vocab


# 测试代码
if __name__ == "__main__":
    # 加载标准词汇表
    print("Loading standard vocabulary...")
    vocab = load_standard_vocabulary()
    print(f"Loaded {len(vocab)} standard operators")

    # 创建标准化器
    normalizer = OperatorNormalizer(vocab)

    # 测试用例
    test_cases = [
        "ee.ImageCollection",  # 基础设施
        "ee.Image",  # 基础设施
        "ee.ImageCollection.filterDate",  # 标准操作
        "ee.ImageCollection.filterDate.filterBounds",  # 链式调用
        "ee.Classifier.smileRandomForest.train",  # 链式调用
        "ee.Filter.calendarRange",  # Filter方法（保留）
        "ee.Reducer.mean",  # Reducer方法（保留）
        "ee.Image.select.clip.mask",  # 多重链式调用
    ]

    print("\n=== Test Cases ===")
    for test_op in test_cases:
        normalized, is_infra, chain = normalizer.normalize(test_op)
        print(f"\nInput: {test_op}")
        print(f"  Is Infrastructure: {is_infra}")
        if not is_infra:
            print(f"  Chain Parts: {chain}")
            print(f"  Normalized: {normalized}")

    # 打印统计信息
    print()
    normalizer.print_statistics()
