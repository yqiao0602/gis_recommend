# -*- coding: utf-8 -*-
"""
任务条件化Transformer训练脚本 V4.2 — 全面修复版 + 共享GPU低显存优化

V4.2 修复内容（相对V4/V4.1）:
- [Fix A] FiLM gamma init: fill_diagonal_(1.0) 替代无效的 diag() (model_v4.py已修)
- [Fix B] _adaptive_sample: linspace加device参数 (model_v4.py已修)
- [Fix C] Config LENGTH_PENALTY 重复问题 (transformer_config.py已修)
- [Fix D] AR步骤移除torch.no_grad(), BERT梯度正常流动
- [Fix E] AR步骤使用label smoothing (统一criterion)
- [Fix F] AR步骤aux losses: 用no_grad全量forward获取正确的decoder输出
- [Fix G] AR步骤attention mask: 基于实际生成长度构建
- [Fix H] task_classifier加入optimizer参数组

共享GPU低显存优化:
- 梯度累积: 物理batch=8 × 累积4步 = 等效batch 32
- AR steps: 20步 (适配低显存)
- DataLoader num_workers: 0 (节省内存)
- empty_cache: AR步骤后主动释放显存
- LR: sqrt scaling (适配大batch)
- DataLoader num_workers: 0→4 (并行数据加载)
- 评估样本: 2→4 batch (更准确的AR指标)
- Warmup: 3→5 epoch (大batch需要更多warmup)

从V4.1采纳的好方案:
- Nucleus sampling in AR-SS
- 频率加权CE loss
- Task classification loss (替代contrastive loss)
- Log-scale length loss
- 渐进式AR ratio ramp-up
- Decode时重复惩罚

从V4保留的正确逻辑:
- Curriculum learning phases
- Transition loss (fix: 使用logits而非detach后的probs计算)
- Training loop结构
- Checkpoint保存/加载
- 评估指标

训练策略:
- Phase A (Epoch 0-9): 纯Teacher Forcing
- Phase B (Epoch 10+): 渐进AR-SS (10%→70%) + nucleus sampling
"""

import os
import json
import math
import hashlib
import random
import time
from pathlib import Path
from collections import Counter

# 防止CUDA显存碎片化OOM
os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader, Subset
from torch.amp import autocast
from torch.cuda.amp import GradScaler
from tqdm import tqdm
from transformers import BertTokenizer

from gis_recommend.config.transformer_config import (
    OUTPUT_DIR, DEVICE, SPECIAL_TOKENS, TOTAL_VOCAB_SIZE, VOCAB_SIZE,
    V4_LABELED_WORKFLOWS_PATH, V4_TASK_TYPE_VOCAB_PATH,
    V4_WARMUP_EPOCHS, V4_GRADIENT_CLIP,
    V4_LABEL_SMOOTHING, V4_TF_PHASE_EPOCHS,
    V4_SS_TF_START, V4_SS_TF_END, V4_SS_K,
    V4_CURRICULUM_PHASE1_MAX_LEN, V4_CURRICULUM_PHASE2_MAX_LEN,
    V4_CURRICULUM_PHASE1_END, V4_CURRICULUM_PHASE2_END,
    V4_TRANSITION_LOSS_WEIGHT,
    V4_BERT_LR, V4_OTHER_LR, V4_BERT_UNFREEZE_LAYERS,
    V4_D_MODEL, V4_N_HEADS, V4_N_LAYERS, V4_D_FF, V4_DROPOUT,
    V4_MAX_SEQ_LENGTH, V4_MAX_MEMORY_TOKENS, V4_BATCH_SIZE,
    L3_EMBEDDINGS_PATH, RANDOM_SEED,
    # V4.1 params adopted in V4.2
    V4_1_AR_SAMPLE_TEMPERATURE, V4_1_AR_SAMPLE_TOP_P,
    V4_1_DECODE_REP_PENALTY, V4_1_DECODE_REP_WINDOW,
    V4_1_FREQ_WEIGHT_ALPHA,
    V4_1_AR_RATIO_START, V4_1_AR_RATIO_END,
    V4_1_LENGTH_LOSS_WEIGHT, V4_1_TASK_CLS_LOSS_WEIGHT,
    V4_1_NUM_EPOCHS, V4_1_EARLY_STOPPING_PATIENCE,
    # V4.2 optimized params (24GB VRAM)
    V4_2_TRANSFORMER_CHECKPOINT_DIR,
    V4_2_BATCH_SIZE, V4_2_OTHER_LR, V4_2_BERT_LR,
    V4_2_WARMUP_EPOCHS, V4_2_NUM_WORKERS,
    V4_2_GEN_EVAL_BATCHES, V4_2_EARLY_STOPPING_PATIENCE,
    V4_2_AR_MAX_STEPS, V4_2_GRADIENT_ACCUM_STEPS,
)
from gis_recommend.models.transformer_model_v4 import TaskConditionedL3TransformerModelV4
from gis_recommend.models.task_text_processor import TaskVocabularyBuilder

# ===================== Constants =====================
SPECIAL_TOKEN_MAP = {v: VOCAB_SIZE + abs(v) - 1 for v in SPECIAL_TOKENS.values()}
PAD_INDEX = SPECIAL_TOKEN_MAP[-1]   # 350
UNK_INDEX = SPECIAL_TOKEN_MAP[-2]   # 351
START_INDEX = SPECIAL_TOKEN_MAP[-3]  # 352
END_INDEX = SPECIAL_TOKEN_MAP[-4]   # 353


# ===================== Token Frequency Weights =====================
def compute_token_freq_weights(workflows, alpha=0.5, vocab_size=TOTAL_VOCAB_SIZE):
    """Compute inverse-frequency weights for CE loss.

    alpha=0: uniform weights (no rebalancing)
    alpha=1: full inverse frequency
    alpha=0.5: sqrt inverse frequency (recommended)
    """
    counter = Counter()
    token_map = {v: VOCAB_SIZE + abs(v) - 1 for v in SPECIAL_TOKENS.values()}
    for wf in workflows:
        for t in wf["l3_sequence"]:
            tok = token_map.get(t, t) if t < 0 else t
            if tok != PAD_INDEX:
                counter[tok] += 1

    total = sum(counter.values())
    weights = torch.ones(vocab_size)
    for tok, cnt in counter.items():
        if 0 <= tok < vocab_size:
            freq = cnt / total
            weights[tok] = (1.0 / (freq + 1e-6)) ** alpha

    # Normalize so mean weight = 1.0
    valid_mask = weights != 1.0
    if valid_mask.sum() > 0:
        weights[valid_mask] = weights[valid_mask] / weights[valid_mask].mean()
    weights[PAD_INDEX] = 0.0
    return weights


