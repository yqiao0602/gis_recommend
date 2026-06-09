from __future__ import annotations

from typing import Optional

import torch
import torch.nn.functional as F


def compute_v5_loss(
    *,
    logits_op: torch.Tensor,
    logits_end: torch.Tensor,
    target_op: torch.Tensor,
    target_end: torch.Tensor,
    pad_mask: Optional[torch.Tensor] = None,
    io_masks: Optional[torch.Tensor] = None,
    lambda_end: float = 0.3,
) -> tuple[torch.Tensor, dict]:
    """Compute the V5_final supervised loss.

    The loss intentionally contains no graph, alpha, provenance, metric, or
    diagnostic terms.
    """
    if io_masks is not None:
        logits_op = logits_op + io_masks.to(device=logits_op.device, dtype=logits_op.dtype)
    if pad_mask is None:
        valid = torch.ones_like(target_op, dtype=torch.bool)
    else:
        valid = ~pad_mask.bool()
    denom = valid.sum().clamp_min(1)
    target = target_op.clamp(0, logits_op.shape[-1] - 1)
    log_probs = F.log_softmax(logits_op, dim=-1)
    nll = -log_probs.gather(dim=-1, index=target.unsqueeze(-1)).squeeze(-1)
    loss_op = (nll * valid.to(nll.dtype)).sum() / denom

    end_loss = F.binary_cross_entropy_with_logits(
        logits_end.squeeze(-1),
        target_end.to(logits_end.dtype),
        reduction="none",
    )
    loss_end = (end_loss * valid.to(end_loss.dtype)).sum() / denom
    loss = loss_op + float(lambda_end) * loss_end
    return loss, {
        "loss": float(loss.detach().cpu()),
        "loss_op": float(loss_op.detach().cpu()),
        "loss_end": float(loss_end.detach().cpu()),
        "lambda_end": float(lambda_end),
    }
