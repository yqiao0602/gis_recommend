"""
完整的交互式QGIS算子链生成系统

整合流程：
1. 用户输入自然语言任务描述
2. LLM入口：提取task_type和任务信息
3. Transformer模型：生成L3原语序列
4. Beam Search：生成多条QGIS候选链
5. GraphRAG + LLM：融合推理，选出最佳链（含链校验）
6. 问答系统：生成详细解释
7. 用户追问：基于RAG的知识驱动回答

使用方法：
    python interactive_system.py
"""

import sys
import json
from pathlib import Path
from typing import List, Dict, Any, Tuple, Optional

# LLM入口模块（完整流程）
from gis_recommend.llm.llm_pipeline import LLMWorkflowPipeline

# 任务→L3模型（V4.2）
from gis_recommend.config.transformer_config import OUTPUT_DIR, DEVICE, V4_2_TRANSFORMER_CHECKPOINT_DIR
from gis_recommend.inference.infer_l3_candidates_v4 import L3SequenceInferencerV4

# L3→QGIS生成器
from gis_recommend.operators.qgis_candidate_generator import QGISCandidateGenerator

# GraphRAG + LLM
from gis_recommend.knowledge_graph.neo4j_graphrag_retriever import Neo4jGraphRAGRetriever
from gis_recommend.knowledge_graph.rag_context_builder import RAGContextBuilder
from gis_recommend.knowledge_graph.chain_validator import ChainValidator
from gis_recommend.llm.llm_scorer import LLMScorer

# 问答系统
from gis_recommend.operators.qgis_operator_qa import QGISOperatorQA


