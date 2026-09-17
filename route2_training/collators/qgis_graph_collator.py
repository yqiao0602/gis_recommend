"""QGIS graph dataset + collator (C0/B1 second stage, and A1's only stage).

Row contract (v2a-A): task_text, processes[{process_id, operator_id}],
links[{source_process_id, target_process_id}].

Serialization keeps the DAG explicit (see harness.graph_to_text) — the model
must learn link structure, adjacency is never implied by ordering.
"""

from __future__ import annotations

import json
from pathlib import Path

from ..harness import graph_to_text, sha256_file


class QgisGraphDataset:
    def __init__(self, path: str | Path):
        self.rows = []
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if line.strip():
                    self.rows.append(json.loads(line))
        self.path = str(path)
        self.sha = sha256_file(path)

    def __len__(self):
        return len(self.rows)

    def prompt_target(self, i: int) -> tuple[str, str]:
        r = self.rows[i]
        target = graph_to_text(r["processes"], r["links"])
        return r["task_text"], target


class QgisGraphCollator:
    """Builds causal-LM training examples: loss on target tokens only."""

    PROMPT_SUFFIX = "\nQGIS workflow:"

    def __init__(self, tokenizer, max_len: int = 1024,
                 prompt_suffix: str | None = None):
        self.tok = tokenizer
        self.max_len = max_len
        if prompt_suffix is not None:
            self.PROMPT_SUFFIX = prompt_suffix

    def encode_pair(self, prompt: str, target: str) -> dict:
        """Return input_ids/labels with loss masked to the target portion.

        Truncation policy (audited, never silent): prompt is hard-truncated
        from the LEFT if overlong so the target head is preserved; target is
        truncated from the RIGHT (tail loss only). Caller logs counts.
        """
        p_ids = self.tok.encode(prompt + self.PROMPT_SUFFIX, add_special_tokens=False)
        t_ids = self.tok.encode(" " + target, add_special_tokens=False) + [self.tok.eos_token_id]
        # budget split: prompt at most 60% of window
        p_budget = int(self.max_len * 0.6)
        p_trunc = 0
        if len(p_ids) > p_budget:
            p_trunc = len(p_ids) - p_budget
            p_ids = p_ids[-p_budget:]          # keep prompt tail (closest to target)
        room = self.max_len - len(p_ids)
        t_trunc = 0
        if len(t_ids) > room:
            t_trunc = len(t_ids) - room
            t_ids = t_ids[:room]
        input_ids = [self.tok.bos_token_id] + p_ids + t_ids if self.tok.bos_token_id is not None else p_ids + t_ids
        labels = [-100] * (1 + len(p_ids) if self.tok.bos_token_id is not None else len(p_ids)) + list(t_ids)
        return {
            "input_ids": input_ids,
            "labels": labels,
            "n_prompt_truncated": p_trunc,
            "n_target_truncated": t_trunc,
        }

    def __call__(self, batch: list[dict]) -> dict:
        enc = [self.encode_pair(b["prompt"], b["target"]) for b in batch]
        maxlen = max(len(e["input_ids"]) for e in enc)
        pad = self.tok.pad_token_id or self.tok.eos_token_id
        input_ids, labels, attn = [], [], []
        for e in enc:
            n = maxlen - len(e["input_ids"])
            input_ids.append(e["input_ids"] + [pad] * n)
            labels.append(e["labels"] + [-100] * n)
            attn.append([1] * len(e["input_ids"]) + [0] * n)
        return {
            "input_ids": input_ids,
            "labels": labels,
            "attention_mask": attn,
        }
