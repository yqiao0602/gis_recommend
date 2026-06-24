from __future__ import annotations

import torch
import torch.nn.functional as F


def weighted_sequence_cross_entropy(
    logits: torch.Tensor,
    targets: torch.Tensor,
    sample_weights: torch.Tensor | None = None,
    *,
    weight: torch.Tensor | None = None,
    ignore_index: int = -100,
    label_smoothing: float = 0.0,
) -> torch.Tensor:
    """Cross entropy with optional per-sample weights.

    ``logits`` may be ``[B, V]`` for one decoding step or ``[B, T, V]`` for a
    full teacher-forcing sequence. Padding is ignored before each sample is
    averaged, then sample weights are applied across the batch.
    """
    if logits.dim() == 2:
        token_loss = F.cross_entropy(
            logits,
            targets,
            weight=weight,
            ignore_index=ignore_index,
            label_smoothing=label_smoothing,
            reduction="none",
        )
        valid = targets.ne(ignore_index).float()
        per_sample = token_loss * valid
    elif logits.dim() == 3:
        batch, steps, vocab = logits.shape
        token_loss = F.cross_entropy(
            logits.reshape(batch * steps, vocab),
            targets.reshape(batch * steps),
            weight=weight,
            ignore_index=ignore_index,
            label_smoothing=label_smoothing,
            reduction="none",
        ).view(batch, steps)
        valid = targets.ne(ignore_index).float()
        per_sample = (token_loss * valid).sum(dim=1) / valid.sum(dim=1).clamp(min=1.0)
    else:
        raise ValueError(f"Expected logits dim 2 or 3, got shape {tuple(logits.shape)}")

    if sample_weights is None:
        if logits.dim() == 2:
            denom = valid.sum().clamp(min=1.0)
            return per_sample.sum() / denom
        return (token_loss * valid).sum() / valid.sum().clamp(min=1.0)

    weights = sample_weights.to(device=logits.device, dtype=torch.float).clamp(min=0.0)
    if weights.dim() != 1 or weights.numel() != per_sample.numel():
        raise ValueError(
            f"sample_weights must be [B], got {tuple(weights.shape)} for batch {per_sample.numel()}"
        )
    if logits.dim() == 2:
        weights = weights * valid
    else:
        weights = weights * valid.sum(dim=1).gt(0).float()
    return (per_sample * weights).sum() / weights.sum().clamp(min=1e-6)
