from __future__ import annotations

import sys
import unittest
from pathlib import Path

import torch
import torch.nn.functional as F


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))


class V46TrainingStabilityTests(unittest.TestCase):
    def test_dynamic_min_length_sampling_mask_does_not_pollute_ce_loss(self) -> None:
        from gis_recommend.training.train_v4_2 import END_INDEX, PAD_INDEX
        from gis_recommend.training.train_v4_6 import split_ar_logits_for_loss_and_sampling

        logits = torch.zeros(2, 98)
        targets = torch.tensor([END_INDEX, 12])
        dynamic_min_lengths = torch.tensor([5, 5])

        loss_logits, sampling_logits = split_ar_logits_for_loss_and_sampling(
            logits,
            dynamic_min_lengths=dynamic_min_lengths,
            step_index=0,
        )

        loss = F.cross_entropy(loss_logits, targets, ignore_index=PAD_INDEX)
        old_polluted_loss = F.cross_entropy(sampling_logits, targets, ignore_index=PAD_INDEX)

        self.assertTrue(torch.isfinite(loss))
        self.assertFalse(torch.isfinite(old_polluted_loss))
        self.assertEqual(float(logits[0, END_INDEX]), 0.0)
        self.assertTrue(torch.isneginf(sampling_logits[0, END_INDEX]))

    def test_dynamic_min_length_sampling_mask_allows_end_after_min_length(self) -> None:
        from gis_recommend.training.train_v4_2 import END_INDEX
        from gis_recommend.training.train_v4_6 import split_ar_logits_for_loss_and_sampling

        logits = torch.zeros(1, 98)

        loss_logits, sampling_logits = split_ar_logits_for_loss_and_sampling(
            logits,
            dynamic_min_lengths=torch.tensor([5]),
            step_index=5,
        )

        self.assertEqual(float(loss_logits[0, END_INDEX]), 0.0)
        self.assertEqual(float(sampling_logits[0, END_INDEX]), 0.0)

    def test_transition_mask_only_affects_sampling_logits_not_loss(self) -> None:
        from gis_recommend.training.train_v4_2 import END_INDEX, PAD_INDEX, START_INDEX
        from gis_recommend.training.train_v4_6 import split_ar_logits_for_loss_and_sampling

        logits = torch.randn(2, 98)
        transition_mask = {0: {10, 20, 30}}  # last_tok=0 → only 10,20,30 allowed
        decoder_input = torch.tensor([[START_INDEX, 0], [START_INDEX, 5]])
        dyn_min = torch.tensor([3, 3])

        loss_logits, sampling_logits = split_ar_logits_for_loss_and_sampling(
            logits,
            dynamic_min_lengths=dyn_min,
            step_index=5,  # past min-length so END is not blocked
            decoder_input=decoder_input,
            transition_mask=transition_mask,
        )

        # loss_logits must be unchanged (original logits)
        self.assertTrue(torch.equal(loss_logits, logits),
                        "loss logits must be unchanged by constraints")

        # sampling_logits: sample 0 has last_tok=0 → only 10,20,30+END allowed
        samp0 = sampling_logits[0]
        for tok in range(98):
            if tok in {10, 20, 30, END_INDEX}:
                self.assertTrue(torch.isfinite(samp0[tok]).item(),
                                f"token {tok} should be allowed for sample 0")
            elif tok == START_INDEX or tok == logits.size(1) or tok >= samp0.size(0):
                continue
            else:
                # transition mask sets -inf for disallowed tokens
                self.assertTrue(torch.isinf(samp0[tok]).item(),
                                f"token {tok} should be blocked by transition mask for sample 0")

        # sample 1 has last_tok=5 not in transition_mask → no mask applied
        samp1 = sampling_logits[1]
        allowed1 = torch.isfinite(samp1).sum().item()
        self.assertGreater(allowed1, 4, "sample without transition should keep most tokens")

    def test_transition_mask_always_allows_end(self) -> None:
        from gis_recommend.training.train_v4_2 import END_INDEX, START_INDEX
        from gis_recommend.training.train_v4_6 import split_ar_logits_for_loss_and_sampling

        logits = torch.randn(2, 98)
        transition_mask = {0: {10}}  # only token 10
        decoder_input = torch.tensor([[START_INDEX, 0], [START_INDEX, 0]])
        dyn_min = torch.tensor([3, 3])

        loss_logits, sampling_logits = split_ar_logits_for_loss_and_sampling(
            logits,
            dynamic_min_lengths=dyn_min,
            step_index=5,  # past min-length so END not blocked by dynamic
            decoder_input=decoder_input,
            transition_mask=transition_mask,
        )

        # END must always be allowed (past min-length, with transition mask)
        for b in range(2):
            self.assertTrue(torch.isfinite(sampling_logits[b, END_INDEX]).item(),
                            f"END must be allowed for sample {b} (past min-length)")

    def test_invalid_transition_diagnostic_counts_unknown_states(self) -> None:
        from gis_recommend.training.train_v4_2 import count_invalid_transitions

        mask = {1: {2}, 2: {3}}
        violations, total = count_invalid_transitions([1, 2, 99, 3], mask)

        self.assertEqual(total, 3)
        self.assertEqual(violations, 2)


if __name__ == "__main__":
    unittest.main()
