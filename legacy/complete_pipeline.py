"""
完整的端到端流程：自然语言任务 → L3序列 → QGIS算子链 → 问答支持

使用示例：
python complete_pipeline.py --task_desc "在某个点附近100米的范围内选定一个点"
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Dict, Any

import torch
from transformers import BertTokenizer

# 导入任务→L3模型相关
from transformer_config import OUTPUT_DIR, DEVICE, SPECIAL_TOKENS, VOCAB_SIZE
from task_conditioned_transformer_model_v3 import TaskConditionedL3TransformerModelV3
from task_text_processor import TaskVocabularyBuilder
from infer_l3_candidates import L3SequenceInferencer

# 导入L3→QGIS相关
from qgis_candidate_generator import QGISCandidateGenerator
from qgis_operator_qa import QGISOperatorQA


class CompletePipeline:
    """完整的任务处理流程"""

    def __init__(
        self,
        model_checkpoint: str,
        llm_api_key: str,
        neo4j_uri: str = "bolt://localhost:7687",
        neo4j_username: str = "neo4j",
        neo4j_password: str = "12345678"
    ):
        """
        初始化完整流程

        参数:
            model_checkpoint: 任务条件化Transformer模型检查点路径
            llm_api_key: LLM API密钥（阿里云通义千问）
            neo4j_uri: Neo4j连接URI
            neo4j_username: Neo4j用户名
            neo4j_password: Neo4j密码
        """
        self.model_checkpoint = Path(model_checkpoint)
        self.llm_api_key = llm_api_key
        self.neo4j_uri = neo4j_uri
        self.neo4j_username = neo4j_username
        self.neo4j_password = neo4j_password

        print("="*70)
        print("初始化完整流程系统")
        print("="*70)

        # 1. 加载任务→L3模型
        print("\n[1/3] 加载任务条件化Transformer模型...")
        self._load_task_to_l3_model()

        # 2. 初始化L3→QGIS生成器
        print("\n[2/3] 初始化QGIS候选生成器...")
        self.qgis_generator = QGISCandidateGenerator(
            beam_width=5,
            max_unknown_ratio=0.3,
            max_unknown_count=3,
            critical_positions={'start'}
        )

        # 3. 初始化问答系统
        print("\n[3/3] 初始化问答系统...")
        self.qa_system = QGISOperatorQA(
            llm_api_key=llm_api_key,
            neo4j_uri=neo4j_uri,
            neo4j_username=neo4j_username,
            neo4j_password=neo4j_password
        )

        print("\n[OK] 系统初始化完成！\n")

    def _load_task_to_l3_model(self):
        """加载任务→L3序列的模型"""
        # 加载任务类型词汇表
        vocab_path = OUTPUT_DIR / "task_type_vocabulary.json"
        with open(vocab_path, "r", encoding="utf-8") as f:
            vocab = json.load(f)

        self.task_vocab_builder = TaskVocabularyBuilder()
        if hasattr(self.task_vocab_builder, "task_type_to_id"):
            self.task_vocab_builder.task_type_to_id = vocab["task_type_to_id"]
        if hasattr(self.task_vocab_builder, "type_to_id"):
            self.task_vocab_builder.type_to_id = vocab["task_type_to_id"]

        id_to = {int(k): v for k, v in vocab["id_to_task_type"].items()}
        if hasattr(self.task_vocab_builder, "id_to_task_type"):
            self.task_vocab_builder.id_to_task_type = id_to
        if hasattr(self.task_vocab_builder, "id_to_type"):
            self.task_vocab_builder.id_to_type = id_to

        # 加载BERT tokenizer
        self.tokenizer = BertTokenizer.from_pretrained("bert-base-chinese")

        # 加载模型
        self.task_model = TaskConditionedL3TransformerModelV3(
            vocab_size=VOCAB_SIZE + len(SPECIAL_TOKENS),  # TOTAL_VOCAB_SIZE = 354
            d_model=256,
            nhead=8,
            num_layers=6,
            dim_feedforward=1024,
            dropout=0.1,
            max_seq_len=100,
            task_type_vocab_size=len(self.task_vocab_builder.task_type_to_id),
            max_memory_tokens=16,
            use_l3_embeddings=True,
            l3_embeddings_path=OUTPUT_DIR / "l3_embeddings.pt",
            freeze_bert=True,
            embedding_dropout=0.1
        ).to(DEVICE)

        # 加载检查点
        checkpoint = torch.load(self.model_checkpoint, map_location=DEVICE)
        if "model_state_dict" in checkpoint:
            self.task_model.load_state_dict(checkpoint["model_state_dict"], strict=False)
        else:
            self.task_model.load_state_dict(checkpoint, strict=False)

        self.task_model.eval()

        # 初始化推理器
        self.l3_inferencer = L3SequenceInferencer(
            model=self.task_model,
            tokenizer=self.tokenizer,
            task_vocab_builder=self.task_vocab_builder,
            device=DEVICE
        )

        print("   [OK] 模型加载成功")

    def process_task(
        self,
        task_desc: str,
        task_type: str = "Spatial Analysis",
        task_name: str = None,
        num_l3_candidates: int = 3,
        num_qgis_candidates: int = 5,
        verbose: bool = True
    ) -> Dict[str, Any]:
        """
        处理完整任务流程

        参数:
            task_desc: 任务描述（自然语言）
            task_type: 任务类型（可选）
            task_name: 任务名称（可选）
            num_l3_candidates: 生成的L3序列候选数量
            num_qgis_candidates: 生成的QGIS链候选数量
            verbose: 是否打印详细信息

        返回:
            包含所有结果的字典
        """
        if verbose:
            print("="*70)
            print("开始处理任务")
            print("="*70)
            print(f"\n任务描述: {task_desc}")
            print(f"任务类型: {task_type}")
            if task_name:
                print(f"任务名称: {task_name}")

        # 阶段1：生成L3序列
        if verbose:
            print("\n" + "-"*70)
            print("阶段1：从任务描述生成L3原语序列")
            print("-"*70)

        l3_sequences = self._generate_l3_sequences(
            task_desc=task_desc,
            task_type=task_type,
            task_name=task_name or task_desc[:30],
            num_candidates=num_l3_candidates,
            verbose=verbose
        )

        if not l3_sequences:
            print("[ERROR] 无法生成L3序列")
            return {"success": False, "error": "L3 generation failed"}

        # 使用第一个L3序列（最佳候选）
        best_l3_sequence = l3_sequences[0]

        # 阶段2：生成QGIS算子链
        if verbose:
            print("\n" + "-"*70)
            print("阶段2：从L3序列生成QGIS算子链")
            print("-"*70)

        qgis_chains = self._generate_qgis_chains(
            l3_sequence=best_l3_sequence,
            num_candidates=num_qgis_candidates,
            verbose=verbose
        )

        if not qgis_chains:
            print("[ERROR] 无法生成QGIS算子链")
            return {"success": False, "error": "QGIS generation failed"}

        # 阶段3：生成问答和解释
        if verbose:
            print("\n" + "-"*70)
            print("阶段3：生成算子链解释和使用指导")
            print("-"*70)

        best_chain = qgis_chains[0]
        explanations = self._generate_explanations(
            qgis_chain=best_chain.qgis_sequence,
            verbose=verbose
        )

        # 汇总结果
        result = {
            "success": True,
            "task_description": task_desc,
            "task_type": task_type,
            "l3_sequences": l3_sequences,
            "best_l3_sequence": best_l3_sequence,
            "qgis_chains": [
                {
                    "chain": chain.qgis_sequence,
                    "score": chain.score,
                    "confidence": chain.confidence,
                    "unknown_count": chain.unknown_count
                }
                for chain in qgis_chains
            ],
            "best_qgis_chain": best_chain.qgis_sequence,
            "explanations": explanations
        }

        if verbose:
            self._print_summary(result)

        return result

    def _generate_l3_sequences(
        self,
        task_desc: str,
        task_type: str,
        task_name: str,
        num_candidates: int,
        verbose: bool
    ) -> List[List[str]]:
        """生成L3序列候选"""
        try:
            # 使用推理器生成L3序列
            results = self.l3_inferencer.infer_with_transition_beam(
                task_type=task_type,
                task_name=task_name,
                task_desc=task_desc,
                max_len=60,
                beam_size=num_candidates,
                decode_min_len=5,
                enable_transition=True
            )

            l3_sequences = []
            for i, result in enumerate(results[:num_candidates], 1):
                l3_seq = result["l3_sequence"]
                l3_sequences.append(l3_seq)

                if verbose:
                    print(f"\nL3候选 {i}:")
                    print(f"  序列: {' → '.join(l3_seq)}")
                    print(f"  长度: {len(l3_seq)}")

            return l3_sequences

        except Exception as e:
            print(f"[ERROR] L3序列生成失败: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _generate_qgis_chains(
        self,
        l3_sequence: List[str],
        num_candidates: int,
        verbose: bool
    ) -> List[Any]:
        """生成QGIS算子链候选"""
        try:
            candidates = self.qgis_generator.generate_candidates(
                l3_sequence=l3_sequence,
                top_k=num_candidates
            )

            if verbose:
                print(f"\n生成了 {len(candidates)} 条QGIS算子链候选:")
                for i, cand in enumerate(candidates, 1):
                    print(f"\nQGIS候选 {i}:")
                    print(f"  链: {' → '.join(cand.qgis_sequence)}")
                    print(f"  评分: {cand.score:.4f}")
                    print(f"  置信度: {cand.confidence:.4f}")
                    print(f"  Unknown数量: {cand.unknown_count}")

            return candidates

        except Exception as e:
            print(f"[ERROR] QGIS链生成失败: {e}")
            import traceback
            traceback.print_exc()
            return []

    def _generate_explanations(
        self,
        qgis_chain: List[str],
        verbose: bool
    ) -> Dict[str, str]:
        """生成算子链的解释和说明"""
        explanations = {}

        try:
            # 1. 解释整条链
            if verbose:
                print("\n生成算子链整体解释...")

            chain_explanation = self.qa_system.explain_operator_chain(qgis_chain)
            explanations["chain_explanation"] = chain_explanation

            if verbose:
                print("[OK] 链解释已生成")

            # 2. 解释第一个非UNKNOWN算子
            for op in qgis_chain:
                if not op.startswith("UNKNOWN"):
                    if verbose:
                        print(f"\n生成算子 '{op}' 的详细说明...")

                    op_explanation = self.qa_system.answer_question(
                        operator_name=op,
                        question="这个算子是做什么的？有哪些参数？如何使用？"
                    )
                    explanations[f"operator_{op}"] = op_explanation

                    if verbose:
                        print(f"[OK] 算子 '{op}' 的说明已生成")

                    break  # 只解释第一个算子，避免太慢

        except Exception as e:
            print(f"[WARNING] 解释生成部分失败: {e}")

        return explanations

    def _print_summary(self, result: Dict[str, Any]):
        """打印结果摘要"""
        print("\n" + "="*70)
        print("处理结果摘要")
        print("="*70)

        print(f"\n任务描述: {result['task_description']}")
        print(f"\n最佳L3序列: {' → '.join(result['best_l3_sequence'])}")
        print(f"\n最佳QGIS算子链: {' → '.join(result['best_qgis_chain'])}")

        best_chain_info = result['qgis_chains'][0]
        print(f"  - 评分: {best_chain_info['score']:.4f}")
        print(f"  - 置信度: {best_chain_info['confidence']:.4f}")
        print(f"  - Unknown数量: {best_chain_info['unknown_count']}")

        print(f"\n生成了 {len(result['qgis_chains'])} 条候选链")
        print(f"生成了 {len(result['explanations'])} 个解释")

        print("\n" + "="*70)

    def save_results(self, result: Dict[str, Any], output_dir: str = "outputs"):
        """保存结果到文件"""
        import os
        os.makedirs(output_dir, exist_ok=True)

        # 保存JSON结果
        json_path = os.path.join(output_dir, "pipeline_result.json")
        with open(json_path, 'w', encoding='utf-8') as f:
            # 移除不能序列化的部分
            save_result = {
                "task_description": result["task_description"],
                "task_type": result["task_type"],
                "best_l3_sequence": result["best_l3_sequence"],
                "best_qgis_chain": result["best_qgis_chain"],
                "qgis_chains": result["qgis_chains"]
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
        if hasattr(self, 'qa_system'):
            self.qa_system.close()


def main():
    parser = argparse.ArgumentParser(description="完整的任务处理流程")
    parser.add_argument("--task_desc", type=str, required=True, help="任务描述（自然语言）")
    parser.add_argument("--task_type", type=str, default="Spatial Analysis", help="任务类型")
    parser.add_argument("--task_name", type=str, default=None, help="任务名称")
    parser.add_argument("--model_checkpoint", type=str,
                        default="outputs/task_conditioned_checkpoints_v3_7_final/best_model.pth",
                        help="模型检查点路径")
    parser.add_argument("--llm_api_key", type=str,
                        default="sk-6d6a3478844243979fd29431ce31a841",
                        help="LLM API密钥")
    parser.add_argument("--neo4j_uri", type=str, default="bolt://localhost:7687", help="Neo4j URI")
    parser.add_argument("--neo4j_user", type=str, default="neo4j", help="Neo4j用户名")
    parser.add_argument("--neo4j_password", type=str, default="12345678", help="Neo4j密码")
    parser.add_argument("--num_l3_candidates", type=int, default=3, help="L3序列候选数量")
    parser.add_argument("--num_qgis_candidates", type=int, default=5, help="QGIS链候选数量")
    parser.add_argument("--save", action="store_true", help="保存结果到文件")

    args = parser.parse_args()

    # 初始化流程
    pipeline = CompletePipeline(
        model_checkpoint=args.model_checkpoint,
        llm_api_key=args.llm_api_key,
        neo4j_uri=args.neo4j_uri,
        neo4j_username=args.neo4j_user,
        neo4j_password=args.neo4j_password
    )

    # 处理任务
    result = pipeline.process_task(
        task_desc=args.task_desc,
        task_type=args.task_type,
        task_name=args.task_name,
        num_l3_candidates=args.num_l3_candidates,
        num_qgis_candidates=args.num_qgis_candidates,
        verbose=True
    )

    # 保存结果
    if args.save and result["success"]:
        pipeline.save_results(result)

    # 关闭连接
    pipeline.close()

    sys.exit(0 if result["success"] else 1)


if __name__ == "__main__":
    main()
