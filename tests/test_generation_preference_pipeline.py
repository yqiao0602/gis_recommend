from __future__ import annotations

import json
import math
import tempfile
import unittest
from pathlib import Path

import torch

from scripts.build_generation_preferences import build_preference_pairs, write_jsonl
from scripts.evaluate_execution_aware_selector import _select_workflow_split
from scripts.train_v4_6_preference import (
    compute_dpo_loss,
    prepare_candidate_sequence,
    sequence_mean_logprob_from_logits,
)


class GenerationPreferencePipelineTests(unittest.TestCase):
    def test_select_workflow_split_returns_requested_indices(self) -> None:
        workflows = [{"id": i} for i in range(6)]
        splits = {
            "train_indices": [0, 2, 4],
            "val_indices": [1, 3],
            "test_indices": [5],
        }

        selected, indices = _select_workflow_split(workflows, splits, "val")

        self.assertEqual(indices, [1, 3])
        self.assertEqual([wf["id"] for wf in selected], [1, 3])

    def test_build_preference_pairs_uses_beam_candidates_with_reward_margin(self) -> None:
        report = {
            "per_sample": [
                {
                    "sample_index": 11,
                    "task_type": "Vegetation",
                    "task_metadata": {
                        "task_name": "NDVI",
                        "task_description": "compute vegetation index",
                    },
                    "pool_candidates": [
                        {
                            "source": "beam",
                            "tokens": [1, 2, 3],
                            "usable": True,
                            "usability_score": 0.92,
                            "features": {"qgis_mapping_rate": 1.0},
                        },
                        {
                            "source": "beam",
                            "tokens": [1, 1, 1],
                            "usable": False,
                            "usability_score": 0.20,
                            "features": {"qgis_mapping_rate": 0.33},
                        },
                        {
                            "source": "retrieval",
                            "tokens": [4, 5, 6],
                            "usable": False,
                            "usability_score": 0.01,
                        },
                    ],
                }
            ]
        }

        pairs = build_preference_pairs(report, source="beam", min_reward_margin=0.15)

        self.assertEqual(len(pairs), 1)
        pair = pairs[0]
        self.assertEqual(pair["sample_index"], 11)
        self.assertEqual(pair["task_type"], "Vegetation")
        self.assertEqual(pair["task_name"], "NDVI")
        self.assertEqual(pair["pos_tokens"], [1, 2, 3])
        self.assertEqual(pair["neg_tokens"], [1, 1, 1])
        self.assertGreaterEqual(pair["reward_margin"], 0.15)

    def test_quality_reward_prefers_clean_usable_over_redundant_usable(self) -> None:
        report = {
            "per_sample": [
                {
                    "sample_index": 12,
                    "task_type": "Classification",
                    "pool_candidates": [
                        {
                            "source": "beam",
                            "tokens": [1, 2, 3],
                            "usable": True,
                            "usability_score": 0.90,
                            "failure_taxonomy": [],
                            "features": {
                                "qgis_mapping_rate": 1.0,
                                "transition_validity": 1.0,
                                "length_bucket_fit": 1.0,
                                "repetition_rate": 0.0,
                            },
                        },
                        {
                            "source": "beam",
                            "tokens": [1, 2, 1, 1],
                            "usable": True,
                            "usability_score": 0.90,
                            "failure_taxonomy": ["FP04:consecutive_duplicate"],
                            "features": {
                                "qgis_mapping_rate": 1.0,
                                "transition_validity": 1.0,
                                "length_bucket_fit": 1.0,
                                "repetition_rate": 0.5,
                            },
                        },
                    ],
                }
            ]
        }

        pairs = build_preference_pairs(
            report,
            source="beam",
            min_reward_margin=0.10,
            reward_mode="quality",
        )

        self.assertEqual(len(pairs), 1)
        pair = pairs[0]
        self.assertEqual(pair["reward_mode"], "quality")
        self.assertEqual(pair["pos_tokens"], [1, 2, 3])
        self.assertEqual(pair["neg_tokens"], [1, 2, 1, 1])
        self.assertLess(pair["pos_quality_penalty"], pair["neg_quality_penalty"])

    def test_quality_reward_penalizes_train_apply_loop_with_token_names(self) -> None:
        report = {
            "per_sample": [
                {
                    "sample_index": 13,
                    "task_type": "Classification",
                    "pool_candidates": [
                        {
                            "source": "beam",
                            "tokens": [1, 2],
                            "usable": True,
                            "usability_score": 0.90,
                            "features": {"qgis_mapping_rate": 1.0, "transition_validity": 1.0},
                        },
                        {
                            "source": "beam",
                            "tokens": [1, 2, 3],
                            "usable": True,
                            "usability_score": 0.90,
                            "features": {"qgis_mapping_rate": 1.0, "transition_validity": 1.0},
                        },
                    ],
                }
            ]
        }
        token_names = {
            1: "Train Random Forest Classifier",
            2: "Apply Classifier",
            3: "Train Random Forest Classifier",
        }

        pairs = build_preference_pairs(
            report,
            source="beam",
            min_reward_margin=0.10,
            reward_mode="quality",
            token_names=token_names,
        )

        self.assertEqual(len(pairs), 1)
        self.assertEqual(pairs[0]["pos_tokens"], [1, 2])
        self.assertEqual(pairs[0]["neg_tokens"], [1, 2, 3])

    def test_quality_reward_does_not_penalize_sample_train_apply(self) -> None:
        report = {
            "per_sample": [
                {
                    "sample_index": 14,
                    "task_type": "Classification",
                    "pool_candidates": [
                        {
                            "source": "beam",
                            "tokens": [1, 2],
                            "usable": True,
                            "usability_score": 0.90,
                            "features": {"qgis_mapping_rate": 1.0, "transition_validity": 1.0},
                        },
                        {
                            "source": "beam",
                            "tokens": [1, 2, 3],
                            "usable": True,
                            "usability_score": 0.90,
                            "features": {"qgis_mapping_rate": 1.0, "transition_validity": 1.0},
                        },
                    ],
                }
            ]
        }
        token_names = {
            1: "Region-based Sample Extraction",
            2: "Train Random Forest Classifier",
            3: "Apply Classifier to Imagery",
        }

        pairs = build_preference_pairs(
            report,
            source="beam",
            min_reward_margin=0.10,
            reward_mode="quality",
            token_names=token_names,
        )

        self.assertEqual(pairs, [])

    def test_write_jsonl_round_trips_pairs(self) -> None:
        pairs = [
            {"task_type": "T", "pos_tokens": [1], "neg_tokens": [2], "reward_margin": 0.5}
        ]
        with tempfile.TemporaryDirectory() as td:
            path = Path(td) / "pairs.jsonl"
            write_jsonl(pairs, path)

            rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]

        self.assertEqual(rows, pairs)

    def test_prepare_candidate_sequence_adds_start_and_end(self) -> None:
        decoder_input, target, mask = prepare_candidate_sequence(
            [4, 5], start_index=96, end_index=97, pad_index=94, max_length=6
        )

        self.assertEqual(decoder_input.tolist(), [96, 4, 5, 94, 94, 94])
        self.assertEqual(target.tolist(), [4, 5, 97, 94, 94, 94])
        self.assertEqual(mask.tolist(), [1, 1, 1, 0, 0, 0])

    def test_sequence_mean_logprob_uses_masked_target_positions(self) -> None:
        logits = torch.full((1, 3, 4), -10.0)
        logits[0, 0, 1] = 10.0
        logits[0, 1, 2] = 10.0
        logits[0, 2, 3] = 10.0
        target = torch.tensor([[1, 2, 0]])
        mask = torch.tensor([[1, 1, 0]])

        score = sequence_mean_logprob_from_logits(logits, target, mask)

        self.assertEqual(score.shape, (1,))
        self.assertAlmostEqual(float(score.item()), 0.0, places=4)

    def test_dpo_loss_prefers_policy_margin_over_reference_margin(self) -> None:
        good_loss = compute_dpo_loss(
            policy_pos=torch.tensor([3.0]),
            policy_neg=torch.tensor([1.0]),
            ref_pos=torch.tensor([1.5]),
            ref_neg=torch.tensor([1.0]),
            beta=0.1,
        )
        bad_loss = compute_dpo_loss(
            policy_pos=torch.tensor([1.0]),
            policy_neg=torch.tensor([3.0]),
            ref_pos=torch.tensor([1.5]),
            ref_neg=torch.tensor([1.0]),
            beta=0.1,
        )

        self.assertLess(float(good_loss.item()), float(bad_loss.item()))
        self.assertTrue(math.isfinite(float(good_loss.item())))


if __name__ == "__main__":
    unittest.main()