class InteractiveQGISSystem:
    """交互式QGIS算子链生成系统"""

    def __init__(
        self,
        model_checkpoint: str = None,  # 默认使用 V4.2 checkpoint
        task_vocab_path: str = "outputs/task_type_vocabulary.json",
        llm_api_key: str = "sk-6d6a3478844243979fd29431ce31a841",
        neo4j_uri: str = "bolt://localhost:7687",
        neo4j_username: str = "neo4j",
        neo4j_password: str = "12345678",
        use_llm_for_task_type: bool = False  # 是否使用LLM选择task_type（可选）
    ):
        """初始化系统"""
        self.llm_api_key = llm_api_key
        self.neo4j_uri = neo4j_uri
        self.neo4j_username = neo4j_username
        self.neo4j_password = neo4j_password

        # 保存最近一次推荐结果，供追问使用
        self._last_result: Optional[Dict[str, Any]] = None

        print("\n" + "="*70)
        print("初始化交互式QGIS算子链生成系统")
        print("="*70)

        # 1. LLM入口：完整工作流（Phase 0-3）
        print("\n[1/5] 初始化LLM入口（完整工作流）...")
        try:
            self.llm_pipeline = LLMWorkflowPipeline(
                task_vocab_path=task_vocab_path,
                llm_backend="openai",
                api_key=llm_api_key,
                model_name="qwen-plus",
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
                use_phase3=True,  # 启用Phase 3 task_type检索
                use_llm_selection=True  # 启用LLM选择以提高准确性
            )
            print("   [OK] LLM入口初始化成功（包含Phase 0-3）")
        except Exception as e:
            print(f"   [WARNING] LLM入口初始化失败: {e}")
            print("   [INFO] 将使用简化模式")
            self.llm_pipeline = None

        # 2. 任务→L3模型
        print("\n[2/5] 加载任务条件化Transformer模型...")
        self._load_task_to_l3_model(model_checkpoint, task_vocab_path)

        # 3. L3→QGIS生成器
        print("\n[3/5] 初始化QGIS候选生成器...")
        self.qgis_generator = QGISCandidateGenerator(
            beam_width=5,
            max_unknown_ratio=0.3,
            max_unknown_count=3,
            critical_positions={'start'}
        )
        print("   [OK] QGIS生成器初始化成功")

        # 4. GraphRAG + 链校验 + LLM评分器
        print("\n[4/5] 初始化GraphRAG、链校验和LLM评分器...")
        try:
            self.graphrag_retriever = Neo4jGraphRAGRetriever(
                uri=neo4j_uri,
                username=neo4j_username,
                password=neo4j_password
            )
            self.rag_builder = RAGContextBuilder(self.graphrag_retriever)
            self.chain_validator = ChainValidator(self.graphrag_retriever)
            self.llm_scorer = LLMScorer(
                api_key=llm_api_key,
                model="qwen-plus",
                base_url="https://dashscope.aliyuncs.com/compatible-mode/v1"
            )
            print("   [OK] GraphRAG + 链校验 + LLM评分器初始化成功")
        except Exception as e:
            print(f"   [WARNING] GraphRAG初始化失败: {e}")
            self.graphrag_retriever = None
            self.rag_builder = None
            self.chain_validator = None
            self.llm_scorer = None

        # 5. 问答系统（注入 RAG builder）
        print("\n[5/5] 初始化问答系统...")
        try:
            self.qa_system = QGISOperatorQA(
                llm_api_key=llm_api_key,
                neo4j_uri=neo4j_uri,
                neo4j_username=neo4j_username,
                neo4j_password=neo4j_password,
                rag_builder=self.rag_builder,
            )
            print("   [OK] 问答系统初始化成功")
        except Exception as e:
            print(f"   [WARNING] 问答系统初始化失败: {e}")
            self.qa_system = None

        print("\n" + "="*70)
        print("系统初始化完成！")
        print("="*70)

    def _load_task_to_l3_model(self, model_checkpoint: str, task_vocab_path: str):
        """加载任务→L3序列的模型（使用V4推理器）"""
        from pathlib import Path

        if model_checkpoint:
            checkpoint_path = Path(model_checkpoint)
        else:
            # 默认使用 V4.2 checkpoint
            checkpoint_path = V4_2_TRANSFORMER_CHECKPOINT_DIR / "best_model.pth"

        self.l3_inferencer = L3SequenceInferencerV4(
            checkpoint_path=checkpoint_path,
            device=DEVICE,
        )

        print("   [OK] V4模型加载成功")

    def process_user_query(self, user_query: str) -> Dict[str, Any]:
        """
        处理用户查询的完整流程

        参数:
            user_query: 用户输入的自然语言任务描述

        返回:
            包含所有结果的字典
        """
        print("\n" + "="*70)
        print("开始处理用户查询")
        print("="*70)
        print(f"\n用户输入: {user_query}")

        # 阶段1：LLM入口 - 提取task_type和任务信息
        print("\n" + "-"*70)
        print("阶段1：LLM入口 - 分析任务类型")
        print("-"*70)

        task_type, task_info = self._extract_task_info(user_query)
        print(f"\n识别的任务类型: {task_type}")

        # 阶段2：生成L3序列（取 top-3 候选）
        print("\n" + "-"*70)
        print("阶段2：Transformer模型 - 生成L3原语序列")
        print("-"*70)

        l3_sequences = self._generate_l3_sequences(
            task_desc=user_query,
            task_type=task_type,
            task_name=task_info.get("task_name", user_query[:30]),
            model_input=task_info.get("model_input"),
            num_candidates=3
        )

        if not l3_sequences:
            return {"success": False, "error": "L3序列生成失败"}

        print(f"\n共生成 {len(l3_sequences)} 条L3候选序列")

        # 阶段3：对每条L3候选生成QGIS链，汇总去重
        print("\n" + "-"*70)
        print("阶段3：Beam Search - 生成QGIS算子链候选")
        print("-"*70)

        all_qgis_candidates = []
        seen_chains = set()
        for i, l3_seq in enumerate(l3_sequences):
            print(f"\n  L3候选 {i+1}/{len(l3_sequences)}:")
            candidates = self._generate_qgis_candidates(l3_seq, num_candidates=5)
            for cand in candidates:
                chain_key = tuple(cand.qgis_sequence)
                if chain_key not in seen_chains:
                    seen_chains.add(chain_key)
                    all_qgis_candidates.append(cand)

        if not all_qgis_candidates:
            return {"success": False, "error": "QGIS链生成失败"}

        print(f"\n汇总去重后共 {len(all_qgis_candidates)} 条候选链")

        # 阶段4：融合推理
        print("\n" + "-"*70)
        print("阶段4：GraphRAG + LLM - 融合推理选出最佳链")
        print("-"*70)

        best_chain, validation_result = self._select_best_chain_with_graphrag(
            all_qgis_candidates,
            user_query,
            l3_sequences[0]  # 传最佳L3序列作为参考
        )

        print(f"\n最佳QGIS链: {' -> '.join(best_chain.qgis_sequence)}")
        print(f"评分: {best_chain.score:.4f}")
        print(f"置信度: {best_chain.confidence:.4f}")

        if validation_result:
            if validation_result.is_valid:
                print(f"链校验: 通过 (置信度: {validation_result.confidence:.4f})")
            else:
                print(f"链校验: 发现 {len(validation_result.issues)} 个问题")
                for issue in validation_result.issues:
                    print(f"  - {issue}")
                for sug in validation_result.suggestions:
                    print(f"  [建议] {sug}")

        # 阶段5：生成解释和指导
        print("\n" + "-"*70)
        print("阶段5：问答系统 - 生成详细解释")
        print("-"*70)

        explanations = self._generate_explanations(
            best_chain.qgis_sequence,
            user_query
        )

        # 汇总结果
        result = {
            "success": True,
            "user_query": user_query,
            "task_type": task_type,
            "l3_sequence": l3_sequences[0],
            "qgis_chain": best_chain.qgis_sequence,
            "score": best_chain.score,
            "confidence": best_chain.confidence,
            "unknown_count": best_chain.unknown_count,
            "all_candidates": [
                {
                    "chain": c.qgis_sequence,
                    "score": c.score,
                    "confidence": c.confidence
                }
                for c in all_qgis_candidates
            ],
            "validation": {
                "is_valid": validation_result.is_valid,
                "issues": validation_result.issues,
                "suggestions": validation_result.suggestions,
                "confidence": validation_result.confidence,
            } if validation_result else None,
            "explanations": explanations
        }

        # 缓存结果供追问使用
        self._last_result = result

        self._print_final_result(result)

        return result

    def _extract_task_info(self, user_query: str) -> Tuple[str, Dict]:
        """使用完整LLM流程提取task_type和任务信息"""
        if self.llm_pipeline is None:
            # 使用默认task_type
            return "Spatial Analysis", {"task_name": user_query[:30], "model_input": None}

        try:
            # 使用完整的LLM工作流（Phase 0-3）
            task_info, template_text, model_input = self.llm_pipeline.process(
                user_query=user_query,
                device=DEVICE,
                use_llm=True
            )

            # 从model_input中获取task_type_id
            task_type_id = model_input['task_type_id'].item()

            # 从task_info中获取task_type（如果有的话）
            task_type = getattr(task_info, 'task_type', 'Unknown')
            if task_type == 'Unknown' and hasattr(self.llm_pipeline, 'task_type_retriever'):
                # 尝试从retriever获取
                try:
                    id_to_type = self.llm_pipeline.task_type_retriever.embedding_retriever.id_to_task_type
                    task_type = id_to_type.get(task_type_id, 'Unknown')
                except:
                    pass

            print(f"  提取的任务信息:")
            print(f"    - 任务名称: {task_info.task_name}")
            print(f"    - 任务类型: {task_type}")
            print(f"    - 任务描述: {task_info.task_description[:50]}...")

            return task_type, {
                "task_name": task_info.task_name,
                "task_description": task_info.task_description,
                "task_type_id": task_type_id,
                "constraints": task_info.constraints,
                "template_text": template_text,
                "model_input": model_input
            }

        except Exception as e:
            print(f"  [WARNING] LLM流程失败: {e}")
            import traceback
            traceback.print_exc()
            return "Spatial Analysis", {"task_name": user_query[:30], "model_input": None}

    def _generate_l3_sequences(
        self,
        task_desc: str,
        task_type: str,
        task_name: str,
        num_candidates: int = 3,
        model_input: Dict[str, Any] = None
    ) -> List[List[str]]:
        """生成L3序列候选"""
        try:
            # Set dynamic expected length based on task type
            if hasattr(self.l3_inferencer, 'set_expected_length'):
                self.l3_inferencer.set_expected_length(task_type)

            # 使用L3SequenceInferencer的infer方法
            if model_input:
                candidates = self.l3_inferencer.infer_from_model_input(
                    model_input=model_input,
                    task_type=task_type
                )
            else:
                candidates = self.l3_inferencer.infer(
                    task_name=task_name,
                    task_description=task_desc,
                    task_type=task_type
                )

            l3_sequences = []
            for i, cand in enumerate(candidates[:num_candidates], 1):
                # 将token IDs解码为L3代码
                l3_seq = self.l3_inferencer.decode_tokens(cand.tokens, use_name=False)
                # 过滤掉特殊token
                l3_seq = [code for code in l3_seq if not code.startswith('<')]
                l3_sequences.append(l3_seq)

                if i <= 3:
                    print(f"\n  L3候选 {i}: {' -> '.join(l3_seq[:5])}{'...' if len(l3_seq) > 5 else ''}")
                    print(f"    评分: {cand.normalized_score:.4f}, 长度: {cand.length}")

            return l3_sequences

        except Exception as e:
            print(f"  [ERROR] L3序列生成失败: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _generate_qgis_candidates(
        self,
        l3_sequence: List[str],
        num_candidates: int = 5
    ) -> List[Any]:
        """生成QGIS算子链候选"""
        try:
            candidates = self.qgis_generator.generate_candidates(
                l3_sequence=l3_sequence,
                top_k=num_candidates
            )

            for i, cand in enumerate(candidates[:3], 1):
                print(f"\n  QGIS候选 {i}:")
                print(f"    链: {' -> '.join(cand.qgis_sequence[:4])}{'...' if len(cand.qgis_sequence) > 4 else ''}")
                print(f"    评分: {cand.score:.4f}, Unknown: {cand.unknown_count}")

            return candidates

        except Exception as e:
            print(f"  [ERROR] QGIS链生成失败: {e}")
            return []

    def _select_best_chain_with_graphrag(
        self,
        candidates: List[Any],
        user_query: str,
        l3_sequence: List[str]
    ) -> Tuple[Any, Any]:
        """
        融合推理：GraphRAG结构化评分 → RAG+LLM打分 → 链修复

        4a. GraphRAG 结构化评分（所有候选链）
        4b. RAG + LLM 打分（top-3）
        4c. 链修复（top-1，如有问题）
        """
        from gis_recommend.knowledge_graph.chain_validator import ChainValidationResult

        if not self.graphrag_retriever or not self.chain_validator:
            print("  [INFO] GraphRAG未启用，使用默认评分")
            return candidates[0], ChainValidationResult(is_valid=True, confidence=0.5)

        # ── 4a. GraphRAG 结构化评分（所有候选链）──────────────
        print("\n  [4a] GraphRAG 结构化评分...")
        scored = []
        for cand in candidates:
            chain = cand.qgis_sequence
            total = len(chain)
            if total == 0:
                continue

            # 算子存在性
            known = 0
            for op in chain:
                if op.startswith("UNKNOWN"):
                    continue
                if self.graphrag_retriever.get_operator_info(op):
                    known += 1
            non_unk = sum(1 for op in chain if not op.startswith("UNKNOWN"))
            known_ratio = known / non_unk if non_unk > 0 else 0.0

            # I/O 兼容性
            compat_pairs = 0
            check_pairs = 0
            for i in range(total - 1):
                a, b = chain[i], chain[i + 1]
                if a.startswith("UNKNOWN") or b.startswith("UNKNOWN"):
                    continue
                check_pairs += 1
                result = self.graphrag_retriever.check_chain_io_compatibility(a, b)
                if result["compatible"]:
                    compat_pairs += 1
            io_score = compat_pairs / check_pairs if check_pairs > 0 else 0.5

            # 链校验
            validation = self.chain_validator.validate_chain(chain)

            structural = (
                cand.confidence * 0.4
                + known_ratio * 0.2
                + io_score * 0.2
                + validation.confidence * 0.2
            )
            scored.append((structural, cand, validation))

        scored.sort(key=lambda x: x[0], reverse=True)

        for i, (s, c, v) in enumerate(scored[:3]):
            print(f"    候选 {i+1}: structural={s:.4f} "
                  f"(conf={c.confidence:.3f}, known={len([o for o in c.qgis_sequence if not o.startswith('UNKNOWN')])}/"
                  f"{len(c.qgis_sequence)}, issues={len(v.issues)})")

        # ── 4b. RAG + LLM 打分（top-3）───────────────────
        top3 = scored[:3]
        if self.llm_scorer and self.rag_builder:
            print("\n  [4b] RAG + LLM 打分 (top-3)...")
            llm_scored = []
            for structural_score, cand, validation in top3:
                try:
                    rag_ctx = self.rag_builder.build_chain_context(cand.qgis_sequence)
                    llm_result = self.llm_scorer.score_chain(
                        user_task=user_query,
                        qgis_chain=cand.qgis_sequence,
                        rag_context=rag_ctx,
                    )
                    llm_s = llm_result["score"]  # 0-10
                    final = structural_score * 0.5 + (llm_s / 10.0) * 0.5
                    print(f"    LLM score={llm_s:.1f}, final={final:.4f}: {llm_result['reasoning'][:80]}")
                except Exception as e:
                    print(f"    [WARNING] LLM打分失败: {e}")
                    final = structural_score
                llm_scored.append((final, cand, validation))
            llm_scored.sort(key=lambda x: x[0], reverse=True)
            best_score, best_cand, best_validation = llm_scored[0]
        else:
            print("\n  [4b] LLM未启用，使用结构化评分")
            best_score, best_cand, best_validation = top3[0]

        print(f"\n  [OK] 选出最佳链 (final={best_score:.4f})")

        # ── 4c. 链修复（如有问题）────────────────────────
        if best_validation.issues:
            print(f"\n  [4c] 链校验发现 {len(best_validation.issues)} 个问题，尝试修复...")
            best_cand = self._repair_chain(best_cand, best_validation, user_query)

        return best_cand, best_validation

    def _repair_chain(self, candidate, validation, user_query: str):
        """
        修复候选链中校验失败的步骤。
        GraphRAG 提供替代算子 → LLM 从中选择。
        只修复最严重的 1 个问题。
        """
        if not validation.step_details or not self.graphrag_retriever:
            return candidate

        # 找到第一个有 I/O 不兼容问题的步骤
        problem_idx = None
        for detail in validation.step_details:
            io_check = detail.get("io_check")
            if isinstance(io_check, dict) and not io_check.get("compatible", True):
                problem_idx = detail["index"]
                break

        if problem_idx is None:
            return candidate

        chain = list(candidate.qgis_sequence)
        problem_op = chain[problem_idx]
        print(f"    修复步骤 {problem_idx + 1}: {problem_op}")

        # GraphRAG 找替代算子
        alternatives = []
        # 方式1：同 L3 映射的其他算子
        if problem_idx < len(candidate.steps):
            step = candidate.steps[problem_idx]
            if hasattr(step, 'l3_code') and step.l3_code:
                l3_ops = self.graphrag_retriever.get_operators_for_l3(step.l3_code, top_k=10)
                for op in l3_ops:
                    if op["name"] != problem_op:
                        alternatives.append({
                            "operator_name": op["name"],
                            "confidence": op["confidence"],
                            "source": "same_l3"
                        })

        # 方式2：同族算子（同 L2 类别）
        related = self.graphrag_retriever.get_related_operators(problem_op, top_k=10)
        for r in related:
            if r["name"] != problem_op and r["name"] not in [a["operator_name"] for a in alternatives]:
                alternatives.append({
                    "operator_name": r["name"],
                    "confidence": r["confidence"],
                    "source": "same_l2"
                })

        if not alternatives:
            print(f"    未找到替代算子，保持原样")
            return candidate

        print(f"    找到 {len(alternatives)} 个替代候选")

        # LLM 从替代中选择
        if self.llm_scorer:
            prev_op = chain[problem_idx - 1] if problem_idx > 0 else "None"
            next_op = chain[problem_idx + 1] if problem_idx < len(chain) - 1 else "None"
            step = candidate.steps[problem_idx] if problem_idx < len(candidate.steps) else None
            context = {
                "prev_operator": prev_op,
                "next_operator": next_op,
                "prev_l3": step.l3_code if step and hasattr(step, 'l3_code') else "Unknown",
                "next_l3": "Unknown",
            }
            constraints = {"platform": "QGIS", "position_type": "middle"}

            result = self.llm_scorer.score_candidates(
                l3_code=step.l3_code if step and hasattr(step, 'l3_code') else "Unknown",
                unknown_type="repair",
                candidates=alternatives[:10],
                context=context,
                constraints=constraints,
            )

            if result.selected_operator != "Unknown":
                chain[problem_idx] = result.selected_operator
                print(f"    替换: {problem_op} -> {result.selected_operator} ({result.reasoning[:60]})")
                candidate.qgis_sequence = chain
        else:
            # 无 LLM 时选第一个替代
            chain[problem_idx] = alternatives[0]["operator_name"]
            candidate.qgis_sequence = chain

        return candidate

    def _generate_explanations(
        self,
        qgis_chain: List[str],
        user_query: str
    ) -> Dict[str, str]:
        """生成轻量链概述（不预生成每个算子的详细解释）"""
        if not self.qa_system:
            return {}

        try:
            print("\n  生成算子链概述...")
            chain_explanation = self.qa_system.explain_operator_chain(qgis_chain)
            print("  [OK] 概述已生成")
            return {"chain_overview": chain_explanation}
        except Exception as e:
            print(f"  [WARNING] 概述生成失败: {e}")
            return {}

    # ------------------------------------------------------------------
    # 追问支持
    # ------------------------------------------------------------------

    def ask_followup(
        self,
        question: str,
        operator_name: Optional[str] = None,
    ) -> str:
        """
        用户追问，基于 RAG 回答

        参数:
            question: 用户追问内容
            operator_name: 可选指定算子名称

        返回:
            回答文本
        """
        if not self.qa_system:
            return "问答系统未初始化。"

        # 从缓存结果中提取上下文
        operator_chain = None
        l3_code = None

        if self._last_result:
            operator_chain = self._last_result.get("qgis_chain")
            l3_seq = self._last_result.get("l3_sequence")
            if l3_seq:
                l3_code = l3_seq[0]  # 使用第一个 L3 作为上下文

        if self.qa_system.rag_builder:
            return self.qa_system.answer_with_rag(
                question=question,
                operator_name=operator_name,
                operator_chain=operator_chain,
                l3_code=l3_code,
            )
        elif operator_name:
            return self.qa_system.answer_question(operator_name, question)
        else:
            return "请指定一个算子名称以便回答您的问题。"

    # ------------------------------------------------------------------
    # 输出与保存
    # ------------------------------------------------------------------

    def _print_final_result(self, result: Dict[str, Any]):
        """打印最终结果"""
        print("\n" + "="*70)
        print("最终结果")
        print("="*70)

        print(f"\n用户查询: {result['user_query']}")
        print(f"\n任务类型: {result['task_type']}")
        print(f"\nL3序列: {' -> '.join(result['l3_sequence'])}")
        print(f"\n最佳QGIS算子链:")
        for i, op in enumerate(result['qgis_chain'], 1):
            print(f"  {i}. {op}")

        print(f"\n评分信息:")
        print(f"  - 综合评分: {result['score']:.4f}")
        print(f"  - 置信度: {result['confidence']:.4f}")
        print(f"  - Unknown数量: {result['unknown_count']}")

        if result.get("validation"):
            v = result["validation"]
            print(f"\n链校验:")
            print(f"  - 通过: {'是' if v['is_valid'] else '否'}")
            print(f"  - 校验置信度: {v['confidence']:.4f}")
            if v["issues"]:
                print(f"  - 问题:")
                for issue in v["issues"]:
                    print(f"    * {issue}")
            if v["suggestions"]:
                print(f"  - 建议:")
                for sug in v["suggestions"]:
                    print(f"    * {sug}")

        print(f"\n生成了 {len(result['all_candidates'])} 条候选链")
        print(f"生成了 {len(result['explanations'])} 个解释")

        print("\n" + "="*70)

    def save_result(self, result: Dict[str, Any], output_dir: str = "outputs"):
        """保存结果到文件"""
        import os
        os.makedirs(output_dir, exist_ok=True)

        # 保存JSON结果
        json_path = os.path.join(output_dir, "result.json")
        with open(json_path, 'w', encoding='utf-8') as f:
            save_result = {
                "user_query": result["user_query"],
                "task_type": result["task_type"],
                "l3_sequence": result["l3_sequence"],
                "qgis_chain": result["qgis_chain"],
                "score": result["score"],
                "confidence": result["confidence"],
                "validation": result.get("validation"),
                "all_candidates": result["all_candidates"]
            }
            json.dump(save_result, f, ensure_ascii=False, indent=2)

        print(f"\n[OK] 结果已保存到: {json_path}")

        # 保存解释文本
        for key, text in result["explanations"].items():
            text_path = os.path.join(output_dir, f"{key}.txt")
            with open(text_path, 'w', encoding='utf-8') as f:
                f.write(text)
            print(f"[OK] 解释已保存到: {text_path}")

    def close(self):
        """关闭连接"""
        if hasattr(self, 'qa_system') and self.qa_system:
            self.qa_system.close()
        if hasattr(self, 'graphrag_retriever') and self.graphrag_retriever:
            self.graphrag_retriever.close()


