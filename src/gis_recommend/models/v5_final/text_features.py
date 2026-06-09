from __future__ import annotations

import hashlib

import torch


def deterministic_task_embeddings(
    text: str,
    *,
    hidden_size: int,
    tokens: int = 4,
    device: torch.device | str | None = None,
) -> torch.Tensor:
    """Create deterministic task embeddings for smoke tests and fixtures.

    Production runs should use frozen BERT or persisted task embeddings.  This
    helper exists so entrypoints can be exercised without network downloads.
    """
    seed = int(hashlib.sha256(text.encode("utf-8")).hexdigest()[:16], 16) % (2**31)
    generator = torch.Generator(device="cpu")
    generator.manual_seed(seed)
    emb = torch.randn(1, int(tokens), int(hidden_size), generator=generator)
    if device is not None:
        emb = emb.to(device)
    return emb
