# -*- coding: utf-8 -*-
"""
GIS Operator Recommendation Pipeline

End-to-end pipeline that combines:
1. Stage A: Task -> L3 Sequence (Transformer Beam Search)
2. Stage B: L3 Sequence -> Platform Operators (Mapping)

Usage:
    from recommend_pipeline import GISOperatorRecommender

    recommender = GISOperatorRecommender(platform='QGIS')
    results = recommender.recommend(
        task_name="Create buffer zones around rivers",
        task_description="Buffer river features by 100 meters",
        task_type="Surface water"
    )
"""

import json
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Any

from gis_recommend.inference.infer_l3_candidates import L3SequenceInferencer, L3Candidate
from gis_recommend.operators.l3_to_platform_mapper import L3ToPlatformMapper, ToolChain, MappingResult


def _resolve_project_root() -> Path:
    p = Path(__file__).resolve()
    for parent in [p.parent, p.parent.parent, p.parent.parent.parent, p.parent.parent.parent.parent]:
        if (parent / "outputs").is_dir():
            return parent
    return p.parent


@dataclass
class RecommendationResult:
    """Single recommendation result"""
    rank: int                      # Ranking (1-based)
    l3_candidate: L3Candidate      # L3 sequence candidate
    l3_names: List[str]            # L3 readable names
    l3_codes: List[str]            # L3 codes
    tool_chain: ToolChain          # Platform tool chain
    overall_score: float           # Combined score

    def to_dict(self) -> Dict[str, Any]:
        return {
            'rank': self.rank,
            'l3_sequence': {
                'tokens': self.l3_candidate.tokens,
                'names': self.l3_names,
                'codes': self.l3_codes,
                'log_prob': self.l3_candidate.log_prob,
                'normalized_score': self.l3_candidate.normalized_score,
                'length': self.l3_candidate.length
            },
            'tool_chain': self.tool_chain.to_dict(),
            'overall_score': self.overall_score
        }


@dataclass
class RecommendationBatch:
    """Batch of recommendations for a task"""
    task_name: str
    task_description: str
    task_type: str
    platform: str
    recommendations: List[RecommendationResult]
    total_candidates: int

    def to_dict(self) -> Dict[str, Any]:
        return {
            'task': {
                'name': self.task_name,
                'description': self.task_description,
                'type': self.task_type
            },
            'platform': self.platform,
            'total_candidates': self.total_candidates,
            'recommendations': [r.to_dict() for r in self.recommendations]
        }


