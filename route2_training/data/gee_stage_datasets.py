"""GEE stage datasets: A1 DAPT corpus and B1 semantic SFT.

A1 (DAPT): raw causal-LM over a domain corpus (instruction text + GEE
canonical chains + task descriptions, no QGIS, no task->workflow mapping).
B1 (Semantic SFT): prompt=instruction, target=semantic_chain_rle ONLY.
gee_canonical_chain is carried in metadata for audit and NEVER enters the
loss (P0-4 ruling; enforced by tests).
"""

from __future__ import annotations

import json
from pathlib import Path

from ..harness import sha256_file


class GeeSemanticDataset:
    """B1 GEE stage: Task -> semantic workflow (single objective)."""

    TARGET_FIELD = "semantic_chain_rle"
    AUDIT_FIELDS = ("gee_canonical_chain", "semantic_chain_raw",
                    "original_semantic_length", "final_semantic_length",
                    "run_cap_applied", "author_proxy")

    def __init__(self, path: str | Path, split: str | None = "train"):
        self.rows = []
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                r = json.loads(line)
                if split is None or r.get("split") == split:
                    self.rows.append(r)
        self.path = str(path)
        self.sha = sha256_file(path)

    def __len__(self):
        return len(self.rows)

    def prompt_target(self, i: int) -> tuple[str, str]:
        r = self.rows[i]
        return r["instruction"], r[self.TARGET_FIELD]

    def audit_row(self, i: int) -> dict:
        r = self.rows[i]
        return {k: r.get(k) for k in self.AUDIT_FIELDS}


class GeeDaptCorpus:
    """A1 GEE stage: domain text for causal-LM adaptation.

    Corpus = instruction text + GEE canonical chain (as text). This is
    domain language exposure, NOT task->workflow supervision: the chain is
    concatenated as plain text without any prompt/target split, so the
    objective is next-token prediction over the domain distribution.
    """

    def __init__(self, path: str | Path, split: str | None = "train"):
        self.rows = []
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                if not line.strip():
                    continue
                r = json.loads(line)
                if split is None or r.get("split") == split:
                    self.rows.append(r)
        self.path = str(path)
        self.sha = sha256_file(path)

    def __len__(self):
        return len(self.rows)

    def domain_text(self, i: int) -> str:
        r = self.rows[i]
        return f"{r['instruction']}\n{r['gee_canonical_chain']}"
