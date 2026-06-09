"""
qgis_candidate_generator.py

从L3序列生成多条QGIS算子链候选（支持typed unknown占位符）

核心设计：
1. 允许unknown存在，但必须是"带类型的占位符"
2. 区分UNMAPPABLE（平台不支持）vs UNMAPPED（映射表未覆盖）
3. 限制unknown占比和位置（关键步骤不允许unknown）
4. 为GraphRAG/LLM补全准备结构化信息
"""

import json
import os
from typing import List, Dict, Tuple, Optional, Set
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum
import heapq


def _resolve_project_root() -> Path:
    """Resolve the project root (system_redesign/) regardless of file depth."""
    p = Path(__file__).resolve()
    for parent in [p.parent, p.parent.parent, p.parent.parent.parent, p.parent.parent.parent.parent]:
        if (parent / "outputs_v2").is_dir() or (parent / "outputs").is_dir():
            return parent
    return p.parent


def _resolve_outputs_dir() -> Path:
    env_dir = os.environ.get("GIS_OUTPUTS_DIR")
    if env_dir:
        return Path(env_dir).expanduser().resolve()
    try:
        from gis_recommend.config.transformer_config import OUTPUT_DIR
        return Path(OUTPUT_DIR)
    except Exception:
        return _resolve_project_root() / "outputs_v2"


def _resolve_default_id_mappings_path() -> Path:
    env_path = os.environ.get("GIS_ID_MAPPINGS")
    if env_path:
        return Path(env_path).expanduser().resolve()
    try:
        from gis_recommend.config.transformer_config import ID_MAPPINGS_PATH
        return Path(ID_MAPPINGS_PATH)
    except Exception:
        return _resolve_outputs_dir() / "id_mappings_v2.json"


def _is_real_l3_code(l3_code: str) -> bool:
    return (
        isinstance(l3_code, str)
        and l3_code.startswith("L3_")
        and not l3_code.startswith("L3_UNKNOWN")
    )


_AUTHORITATIVE_MAPPING_FLAGS = {"manual_override", "manual_reviewed"}


def _is_authoritative_mapping(info: dict) -> bool:
    """Return True when v2 metadata marks the top-level primary_l3 as reviewed."""
    flag = str(info.get("mapping_confidence", "")).strip().lower()
    return flag in _AUTHORITATIVE_MAPPING_FLAGS or flag.startswith("manual_")


