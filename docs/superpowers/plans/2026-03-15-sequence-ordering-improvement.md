# L3 Sequence Ordering Improvement Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Improve L3 sequence ordering from Token Accuracy 7.65% to >15% by fixing the AR training regime (V4.3) and optionally adding REINFORCE fine-tuning (V4.3-RL).

**Architecture:** V4.3 reuses the existing `ScheduledSamplingTrainerV4_2` class with updated AR schedule parameters and warm-start from V4.2. V4.3-RL adds a new `REINFORCETrainer` class that fine-tunes with sequence-level rewards (SetF1 + LCS + L2 accuracy) using Self-Critical Sequence Training.

**Tech Stack:** PyTorch, transformers (BERT tokenizer), existing `SemanticMetricsCalculator` for reward computation.

---

## Chunk 1: Config + V4.3 Training Script

### File Structure (Chunk 1)

| File | Action | Responsibility |
|------|--------|---------------|
| `src/gis_recommend/config/transformer_config.py` | **Edit** | Add V4.3 + V4.3-RL config constants |
| `src/gis_recommend/training/train_v4_3.py` | **Create** | V4.3 training with fixed AR schedule + warm-start |

---

### Task 1: Add V4.3 Config Constants

**Files:**
- Modify: `src/gis_recommend/config/transformer_config.py:198` (after V4.2 section)

- [ ] **Step 1: Add V4.3 config block after V4.2 section**

Open `src/gis_recommend/config/transformer_config.py` and add the following block after line 209 (`V4_2_AR_MAX_STEPS = 40`), before the V4.1 section:

```python
# ===================== V4.3 Configuration (Fix AR Training) =====================
V4_3_TRANSFORMER_CHECKPOINT_DIR = OUTPUT_DIR / "transformer_checkpoints_v4_3"
V4_3_TRANSFORMER_CHECKPOINT_DIR.mkdir(exist_ok=True)

# Warm-start from V4.2
V4_3_WARMSTART_PATH = V4_2_TRANSFORMER_CHECKPOINT_DIR / "best_model.pth"

# AR Schedule — key changes from V4.2
V4_3_TF_PHASE_EPOCHS = 3             # was 10: shorter TF-only phase
V4_3_SS_TF_START = 0.5               # was 1.0: start with 50% own-predictions
V4_3_SS_TF_END = 0.0                 # was 0.1: reach pure AR by end
V4_3_AR_RATIO_START = 0.3            # was 0.1: more AR batches from start
V4_3_AR_RATIO_END = 1.0              # was 0.7: all batches AR by end

# Training
V4_3_NUM_EPOCHS = 40
V4_3_WARMUP_EPOCHS = 1               # short warmup for warm-start
V4_3_EARLY_STOPPING_PATIENCE = 18

# ===================== V4.3-RL Configuration (REINFORCE Fine-tuning) =====================
V4_3_RL_CHECKPOINT_DIR = OUTPUT_DIR / "transformer_checkpoints_v4_3_rl"
V4_3_RL_CHECKPOINT_DIR.mkdir(exist_ok=True)

V4_3_RL_LR = 1e-5                    # 10x lower than CE training
V4_3_RL_GRADIENT_CLIP = 0.5          # tighter clipping
V4_3_RL_BATCH_SIZE = 16
V4_3_RL_NUM_SAMPLES = 4              # K=4 sampled sequences per instance
V4_3_RL_CE_WEIGHT = 0.1              # CE regularization weight
V4_3_RL_NUM_EPOCHS = 10
V4_3_RL_EARLY_STOPPING_PATIENCE = 5
```

- [ ] **Step 2: Verify config loads without errors**

Run: `cd E:/02_projects/03_PythonProject/Operator-recommend-system/Algorithm_classification/system_redesign && python -c "from gis_recommend.config.transformer_config import V4_3_TRANSFORMER_CHECKPOINT_DIR, V4_3_WARMSTART_PATH; print('V4.3 config OK')"`

