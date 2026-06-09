# -*- coding: utf-8 -*-
"""
Set Predictor V3 训练脚本 — Rich Cross-Attention + Self-Attention + 二阶段损失

V3 架构: BERT full_seq + FiLM + Token-Token Self-Attention
损失: BCE(binary) + CE(count)
评估: 记录 soft prior 阈值指标，同时输出 0.5 与多阈值参考

用法:
    python -m gis_recommend.training.train_set_predictor_v3
"""

import json
import random
import hashlib
import time
from collections import Counter
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader, WeightedRandomSampler
from transformers import BertTokenizer
from tqdm import tqdm

from gis_recommend.config.transformer_config import (
    OUTPUT_DIR, DEVICE, VOCAB_SIZE, SPECIAL_TOKENS,
    V4_LABELED_WORKFLOWS_PATH, V4_TASK_TYPE_VOCAB_PATH,
    SET_PREDICTOR_CHECKPOINT_DIR, SET_PREDICTOR_ACTIVE_TOKENS_PATH,
    SET_PREDICTOR_D_CONDITION, SET_PREDICTOR_D_HIDDEN,
    SET_PREDICTOR_DROPOUT, SET_PREDICTOR_BERT_UNFREEZE_LAYERS,
    SET_PREDICTOR_BATCH_SIZE, SET_PREDICTOR_LR, SET_PREDICTOR_BERT_LR,
    SET_PREDICTOR_NUM_EPOCHS, SET_PREDICTOR_WARMUP_EPOCHS,
    SET_PREDICTOR_NUM_COUNT_CLASSES,
    SET_PREDICTOR_NUM_ATTN_HEADS, SET_PREDICTOR_SOFT_PRIOR_THRESHOLD,
    SET_PREDICTOR_CONFIDENCE_THRESHOLD,
    SET_PREDICTOR_NUM_SELF_ATTN_LAYERS, SET_PREDICTOR_SELF_ATTN_DIM_FF,
)
from gis_recommend.models.set_predictor_v3 import L3SetPredictor
from gis_recommend.training.splits import load_or_create_valid_splits

# Special token IDs
SPECIAL_TOKEN_MAP = {v: VOCAB_SIZE + abs(v) - 1 for v in SPECIAL_TOKENS.values()}
PAD_INDEX = SPECIAL_TOKEN_MAP[-1]
UNK_INDEX = SPECIAL_TOKEN_MAP[-2]
START_INDEX = SPECIAL_TOKEN_MAP[-3]
END_INDEX = SPECIAL_TOKEN_MAP[-4]

SPECIAL_IDS = {PAD_INDEX, UNK_INDEX, START_INDEX, END_INDEX}
CHECKPOINT_SCHEMA = "gis_recommend.checkpoint.v1"


def _make_task_key(
    task_type: str = "",
    task_name: str = "",
    task_description: str = "",
) -> str:
    return json.dumps(
        {
            "task_type": task_type or "",
            "task_name": task_name or "",
            "task_description": task_description or "",
        },
        ensure_ascii=False,
        sort_keys=True,
    )


def _set_predictor_model_config(model, num_task_types: int) -> dict:
    return {
        'arch_version': 'v3',
        'num_task_types': num_task_types,
        'd_condition': SET_PREDICTOR_D_CONDITION,
        'd_hidden': SET_PREDICTOR_D_HIDDEN,
        'head_hidden_dim': model.head_hidden_dim,
        'num_count_classes': SET_PREDICTOR_NUM_COUNT_CLASSES,
        'bert_unfreeze_layers': SET_PREDICTOR_BERT_UNFREEZE_LAYERS,
        'dropout': SET_PREDICTOR_DROPOUT,
        'num_attn_heads': SET_PREDICTOR_NUM_ATTN_HEADS,
        'num_self_attn_layers': SET_PREDICTOR_NUM_SELF_ATTN_LAYERS,
        'self_attn_dim_feedforward': SET_PREDICTOR_SELF_ATTN_DIM_FF,
        'use_rich_cross_attn': True,
    }


def _build_set_predictor_checkpoint_payload(
    *,
    model_state_dict,
    config,
    active_token_ids,
    epoch,
    runtime_profile,
    dataset_identity,
    metric_bundle,
    provenance,
):
    """Build a checkpoint snapshot. Only model_state_dict is load authority."""
    return {
        'checkpoint_schema': CHECKPOINT_SCHEMA,
        'model_state_dict': model_state_dict,
        'config': config,
        'active_token_ids': active_token_ids,
        'epoch': epoch,
        'runtime_profile': runtime_profile,
        'dataset_identity': dataset_identity,
        'metric_bundle': metric_bundle,
        'provenance': provenance,
    }


