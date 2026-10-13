#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Check 3 evidence: endpoint-EOS loss weighting (lambda=2) — mask + formula
assertions on CPU (no model, no GPU, no training).

Frozen spec (A_DPRIME_PREREGISTRATION v0.3):
  w_i = LAMBDA for each row's TERMINAL EOS label position; 1 for every other
  non-masked label; loss = sum(ce_i * w_i) / sum(w_i).
  Assertions:
    A1: exactly ONE weighted position per row
    A2: that position's label == eos_token_id
    A3: that position is the LAST non-masked label of the row
    A4: lambda=1 reduces to the plain mean over non-masked tokens
    A5: end-to-end gradient-scale sanity: weighted loss is finite and
        >= plain loss when lambda > 1 on a row whose terminal token is
        not already the argmax (monotone pressure toward EOS)
"""
import json
import sys

import torch
import torch.nn.functional as F

sys.stdout.reconfigure(encoding="utf-8")

LAMBDA = 2.0


def endpoint_eos_loss(logits, labels, eos_id, lam=LAMBDA):
    shift_logits = logits[:, :-1, :].float()
    shift_labels = labels[:, 1:]
    ce = F.cross_entropy(shift_logits.transpose(1, 2), shift_labels,
                         ignore_index=-100, reduction="none")
    mask = shift_labels != -100
    # A2/A3: the terminal non-masked label of every row must be EOS
    pos = torch.arange(1, labels.shape[1], device=labels.device)
    last = (mask.float() * pos).argmax(dim=1)
    has = mask.any(dim=1)
    rows = torch.arange(ce.shape[0], device=ce.device)
    assert shift_labels[rows[has], last[has]].eq(eos_id).all(), \
        "A2/A3 FAIL: terminal non-masked label is not EOS (or not last)"
    # A1: exactly one lambda-weighted position per row (only when lam != 1)
    w = mask.float()
    w[rows[has], last[has]] = lam
    if lam != 1.0:
        assert ((w == lam).sum(dim=1)[has] == 1).all(), \
            "A1 FAIL: not exactly one lambda pos"
    return (ce * w).sum() / w.sum()


def main():
    torch.manual_seed(0)
    V, T, B = 50, 12, 4
    eos_id = V - 1
    # rows mimic collator: [-100]*prefix + target + eos (+ [-100] pad)
    labels = torch.full((B, T), -100, dtype=torch.long)
    labels[0, 3:] = torch.tensor([5, 6, 7, eos_id] + [-100] * (T - 7))
    labels[1, 1:] = torch.tensor([8, eos_id] + [-100] * (T - 3))
    labels[2, 0:] = torch.tensor([9, 10, eos_id] + [-100] * (T - 3))
    labels[3, 2:] = torch.tensor([11, eos_id] + [-100] * (T - 4))
    logits = torch.randn(B, T, V)
    # make the terminal token NOT the argmax (so lambda adds real pressure)
    for b, tpos in ((0, 6), (1, 2), (2, 2), (3, 3)):
        logits[b, tpos - 1, eos_id] = -0.5
        logits[b, tpos - 1, (eos_id + 3) % V] = 1.5

    lw = endpoint_eos_loss(logits, labels, eos_id, LAMBDA)
    l1 = endpoint_eos_loss(logits, labels, eos_id, 1.0)
    plain = F.cross_entropy(
        logits[:, :-1, :].transpose(1, 2), labels[:, 1:],
        ignore_index=-100)
    assert torch.isfinite(lw), "A5 FAIL: non-finite weighted loss"
    assert torch.allclose(l1, plain, atol=1e-6), \
        "A4 FAIL: lambda=1 != plain mean"
    assert float(lw) >= float(plain), "A5 FAIL: lambda>1 lowered loss"
    print(json.dumps({
        "A1_one_lambda_pos_per_row": True,
        "A2_terminal_label_is_eos": True,
        "A3_position_is_last_nonmasked": True,
        "A4_lambda1_equals_plain_mean": True,
        "A5_finite_and_monotone": True,
        "weighted_loss": round(float(lw), 5),
        "plain_loss": round(float(plain), 5),
        "lambda": LAMBDA,
        "verdict": "CHECK3 PASS (mask + formula verified; lambda applies "
                   "ONLY to the terminal EOS label position)",
    }, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
