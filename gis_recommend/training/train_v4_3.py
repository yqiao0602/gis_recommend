"""
V4.3 Training: Fixed AR Schedule + Warm-start from V4.2

Key changes from V4.2:
  - TF-only phase: 10 → 0 epochs (skipped with warm-start)
  - tf_ratio: 1.0→0.1 becomes 0.5→0.0 (faster AR exposure)
  - ar_ratio: 0.1→0.7 becomes 0.3→1.0 (more AR batches)
  - Warm-start from V4.2 best checkpoint

Usage:
    python -m gis_recommend.training.train_v4_3
"""

from __future__ import annotations

import json
import random
import sys
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader
from transformers import BertTokenizer

# ── project imports ──────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from gis_recommend.config.transformer_config import (
    DEVICE, RANDOM_SEED, OUTPUT_DIR, TOTAL_VOCAB_SIZE,
    V4_LABELED_WORKFLOWS_PATH, V4_TASK_TYPE_VOCAB_PATH,
    V4_D_MODEL, V4_N_HEADS, V4_N_LAYERS, V4_D_FF, V4_DROPOUT,
    V4_MAX_SEQ_LENGTH, V4_MAX_MEMORY_TOKENS,
    V4_BERT_UNFREEZE_LAYERS,
    V4_1_FREQ_WEIGHT_ALPHA,
    V4_2_BATCH_SIZE, V4_2_NUM_WORKERS,
    V4_2_BERT_LR, V4_2_OTHER_LR,
    L3_EMBEDDINGS_PATH,
    # V4.3 specific
    V4_3_TRANSFORMER_CHECKPOINT_DIR, V4_3_WARMSTART_PATH,
    V4_3_TF_PHASE_EPOCHS, V4_3_SS_TF_START, V4_3_SS_TF_END,
    V4_3_AR_RATIO_START, V4_3_AR_RATIO_END,
    V4_3_NUM_EPOCHS, V4_3_WARMUP_EPOCHS, V4_3_EARLY_STOPPING_PATIENCE,
)
from gis_recommend.models.transformer_model_v4 import TaskConditionedL3TransformerModelV4
from gis_recommend.models.task_text_processor import TaskVocabularyBuilder
from gis_recommend.training.train_v4_2 import (
    ScheduledSamplingTrainerV4_2,
    TaskConditionedL3DatasetV4,
    compute_token_freq_weights,
    load_or_create_splits,
    set_seed,
)


def load_warmstart_checkpoint(model, checkpoint_path, device):
    """Load V4.2 best checkpoint weights into model.

    Loads model_state_dict and optionally task_classifier_state_dict.
    Returns the task_classifier state dict (or None) for the trainer.
    """
    if not Path(checkpoint_path).exists():
        print(f"  [WARN] Warm-start checkpoint not found: {checkpoint_path}")
        print(f"  Training from scratch instead.")
        return None

    print(f"  Loading warm-start from {checkpoint_path} ...")
    ckpt = torch.load(checkpoint_path, map_location=device, weights_only=True)

    # Load model weights
    model.load_state_dict(ckpt['model_state_dict'])
    val_loss = ckpt.get('val_loss')
    val_loss_str = f"{val_loss:.4f}" if val_loss is not None else "?"
    print(f"  Model weights loaded (epoch {ckpt.get('epoch', '?')}, "
          f"val_loss={val_loss_str})")

    return ckpt.get('task_classifier_state_dict')