Expected: `V4.3 config OK` (after the standard config print block).

- [ ] **Step 3: Commit**

```bash
git add src/gis_recommend/config/transformer_config.py
git commit -m "config: add V4.3 and V4.3-RL configuration constants"
```

---

### Task 2: Create V4.3 Training Script

**Files:**
- Create: `src/gis_recommend/training/train_v4_3.py`

**Key design decision:** Reuse `ScheduledSamplingTrainerV4_2` directly — pass different config values to its constructor. No need to copy the 1000+ line trainer class. Write only a new `main()` function that handles warm-start loading.

- [ ] **Step 1: Create train_v4_3.py with imports and warm-start loader**

Create `src/gis_recommend/training/train_v4_3.py`:

```python
"""
V4.3 Training: Fixed AR Schedule + Warm-start from V4.2

Key changes from V4.2:
  - TF-only phase: 10 → 3 epochs (or 0 with warm-start)
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
    V4_BERT_UNFREEZE_LAYERS, V4_LABEL_SMOOTHING, V4_GRADIENT_CLIP,
    V4_SS_K,
    V4_1_FREQ_WEIGHT_ALPHA,
    V4_1_LENGTH_LOSS_WEIGHT, V4_1_TASK_CLS_LOSS_WEIGHT,
    V4_TRANSITION_LOSS_WEIGHT,
    V4_1_AR_SAMPLE_TEMPERATURE, V4_1_AR_SAMPLE_TOP_P,
    V4_1_DECODE_REP_PENALTY, V4_1_DECODE_REP_WINDOW,
    V4_CURRICULUM_PHASE1_END, V4_CURRICULUM_PHASE1_MAX_LEN,
    V4_CURRICULUM_PHASE2_END, V4_CURRICULUM_PHASE2_MAX_LEN,
    V4_2_BATCH_SIZE, V4_2_NUM_WORKERS, V4_2_GRADIENT_ACCUM_STEPS,
    V4_2_BERT_LR, V4_2_OTHER_LR, V4_2_GEN_EVAL_BATCHES,
    L3_EMBEDDINGS_PATH,
    # V4.3 specific
    V4_3_TRANSFORMER_CHECKPOINT_DIR, V4_3_WARMSTART_PATH,
    V4_3_TF_PHASE_EPOCHS, V4_3_SS_TF_START, V4_3_SS_TF_END,
    V4_3_AR_RATIO_START, V4_3_AR_RATIO_END,
    V4_3_NUM_EPOCHS, V4_3_WARMUP_EPOCHS, V4_3_EARLY_STOPPING_PATIENCE,
)
from gis_recommend.models.transformer_model_v4 import TaskConditionedL3TransformerModelV4
from gis_recommend.training.train_v4_2 import (
    ScheduledSamplingTrainerV4_2,
    TaskConditionedL3DatasetV4,
    TaskVocabularyBuilder,
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
```

- [ ] **Step 2: Verify imports work**

Run: `cd E:/02_projects/03_PythonProject/Operator-recommend-system/Algorithm_classification/system_redesign && python -c "from gis_recommend.training.train_v4_3 import main; print('train_v4_3 imports OK')"`

Expected: `train_v4_3 imports OK` (after config print block).

- [ ] **Step 3: Fix any import issues**

Common issues:
- `TaskVocabularyBuilder` import — verify it exists in `train_v4_2.py`. If not, find the correct import path by grepping for `class TaskVocabularyBuilder`.

- [ ] **Step 4: Verify AR schedule values are correct**

Run: `cd E:/02_projects/03_PythonProject/Operator-recommend-system/Algorithm_classification/system_redesign && python -c "
from gis_recommend.training.train_v4_3 import *
from gis_recommend.training.train_v4_2 import ScheduledSamplingTrainerV4_2
import torch

# Check V4.3 schedule params
print('V4.3 TF phase epochs:', V4_3_TF_PHASE_EPOCHS)  # expect 3
print('V4.3 SS TF start:', V4_3_SS_TF_START)          # expect 0.5
print('V4.3 SS TF end:', V4_3_SS_TF_END)              # expect 0.0
print('V4.3 AR ratio start:', V4_3_AR_RATIO_START)     # expect 0.3
print('V4.3 AR ratio end:', V4_3_AR_RATIO_END)         # expect 1.0
print('All V4.3 config OK')
"`

