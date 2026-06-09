# -*- coding: utf-8 -*-
"""
Reranker / Verifier V2 — 结构化候选重排序与验证

V2 改进（相对 V1）:
  - VerifiedFeatures 补齐独立维度：io_compatibility, validation_confidence, is_valid
  - verify() 轻量版支持本地 I/O 类型检查（复用 qgis_candidate_generator 的 io_types）
  - _compute_score() 不使用 validation/compatibility 分类控制候选选择
  - 不再混淆 known_operator_ratio 和 validation_confidence

职责分离：
  - CandidateVerifier: 对候选链提取结构化特征，不负责排序
  - StructuredReranker: 基于特征做加权排序，选出最优候选

用法:
    from gis_recommend.reranking import CandidateVerifier, StructuredReranker
    verifier = CandidateVerifier()
    reranker = StructuredReranker(verifier)
    result = reranker.rerank(qgis_candidates, l3_candidates, context)
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional

import numpy as np

from gis_recommend.evaluation.run_contract import build_mainline_run_contract


def _resolve_project_root() -> Path:
    """Find the project root (directory containing 'outputs/')."""
    p = Path(__file__).resolve()
    for parent in [p.parent, p.parent.parent, p.parent.parent.parent,
                   p.parent.parent.parent.parent]:
        if (parent / "outputs").is_dir():
            return parent
    return p.parent


@dataclass
class VerifiedFeatures:
    """结构化特征，由 Verifier 提取。"""
    # L3 来源特征
    l3_score: float = 0.0           # L3 候选的 final_score
    l3_length: int = 0              # L3 序列长度
    l3_length_deviation: float = 0.0  # 与期望长度的偏差 (|actual - expected| / expected)
    set_overlap: float = 0.0        # 与 set predictor 预测集合的 Jaccard 系数

    # QGIS 候选特征（来自候选生成器上游信号）
    qgis_score: float = 0.0        # QGIS 候选的 score（含语义映射 + I/O 因子）
    qgis_confidence: float = 0.0   # QGIS 候选的 confidence（per-step 平均）
    unknown_count: int = 0         # unknown 算子数量
    unknown_ratio: float = 0.0     # unknown 占比
    has_critical_unknown: bool = False  # 关键位置是否有 unknown
    chain_length: int = 0          # QGIS 链长度

    # Verifier 结构特征（独立维度，不互相覆盖）
    known_operator_ratio: float = 0.0    # 非 UNKNOWN 算子占总步骤的比例
    io_compatibility_ratio: float = 0.5  # 相邻算子对的 I/O 兼容比例 (0-1)
    validation_confidence: float = 0.0   # 链校验整体置信度 (0-1)
    is_valid: bool = True                # 链是否通过校验
    issue_count: int = 0                 # 结构问题数

    # V3 语义特征（两阶段 reranker 使用）
    query_chain_sim: float = 0.0        # task_description → L3 chain 的语义相似度
    set_recall: float = 0.0             # set predictor 覆盖率: |pred ∩ gen| / |pred|
    set_precision: float = 0.0          # set predictor 精确率: |pred ∩ gen| / |gen|
    set_excess_ratio: float = 0.0       # 多余 token 比例: |gen - pred| / |gen|
    l3_rank: int = 0                    # 该 L3 候选在原始 beam 中的排名 (0-based)
    l3_score_margin: float = 0.0        # top1_score - 该候选 final_score
    length_ratio: float = 1.0           # actual_length / expected_length

    # 综合得分（由 Reranker 计算）
    final_score: float = 0.0

    def to_dict(self) -> dict:
        return {
            'l3_score': round(self.l3_score, 4),
            'l3_length': self.l3_length,
            'l3_length_deviation': round(self.l3_length_deviation, 4),
            'set_overlap': round(self.set_overlap, 4),
            'qgis_score': round(self.qgis_score, 4),
            'qgis_confidence': round(self.qgis_confidence, 4),
            'unknown_count': self.unknown_count,
            'unknown_ratio': round(self.unknown_ratio, 4),
            'has_critical_unknown': self.has_critical_unknown,
            'chain_length': self.chain_length,
            'known_operator_ratio': round(self.known_operator_ratio, 4),
            'io_compatibility_ratio': round(self.io_compatibility_ratio, 4),
            'validation_confidence': round(self.validation_confidence, 4),
            'is_valid': self.is_valid,
            'issue_count': self.issue_count,
            'query_chain_sim': round(self.query_chain_sim, 4),
            'set_recall': round(self.set_recall, 4),
            'set_precision': round(self.set_precision, 4),
            'set_excess_ratio': round(self.set_excess_ratio, 4),
            'l3_rank': self.l3_rank,
            'l3_score_margin': round(self.l3_score_margin, 4),
            'length_ratio': round(self.length_ratio, 4),
            'final_score': round(self.final_score, 4),
        }


@dataclass
class RerankerResult:
    """Reranker 输出结果。"""
    best_candidate: Any             # 最优 QGISCandidate
    best_features: VerifiedFeatures  # 最优候选的特征
    best_l3_candidate: Any = None   # 与最优 QGIS 候选对应的 L3Candidate
    all_ranked: List[tuple] = field(default_factory=list)  # [(QGISCandidate, L3Candidate, VerifiedFeatures), ...]
    oracle_best: Optional[Any] = None


class CandidateVerifier:
    """对 QGIS 候选链提取结构化特征。

    轻量版：不依赖 Neo4j，用本地 io_types JSON 做 I/O 兼容性检查。
    增强版（可选）：接入 GraphRAG 做更精确的存在性和兼容性检查。
    """

    def __init__(
        self,
        graphrag_retriever=None,
        chain_validator=None,
        io_types_path: Optional[str | Path] = None,
        allow_legacy_io_types: bool = False,
        run_contract=None,
    ):
        self.retriever = graphrag_retriever
        self.validator = chain_validator
        self.run_contract = run_contract or build_mainline_run_contract(
            io_types_path=io_types_path,
            allow_legacy_io_types=allow_legacy_io_types,
        )
        self.io_types_path = self.run_contract.data_authority.qgis_io_types_path
        self.io_metadata_profile = dict(self.run_contract.data_authority.io_metadata_profile)
        self.io_types = self._load_io_types(self.io_types_path)

    @staticmethod
    def _load_io_types(path: Path) -> dict:
        """加载预计算的 QGIS 算子 I/O 类型（轻量 I/O 兼容性检查）。"""
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            return data.get("operators", {})
        return {}

    @staticmethod
    def _estimate_lightweight_issue_count(chain: List[str]) -> int:
        """Estimate structural issues without Neo4j/GraphRAG."""
        if not chain:
            return 1
        issues = 0
        # 连续重复算子
        for i in range(1, len(chain)):
            if chain[i] == chain[i - 1] and not chain[i].startswith("UNKNOWN"):
                issues += 1
        # 首尾 UNKNOWN
        if chain[0].startswith("UNKNOWN"):
            issues += 1
        if len(chain) > 1 and chain[-1].startswith("UNKNOWN"):
            issues += 1
        # 全部 UNKNOWN
        if all(op.startswith("UNKNOWN") for op in chain):
            issues += 1
        return issues

    def _compute_io_compatibility(self, chain: List[str]) -> float:
        """计算链中相邻算子对的 I/O 兼容比例（轻量版，用本地 io_types）。

        复用 qgis_candidate_generator._compute_io_factor 的思路。
        """
        if len(chain) < 2 or not self.io_types:
            return 0.5  # 数据不足时返回中性值

        compat_pairs = 0
        check_pairs = 0
        for i in range(len(chain) - 1):
            a, b = chain[i], chain[i + 1]
            if a.startswith("UNKNOWN") or b.startswith("UNKNOWN"):
                continue
            a_info = self.io_types.get(a, {})
            b_info = self.io_types.get(b, {})
            a_out = a_info.get("outputs", [])
            b_in = b_info.get("inputs", [])
            if not a_out or not b_in:
                continue  # 缺 I/O 元数据，不计入分子也不计入分母
            check_pairs += 1
            if set(a_out) & set(b_in):
                compat_pairs += 1

        return compat_pairs / check_pairs if check_pairs > 0 else 0.5

    def verify(
        self,
        qgis_candidate,
        l3_candidate=None,
        expected_length: int = 8,
        set_predictor_tokens: Optional[Dict[int, float]] = None,
        l3_rank: int = 0,
        l3_top1_score: float = 0.0,
        set_threshold: float = 0.5,
    ) -> VerifiedFeatures:
        """提取单个候选的结构化特征。"""
        feat = VerifiedFeatures()

        # ── L3 来源特征 ──
        if l3_candidate is not None:
            feat.l3_score = l3_candidate.final_score
            feat.l3_length = l3_candidate.length
            if expected_length > 0:
                feat.l3_length_deviation = abs(l3_candidate.length - expected_length) / expected_length
                feat.length_ratio = l3_candidate.length / expected_length

        # ── L3 排序信号 ──
        feat.l3_rank = l3_rank
        if l3_candidate is not None:
            feat.l3_score_margin = l3_top1_score - l3_candidate.final_score

        # ── Set Predictor 一致性（拆分为 recall / precision / excess + 保留 Jaccard）──
        if set_predictor_tokens and l3_candidate is not None:
            pred_set = set(t for t, p in set_predictor_tokens.items() if p > set_threshold)
            gen_set = set(l3_candidate.tokens)
            if pred_set or gen_set:
                intersection = pred_set & gen_set
                union = pred_set | gen_set
                feat.set_overlap = len(intersection) / len(union) if union else 0.0
                feat.set_recall = len(intersection) / len(pred_set) if pred_set else 0.0
                feat.set_precision = len(intersection) / len(gen_set) if gen_set else 0.0
                excess = gen_set - pred_set
                feat.set_excess_ratio = len(excess) / len(gen_set) if gen_set else 0.0

        # ── QGIS 候选特征（上游信号，不丢弃）──
        feat.qgis_score = qgis_candidate.score
        feat.qgis_confidence = qgis_candidate.confidence
        feat.unknown_count = qgis_candidate.unknown_count
        feat.unknown_ratio = qgis_candidate.unknown_ratio
        feat.has_critical_unknown = qgis_candidate.has_critical_unknown
        feat.chain_length = len(qgis_candidate.qgis_sequence)

        # ── 轻量结构检查（独立维度）──
        chain = qgis_candidate.qgis_sequence
        non_unknown = [op for op in chain if not op.startswith("UNKNOWN")]
        feat.known_operator_ratio = len(non_unknown) / len(chain) if chain else 0.0
        feat.issue_count = self._estimate_lightweight_issue_count(chain)
        feat.io_compatibility_ratio = self._compute_io_compatibility(chain)

        # 轻量版 validation：同时考虑 issue_count 和 io_compatibility
        has_structural_issues = feat.issue_count > 0
        has_io_issues = feat.io_compatibility_ratio < 0.5
        feat.is_valid = not has_structural_issues and not has_io_issues

        if feat.is_valid:
            feat.validation_confidence = (
                feat.known_operator_ratio * 0.4
                + feat.io_compatibility_ratio * 0.4
                + (1.0 - feat.unknown_ratio) * 0.2
            )
        else:
            feat.validation_confidence = max(0.0,
                feat.known_operator_ratio * 0.3
                + feat.io_compatibility_ratio * 0.3
                - feat.issue_count * 0.1
            )

        # ── 增强版：GraphRAG 验证（可选，覆盖轻量版的 validation 字段）──
        if self.validator is not None:
            try:
                val_result = self.validator.validate_chain(chain)
                # 独立更新，不覆盖 known_operator_ratio
                feat.is_valid = val_result.is_valid
                feat.validation_confidence = val_result.confidence
                feat.issue_count = max(feat.issue_count, len(val_result.issues))
            except Exception:
                pass  # GraphRAG 失败时保留轻量版结果

        # ── 增强版：GraphRAG I/O 兼容性（更精确）──
        if self.retriever is not None:
            try:
                compat_pairs = 0
                check_pairs = 0
                for i in range(len(chain) - 1):
                    a, b = chain[i], chain[i + 1]
                    if a.startswith("UNKNOWN") or b.startswith("UNKNOWN"):
                        continue
                    check_pairs += 1
                    result = self.retriever.check_chain_io_compatibility(a, b)
                    if result.get("compatible", False):
                        compat_pairs += 1
                if check_pairs > 0:
                    feat.io_compatibility_ratio = compat_pairs / check_pairs
            except Exception:
                pass  # GraphRAG 失败时保留轻量版结果

        return feat


class StructuredReranker:
    """基于结构化特征的加权重排序器。

    V2 评分函数仅使用直接候选/模型信号；validation/compatibility 保留为报告字段。
    final_score = w_qgis_score * qgis_score
                + w_confidence * qgis_confidence
                + w_l3_score * l3_score
                + w_set_overlap * set_overlap
                - w_unknown * unknown_ratio
                - w_length_dev * length_deviation
                - w_critical * critical_unknown_penalty
    """

    DEFAULT_WEIGHTS = {
        # 正项：越高越好
        'w_qgis_score': 0.20,        # QGIS 候选分数（含语义映射 + I/O 因子）
        'w_confidence': 0.15,         # QGIS per-step 置信度
        'w_l3_score': 0.10,           # L3 候选质量
        'w_set_overlap': 0.05,        # 与 set predictor 一致性
        # 惩罚项：越高越差
        'w_unknown': 0.10,            # unknown 占比惩罚
        'w_length_dev': 0.05,         # 长度偏差惩罚
        'w_critical': 0.08,           # 关键位置 unknown 硬惩罚
    }

    def __init__(self, verifier: CandidateVerifier, weights: Optional[Dict] = None):
        self.verifier = verifier
        self.weights = weights or self.DEFAULT_WEIGHTS

    def _compute_score(self, feat: VerifiedFeatures) -> float:
        """计算单个候选的综合得分。"""
        w = self.weights

        # 正项
        score = (
            w['w_qgis_score'] * feat.qgis_score
            + w['w_confidence'] * feat.qgis_confidence
            + w['w_l3_score'] * feat.l3_score
            + w['w_set_overlap'] * feat.set_overlap
        )

        # 惩罚项
        score -= w['w_unknown'] * feat.unknown_ratio
        score -= w['w_length_dev'] * min(feat.l3_length_deviation, 1.0)
        score -= w['w_critical'] * (1.0 if feat.has_critical_unknown else 0.0)

        return score

    def rerank(
        self,
        qgis_candidates: List,
        l3_candidates: Optional[List] = None,
        expected_length: int = 8,
        set_predictor_tokens: Optional[Dict[int, float]] = None,
    ) -> RerankerResult:
        """对 QGIS 候选链做重排序。"""
        if not qgis_candidates:
            return RerankerResult(
                best_candidate=None,
                best_features=VerifiedFeatures(),
                best_l3_candidate=None,
                all_ranked=[],
            )

        scored = []
        for i, qgis_cand in enumerate(qgis_candidates):
            l3_cand = l3_candidates[i] if l3_candidates and i < len(l3_candidates) else None
            feat = self.verifier.verify(
                qgis_cand,
                l3_candidate=l3_cand,
                expected_length=expected_length,
                set_predictor_tokens=set_predictor_tokens,
            )
            feat.final_score = self._compute_score(feat)
            scored.append((qgis_cand, l3_cand, feat))

        scored.sort(key=lambda x: x[2].final_score, reverse=True)

        return RerankerResult(
            best_candidate=scored[0][0],
            best_features=scored[0][2],
            best_l3_candidate=scored[0][1],
            all_ranked=scored,
        )


# ═══════════════════════════════════════════════════════════════════
# V3: Two-Stage Reranker (semantic selector)
# ═══════════════════════════════════════════════════════════════════

class QueryChainEncoder:
    """用 all-MiniLM-L6-v2 计算 task_description → L3 chain 的语义匹配分。

    L3 token 序列转为 name 列表拼接（如 'Buffer → Clip → Reclassify'），
    编码后与 task_description 算 cosine similarity。
    """

    def __init__(self, hierarchy_csv_path=None, id_to_l3_code: Optional[Dict[int, str]] = None):
        self.l3_code_to_name: Dict[str, str] = {}
        self.id_to_l3_code = id_to_l3_code or {}
        self._model = None
        self._model_available = True  # False if loading failed
        self._model_load_error: Optional[str] = None  # 加载失败原因（可读字符串）
        self._query_cache: Dict[str, np.ndarray] = {}
        self._chain_cache: Dict[tuple, np.ndarray] = {}

        # 加载 L3 code → name 映射
        csv_path = hierarchy_csv_path or (_resolve_project_root() / "classification_hierarchy.csv")
        if Path(csv_path).exists():
            with open(csv_path, "r", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    code = (row.get("l3_code") or "").strip()
                    name = (row.get("l3_name") or "").strip()
                    if code and name:
                        self.l3_code_to_name[code] = name

    def _ensure_model(self) -> bool:
        """延迟加载 SentenceTransformer 模型。返回 False 表示不可用。"""
        if not self._model_available:
            return False
        if self._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                self._model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
            except Exception as e:
                print(f"  [WARN] QueryChainEncoder: model load failed: {e}")
                self._model_available = False
                self._model_load_error = f"{type(e).__name__}: {e}"
                return False
        return True

    def probe(self) -> bool:
        """主动探测模型是否可用（触发一次加载尝试）。True=可用。"""
        return self._ensure_model()

    def status(self) -> Dict[str, Any]:
        """返回模型状态，方便写入实验元信息。"""
        return {
            "model_name": "sentence-transformers/all-MiniLM-L6-v2",
            "available": bool(self._model_available),
            "loaded": self._model is not None,
            "load_error": self._model_load_error,
            "l3_name_mapping_size": len(self.l3_code_to_name),
        }

    def clear_cache(self):
        """清空缓存（每个 sample 切换时调用）。"""
        self._query_cache.clear()
        self._chain_cache.clear()

    def encode_query(self, task_description: str) -> Optional[np.ndarray]:
        """编码用户任务描述（带缓存）。"""
        if not self._ensure_model():
            return None
        if task_description in self._query_cache:
            return self._query_cache[task_description]
        emb = self._model.encode(task_description, normalize_embeddings=True)
        self._query_cache[task_description] = emb
        return emb

    def encode_chain_from_tokens(self, l3_tokens: List[int]) -> Optional[np.ndarray]:
        """将 L3 token ID 序列转为 name 文本再编码（带缓存）。"""
        if not self._ensure_model():
            return None
        cache_key = tuple(l3_tokens)
        if cache_key in self._chain_cache:
            return self._chain_cache[cache_key]
        names = []
        for tid in l3_tokens:
            code = self.id_to_l3_code.get(tid, "")
            name = self.l3_code_to_name.get(code, code)
            if name:
                names.append(name)
        chain_text = " → ".join(names) if names else "unknown"
        emb = self._model.encode(chain_text, normalize_embeddings=True)
        self._chain_cache[cache_key] = emb
        return emb

    def encode_chain_from_codes(self, l3_codes: List[str]) -> Optional[np.ndarray]:
        """将 L3 code 序列转为 name 文本再编码。"""
        if not self._ensure_model():
            return None
        names = []
        for code in l3_codes:
            name = self.l3_code_to_name.get(code, code)
            if name:
                names.append(name)
        chain_text = " → ".join(names) if names else "unknown"
        return self._model.encode(chain_text, normalize_embeddings=True)

    @staticmethod
    def similarity(query_emb: Optional[np.ndarray], chain_emb: Optional[np.ndarray]) -> float:
        """Cosine similarity（embeddings 已经 L2-normalized）。返回 0.0 if either is None。"""
        if query_emb is None or chain_emb is None:
            return 0.0
        return float(np.dot(query_emb, chain_emb))


class TwoStageReranker:
    """两阶段重排序器：Stage 1 硬过滤 → Stage 2 语义排序。

    Stage 1 砍掉明显差的候选（结构硬伤），减少 Stage 2 的计算量。
    Stage 2 在 shortlist 上做 query-aware 语义排序，语义信号为主。
    """

    # Stage 1 硬过滤阈值
    PRUNE_THRESHOLDS = {
        'max_length_deviation': 1.0,
        'max_unknown_ratio': 0.5,
    }

    # Stage 2 语义排序权重
    SEMANTIC_WEIGHTS = {
        # 语义信号（主导，50%）
        'w_query_chain_sim': 0.25,
        'w_set_recall': 0.15,
        'w_set_precision': 0.10,
        # 模型信号（20%）
        'w_l3_score': 0.10,
        'w_l3_rank_penalty': 0.05,
        'w_l3_margin_penalty': 0.05,
        # 直接候选信号
        'w_qgis_confidence': 0.05,
        # 惩罚项（15%）
        'w_set_excess': 0.05,
        'w_length_penalty': 0.05,
        'w_unknown': 0.05,
    }

    def __init__(
        self,
        verifier: CandidateVerifier,
        query_encoder: Optional[QueryChainEncoder] = None,
        weights: Optional[Dict] = None,
        prune_thresholds: Optional[Dict] = None,
    ):
        self.verifier = verifier
        self.query_encoder = query_encoder
        self.weights = weights or self.SEMANTIC_WEIGHTS
        self.prune = prune_thresholds or self.PRUNE_THRESHOLDS

    def _extract_features(
        self,
        qgis_candidates: List,
        l3_candidates: Optional[List],
        expected_length: int,
        set_predictor_tokens: Optional[Dict[int, float]],
        l3_top1_score: float,
        beam_ranks: Optional[List[int]] = None,
        set_threshold: float = 0.5,
    ) -> List[tuple]:
        """提取所有候选的结构化特征。返回 [(qgis_cand, l3_cand, feat), ...]"""
        entries = []
        for i, qgis_cand in enumerate(qgis_candidates):
            l3_cand = l3_candidates[i] if l3_candidates and i < len(l3_candidates) else None
            rank = beam_ranks[i] if beam_ranks and i < len(beam_ranks) else 0
            feat = self.verifier.verify(
                qgis_cand,
                l3_candidate=l3_cand,
                expected_length=expected_length,
                set_predictor_tokens=set_predictor_tokens,
                l3_rank=rank,
                l3_top1_score=l3_top1_score,
                set_threshold=set_threshold,
            )
            entries.append((qgis_cand, l3_cand, feat))
        return entries

    def _prune_candidates(self, entries: List[tuple]) -> List[tuple]:
        """Stage 1: 硬过滤，砍掉明显差的候选。"""
        shortlist = []
        for qgis_cand, l3_cand, feat in entries:
            if feat.has_critical_unknown:
                continue
            if feat.l3_length_deviation > self.prune['max_length_deviation']:
                continue
            if feat.unknown_ratio > self.prune['max_unknown_ratio']:
                continue
            shortlist.append((qgis_cand, l3_cand, feat))

        # 安全阀：shortlist 为空时回退全部候选
        if not shortlist:
            shortlist = list(entries)

        return shortlist

    def _compute_semantic_score(self, feat: VerifiedFeatures) -> float:
        """Stage 2: 语义排序打分。"""
        w = self.weights

        score = (
            w['w_query_chain_sim'] * feat.query_chain_sim
            + w['w_set_recall'] * feat.set_recall
            + w['w_set_precision'] * feat.set_precision
            + w['w_l3_score'] * feat.l3_score
            + w['w_qgis_confidence'] * feat.qgis_confidence
        )

        # l3_rank penalty: beam rank 0 → 0, rank 1 → 0.2, rank 2 → 0.4, ...
        rank_penalty = min(feat.l3_rank * 0.2, 1.0)
        score -= w['w_l3_rank_penalty'] * rank_penalty

        # l3_score_margin penalty: 离 top1 越远越差 (margin 已经是非负数)
        margin_penalty = min(feat.l3_score_margin * 2.0, 1.0)
        score -= w['w_l3_margin_penalty'] * margin_penalty

        score -= w['w_set_excess'] * feat.set_excess_ratio
        score -= w['w_unknown'] * feat.unknown_ratio

        # 长度惩罚：偏离 1.0 越远越差
        length_penalty = abs(1.0 - feat.length_ratio) if feat.length_ratio > 0 else 1.0
        score -= w['w_length_penalty'] * min(length_penalty, 1.0)

        return score

    def rerank(
        self,
        qgis_candidates: List,
        l3_candidates: Optional[List] = None,
        expected_length: int = 8,
        set_predictor_tokens: Optional[Dict[int, float]] = None,
        task_description: str = "",
        l3_top1_score: float = 0.0,
        beam_ranks: Optional[List[int]] = None,
        set_threshold: float = 0.5,
    ) -> RerankerResult:
        """两阶段重排序。"""
        if not qgis_candidates:
            return RerankerResult(
                best_candidate=None,
                best_features=VerifiedFeatures(),
                best_l3_candidate=None,
                all_ranked=[],
            )

        # 提取全部候选的结构化特征
        entries = self._extract_features(
            qgis_candidates, l3_candidates,
            expected_length, set_predictor_tokens, l3_top1_score,
            beam_ranks=beam_ranks,
            set_threshold=set_threshold,
        )

        # Stage 1: 硬过滤
        shortlist = self._prune_candidates(entries)

        # 计算语义匹配分（如果有 query_encoder）
        query_emb = None
        if self.query_encoder and task_description:
            self.query_encoder.clear_cache()
            query_emb = self.query_encoder.encode_query(task_description)

        # Stage 2: 语义排序
        for qgis_cand, l3_cand, feat in shortlist:
            # 计算 query-chain 语义匹配
            if query_emb is not None and self.query_encoder and l3_cand is not None:
                chain_emb = self.query_encoder.encode_chain_from_tokens(l3_cand.tokens)
                feat.query_chain_sim = self.query_encoder.similarity(query_emb, chain_emb)

            feat.final_score = self._compute_semantic_score(feat)

        shortlist.sort(key=lambda x: x[2].final_score, reverse=True)

        return RerankerResult(
            best_candidate=shortlist[0][0],
            best_features=shortlist[0][2],
            best_l3_candidate=shortlist[0][1],
            all_ranked=shortlist + filtered,
        )


# ═══════════════════════════════════════════════════════════════════
# V4: Learned Reranker (trainable linear weights)
# ═══════════════════════════════════════════════════════════════════

FEATURE_KEYS = [
    "qgis_score", "qgis_confidence", "l3_score",
    "set_overlap", "known_operator_ratio",
    "io_compatibility_ratio", "validation_confidence",
    "unknown_ratio", "l3_length_deviation", "issue_count",
    "query_chain_sim", "set_recall", "set_precision",
    "length_ratio",
]


def features_to_vector(feat: VerifiedFeatures) -> list[float]:
    return [
        float(feat.qgis_score),
        float(feat.qgis_confidence),
        float(feat.l3_score),
        float(feat.set_overlap),
        float(feat.known_operator_ratio),
        float(feat.io_compatibility_ratio),
        float(feat.validation_confidence),
        float(feat.unknown_ratio),
        float(feat.l3_length_deviation),
        float(feat.issue_count) / max(feat.chain_length, 1),
        float(feat.query_chain_sim),
        float(feat.set_recall),
        float(feat.set_precision),
        float(feat.length_ratio),
    ]


DEFAULT_LEARNED_WEIGHTS = [
    0.20,   # qgis_score
    0.15,   # qgis_confidence
    0.10,   # l3_score
    0.05,   # set_overlap
    0.08,   # known_operator_ratio
    0.10,   # io_compatibility_ratio
    0.05,   # validation_confidence
    -0.10,  # unknown_ratio (negative)
    -0.05,  # l3_length_deviation (negative)
    -0.08,  # issue_count (negative)
    0.05,   # query_chain_sim
    0.04,   # set_recall
    0.03,   # set_precision
    0.02,   # length_ratio
]


class LearnedReranker:
    """Reranker with trainable linear weights over VerifiedFeatures.

    Weights can be trained via logistic regression on pairwise ranking data
    and saved/loaded as JSON.
    """

    def __init__(self, verifier, weights: list[float] | None = None):
        self.verifier = verifier
        self.weights = list(weights) if weights else list(DEFAULT_LEARNED_WEIGHTS)
        if len(self.weights) != len(FEATURE_KEYS):
            raise ValueError(
                f"Expected {len(FEATURE_KEYS)} weights, got {len(self.weights)}"
            )

    def _compute_score(self, feat: VerifiedFeatures) -> float:
        vec = features_to_vector(feat)
        return sum(w * v for w, v in zip(self.weights, vec))

    def rerank(
        self,
        qgis_candidates: list,
        l3_candidates: list | None = None,
        expected_length: int = 8,
        set_predictor_tokens: dict | None = None,
    ) -> RerankerResult:
        if not qgis_candidates:
            return RerankerResult(
                best_candidate=None, best_features=VerifiedFeatures(),
                best_l3_candidate=None, all_ranked=[],
            )
        scored = []
        for i, qgis_cand in enumerate(qgis_candidates):
            l3_cand = l3_candidates[i] if l3_candidates and i < len(l3_candidates) else None
            feat = self.verifier.verify(
                qgis_cand, l3_candidate=l3_cand,
                expected_length=expected_length,
                set_predictor_tokens=set_predictor_tokens,
            )
            feat.final_score = self._compute_score(feat)
            scored.append((qgis_cand, l3_cand, feat))
        scored.sort(key=lambda x: x[2].final_score, reverse=True)
        return RerankerResult(
            best_candidate=scored[0][0],
            best_features=scored[0][2],
            best_l3_candidate=scored[0][1],
            all_ranked=scored,
        )

    def save_weights(self, path) -> None:
        import json
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(
                {"feature_keys": FEATURE_KEYS, "weights": self.weights},
                f, indent=2, ensure_ascii=False,
            )

    @classmethod
    def load_weights(cls, verifier, path) -> "LearnedReranker":
        import json
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls(verifier, weights=data["weights"])
