"""
stage2_completion_pipeline.py

阶段2完整流水线：从骨架链到完整QGIS工具链

功能：
1. 加载Stage A生成的骨架链
2. 对每个unknown占位符进行补全
3. 生成最终的完整QGIS工具链
4. 验证和评估补全质量
"""

import json
from typing import List, Dict, Optional
from pathlib import Path
from dataclasses import dataclass, field
from gis_recommend.operators.unknown_completer import UnknownCompleter, CompletionResult


@dataclass
class CompletedChain:
    """补全后的完整链"""
    original_rank: int
    original_score: float
    qgis_sequence: List[str]  # 补全后的QGIS序列
    l3_sequence: List[str]
    completion_results: List[CompletionResult]
    final_score: float
    completion_rate: float  # 补全成功率
    avg_completion_confidence: float  # 平均补全置信度
    is_fully_completed: bool  # 是否完全补全


class Stage2Pipeline:
    """
    阶段2流水线：Unknown补全

    输入：Stage A的骨架链（含unknown占位符）
    输出：完整的QGIS工具链
    """

    def __init__(
        self,
        completer: UnknownCompleter,
        min_completion_rate: float = 0.5  # 最小补全率
    ):
        """
        初始化流水线

        参数:
            completer: Unknown补全器
            min_completion_rate: 最小补全率（低于此值的链将被过滤）
        """
        self.completer = completer
        self.min_completion_rate = min_completion_rate

    def load_skeleton_chains(self, input_path: str) -> Dict:
        """
        加载Stage A生成的骨架链

        参数:
            input_path: 输入文件路径

        返回:
            骨架链数据
        """
        input_path = Path(input_path)

        if not input_path.exists():
            raise FileNotFoundError(f"Skeleton chains file not found: {input_path}")

        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        print(f"[LOAD] Loaded skeleton chains from: {input_path}")
        print(f"  - Stage: {data.get('stage')}")
        print(f"  - Candidates: {len(data.get('candidates', []))}")

        return data

    def complete_candidate(self, candidate: Dict) -> CompletedChain:
        """
        补全单个候选链

        参数:
            candidate: 候选链数据

        返回:
            CompletedChain对象
        """
        rank = candidate['rank']
        original_score = candidate['score']
        qgis_sequence = candidate['qgis_sequence'].copy()
        l3_sequence = candidate['l3_sequence']
        completion_context = candidate['completion_context']

        print(f"\n{'='*80}")
        print(f"Completing Candidate {rank}")
        print(f"{'='*80}")
        print(f"Original Score: {original_score:.2f}")
        print(f"Unknown Count: {completion_context['unknown_count']}")

        completion_results = []

        # 对每个unknown进行补全
        for task in completion_context['completion_tasks']:
            result = self.completer.complete_unknown(task)
            completion_results.append(result)

            # 如果补全成功，替换unknown占位符
            if result.is_completed:
                position = result.position
                qgis_sequence[position] = result.selected_operator

        # 计算补全统计
        completed_count = sum(1 for r in completion_results if r.is_completed)
        total_unknown = len(completion_results)
        completion_rate = completed_count / total_unknown if total_unknown > 0 else 1.0

        # 计算平均补全置信度
        completed_results = [r for r in completion_results if r.is_completed]
        avg_completion_confidence = (
            sum(r.confidence for r in completed_results) / len(completed_results)
            if completed_results else 0.0
        )

        # 计算最终分数（原始分数 + 补全奖励 - 未补全惩罚）
        completion_bonus = completed_count * 0.5
        incompletion_penalty = (total_unknown - completed_count) * 1.0
        final_score = original_score + completion_bonus - incompletion_penalty

        is_fully_completed = (completion_rate == 1.0)

        print(f"\n[Summary]")
        print(f"  Completion Rate: {completion_rate:.1%} ({completed_count}/{total_unknown})")
        print(f"  Avg Completion Confidence: {avg_completion_confidence:.3f}")
        print(f"  Final Score: {final_score:.2f}")
        print(f"  Fully Completed: {is_fully_completed}")

        return CompletedChain(
            original_rank=rank,
            original_score=original_score,
            qgis_sequence=qgis_sequence,
            l3_sequence=l3_sequence,
            completion_results=completion_results,
            final_score=final_score,
            completion_rate=completion_rate,
            avg_completion_confidence=avg_completion_confidence,
            is_fully_completed=is_fully_completed
        )

    def complete_all_candidates(
        self,
        skeleton_data: Dict
    ) -> List[CompletedChain]:
        """
        补全所有候选链

        参数:
            skeleton_data: 骨架链数据

        返回:
            补全后的链列表
        """
        candidates = skeleton_data.get('candidates', [])

        print(f"\n{'='*80}")
        print(f"STAGE 2: Complete All Candidates")
        print(f"{'='*80}")
        print(f"Total Candidates: {len(candidates)}")

        completed_chains = []

        for candidate in candidates:
            completed_chain = self.complete_candidate(candidate)
            completed_chains.append(completed_chain)

        # 过滤低补全率的链
        filtered_chains = [
            chain for chain in completed_chains
            if chain.completion_rate >= self.min_completion_rate
        ]

        print(f"\n{'='*80}")
        print(f"Completion Summary")
        print(f"{'='*80}")
        print(f"Total Chains: {len(completed_chains)}")
        print(f"Fully Completed: {sum(1 for c in completed_chains if c.is_fully_completed)}")
        print(f"Partially Completed: {sum(1 for c in completed_chains if not c.is_fully_completed and c.completion_rate > 0)}")
        print(f"Failed: {sum(1 for c in completed_chains if c.completion_rate == 0)}")
        print(f"After Filtering (>={self.min_completion_rate:.0%}): {len(filtered_chains)}")

        # 按最终分数排序
        filtered_chains.sort(key=lambda x: x.final_score, reverse=True)

        return filtered_chains

    def export_completed_chains(
        self,
        completed_chains: List[CompletedChain],
        output_path: str
    ):
        """
        导出补全后的链

        参数:
            completed_chains: 补全后的链列表
            output_path: 输出文件路径
        """
        export_data = {
            "stage": "B",
            "description": "Completed QGIS tool chains",
            "chains": []
        }

        for i, chain in enumerate(completed_chains, 1):
            chain_data = {
                "rank": i,
                "original_rank": chain.original_rank,
                "original_score": chain.original_score,
                "final_score": chain.final_score,
                "completion_rate": chain.completion_rate,
                "avg_completion_confidence": chain.avg_completion_confidence,
                "is_fully_completed": chain.is_fully_completed,
                "qgis_sequence": chain.qgis_sequence,
                "l3_sequence": chain.l3_sequence,
                "completion_details": [
                    {
                        "position": r.position,
                        "l3_code": r.l3_code,
                        "unknown_type": r.unknown_type,
                        "is_completed": r.is_completed,
                        "selected_operator": r.selected_operator,
                        "confidence": r.confidence,
                        "selection_reason": r.selection_reason,
                        "num_candidates": len(r.candidates)
                    }
                    for r in chain.completion_results
                ]
            }

            export_data["chains"].append(chain_data)

        # 保存到文件
        output_path = Path(output_path)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)

        print(f"\n[EXPORT] Saved to: {output_path}")
        print(f"  - Completed Chains: {len(completed_chains)}")

    def print_chain_details(self, chain: CompletedChain):
        """打印链的详细信息"""
        print(f"\n{'='*80}")
        print(f"Completed Chain Details (Rank {chain.original_rank})")
        print(f"{'='*80}")
        print(f"Original Score: {chain.original_score:.2f}")
        print(f"Final Score: {chain.final_score:.2f}")
        print(f"Completion Rate: {chain.completion_rate:.1%}")
        print(f"Avg Completion Confidence: {chain.avg_completion_confidence:.3f}")
        print(f"Fully Completed: {chain.is_fully_completed}")

        print(f"\nQGIS Operator Sequence:")
        for i, (qgis_op, l3_code) in enumerate(zip(chain.qgis_sequence, chain.l3_sequence), 1):
            # 检查是否是补全的算子
            completion_result = next(
                (r for r in chain.completion_results if r.position == i-1),
                None
            )

            if completion_result:
                status = "[COMPLETED]" if completion_result.is_completed else "[FAILED]"
                print(f"  {i}. {qgis_op} {status}")
                print(f"     <- {l3_code} ({completion_result.unknown_type})")
                if completion_result.is_completed:
                    print(f"     Confidence: {completion_result.confidence:.3f}")
            else:
                print(f"  {i}. {qgis_op}")
                print(f"     <- {l3_code}")

        print(f"{'='*80}\n")


# 使用示例
if __name__ == "__main__":
    # 初始化补全器
    completer = UnknownCompleter(
        min_confidence=0.25,  # 降低阈值以便测试
        top_k_candidates=5
    )

    # 初始化Stage 2流水线
    pipeline = Stage2Pipeline(
        completer=completer,
        min_completion_rate=0.0  # 测试时不过滤
    )

    # 加载Stage A的骨架链
    skeleton_data = pipeline.load_skeleton_chains(
        "outputs/stage_a_skeleton_chains.json"
    )

    # 补全所有候选链
    completed_chains = pipeline.complete_all_candidates(skeleton_data)

    # 显示第一条链的详细信息
    if completed_chains:
        pipeline.print_chain_details(completed_chains[0])

    # 导出补全后的链
    pipeline.export_completed_chains(
        completed_chains=completed_chains,
        output_path="outputs/stage_b_completed_chains.json"
    )

    print("\n" + "="*80)
    print("Stage 2 Complete!")
    print("="*80)
    print("\nNext Steps:")
    print("  1. Review completed chains in outputs/stage_b_completed_chains.json")
    print("  2. Validate operator sequences")
    print("  3. Test execution on QGIS platform")