def interactive_mode():
    """交互式模式"""
    print("\n" + "="*70)
    print("欢迎使用交互式QGIS算子链生成系统")
    print("="*70)
    print("\n这个系统可以将您的自然语言任务描述转换为QGIS算子链")
    print("\n示例任务：")
    print("  - 在某个点附近100米的范围内选定一个点")
    print("  - 从卫星影像中提取水体并导出为矢量多边形")
    print("  - 对道路图层创建500米缓冲区，然后与建筑物图层相交")
    print("  - 计算NDVI并进行时间序列分析")
    print("\n命令：")
    print("  输入任务描述 → 生成算子链")
    print("  ?<问题>       → 追问（如 ?Buffer vectors怎么用）")
    print("  quit/exit     → 退出系统")
    print("="*70)

    # 初始化系统
    system = InteractiveQGISSystem()

    # 交互循环
    while True:
        print("\n" + "-"*70)
        user_input = input("\n请输入您的任务描述（或 ?追问）: ").strip()

        if user_input.lower() in ['quit', 'exit', 'q']:
            print("\n感谢使用！再见！")
            break

        if not user_input:
            print("请输入有效的任务描述")
            continue

        # 追问模式
        if user_input.startswith("?"):
            question = user_input[1:].strip()
            if not question:
                print("请输入您的问题（如 ?Buffer vectors怎么用）")
                continue

            # 尝试提取算子名称（简单启发式：检查引号或已知算子）
            op_name = None
            if system._last_result:
                for op in system._last_result.get("qgis_chain", []):
                    if op in question:
                        op_name = op
                        break

            try:
                answer = system.ask_followup(question, operator_name=op_name)
                print(f"\n{answer}")
            except Exception as e:
                print(f"\n[ERROR] 追问失败: {e}")
            continue

        # 正常查询模式
        try:
            result = system.process_user_query(user_input)

            if result["success"]:
                # 询问是否保存结果
                save_choice = input("\n是否保存结果到文件？(y/n): ").strip().lower()
                if save_choice == 'y':
                    system.save_result(result)

        except Exception as e:
            print(f"\n[ERROR] 处理失败: {e}")
            import traceback
            traceback.print_exc()

    # 关闭系统
    system.close()


if __name__ == "__main__":
    interactive_mode()
