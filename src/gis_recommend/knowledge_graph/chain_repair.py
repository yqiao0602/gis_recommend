"""
chain_repair.py

链修复建议器。

从编排器解耦的独立模块，负责报告 QGIS 候选链中的 I/O 不兼容修复建议。
策略：找最严重问题 → I/O 预过滤替代算子 → LLM 选择 → 记录建议。
该入口不修改候选链，也不返回可被执行路径直接采用的修复结果。
"""

import copy
from typing import List, Dict, Tuple, Optional


class ChainRepairer:
    """迭代多步链修复器。"""

    def __init__(self, retriever, validator, llm_scorer, io_types: dict):
        """
        Args:
            retriever: Neo4jGraphRAGRetriever 实例
            validator: ChainValidator 实例
            llm_scorer: LLMScorer 实例（可为 None）
            io_types: dict, 来自 qgis_operator_io_types.json 的预计算缓存。
                      格式: {"Slope": {"inputs": ["raster"], "outputs": ["raster"]}, ...}
                      已归一化为扁平字符串列表，可直接做 set() 交集运算。
        """
        self.retriever = retriever
        self.validator = validator
        self.llm_scorer = llm_scorer
        self.io_types = io_types

    def repair(self, candidate, validation, user_query: str, max_rounds: int = 3):
        """
        报告候选链中的 I/O 不兼容修复建议，不修改候选链。

        Args:
            candidate: QGISCandidate 对象
            validation: ChainValidationResult 对象
            user_query: 用户原始查询，传给 LLM 作为修复选择的上下文
            max_rounds: 最大修复轮次

        Returns:
            (candidate, validation, repair_log)
            repair_log: List[Dict] 每轮修复记录
        """
        repair_log = []
        old_issue_count = len(validation.issues)
        skipped_indices = set()

        for round_num in range(1, max_rounds + 1):
            chain = list(candidate.qgis_sequence)

            # 1. 找最严重问题（跳过已知无法修复的）
            problem_idx, severity = self._find_worst_problem(
                validation, chain, skipped_indices
            )
            if problem_idx is None:
                break

            problem_op = chain[problem_idx]
            step = candidate.steps[problem_idx] if problem_idx < len(candidate.steps) else None

            # 2. 获取 I/O 预过滤后的替代算子
            prev_op = chain[problem_idx - 1] if problem_idx > 0 else None
            next_op = chain[problem_idx + 1] if problem_idx < len(chain) - 1 else None
            alternatives = self._get_alternatives(step, problem_op, prev_op, next_op)

            if not alternatives:
                repair_log.append({
                    "round": round_num, "problem_idx": problem_idx,
                    "old_op": problem_op, "new_op": None,
                    "action": "skipped", "reason": "no alternatives",
                })
                skipped_indices.add(problem_idx)
                continue

            # 3. LLM 选择或 fallback
            context = {
                "prev_operator": prev_op or "None",
                "next_operator": next_op or "None",
                "prev_l3": step.l3_code if step and hasattr(step, 'l3_code') else "Unknown",
                "user_query": user_query,
            }
            selected_alt = self._select_replacement(alternatives, context, user_query, step)

            if selected_alt is None:
                repair_log.append({
                    "round": round_num, "problem_idx": problem_idx,
                    "old_op": problem_op, "new_op": None,
                    "action": "skipped", "reason": "selection failed",
                })
                skipped_indices.add(problem_idx)
                continue

            # 4. 仅生成建议链，不替换候选，也不改变后续执行路径
            new_op = selected_alt["operator_name"]
            suggested_chain = list(chain)
            suggested_chain[problem_idx] = new_op
            suggested_issue_count = old_issue_count
            if self.validator is not None:
                try:
                    suggested_issue_count = len(self.validator.validate_chain(suggested_chain).issues)
                except Exception:
                    pass

            repair_log.append({
                "round": round_num, "problem_idx": problem_idx,
                "old_op": problem_op, "new_op": new_op,
                "severity": severity, "alternatives_count": len(alternatives),
                "issues_before": old_issue_count, "issues_after": suggested_issue_count,
                "suggested_chain": suggested_chain,
                "action": "suggestion",
                "applied": False,
            })
            break

        return candidate, validation, repair_log

    # ── 私有方法 ──────────────────────────────────────────

    def _compute_severity(self, detail, chain, idx, all_step_details):
        """
        计算单步不兼容的严重度。

        Returns:
            2: 前后两端都不兼容（完全孤立）
            1: 只有一端不兼容
            0: 兼容或 UNKNOWN 步骤

        step_details 索引语义（来自 chain_validator.py）：
          step_details[i].io_check 表示 chain[i] → chain[i+1] 的兼容性
        因此：
          chain[idx-1] → chain[idx] 的兼容性在 step_details[idx-1].io_check
          chain[idx] → chain[idx+1] 的兼容性在 step_details[idx].io_check
        """
        if chain[idx].startswith("UNKNOWN"):
            return 0

        # 前一步 → 当前步
        prev_incompatible = False
        if idx > 0:
            prev_detail = all_step_details[idx - 1]
            prev_io = prev_detail.get("io_check")
            if isinstance(prev_io, dict) and not prev_io.get("compatible", True):
                prev_incompatible = True

        # 当前步 → 后一步
        curr_incompatible = False
        curr_io = detail.get("io_check")
        if isinstance(curr_io, dict) and not curr_io.get("compatible", True):
            curr_incompatible = True

        if prev_incompatible and curr_incompatible:
            return 2
        elif prev_incompatible or curr_incompatible:
            return 1
        return 0

    def _find_worst_problem(self, validation, chain, skipped_indices=None):
        """返回 (problem_idx, severity) 或 (None, 0)。跳过 UNKNOWN 和已跳过的索引。"""
        skipped = skipped_indices or set()
        problems = []
        for detail in validation.step_details:
            idx = detail["index"]
            if idx in skipped:
                continue
            severity = self._compute_severity(detail, chain, idx, validation.step_details)
            if severity > 0:
                problems.append((idx, severity))
        if not problems:
            return None, 0
        problems.sort(key=lambda x: (-x[1], x[0]))
        return problems[0]

    def _fetch_raw_alternatives(self, step, problem_op):
        """从 GraphRAG 获取原始替代算子。来源：同 L3 映射 + 同 L2 族。"""
        alternatives = []
        # 来源1：同 L3 映射
        if step and hasattr(step, 'l3_code') and step.l3_code:
            l3_ops = self.retriever.get_operators_for_l3(step.l3_code, top_k=10)
            for op in l3_ops:
                if op["name"] != problem_op:
                    alternatives.append({
                        "operator_name": op["name"],
                        "confidence": op["confidence"],
                        "source": "same_l3",
                    })
        # 来源2：同 L2 族
        related = self.retriever.get_related_operators(problem_op, top_k=10)
        seen = {a["operator_name"] for a in alternatives}
        for r in related:
            if r["name"] != problem_op and r["name"] not in seen:
                alternatives.append({
                    "operator_name": r["name"],
                    "confidence": r["confidence"],
                    "source": "same_l2",
                })
        return alternatives

    def _get_alternatives(self, step, problem_op, prev_op, next_op):
        """获取 I/O 预过滤后的替代算子。"""
        raw = self._fetch_raw_alternatives(step, problem_op)
        filtered = []
        for alt in raw:
            alt_name = alt["operator_name"]
            alt_info = self.io_types.get(alt_name, {})
            alt_in = alt_info.get("inputs", [])
            alt_out = alt_info.get("outputs", [])

            prev_ok = True
            if prev_op:
                prev_out = self.io_types.get(prev_op, {}).get("outputs", [])
                if prev_out and alt_in:
                    prev_ok = bool(set(prev_out) & set(alt_in))

            next_ok = True
            if next_op:
                next_in = self.io_types.get(next_op, {}).get("inputs", [])
                if alt_out and next_in:
                    next_ok = bool(set(alt_out) & set(next_in))

            if prev_ok and next_ok:
                alt["io_match"] = "both"
                filtered.append(alt)
            elif prev_ok or next_ok:
                alt["io_match"] = "partial"
                filtered.append(alt)
            # 两端都不兼容：丢弃

        # both > partial，然后按 confidence 降序
        filtered.sort(key=lambda a: (a["io_match"] == "both", a["confidence"]), reverse=True)
        return filtered

    def _select_replacement(self, alternatives, context, user_query, step):
        """LLM 选择最佳替代算子，或 fallback 到最高置信度。返回候选 dict 或 None。"""
        if not alternatives:
            return None

        if self.llm_scorer:
            l3_code = step.l3_code if step and hasattr(step, 'l3_code') else "Unknown"
            constraints = {"platform": "QGIS", "position_type": "middle"}
            try:
                result = self.llm_scorer.score_candidates(
                    l3_code=l3_code,
                    unknown_type="repair",
                    candidates=alternatives[:10],
                    context=context,
                    constraints=constraints,
                )
                if result.selected_operator != "Unknown":
                    for alt in alternatives:
                        if alt["operator_name"] == result.selected_operator:
                            return alt
            except Exception:
                pass

        # Fallback: 最高置信度
        return alternatives[0]

    def _apply_repair(self, candidate, idx, selected_alt):
        """深拷贝 candidate 并替换指定位置算子。不修改原对象。"""
        new_cand = copy.deepcopy(candidate)
        new_op = selected_alt["operator_name"]
        new_chain = list(new_cand.qgis_sequence)
        new_chain[idx] = new_op
        new_cand.qgis_sequence = new_chain
        if idx < len(new_cand.steps):
            step = new_cand.steps[idx]
            step.operator = new_op
            step.is_unknown = new_op.startswith("UNKNOWN")
            step.unknown_info = None if not step.is_unknown else step.unknown_info
            step.confidence = float(selected_alt.get("confidence", step.confidence or 0.0))
            step.mapping = None
        return new_cand