# ═══════════════════════════════════════════════════════════════════════
#  Active Token Discovery
# ═══════════════════════════════════════════════════════════════════════

def discover_active_tokens(workflows: list, mr_registry: dict | None = None) -> list:
    """Find all L3 token IDs that appear in the training data (excl. special tokens).

    If an MR registry is provided, also include tokens that appear in verified
    variant references for the same training tasks so the coverage prior can
    learn alternate valid operator sets.
    """
    active = set()
    for wf in workflows:
        for t in wf["l3_sequence"]:
            if 0 <= t < VOCAB_SIZE:
                active.add(t)
        if mr_registry:
            meta = wf.get("task_metadata", {}) or {}
            key = json.dumps(
                {
                    "task_type": meta.get("task_type", "") or "",
                    "task_name": meta.get("task_name", "") or "",
                    "task_description": meta.get("task_description", "") or "",
                },
                ensure_ascii=False,
                sort_keys=True,
            )
            entry = mr_registry.get(key)
            if entry:
                for ref in entry.get("references", []):
                    for t in ref:
                        if 0 <= t < VOCAB_SIZE:
                            active.add(t)
    active = sorted(active)
    print(f"  Active tokens: {len(active)} / {VOCAB_SIZE}")
    return active


def save_active_tokens(active_token_ids: list, path: Path):
    with open(path, 'w', encoding='utf-8') as f:
        json.dump({'active_token_ids': active_token_ids, 'count': len(active_token_ids)}, f)
    print(f"  Saved active tokens to {path}")


# ═══════════════════════════════════════════════════════════════════════
#  Dataset
# ═══════════════════════════════════════════════════════════════════════

class SetPredictorDataset(Dataset):
    """每个样本返回:
        task_type_id: scalar int
        text_input_ids: [128] int
        text_attention_mask: [128] int
        binary_targets: [N] float, 0.0 or 1.0 (present/absent)
        count_targets: [N] long, 值 ∈ {0,1,2} → 对应 count {1,2,3+}
                       只在 binary_targets=1 的位置有意义
    """

    def __init__(self, workflows: list, active_token_ids: list,
                 task_type_vocab: dict, bert_tokenizer,
                 max_text_length: int = 128, num_count_classes: int = 3,
                 mr_registry: dict | None = None):
        self.workflows = workflows
        self.bert_tokenizer = bert_tokenizer
        self.max_text_length = max_text_length
        self.num_count_classes = num_count_classes
        self.task_type_to_id = task_type_vocab['task_type_to_id']
        self.token_to_active_idx = {tid: i for i, tid in enumerate(active_token_ids)}
        self.num_active = len(active_token_ids)
        self._text_cache = {}
        self.mr_registry = mr_registry or {}
        self._mr_token_to_idx = {}

    def __len__(self):
        return len(self.workflows)

    def __getitem__(self, idx):
        wf = self.workflows[idx]
        meta = wf.get('task_metadata', {}) or {}
        task_type = meta.get('task_type', 'Unknown')
        task_name = meta.get('task_name', '') or ''
        task_desc = meta.get('task_description', '') or ''

        task_type_id = self.task_type_to_id.get(task_type, 0)
        text = f"{task_name} {task_desc}".strip() or "unknown task"
        text_ids, text_mask = self._encode_text(text)

        # Count occurrences per active token. If an MR registry is present,
        # union the verified equivalent references so multi-solution operators
        # can appear as positive coverage targets.
        counts = Counter()
        references = [wf["l3_sequence"]]
        if self.mr_registry:
            task_key = _make_task_key(
                meta.get("task_type", ""),
                meta.get("task_name", ""),
                meta.get("task_description", ""),
            )
            entry = self.mr_registry.get(task_key)
            if entry and len(entry.get("references", [])) > 1:
                references.extend(entry["references"])

        for ref in references:
            ref_counts = Counter()
            for t in ref:
                if t in self.token_to_active_idx:
                    ref_counts[t] += 1
            for token_id, cnt in ref_counts.items():
                counts[token_id] = max(counts[token_id], cnt)

        binary_targets = torch.zeros(self.num_active, dtype=torch.float)
        count_targets = torch.zeros(self.num_active, dtype=torch.long)
        for token_id, cnt in counts.items():
            active_idx = self.token_to_active_idx[token_id]
            binary_targets[active_idx] = 1.0
            # count class: count=1→0, count=2→1, ..., count>=num_count_classes→last class
            count_targets[active_idx] = min(cnt, self.num_count_classes) - 1

        return {
            'task_type_id': torch.tensor(task_type_id, dtype=torch.long),
            'text_input_ids': text_ids,
            'text_attention_mask': text_mask,
            'binary_targets': binary_targets,
            'count_targets': count_targets,
        }

    def _encode_text(self, text: str):
        key = hashlib.md5(text.encode()).hexdigest()
        if key in self._text_cache:
            return self._text_cache[key]
        enc = self.bert_tokenizer(
            text, max_length=self.max_text_length, padding='max_length',
            truncation=True, return_tensors='pt',
        )
        ids = enc['input_ids'].squeeze(0)
        mask = enc['attention_mask'].squeeze(0)
        self._text_cache[key] = (ids, mask)
        return ids, mask