# ===================== Dataset (same as V4) =====================
class TaskConditionedL3DatasetV4(Dataset):
    """V4 Dataset with BERT tokenization and curriculum support."""

    def __init__(self, workflows, task_vocab_builder, bert_tokenizer,
                 max_seq_length=V4_MAX_SEQ_LENGTH, max_text_length=128):
        self.workflows = workflows
        self.task_vocab_builder = task_vocab_builder
        self.bert_tokenizer = bert_tokenizer
        self.max_seq_length = max_seq_length
        self.max_text_length = max_text_length
        self._text_cache = {}
        self.content_lengths = []
        for wf in workflows:
            seq = wf["l3_sequence"]
            cl = sum(1 for t in seq if t >= 0)
            self.content_lengths.append(cl)

    def __len__(self):
        return len(self.workflows)

    def _convert_token(self, t):
        if t < 0:
            return SPECIAL_TOKEN_MAP.get(t, UNK_INDEX)
        return t

    def _encode_text(self, text):
        key = hashlib.md5(text.encode()).hexdigest()
        if key in self._text_cache:
            return self._text_cache[key]
        enc = self.bert_tokenizer(
            text, max_length=self.max_text_length, padding="max_length",
            truncation=True, return_tensors="pt",
        )
        result = (enc["input_ids"].squeeze(0), enc["attention_mask"].squeeze(0))
        if len(self._text_cache) < 4096:
            self._text_cache[key] = result
        return result

    def __getitem__(self, idx):
        wf = self.workflows[idx]
        raw_seq = wf["l3_sequence"]
        converted = [self._convert_token(t) for t in raw_seq]
        if len(converted) > self.max_seq_length:
            converted = converted[:self.max_seq_length - 1] + [END_INDEX]
        seq_len = len(converted) - 1
        input_ids = converted[:-1]
        target_ids = converted[1:]
        pad_len = self.max_seq_length - len(input_ids)
        attention_mask = [1] * len(input_ids) + [0] * pad_len
        input_ids = input_ids + [PAD_INDEX] * pad_len
        target_ids = target_ids + [PAD_INDEX] * pad_len
        meta = wf.get("task_metadata", {}) or {}
        task_type = meta.get("task_type", "Unknown")
        task_name = meta.get("task_name", "") or ""
        task_desc = meta.get("task_description", "") or ""
        task_type_id = self.task_vocab_builder.encode(task_type)
        text = f"{task_name} {task_desc}".strip() or "unknown task"
        text_ids, text_mask = self._encode_text(text)
        return {
            "input_ids": torch.tensor(input_ids, dtype=torch.long),
            "target_ids": torch.tensor(target_ids, dtype=torch.long),
            "task_type_id": torch.tensor(task_type_id, dtype=torch.long),
            "text_input_ids": text_ids,
            "text_attention_mask": text_mask,
            "attention_mask": torch.tensor(attention_mask, dtype=torch.long),
            "seq_len": seq_len,
        }


def get_curriculum_indices(dataset, epoch, p1_end, p1_max, p2_end, p2_max):
    """Return sample indices based on curriculum phase."""
    if epoch <= p1_end:
        max_len = p1_max
    elif epoch <= p2_end:
        max_len = p2_max
    else:
        return list(range(len(dataset)))
    return [i for i, cl in enumerate(dataset.content_lengths) if cl <= max_len]