def _coerce_confidence(value, fallback: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def _first_candidate_confidence(raw_candidates, fallback: float) -> float:
    for candidate in raw_candidates:
        if isinstance(candidate, dict) and "confidence" in candidate:
            return _coerce_confidence(candidate.get("confidence"), fallback)
    return fallback


def _candidate_from_primary_metadata(info: dict, raw_candidates: list, manual_keep: bool) -> dict:
    fallback = _coerce_confidence(
        info.get("confidence", info.get("mapping_confidence")),
        1.0 if manual_keep else 0.0,
    )
    return {
        "l3_code": info.get("primary_l3") or info.get("l3_code"),
        "confidence": _first_candidate_confidence(raw_candidates, fallback),
        "l3_name": info.get("l3_name", ""),
        "_manual_keep": manual_keep,
    }


class UnknownType(Enum):
    """Unknown算子的类型分类"""
    INDEX_COMPUTE = "index_compute"  # 指数计算（NDVI/EVI等）
    CLOUD_MASK = "cloud_mask"  # 云掩膜
    TEMPORAL_AGGREGATE = "temporal_aggregate"  # 时序聚合
    VECTOR_OVERLAY = "vector_overlay"  # 矢量叠加
    EXPORT = "export"  # 数据导出
    REPROJECT = "reproject"  # 投影转换
    FILTER = "filter"  # 数据过滤
    CLASSIFICATION = "classification"  # 分类
    STATISTICS = "statistics"  # 统计分析
    MORPHOLOGY = "morphology"  # 形态学操作
    GENERIC = "generic"  # 通用（无法细分）


class UnknownReason(Enum):
    """Unknown的原因分类"""
    UNMAPPABLE = "unmappable"  # 平台客观不支持
    UNMAPPED = "unmapped"  # 映射表未覆盖（可补全）


@dataclass
class TypedUnknown:
    """带类型的Unknown占位符"""
    l3_code: str
    l3_name: str
    unknown_type: UnknownType
    reason: UnknownReason
    expected_input: Optional[str] = None  # 预期输入类型
    expected_output: Optional[str] = None  # 预期输出类型
    evidence: str = ""  # 证据链：为什么是unknown

    def to_placeholder(self) -> str:
        """生成占位符字符串"""
        return f"UNKNOWN[{self.unknown_type.value}]"

    def __repr__(self):
        return f"{self.to_placeholder()}({self.l3_code})"


@dataclass
class L3ToQGISMapping:
    """L3到QGIS的映射"""
    l3_code: str
    qgis_operator: str
    confidence: float
    l3_name: str = ""


@dataclass
class StepInfo:
    """候选链中每一步的信息"""
    position: int  # 位置索引
    l3_code: str
    operator: str  # QGIS算子名 或 UNKNOWN[type]
    is_unknown: bool
    mapping: Optional[L3ToQGISMapping] = None
    unknown_info: Optional[TypedUnknown] = None
    confidence: float = 0.0


@dataclass
class QGISCandidate:
    """QGIS算子链候选"""
    qgis_sequence: List[str]  # QGIS算子序列（含UNKNOWN占位符）
    l3_sequence: List[str]  # 对应的L3序列
    steps: List[StepInfo]  # 每步的详细信息
    score: float  # 候选链的总分数
    confidence: float  # 平均置信度
    unknown_count: int = 0  # unknown数量
    unknown_ratio: float = 0.0  # unknown占比
    has_critical_unknown: bool = False  # 关键步骤是否有unknown
    score_components: Dict[str, object] = field(default_factory=dict)  # QGIS score来源分解


class QGISCandidateGenerator:
    """
    QGIS候选链生成器（支持typed unknown）

    使用Beam Search从L3序列生成多条QGIS算子链候选
    允许unknown占位符，但进行严格控制
    """

    def __init__(
        self,
        mapping_dir: str = None,
        id_mappings_path: str = None,
        beam_width: int = 5,
        min_confidence: float = 0.3,
        max_unknown_ratio: float = 0.3,  # unknown占比上限
        max_unknown_count: int = 2,  # unknown数量上限
        critical_positions: Set[str] = None,  # 关键位置（不允许unknown）
        io_types_path: str = None,
        allow_legacy_io_types: bool = False,
        run_contract=None,
        verbose: bool = False,
    ):
        """
        初始化生成器

        参数:
            mapping_dir: L3→QGIS映射文件目录
            id_mappings_path: v2 id_mappings JSON path (default: config ID_MAPPINGS_PATH)
            beam_width: Beam Search的宽度
            min_confidence: 最小置信度阈值
            max_unknown_ratio: unknown占比上限（超过则降权）
            max_unknown_count: unknown数量上限
            critical_positions: 关键位置标识（如'first', 'last'）
            io_types_path: QGIS I/O metadata path (default: mainline run contract)
            allow_legacy_io_types: only allow legacy outputs/ metadata when explicit
            run_contract: optional MainlineRunContract carrying data authority
            verbose: 是否输出详细候选生成日志
        """
        self.beam_width = beam_width
        self.min_confidence = min_confidence
        self.max_unknown_ratio = max_unknown_ratio
        self.max_unknown_count = max_unknown_count
        self.critical_positions = critical_positions or {'first', 'last'}
        self.verbose = verbose
        self.run_contract = run_contract
        self.allow_legacy_io_types = allow_legacy_io_types

        # 设置映射数据源。默认走 outputs_v2/id_mappings_v2.json；显式
        # mapping_dir 仍保留旧 L3_classification/QGIS 兼容路径。
        self.id_mappings_path = None
        if id_mappings_path is not None:
            self.id_mappings_path = Path(id_mappings_path).expanduser().resolve()
            mapping_dir = None
        elif mapping_dir is None:
            default_id_mappings = _resolve_default_id_mappings_path()
            if default_id_mappings.exists():
                self.id_mappings_path = default_id_mappings

        if mapping_dir is None and self.id_mappings_path is None:
            base_dir = _resolve_project_root().parent
            mapping_dir = base_dir / "L3_classification" / "QGIS"
        elif mapping_dir is not None:
            mapping_dir = Path(mapping_dir)

        self.mapping_dir = mapping_dir

        # 加载映射关系
        self.l3_to_qgis_map = self._load_mappings()

        # 加载语义相似度分数
        self._load_semantic_scores()

        # 主线 I/O metadata 来源由 run contract 统一管理，避免 generator
        # 与 verifier/report 读取不同版本的数据资产。
        self._resolve_io_authority(io_types_path)

        # 加载 I/O 类型缓存
        self._load_io_types()

        # L3类型推断规则（用于生成typed unknown）
        self.l3_type_rules = self._init_l3_type_rules()

        self._log("[INFO] QGIS候选生成器已初始化")
        self._log(f"  - 映射源: {self.id_mappings_path or mapping_dir}")
        self._log(f"  - Beam宽度: {beam_width}")
        self._log(f"  - 最小置信度: {min_confidence}")
        self._log(f"  - Unknown占比上限: {max_unknown_ratio}")
        self._log(f"  - Unknown数量上限: {max_unknown_count}")
        self._log(f"  - 加载的L3代码数: {len(self.l3_to_qgis_map)}")
        self._log(f"  - 语义分数L3数: {len(self.semantic_scores)}")
        self._log(f"  - 发现的新映射L3数: {len(self.discovered_mappings)}")
        self._log(f"  - I/O类型算子数: {len(self.io_types)}")
        self._log(f"  - I/O metadata: {self.io_types_path} ({self.io_metadata_profile.get('fallback_status')})")

    def _log(self, message: str):
        if self.verbose:
            print(message)

    def _init_l3_type_rules(self) -> Dict[str, UnknownType]:
        """
        初始化L3代码到Unknown类型的推断规则

        基于L3代码的命名模式推断其功能类型
        """
        return {
            # 基于关键词的模糊匹配规则
            "index": UnknownType.INDEX_COMPUTE,
            "ndvi": UnknownType.INDEX_COMPUTE,
            "evi": UnknownType.INDEX_COMPUTE,
            "cloud": UnknownType.CLOUD_MASK,
            "mask": UnknownType.CLOUD_MASK,
            "temporal": UnknownType.TEMPORAL_AGGREGATE,
            "time": UnknownType.TEMPORAL_AGGREGATE,
            "aggregate": UnknownType.TEMPORAL_AGGREGATE,
            "overlay": UnknownType.VECTOR_OVERLAY,
            "vector": UnknownType.VECTOR_OVERLAY,
            "export": UnknownType.EXPORT,
            "output": UnknownType.EXPORT,
            "project": UnknownType.REPROJECT,
            "crs": UnknownType.REPROJECT,
            "filter": UnknownType.FILTER,
            "select": UnknownType.FILTER,
            "classif": UnknownType.CLASSIFICATION,
            "cluster": UnknownType.CLASSIFICATION,
            "statistic": UnknownType.STATISTICS,
            "stat": UnknownType.STATISTICS,
            "morpholog": UnknownType.MORPHOLOGY,
            "dilate": UnknownType.MORPHOLOGY,
            "erode": UnknownType.MORPHOLOGY,
        }

    def _infer_unknown_type(self, l3_code: str, l3_name: str) -> UnknownType:
        """
        根据L3代码和名称推断Unknown类型

        参数:
            l3_code: L3代码
            l3_name: L3名称

        返回:
            推断的Unknown类型
        """
        # 合并代码和名称进行匹配
        text = f"{l3_code} {l3_name}".lower()

        for keyword, unknown_type in self.l3_type_rules.items():
            if keyword in text:
                return unknown_type

        return UnknownType.GENERIC

    def _load_mappings(self) -> Dict[str, List[L3ToQGISMapping]]:
        """
        加载L3→QGIS映射关系

        返回:
            {l3_code: [L3ToQGISMapping, ...]}
        """
        if self.id_mappings_path is not None:
            return self._load_mappings_from_id_mappings(self.id_mappings_path)

        l3_to_qgis = {}

        # 查找所有QGIS映射文件
        mapping_files = list(self.mapping_dir.glob("QGIS_to_L3_*_Mapping_Full.json"))

        self._log(f"[INFO] 找到 {len(mapping_files)} 个映射文件")

        for mapping_file in mapping_files:
            try:
                with open(mapping_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # 遍历每个QGIS算子的映射
                for result in data.get('results', []):
                    qgis_op = result['operator']

                    # 遍历该QGIS算子映射到的L3代码
                    for l3_mapping in result.get('mapped_l3s', []):
                        l3_code = l3_mapping['l3_code']
                        confidence = l3_mapping['confidence']
                        l3_name = l3_mapping.get('l3_name', '')

                        # 过滤低置信度映射
                        if confidence < self.min_confidence:
                            continue

                        # 创建反向映射：L3 → QGIS
                        mapping = L3ToQGISMapping(
                            l3_code=l3_code,
                            qgis_operator=qgis_op,
                            confidence=confidence,
                            l3_name=l3_name
                        )

                        if l3_code not in l3_to_qgis:
                            l3_to_qgis[l3_code] = []

                        l3_to_qgis[l3_code].append(mapping)

            except Exception as e:
                self._log(f"[WARNING] 加载映射文件失败 {mapping_file}: {e}")

        # 对每个L3的QGIS映射按置信度排序
        for l3_code in l3_to_qgis:
            l3_to_qgis[l3_code].sort(key=lambda x: x.confidence, reverse=True)

        return l3_to_qgis

    def _load_mappings_from_id_mappings(self, id_mappings_path: Path) -> Dict[str, List[L3ToQGISMapping]]:
        """Load v2 QGIS mappings from id_mappings_v2.json mapping metadata."""
        l3_to_qgis: Dict[str, List[L3ToQGISMapping]] = {}

        try:
            with open(id_mappings_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            self._log(f"[WARNING] 加载id_mappings失败 {id_mappings_path}: {e}")
            return l3_to_qgis

        metadata = data.get("mapping_metadata", {}) if isinstance(data, dict) else {}
        qgis_to_l3 = metadata.get("qgis_to_l3") or data.get("qgis_to_l3", {})
        if not isinstance(qgis_to_l3, dict):
            self._log(f"[WARNING] id_mappings缺少qgis_to_l3: {id_mappings_path}")
            return l3_to_qgis

        for qgis_op, info in qgis_to_l3.items():
            candidates = []
            if isinstance(info, dict):
                raw_candidates = info.get("all_candidates") or []
                manual_keep = _is_authoritative_mapping(info)
                if manual_keep and _is_real_l3_code(info.get("primary_l3") or info.get("l3_code")):
                    candidates.append(_candidate_from_primary_metadata(info, raw_candidates, manual_keep))
                elif raw_candidates:
                    candidates.extend(raw_candidates)
                else:
                    candidates.append(_candidate_from_primary_metadata(info, raw_candidates, manual_keep))
            elif _is_real_l3_code(info):
                candidates.append({"l3_code": info, "confidence": 1.0, "l3_name": ""})

            for candidate in candidates:
                if not isinstance(candidate, dict):
                    continue
                l3_code = candidate.get("l3_code") or candidate.get("primary_l3")
                if not _is_real_l3_code(l3_code):
                    continue
                confidence = _coerce_confidence(candidate.get("confidence"), 0.0)
                if confidence < self.min_confidence and not candidate.get("_manual_keep"):
                    continue

                mapping = L3ToQGISMapping(
                    l3_code=l3_code,
                    qgis_operator=qgis_op,
                    confidence=confidence,
                    l3_name=candidate.get("l3_name", ""),
                )
                l3_to_qgis.setdefault(l3_code, []).append(mapping)

        for l3_code in l3_to_qgis:
            l3_to_qgis[l3_code].sort(key=lambda x: x.confidence, reverse=True)

        self._log(f"[INFO] 从id_mappings加载QGIS→L3映射: {len(qgis_to_l3)} 个QGIS算子")
        return l3_to_qgis

    def _load_semantic_scores(self):
        """加载预计算的语义相似度分数"""
        output_dir = _resolve_outputs_dir()
        path = output_dir / "l3_qgis_semantic_scores.json"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # {l3_code: [{qgis_name, semantic_score, original_confidence}, ...]}
            self.semantic_scores = data.get("scores", {})
            # {l3_code: [{qgis_name, semantic_score}, ...]}
            self.discovered_mappings = data.get("discovered_mappings", {})
            self._log(f"[INFO] 已加载语义分数 (模型: {data.get('model', '?')})")
        else:
            self.semantic_scores = {}
            self.discovered_mappings = {}
            self._log(f"[WARNING] 语义分数文件不存在: {path}")

    def _resolve_io_authority(self, io_types_path: Optional[str]):
        """Resolve QGIS I/O metadata from the same authority used by mainline."""
        if self.run_contract is None:
            try:
                from gis_recommend.evaluation.run_contract import build_mainline_run_contract
                self.run_contract = build_mainline_run_contract(
                    io_types_path=io_types_path,
                    allow_legacy_io_types=self.allow_legacy_io_types,
                )
            except Exception:
                self.run_contract = None

        if self.run_contract is not None:
            authority = self.run_contract.data_authority
            self.io_types_path = Path(authority.qgis_io_types_path)
            self.io_metadata_profile = dict(authority.io_metadata_profile)
            return

        if io_types_path is not None:
            self.io_types_path = Path(io_types_path).expanduser().resolve()
        else:
            self.io_types_path = _resolve_outputs_dir() / "qgis_operator_io_types.json"

        version_family = "legacy" if "outputs" in {p.lower() for p in self.io_types_path.parts} else "custom"
        exists = self.io_types_path.exists()
        self.io_metadata_profile = {
            "version_family": version_family,
            "path": str(self.io_types_path),
            "exists": exists,
            "fallback_status": "available" if exists else "missing",
        }

    def _load_io_types(self):
        """加载预计算的 QGIS 算子 I/O 数据类型"""
        path = self.io_types_path
        if self.io_metadata_profile.get("fallback_status") == "legacy_not_allowed":
            self.io_types = {}
            self._log(f"[INFO] Legacy I/O metadata not allowed for this run: {path}")
            return
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            self.io_types = data.get("operators", {})
            self._log(f"[INFO] I/O types loaded for {len(self.io_types)} operators")
        else:
            self.io_types = {}
            self._log("[INFO] No I/O types file, io_factor disabled")

    def _build_score_components(
        self,
        qgis_seq: List[str],
        steps: List[StepInfo],
        raw_score: float,
        final_score: float,
        unknown_ratio: float,
    ) -> Dict[str, object]:
        """Expose the major contributors folded into QGISCandidate.score."""
        non_unknown_steps = [s for s in steps if not s.is_unknown]
        mapping_scores = [float(s.confidence) for s in non_unknown_steps]
        transition_io_factors = [
            float(self._compute_io_factor(qgis_seq[i - 1], qgis_seq[i]))
            for i in range(1, len(qgis_seq))
        ]
        io_product = 1.0
        for factor in transition_io_factors:
            io_product *= factor
        mean_mapping = sum(mapping_scores) / len(mapping_scores) if mapping_scores else 0.0
        mean_io = (
            sum(transition_io_factors) / len(transition_io_factors)
            if transition_io_factors else 1.0
        )
        min_io = min(transition_io_factors) if transition_io_factors else 1.0
        return {
            "score_formula": "sum(step_mapping_score * transition_io_factor) with optional unknown penalty",
            "raw_score": raw_score,
            "final_score": final_score,
            "mapping_score_sum": sum(mapping_scores),
            "mean_mapping_score": mean_mapping,
            "transition_io_factors": transition_io_factors,
            "io_factor_product": io_product,
            "mean_io_factor": mean_io,
            "min_io_factor": min_io,
            "unknown_penalty_applied": unknown_ratio > self.max_unknown_ratio,
            "unknown_ratio": unknown_ratio,
            "io_metadata_profile": dict(self.io_metadata_profile),
        }

    def _compute_io_factor(self, prev_op: str, curr_op: str) -> float:
        """Compute I/O compatibility factor between consecutive operators.

        Returns:
            1.0 if compatible (output types overlap with input types)
            0.3 if incompatible (no overlap)
            0.7 if data insufficient (missing I/O info for either operator)
        """
        prev_info = self.io_types.get(prev_op, {})
        curr_info = self.io_types.get(curr_op, {})
        prev_out = prev_info.get("outputs", [])
        curr_in = curr_info.get("inputs", [])
        if not prev_out or not curr_in:
            return 0.7
        if set(prev_out) & set(curr_in):
            return 1.0
        return 0.3

    def _lookup_semantic_score(self, l3_code: str, qgis_name: str) -> float:
        """查找某个 L3→QGIS 映射的语义相似度，找不到返回 -1"""
        entries = self.semantic_scores.get(l3_code, [])
        for e in entries:
            if e["qgis_name"] == qgis_name:
                return e["semantic_score"]
        return -1.0

    def _get_mapping_score(self, l3_code: str, qgis_name: str, original_confidence: float) -> float:
        """
        综合评分：语义相似度为主，原始 confidence 为辅

        语义分数存在时：70% 语义 + 30% 原始 confidence
        L3 有语义记录但此 QGIS 不在其中：降权（0.3 × 原始 confidence）
        完全无语义数据时：fallback 到原始 confidence
        """
        sem_score = self._lookup_semantic_score(l3_code, qgis_name)
        if sem_score >= 0:
            return 0.7 * sem_score + 0.3 * original_confidence
        # L3 有语义记录但此 QGIS 不在其中 → 可能是 mapping 文件特有的低质量映射
        if l3_code in self.semantic_scores:
            return 0.3 * original_confidence
        return original_confidence

    def _append_unknown_beams(self, beams, new_beams, step_idx, l3_code, l3_name, is_critical):
        """为无映射的 L3 步骤追加 typed-unknown beam 分支"""
        typed_unknown = self._create_typed_unknown(
            l3_code=l3_code,
            l3_name=l3_name,
            reason=UnknownReason.UNMAPPED,
        )
        self._log(f"    生成占位符: {typed_unknown.to_placeholder()}")

        for qgis_seq, l3_seq, steps, score, unk_count in beams:
            new_unk_count = unk_count + 1
            if new_unk_count > self.max_unknown_count:
                self._log(f"    跳过：超过unknown数量上限({self.max_unknown_count})")
                continue
            if is_critical:
                self._log("    跳过：关键位置不允许unknown")
                continue

            step_info = StepInfo(
                position=step_idx,
                l3_code=l3_code,
                operator=typed_unknown.to_placeholder(),
                is_unknown=True,
                unknown_info=typed_unknown,
                confidence=0.0,
            )
            new_beams.append((
                qgis_seq + [typed_unknown.to_placeholder()],
                l3_seq + [l3_code],
                steps + [step_info],
                score - 0.5,  # 惩罚项
                new_unk_count,
            ))

    def _create_typed_unknown(
        self,
        l3_code: str,
        l3_name: str = "",
        reason: UnknownReason = UnknownReason.UNMAPPED
    ) -> TypedUnknown:
        """
        创建带类型的Unknown占位符

        参数:
            l3_code: L3代码
            l3_name: L3名称
            reason: Unknown原因

        返回:
            TypedUnknown对象
        """
        # 推断Unknown类型
        unknown_type = self._infer_unknown_type(l3_code, l3_name)

        # 生成证据链
        if reason == UnknownReason.UNMAPPED:
            evidence = f"映射表中未找到 {l3_code} 的QGIS映射（可补全）"
        else:
            evidence = f"{l3_code} 在QGIS平台不支持（平台限制）"

        return TypedUnknown(
            l3_code=l3_code,
            l3_name=l3_name,
            unknown_type=unknown_type,
            reason=reason,
            evidence=evidence
        )

    def generate_candidates(
        self,
        l3_sequence: List[str],
        l3_names: Dict[str, str] = None,
        top_k: int = None
    ) -> List[QGISCandidate]:
        """
        从L3序列生成多条QGIS算子链候选

        使用Beam Search策略，允许typed unknown占位符

        参数:
            l3_sequence: L3算子序列
            l3_names: L3代码到名称的映射（可选）
            top_k: 返回top-k个候选（默认使用beam_width）

        返回:
            候选QGIS算子链列表（按分数降序）
        """
        if top_k is None:
            top_k = self.beam_width

        if l3_names is None:
            l3_names = {}

        self._log(f"\n[生成候选] L3序列长度: {len(l3_sequence)}")
        self._log(f"  L3序列: {l3_sequence[:5]}..." if len(l3_sequence) > 5 else f"  L3序列: {l3_sequence}")

        # 初始化：一条空路径
        # (qgis_seq, l3_seq, steps, score, unknown_count)
        beams = [([], [], [], 0.0, 0)]

        # 逐步扩展每个L3算子
        for step_idx, l3_code in enumerate(l3_sequence):
            l3_name = l3_names.get(l3_code, "")
            self._log(f"\n  步骤 {step_idx+1}/{len(l3_sequence)}: {l3_code} ({l3_name})")

            # 判断是否是关键位置
            is_critical = (
                (step_idx == 0 and 'first' in self.critical_positions) or
                (step_idx == len(l3_sequence) - 1 and 'last' in self.critical_positions)
            )

            # 查询该L3的QGIS映射
            qgis_mappings = self.l3_to_qgis_map.get(l3_code, [])

            new_beams = []

            if qgis_mappings:
                # 有映射：扩展所有beam
                self._log(f"    找到 {len(qgis_mappings)} 个QGIS映射")

                for qgis_seq, l3_seq, steps, score, unk_count in beams:
                    # 尝试每个QGIS映射
                    for mapping in qgis_mappings:
                        # 使用语义相似度综合评分
                        combined_score = self._get_mapping_score(
                            l3_code, mapping.qgis_operator, mapping.confidence
                        )

                        # I/O 兼容性因子
                        if qgis_seq:
                            io_factor = self._compute_io_factor(qgis_seq[-1], mapping.qgis_operator)
                        else:
                            io_factor = 1.0

                        step_info = StepInfo(
                            position=step_idx,
                            l3_code=l3_code,
                            operator=mapping.qgis_operator,
                            is_unknown=False,
                            mapping=mapping,
                            confidence=combined_score
                        )

                        new_qgis_seq = qgis_seq + [mapping.qgis_operator]
                        new_l3_seq = l3_seq + [l3_code]
                        new_steps = steps + [step_info]
                        new_score = score + combined_score * io_factor

                        new_beams.append((new_qgis_seq, new_l3_seq, new_steps, new_score, unk_count))

            elif l3_code in self.discovered_mappings:
                # 无原始映射但有语义发现的候选
                disc_candidates = self.discovered_mappings[l3_code]
                # 过滤：语义分数 > 0.3 才算有效
                valid = [c for c in disc_candidates if c["semantic_score"] > 0.3]
                if valid:
                    self._log(f"    [DISCOVERED] 发现 {len(valid)} 个语义匹配候选")
                    for qgis_seq, l3_seq, steps, score, unk_count in beams:
                        for cand in valid:
                            sem = cand["semantic_score"]
                            # I/O 兼容性因子
                            if qgis_seq:
                                io_factor = self._compute_io_factor(qgis_seq[-1], cand["qgis_name"])
                            else:
                                io_factor = 1.0
                            step_info = StepInfo(
                                position=step_idx,
                                l3_code=l3_code,
                                operator=cand["qgis_name"],
                                is_unknown=False,
                                mapping=L3ToQGISMapping(
                                    l3_code=l3_code,
                                    qgis_operator=cand["qgis_name"],
                                    confidence=sem,
                                    l3_name=l3_name,
                                ),
                                confidence=sem,
                            )
                            new_qgis_seq = qgis_seq + [cand["qgis_name"]]
                            new_l3_seq = l3_seq + [l3_code]
                            new_steps = steps + [step_info]
                            new_score = score + sem * io_factor
                            new_beams.append((new_qgis_seq, new_l3_seq, new_steps, new_score, unk_count))
                else:
                    # 语义分数都太低，仍走 unknown 路径
                    self._log("    [WARNING] 语义候选分数均 < 0.3，标记为UNKNOWN")
                    self._append_unknown_beams(
                        beams, new_beams, step_idx, l3_code, l3_name, is_critical
                    )

            else:
                # 无映射也无语义发现：生成typed unknown
                self._log("    [WARNING] 未找到映射")
                self._append_unknown_beams(
                    beams, new_beams, step_idx, l3_code, l3_name, is_critical
                )

            if not new_beams:
                self._log("    [ERROR] 无法扩展，终止生成")
                break

            # 保留top-k条最优路径
            beams = heapq.nlargest(
                self.beam_width,
                new_beams,
                key=lambda x: x[3]  # 按score排序
            )

            self._log(f"    保留 {len(beams)} 条beam")

        # 转换为QGISCandidate对象
        candidates = []
        for qgis_seq, l3_seq, steps, score, unk_count in beams:
            if len(qgis_seq) == 0:
                continue

            # 计算统计信息
            total_steps = len(steps)
            unknown_count = sum(1 for s in steps if s.is_unknown)
            unknown_ratio = unknown_count / total_steps if total_steps > 0 else 0.0

            # 检查关键步骤是否有unknown
            has_critical_unknown = any(
                s.is_unknown and (
                    (s.position == 0 and 'first' in self.critical_positions) or
                    (s.position == total_steps - 1 and 'last' in self.critical_positions)
                )
                for s in steps
            )

            # 计算平均置信度（只计算非unknown步骤）
            non_unknown_steps = [s for s in steps if not s.is_unknown]
            avg_confidence = (
                sum(s.confidence for s in non_unknown_steps) / len(non_unknown_steps)
                if non_unknown_steps else 0.0
            )

            # 应用unknown惩罚
            final_score = score
            if unknown_ratio > self.max_unknown_ratio:
                final_score *= 0.5  # 降权

            candidate = QGISCandidate(
                qgis_sequence=qgis_seq,
                l3_sequence=l3_seq,
                steps=steps,
                score=final_score,
                confidence=avg_confidence,
                unknown_count=unknown_count,
                unknown_ratio=unknown_ratio,
                has_critical_unknown=has_critical_unknown,
                score_components=self._build_score_components(
                    qgis_seq=qgis_seq,
                    steps=steps,
                    raw_score=score,
                    final_score=final_score,
                    unknown_ratio=unknown_ratio,
                ),
            )
            candidates.append(candidate)

        # 按分数降序排序
        candidates.sort(key=lambda x: x.score, reverse=True)

        # 返回top-k
        result = candidates[:top_k]

        self._log(f"\n[完成] 生成 {len(result)} 条候选链")
        for i, cand in enumerate(result, 1):
            self._log(
                f"  候选{i}: {len(cand.qgis_sequence)}步, "
                f"分数={cand.score:.2f}, 置信度={cand.confidence:.3f}, "
                f"unknown={cand.unknown_count}({cand.unknown_ratio:.1%})"
            )

        return result

    def print_candidate_details(self, candidate: QGISCandidate):
        """Print candidate chain details"""
        print(f"\n{'='*80}")
        print(f"Candidate Chain Details")
        print(f"{'='*80}")
        print(f"  Total Score: {candidate.score:.2f}")
        print(f"  Avg Confidence: {candidate.confidence:.3f}")
        print(f"  Length: {len(candidate.qgis_sequence)} operators")
        print(f"  Unknown Count: {candidate.unknown_count} ({candidate.unknown_ratio:.1%})")
        print(f"  Critical Unknown: {'Yes' if candidate.has_critical_unknown else 'No'}")
        print(f"\n  Operator Sequence:")

        for step in candidate.steps:
            prefix = f"    {step.position+1}."
            if step.is_unknown:
                print(f"{prefix} {step.operator} [UNKNOWN]")
                print(f"       <- {step.l3_code}")
                print(f"       Type: {step.unknown_info.unknown_type.value}")
                print(f"       Reason: {step.unknown_info.reason.value}")
                print(f"       Evidence: {step.unknown_info.evidence}")
            else:
                print(f"{prefix} {step.operator}")
                print(f"       <- {step.l3_code}")
                print(f"       Confidence: {step.confidence:.3f}")

        print(f"{'='*80}\n")


# 使用示例
if __name__ == "__main__":
    # 初始化生成器
    generator = QGISCandidateGenerator(
        beam_width=5,
        min_confidence=0.3,
        max_unknown_ratio=0.3,
        max_unknown_count=2,
        verbose=True,
    )

    # 测试L3序列
    test_l3_sequence = [
        "L3_01_01_01",  # Load Data
        "L3_01_10_02",  # Define Projection
        "L3_01_03_04",  # Merge
        "L3_UNKNOWN_INDEX",  # 假设的未映射算子
        "L3_01_09_03",  # Raster-Vector Conversion
    ]

    test_l3_names = {
        "L3_01_01_01": "Load Data",
        "L3_01_10_02": "Define Projection",
        "L3_01_03_04": "Merge",
        "L3_UNKNOWN_INDEX": "NDVI Index Calculation",
        "L3_01_09_03": "Raster-Vector Conversion",
    }

    print("\n" + "=" * 80)
    print("测试：生成QGIS候选链（支持typed unknown）")
    print("=" * 80)

    # 生成候选
    candidates = generator.generate_candidates(
        test_l3_sequence,
        l3_names=test_l3_names,
        top_k=3
    )

    # 显示结果
    for i, candidate in enumerate(candidates, 1):
        print(f"\n【候选 {i}】")
        generator.print_candidate_details(candidate)
