# -*- coding: utf-8 -*-
"""
Project the old 350x256 L3 graph embeddings (outputs/l3_embeddings.pt) to the
v2 94x256 vocab by averaging old member embeddings for each v2 L3 code.

Strategy (no retraining needed — cheap & lossless for kept codes):
  - Kept L3:  copy the row 1:1.
  - Merged L3 (e.g. L3_03_03_A ← L3_03_03_01 | L3_03_03_04 | L3_03_03_06):
              mean of the member rows.
  - No 'delete' action targets exist in v2 vocab, by construction.

Output: outputs_v2/l3_embeddings_v2.pt
        { 'embeddings': FloatTensor[94, 256],
          'l3_codes': sorted list of v2 codes,
          'embedding_dim': 256,
          'v2_provenance': { new_code: [old_members...] } }
"""
from __future__ import annotations
import csv
import json
from collections import defaultdict
from pathlib import Path

import torch

ROOT = Path(__file__).resolve().parents[1]
OLD_EMB = ROOT / "outputs" / "l3_embeddings.pt"
MERGE_PLAN = ROOT / "outputs_v2" / "l3_merge_plan.csv"
HIER_V2 = ROOT / "outputs_v2" / "classification_hierarchy_v2.csv"
OUT = ROOT / "outputs_v2" / "l3_embeddings_v2.pt"


def main():
    # Load old embeddings
    old = torch.load(OLD_EMB, weights_only=True, map_location="cpu")
    old_emb: torch.Tensor = old["embeddings"]
    old_codes: list[str] = old["l3_codes"]
    dim: int = old["embedding_dim"]
    old_idx = {c: i for i, c in enumerate(old_codes)}
    assert old_emb.shape == (len(old_codes), dim), "shape mismatch"

    # Load merge plan  old_l3 -> (action, new_l3)
    plan: dict[str, tuple[str, str]] = {}
    with MERGE_PLAN.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            plan[r["old_l3"]] = (r["action"], r["new_l3"])

    # Build new_code -> [old_members] via the plan
    new_to_old: dict[str, list[str]] = defaultdict(list)
    for old_code, (action, new_code) in plan.items():
        if action == "delete":
            continue
        new_to_old[new_code].append(old_code)

    # v2 vocab (sorted)
    v2_codes: list[str] = []
    with HIER_V2.open(encoding="utf-8") as f:
        for r in csv.DictReader(f):
            v2_codes.append(r["l3_code"])
    v2_codes.sort()

    # Project
    new_emb = torch.zeros(len(v2_codes), dim)
    provenance = {}
    missing = []
    for i, new_code in enumerate(v2_codes):
        members = new_to_old.get(new_code, [])
        # members that exist in old vocab
        existing = [m for m in members if m in old_idx]
        if not existing:
            missing.append(new_code)
            continue
        rows = old_emb[[old_idx[m] for m in existing]]
        new_emb[i] = rows.mean(dim=0)
        provenance[new_code] = existing

    print(f"v2 vocab: {len(v2_codes)}  projected: {len(v2_codes) - len(missing)}  missing: {len(missing)}")
    if missing:
        print(f"  missing v2 codes without any old member: {missing}")

    # Sanity: mean norm check
    norms = new_emb.norm(dim=1)
    print(f"  embedding norm mean={norms.mean().item():.3f}  min={norms.min().item():.3f}  max={norms.max().item():.3f}")

    torch.save({
        "embeddings": new_emb,
        "l3_codes": v2_codes,
        "embedding_dim": dim,
        "v2_provenance": provenance,
        "source": "projection_of_v1_graph_embeddings",
    }, OUT)
    print(f"Wrote {OUT}")


if __name__ == "__main__":
    main()
