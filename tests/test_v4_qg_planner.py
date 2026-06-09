from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from scripts.run_v4_qg_planner import (  # noqa: E402
    PlannerWeights,
    default_paths,
    forbidden_pattern_scan,
    _load_length_stats,
    merge_candidate_pool,
    rerank_candidates,
    set_coverage_features,
    soft_transition_score,
)


class FakeUsabilityEvaluator:
    def __init__(self, by_tokens: dict[tuple[int, ...], SimpleNamespace]) -> None:
        self.by_tokens = by_tokens

    def evaluate(self, tokens, task: str) -> SimpleNamespace:
        return self.by_tokens[tuple(tokens)]


class V4QGPlannerTests(unittest.TestCase):
    def test_default_paths_are_quality_gate_scoped(self) -> None:
        paths = default_paths()

        self.assertEqual(paths["data"].name, "labeled_workflows_l3_v4_quality_gate.json")
        self.assertEqual(paths["splits"].name, "dataset_splits_v4_quality_gate.json")
        self.assertEqual(paths["task_vocab"].name, "task_type_vocabulary_v4_quality_gate.json")
        self.assertEqual(paths["checkpoint"].parent.name, "transformer_checkpoints_v4_6_quality_gate")
        self.assertEqual(paths["set_predictor_checkpoint"].parent.name, "set_predictor_checkpoints_v3_quality_gate_v4_6")
        self.assertEqual(paths["length_stats"].name, "task_type_length_stats.json")
        self.assertIn("step8_quality_gate", str(paths["length_stats"]))
        self.assertIn("step8_quality_gate", str(paths["data"]))

    def test_load_length_stats_uses_explicit_quality_gate_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            stats_path = Path(tmp) / "task_type_length_stats.json"
            stats_path.write_text(
                json.dumps({"by_task_type": {"Flood": {"median": 13}}}),
                encoding="utf-8",
            )

            stats = _load_length_stats(stats_path)

        self.assertEqual(stats["Flood"]["median"], 13)

    def test_soft_transition_scores_seen_edges_without_banning_unseen_edges(self) -> None:
        matrix = {
            "allowed_next": {
                "1": {"2": 5},
                "2": {"3": 3},
            }
        }

        seen = soft_transition_score([1, 2, 3], matrix)
        partly_unseen = soft_transition_score([1, 4, 3], matrix)

        self.assertGreater(seen, partly_unseen)
        self.assertGreater(partly_unseen, 0.0)
        self.assertLessEqual(seen, 1.0)

    def test_set_coverage_features_reward_predicted_operator_overlap(self) -> None:
        features = set_coverage_features(
            candidate_tokens=[1, 2, 9],
            token_scores={1: 0.9, 2: 0.8, 3: 0.75, 9: 0.1},
            threshold=0.7,
        )

        self.assertEqual(features["predicted_set_size"], 3)
        self.assertEqual(features["overlap_count"], 2)
        self.assertAlmostEqual(features["set_recall"], 2 / 3)
        self.assertGreater(features["set_coverage_score"], 0.0)

    def test_merge_candidate_pool_dedupes_sequences_and_preserves_sources(self) -> None:
        merged = merge_candidate_pool(
            [
                {"tokens": [1, 2, 3], "source": "retrieval", "retrieval_score": 0.8},
                {"tokens": [1, 2, 3], "source": "v4_ar", "model_score": 0.6},
                {"tokens": [2, 3], "source": "retrieval", "retrieval_score": 0.2},
            ]
        )

        self.assertEqual(len(merged), 2)
        first = next(row for row in merged if row["tokens"] == [1, 2, 3])
        self.assertEqual(first["sources"], ["retrieval", "v4_ar"])
        self.assertEqual(first["retrieval_score"], 0.8)
        self.assertEqual(first["model_score"], 0.6)

    def test_rerank_prefers_usable_set_covering_candidate_over_high_retrieval_bad_candidate(self) -> None:
        bad = SimpleNamespace(
            required_step_coverage=0.2,
            executable_qgis_mapping_rate=0.4,
            workflow_logic_consistency=0.2,
            harmful_step_rate=0.8,
            redundancy_rate=0.3,
            missing_critical_step_rate=0.8,
            usability_score=0.2,
            usable=False,
            forbidden_patterns=["FP02:export_before_processing"],
            failure_taxonomy=["harmful_steps"],
        )
        good = SimpleNamespace(
            required_step_coverage=1.0,
            executable_qgis_mapping_rate=1.0,
            workflow_logic_consistency=0.95,
            harmful_step_rate=0.0,
            redundancy_rate=0.0,
            missing_critical_step_rate=0.0,
            usability_score=0.95,
            usable=True,
            forbidden_patterns=[],
            failure_taxonomy=["usable_no_failure"],
        )
        evaluator = FakeUsabilityEvaluator({(9, 9): bad, (1, 2, 3): good})

        ranked = rerank_candidates(
            candidates=[
                {"tokens": [9, 9], "source": "retrieval", "retrieval_score": 1.0},
                {"tokens": [1, 2, 3], "source": "retrieval", "retrieval_score": 0.4},
            ],
            evaluator=evaluator,
            task="Vegetation",
            set_token_scores={1: 0.9, 2: 0.85, 3: 0.8},
            transition_matrix={"allowed_next": {"1": {"2": 1}, "2": {"3": 1}}},
            weights=PlannerWeights(),
        )

        self.assertEqual(ranked[0]["tokens"], [1, 2, 3])
        self.assertTrue(ranked[0]["usability"]["usable"])
        self.assertGreater(ranked[0]["final_score"], ranked[1]["final_score"])

    def test_rerank_prioritizes_rule_usable_candidate_over_critical_failure(self) -> None:
        critical_failure = SimpleNamespace(
            required_step_coverage=1.0,
            executable_qgis_mapping_rate=1.0,
            workflow_logic_consistency=1.0,
            harmful_step_rate=0.0,
            redundancy_rate=0.0,
            missing_critical_step_rate=0.0,
            usability_score=0.98,
            usable=False,
            forbidden_patterns=["FP02:export_before_processing"],
            failure_taxonomy=["FP02:export_before_processing"],
        )
        usable = SimpleNamespace(
            required_step_coverage=0.75,
            executable_qgis_mapping_rate=0.8,
            workflow_logic_consistency=0.8,
            harmful_step_rate=0.0,
            redundancy_rate=0.0,
            missing_critical_step_rate=0.1,
            usability_score=0.72,
            usable=True,
            forbidden_patterns=[],
            failure_taxonomy=["usable_no_failure"],
        )
        evaluator = FakeUsabilityEvaluator({(9, 9, 9): critical_failure, (1, 2, 3): usable})

        ranked = rerank_candidates(
            candidates=[
                {"tokens": [9, 9, 9], "source": "retrieval", "retrieval_score": 1.0},
                {"tokens": [1, 2, 3], "source": "retrieval", "retrieval_score": 0.2},
            ],
            evaluator=evaluator,
            task="Export",
            set_token_scores={1: 0.8, 2: 0.8, 3: 0.8},
            transition_matrix={},
            weights=PlannerWeights(),
        )

        self.assertEqual(ranked[0]["tokens"], [1, 2, 3])
        self.assertTrue(ranked[0]["usability"]["usable"])

    def test_forbidden_pattern_scan_reports_clean_files(self) -> None:
        scan = forbidden_pattern_scan([Path("tests") / "test_v4_qg_planner.py"])

        self.assertEqual(scan["status"], "pass")
        self.assertEqual(scan["match_count"], 0)


if __name__ == "__main__":
    unittest.main()
