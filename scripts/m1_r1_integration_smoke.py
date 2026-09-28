#!/usr/bin/env python3
"""M1-R1 integration smoke: the 10-item pre-training checklist.

Verifies, on the real paper_v1 data and the real V4.6 model, that the frozen
protocol trainer wires up correctly — without running a full epoch:

  1  7-key batch contract complete
  2  276 steps/epoch (8,832 samples at batch 32)
  3  platform/family/length metadata does not pollute the batch
  4  forward pass
  5  backward pass
  6  gradients finite
  7  TF phase runs
  8  AR-SS phase produces autoregressive samples
  9  EOS mask does not produce inf loss
 10  checkpoint save/reload round-trips

Run with the `transformer` env on the compute server; writes a JSON ledger.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

import torch
from torch.utils.data import DataLoader
from transformers import BertTokenizer

PROJECT_ROOT = Path("/home/qy/system_redesign")
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from gis_recommend.config.transformer_config import (  # noqa: E402
    L3_EMBEDDINGS_PATH, TOTAL_VOCAB_SIZE, V4_D_FF, V4_D_MODEL, V4_DROPOUT, V4_MAX_MEMORY_TOKENS,
    V4_MAX_SEQ_LENGTH, V4_N_HEADS, V4_N_LAYERS, V4_BERT_UNFREEZE_LAYERS,
)
from gis_recommend.models.task_text_processor import TaskVocabularyBuilder  # noqa: E402
from gis_recommend.models.transformer_model_v4 import TaskConditionedL3TransformerModelV4  # noqa: E402
from gis_recommend.training.train_v4_2 import TaskConditionedL3DatasetV4  # noqa: E402
from scripts.m1_r1_trainer import (  # noqa: E402
    GEE_RATIO, SAMPLES_PER_EPOCH, PlatformStratifiedTrainerV4_6_R1,
)

BATCH_KEYS = {"input_ids", "target_ids", "task_type_id", "text_input_ids",
              "text_attention_mask", "attention_mask", "sample_weight"}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=Path("/home/qy/gee_llm_smoke/m1_r1_smoke_v1.json"))
    args = ap.parse_args()

    results: dict = {"schema": "gis_recommend.m1_r1_integration_smoke.v1"}
    t0 = time.time()

    raw = json.loads(args.data.read_text(encoding="utf-8"))
    workflows = raw["labeled_workflows"]
    splits = raw["splits"]
    train_wf = [workflows[i] for i in splits["train_indices"]]
    val_wf = [workflows[i] for i in splits["val_indices"]]

    builder = TaskVocabularyBuilder()
    builder.build_from_workflows(train_wf)
    tokenizer = BertTokenizer.from_pretrained("bert-base-uncased", local_files_only=True)
    train_ds = TaskConditionedL3DatasetV4(train_wf, builder, tokenizer,
                                         max_seq_length=V4_MAX_SEQ_LENGTH, max_text_length=256)
    val_ds = TaskConditionedL3DatasetV4(val_wf, builder, tokenizer,
                                       max_seq_length=V4_MAX_SEQ_LENGTH, max_text_length=256)

    model = TaskConditionedL3TransformerModelV4(
        vocab_size=TOTAL_VOCAB_SIZE, num_task_types=int(len(builder.task_type_to_id)),
        d_model=V4_D_MODEL, n_heads=V4_N_HEADS, n_layers=V4_N_LAYERS, dim_feedforward=V4_D_FF,
        dropout=V4_DROPOUT, max_seq_length=V4_MAX_SEQ_LENGTH, max_memory_tokens=V4_MAX_MEMORY_TOKENS,
        use_l3_embeddings=True, l3_embeddings_path=str(L3_EMBEDDINGS_PATH),
        freeze_bert=False, bert_unfreeze_layers=V4_BERT_UNFREEZE_LAYERS,
        bert_model_name="bert-base-uncased", bert_local_files_only=True,
    ).to("cuda:0")
    results["params_m"] = round(sum(p.numel() for p in model.parameters()) / 1e6, 1)

    trainer = PlatformStratifiedTrainerV4_6_R1.__new__(PlatformStratifiedTrainerV4_6_R1)
    trainer.model = model
    trainer.train_dataset = train_ds
    trainer.batch_size = 32
    trainer.num_workers = 0
    trainer.gee_ratio = GEE_RATIO
    trainer._sampler_report = None
    trainer.device = torch.device("cuda:0")

    # 1-3: loader / contract / metadata isolation
    loader, samples = trainer._build_train_loader(0)
    results["1_epoch_samples"] = samples
    results["2_steps_per_epoch"] = len(loader)
    batch = next(iter(loader))
    keys = set(batch.keys())
    results["3_batch_keys"] = sorted(keys)
    results["3_contract_complete"] = keys == BATCH_KEYS
    results["3_metadata_isolated"] = not (keys - BATCH_KEYS)
    results["2_steps_ok"] = len(loader) == SAMPLES_PER_EPOCH // 32 == 276

    # 4-6: forward / backward / grads finite (TF step via the trainer's own path)
    batch = {k: v.to("cuda:0") for k, v in batch.items()}
    trainer.optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=1e-4)
    trainer.scaler = torch.amp.GradScaler("cuda", enabled=False)
    model.train()
    try:
        loss_dict = trainer._train_step_tf(batch)
        results["4_forward"] = True
        loss_val = float(loss_dict["main_loss"]) if isinstance(loss_dict, dict) else float(loss_dict)
        results["5_backward"] = True
        grads = [p.grad for p in model.parameters() if p.grad is not None]
        results["6_grads_finite"] = bool(grads) and all(bool(torch.isfinite(g).all()) for g in grads)
        results["7_tf_loss_finite"] = math.isfinite(loss_val)
        results["9_no_inf_eos"] = math.isfinite(loss_val)
    except Exception as exc:
        results["4_forward"] = results.get("4_forward", False)
        results["error_tf_step"] = f"{type(exc).__name__}: {exc}"

    # 8: AR-SS step produces autoregressive samples
    model.train()
    trainer.optimizer.zero_grad(set_to_none=True)
    try:
        ar_out = trainer._train_step_autoregressive(batch, 1.0)
        results["8_ar_step"] = ar_out is not None
        if isinstance(ar_out, dict):
            results["8_ar_keys"] = sorted(ar_out.keys())
    except Exception as exc:
        results["8_ar_step"] = False
        results["error_ar_step"] = f"{type(exc).__name__}: {exc}"

    # 10: checkpoint save/reload
    ckpt = Path("/home/qy/gee_llm_smoke/m1_smoke_ckpt")
    ckpt.mkdir(parents=True, exist_ok=True)
    path = ckpt / "smoke_step.pth"
    torch.save({"model_state_dict": model.state_dict()}, path)
    state = torch.load(path, map_location="cpu", weights_only=False)
    same = all(torch.equal(v.cpu(), model.state_dict()[k].cpu())
               for k, v in state["model_state_dict"].items() if k in model.state_dict())
    results["10_checkpoint_roundtrip"] = bool(same)

    results["minutes"] = round((time.time() - t0) / 60, 2)
    results["peak_memory_gb"] = round(torch.cuda.max_memory_allocated() / 2**30, 2)
    args.out.write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(results, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
