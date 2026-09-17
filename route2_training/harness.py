"""Route-2 Training Harness v1 — shared experiment core.

Single implementation, three arms (C0 / A1 / B1) via config. Arms differ
ONLY in their GEE stage; every arm ends in the SAME QGIS SFT stage, then
dev-120 checkpoint selection, then final-100 + refusal-12 (locked scorer).

Rulings baked in (P0 contract 33cc614, QC a5756a0):
  - C0: Base -> QGIS SFT only (true baseline, zero GEE)
  - A1: Base -> GEE DAPT (causal LM on domain corpus) -> QGIS SFT
  - B1: Base -> GEE Semantic SFT (Task -> semantic_chain_rle ONLY;
        gee_canonical_chain is audit-only, never in loss) -> QGIS SFT
  - checkpoint: QGIS dev-120 primary task metric (uniform across arms)
  - forbidden this round: aux GEE loss, DPO/RL, curriculum, dynamic
    sampling, ratio tuning, new splits, touching frozen data
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from pathlib import Path


def sha256_file(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ── QGIS graph serialization (round-trip safe) ─────────────────────────────

def graph_to_text(processes: list[dict], links: list[dict]) -> str:
    """Serialize a v2a graph to the LM target format.

    Preserves process identity and DAG structure: processes are emitted in
    the order of their process_id as given (v2a rows are ID-ordered), each
    as `PID:operator`; links then follow as explicit `L:src>dst` tokens.
    Branching and multi-parent nodes survive the round-trip because links
    are never inferred from adjacency — the DAG is stated, not implied.
    """
    pdefs = [f"P:{p['process_id']}:{p['operator_id']}" for p in processes]
    ldefs = [f"L:{l['source_process_id']}>{l['target_process_id']}" for l in links]
    return " ".join(pdefs + ldefs) if (pdefs or ldefs) else ""


def text_to_graph(text: str) -> tuple[list[dict], list[dict]]:
    """Inverse of graph_to_text; raises on malformed tokens (fail-closed)."""
    processes, links = [], []
    for tok in text.split():
        if tok.startswith("P:"):
            _, pid, op = tok.split(":", 2)
            processes.append({"process_id": pid, "operator_id": op})
        elif tok.startswith("L:"):
            src, dst = tok[2:].split(">")
            links.append({"source_process_id": src, "target_process_id": dst})
        else:
            raise ValueError(f"malformed graph token: {tok!r}")
    return processes, links


@dataclass
class ArmConfig:
    name: str                      # "C0" | "A1" | "B1"
    base_model: str
    # QGIS SFT stage (identical across arms)
    qgis_train: str
    qgis_dev: str
    qgis_test: str
    output_dir: str
    # GEE stage (arm-specific; empty for C0)
    gee_stage: str = "none"        # none | dapt | semantic_sft
    gee_data: str = ""             # DAPT corpus file or b1 stage jsonl
    # hyperparameters (uniform; single values, no tuning this round)
    qgis_epochs: int = 20
    gee_epochs: int = 1
    max_lr: float = 1e-4
    batch_size: int = 8
    grad_accum: int = 4
    max_len: int = 1024            # prompt+target token cap
    seed: int = 20260917
    # audit
    truncation_log: str = ""


@dataclass
class TruncationReport:
    n_total: int = 0
    n_truncated: int = 0
    raw_len_p50: int = 0
    raw_len_p90: int = 0
    final_len_p50: int = 0
    final_len_p90: int = 0
    max_len: int = 0
    max_observed: int = 0

    @property
    def truncation_rate(self) -> float:
        return self.n_truncated / max(self.n_total, 1)

    def to_dict(self) -> dict:
        return {
            "n_total": self.n_total, "n_truncated": self.n_truncated,
            "truncation_rate": round(self.truncation_rate, 4),
            "raw_length_p50": self.raw_len_p50, "raw_length_p90": self.raw_len_p90,
            "final_length_p50": self.final_len_p50, "final_length_p90": self.final_len_p90,
            "max_length": self.max_len, "max_observed": self.max_observed,
        }