Expected: All values match the spec.

- [ ] **Step 5: Commit**

```bash
git add src/gis_recommend/training/train_v4_3.py
git commit -m "feat: add V4.3 training script with fixed AR schedule and warm-start"
```

---

## Chunk 2: V4.3-RL REINFORCE Training Script

### File Structure (Chunk 2)

| File | Action | Responsibility |
|------|--------|---------------|
| `src/gis_recommend/training/train_v4_3_rl.py` | **Create** | REINFORCE fine-tuning with sequence-level rewards |

---

### Task 3: Create V4.3-RL REINFORCE Training Script

**Files:**
- Create: `src/gis_recommend/training/train_v4_3_rl.py`

This script has its own `REINFORCETrainer` class since the training loop is fundamentally different from CE-based training (sample sequences → compute reward → policy gradient).

- [ ] **Step 1: Create the REINFORCE trainer class**

Create `src/gis_recommend/training/train_v4_3_rl.py`:

```python
"""
V4.3-RL Training: REINFORCE Fine-tuning with Sequence-Level Rewards

Method: Self-Critical Sequence Training (SCST)
  - Sample K=4 sequences via nucleus sampling
  - Greedy decode 1 baseline sequence
  - Reward = 0.5*SetF1 + 0.3*LCS_ratio + 0.2*L2_accuracy
  - Loss = -mean((R_k - R_baseline) * log_prob(seq_k)) + 0.1 * CE_loss

Usage:
    python -m gis_recommend.training.train_v4_3_rl
"""

from __future__ import annotations

import json
import math
import random
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader
from tqdm import tqdm
from transformers import BertTokenizer

# ── project imports ──────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from gis_recommend.config.transformer_config import (
    DEVICE, RANDOM_SEED, OUTPUT_DIR, TOTAL_VOCAB_SIZE, VOCAB_SIZE,
    V4_LABELED_WORKFLOWS_PATH, V4_TASK_TYPE_VOCAB_PATH,
    V4_D_MODEL, V4_N_HEADS, V4_N_LAYERS, V4_D_FF, V4_DROPOUT,
    V4_MAX_SEQ_LENGTH, V4_MAX_MEMORY_TOKENS,
    V4_BERT_UNFREEZE_LAYERS, V4_LABEL_SMOOTHING,
    V4_1_FREQ_WEIGHT_ALPHA,
    V4_2_NUM_WORKERS,
    L3_EMBEDDINGS_PATH,
    # V4.3-RL specific
    V4_3_RL_CHECKPOINT_DIR, V4_3_RL_LR, V4_3_RL_GRADIENT_CLIP,
    V4_3_RL_BATCH_SIZE, V4_3_RL_NUM_SAMPLES, V4_3_RL_CE_WEIGHT,
    V4_3_RL_NUM_EPOCHS, V4_3_RL_EARLY_STOPPING_PATIENCE,
    V4_3_TRANSFORMER_CHECKPOINT_DIR,
)
from gis_recommend.models.transformer_model_v4 import TaskConditionedL3TransformerModelV4
from gis_recommend.training.train_v4_2 import (
    TaskConditionedL3DatasetV4,
    TaskVocabularyBuilder,
    compute_token_freq_weights,
    load_or_create_splits,
    set_seed,
)
from gis_recommend.evaluation.semantic_metrics import (
    SemanticMetricsCalculator,
)

# Special tokens
PAD_INDEX = VOCAB_SIZE + 0   # 350
UNK_INDEX = VOCAB_SIZE + 1   # 351
START_INDEX = VOCAB_SIZE + 2 # 352
END_INDEX = VOCAB_SIZE + 3   # 353

HIERARCHY_CSV_PATH = PROJECT_ROOT / "classification_hierarchy.csv"
ID_MAPPINGS_PATH = OUTPUT_DIR / "id_mappings.json"


class REINFORCETrainer:
    """SCST-based REINFORCE fine-tuning for L3 sequence generation.

    Samples K sequences per training instance, computes sequence-level
    reward (SetF1 + LCS + L2Accuracy), uses greedy decode as SCST baseline,
    and applies policy gradient with CE regularization.
    """

    def __init__(
        self,
        model: TaskConditionedL3TransformerModelV4,
        train_loader: DataLoader,
        val_loader: DataLoader,
        metrics_calculator: SemanticMetricsCalculator,
        device: torch.device = DEVICE,
        checkpoint_dir: Path = V4_3_RL_CHECKPOINT_DIR,
        lr: float = V4_3_RL_LR,
        gradient_clip: float = V4_3_RL_GRADIENT_CLIP,
        num_samples: int = V4_3_RL_NUM_SAMPLES,
        ce_weight: float = V4_3_RL_CE_WEIGHT,
        num_epochs: int = V4_3_RL_NUM_EPOCHS,
        patience: int = V4_3_RL_EARLY_STOPPING_PATIENCE,
        sample_temp: float = 0.8,
        sample_top_p: float = 0.9,
        max_decode_len: int = 30,
    ):
        self.model = model.to(device)
        self.train_loader = train_loader
        self.val_loader = val_loader
        self.calc = metrics_calculator
        self.device = device
        self.num_samples = num_samples
        self.ce_weight = ce_weight
        self.num_epochs = num_epochs
        self.patience = patience
        self.sample_temp = sample_temp
        self.sample_top_p = sample_top_p
        self.max_decode_len = max_decode_len

        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

        # Freeze BERT entirely — only train decoder
        for name, param in self.model.named_parameters():
            if name.startswith("text_encoder.bert."):
                param.requires_grad = False

        trainable = [p for p in self.model.parameters() if p.requires_grad]
        self.optimizer = torch.optim.AdamW(trainable, lr=lr, weight_decay=0.01)
        self.gradient_clip = gradient_clip

        # CE loss for regularization
        self.ce_criterion = nn.CrossEntropyLoss(
            ignore_index=PAD_INDEX, label_smoothing=V4_LABEL_SMOOTHING,
        )

    # ── sequence generation ──────────────────────────────────────

    def _encode_context(self, batch):
        """Encode BERT memory and condition vector (shared across all samples)."""
        text_input_ids = batch['text_input_ids'].to(self.device)
        text_attention_mask = batch['text_attention_mask'].to(self.device)
        task_type_ids = batch['task_type_id'].to(self.device)

        with torch.no_grad():
            memory_raw, memory_mask, text_pooled = self.model.text_encoder(
                text_input_ids, text_attention_mask
            )
            memory = self.model.memory_positional_encoding(
                self.model.text_projection(memory_raw)
            )
            condition = self.model._fuse_condition(task_type_ids, text_pooled)

        return memory, memory_mask, condition

    def _generate_sequence(self, memory, memory_mask, condition, greedy=False):
        """Generate a single sequence for each item in the batch.

        Args:
            greedy: If True, use argmax. If False, use nucleus sampling.

        Returns:
            tokens: [B, max_len] generated token IDs (padded)
            log_probs: [B, max_len] log probabilities of selected tokens
            lengths: [B] actual sequence lengths (including END)
        """
        B = memory.size(0)
        decoder_input = torch.full((B, 1), START_INDEX, dtype=torch.long,
                                   device=self.device)
        all_log_probs = []
        all_tokens = []
        finished = torch.zeros(B, dtype=torch.bool, device=self.device)
        lengths = torch.zeros(B, dtype=torch.long, device=self.device)

        gamma_input = self.model.input_film_gamma(condition).unsqueeze(1)
        beta_input = self.model.input_film_beta(condition).unsqueeze(1)
        memory_pad_mask = ~memory_mask if memory_mask is not None else None

        for step in range(self.max_decode_len):
            tok_emb = self.model.token_embedding(decoder_input)
            tok_emb = gamma_input * tok_emb + beta_input
            tok_emb = self.model.positional_encoding(tok_emb)

            cur_len = tok_emb.size(1)
            causal_mask = self.model._generate_causal_mask(cur_len, self.device)

            x = tok_emb
            for layer in self.model.decoder_layers:
                x = layer(x, memory, condition,
                          tgt_mask=causal_mask,
                          memory_key_padding_mask=memory_pad_mask)
            x = self.model.decoder_norm(x)
            logits = self.model.output_projection(x[:, -1, :])  # [B, V]

            # Block special tokens
            logits[:, PAD_INDEX] = float('-inf')
            logits[:, UNK_INDEX] = float('-inf')
            logits[:, START_INDEX] = float('-inf')
            if step < 3:
                logits[:, END_INDEX] = float('-inf')

            # Select token
            log_prob_dist = F.log_softmax(logits, dim=-1)

            if greedy:
                next_token = logits.argmax(dim=-1)
            else:
                # Nucleus sampling
                scaled_logits = logits / self.sample_temp
                sorted_logits, sorted_indices = torch.sort(
                    scaled_logits, descending=True, dim=-1)
                cumulative_probs = torch.cumsum(
                    F.softmax(sorted_logits, dim=-1), dim=-1)
                sorted_mask = (cumulative_probs
                               - F.softmax(sorted_logits, dim=-1)) >= self.sample_top_p
                sorted_logits[sorted_mask] = float('-inf')
                probs = F.softmax(sorted_logits, dim=-1)
                sampled_idx = torch.multinomial(probs, num_samples=1).squeeze(-1)
                next_token = sorted_indices.gather(-1, sampled_idx.unsqueeze(-1)).squeeze(-1)

            # Gather log prob of selected token
            token_log_prob = log_prob_dist.gather(1, next_token.unsqueeze(1)).squeeze(1)

            # Mask finished sequences
            token_log_prob = token_log_prob.masked_fill(finished, 0.0)
            next_token_masked = next_token.masked_fill(finished, PAD_INDEX)

            all_tokens.append(next_token_masked)
            all_log_probs.append(token_log_prob)

            # Update finished and lengths
            just_ended = (next_token == END_INDEX) & ~finished
            lengths += (~finished).long()
            finished = finished | just_ended

            # Append to decoder input
            decoder_input = torch.cat(
                [decoder_input, next_token.unsqueeze(1)], dim=1)

            if finished.all():
                break

        tokens = torch.stack(all_tokens, dim=1)       # [B, steps]
        log_probs = torch.stack(all_log_probs, dim=1)  # [B, steps]
        return tokens, log_probs, lengths

    # ── reward computation ───────────────────────────────────────

    def _compute_reward(self, pred_tokens: list[int], ref_tokens: list[int]) -> float:
        """Compute sequence-level reward: 0.5*SetF1 + 0.3*LCS + 0.2*L2Acc."""
        set_f1 = self.calc.set_f1(pred_tokens, ref_tokens)
        lcs = self.calc.lcs_ratio(pred_tokens, ref_tokens)
        l2_acc = self.calc.l2_accuracy(pred_tokens, ref_tokens)
        return 0.5 * set_f1 + 0.3 * lcs + 0.2 * l2_acc

    # ── training step ────────────────────────────────────────────

    def _train_step(self, batch):
        """One training step: sample K sequences, compute REINFORCE + CE loss."""
        self.model.train()

        # Encode shared context
        memory, memory_mask, condition = self._encode_context(batch)
        target_ids = batch['target_ids'].to(self.device)
        ref_seqs = batch['target_ids'].tolist()  # [B, T] as lists

        B = memory.size(0)

        # 1. Greedy baseline (no grad)
        with torch.no_grad():
            baseline_tokens, _, baseline_lengths = self._generate_sequence(
                memory, memory_mask, condition, greedy=True)

        # 2. Compute baseline rewards
        baseline_rewards = []
        for b in range(B):
            pred = baseline_tokens[b, :baseline_lengths[b]].tolist()
            ref = ref_seqs[b]
            baseline_rewards.append(self._compute_reward(pred, ref))
        baseline_rewards = torch.tensor(baseline_rewards, device=self.device)  # [B]

        # 3. Sample K sequences and accumulate REINFORCE loss
        total_rl_loss = torch.tensor(0.0, device=self.device)
        total_reward = 0.0

        for k in range(self.num_samples):
            sample_tokens, sample_log_probs, sample_lengths = \
                self._generate_sequence(memory, memory_mask, condition, greedy=False)

            # Compute rewards for this sample
            sample_rewards = []
            for b in range(B):
                pred = sample_tokens[b, :sample_lengths[b]].tolist()
                ref = ref_seqs[b]
                sample_rewards.append(self._compute_reward(pred, ref))
            sample_rewards = torch.tensor(sample_rewards, device=self.device)  # [B]

            total_reward += sample_rewards.mean().item()

            # REINFORCE: advantage = reward - baseline
            advantage = sample_rewards - baseline_rewards  # [B]

            # Sequence log prob = sum of token log probs
            # Mask padding positions
            max_steps = sample_log_probs.size(1)
            step_mask = torch.arange(max_steps, device=self.device).unsqueeze(0) < \
                        sample_lengths.unsqueeze(1)  # [B, steps]
            seq_log_prob = (sample_log_probs * step_mask.float()).sum(dim=1)  # [B]

            # REINFORCE loss = -advantage * log_prob (negative because we minimize)
            rl_loss_k = -(advantage.detach() * seq_log_prob).mean()
            total_rl_loss = total_rl_loss + rl_loss_k

        avg_rl_loss = total_rl_loss / self.num_samples
        avg_reward = total_reward / self.num_samples

        # 4. CE regularization loss (teacher forcing on the same batch)
        input_ids = batch['input_ids'].to(self.device)
        task_type_ids = batch['task_type_id'].to(self.device)
        text_input_ids = batch['text_input_ids'].to(self.device)
        text_attention_mask = batch['text_attention_mask'].to(self.device)
        attention_mask = batch['attention_mask'].to(self.device)

        logits, _ = self.model(
            input_ids, task_type_ids, text_input_ids, text_attention_mask,
            attention_mask=attention_mask,
        )
        ce_loss = self.ce_criterion(
            logits.view(-1, logits.size(-1)), target_ids.view(-1))

        # 5. Combined loss
        total_loss = avg_rl_loss + self.ce_weight * ce_loss

        # Backward
        self.optimizer.zero_grad()
        total_loss.backward()
        torch.nn.utils.clip_grad_norm_(
            [p for p in self.model.parameters() if p.requires_grad],
            self.gradient_clip,
        )
        self.optimizer.step()

        return {
            'total_loss': total_loss.item(),
            'rl_loss': avg_rl_loss.item(),
            'ce_loss': ce_loss.item(),
            'reward': avg_reward,
            'baseline_reward': baseline_rewards.mean().item(),
        }

    # ── validation ───────────────────────────────────────────────

    @torch.no_grad()
    def validate(self):
        """Compute mean reward on validation set via greedy decode."""
        self.model.eval()
        total_reward = 0.0
        n_samples = 0

        for batch in self.val_loader:
            memory, memory_mask, condition = self._encode_context(batch)
            tokens, _, lengths = self._generate_sequence(
                memory, memory_mask, condition, greedy=True)

            ref_seqs = batch['target_ids'].tolist()
            B = tokens.size(0)

            for b in range(B):
                pred = tokens[b, :lengths[b]].tolist()
                ref = ref_seqs[b]
                total_reward += self._compute_reward(pred, ref)
                n_samples += 1

        return total_reward / max(n_samples, 1)

    # ── training loop ────────────────────────────────────────────

    def train(self):
        print("=" * 80)
        print("V4.3-RL: REINFORCE Fine-tuning (SCST)")
        print("=" * 80)
        print(f"  Device: {self.device}")
        print(f"  K={self.num_samples} samples, CE_weight={self.ce_weight}")
        print(f"  LR={self.optimizer.param_groups[0]['lr']:.1e}, "
              f"Clip={self.gradient_clip}")
        print(f"  Batch: {self.train_loader.batch_size}")
        print(f"  Epochs: {self.num_epochs}, Patience: {self.patience}")
        print("=" * 80)

        best_reward = -1.0
        epochs_no_improve = 0
        history = []

        for epoch in range(self.num_epochs):
            t0 = time.time()
            self.model.train()

            epoch_totals = {
                'total_loss': 0, 'rl_loss': 0, 'ce_loss': 0,
                'reward': 0, 'baseline_reward': 0,
            }
            n_batches = 0

            pbar = tqdm(self.train_loader,
                        desc=f"Epoch {epoch+1}/{self.num_epochs}")
            for batch in pbar:
                losses = self._train_step(batch)
                for k in epoch_totals:
                    epoch_totals[k] += losses[k]
                n_batches += 1
                pbar.set_postfix({
                    'rl': f"{losses['rl_loss']:.4f}",
                    'R': f"{losses['reward']:.3f}",
                })

            avg = {k: v / max(n_batches, 1) for k, v in epoch_totals.items()}
            elapsed = time.time() - t0

            # Validate
            val_reward = self.validate()

            print(f"\n  Epoch {epoch+1}/{self.num_epochs} ({elapsed:.0f}s)")
            print(f"  Train: RL={avg['rl_loss']:.4f} CE={avg['ce_loss']:.4f} "
                  f"Total={avg['total_loss']:.4f}")
            print(f"  Train R={avg['reward']:.4f} (baseline={avg['baseline_reward']:.4f})")
            print(f"  Val Reward={val_reward:.4f}")

            record = {
                'epoch': epoch + 1, **avg,
                'val_reward': val_reward, 'time': elapsed,
            }
            history.append(record)

            # Checkpointing on validation reward
            if val_reward > best_reward:
                best_reward = val_reward
                epochs_no_improve = 0
                ckpt_path = self.checkpoint_dir / "best_model.pth"
                torch.save({
                    'model_state_dict': self.model.state_dict(),
                    'epoch': epoch + 1,
                    'val_reward': val_reward,
                }, ckpt_path)
                print(f"  [BEST] Saved: {ckpt_path} (reward={val_reward:.4f})")
            else:
                epochs_no_improve += 1
                print(f"  No improvement for {epochs_no_improve} epoch(s)")

            if epochs_no_improve >= self.patience:
                print(f"\nEarly stopping at epoch {epoch+1}")
                break

        # Save history
        hist_path = self.checkpoint_dir / "training_history_v4_3_rl.json"
        with open(hist_path, 'w', encoding='utf-8') as f:
            json.dump(history, f, indent=2)
        print(f"\nHistory saved: {hist_path}")

        return history


# ═════════════════════════════════════════════════════════════════
# Main
# ═════════════════════════════════════════════════════════════════
def main():
    print("=" * 80)
    print("V4.3-RL: REINFORCE Fine-tuning for Sequence Ordering")
    print("=" * 80)

    if not torch.cuda.is_available():
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

    # [2] Task type vocabulary
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

    # [3] Split dataset
    print("\n[3] Splitting dataset...")
    split_path = OUTPUT_DIR / "dataset_splits_v4.json"
    splits = load_or_create_splits(workflows, split_path, seed=RANDOM_SEED)
    train_wf = [workflows[i] for i in splits['train_indices']]
    val_wf = [workflows[i] for i in splits['val_indices']]

    # [4] Datasets
    print("\n[4] Creating datasets...")
    train_dataset = TaskConditionedL3DatasetV4(train_wf, task_vocab_builder, bert_tokenizer)
    val_dataset = TaskConditionedL3DatasetV4(val_wf, task_vocab_builder, bert_tokenizer)
    train_loader = DataLoader(train_dataset, batch_size=V4_3_RL_BATCH_SIZE,
                              shuffle=True, num_workers=V4_2_NUM_WORKERS)
    val_loader = DataLoader(val_dataset, batch_size=V4_3_RL_BATCH_SIZE,
                            shuffle=False, num_workers=V4_2_NUM_WORKERS)

    # [5] Create model + load V4.3 checkpoint
    print("\n[5] Creating model and loading V4.3 checkpoint...")
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
        freeze_bert=True,   # fully frozen for RL
        bert_unfreeze_layers=0,
    )

    v43_ckpt = V4_3_TRANSFORMER_CHECKPOINT_DIR / "best_model.pth"
    if not v43_ckpt.exists():
        print(f"  [ERROR] V4.3 checkpoint not found: {v43_ckpt}")
        print(f"  Run V4.3 training first: python -m gis_recommend.training.train_v4_3")
        return

    ckpt = torch.load(v43_ckpt, map_location=DEVICE, weights_only=True)
    model.load_state_dict(ckpt['model_state_dict'])
    print(f"  Loaded V4.3 checkpoint (epoch {ckpt.get('epoch', '?')})")

    counts = model.count_parameters()
    print(f"  Params: {counts['trainable']/1e6:.1f}M trainable (BERT frozen)")

    # [6] Load SemanticMetricsCalculator
    print("\n[6] Loading metrics calculator...")
    with open(ID_MAPPINGS_PATH, 'r', encoding='utf-8') as f:
        id_mappings = json.load(f)
    l3_map = id_mappings.get('l3', {})
    id_to_l3_code = {int(v): k for k, v in l3_map.items()}

    calc = SemanticMetricsCalculator(
        l3_embeddings_path=L3_EMBEDDINGS_PATH,
        hierarchy_csv_path=HIERARCHY_CSV_PATH,
        id_to_l3_code=id_to_l3_code,
    )
    print(f"  L3→L2 mappings: {len(calc.l3_to_l2)}")
    print(f"  Embeddings shape: {calc.embeddings.shape}")

    # [7] Create trainer
    print("\n[7] Creating REINFORCE trainer...")
    trainer = REINFORCETrainer(
        model=model,
        train_loader=train_loader,
        val_loader=val_loader,
        metrics_calculator=calc,
    )

    # [8] Train
    print("\n[8] Starting REINFORCE training...")
    trainer.train()
    print("\nV4.3-RL training complete!")


if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Verify imports work**

Run: `cd E:/02_projects/03_PythonProject/Operator-recommend-system/Algorithm_classification/system_redesign && python -c "from gis_recommend.training.train_v4_3_rl import main; print('train_v4_3_rl imports OK')"`

Expected: `train_v4_3_rl imports OK` (after config print block).

- [ ] **Step 3: Commit**

```bash
git add src/gis_recommend/training/train_v4_3_rl.py
git commit -m "feat: add V4.3-RL REINFORCE fine-tuning script"
```

---

## Execution Order

1. **Task 1** → add config (prerequisite for both scripts)
2. **Task 2** → create train_v4_3.py (Phase 1)
3. **Task 3** → create train_v4_3_rl.py (Phase 2, depends on V4.3 checkpoint)

### Running the training

After implementation:

```bash
cd E:/02_projects/03_PythonProject/Operator-recommend-system/Algorithm_classification/system_redesign

# Phase 1: V4.3 training (~60-90 min on GPU)
python -m gis_recommend.training.train_v4_3

# Evaluate V4.3
python scripts/evaluate_system.py --skip-qgis

# Phase 2 (if Token Accuracy < 25%): REINFORCE fine-tuning
python -m gis_recommend.training.train_v4_3_rl

# Re-evaluate
python scripts/evaluate_system.py --skip-qgis
```