class GISOperatorRecommender:
    """GIS Operator Recommendation System"""

    def __init__(
        self,
        platform: str = "QGIS",
        beam_size: int = 10,
        max_length: int = 30,
        min_length: int = 5,
        return_top_n: int = 5,
        min_confidence: float = 0.5
    ):
        """
        Initialize the recommender

        Args:
            platform: Target platform (QGIS/GDAL/GRASS/SAGA/OTB/ALL)
            beam_size: Beam search width
            max_length: Maximum L3 sequence length
            min_length: Minimum L3 sequence length
            return_top_n: Number of recommendations to return
            min_confidence: Minimum operator mapping confidence
        """
        print("=" * 70)
        print("GIS Operator Recommender - Initializing")
        print("=" * 70)

        self.platform = platform
        self.return_top_n = return_top_n

        # Initialize Stage A: L3 Sequence Inferencer
        print("\n[Stage A] Loading L3 Sequence Inferencer...")
        self.inferencer = L3SequenceInferencer(
            beam_size=beam_size,
            max_length=max_length,
            min_length=min_length,
            return_top_n=return_top_n * 2  # Get more candidates for filtering
        )

        # Initialize Stage B: Platform Mapper
        print("\n[Stage B] Loading Platform Mapper...")
        self.mapper = L3ToPlatformMapper(
            platform=platform,
            min_confidence=min_confidence
        )

        print("\n" + "=" * 70)
        print("Recommender Ready")
        print(f"  Platform: {platform}")
        print(f"  Top-N: {return_top_n}")
        print("=" * 70)

    def recommend(
        self,
        task_name: str,
        task_description: str = "",
        task_type: str = "Unknown",
        filter_io_compatible: bool = True,
        filter_no_unknown: bool = False
    ) -> RecommendationBatch:
        """
        Generate operator recommendations for a task

        Args:
            task_name: Task name
            task_description: Task description
            task_type: Task type (from vocabulary)
            filter_io_compatible: Only return I/O compatible tool chains
            filter_no_unknown: Only return tool chains with all operators mapped

        Returns:
            RecommendationBatch: Batch of recommendations
        """
        # Stage A: Generate L3 candidates
        l3_candidates = self.inferencer.infer(
            task_name=task_name,
            task_description=task_description,
            task_type=task_type
        )

        # Stage B: Map each candidate to platform operators
        recommendations = []
        for i, candidate in enumerate(l3_candidates):
            # Skip incomplete candidates
            if not candidate.is_complete:
                continue

            # Get L3 codes and names
            l3_codes = []
            l3_names = []
            for token_id in candidate.tokens:
                l3_code = self.mapper.get_l3_code(token_id)
                if l3_code:
                    l3_codes.append(l3_code)
                    l3_info = self.mapper.get_l3_info(l3_code)
                    l3_names.append(l3_info.get('name', 'Unknown'))
                else:
                    l3_codes.append(f"UNK_{token_id}")
                    l3_names.append(f"Unknown_{token_id}")

            # Map to platform operators
            tool_chain = self.mapper.map_sequence(
                l3_tokens=candidate.tokens,
                check_io_compatibility=True,
                top_k_operators=3
            )

            # Apply filters
            if filter_io_compatible and not tool_chain.io_compatible:
                # Currently skip I/O filter as many L3 operations lack type info
                pass  # continue
            if filter_no_unknown and tool_chain.unknown_count > 0:
                continue

            # Calculate overall score
            # Combine L3 score with mapping confidence
            # L3 score is negative log prob, convert to positive scale [0,1]
            l3_score = max(0, 1.0 + candidate.normalized_score / 10)  # Normalize to ~[0,1]
            mapping_score = tool_chain.confidence_score
            # Penalize UNKNOWN mappings
            unknown_penalty = 1.0 - (tool_chain.unknown_count / max(len(candidate.tokens), 1)) * 0.5
            overall_score = l3_score * 0.3 + mapping_score * 0.4 + unknown_penalty * 0.3

            result = RecommendationResult(
                rank=len(recommendations) + 1,
                l3_candidate=candidate,
                l3_names=l3_names,
                l3_codes=l3_codes,
                tool_chain=tool_chain,
                overall_score=overall_score
            )
            recommendations.append(result)

        # Sort by overall score and take top-N
        recommendations.sort(key=lambda x: x.overall_score, reverse=True)
        recommendations = recommendations[:self.return_top_n]

        # Update ranks
        for i, rec in enumerate(recommendations):
            rec.rank = i + 1

        return RecommendationBatch(
            task_name=task_name,
            task_description=task_description,
            task_type=task_type,
            platform=self.platform,
            recommendations=recommendations,
            total_candidates=len(l3_candidates)
        )

    def recommend_and_print(
        self,
        task_name: str,
        task_description: str = "",
        task_type: str = "Unknown"
    ) -> RecommendationBatch:
        """Generate recommendations and print results"""
        print("\n" + "=" * 70)
        print("Task Information")
        print("=" * 70)
        print(f"  Name: {task_name}")
        print(f"  Description: {task_description}")
        print(f"  Type: {task_type}")
        print(f"  Platform: {self.platform}")

        batch = self.recommend(
            task_name=task_name,
            task_description=task_description,
            task_type=task_type
        )

        print("\n" + "=" * 70)
        print(f"Recommendations ({len(batch.recommendations)} / {batch.total_candidates} candidates)")
        print("=" * 70)

        for rec in batch.recommendations:
            self._print_recommendation(rec)

        return batch

    def _print_recommendation(self, rec: RecommendationResult):
        """Print a single recommendation"""
        print(f"\n[Rank {rec.rank}] Score: {rec.overall_score:.4f}")
        print("-" * 60)

        # L3 Sequence
        print(f"  L3 Sequence (len={rec.l3_candidate.length}):")
        print(f"    Codes: {' -> '.join(rec.l3_codes)}")
        print(f"    Names: {' -> '.join(rec.l3_names)}")
        print(f"    L3 Score: {rec.l3_candidate.normalized_score:.4f}")

        # Tool Chain
        tc = rec.tool_chain
        print(f"\n  Tool Chain:")
        print(f"    I/O Compatible: {'Yes' if tc.io_compatible else 'No'}")
        print(f"    Mapping Confidence: {tc.confidence_score:.4f}")
        print(f"    Unknown Steps: {tc.unknown_count}")

        # Steps with operators
        print(f"\n  Steps:")
        for i, step in enumerate(tc.steps):
            if step.is_unknown:
                print(f"    [{i+1}] {step.l3_code} ({step.l3_name}) - [No mapping]")
            elif step.operators:
                top_op = step.operators[0]
                print(f"    [{i+1}] {step.l3_code} ({step.l3_name})")
                print(f"        -> {top_op.identifier} ({top_op.platform}, conf={top_op.confidence:.2f})")


def main():
    """Test the recommendation pipeline"""
    print("=" * 70)
    print("GIS Operator Recommendation Pipeline Test")
    print("=" * 70)

    # Create recommender
    recommender = GISOperatorRecommender(
        platform='QGIS',
        beam_size=10,
        max_length=25,
        min_length=5,
        return_top_n=3
    )

    # Test cases
    test_cases = [
        {
            "task_name": "Land cover classification",
            "task_description": "Classify land use and land cover from satellite imagery using machine learning",
            "task_type": "Land use/land cover"
        },
        {
            "task_name": "NDVI calculation",
            "task_description": "Calculate normalized difference vegetation index from Landsat bands",
            "task_type": "Vegetation"
        },
        {
            "task_name": "Flood risk mapping",
            "task_description": "Create flood risk zones based on elevation and proximity to rivers",
            "task_type": "Surface water"
        }
    ]

    for case in test_cases:
        batch = recommender.recommend_and_print(**case)

        # Save results
        output_path = _resolve_project_root() / "outputs" / f"recommendation_{case['task_name'].replace(' ', '_')[:20]}.json"
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(batch.to_dict(), f, indent=2, ensure_ascii=False)
        print(f"\n  Results saved to: {output_path}")

    print("\n" + "=" * 70)
    print("Pipeline Test Complete")
    print("=" * 70)


if __name__ == "__main__":
    main()
