"""Unit tests for V4.6 training rollout metrics and Set Predictor metrics.

Tests the real module's _lcs_ratio, _set_f1, and compute_metrics functions.
"""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))


def _import_rollout_helpers():
    """Import real _lcs_ratio and _set_f1 from train_v4_2 module."""
    from gis_recommend.training.train_v4_2 import ScheduledSamplingTrainerV4_2
    return (
        ScheduledSamplingTrainerV4_2._lcs_ratio,
        ScheduledSamplingTrainerV4_2._set_f1,
    )


class RolloutMetricsTests(unittest.TestCase):
    """Test _lcs_ratio and _set_f1 from the actual train_v4_2 module."""

    def test_lcs_empty(self) -> None:
        lcs, _ = _import_rollout_helpers()
        self.assertEqual(lcs([], []), 0.0)
        self.assertEqual(lcs([1, 2], []), 0.0)
        self.assertEqual(lcs([], [1, 2]), 0.0)

    def test_lcs_identical(self) -> None:
        lcs, _ = _import_rollout_helpers()
        self.assertEqual(lcs([1, 2, 3], [1, 2, 3]), 1.0)

    def test_lcs_subsequence(self) -> None:
        lcs, _ = _import_rollout_helpers()
        self.assertAlmostEqual(lcs([1, 3, 5], [1, 2, 3, 4, 5]), 0.6)
        self.assertAlmostEqual(lcs([1, 2, 8, 9], [1, 2, 3, 4]), 0.5)

    def test_lcs_disjoint(self) -> None:
        lcs, _ = _import_rollout_helpers()
        self.assertEqual(lcs([1, 2], [3, 4]), 0.0)

    def test_set_f1_empty(self) -> None:
        _, sf1 = _import_rollout_helpers()
        self.assertEqual(sf1([], []), 0.0)
        self.assertEqual(sf1([1, 2], []), 0.0)

    def test_set_f1_identical(self) -> None:
        _, sf1 = _import_rollout_helpers()
        self.assertEqual(sf1([1, 2, 3], [1, 2, 3]), 1.0)

    def test_set_f1_partial_overlap(self) -> None:
        _, sf1 = _import_rollout_helpers()
        self.assertAlmostEqual(sf1([1, 2], [2, 3]), 0.5)

    def test_set_f1_multiset(self) -> None:
        _, sf1 = _import_rollout_helpers()
        self.assertAlmostEqual(sf1([1, 1, 2], [1, 2, 2]), 2 / 3, places=4)


class SetPredictorMetricsTests(unittest.TestCase):
    """Test compute_metrics from the actual train_set_predictor_v3 module."""

    def test_compute_metrics_basic(self) -> None:
        import torch
        from gis_recommend.training.train_set_predictor_v3 import compute_metrics

        binary_logits = torch.tensor([
            [3.0, -3.0, 2.0, -3.0, -3.0],
            [-3.0, 3.0, -3.0, 3.0, -3.0],
        ])
        binary_targets = torch.tensor([
            [1.0, 0.0, 1.0, 0.0, 0.0],
            [0.0, 1.0, 0.0, 0.0, 0.0],
        ])
        count_logits = torch.zeros(2, 5, 3)
        count_targets = torch.zeros(2, 5, dtype=torch.long)

        m = compute_metrics(binary_logits, count_logits, binary_targets, count_targets, threshold=0.5)

        self.assertAlmostEqual(m['set_f1'], (1 + 2 / 3) / 2, places=3)
        self.assertAlmostEqual(m['exact_set_match'], 0.5, places=1)
        self.assertAlmostEqual(m['avg_pred_size'], 2.0, places=1)
        self.assertAlmostEqual(m['mean_true_set_size'], 1.5, places=1)
        self.assertAlmostEqual(m['zero_pred_rate'], 0.0, places=3)
        self.assertAlmostEqual(m['small_pred_rate_lt2'], 0.0, places=3)
        self.assertGreater(m['topk_recall@5'], 0.5)
        self.assertAlmostEqual(m['topk_recall@10'], 1.0, places=1)

    def test_zero_pred_rate(self) -> None:
        import torch
        from gis_recommend.training.train_set_predictor_v3 import compute_metrics

        binary_logits = torch.tensor([
            [-3.0, -3.0, -3.0, -3.0],
            [3.0, -3.0, -3.0, -3.0],
        ])
        binary_targets = torch.ones(2, 4)
        count_logits = torch.zeros(2, 4, 3)
        count_targets = torch.zeros(2, 4, dtype=torch.long)

        m = compute_metrics(binary_logits, count_logits, binary_targets, count_targets, threshold=0.5)

        self.assertAlmostEqual(m['zero_pred_rate'], 0.5, places=3)
        self.assertAlmostEqual(m['small_pred_rate_lt2'], 1.0, places=3)


if __name__ == "__main__":
    unittest.main()
