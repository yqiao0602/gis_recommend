#!/usr/bin/env python3
"""Expand a 47-task checkpoint to 48-task checkpoint for QGIS vector combined training.

Adds a new "Vector Analysis" task type row to task_type_embedding and
task_classifier, initialised with the mean of existing task embeddings.

Usage:
    python scripts/expand_checkpoint_task_types.py \
        --input outputs_v2/transformer_checkpoints_v4_6_preference_dpo_v2_quality_cycle_fixed/best_preference_model.pth \
        --output outputs_v2/transformer_checkpoints_v4_6_quality_gate_qgis_vector/warmstart_48task.pth
"""

import argparse, sys
from pathlib import Path
import torch

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path: sys.path.insert(0, str(SRC))

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    ckpt = torch.load(args.input, map_location="cpu", weights_only=True)
    sd = ckpt["model_state_dict"]
    tcls_sd = ckpt.get("task_classifier_state_dict", {})

    # Check current size
    embed_key = "task_type_embedding.weight"
    if embed_key not in sd:
        print("ERROR: task_type_embedding.weight not found")
        return 1
    old_shape = sd[embed_key].shape  # [47, 256]
    print(f"Old task_type_embedding: {old_shape}")

    # Expand: add 1 row initialised to mean of existing rows
    new_embed = torch.cat([sd[embed_key], sd[embed_key].mean(dim=0, keepdim=True)], dim=0)
    sd[embed_key] = new_embed
    print(f"New task_type_embedding: {new_embed.shape}")

    # Expand task_classifier
    cls_weight_key = "weight"
    if cls_weight_key in tcls_sd:
        old_cls = tcls_sd[cls_weight_key].shape  # [47, 128]
        new_cls_w = torch.cat([tcls_sd[cls_weight_key], tcls_sd[cls_weight_key].mean(dim=0, keepdim=True)], dim=0)
        tcls_sd[cls_weight_key] = new_cls_w
        print(f"task_classifier.weight: {old_cls} -> {new_cls_w.shape}")
    cls_bias_key = "bias"
    if cls_bias_key in tcls_sd:
        new_cls_b = torch.cat([tcls_sd[cls_bias_key], tcls_sd[cls_bias_key].mean(dim=0, keepdim=True)], dim=0)
        tcls_sd[cls_bias_key] = new_cls_b

    # Update checkpoint metadata
    ckpt["task_classifier_state_dict"] = tcls_sd
    if "model_config" in ckpt:
        ckpt["model_config"]["num_task_types"] = new_embed.shape[0]

    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    torch.save(ckpt, args.output)
    print(f"\nSaved expanded checkpoint: {args.output}")
    print(f"  Task types: {old_shape[0]} -> {new_embed.shape[0]}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