# ===================== Trainer V4.2 =====================
class ScheduledSamplingTrainerV4_2:
    """V4.2 Trainer: all bug fixes applied, clean merge of V4+V4.1."""

    def __init__(self, model, train_dataset, val_loader, test_loader,
                 num_task_types, token_freq_weights=None,
                 bert_lr=V4_2_BERT_LR, other_lr=V4_2_OTHER_LR,
                 num_epochs=V4_1_NUM_EPOCHS, warmup_epochs=V4_2_WARMUP_EPOCHS,
                 device=DEVICE, checkpoint_dir=None,
                 label_smoothing=V4_LABEL_SMOOTHING,
                 gradient_clip=V4_GRADIENT_CLIP,
                 batch_size=V4_2_BATCH_SIZE,
                 num_workers=V4_2_NUM_WORKERS,
                 gradient_accum_steps=V4_2_GRADIENT_ACCUM_STEPS,
                 # Scheduled Sampling
                 tf_phase_epochs=V4_TF_PHASE_EPOCHS,
                 ss_tf_start=V4_SS_TF_START, ss_tf_end=V4_SS_TF_END,
                 ss_k=V4_SS_K,
                 ar_ratio_start=V4_1_AR_RATIO_START,
                 ar_ratio_end=V4_1_AR_RATIO_END,
                 # Curriculum
                 curriculum_p1_end=V4_CURRICULUM_PHASE1_END,
                 curriculum_p1_max=V4_CURRICULUM_PHASE1_MAX_LEN,
                 curriculum_p2_end=V4_CURRICULUM_PHASE2_END,
                 curriculum_p2_max=V4_CURRICULUM_PHASE2_MAX_LEN,
                 # Aux tasks
                 length_loss_weight=V4_1_LENGTH_LOSS_WEIGHT,
                 task_cls_loss_weight=V4_1_TASK_CLS_LOSS_WEIGHT,
                 # Transition
                 transition_loss_weight=V4_TRANSITION_LOSS_WEIGHT,
                 transition_path=None,
                 # AR-SS sampling
                 ar_sample_temp=V4_1_AR_SAMPLE_TEMPERATURE,
                 ar_sample_top_p=V4_1_AR_SAMPLE_TOP_P,
                 # Decode repetition penalty
                 decode_rep_penalty=V4_1_DECODE_REP_PENALTY,
                 decode_rep_window=V4_1_DECODE_REP_WINDOW,
                 # Eval
                 early_stopping_patience=V4_2_EARLY_STOPPING_PATIENCE,
                 generation_eval_batches=V4_2_GEN_EVAL_BATCHES,
                 use_amp=True):

        self.model = model.to(device)
        self.train_dataset = train_dataset
        self.val_loader = val_loader
        self.test_loader = test_loader
        self.device = device
        self.num_epochs = num_epochs
        self.warmup_epochs = warmup_epochs
        self.batch_size = batch_size
        self.num_workers = num_workers
        self.gradient_accum_steps = gradient_accum_steps
        self.gradient_clip = gradient_clip
        self.tf_phase_epochs = tf_phase_epochs
        self.ss_tf_start = ss_tf_start
        self.ss_tf_end = ss_tf_end
        self.ss_k = ss_k
        self.ar_ratio_start = ar_ratio_start
        self.ar_ratio_end = ar_ratio_end
        self.curriculum_p1_end = curriculum_p1_end
        self.curriculum_p1_max = curriculum_p1_max
        self.curriculum_p2_end = curriculum_p2_end
        self.curriculum_p2_max = curriculum_p2_max
        self.length_loss_weight = length_loss_weight
        self.task_cls_loss_weight = task_cls_loss_weight
        self.transition_loss_weight = transition_loss_weight
        self.early_stopping_patience = early_stopping_patience
        self.generation_eval_batches = generation_eval_batches
        self.ar_sample_temp = ar_sample_temp
        self.ar_sample_top_p = ar_sample_top_p
        self.decode_rep_penalty = decode_rep_penalty
        self.decode_rep_window = decode_rep_window
        self.use_amp = use_amp and device.type == "cuda"

        self.checkpoint_dir = Path(checkpoint_dir or V4_2_TRANSFORMER_CHECKPOINT_DIR)
        self.checkpoint_dir.mkdir(parents=True, exist_ok=True)

        # Frequency-weighted CE loss with label smoothing
        if token_freq_weights is not None:
            w = token_freq_weights.to(device)
            self.criterion = nn.CrossEntropyLoss(
                weight=w, ignore_index=PAD_INDEX, label_smoothing=label_smoothing
            )
            print(f"  [V4.2] Using frequency-weighted CE loss (alpha={V4_1_FREQ_WEIGHT_ALPHA})")
        else:
            self.criterion = nn.CrossEntropyLoss(
                ignore_index=PAD_INDEX, label_smoothing=label_smoothing
            )

        # Task classification head (replaces contrastive loss)
        self.task_classifier = nn.Linear(V4_D_MODEL // 2, num_task_types).to(device)

        # [Fix H] Optimizer with grouped LR — include task_classifier parameters
        param_groups = model.get_parameter_groups(bert_lr, other_lr)
        param_groups[1]['params'].extend(list(self.task_classifier.parameters()))
        self.optimizer = torch.optim.AdamW(param_groups, weight_decay=0.01)

        # LR scheduler: warmup + cosine
        total_steps = num_epochs
        self.scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
            self.optimizer, T_max=max(total_steps - warmup_epochs, 1), eta_min=1e-6
        )

        # AMP
        self.scaler = GradScaler() if self.use_amp else None

        # Transition matrix
        self.transition_mask = {}
        self._load_transition_matrix(transition_path)

        self.history = {"metrics": {}, "config": {}}

    def _load_transition_matrix(self, path):
        if path is None:
            path = OUTPUT_DIR / "transition_allowed_next.json"
        if not Path(path).exists():
            print(f"  [Warn] 转移矩阵文件不存在: {path}")
            return
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
        raw = data.get("allowed_next", {})
        for a_str, nxt in raw.items():
            a = int(a_str)
            allowed = set(int(b) for b in nxt.keys())
            if allowed:
                self.transition_mask[a] = allowed
        print(f"  [V4.2] 转移矩阵: {len(self.transition_mask)} states loaded")

    # ---- TF Ratio Schedule ----
    def get_tf_ratio(self, epoch):
        if epoch < self.tf_phase_epochs:
            return 1.0
        ss_epoch = epoch - self.tf_phase_epochs
        total_ss = max(self.num_epochs - self.tf_phase_epochs, 1)
        progress = ss_epoch / total_ss
        ratio = self.ss_k / (self.ss_k + math.exp(progress * self.ss_k))
        return self.ss_tf_end + (self.ss_tf_start - self.ss_tf_end) * ratio

    # ---- Gradual AR Ratio ----
    def get_ar_ratio(self, epoch):
        """Gradually increase AR batch ratio from start to end."""
        if epoch < self.tf_phase_epochs:
            return 0.0
        progress = (epoch - self.tf_phase_epochs) / max(self.num_epochs - self.tf_phase_epochs, 1)
        return self.ar_ratio_start + (self.ar_ratio_end - self.ar_ratio_start) * min(progress, 1.0)

    # ---- Curriculum DataLoader ----
    def _build_train_loader(self, epoch):
        indices = get_curriculum_indices(
            self.train_dataset, epoch,
            self.curriculum_p1_end, self.curriculum_p1_max,
            self.curriculum_p2_end, self.curriculum_p2_max,
        )
        subset = Subset(self.train_dataset, indices)
        loader = DataLoader(subset, batch_size=self.batch_size, shuffle=True,
                            num_workers=self.num_workers, drop_last=True)
        return loader, len(indices)

    # ---- Nucleus Sampling ----
    def _nucleus_sample(self, logits, temperature=None, top_p=None):
        """Top-p nucleus sampling. Returns [B] token indices."""
        temp = temperature or self.ar_sample_temp
        top_p = top_p or self.ar_sample_top_p
        logits = logits / temp
        sorted_logits, sorted_indices = torch.sort(logits, descending=True, dim=-1)
        cumulative_probs = torch.cumsum(F.softmax(sorted_logits, dim=-1), dim=-1)
        sorted_mask = cumulative_probs - F.softmax(sorted_logits, dim=-1) >= top_p
        sorted_logits[sorted_mask] = float('-inf')
        probs = F.softmax(sorted_logits, dim=-1)
        sampled_idx = torch.multinomial(probs, num_samples=1).squeeze(-1)
        return sorted_indices.gather(-1, sampled_idx.unsqueeze(-1)).squeeze(-1)

    # ---- Transition Loss ----
    def _transition_loss(self, logits, input_ids, attention_mask):
        """Penalize probability mass on illegal transitions."""
        if not self.transition_mask:
            return torch.tensor(0.0, device=self.device)
        B, T, V = logits.shape
        loss = torch.tensor(0.0, device=self.device)
        count = 0
        for b in range(min(B, 8)):
            valid_len = attention_mask[b].sum().item()
            for t in range(min(int(valid_len) - 1, T - 1)):
                prev_tok = input_ids[b, t].item()
                allowed = self.transition_mask.get(prev_tok)
                if allowed is None:
                    continue
                mask_vec = torch.zeros(V, device=self.device)
                idx = torch.tensor(list(allowed), device=self.device, dtype=torch.long)
                mask_vec[idx] = 1.0
                allowed_prob = (F.softmax(logits[b, t], dim=-1) * mask_vec).sum()
                loss += -torch.log(allowed_prob.clamp(min=1e-8))
                count += 1
        return loss / max(count, 1)

    # ---- Task Classification Loss ----
    def _task_cls_loss(self, repr_batch, task_type_ids):
        """Task type classification from sequence representation."""
        logits = self.task_classifier(repr_batch)
        return F.cross_entropy(logits, task_type_ids)

    # ---- Log-scale Length Loss ----
    def _length_loss(self, length_pred, seq_lens):
        """MSE on log(length) for stable training."""
        if isinstance(seq_lens, torch.Tensor):
            true_len = seq_lens.float().to(self.device)
        else:
            true_len = torch.tensor(seq_lens, dtype=torch.float, device=self.device)
        log_true = torch.log(true_len.clamp(min=1))
        return F.mse_loss(length_pred.squeeze(-1), log_true)

    # ---- Fast Teacher Forcing Step ----
    def _train_step_tf(self, batch):
        """Standard teacher forcing with freq-weighted CE + aux losses.
        Only forward+backward, optimizer step handled by train_epoch.
        """
        input_ids = batch['input_ids'].to(self.device)
        target_ids = batch['target_ids'].to(self.device)
        task_type_ids = batch['task_type_id'].to(self.device)
        text_input_ids = batch['text_input_ids'].to(self.device)
        text_attention_mask = batch['text_attention_mask'].to(self.device)
        attention_mask = batch['attention_mask'].to(self.device)
        seq_lens = batch['seq_len']

        with autocast('cuda', enabled=self.use_amp):
            logits, aux = self.model(
                input_ids, task_type_ids,
                text_input_ids, text_attention_mask,
                attention_mask=attention_mask, return_aux=True,
            )
            # Frequency-weighted main CE loss (with label smoothing via criterion)
            main_loss = self.criterion(
                logits.view(-1, logits.size(-1)), target_ids.view(-1)
            )
            # Log-scale length loss
            length_loss = self._length_loss(aux['length_pred'], seq_lens)
            # Task classification loss
            task_loss = self._task_cls_loss(aux['contrastive_repr'], task_type_ids)
            # Transition loss
            transition_loss = self._transition_loss(logits, input_ids, attention_mask)

            total_loss = (main_loss
                          + self.length_loss_weight * length_loss
                          + self.task_cls_loss_weight * task_loss
                          + self.transition_loss_weight * transition_loss)

            # Scale for gradient accumulation
            backward_loss = total_loss / self.gradient_accum_steps

        if self.use_amp:
            self.scaler.scale(backward_loss).backward()
        else:
            backward_loss.backward()

        return {
            'total_loss': total_loss.item(),
            'main_loss': main_loss.item(),
            'length_loss': length_loss.item(),
            'task_cls_loss': task_loss.item(),
            'transition_loss': transition_loss.item(),
        }

    # ---- True AR-SS Step (all fixes applied, low-VRAM optimized) ----
    def _train_step_autoregressive(self, batch, tf_ratio):
        """Token-by-token AR training with:
        - [Fix D] BERT gradients enabled via separate BERT loss term
        - [Fix E] Label-smoothed loss via self.criterion
        - [Fix F] Aux losses from full forward pass (no partial x)
        - [Fix G] Proper attention mask from actual sequence lengths
        - Nucleus sampling instead of argmax
        - Memory optimization: detach memory/condition for AR loop
        - Gradient accumulation: only backward, optimizer step in train_epoch
        """
        target_ids = batch['target_ids'].to(self.device)
        task_type_ids = batch['task_type_id'].to(self.device)
        text_input_ids = batch['text_input_ids'].to(self.device)
        text_attention_mask = batch['text_attention_mask'].to(self.device)
        attention_mask = batch['attention_mask'].to(self.device)
        seq_lens = batch['seq_len']

        B, T = target_ids.shape
        ar_max_steps = min(T, V4_2_AR_MAX_STEPS)

        # [Fix D] Compute BERT memory WITH gradients — BERT top layers can learn
        memory_raw, memory_mask, text_pooled = self.model.text_encoder(
            text_input_ids, text_attention_mask
        )
        memory_proj = self.model.text_projection(memory_raw)
        memory = self.model.memory_positional_encoding(memory_proj)
        condition = self.model._fuse_condition(task_type_ids, text_pooled)

        # BERT anchor loss: task classification from BERT pooled output
        bert_condition_repr = self.model.contrastive_projector(
            self.model.condition_projection(text_pooled)
        )
        bert_task_loss = self._task_cls_loss(bert_condition_repr, task_type_ids)

        # Detach memory/condition for AR loop — saves massive VRAM
        memory_d = memory.detach()
        condition_d = condition.detach()
        memory_mask_d = memory_mask.detach() if memory_mask is not None else None

        # Build decoder input token-by-token
        decoder_input = torch.full((B, 1), START_INDEX, dtype=torch.long, device=self.device)
        total_loss = torch.tensor(0.0, device=self.device)
        valid_steps = 0

        # [Fix G] Track actual generated lengths per sample
        gen_lengths = torch.ones(B, dtype=torch.long, device=self.device)

        with autocast('cuda', enabled=self.use_amp):
            for t in range(ar_max_steps):
                step_mask = attention_mask[:, t]
                if step_mask.sum() == 0:
                    break

                # Embed current decoder input
                tok_emb = self.model.token_embedding(decoder_input)
                gamma = self.model.input_film_gamma(condition_d).unsqueeze(1)
                beta = self.model.input_film_beta(condition_d).unsqueeze(1)
                tok_emb = gamma * tok_emb + beta
                tok_emb = self.model.positional_encoding(tok_emb)

                cur_len = tok_emb.size(1)
                causal_mask = self.model._generate_causal_mask(cur_len, self.device)
                memory_pad_mask = ~memory_mask_d if memory_mask_d is not None else None

                x = tok_emb
                for layer in self.model.decoder_layers:
                    x = layer(x, memory_d, condition_d,
                              tgt_mask=causal_mask,
                              memory_key_padding_mask=memory_pad_mask)
                x = self.model.decoder_norm(x)

                next_logits = self.model.output_projection(x[:, -1, :])

                # [Fix E] Use self.criterion (with label smoothing + freq weights)
                loss_t = self.criterion(next_logits, target_ids[:, t])
                total_loss = total_loss + loss_t
                valid_steps += 1

                # Nucleus sampling for next token selection
                if random.random() < tf_ratio:
                    next_token = target_ids[:, t].unsqueeze(1)
                else:
                    with torch.no_grad():
                        next_token = self._nucleus_sample(next_logits).unsqueeze(1)

                decoder_input = torch.cat([decoder_input, next_token], dim=1)
                gen_lengths += step_mask.long()

                if decoder_input.size(1) > self.model.max_seq_length:
                    break

            avg_loss = total_loss / max(valid_steps, 1)

            # [Fix F] Compute aux losses from a clean full forward pass
            with torch.no_grad():
                gen_input = decoder_input[:, :-1] if decoder_input.size(1) > 1 else decoder_input
                gen_attn = torch.zeros(B, gen_input.size(1), dtype=torch.long, device=self.device)
                for b in range(B):
                    valid = min(gen_lengths[b].item(), gen_input.size(1))
                    gen_attn[b, :valid] = 1

                _, aux = self.model(
                    gen_input, task_type_ids,
                    text_input_ids, text_attention_mask,
                    attention_mask=gen_attn, return_aux=True,
                )

            length_loss = self._length_loss(aux['length_pred'], seq_lens)
            task_loss = self._task_cls_loss(aux['contrastive_repr'], task_type_ids)

            # Total: AR decoder loss + BERT anchor loss + aux losses
            total_ar_loss = (avg_loss
                             + self.task_cls_loss_weight * bert_task_loss
                             + self.length_loss_weight * length_loss
                             + self.task_cls_loss_weight * task_loss)

            # Scale for gradient accumulation
            backward_loss = total_ar_loss / self.gradient_accum_steps

        if self.use_amp:
            self.scaler.scale(backward_loss).backward()
        else:
            backward_loss.backward()

        # 释放AR步骤积累的显存
        del decoder_input, total_loss, avg_loss, backward_loss
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        return {
            'total_loss': total_ar_loss.item(),
            'main_loss': (total_ar_loss - self.task_cls_loss_weight * bert_task_loss).item(),
            'length_loss': length_loss.item(),
            'task_cls_loss': task_loss.item(),
            'transition_loss': 0.0,
        }

    # ---- Optimizer Step (called every gradient_accum_steps) ----
    def _optimizer_step(self):
        """Gradient clipping + optimizer step + zero_grad."""
        if self.use_amp:
            self.scaler.unscale_(self.optimizer)
            nn.utils.clip_grad_norm_(
                list(self.model.parameters()) + list(self.task_classifier.parameters()),
                self.gradient_clip
            )
            self.scaler.step(self.optimizer)
            self.scaler.update()
        else:
            nn.utils.clip_grad_norm_(
                list(self.model.parameters()) + list(self.task_classifier.parameters()),
                self.gradient_clip
            )
            self.optimizer.step()
        self.optimizer.zero_grad()

    # ---- Train Epoch ----
    def train_epoch(self, epoch):
        self.model.train()
        self.task_classifier.train()
        loader, n_samples = self._build_train_loader(epoch)
        tf_ratio = self.get_tf_ratio(epoch)
        ar_ratio = self.get_ar_ratio(epoch)
        use_ar = epoch >= self.tf_phase_epochs

        eff_batch = self.batch_size * self.gradient_accum_steps
        mode_str = f"AR-SS(tf={tf_ratio:.2f},ar={ar_ratio:.0%})" if use_ar else "TF"
        pbar = tqdm(loader, desc=f"Epoch {epoch+1}/{self.num_epochs} [{mode_str}, n={n_samples}]")

        totals = {'total_loss': 0, 'main_loss': 0, 'length_loss': 0,
                  'task_cls_loss': 0, 'transition_loss': 0}
        num_batches = 0

        self.optimizer.zero_grad()  # Initial zero_grad

        for i, batch in enumerate(pbar):
            if use_ar and random.random() < ar_ratio:
                losses = self._train_step_autoregressive(batch, tf_ratio)
            else:
                losses = self._train_step_tf(batch)

            for k in totals:
                totals[k] += losses[k]
            num_batches += 1

            # Optimizer step every gradient_accum_steps batches
            if (i + 1) % self.gradient_accum_steps == 0:
                self._optimizer_step()

            pbar.set_postfix({
                'loss': f"{losses['total_loss']:.4f}",
                'main': f"{losses['main_loss']:.4f}",
            })

        # Handle remaining accumulated gradients
        if num_batches % self.gradient_accum_steps != 0:
            self._optimizer_step()

        denom = max(1, num_batches)
        return {k: v / denom for k, v in totals.items()}

    # ---- Validate ----
    def validate(self, loader=None):
        self.model.eval()
        loader = loader or self.val_loader
        total_loss = 0.0
        correct_top1 = correct_top5 = correct_top10 = 0
        total_tokens = 0
        seq_em = total_seqs = 0
        num_batches = 0

        with torch.no_grad():
            for batch in loader:
                input_ids = batch['input_ids'].to(self.device)
                target_ids = batch['target_ids'].to(self.device)
                task_type_ids = batch['task_type_id'].to(self.device)
                text_input_ids = batch['text_input_ids'].to(self.device)
                text_attention_mask = batch['text_attention_mask'].to(self.device)
                attention_mask = batch['attention_mask'].to(self.device)

                logits = self.model(
                    input_ids, task_type_ids,
                    text_input_ids, text_attention_mask,
                    attention_mask=attention_mask, return_aux=False,
                )
                loss = F.cross_entropy(
                    logits.view(-1, logits.size(-1)), target_ids.view(-1),
                    ignore_index=PAD_INDEX
                )
                total_loss += loss.item()
                num_batches += 1

                mask = attention_mask.bool()
                valid_logits = logits[mask]
                valid_targets = target_ids[mask]

                if valid_targets.numel() > 0:
                    correct_top1 += (valid_logits.argmax(-1) == valid_targets).sum().item()
                    top5 = valid_logits.topk(5, dim=-1).indices
                    correct_top5 += (top5 == valid_targets.unsqueeze(-1)).any(-1).sum().item()
                    top10 = valid_logits.topk(10, dim=-1).indices
                    correct_top10 += (top10 == valid_targets.unsqueeze(-1)).any(-1).sum().item()
                    total_tokens += valid_targets.numel()

                predictions = logits.argmax(dim=-1)
                seq_lens = batch['seq_len']
                if isinstance(seq_lens, torch.Tensor):
                    seq_lens = seq_lens.tolist()
                for i in range(target_ids.size(0)):
                    sl = int(seq_lens[i])
                    if sl <= 0:
                        continue
                    total_seqs += 1
                    if torch.equal(predictions[i, :sl], target_ids[i, :sl]):
                        seq_em += 1

        denom = max(1, num_batches)
        avg_loss = total_loss / denom
        return {
            'loss': avg_loss,
            'perplexity': math.exp(min(avg_loss, 20)),
            'top1_acc': correct_top1 / max(total_tokens, 1),
            'top5_acc': correct_top5 / max(total_tokens, 1),
            'top10_acc': correct_top10 / max(total_tokens, 1),
            'tf_sequence_em': seq_em / max(total_seqs, 1),
        }

    # ---- Greedy Decode with Repetition Penalty ----
    def _greedy_decode_batch(self, batch, max_length):
        """Autoregressive greedy decode with repetition penalty."""
        task_type_ids = batch['task_type_id'].to(self.device)
        text_input_ids = batch['text_input_ids'].to(self.device)
        text_attention_mask = batch['text_attention_mask'].to(self.device)
        B = task_type_ids.size(0)

        generated = torch.full((B, max_length), PAD_INDEX, dtype=torch.long, device=self.device)
        generated[:, 0] = START_INDEX
        attn_mask = torch.zeros((B, max_length), dtype=torch.long, device=self.device)
        attn_mask[:, 0] = 1
        finished = torch.zeros(B, dtype=torch.bool, device=self.device)

        for step in range(1, max_length):
            logits = self.model(
                generated, task_type_ids,
                text_input_ids, text_attention_mask,
                attention_mask=attn_mask, return_aux=False,
            )
            step_logits = logits[:, step - 1, :]
            # Block special tokens
            step_logits[:, PAD_INDEX] = float('-inf')
            step_logits[:, UNK_INDEX] = float('-inf')
            step_logits[:, START_INDEX] = float('-inf')
            if step < 5:
                step_logits[:, END_INDEX] = float('-inf')

            # Repetition penalty on recent window
            window_start = max(1, step - self.decode_rep_window)
            for prev_step in range(window_start, step):
                prev_tokens = generated[:, prev_step]
                for b in range(B):
                    tok = prev_tokens[b].item()
                    if tok not in (PAD_INDEX, START_INDEX, END_INDEX):
                        step_logits[b, tok] -= self.decode_rep_penalty

            next_tokens = step_logits.argmax(dim=-1)
            next_tokens = torch.where(finished, torch.full_like(next_tokens, PAD_INDEX), next_tokens)
            generated[:, step] = next_tokens
            attn_mask[:, step] = (~finished).long()
            finished = finished | (next_tokens == END_INDEX)
            if finished.all():
                break

        return generated

    # ---- Evaluate Generation ----
    def evaluate_generation(self, epoch=None, num_batches=2, loader=None):
        self.model.eval()
        loader = loader or self.val_loader
        if loader is None:
            return {}

        seq_total = seq_em = tok_total = tok_correct = 0
        collected = []

        with torch.no_grad():
            for batch_idx, batch in enumerate(loader):
                if batch_idx >= num_batches:
                    break
                target_ids = batch['target_ids'].to(self.device)
                seq_lens = batch['seq_len']
                if isinstance(seq_lens, torch.Tensor):
                    seq_lens = seq_lens.tolist()

                generated = self._greedy_decode_batch(batch, self.model.max_seq_length)
                pred_tokens = generated[:, 1:]
                T = pred_tokens.size(1)
                target_trunc = target_ids[:, :T]

                for i in range(target_ids.size(0)):
                    vl = min(int(seq_lens[i]), T)
                    if vl <= 0:
                        continue
                    p = pred_tokens[i, :vl]
                    t = target_trunc[i, :vl]
                    tok_correct += (p == t).sum().item()
                    tok_total += vl
                    seq_total += 1
                    if torch.equal(p, t):
                        seq_em += 1

                    if len(collected) < 8:
                        collected.append({
                            'task_type_id': int(batch['task_type_id'][i].item()),
                            'target': t.cpu().tolist(),
                            'prediction': p.cpu().tolist(),
                        })

        if collected and epoch is not None:
            suffix = f"{epoch+1:03d}" if isinstance(epoch, int) else str(epoch)
            path = self.checkpoint_dir / f"generation_samples_{suffix}.json"
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(collected, f, ensure_ascii=False, indent=2)

        self.model.train()
        return {
            'ar_seq_em': seq_em / max(seq_total, 1),
            'ar_token_acc': tok_correct / max(tok_total, 1),
        }

    # ---- Main Training Loop ----
    def train(self):
        print("=" * 80)
        print("V4.2 Training: All Bug Fixes + Low-VRAM Optimization")
        print("=" * 80)
        print(f"  Device: {self.device}, AMP: {self.use_amp}")
        print(f"  Batch: {self.batch_size} x {self.gradient_accum_steps} accum = {self.batch_size * self.gradient_accum_steps} effective")
        print(f"  LR: BERT={self.optimizer.param_groups[0]['lr']:.1e}, Other={self.optimizer.param_groups[1]['lr']:.1e}")
        print(f"  TF Phase: epoch 0-{self.tf_phase_epochs-1}, then AR-SS")
        print(f"  AR ratio: {self.ar_ratio_start:.0%} -> {self.ar_ratio_end:.0%} (gradual)")
        print(f"  AR max steps: {V4_2_AR_MAX_STEPS}")
        print(f"  AR sampling: temp={self.ar_sample_temp}, top_p={self.ar_sample_top_p}")
        print(f"  Decode rep penalty: {self.decode_rep_penalty}, window={self.decode_rep_window}")
        print(f"  Curriculum: phase1 <={self.curriculum_p1_max} (ep 0-{self.curriculum_p1_end}), "
              f"phase2 <={self.curriculum_p2_max} (ep {self.curriculum_p1_end+1}-{self.curriculum_p2_end})")
        print(f"  Warmup: {self.warmup_epochs} epochs, Patience: {self.early_stopping_patience}")
        print(f"  Fixes applied: FiLM init, BERT grad, label smooth AR, aux from forward, attn mask, optimizer")
        print("=" * 80)

        best_val_loss = float('inf')
        epochs_no_improve = 0
        prev_curriculum_phase = -1
        history = []

        for epoch in range(self.num_epochs):
            print(f"\nEpoch {epoch+1}/{self.num_epochs}")
            print("-" * 70)

            # Detect curriculum phase change -> reset patience
            if epoch <= self.curriculum_p1_end:
                curr_phase = 0
            elif epoch <= self.curriculum_p2_end:
                curr_phase = 1
            else:
                curr_phase = 2
            if curr_phase != prev_curriculum_phase and prev_curriculum_phase >= 0:
                print(f"  [Curriculum] Phase {prev_curriculum_phase} -> {curr_phase}, resetting patience")
                epochs_no_improve = 0
                best_val_loss = float('inf')
            prev_curriculum_phase = curr_phase

            # Reset patience when AR-SS starts
            if epoch == self.tf_phase_epochs:
                print(f"  [AR-SS] Starting autoregressive scheduled sampling, resetting patience")
                epochs_no_improve = 0

            train_m = self.train_epoch(epoch)
            val_m = self.validate()

            gen_m = {}
            do_gen = (epoch % 3 == 0 or epoch >= self.num_epochs - 5
                      or epoch >= self.tf_phase_epochs)
            if do_gen:
                gen_m = self.evaluate_generation(epoch=epoch, num_batches=self.generation_eval_batches)

            if epoch >= self.warmup_epochs:
                self.scheduler.step()

            tf_ratio = self.get_tf_ratio(epoch)
            ar_ratio = self.get_ar_ratio(epoch)
            lr = self.optimizer.param_groups[-1]['lr']

            epoch_record = {
                'epoch': epoch + 1, 'tf_ratio': tf_ratio, 'ar_ratio': ar_ratio,
                'lr': lr, 'curriculum_phase': curr_phase,
                **{f'train_{k}': v for k, v in train_m.items()},
                **{f'val_{k}': v for k, v in val_m.items()},
                **{f'gen_{k}': v for k, v in gen_m.items()},
            }
            history.append(epoch_record)

            print(f"\n  Train: Loss={train_m['total_loss']:.4f} "
                  f"(main={train_m['main_loss']:.4f}, len={train_m['length_loss']:.3f}, "
                  f"tcls={train_m['task_cls_loss']:.3f})")
            print(f"  Val:   Loss={val_m['loss']:.4f} | PPL={val_m['perplexity']:.1f} | "
                  f"Top1={val_m['top1_acc']*100:.1f}% Top5={val_m['top5_acc']*100:.1f}% "
                  f"TF-SeqEM={val_m['tf_sequence_em']*100:.1f}%")
            if gen_m:
                print(f"  Gen:   AR-SeqEM={gen_m.get('ar_seq_em',0)*100:.1f}% "
                      f"AR-TokenAcc={gen_m.get('ar_token_acc',0)*100:.1f}%")
            print(f"  TF={tf_ratio:.3f}, AR={ar_ratio:.0%}, LR={lr:.6f}")

            # Verify BERT gradients on first AR epoch (diagnostic)
            if epoch == self.tf_phase_epochs:
                bert_grad_ok = False
                for name, param in self.model.named_parameters():
                    if name.startswith("text_encoder.bert.") and param.requires_grad:
                        if param.grad is not None and param.grad.abs().sum() > 0:
                            bert_grad_ok = True
                            break
                print(f"  [Diag] BERT top-layer gradients: {'OK' if bert_grad_ok else 'MISSING (check Fix D)'}")

            # Checkpoint
            if val_m['loss'] < best_val_loss:
                best_val_loss = val_m['loss']
                epochs_no_improve = 0
                ckpt_path = self.checkpoint_dir / "best_model.pth"
                torch.save({
                    'model_state_dict': self.model.state_dict(),
                    'task_classifier_state_dict': self.task_classifier.state_dict(),
                    'epoch': epoch + 1,
                    'val_loss': val_m['loss'],
                    'model_config': {
                        'max_memory_tokens': V4_MAX_MEMORY_TOKENS,
                        'd_model': V4_D_MODEL,
                        'n_heads': V4_N_HEADS,
                        'n_layers': V4_N_LAYERS,
                    },
                }, ckpt_path)
                print(f"  [BEST] Saved: {ckpt_path} (val_loss={val_m['loss']:.4f})")
            else:
                epochs_no_improve += 1
                print(f"  No improvement for {epochs_no_improve} epoch(s)")

            if (epoch + 1) % 5 == 0:
                torch.save(self.model.state_dict(),
                           self.checkpoint_dir / f"checkpoint_epoch_{epoch+1:03d}.pth")

            if epochs_no_improve >= self.early_stopping_patience:
                print(f"\nEarly stopping at epoch {epoch+1}")
                break

        # Final test evaluation
        print("\n" + "=" * 80)
        print("Training complete! Loading best model for test evaluation...")
        best_ckpt = torch.load(self.checkpoint_dir / "best_model.pth",
                               map_location=self.device, weights_only=True)
        self.model.load_state_dict(best_ckpt['model_state_dict'])
        if 'task_classifier_state_dict' in best_ckpt:
            self.task_classifier.load_state_dict(best_ckpt['task_classifier_state_dict'])

        test_val = self.validate(loader=self.test_loader)
        test_gen = self.evaluate_generation(epoch='test', num_batches=4, loader=self.test_loader)
        print(f"\nTest Results:")
        print(f"  Loss={test_val['loss']:.4f} PPL={test_val['perplexity']:.1f}")
        print(f"  Top1={test_val['top1_acc']*100:.1f}% Top5={test_val['top5_acc']*100:.1f}%")
        print(f"  TF-SeqEM={test_val['tf_sequence_em']*100:.1f}%")
        print(f"  AR-SeqEM={test_gen.get('ar_seq_em',0)*100:.1f}% "
              f"AR-TokenAcc={test_gen.get('ar_token_acc',0)*100:.1f}%")

        self.history['metrics'] = history
        self.history['test'] = {**test_val, **test_gen}
        hist_path = self.checkpoint_dir / "training_history_v4_2.json"
        with open(hist_path, 'w', encoding='utf-8') as f:
            json.dump(self.history, f, indent=2, ensure_ascii=False)
        print(f"\nHistory saved: {hist_path}")

        return history


