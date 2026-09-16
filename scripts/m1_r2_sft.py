#!/usr/bin/env python3
"""M1-R2 Phase 2-D: SFT with the DAPT-pretrained decoder backbone.

Protocol = M1-R1 EXACTLY (frozen 2026-09-09): same data, splits, task vocab,
l3-embedding init, length stats, 20 epochs, TF phase 10, ar_max_steps 40,
platform-stratified sampler (GIS_V4_TRAINER=platform_r1), same loss/optimizer/
checkpoint selection. The ONLY difference: after _build_model constructs the
R1-identical model (including the l3_embeddings-based 132-token embedding
init), the DAPT carry set (decoder_layers + decoder_norm + input FiLM
gamma/beta) is loaded from the Phase 2-C audited artifact.

Implementation is deliberately minimal-invasion: this wrapper imports the
quality-gate module, patches ONLY _build_model to append the carry load, and
replays the run_m1_r1.sh argument vector. No training-loop code is touched.
"""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT_ROOT = Path("/home/qy/system_redesign")
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

CARRY_PTH = "/home/qy/gee_llm_smoke/m1_r2/m1_r2_sft_init_carry.pth"

# R1 launch vector (run_m1_r1.sh), verbatim except checkpoint-dir and log
R1_ARGV = [
    "--data", "/home/qy/gee_llm_smoke/m1_smoke_data_v1.json",
    "--splits", "/home/qy/gee_llm_smoke/m1_splits_full_v1.json",
    "--task-vocab", "/home/qy/gee_llm_smoke/m1_task_vocab_v1.json",
    "--l3-embeddings", "docs/reports/paper_v1_profile_v1/l3_embeddings_paper_v1_128.pt",
    "--length-stats", "docs/reports/paper_v1_profile_v1/task_type_length_stats_paper_v1.json",
    "--num-epochs", "20",
    "--ar-max-steps", "40",
    "--checkpoint-dir", "/home/qy/gee_llm_smoke/m1_r2_sft_ckpt",
]


def main() -> int:
    import torch
    import train_v4_6_quality_gate as gate  # scripts/ on sys.path via PROJECT_ROOT

    original_build_model = gate._build_model
    carry = torch.load(CARRY_PTH, map_location="cpu", weights_only=False)
    assert carry["schema"] == "gis_recommend.m1_r2_sft_init.v1"
    assert all(carry["audit"].values()), "Phase 2-C audit must be all-pass"
    carry_state = carry["carry_state"]

    def build_model_with_dapt_backbone(**kwargs):
        model = original_build_model(**kwargs)
        # Record pre-carry SHAs for the training log (proof of what changed)
        import hashlib
        def sha(t):
            return hashlib.sha256(
                t.detach().cpu().contiguous().numpy().tobytes()).hexdigest()[:12]
        pre = {k: {kk: sha(vv) for kk, vv in getattr(model, k).state_dict().items()}
               for k in ("decoder_layers", "decoder_norm", "input_film_gamma", "input_film_beta")}
        emb_sha_pre = sha(model.token_embedding.weight)
        # Load the DAPT carry set — the ONLY initialization difference vs R1
        with torch.no_grad():
            for key, state in carry_state.items():
                getattr(model, key).load_state_dict(state)
        post = {k: {kk: sha(vv) for kk, vv in getattr(model, k).state_dict().items()}
                for k in ("decoder_layers", "decoder_norm", "input_film_gamma", "input_film_beta")}
        changed = [k for k in post if post[k] != pre[k]]
        unchanged_emb = sha(model.token_embedding.weight) == emb_sha_pre
        print(f"\n  [M1-R2] DAPT carry loaded from {CARRY_PTH}")
        print(f"  [M1-R2] source: dapt_step={carry['dapt_step']} "
              f"checkpoint={carry['source_checkpoint']}")
        print(f"  [M1-R2] carry changed modules: {changed} (expect all 4)")
        print(f"  [M1-R2] token_embedding unchanged vs R1 init (l3_embeddings): "
              f"{unchanged_emb} (expect True)\n")
        assert len(changed) == 4, f"carry must change exactly 4 modules, got {changed}"
        assert unchanged_emb, "embedding must stay at the R1 l3_embeddings init"
        return model

    gate._build_model = build_model_with_dapt_backbone

    sys.argv = ["train_v4_6_quality_gate.py"] + R1_ARGV
    gate.main(R1_ARGV)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