def main():
    print("=" * 80)
    print("V4.3 Training: Fixed AR Schedule + Warm-start")
    print("  Changes: TF phase 3ep, tf_ratio 0.5→0.0, ar_ratio 0.3→1.0")
    print("=" * 80)

    # CUDA check
    if torch.cuda.is_available():
        print(f"  CUDA: {torch.cuda.get_device_name(0)}")
        print(f"  GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
    else:
        print("  [WARNING] CUDA NOT AVAILABLE!")
        resp = input("  Continue on CPU? (y/n): ").strip().lower()
        if resp != 'y':
            return

    set_seed(RANDOM_SEED)

    # [1] Load data
    print("\n[1] Loading data...")
    with open(V4_LABELED_WORKFLOWS_PATH, 'r', encoding='utf-8') as f:
        data = json.load(f)
    workflows = data['labeled_workflows']
    print(f"  Workflows: {len(workflows)}")

    # [2] Load task type vocabulary
    print("\n[2] Loading task type vocabulary...")
    with open(V4_TASK_TYPE_VOCAB_PATH, 'r', encoding='utf-8') as f:
        task_type_vocab = json.load(f)
    num_task_types = task_type_vocab['num_types']

    task_vocab_builder = TaskVocabularyBuilder()
    task_vocab_builder.task_type_to_id = task_type_vocab['task_type_to_id']
    task_vocab_builder.id_to_task_type = {
        int(k): v for k, v in task_type_vocab['id_to_task_type'].items()
    }
    bert_tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')

    # [3] Split dataset (reuse V4 splits)
    print("\n[3] Splitting dataset...")
    split_path = OUTPUT_DIR / "dataset_splits_v4.json"
    splits = load_or_create_splits(workflows, split_path, seed=RANDOM_SEED)
    train_wf = [workflows[i] for i in splits['train_indices']]
    val_wf = [workflows[i] for i in splits['val_indices']]
    test_wf = [workflows[i] for i in splits['test_indices']]
    print(f"  Train: {len(train_wf)}, Val: {len(val_wf)}, Test: {len(test_wf)}")

    # [4] Token frequency weights
    print("\n[4] Computing token frequency weights...")
    freq_weights = compute_token_freq_weights(
        train_wf, alpha=V4_1_FREQ_WEIGHT_ALPHA, vocab_size=TOTAL_VOCAB_SIZE
    )

    # [5] Create datasets
    print("\n[5] Creating datasets...")
    train_dataset = TaskConditionedL3DatasetV4(train_wf, task_vocab_builder, bert_tokenizer)
    val_dataset = TaskConditionedL3DatasetV4(val_wf, task_vocab_builder, bert_tokenizer)
    test_dataset = TaskConditionedL3DatasetV4(test_wf, task_vocab_builder, bert_tokenizer)
    val_loader = DataLoader(val_dataset, batch_size=V4_2_BATCH_SIZE, shuffle=False,
                            num_workers=V4_2_NUM_WORKERS)
    test_loader = DataLoader(test_dataset, batch_size=V4_2_BATCH_SIZE, shuffle=False,
                             num_workers=V4_2_NUM_WORKERS)

    # [6] Create model
    print("\n[6] Creating model...")
    model = TaskConditionedL3TransformerModelV4(
        vocab_size=TOTAL_VOCAB_SIZE,
        num_task_types=num_task_types,
        d_model=V4_D_MODEL,
        n_heads=V4_N_HEADS,
        n_layers=V4_N_LAYERS,
        dim_feedforward=V4_D_FF,
        dropout=V4_DROPOUT,
        max_seq_length=V4_MAX_SEQ_LENGTH,
        max_memory_tokens=V4_MAX_MEMORY_TOKENS,
        use_l3_embeddings=True,
        l3_embeddings_path=str(L3_EMBEDDINGS_PATH),
        freeze_bert=False,
        bert_unfreeze_layers=V4_BERT_UNFREEZE_LAYERS,
    )
    counts = model.count_parameters()
    print(f"  Params: {counts['trainable']/1e6:.1f}M trainable, {counts['total']/1e6:.1f}M total")

    # [7] Warm-start from V4.2
    print("\n[7] Loading warm-start checkpoint...")
    task_cls_state = load_warmstart_checkpoint(model, V4_3_WARMSTART_PATH, DEVICE)
    warm_started = task_cls_state is not None

    # [8] Create trainer with V4.3 AR schedule
    #     When warm-starting, skip TF-only phase (set tf_phase_epochs=0)
    #     so the model immediately enters AR-SS training.
    print("\n[8] Creating V4.3 trainer...")
    effective_tf_phase = 0 if warm_started else V4_3_TF_PHASE_EPOCHS
    trainer = ScheduledSamplingTrainerV4_2(
        model=model,
        train_dataset=train_dataset,
        val_loader=val_loader,
        test_loader=test_loader,
        num_task_types=num_task_types,
        token_freq_weights=freq_weights,
        checkpoint_dir=V4_3_TRANSFORMER_CHECKPOINT_DIR,
        use_amp=(DEVICE.type == 'cuda'),
        # V4.3 AR schedule changes
        tf_phase_epochs=effective_tf_phase,
        ss_tf_start=V4_3_SS_TF_START,
        ss_tf_end=V4_3_SS_TF_END,
        ar_ratio_start=V4_3_AR_RATIO_START,
        ar_ratio_end=V4_3_AR_RATIO_END,
        num_epochs=V4_3_NUM_EPOCHS,
        warmup_epochs=V4_3_WARMUP_EPOCHS,
        early_stopping_patience=V4_3_EARLY_STOPPING_PATIENCE,
        bert_lr=V4_2_BERT_LR,
        other_lr=V4_2_OTHER_LR,
    )

    # Load task classifier weights if warm-starting
    if task_cls_state is not None:
        trainer.task_classifier.load_state_dict(task_cls_state)
        print("  Task classifier weights loaded from V4.2")

    # [9] Print V4.3 schedule preview
    print("\n[9] V4.3 Schedule Preview:")
    print(f"  Warm-start: {'YES (TF phase skipped)' if warm_started else 'NO'}")
    for ep in [0, 2, 3, 5, 10, 20, 30, 39]:
        if ep >= V4_3_NUM_EPOCHS:
            break
        tf = trainer.get_tf_ratio(ep)
        ar = trainer.get_ar_ratio(ep)
        phase = "TF" if ep < effective_tf_phase else "AR-SS"
        print(f"  Epoch {ep+1:3d}: [{phase:5s}] tf_ratio={tf:.3f}, ar_ratio={ar:.0%}")

    # [10] Train
    print("\n[10] Starting V4.3 training...")
    trainer.train()
    print("\nV4.3 training complete!")


if __name__ == "__main__":
    main()
