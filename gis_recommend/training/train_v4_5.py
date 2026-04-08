# -*- coding: utf-8 -*-
"""
V4.5 Training: Balanced Task Sampling + Stronger Task Signal

Changes from V4.4:
  1. WeightedRandomSampler — each task type sampled equally per epoch
  2. task_cls_loss_weight 0.1 -> 0.3 — stronger task-type conditioning signal

All other settings (AR schedule, length loss, early END penalty) same as V4.4.

Usage:
    python -m gis_recommend.training.train_v4_5
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

import torch
from torch.utils.data import DataLoader, Subset, WeightedRandomSampler
from transformers import BertTokenizer

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from gis_recommend.config.transformer_config import (
    DEVICE, RANDOM_SEED, OUTPUT_DIR, TOTAL_VOCAB_SIZE,
    V4_LABELED_WORKFLOWS_PATH, V4_TASK_TYPE_VOCAB_PATH,
    V4_D_MODEL, V4_N_HEADS, V4_N_LAYERS, V4_D_FF, V4_DROPOUT,
    V4_MAX_SEQ_LENGTH, V4_MAX_MEMORY_TOKENS,
    V4_BERT_UNFREEZE_LAYERS,
    V4_1_FREQ_WEIGHT_ALPHA,
    V4_LABEL_SMOOTHING, V4_GRADIENT_CLIP,
    V4_SS_K,
    V4_1_AR_SAMPLE_TEMPERATURE, V4_1_AR_SAMPLE_TOP_P,
    V4_1_DECODE_REP_PENALTY, V4_1_DECODE_REP_WINDOW,
    V4_TRANSITION_LOSS_WEIGHT,
    L3_EMBEDDINGS_PATH,
    V4_2_NUM_WORKERS, V4_2_AR_MAX_STEPS,
    V4_2_GEN_EVAL_BATCHES, V4_2_GRADIENT_ACCUM_STEPS,
    V4_4_WARMSTART_PATH,
    # V4.5 specific
    V4_5_TRANSFORMER_CHECKPOINT_DIR, V4_5_WARMSTART_PATH,
    V4_5_NUM_EPOCHS, V4_5_TF_PHASE_EPOCHS,
    V4_5_SS_TF_START, V4_5_SS_TF_END,
    V4_5_AR_RATIO_START, V4_5_AR_RATIO_END,
    V4_5_WARMUP_EPOCHS, V4_5_EARLY_STOPPING_PATIENCE,
    V4_5_OTHER_LR, V4_5_BERT_LR, V4_5_BATCH_SIZE,
    V4_5_LENGTH_LOSS_WEIGHT,
    V4_5_EARLY_END_PENALTY, V4_5_EARLY_END_THRESHOLD,
    V4_5_AR_DYNAMIC_MIN_RATIO,
    V4_5_TASK_CLS_LOSS_WEIGHT,
)
from gis_recommend.models.transformer_model_v4 import TaskConditionedL3TransformerModelV4
from gis_recommend.models.task_text_processor import TaskVocabularyBuilder
from gis_recommend.training.train_v4_2 import (
    TaskConditionedL3DatasetV4,
    compute_token_freq_weights,
    load_or_create_splits,
    set_seed,
    PAD_INDEX, START_INDEX, END_INDEX,
)
from gis_recommend.training.train_v4_4 import (
    ScheduledSamplingTrainerV4_4,
    load_warmstart_checkpoint,
)


def build_task_type_sampler(dataset: TaskConditionedL3DatasetV4) -> WeightedRandomSampler:
    """Build a WeightedRandomSampler that equalizes task type frequency.

    Each task type gets weight = 1 / count(task_type), so rare types
    are sampled as often as common ones within each epoch.
    """
    task_type_ids = [dataset[i]['task_type_id'].item() for i in range(len(dataset))]
    counts = Counter(task_type_ids)
    # weight per sample = inverse of its task type count
    weights = [1.0 / counts[t] for t in task_type_ids]
    sampler = WeightedRandomSampler(
        weights=weights,
        num_samples=len(weights),
        replacement=True,
    )
    return sampler


class ScheduledSamplingTrainerV4_5(ScheduledSamplingTrainerV4_4):
    """V4.5: Balanced task sampling + stronger task classification signal.

    Overrides from V4.4:
    - _build_train_loader: uses WeightedRandomSampler by task type
    - task_cls_loss_weight: 0.1 -> 0.3
    """

    def __init__(self, *args, task_cls_loss_weight=V4_5_TASK_CLS_LOSS_WEIGHT, **kwargs):
        super().__init__(*args, **kwargs)
        # Override the inherited weight
        self.task_cls_loss_weight = task_cls_loss_weight
        print(f"  [V4.5] task_cls_loss_weight overridden to {self.task_cls_loss_weight}")

    def _build_train_loader(self, epoch):
        """Balanced sampling: each task type equally represented per epoch."""
        sampler = build_task_type_sampler(self.train_dataset)
        loader = DataLoader(
            self.train_dataset,
            batch_size=self.batch_size,
            sampler=sampler,
            num_workers=self.num_workers,
            drop_last=True,
        )
        return loader, len(self.train_dataset)


def main():
    print("=" * 80)
    print("V4.5 Training: Balanced Task Sampling + Stronger Task Signal")
    print("  Changes: WeightedRandomSampler + task_cls_loss_weight 0.1->0.3")
    print("=" * 80)

    if torch.cuda.is_available():
        print(f"  CUDA: {torch.cuda.get_device_name(0)}")
        print(f"  GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1e9:.1f} GB")
    else:
        print("  [WARNING] CUDA NOT AVAILABLE!")

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
    print(f"  Task types: {num_task_types}")

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
    val_loader = DataLoader(val_dataset, batch_size=V4_5_BATCH_SIZE, shuffle=False,
                            num_workers=V4_2_NUM_WORKERS)
    test_loader = DataLoader(test_dataset, batch_size=V4_5_BATCH_SIZE, shuffle=False,
                             num_workers=V4_2_NUM_WORKERS)

    # Show task type distribution in training set
    task_counts = Counter(
        train_dataset[i]['task_type_id'].item() for i in range(len(train_dataset))
    )
    print(f"  Unique task types in train: {len(task_counts)}")
    top5 = task_counts.most_common(5)
    bot5 = task_counts.most_common()[:-6:-1]
    print(f"  Top-5 task types (count): {[(task_type_vocab['id_to_task_type'].get(str(k), k), v) for k, v in top5]}")
    print(f"  Bot-5 task types (count): {[(task_type_vocab['id_to_task_type'].get(str(k), k), v) for k, v in bot5]}")

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
    task_cls_state = load_warmstart_checkpoint(model, V4_5_WARMSTART_PATH, DEVICE)
    warm_started = task_cls_state is not None

    # [8] Create V4.5 trainer
    print("\n[8] Creating V4.5 trainer...")
    trainer = ScheduledSamplingTrainerV4_5(
        model=model,
        train_dataset=train_dataset,
        val_loader=val_loader,
        test_loader=test_loader,
        num_task_types=num_task_types,
        token_freq_weights=freq_weights,
        checkpoint_dir=V4_5_TRANSFORMER_CHECKPOINT_DIR,
        use_amp=(DEVICE.type == 'cuda'),
        # Schedule (same as V4.4)
        tf_phase_epochs=V4_5_TF_PHASE_EPOCHS,
        ss_tf_start=V4_5_SS_TF_START,
        ss_tf_end=V4_5_SS_TF_END,
        ar_ratio_start=V4_5_AR_RATIO_START,
        ar_ratio_end=V4_5_AR_RATIO_END,
        num_epochs=V4_5_NUM_EPOCHS,
        warmup_epochs=V4_5_WARMUP_EPOCHS,
        early_stopping_patience=V4_5_EARLY_STOPPING_PATIENCE,
        bert_lr=V4_5_BERT_LR,
        other_lr=V4_5_OTHER_LR,
        batch_size=V4_5_BATCH_SIZE,
        # Length-aware (same as V4.4)
        length_loss_weight=V4_5_LENGTH_LOSS_WEIGHT,
        early_end_penalty=V4_5_EARLY_END_PENALTY,
        early_end_threshold=V4_5_EARLY_END_THRESHOLD,
        ar_dynamic_min_ratio=V4_5_AR_DYNAMIC_MIN_RATIO,
        # No curriculum
        curriculum_p1_end=-1,
        curriculum_p1_max=999,
        curriculum_p2_end=-1,
        curriculum_p2_max=999,
        # V4.5: stronger task signal
        task_cls_loss_weight=V4_5_TASK_CLS_LOSS_WEIGHT,
    )

    if task_cls_state is not None:
        trainer.task_classifier.load_state_dict(task_cls_state)
        print("  Task classifier weights loaded from V4.2")

    # [9] Schedule preview
    print("\n[9] V4.5 Schedule Preview:")
    print(f"  Warm-start: {'YES' if warm_started else 'NO'}")
    print(f"  Balanced sampling: YES (WeightedRandomSampler by task type)")
    print(f"  task_cls_loss_weight: {V4_5_TASK_CLS_LOSS_WEIGHT}")
    print(f"  Length loss weight: {V4_5_LENGTH_LOSS_WEIGHT}")
    print(f"  Early END penalty: {V4_5_EARLY_END_PENALTY} (threshold={V4_5_EARLY_END_THRESHOLD})")
    for ep in [0, 2, 5, 10, 15, 20, 29]:
        if ep >= V4_5_NUM_EPOCHS:
            break
        tf = trainer.get_tf_ratio(ep)
        ar = trainer.get_ar_ratio(ep)
        print(f"  Epoch {ep+1:3d}: tf_ratio={tf:.3f}, ar_ratio={ar:.0%}")

    # [10] Train
    print("\n[10] Starting training...")
    trainer.train()
    print("\nV4.5 training complete!")


if __name__ == "__main__":
    main()
