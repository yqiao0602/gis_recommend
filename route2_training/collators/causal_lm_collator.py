"""Causal-LM collator for A1 DAPT and B1 semantic SFT (packed/flat)."""

from __future__ import annotations


class CausalLMCollator:
    """Plain causal-LM batches with loss over all (non-pad) tokens.

    For DAPT: whole text is the target (no masking).
    For B1 semantic SFT the caller uses QgisGraphCollator-style masking via
    encode_pair in qgis_graph_collator (same class handles prompt/target
    masking); this collator is the DAPT + truncation-audit path.
    """

    def __init__(self, tokenizer, max_len: int = 1024):
        self.tok = tokenizer
        self.max_len = max_len

    def encode_text(self, text: str) -> dict:
        ids = self.tok.encode(text, add_special_tokens=False)
        if self.tok.bos_token_id is not None:
            ids = [self.tok.bos_token_id] + ids
        n_trunc = 0
        if len(ids) > self.max_len:
            n_trunc = len(ids) - self.max_len
            ids = ids[:self.max_len]
        return {"input_ids": ids, "n_truncated": n_trunc, "raw_len": n_trunc + len(ids)}

    def __call__(self, batch: list[dict]) -> dict:
        enc = [self.encode_text(b["text"]) for b in batch]
        maxlen = max(len(e["input_ids"]) for e in enc)
        pad = self.tok.pad_token_id or self.tok.eos_token_id
        input_ids, labels, attn = [], [], []
        for e in enc:
            n = maxlen - len(e["input_ids"])
            input_ids.append(e["input_ids"] + [pad] * n)
            labels.append(e["input_ids"] + [-100] * n)   # loss on real tokens
            attn.append([1] * len(e["input_ids"]) + [0] * n)
        return {"input_ids": input_ids, "labels": labels, "attention_mask": attn}