# ===================== Utilities =====================
def set_seed(seed):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def load_or_create_splits(workflows, split_path, train_ratio=0.8, val_ratio=0.1, seed=42):
    """Load existing splits or create new ones."""
    if Path(split_path).exists():
        with open(split_path, 'r', encoding='utf-8') as f:
            splits = json.load(f)
        print(f"  Loaded existing splits from {split_path}")
        return splits
    n = len(workflows)
    indices = list(range(n))
    rng = random.Random(seed)
    rng.shuffle(indices)
    n_train = int(n * train_ratio)
    n_val = int(n * val_ratio)
    splits = {
        'train_indices': indices[:n_train],
        'val_indices': indices[n_train:n_train + n_val],
        'test_indices': indices[n_train + n_val:],
    }
    with open(split_path, 'w', encoding='utf-8') as f:
        json.dump(splits, f)
    print(f"  Created new splits: train={n_train}, val={n_val}, test={n - n_train - n_val}")
    return splits


# ===================== Main =====================
def main():
    print("=" * 80)
    print("V4.2 Task-Conditioned L3 Transformer Training")
    print("  All bug fixes: FiLM init, BERT grad, label smooth AR, aux forward, attn mask, optimizer")
    print("=" * 80)

    # CUDA check
    if torch.cuda.is_available():
        print(f"  CUDA: Available ({torch.cuda.get_device_name(0)})")
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
    print(f"  Task types: {num_task_types}")

    task_vocab_builder = TaskVocabularyBuilder()
    task_vocab_builder.task_type_to_id = task_type_vocab['task_type_to_id']
    task_vocab_builder.id_to_task_type = {
        int(k): v for k, v in task_type_vocab['id_to_task_type'].items()
    }

    bert_tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')
    print("  BERT tokenizer loaded")

    # [3] Split dataset (reuse V4 splits for fair comparison)
    print("\n[3] Splitting dataset...")
    split_path = OUTPUT_DIR / "dataset_splits_v4.json"
    splits = load_or_create_splits(workflows, split_path, seed=RANDOM_SEED)

    train_wf = [workflows[i] for i in splits['train_indices']]
    val_wf = [workflows[i] for i in splits['val_indices']]
    test_wf = [workflows[i] for i in splits['test_indices']]
    print(f"  Train: {len(train_wf)}, Val: {len(val_wf)}, Test: {len(test_wf)}")

    # [4] Compute token frequency weights
    print("\n[4] Computing token frequency weights...")
    freq_weights = compute_token_freq_weights(
        train_wf, alpha=V4_1_FREQ_WEIGHT_ALPHA, vocab_size=TOTAL_VOCAB_SIZE
    )
    top_tokens = freq_weights.topk(5, largest=False)
    print(f"  Lowest weights (most frequent): "
          f"{list(zip(top_tokens.indices.tolist(), [f'{w:.3f}' for w in top_tokens.values.tolist()]))}")
    bottom_tokens = freq_weights[freq_weights > 0].topk(5, largest=True)
    print(f"  Highest weights (least frequent): "
          f"{[f'{w:.3f}' for w in bottom_tokens.values.tolist()]}")

    # [5] Create datasets
    print("\n[5] Creating datasets...")
    train_dataset = TaskConditionedL3DatasetV4(train_wf, task_vocab_builder, bert_tokenizer)
    val_dataset = TaskConditionedL3DatasetV4(val_wf, task_vocab_builder, bert_tokenizer)
    test_dataset = TaskConditionedL3DatasetV4(test_wf, task_vocab_builder, bert_tokenizer)

    val_loader = DataLoader(val_dataset, batch_size=V4_2_BATCH_SIZE, shuffle=False, num_workers=V4_2_NUM_WORKERS)
    test_loader = DataLoader(test_dataset, batch_size=V4_2_BATCH_SIZE, shuffle=False, num_workers=V4_2_NUM_WORKERS)

    # [6] Create model (with fixed FiLM init)
    print("\n[6] Creating V4 model (with FiLM init fix)...")
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

    # Verify FiLM init fix
    gamma_diag = model.input_film_gamma.weight.data.diag()
    gamma_off_diag = model.input_film_gamma.weight.data[~torch.eye(V4_D_MODEL, dtype=torch.bool)]
    print(f"  [Verify] FiLM gamma diagonal mean: {gamma_diag.mean():.4f} (should be ~1.0)")
    print(f"  [Verify] FiLM gamma off-diagonal mean: {gamma_off_diag.mean():.6f} (should be ~0.0)")

    counts = model.count_parameters()
    print(f"  Total params: {counts['total']/1e6:.1f}M")
    print(f"  Trainable: {counts['trainable']/1e6:.1f}M "
          f"(BERT: {counts['bert_trainable']/1e6:.1f}M, "
          f"Other: {counts['other_trainable']/1e6:.1f}M)")

    # [7] Forward pass verification
    print("\n[7] Forward pass verification...")
    model.eval()
    model.to(DEVICE)
    with torch.no_grad():
        sample = next(iter(val_loader))
        for k in sample:
            if isinstance(sample[k], torch.Tensor):
                sample[k] = sample[k].to(DEVICE)
        logits, aux = model(
            sample['input_ids'], sample['task_type_id'],
            sample['text_input_ids'], sample['text_attention_mask'],
            attention_mask=sample['attention_mask'], return_aux=True,
        )
        print(f"  logits: {tuple(logits.shape)}")
        print(f"  length_pred: {tuple(aux['length_pred'].shape)}")
        print(f"  contrastive_repr: {tuple(aux['contrastive_repr'].shape)}")

    # [8] Train
    print("\n[8] Starting V4.2 training...")
    trainer = ScheduledSamplingTrainerV4_2(
        model=model,
        train_dataset=train_dataset,
        val_loader=val_loader,
        test_loader=test_loader,
        num_task_types=num_task_types,
        token_freq_weights=freq_weights,
        checkpoint_dir=V4_2_TRANSFORMER_CHECKPOINT_DIR,
        use_amp=(DEVICE.type == 'cuda'),
    )
    trainer.train()

    print("\nDone!")


if __name__ == "__main__":
    main()