# ═══════════════════════════════════════════════════════════════════════
#  Two-Stage Loss
# ═══════════════════════════════════════════════════════════════════════

class TwoStageLoss(nn.Module):
    """Binary presence loss + conditional count loss.

    binary_loss = BCE(binary_logits, binary_targets, pos_weight)
    count_loss  = CE(count_logits[present_mask], count_targets[present_mask])
    total = binary_loss + count_weight * count_loss
    """

    def __init__(self, pos_weight: float = 8.0, count_weight: float = 0.5):
        super().__init__()
        self.register_buffer('pos_weight', torch.tensor([pos_weight]))
        self.count_weight = count_weight

    def forward(self, binary_logits, count_logits, binary_targets, count_targets):
        """
        Args:
            binary_logits: [B, N]
            count_logits:  [B, N, 3]
            binary_targets: [B, N] float 0/1
            count_targets:  [B, N] long {0,1,2}
        """
        # Binary loss
        binary_loss = F.binary_cross_entropy_with_logits(
            binary_logits, binary_targets,
            pos_weight=self.pos_weight.expand_as(binary_logits),
        )

        # Count loss: only on present tokens
        present_mask = binary_targets > 0.5  # [B, N]
        if present_mask.any():
            # Flatten masked positions
            count_logits_masked = count_logits[present_mask]  # [K, 3]
            count_targets_masked = count_targets[present_mask]  # [K]
            count_loss = F.cross_entropy(count_logits_masked, count_targets_masked)
        else:
            count_loss = torch.tensor(0.0, device=binary_logits.device)

        total = binary_loss + self.count_weight * count_loss
        return total, binary_loss.item(), count_loss.item()


# ═══════════════════════════════════════════════════════════════════════
#  Evaluation Metrics
# ═══════════════════════════════════════════════════════════════════════

