#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Per-item termination classification (P2-R instrument fix).

Frozen separation of two dimensions (owner ruling):
  output_state : "empty" | "non_empty"   (observable: raw text)
  term         : "END_MARK" | "CAP_TRUNC" | "EOS" | "IMMEDIATE_EOS"
                 (mechanism: per-item generated length + markers)

Batch-level length must never decide an individual item's term (the v1 bug).
"""
from typing import Iterable, Sequence

END_MARKERS = ("END OF PLAN", "END OF LIST", "NO OPERATOR FOR THIS STEP")


def classify_item(text: str, n_item: int, maxnew: int) -> dict:
    """n_item = number of generated tokens for THIS item (including the EOS
    token when one was sampled); never a batch maximum."""
    empty = not (text or "").strip()
    marked = any(m in (text or "") for m in END_MARKERS)
    if maxnew and n_item >= maxnew:
        term = "CAP_TRUNC"
    elif marked:
        term = "END_MARK"
    elif n_item <= 1:
        term = "IMMEDIATE_EOS"
    else:
        term = "EOS"
    return {"output_state": "empty" if empty else "non_empty",
            "term": term, "n_item": int(n_item), "maxnew": int(maxnew),
            "marked": marked}


def classify_batch(texts: Sequence[str], n_items: Sequence[int],
                   maxnew: int) -> list:
    if len(texts) != len(n_items):
        raise ValueError("texts and n_items must align")
    return [classify_item(t, n, maxnew) for t, n in zip(texts, n_items)]


def first_stop_index(token_ids: Iterable[int], stop_ids: Iterable[int],
                     default: int) -> int:
    """Index (1-based) of the first stop token in a generated tail; the item's
    generated length. If none, the full tail length."""
    stops = set(stop_ids)
    for i, t in enumerate(token_ids):
        if t in stops:
            return i + 1
    return default