def compute_metrics(binary_logits: torch.Tensor, count_logits: torch.Tensor,
                    binary_targets: torch.Tensor, count_targets: torch.Tensor,
                    threshold: float = 0.5) -> dict:
    """Set Predictor metrics: threshold, coverage (topk recall), calibration.

    Uses sigmoid(binary_logits) for probability-based metrics.
    """
    binary_probs = torch.sigmoid(binary_logits)  # [B, N]
    pred_present = (binary_probs > threshold)
    true_present = (binary_targets > 0.5)
    B, N = binary_probs.shape

    # ---- Per-sample TP/FP/FN ----
    tp = (pred_present & true_present).float().sum(dim=1)
    fp = (pred_present & ~true_present).float().sum(dim=1)
    fn = (~pred_present & true_present).float().sum(dim=1)

    precision = tp / (tp + fp + 1e-8)
    recall = tp / (tp + fn + 1e-8)
    f1_per = 2 * precision * recall / (precision + recall + 1e-8)
    f1_per = torch.where((tp + fp + fn) > 0, f1_per, torch.zeros_like(f1_per))

    # ---- Set-level Jaccard & Exact Match ----
    intersection = tp
    union = (pred_present | true_present).float().sum(dim=1)
    set_jaccard = intersection / (union + 1e-8)
    set_jaccard = torch.where(union > 0, set_jaccard, torch.ones_like(set_jaccard))
    exact_set = (pred_present == true_present).all(dim=1).float()

    # ---- Set sizes ----
    pred_sizes = pred_present.float().sum(dim=1)  # [B]
    true_sizes = true_present.float().sum(dim=1)  # [B]
    avg_pred_size = pred_sizes.mean().item()
    mean_true_size = true_sizes.mean().item()
    pred_size_ratio = (pred_sizes / (true_sizes + 1e-8)).mean().item()
    zero_pred_rate = (pred_sizes == 0).float().mean().item()
    small_pred_rate_lt2 = (pred_sizes < 2).float().mean().item()
    under_pred_rate = (pred_sizes < true_sizes * 0.5).float().mean().item()
    over_pred_rate = (pred_sizes > true_sizes * 2.0).float().mean().item()

    # ---- Top-K recall: how many true tokens are in top-K predictions ----
    topk_recalls = {}
    for k in (3, 5, 8, 10):
        topk_mask = torch.zeros_like(binary_probs)
        # Per-sample top-K by binary probability
        _, topk_idx = binary_probs.topk(min(k, N), dim=1)
        for b in range(B):
            topk_mask[b, topk_idx[b]] = 1.0
        topk_tp = (topk_mask * true_present.float()).sum(dim=1)
        topk_rec = topk_tp / (true_sizes + 1e-8)
        topk_rec = torch.where(true_sizes > 0, topk_rec, torch.ones_like(topk_rec))
        topk_recalls[f'topk_recall@{k}'] = topk_rec.mean().item()

    # ---- Count accuracy on correctly identified present tokens ----
    both_present = pred_present & true_present
    if both_present.any():
        pred_count_class = count_logits.argmax(dim=-1)  # [B, N]
        count_correct = (pred_count_class[both_present] == count_targets[both_present])
        count_acc = count_correct.float().mean().item()
        pred_count_val = pred_count_class[both_present].float() + 1
        true_count_val = count_targets[both_present].float() + 1
        count_mae = (pred_count_val - true_count_val).abs().mean().item()
    else:
        count_acc = 0.0
        count_mae = 0.0

    # ---- Calibration: Brier score & ECE ----
    brier = ((binary_probs - binary_targets.float()) ** 2).mean().item()
    # ECE: expected calibration error (10 bins)
    n_bins = 10
    ece = 0.0
    for bin_idx in range(n_bins):
        lo = bin_idx / n_bins
        hi = (bin_idx + 1) / n_bins
        bin_mask = (binary_probs >= lo) & (binary_probs < hi)
        if bin_mask.sum() < 1:
            continue
        bin_conf = binary_probs[bin_mask].mean().item()
        bin_acc = binary_targets[bin_mask].float().mean().item()
        bin_weight = bin_mask.float().sum().item() / (B * N)
        ece += bin_weight * abs(bin_conf - bin_acc)

    return {
        # Threshold metrics
        'set_f1': f1_per.mean().item(),
        'set_precision': precision.mean().item(),
        'set_recall': recall.mean().item(),
        'set_jaccard': set_jaccard.mean().item(),
        'exact_set_match': exact_set.mean().item(),
        # Size diagnostics
        'avg_pred_size': avg_pred_size,
        'mean_true_set_size': mean_true_size,
        'pred_size_ratio': pred_size_ratio,
        'zero_pred_rate': zero_pred_rate,
        'small_pred_rate_lt2': small_pred_rate_lt2,
        'under_prediction_rate': under_pred_rate,
        'over_prediction_rate': over_pred_rate,
        # Coverage (top-k recall)
        **topk_recalls,
        # Count
        'count_acc': count_acc,
        'count_mae': count_mae,
        # Calibration
        'brier_score': brier,
        'ece': ece,
    }


# ═══════════════════════════════════════════════════════════════════════
#  Data Loading
# ═══════════════════════════════════════════════════════════════════════

def load_or_create_splits(workflows, split_path, train_ratio=0.8, val_ratio=0.1, seed=42):
    return load_or_create_valid_splits(
        workflows,
        split_path,
        train_ratio=train_ratio,
        val_ratio=val_ratio,
        seed=seed,
    )


def compute_pos_weight(
    train_workflows: list,
    active_token_ids: list,
    mr_registry: dict | None = None,
) -> float:
    """Compute pos_weight for BCE: num_absent / num_present.

    If MR registry is supplied, count positives against the union of verified
    equivalent references so that alternate valid operators are not treated as
    always-absent targets.
    """
    token_to_idx = {tid: i for i, tid in enumerate(active_token_ids)}
    n_present = 0
    n_total = 0
    for wf in train_workflows:
        present = set()
        sequences = [wf["l3_sequence"]]
        if mr_registry:
            meta = wf.get("task_metadata", {}) or {}
            key = _make_task_key(
                meta.get("task_type", ""),
                meta.get("task_name", ""),
                meta.get("task_description", ""),
            )
            entry = mr_registry.get(key)
            if entry and len(entry.get("references", [])) > 1:
                sequences.extend(entry["references"])
        for seq in sequences:
            for t in seq:
                if t in token_to_idx:
                    present.add(t)
        n_present += len(present)
        n_total += len(active_token_ids)
    n_absent = n_total - n_present
    pw = n_absent / max(n_present, 1)
    return pw


def build_task_type_sampler(dataset: SetPredictorDataset):
    """Build a WeightedRandomSampler that equalizes task-type frequency."""
    task_type_ids = []
    for wf in dataset.workflows:
        meta = wf.get('task_metadata', {}) or {}
        task_type = meta.get('task_type', 'Unknown')
        task_type_ids.append(dataset.task_type_to_id.get(task_type, 0))

    counts = Counter(task_type_ids)
    weights = [1.0 / counts[t] for t in task_type_ids]
    sampler = WeightedRandomSampler(
        weights=weights,
        num_samples=len(weights),
        replacement=True,
    )
    return sampler, counts


# ═══════════════════════════════════════════════════════════════════════
#  Training Loop
# ═══════════════════════════════════════════════════════════════════════

def train():
    """Main training function."""
    from gis_recommend.config.transformer_config import ensure_output_dirs
    ensure_output_dirs()
    # ── 全局随机种子 ──
    SEED = 42
    random.seed(SEED)
    np.random.seed(SEED)
    torch.manual_seed(SEED)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(SEED)

    print("=" * 70)
    print("Set Predictor V3 Training (Rich Cross-Attn + Self-Attn)")
    print("=" * 70)

    # ── Load data ──
    print("\n[1] Loading data...")
    with open(V4_LABELED_WORKFLOWS_PATH, 'r', encoding='utf-8') as f:
        raw = json.load(f)
    if isinstance(raw, dict) and 'labeled_workflows' in raw:
        workflows = raw['labeled_workflows']
    else:
        workflows = raw
    print(f"  Loaded {len(workflows)} workflows")

    with open(V4_TASK_TYPE_VOCAB_PATH, 'r', encoding='utf-8') as f:
        task_type_vocab = json.load(f)
    num_task_types = task_type_vocab['num_types']
    print(f"  Task types: {num_task_types}")

    # ── Split data（先 split，再从 train 发现 active tokens）──
    print("\n[2] Splitting data...")
    split_path = OUTPUT_DIR / "dataset_splits_v4.json"
    splits = load_or_create_splits(workflows, split_path)

    train_wfs = [workflows[i] for i in splits['train_indices']]
    val_wfs = [workflows[i] for i in splits['val_indices']]
    test_wfs = [workflows[i] for i in splits['test_indices']]
    print(f"  Train: {len(train_wfs)}, Val: {len(val_wfs)}, Test: {len(test_wfs)}")

    # ── Discover active tokens（只从 train split）──
    print("\n[3] Discovering active tokens (from train split only)...")
    active_token_ids = discover_active_tokens(train_wfs)
    save_active_tokens(active_token_ids, SET_PREDICTOR_ACTIVE_TOKENS_PATH)

    # ── Build datasets ──
    print("\n[4] Building datasets...")
    bert_tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')

    train_ds = SetPredictorDataset(
        train_wfs, active_token_ids, task_type_vocab, bert_tokenizer,
        num_count_classes=SET_PREDICTOR_NUM_COUNT_CLASSES,
    )
    val_ds = SetPredictorDataset(
        val_wfs, active_token_ids, task_type_vocab, bert_tokenizer,
        num_count_classes=SET_PREDICTOR_NUM_COUNT_CLASSES,
    )
    test_ds = SetPredictorDataset(
        test_wfs, active_token_ids, task_type_vocab, bert_tokenizer,
        num_count_classes=SET_PREDICTOR_NUM_COUNT_CLASSES,
    )

    train_sampler, task_type_counts = build_task_type_sampler(train_ds)
    train_loader = DataLoader(train_ds, batch_size=SET_PREDICTOR_BATCH_SIZE,
                              sampler=train_sampler, num_workers=0, pin_memory=True)
    val_loader = DataLoader(val_ds, batch_size=SET_PREDICTOR_BATCH_SIZE,
                            shuffle=False, num_workers=0, pin_memory=True)
    test_loader = DataLoader(test_ds, batch_size=SET_PREDICTOR_BATCH_SIZE,
                             shuffle=False, num_workers=0, pin_memory=True)

    print(f"  Balanced sampling: YES (WeightedRandomSampler by task type)")
    print(f"  Unique task types in train: {len(task_type_counts)}")
    print(f"  Top-5 task types (count): {task_type_counts.most_common(5)}")
    print(f"  Bot-5 task types (count): {task_type_counts.most_common()[:-6:-1]}")

    # ── Compute pos_weight ──
    print("\n[5] Computing pos_weight...")
    pos_weight = compute_pos_weight(train_wfs, active_token_ids)
    print(f"  pos_weight (absent/present ratio): {pos_weight:.2f}")

    # ── Build model ──
    print("\n[6] Building model...")
    model = L3SetPredictor(
        num_task_types=num_task_types,
        d_condition=SET_PREDICTOR_D_CONDITION,
        d_hidden=SET_PREDICTOR_D_HIDDEN,
        head_hidden_dim=SET_PREDICTOR_D_HIDDEN,  # 显式传入，避免隐式依赖
        num_count_classes=SET_PREDICTOR_NUM_COUNT_CLASSES,
        active_token_ids=active_token_ids,
        bert_unfreeze_layers=SET_PREDICTOR_BERT_UNFREEZE_LAYERS,
        dropout=SET_PREDICTOR_DROPOUT,
        num_attn_heads=SET_PREDICTOR_NUM_ATTN_HEADS,
        num_self_attn_layers=SET_PREDICTOR_NUM_SELF_ATTN_LAYERS,
        self_attn_dim_feedforward=SET_PREDICTOR_SELF_ATTN_DIM_FF,
        use_rich_cross_attn=True,   # V3 架构（full_seq + FiLM）
    ).to(DEVICE)

    total_params = sum(p.numel() for p in model.parameters())
    trainable_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"  Total params: {total_params:,}")
    print(f"  Trainable params: {trainable_params:,}")

    # ── Loss, optimizer, scheduler ──
    criterion = TwoStageLoss(pos_weight=pos_weight, count_weight=0.5).to(DEVICE)

    param_groups = model.get_parameter_groups(SET_PREDICTOR_BERT_LR, SET_PREDICTOR_LR)
    optimizer = torch.optim.AdamW(param_groups, weight_decay=0.01)

    total_steps = SET_PREDICTOR_NUM_EPOCHS * len(train_loader)
    warmup_steps = SET_PREDICTOR_WARMUP_EPOCHS * len(train_loader)

    def lr_lambda(step):
        if step < warmup_steps:
            return step / max(warmup_steps, 1)
        progress = (step - warmup_steps) / max(total_steps - warmup_steps, 1)
        return 0.5 * (1.0 + np.cos(np.pi * progress))

    scheduler = torch.optim.lr_scheduler.LambdaLR(optimizer, lr_lambda)

    # ── Training ──
    print(f"\n[7] Training for {SET_PREDICTOR_NUM_EPOCHS} epochs...")
    print(f"  Device: {DEVICE}")
    print(f"  Batch size: {SET_PREDICTOR_BATCH_SIZE}")
    print(f"  LR: BERT={SET_PREDICTOR_BERT_LR}, Other={SET_PREDICTOR_LR}")
    print(f"  pos_weight: {pos_weight:.2f}, count_weight: 0.5")
    print(f"  Soft-prior metric threshold: {SET_PREDICTOR_SOFT_PRIOR_THRESHOLD:.2f}")
    print("  Checkpoint: latest epoch snapshot; metrics are recorded only")

    latest_val_soft_f1 = 0.0
    history = []

    for epoch in range(SET_PREDICTOR_NUM_EPOCHS):
        t0 = time.time()

        # ── Train epoch ──
        model.train()
        train_total_loss = 0.0
        train_binary_loss = 0.0
        train_count_loss = 0.0
        n_batches = 0

        pbar = tqdm(train_loader, desc=f"Epoch {epoch+1}/{SET_PREDICTOR_NUM_EPOCHS}")
        for batch in pbar:
            task_type_ids = batch['task_type_id'].to(DEVICE)
            text_input_ids = batch['text_input_ids'].to(DEVICE)
            text_attention_mask = batch['text_attention_mask'].to(DEVICE)
            binary_targets = batch['binary_targets'].to(DEVICE)
            count_targets = batch['count_targets'].to(DEVICE)

            binary_logits, count_logits = model(
                task_type_ids, text_input_ids, text_attention_mask
            )
            loss, b_loss, c_loss = criterion(
                binary_logits, count_logits, binary_targets, count_targets
            )

            optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()

            train_total_loss += loss.item()
            train_binary_loss += b_loss
            train_count_loss += c_loss
            n_batches += 1
            pbar.set_postfix({'loss': f'{loss.item():.4f}',
                              'bin': f'{b_loss:.4f}', 'cnt': f'{c_loss:.4f}'})

        avg_total = train_total_loss / max(n_batches, 1)
        avg_bin = train_binary_loss / max(n_batches, 1)
        avg_cnt = train_count_loss / max(n_batches, 1)

        # ── Validate ──
        model.eval()
        val_loss_sum = 0.0
        val_n = 0
        all_binary_logits = []
        all_count_logits = []
        all_binary_targets = []
        all_count_targets = []

        with torch.no_grad():
            for batch in val_loader:
                task_type_ids = batch['task_type_id'].to(DEVICE)
                text_input_ids = batch['text_input_ids'].to(DEVICE)
                text_attention_mask = batch['text_attention_mask'].to(DEVICE)
                binary_targets = batch['binary_targets'].to(DEVICE)
                count_targets = batch['count_targets'].to(DEVICE)

                binary_logits, count_logits = model(
                    task_type_ids, text_input_ids, text_attention_mask
                )
                loss, _, _ = criterion(
                    binary_logits, count_logits, binary_targets, count_targets
                )

                val_loss_sum += loss.item()
                val_n += 1
                all_binary_logits.append(binary_logits.cpu())
                all_count_logits.append(count_logits.cpu())
                all_binary_targets.append(binary_targets.cpu())
                all_count_targets.append(count_targets.cpu())

        avg_val_loss = val_loss_sum / max(val_n, 1)
        all_bl = torch.cat(all_binary_logits, dim=0)
        all_cl = torch.cat(all_count_logits, dim=0)
        all_bt = torch.cat(all_binary_targets, dim=0)
        all_ct = torch.cat(all_count_targets, dim=0)

        metrics_default = compute_metrics(all_bl, all_cl, all_bt, all_ct, threshold=0.5)
        metrics_soft = compute_metrics(
            all_bl, all_cl, all_bt, all_ct, threshold=SET_PREDICTOR_SOFT_PRIOR_THRESHOLD
        )

        elapsed = time.time() - t0
        current_lr = scheduler.get_last_lr()[0]

        print(f"  Epoch {epoch+1}: "
              f"loss={avg_total:.4f}(bin={avg_bin:.4f},cnt={avg_cnt:.4f}), "
              f"val_loss={avg_val_loss:.4f}, "
              f"F1@0.50={metrics_default['set_f1']:.4f}, "
              f"F1@{SET_PREDICTOR_SOFT_PRIOR_THRESHOLD:.2f}={metrics_soft['set_f1']:.4f}, "
              f"P@{SET_PREDICTOR_SOFT_PRIOR_THRESHOLD:.2f}={metrics_soft['set_precision']:.4f}, "
              f"R@{SET_PREDICTOR_SOFT_PRIOR_THRESHOLD:.2f}={metrics_soft['set_recall']:.4f}, "
              f"AvgSize@{SET_PREDICTOR_SOFT_PRIOR_THRESHOLD:.2f}={metrics_soft['avg_pred_size']:.1f}, "
              f"CntAcc={metrics_soft['count_acc']:.4f}, "
              f"CntMAE={metrics_soft['count_mae']:.4f}, "
              f"LR={current_lr:.2e}, "
              f"Time={elapsed:.1f}s")

        history.append({
            'epoch': epoch + 1,
            'train_loss': avg_total,
            'train_binary_loss': avg_bin,
            'train_count_loss': avg_cnt,
            'val_loss': avg_val_loss,
            'soft_prior_metric_threshold': SET_PREDICTOR_SOFT_PRIOR_THRESHOLD,
            'val_metrics_default': metrics_default,
            'val_metrics_soft_prior': metrics_soft,
        })

        latest_val_soft_f1 = metrics_soft['set_f1']
        save_path = SET_PREDICTOR_CHECKPOINT_DIR / "best_model.pth"
        torch.save(
            _build_set_predictor_checkpoint_payload(
                model_state_dict=model.state_dict(),
                config=_set_predictor_model_config(model, num_task_types),
                active_token_ids=active_token_ids,
                epoch=epoch + 1,
                runtime_profile={
                    'trainer': 'train_set_predictor_v3',
                    'num_epochs': SET_PREDICTOR_NUM_EPOCHS,
                    'batch_size': SET_PREDICTOR_BATCH_SIZE,
                    'soft_prior_metric_threshold': SET_PREDICTOR_SOFT_PRIOR_THRESHOLD,
                },
                dataset_identity={
                    'data_path': str(V4_LABELED_WORKFLOWS_PATH),
                    'split_path': str(split_path),
                    'task_vocab_path': str(V4_TASK_TYPE_VOCAB_PATH),
                    'train_samples': len(train_wfs),
                    'val_samples': len(val_wfs),
                    'test_samples': len(test_wfs),
                },
                metric_bundle={
                    'train_loss': avg_total,
                    'train_binary_loss': avg_bin,
                    'train_count_loss': avg_cnt,
                    'val_loss': avg_val_loss,
                    'metrics_default': metrics_default,
                    'metrics_soft_prior': metrics_soft,
                },
                provenance={
                    'format_version': CHECKPOINT_SCHEMA,
                    'trainer': 'train_set_predictor_v3',
                    'checkpoint_dir': str(SET_PREDICTOR_CHECKPOINT_DIR),
                    'runtime_profile': {
                        'num_epochs': SET_PREDICTOR_NUM_EPOCHS,
                        'batch_size': SET_PREDICTOR_BATCH_SIZE,
                        'soft_prior_metric_threshold': SET_PREDICTOR_SOFT_PRIOR_THRESHOLD,
                    },
                    'dataset_identity': {
                        'data_path': str(V4_LABELED_WORKFLOWS_PATH),
                        'split_path': str(split_path),
                        'task_vocab_path': str(V4_TASK_TYPE_VOCAB_PATH),
                    },
                },
            ),
            save_path,
        )
        print(f"  ** Latest snapshot saved -> {save_path}")

    # ── Test evaluation ──
    print(
        f"\n[8] Test evaluation "
        f"(latest val F1@{SET_PREDICTOR_SOFT_PRIOR_THRESHOLD:.2f}={latest_val_soft_f1:.4f})..."
    )
    best_path = SET_PREDICTOR_CHECKPOINT_DIR / "best_model.pth"
    if not best_path.exists():
        raise FileNotFoundError(f"Expected latest checkpoint not found: {best_path}")
    checkpoint = torch.load(best_path, map_location=DEVICE, weights_only=True)
    model.load_state_dict(checkpoint['model_state_dict'])

    model.eval()
    all_binary_logits = []
    all_count_logits = []
    all_binary_targets = []
    all_count_targets = []
    with torch.no_grad():
        for batch in tqdm(test_loader, desc="Testing"):
            task_type_ids = batch['task_type_id'].to(DEVICE)
            text_input_ids = batch['text_input_ids'].to(DEVICE)
            text_attention_mask = batch['text_attention_mask'].to(DEVICE)
            binary_targets = batch['binary_targets'].to(DEVICE)
            count_targets = batch['count_targets'].to(DEVICE)

            binary_logits, count_logits = model(
                task_type_ids, text_input_ids, text_attention_mask
            )
            all_binary_logits.append(binary_logits.cpu())
            all_count_logits.append(count_logits.cpu())
            all_binary_targets.append(binary_targets.cpu())
            all_count_targets.append(count_targets.cpu())

    all_bl = torch.cat(all_binary_logits, dim=0)
    all_cl = torch.cat(all_count_logits, dim=0)
    all_bt = torch.cat(all_binary_targets, dim=0)
    all_ct = torch.cat(all_count_targets, dim=0)

    # Multi-threshold evaluation
    print(f"\n{'='*70}")
    print(f"  Test Results (multi-threshold):")
    thresholds = sorted({
        0.3, 0.4, 0.5, 0.6,
        float(SET_PREDICTOR_SOFT_PRIOR_THRESHOLD),
        float(SET_PREDICTOR_CONFIDENCE_THRESHOLD),
    })
    for thr in thresholds:
        m = compute_metrics(all_bl, all_cl, all_bt, all_ct, threshold=thr)
        markers = []
        if abs(thr - 0.5) < 1e-8:
            markers.append("default")
        if abs(thr - SET_PREDICTOR_SOFT_PRIOR_THRESHOLD) < 1e-8:
            markers.append("soft-prior")
        if abs(thr - SET_PREDICTOR_CONFIDENCE_THRESHOLD) < 1e-8:
            markers.append("hard-threshold")
        marker = f" ← {', '.join(markers)}" if markers else ""
        print(f"    thr={thr}: F1={m['set_f1']:.4f}, "
              f"P={m['set_precision']:.4f}, R={m['set_recall']:.4f}, "
              f"AvgSize={m['avg_pred_size']:.1f}, "
              f"CntAcc={m['count_acc']:.4f}{marker}")

    test_metrics_default = compute_metrics(all_bl, all_cl, all_bt, all_ct, threshold=0.5)
    test_metrics_soft_prior = compute_metrics(
        all_bl, all_cl, all_bt, all_ct, threshold=SET_PREDICTOR_SOFT_PRIOR_THRESHOLD
    )
    print(f"{'='*70}")

    # Save training history
    history_path = SET_PREDICTOR_CHECKPOINT_DIR / "training_history.json"
    with open(history_path, 'w', encoding='utf-8') as f:
        json.dump({
            'history': history,
            'test_metrics_default': test_metrics_default,
            'test_metrics_soft_prior': test_metrics_soft_prior,
            'latest_val_f1': latest_val_soft_f1,
            'soft_prior_metric_threshold': SET_PREDICTOR_SOFT_PRIOR_THRESHOLD,
            'active_tokens_count': len(active_token_ids),
        }, f, indent=2)
    print(f"  History saved to {history_path}")

    return model, test_metrics_soft_prior


def main(argv=None):
    """Delegate direct module execution to the quality-gate launcher."""
    from scripts.train_set_predictor_quality_gate import main as quality_gate_main

    return quality_gate_main(argv)


if __name__ == '__main__':
    main()
