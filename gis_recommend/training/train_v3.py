# -*- coding: utf-8 -*-
"""
任务条件化Transformer训练脚本 V3.7 - 最终稳健版（Warm-start + Scheduled Sampling + 双评估 + 约束解码）

融合与修正（把你 V3.6 的修复 + 我 V3.5 的 warm-start 思路合并成最终版）：
1) Warm-start 更稳健
   - 自动探测 shape mismatch
   - 只允许 memory_positional_encoding.pe mismatch（可扩容）
   - 其他 mismatch 直接报错（避免“以为 warm-start 了其实没成功”）
   - pe 扩容：复制旧 tail + 极小噪声（避免新增 memory 位完全同质化）

2) Dataset 更稳
   - 过滤：同时兼容“原始负数 special token”和“已映射的正数 special token”
   - 文本缓存：用 text_hash 作为 key（命中率高，shuffle 不影响）
   - 序列截断：先取 max_seq_length+1 再 shift（避免少用 1 个 token 的容量）

3) Decode 更正确
   - attention_mask 按 finished 更新（END 后 mask=0）
   - 约束解码：UNK/PAD/START 禁用，min_length，重复惩罚，no_repeat_ngram，end_length_bias

4) 训练更可复现
   - 可选 seed
   - 更清晰的训练日志与指标落盘
"""

import json
import math
import hashlib
import random
from collections import OrderedDict, Counter
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import Dataset, DataLoader
from tqdm import tqdm
from transformers import BertTokenizer

try:
    from sklearn.model_selection import train_test_split
except ImportError:
    train_test_split = None

from gis_recommend.config.transformer_config import (
    OUTPUT_DIR,
    DEVICE,
    SPECIAL_TOKENS,
    TOTAL_VOCAB_SIZE,
    VOCAB_SIZE,
    # Model architecture
    D_MODEL,
    N_HEADS,
    N_LAYERS,
    D_FF,
    DROPOUT,
    MAX_SEQ_LENGTH,
    MAX_MEMORY_TOKENS,
    # L3 Embeddings
    USE_L3_EMBEDDINGS,
    L3_EMBEDDINGS_PATH,
    FREEZE_BERT,
    EMBEDDING_DROPOUT,
    # Training
    BATCH_SIZE,
    LEARNING_RATE,
    NUM_EPOCHS,
    WARMUP_STEPS,
    GRADIENT_CLIP,
    PATIENCE,
    LABEL_SMOOTHING,
    # Data
    LABELED_WORKFLOWS_PATH,  # 添加这个！
    TRAIN_SPLIT,
    VAL_SPLIT,
    MIN_SEQ_LENGTH,
    # Evaluation
    SAVE_CHECKPOINT_EVERY,
    # Logging
    VERBOSE,
    RANDOM_SEED,
    # Paths
    TRANSFORMER_MODEL_PATH,
    TRANSFORMER_CHECKPOINT_DIR
)

from gis_recommend.models.transformer_model_v3 import TaskConditionedL3TransformerModelV3
from gis_recommend.models.task_text_processor import TaskVocabularyBuilder


class LabelSmoothingCrossEntropy(nn.Module):
    """Label Smoothing交叉熵损失"""

    def __init__(self, smoothing=0.1, ignore_index=-100):
        super().__init__()
        self.smoothing = smoothing
        self.ignore_index = ignore_index
        self.confidence = 1.0 - smoothing

    def forward(self, pred, target):
        vocab_size = pred.size(-1)
        if self.ignore_index >= 0:
            mask = (target != self.ignore_index)
            if mask.sum() == 0:
                return torch.tensor(0.0, device=pred.device)
            pred = pred[mask]
            target = target[mask]
        log_probs = F.log_softmax(pred, dim=-1)
        true_dist = torch.zeros_like(log_probs)
        true_dist.fill_(self.smoothing / (vocab_size - 1))
        true_dist.scatter_(1, target.unsqueeze(1), self.confidence)
        loss = torch.sum(-true_dist * log_probs, dim=-1).mean()
        return loss


# =========================
# Special Token IDs（与训练一致）
# =========================
SPECIAL_TOKEN_IDS = {
    name: VOCAB_SIZE + abs(token_id) - 1
    for name, token_id in SPECIAL_TOKENS.items()
}
PAD_TOKEN_ID = SPECIAL_TOKEN_IDS['<PAD>']
UNK_TOKEN_ID = SPECIAL_TOKEN_IDS['<UNK>']
START_TOKEN_ID = SPECIAL_TOKEN_IDS['<START>']
END_TOKEN_ID = SPECIAL_TOKEN_IDS['<END>']

PAD_INDEX = PAD_TOKEN_ID
assert 0 <= PAD_INDEX < TOTAL_VOCAB_SIZE, "PAD index 超出词表范围"

EVAL_OUTPUT_DIR = OUTPUT_DIR / "v3_evaluation"
EVAL_OUTPUT_DIR.mkdir(exist_ok=True, parents=True)


# =========================
# Utils
# =========================
def set_seed(seed: int = 42):
    random.seed(seed)
    np.random.seed(seed)
    torch.manual_seed(seed)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(seed)


def report_shape_mismatch(model: torch.nn.Module, state: dict):
    ms = model.state_dict()
    mismatch = []
    for k, v in state.items():
        if k in ms and hasattr(v, "shape") and hasattr(ms[k], "shape"):
            if tuple(v.shape) != tuple(ms[k].shape):
                mismatch.append((k, tuple(v.shape), tuple(ms[k].shape)))
    if mismatch:
        print("[Warm-start] shape mismatch keys (ckpt -> model):")
        for k, a, b in mismatch[:40]:
            print(f"  - {k}: {a} -> {b}")
        if len(mismatch) > 40:
            print(f"  ... and {len(mismatch)-40} more")
    return mismatch


# ======================================================================
# ✅ Warm-start：只允许 memory_positional_encoding.pe mismatch，并做扩容初始化
# ======================================================================
def warmstart_resize_memory_pe_only(
    model: torch.nn.Module,
    ckpt_path: Path,
    device: torch.device,
    pe_key: str = "memory_positional_encoding.pe",
    noise_std: float = 1e-4
):
    """
    仅处理 key：memory_positional_encoding.pe
    - 若 checkpoint 的 pe 是 [1, old_M, d]，当前模型是 [1, new_M, d]：
        * 拷贝前 min(old_M, new_M)
        * 若扩容：复制旧 tail + 极小噪声（避免新增位完全同质化）
    - 其他 shape mismatch：直接报错（避免 silent failure）
    - 其他权重：strict=False 正常加载
    """
    state = torch.load(ckpt_path, map_location=device)

    # 先探测 mismatch
    mismatch = report_shape_mismatch(model, state)
    mismatch_keys = {k for k, _, _ in mismatch}

    # 若存在除了 pe_key 以外的 mismatch，直接报错
    illegal = [x for x in mismatch if x[0] != pe_key]
    if illegal:
        msg = "\n".join([f"{k}: {a} -> {b}" for k, a, b in illegal[:20]])
        raise RuntimeError(
            f"[Warm-start] 检测到除 {pe_key} 之外的 shape mismatch（拒绝 silent load）：\n{msg}\n"
            f"请确认：是否改了模型结构（d_model/n_layers/embedding等），或需要为更多 key 写扩容逻辑。"
        )

    model_state = model.state_dict()
    if pe_key in state and pe_key in model_state:
        old_pe = state[pe_key]
        new_pe = model_state[pe_key]

        if tuple(old_pe.shape) != tuple(new_pe.shape):
            print(f"[Warm-start] resize {pe_key}: {tuple(old_pe.shape)} -> {tuple(new_pe.shape)}")

            # 保证 dtype/device 一致
            old_pe = old_pe.to(dtype=new_pe.dtype, device=new_pe.device)

            # shape: [1, M, d]
            assert old_pe.dim() == 3 and new_pe.dim() == 3, "pe 维度不符合预期"
            assert old_pe.size(0) == 1 and new_pe.size(0) == 1, "pe batch维度不符合预期"
            assert old_pe.size(2) == new_pe.size(2), "pe d_model 不一致，无法扩容"

            old_M = old_pe.size(1)
            new_M = new_pe.size(1)
            d = old_pe.size(2)

            m = min(old_M, new_M)
            new_pe[:, :m, :] = old_pe[:, :m, :]

            if new_M > old_M:
                tail = old_pe[:, old_M - 1:old_M, :].expand(1, new_M - old_M, d).clone()
                if noise_std and noise_std > 0:
                    tail += noise_std * torch.randn_like(tail)
                new_pe[:, old_M:, :] = tail

            state[pe_key] = new_pe.detach().clone()

    missing, unexpected = model.load_state_dict(state, strict=False)
    print(f"[Warm-start] Loaded weights from: {ckpt_path}")
    print(f"  missing keys: {len(missing)}, unexpected keys: {len(unexpected)}")

    # 额外提醒：如果有 missing/unexpected，通常不致命，但你至少要知道
    if missing:
        print(f"  (missing sample) {missing[:10]}")
    if unexpected:
        print(f"  (unexpected sample) {unexpected[:10]}")

    return missing, unexpected


# =========================
# Trainer
# =========================
class ScheduledSamplingTrainerV3:
    """
    V3.7训练器（Warm-start + Scheduled Sampling + 双评估 + 约束解码 + AMP + Aux Loss）
    """

    def __init__(
        self,
        model,
        train_loader,
        val_loader,
        test_loader,
        lr=5e-5,
        num_epochs=20,
        warmup_epochs=2,
        device=DEVICE,
        checkpoint_dir=None,
        aux_task_weight=0.05,
        early_stopping_patience=5,
        label_smoothing=0.1,
        sampling_strategy='linear',
        sampling_start_epoch=10,
        sampling_end_ratio=0.3,
        use_amp=True,
        ss_refine_steps=1,
        ss_keep_prefix_ratio=0.2,
        generation_eval_batches=1,
        generation_sample_size=5,
        # 约束解码参数
        decode_use_constraints=True,
        decode_min_length=6,
        decode_repetition_penalty=1.2,
        decode_no_repeat_ngram=3,
        decode_end_length_bias=0.1
    ):
        self.model = model.to(device)
        self.train_loader = train_loader
        self.val_loader = val_loader
        self.test_loader = test_loader
        self.device = device
        self.num_epochs = num_epochs
        self.warmup_epochs = warmup_epochs
        self.aux_task_weight = aux_task_weight
        self.early_stopping_patience = early_stopping_patience
        self.ss_refine_steps = max(1, ss_refine_steps)
        self.ss_keep_prefix_ratio = max(0.0, min(1.0, ss_keep_prefix_ratio))

        # Scheduled Sampling参数
        self.sampling_strategy = sampling_strategy
        self.sampling_start_epoch = sampling_start_epoch
        self.sampling_end_ratio = sampling_end_ratio

        # 约束解码参数
        self.decode_use_constraints = decode_use_constraints
        self.decode_min_length = decode_min_length
        self.decode_repetition_penalty = decode_repetition_penalty
        self.decode_no_repeat_ngram = decode_no_repeat_ngram
        self.decode_end_length_bias = decode_end_length_bias

        # AMP
        self.use_amp = use_amp and device.type == 'cuda'
        self.scaler = torch.cuda.amp.GradScaler() if self.use_amp else None

        # Optimizer & Scheduler
        self.optimizer = torch.optim.AdamW(model.parameters(), lr=lr, weight_decay=0.01)
        self.scheduler = self._create_scheduler(num_epochs, warmup_epochs)

        # Loss
        self.main_criterion = LabelSmoothingCrossEntropy(
            smoothing=label_smoothing,
            ignore_index=PAD_INDEX
        )
        self.aux_criterion = nn.CrossEntropyLoss()

        # Checkpoint dir
        if checkpoint_dir is None:
            checkpoint_dir = OUTPUT_DIR / "task_conditioned_checkpoints_v3_7_final"
        self.checkpoint_dir = Path(checkpoint_dir)
        self.checkpoint_dir.mkdir(exist_ok=True, parents=True)

        # History
        self.train_history = {
            'train_loss': [], 'train_main_loss': [], 'train_aux_loss': [],
            'val_loss': [], 'val_main_loss': [], 'val_aux_loss': [],
            'val_perplexity': [],
            'val_top1_acc': [], 'val_top5_acc': [], 'val_top10_acc': [],
            'val_tf_sequence_em': [],
            # 双评估：free vs constrained
            'val_gen_free_seq_em': [], 'val_gen_free_token_acc': [], 'val_gen_free_avg_len': [], 'val_gen_free_end_rate': [],
            'val_gen_cons_seq_em': [], 'val_gen_cons_token_acc': [], 'val_gen_cons_avg_len': [], 'val_gen_cons_end_rate': [],
            'learning_rate': [], 'teacher_forcing_ratio': []
        }

        self.best_val_loss = float('inf')
        self.epochs_without_improvement = 0
        self.generation_eval_batches = max(1, generation_eval_batches)
        self.generation_sample_size = generation_sample_size
        self.eval_output_dir = EVAL_OUTPUT_DIR

        self.training_config = {
            'learning_rate': lr,
            'num_epochs': num_epochs,
            'warmup_epochs': warmup_epochs,
            'aux_task_weight': aux_task_weight,
            'label_smoothing': label_smoothing,
            'sampling_strategy': sampling_strategy,
            'sampling_start_epoch': sampling_start_epoch,
            'sampling_end_ratio': sampling_end_ratio,
            'ss_refine_steps': self.ss_refine_steps,
            'ss_keep_prefix_ratio': self.ss_keep_prefix_ratio,
            'generation_eval_batches': self.generation_eval_batches,
            'generation_sample_size': self.generation_sample_size,
            'decode_use_constraints': self.decode_use_constraints,
            'decode_min_length': self.decode_min_length,
            'decode_repetition_penalty': self.decode_repetition_penalty,
            'decode_no_repeat_ngram': self.decode_no_repeat_ngram,
            'decode_end_length_bias': self.decode_end_length_bias
        }

    def _create_scheduler(self, num_epochs, warmup_epochs):
        def lr_lambda(epoch):
            if epoch < warmup_epochs:
                return (epoch + 1) / max(1, warmup_epochs)
            progress = (epoch - warmup_epochs) / max(1, (num_epochs - warmup_epochs))
            return 0.5 * (1 + math.cos(math.pi * progress))
        return torch.optim.lr_scheduler.LambdaLR(self.optimizer, lr_lambda)

    def _get_teacher_forcing_ratio(self, epoch):
        if epoch < self.sampling_start_epoch:
            return 1.0
        progress = (epoch - self.sampling_start_epoch) / max(1, (self.num_epochs - self.sampling_start_epoch))
        if self.sampling_strategy == 'linear':
            ratio = 1.0 - progress * (1.0 - self.sampling_end_ratio)
        elif self.sampling_strategy == 'exponential':
            ratio = max(self.sampling_end_ratio, 0.95 ** (epoch - self.sampling_start_epoch))
        else:
            ratio = 1.0
        return max(ratio, self.sampling_end_ratio)

    def _build_scheduled_sampling_inputs(
        self,
        input_ids,
        task_type_ids,
        text_input_ids,
        text_attention_mask,
        attention_mask,
        teacher_forcing_ratio
    ):
        if teacher_forcing_ratio >= 0.999:
            return input_ids

        batch_size, seq_len = input_ids.shape
        lengths = attention_mask.sum(dim=1).clamp(min=1)

        positions = torch.arange(seq_len, device=self.device).float().unsqueeze(0).expand(batch_size, -1)
        normalized_positions = positions / torch.clamp(lengths.unsqueeze(1).float() - 1, min=1.0)

        use_teacher_prob = torch.clamp(
            1.0 - (1.0 - teacher_forcing_ratio) * normalized_positions,
            min=0.0, max=1.0
        )
        use_teacher = torch.rand(batch_size, seq_len, device=self.device) < use_teacher_prob

        valid_positions = attention_mask.bool()
        valid_positions[:, 0] = False  # START位置固定用真值

        # keep_prefix：前缀永远 teacher-forcing
        if self.ss_keep_prefix_ratio > 0:
            prefix_lengths = torch.clamp((lengths.float() * self.ss_keep_prefix_ratio).long(), min=1)
            for i in range(batch_size):
                prefix_len = min(seq_len, int(prefix_lengths[i].item()))
                if prefix_len > 0:
                    valid_positions[i, :prefix_len] = False

        replace_mask = (~use_teacher) & valid_positions

        # 限制每条样本替换比例，避免“全换掉”导致不稳定
        if replace_mask.any():
            max_replace = torch.clamp((lengths.float() * 0.4).long(), min=1)
            for i in range(batch_size):
                indices = torch.nonzero(replace_mask[i], as_tuple=False).flatten()
                limit = int(max_replace[i].item())
                if indices.numel() > limit:
                    perm = indices[torch.randperm(indices.numel(), device=self.device)]
                    keep = perm[:limit]
                    mask = torch.zeros_like(replace_mask[i])
                    mask[keep] = True
                    replace_mask[i] = mask

        if not replace_mask.any():
            return input_ids

        mixed_input = input_ids.clone()

        for _ in range(self.ss_refine_steps):
            with torch.no_grad():
                logits = self.model(
                    mixed_input,
                    task_type_ids,
                    text_input_ids,
                    text_attention_mask,
                    attention_mask=attention_mask,
                    return_task_logits=False
                )
            predictions = torch.argmax(logits, dim=-1)
            candidate_inputs = mixed_input.clone()
            candidate_inputs[:, 1:] = predictions[:, :-1]
            mixed_input = torch.where(replace_mask, candidate_inputs, mixed_input)

        mixed_input[:, 0] = input_ids[:, 0]
        return mixed_input

    def _backward_step(self, total_loss):
        self.optimizer.zero_grad(set_to_none=True)

        if self.use_amp:
            self.scaler.scale(total_loss).backward()
            self.scaler.unscale_(self.optimizer)
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
            self.scaler.step(self.optimizer)
            self.scaler.update()
        else:
            total_loss.backward()
            torch.nn.utils.clip_grad_norm_(self.model.parameters(), max_norm=1.0)
            self.optimizer.step()

    def train_step_fast(self, batch):
        self.model.train()

        input_ids = batch['input_ids'].to(self.device)
        target_ids = batch['target_ids'].to(self.device)
        task_type_ids = batch['task_type_id'].to(self.device)
        text_input_ids = batch['text_input_ids'].to(self.device)
        text_attention_mask = batch['text_attention_mask'].to(self.device)
        attention_mask = batch['attention_mask'].to(self.device)

        with torch.cuda.amp.autocast(enabled=self.use_amp):
            logits, task_type_logits = self.model(
                input_ids, task_type_ids,
                text_input_ids, text_attention_mask,
                attention_mask=attention_mask,
                return_task_logits=True
            )

            main_loss = self.main_criterion(
                logits.view(-1, logits.size(-1)),
                target_ids.view(-1)
            )
            aux_loss = self.aux_criterion(task_type_logits, task_type_ids)
            total_loss = main_loss + self.aux_task_weight * aux_loss

        self._backward_step(total_loss)

        return {'total_loss': total_loss.item(), 'main_loss': main_loss.item(), 'aux_loss': aux_loss.item()}

    def train_step_with_scheduled_sampling(self, batch, epoch):
        self.model.train()

        input_ids = batch['input_ids'].to(self.device)
        target_ids = batch['target_ids'].to(self.device)
        task_type_ids = batch['task_type_id'].to(self.device)
        text_input_ids = batch['text_input_ids'].to(self.device)
        text_attention_mask = batch['text_attention_mask'].to(self.device)
        attention_mask = batch['attention_mask'].to(self.device)

        teacher_forcing_ratio = self._get_teacher_forcing_ratio(epoch)

        with torch.cuda.amp.autocast(enabled=self.use_amp):
            mixed_input = self._build_scheduled_sampling_inputs(
                input_ids, task_type_ids,
                text_input_ids, text_attention_mask,
                attention_mask, teacher_forcing_ratio
            )

            logits, task_type_logits = self.model(
                mixed_input, task_type_ids,
                text_input_ids, text_attention_mask,
                attention_mask=attention_mask,
                return_task_logits=True
            )

            main_loss = self.main_criterion(
                logits.view(-1, logits.size(-1)),
                target_ids.view(-1)
            )
            aux_loss = self.aux_criterion(task_type_logits, task_type_ids)
            total_loss = main_loss + self.aux_task_weight * aux_loss

        self._backward_step(total_loss)

        return {'total_loss': total_loss.item(), 'main_loss': main_loss.item(), 'aux_loss': aux_loss.item()}

    def train_epoch(self, epoch):
        self.model.train()

        total_loss = total_main_loss = total_aux_loss = 0.0
        num_batches = 0

        use_fast_mode = epoch < self.sampling_start_epoch
        tf_ratio = self._get_teacher_forcing_ratio(epoch)
        mode_str = "Fast" if use_fast_mode else f"SS(tf={tf_ratio:.2f})"
        pbar = tqdm(self.train_loader, desc=f"Epoch {epoch+1}/{self.num_epochs} [{mode_str}]")

        for batch in pbar:
            losses = self.train_step_fast(batch) if use_fast_mode else self.train_step_with_scheduled_sampling(batch, epoch)

            total_loss += losses['total_loss']
            total_main_loss += losses['main_loss']
            total_aux_loss += losses['aux_loss']
            num_batches += 1

            pbar.set_postfix({
                'loss': f"{losses['total_loss']:.4f}",
                'main': f"{losses['main_loss']:.4f}",
                'aux': f"{losses['aux_loss']:.4f}"
            })

        denom = max(1, num_batches)
        return {'loss': total_loss / denom, 'main_loss': total_main_loss / denom, 'aux_loss': total_aux_loss / denom}

    def validate(self):
        self.model.eval()

        total_loss = total_main_loss = total_aux_loss = 0.0
        num_batches = 0

        correct_top1 = correct_top5 = correct_top10 = 0
        total_tokens = 0
        seq_exact_matches = 0
        total_sequences = 0

        with torch.no_grad():
            for batch in self.val_loader:
                input_ids = batch['input_ids'].to(self.device)
                target_ids = batch['target_ids'].to(self.device)
                task_type_ids = batch['task_type_id'].to(self.device)
                text_input_ids = batch['text_input_ids'].to(self.device)
                text_attention_mask = batch['text_attention_mask'].to(self.device)
                attention_mask = batch['attention_mask'].to(self.device)

                logits, task_type_logits = self.model(
                    input_ids, task_type_ids,
                    text_input_ids, text_attention_mask,
                    attention_mask=attention_mask,
                    return_task_logits=True
                )

                main_loss = self.main_criterion(logits.view(-1, logits.size(-1)), target_ids.view(-1))
                aux_loss = self.aux_criterion(task_type_logits, task_type_ids)
                loss_batch = main_loss + self.aux_task_weight * aux_loss

                total_loss += loss_batch.item()
                total_main_loss += main_loss.item()
                total_aux_loss += aux_loss.item()
                num_batches += 1

                mask = attention_mask.bool()
                valid_targets = target_ids[mask]
                valid_logits = logits[mask]
                predictions = logits.argmax(dim=-1)

                if valid_targets.numel() > 0:
                    top1_preds = valid_logits.argmax(dim=-1)
                    correct_top1 += (top1_preds == valid_targets).sum().item()

                    top5_preds = valid_logits.topk(5, dim=-1).indices
                    correct_top5 += (top5_preds == valid_targets.unsqueeze(-1)).any(dim=-1).sum().item()

                    top10_preds = valid_logits.topk(10, dim=-1).indices
                    correct_top10 += (top10_preds == valid_targets.unsqueeze(-1)).any(dim=-1).sum().item()

                    total_tokens += valid_targets.numel()

                seq_lens = batch.get('seq_len')
                if isinstance(seq_lens, torch.Tensor):
                    seq_lens = seq_lens.tolist()
                if seq_lens is None:
                    seq_lens = mask.sum(dim=1).cpu().tolist()

                bs = target_ids.size(0)
                for i in range(bs):
                    seq_len = int(seq_lens[i])
                    if seq_len <= 0:
                        continue
                    total_sequences += 1
                    pred_seq = predictions[i, :seq_len]
                    gold_seq = target_ids[i, :seq_len]
                    if torch.equal(pred_seq, gold_seq):
                        seq_exact_matches += 1

        denom = max(1, num_batches)
        avg_loss = total_loss / denom
        avg_main_loss = total_main_loss / denom
        avg_aux_loss = total_aux_loss / denom
        perplexity = math.exp(min(avg_main_loss, 20))

        top1_acc = correct_top1 / total_tokens if total_tokens > 0 else 0
        top5_acc = correct_top5 / total_tokens if total_tokens > 0 else 0
        top10_acc = correct_top10 / total_tokens if total_tokens > 0 else 0
        tf_sequence_em = seq_exact_matches / total_sequences if total_sequences > 0 else 0

        return {
            'loss': avg_loss,
            'main_loss': avg_main_loss,
            'aux_loss': avg_aux_loss,
            'perplexity': perplexity,
            'top1_acc': top1_acc,
            'top5_acc': top5_acc,
            'top10_acc': top10_acc,
            'tf_sequence_em': tf_sequence_em
        }

    def _greedy_decode_batch(
        self,
        batch,
        max_length,
        use_constraints=True,
        min_length=6,
        repetition_penalty=1.2,
        no_repeat_ngram=3,
        end_length_bias=0.1
    ):
        task_type_ids = batch['task_type_id'].to(self.device)
        text_input_ids = batch['text_input_ids'].to(self.device)
        text_attention_mask = batch['text_attention_mask'].to(self.device)
        batch_size = task_type_ids.size(0)

        generated = torch.full((batch_size, max_length), PAD_TOKEN_ID, dtype=torch.long, device=self.device)
        generated[:, 0] = START_TOKEN_ID

        # decode attention_mask：long(0/1)，与训练一致
        attention_mask = torch.zeros((batch_size, max_length), dtype=torch.long, device=self.device)
        attention_mask[:, 0] = 1

        finished = torch.zeros(batch_size, dtype=torch.bool, device=self.device)
        generated_tokens_list = [[] for _ in range(batch_size)]

        for step in range(1, max_length):
            logits = self.model(
                generated,
                task_type_ids,
                text_input_ids,
                text_attention_mask,
                attention_mask=attention_mask,
                return_task_logits=False
            )
            step_logits = logits[:, step - 1, :].clone()

            if use_constraints:
                step_logits[:, UNK_TOKEN_ID] = float('-inf')
                step_logits[:, PAD_TOKEN_ID] = float('-inf')
                step_logits[:, START_TOKEN_ID] = float('-inf')
                if step < min_length:
                    step_logits[:, END_TOKEN_ID] = float('-inf')

                for b in range(batch_size):
                    if finished[b]:
                        continue
                    gen_tokens = generated_tokens_list[b]

                    # repetition penalty
                    if repetition_penalty != 1.0 and len(gen_tokens) > 0:
                        for token in set(gen_tokens):
                            if token < step_logits.size(1):
                                if step_logits[b, token] > 0:
                                    step_logits[b, token] /= repetition_penalty
                                else:
                                    step_logits[b, token] *= repetition_penalty

                    # no_repeat_ngram
                    if no_repeat_ngram > 0 and len(gen_tokens) >= no_repeat_ngram - 1:
                        prefix = tuple(gen_tokens[-(no_repeat_ngram - 1):])
                        for prev_start in range(len(gen_tokens) - no_repeat_ngram + 1):
                            prev_prefix = tuple(gen_tokens[prev_start:prev_start + no_repeat_ngram - 1])
                            if prev_prefix == prefix:
                                blocked = gen_tokens[prev_start + no_repeat_ngram - 1]
                                if blocked < step_logits.size(1):
                                    step_logits[b, blocked] = float('-inf')

                # END length bias
                if step >= min_length and end_length_bias > 0:
                    end_bonus = (step - min_length) * end_length_bias
                    step_logits[:, END_TOKEN_ID] += end_bonus

            next_tokens = torch.argmax(step_logits, dim=-1)
            next_tokens = torch.where(finished, torch.full_like(next_tokens, PAD_TOKEN_ID), next_tokens)

            generated[:, step] = next_tokens
            for b in range(batch_size):
                if not finished[b]:
                    generated_tokens_list[b].append(next_tokens[b].item())

            # ✅ 正确更新：本步对未 finished 的样本有效；下一步 END 之后 mask=0
            attention_mask[:, step] = (~finished).long()
            finished = finished | (next_tokens == END_TOKEN_ID)

            if finished.all():
                break

        return generated

    @staticmethod
    def _calc_pred_len_and_end_rate(pred_tokens_2d: torch.Tensor):
        bsz, T = pred_tokens_2d.size()
        lengths = []
        end_hit = 0
        for i in range(bsz):
            seq = pred_tokens_2d[i].tolist()
            if END_TOKEN_ID in seq:
                end_hit += 1
                pos = seq.index(END_TOKEN_ID)
                lengths.append(pos)  # 不含 END
            else:
                lengths.append(T)
        avg_len = float(sum(lengths) / max(1, len(lengths)))
        end_rate = float(end_hit / max(1, bsz))
        return avg_len, end_rate

    def evaluate_generation(self, epoch=None, num_batches=1, loader=None, save_samples=True):
        dataloader = loader or self.val_loader
        if dataloader is None:
            return {}

        was_training = self.model.training
        self.model.eval()

        agg = {
            'free': {'seq_total': 0, 'seq_em': 0, 'tok_total': 0, 'tok_correct': 0, 'len_sum': 0.0, 'end_sum': 0.0, 'sample_total': 0},
            'cons': {'seq_total': 0, 'seq_em': 0, 'tok_total': 0, 'tok_correct': 0, 'len_sum': 0.0, 'end_sum': 0.0, 'sample_total': 0}
        }

        collected_samples = []

        def decode_batch(batch, constrained: bool):
            if constrained:
                return self._greedy_decode_batch(
                    batch, self.model.max_seq_length,
                    use_constraints=self.decode_use_constraints,
                    min_length=self.decode_min_length,
                    repetition_penalty=self.decode_repetition_penalty,
                    no_repeat_ngram=self.decode_no_repeat_ngram,
                    end_length_bias=self.decode_end_length_bias
                )
            return self._greedy_decode_batch(batch, self.model.max_seq_length, use_constraints=False)

        with torch.no_grad():
            for batch_idx, batch in enumerate(dataloader):
                if batch_idx >= num_batches:
                    break

                target_ids = batch['target_ids'].to(self.device)
                seq_lens = batch['seq_len']
                if isinstance(seq_lens, torch.Tensor):
                    seq_lens = seq_lens.tolist()

                bs = target_ids.size(0)

                for mode_key, constrained in [('free', False), ('cons', True)]:
                    generated = decode_batch(batch, constrained=constrained)
                    pred_tokens = generated[:, 1:]  # remove START, [B, T]

                    avg_len, end_rate = self._calc_pred_len_and_end_rate(pred_tokens)
                    agg[mode_key]['len_sum'] += avg_len * bs
                    agg[mode_key]['end_sum'] += end_rate * bs
                    agg[mode_key]['sample_total'] += bs

                    T = pred_tokens.size(1)
                    target_trunc = target_ids[:, :T]

                    for i in range(bs):
                        # seq_len 是 input_ids 的长度，与 target_ids 和 pred_tokens 对齐
                        valid_len = min(int(seq_lens[i]), T)
                        if valid_len <= 0:
                            continue
                        p = pred_tokens[i, :valid_len]
                        t = target_trunc[i, :valid_len]

                        m = (p == t)
                        agg[mode_key]['tok_correct'] += int(m.sum().item())
                        agg[mode_key]['tok_total'] += int(valid_len)

                        agg[mode_key]['seq_total'] += 1
                        if torch.equal(p, t):
                            agg[mode_key]['seq_em'] += 1

                    if constrained and self.generation_sample_size and len(collected_samples) < self.generation_sample_size:
                        take = min(self.generation_sample_size - len(collected_samples), bs)
                        for i in range(take):
                            valid_len = min(int(seq_lens[i]), T)
                            if valid_len <= 0:
                                continue
                            collected_samples.append({
                                'task_type_id': int(batch['task_type_id'][i].item()),
                                'seq_len': valid_len,
                                'target': target_trunc[i, :valid_len].detach().cpu().tolist(),
                                'prediction': pred_tokens[i, :valid_len].detach().cpu().tolist()
                            })

        final_metrics = {'free': {}, 'cons': {}}
        for mode in ['free', 'cons']:
            seq_total = agg[mode]['seq_total']
            tok_total = agg[mode]['tok_total']
            sample_total = agg[mode]['sample_total']

            final_metrics[mode] = {
                'sequence_em': (agg[mode]['seq_em'] / seq_total) if seq_total > 0 else 0.0,
                'token_accuracy': (agg[mode]['tok_correct'] / tok_total) if tok_total > 0 else 0.0,
                'avg_pred_len': (agg[mode]['len_sum'] / sample_total) if sample_total > 0 else 0.0,
                'end_rate': (agg[mode]['end_sum'] / sample_total) if sample_total > 0 else 0.0
            }

        if collected_samples and save_samples and epoch is not None:
            suffix = f"{epoch + 1:03d}" if isinstance(epoch, int) else str(epoch)
            sample_path = self.eval_output_dir / f"generation_samples_{suffix}.json"
            with open(sample_path, 'w', encoding='utf-8') as f:
                json.dump(collected_samples, f, ensure_ascii=False, indent=2)

        if was_training:
            self.model.train()

        return final_metrics

    def validate_on_test(self):
        original_loader = self.val_loader
        self.val_loader = self.test_loader
        metrics = self.validate()
        self.val_loader = original_loader
        return metrics

    def train(self):
        print("=" * 80)
        print("开始训练任务条件化Transformer V3.7（Final）")
        print("=" * 80)
        print(f"  Device: {self.device}")
        print(f"  AMP: {'ON' if self.use_amp else 'OFF'}")
        print(f"  SS start: epoch {self.sampling_start_epoch}, end ratio: {self.sampling_end_ratio}")
        print(f"  Decode constraints: {self.decode_use_constraints} "
              f"(min_len={self.decode_min_length}, rep_pen={self.decode_repetition_penalty}, "
              f"no_repeat_ngram={self.decode_no_repeat_ngram}, end_bias={self.decode_end_length_bias})")
        print(f"  Checkpoints: {self.checkpoint_dir}")
        print("=" * 80)

        for epoch in range(self.num_epochs):
            print(f"\nEpoch {epoch+1}/{self.num_epochs}")
            print("-" * 80)

            train_metrics = self.train_epoch(epoch)
            val_metrics = self.validate()
            gen_metrics = self.evaluate_generation(epoch=epoch, num_batches=self.generation_eval_batches)

            self.scheduler.step()
            current_lr = self.optimizer.param_groups[0]['lr']
            tf_ratio = self._get_teacher_forcing_ratio(epoch)

            self.train_history['train_loss'].append(train_metrics['loss'])
            self.train_history['train_main_loss'].append(train_metrics['main_loss'])
            self.train_history['train_aux_loss'].append(train_metrics['aux_loss'])
            self.train_history['val_loss'].append(val_metrics['loss'])
            self.train_history['val_main_loss'].append(val_metrics['main_loss'])
            self.train_history['val_aux_loss'].append(val_metrics['aux_loss'])
            self.train_history['val_perplexity'].append(val_metrics['perplexity'])
            self.train_history['val_top1_acc'].append(val_metrics['top1_acc'])
            self.train_history['val_top5_acc'].append(val_metrics['top5_acc'])
            self.train_history['val_top10_acc'].append(val_metrics['top10_acc'])
            self.train_history['val_tf_sequence_em'].append(val_metrics['tf_sequence_em'])

            free = gen_metrics.get('free', {})
            cons = gen_metrics.get('cons', {})
            self.train_history['val_gen_free_seq_em'].append(free.get('sequence_em', 0.0))
            self.train_history['val_gen_free_token_acc'].append(free.get('token_accuracy', 0.0))
            self.train_history['val_gen_free_avg_len'].append(free.get('avg_pred_len', 0.0))
            self.train_history['val_gen_free_end_rate'].append(free.get('end_rate', 0.0))
            self.train_history['val_gen_cons_seq_em'].append(cons.get('sequence_em', 0.0))
            self.train_history['val_gen_cons_token_acc'].append(cons.get('token_accuracy', 0.0))
            self.train_history['val_gen_cons_avg_len'].append(cons.get('avg_pred_len', 0.0))
            self.train_history['val_gen_cons_end_rate'].append(cons.get('end_rate', 0.0))

            self.train_history['learning_rate'].append(current_lr)
            self.train_history['teacher_forcing_ratio'].append(tf_ratio)

            print(f"\nEpoch {epoch+1} Summary:")
            print(f"  Train: Loss={train_metrics['loss']:.4f} (Main={train_metrics['main_loss']:.4f}, Aux={train_metrics['aux_loss']:.4f})")
            print(f"  Val:   Loss={val_metrics['loss']:.4f} (Main={val_metrics['main_loss']:.4f}) | PPL={val_metrics['perplexity']:.2f}")
            print(f"  Val Acc: Top1={val_metrics['top1_acc']*100:.1f}%, Top5={val_metrics['top5_acc']*100:.1f}%, Top10={val_metrics['top10_acc']*100:.1f}%")
            print(f"  Val TF SeqEM: {val_metrics['tf_sequence_em']*100:.1f}%")
            print(f"  Gen FREE: SeqEM={free.get('sequence_em',0)*100:.1f}%, TokenAcc={free.get('token_accuracy',0)*100:.1f}%, "
                  f"AvgLen={free.get('avg_pred_len',0):.2f}, EndRate={free.get('end_rate',0)*100:.1f}%")
            print(f"  Gen CONS: SeqEM={cons.get('sequence_em',0)*100:.1f}%, TokenAcc={cons.get('token_accuracy',0)*100:.1f}%, "
                  f"AvgLen={cons.get('avg_pred_len',0):.2f}, EndRate={cons.get('end_rate',0)*100:.1f}%")
            print(f"  TF Ratio: {tf_ratio:.2f}, LR: {current_lr:.6f}")

            if val_metrics['loss'] < self.best_val_loss:
                self.best_val_loss = val_metrics['loss']
                self.epochs_without_improvement = 0
                checkpoint_path = self.checkpoint_dir / "best_model.pth"
                torch.save(self.model.state_dict(), checkpoint_path)
                print(f"  [OK] New best saved: {checkpoint_path} (Val Loss: {val_metrics['loss']:.4f})")
            else:
                self.epochs_without_improvement += 1
                print(f"  No improvement for {self.epochs_without_improvement} epoch(s)")

            if self.epochs_without_improvement >= self.early_stopping_patience:
                print(f"\nEarly stopping triggered after {epoch+1} epochs")
                break

        print("\n" + "=" * 80)
        print("训练完成！")
        print(f"Best validation loss: {self.best_val_loss:.4f}")
        print("=" * 80)

        print("\n加载最佳模型进行最终评估...")
        best_state = torch.load(self.checkpoint_dir / "best_model.pth", map_location=self.device)
        self.model.load_state_dict(best_state)

        test_metrics = self.validate_on_test()
        print(f"\nTest Set Performance:")
        print(f"  Test Loss: {test_metrics['loss']:.4f} | PPL={test_metrics['perplexity']:.2f}")
        print(f"  Test Acc:  Top1={test_metrics['top1_acc']*100:.1f}%, Top5={test_metrics['top5_acc']*100:.1f}%, Top10={test_metrics['top10_acc']*100:.1f}%")
        print(f"  Test TF SeqEM: {test_metrics['tf_sequence_em']*100:.1f}%")

        test_generation = self.evaluate_generation(epoch='test', num_batches=self.generation_eval_batches, loader=self.test_loader, save_samples=True)
        free = test_generation.get('free', {})
        cons = test_generation.get('cons', {})
        print(f"  Test Gen FREE: SeqEM={free.get('sequence_em',0)*100:.1f}%, TokenAcc={free.get('token_accuracy',0)*100:.1f}%, "
              f"AvgLen={free.get('avg_pred_len',0):.2f}, EndRate={free.get('end_rate',0)*100:.1f}%")
        print(f"  Test Gen CONS: SeqEM={cons.get('sequence_em',0)*100:.1f}%, TokenAcc={cons.get('token_accuracy',0)*100:.1f}%, "
              f"AvgLen={cons.get('avg_pred_len',0):.2f}, EndRate={cons.get('end_rate',0)*100:.1f}%")

        history_path = self.checkpoint_dir / "training_history_v3_7_final.json"
        with open(history_path, 'w', encoding='utf-8') as f:
            json.dump({'metrics': self.train_history, 'config': self.training_config}, f, indent=2, ensure_ascii=False)
        print(f"\n训练历史已保存到: {history_path}")

        return self.train_history


# =========================
# Dataset
# =========================
class TaskConditionedL3DatasetV3(Dataset):
    """
    任务条件化的L3序列数据集 V3.7（稳健过滤 + text_hash LRU缓存 + 正确的 max_seq_length+1 shift）
    """

    def __init__(
        self,
        workflows,
        task_vocab_builder,
        bert_tokenizer,
        max_seq_length=100,
        max_text_length=128
    ):
        self.task_vocab_builder = task_vocab_builder
        self.bert_tokenizer = bert_tokenizer
        self.max_seq_length = max_seq_length
        self.max_text_length = max_text_length

        # 将负数 special token 映射到“训练用正数空间”
        self.special_tokens_mapping = {
            token_id: VOCAB_SIZE + abs(token_id) - 1
            for token_id in SPECIAL_TOKENS.values()
        }

        self.workflows = self._filter_workflows(workflows)
        self.filtered_out = len(workflows) - len(self.workflows)
        if self.filtered_out > 0:
            print(f"  [Dataset] 跳过无效工作流: {self.filtered_out}")

        # LRU cache（key 用 text_hash）
        self.text_cache = OrderedDict()
        self.text_cache_size = 2048

    def _filter_workflows(self, workflows):
        valid = []
        # 兼容两种数据：原始负数 vs 已映射正数
        original_start = SPECIAL_TOKENS['<START>']
        original_end = SPECIAL_TOKENS['<END>']
        start_candidates = {original_start, START_TOKEN_ID}
        end_candidates = {original_end, END_TOKEN_ID}

        for wf in workflows:
            seq = wf.get('l3_sequence', [])
            if not seq or len(seq) < 3:
                continue
            if seq[0] not in start_candidates or seq[-1] not in end_candidates:
                continue
            valid.append(wf)
        return valid

    def _get_text_encoding(self, combined_text: str):
        text_hash = hashlib.md5(combined_text.encode('utf-8')).hexdigest()
        cached = self.text_cache.get(text_hash)
        if cached is not None:
            self.text_cache.move_to_end(text_hash)
            return cached

        tokenized = self.bert_tokenizer(
            combined_text,
            max_length=self.max_text_length,
            padding='max_length',
            truncation=True,
            return_tensors='pt'
        )
        encoded = {
            'input_ids': tokenized['input_ids'].squeeze(0),
            'attention_mask': tokenized['attention_mask'].squeeze(0)
        }

        if len(self.text_cache) >= self.text_cache_size:
            self.text_cache.popitem(last=False)
        self.text_cache[text_hash] = encoded
        return encoded

    def _convert_token_ids(self, token_list):
        return [self.special_tokens_mapping.get(t, t) for t in token_list]

    def __len__(self):
        return len(self.workflows)

    def __getitem__(self, idx):
        wf = self.workflows[idx]

        # ✅ 先截断到 max_seq_length+1，再 shift 后刚好 max_seq_length
        l3_sequence = wf['l3_sequence'][:self.max_seq_length + 1]

        task_meta = wf.get('task_metadata', {}) or {}
        task_type = task_meta.get('task_type', 'Unknown') or 'Unknown'
        task_type_id = self.task_vocab_builder.encode(task_type)

        task_name = (task_meta.get('task_name', '') or '').strip()
        task_desc = (task_meta.get('task_description', '') or '').strip()
        combined_text = " ".join(filter(None, [task_name, task_desc]))
        text_encoded = self._get_text_encoding(combined_text)

        # shift
        input_ids = l3_sequence[:-1]
        target_ids = l3_sequence[1:]

        # 转换 special token 到正数空间
        input_ids = self._convert_token_ids(input_ids)
        target_ids = self._convert_token_ids(target_ids)

        seq_len = len(input_ids)
        if seq_len > self.max_seq_length:
            input_ids = input_ids[:self.max_seq_length]
            target_ids = target_ids[:self.max_seq_length]
            seq_len = self.max_seq_length

        if seq_len < self.max_seq_length:
            pad_len = self.max_seq_length - seq_len
            input_ids = input_ids + [PAD_INDEX] * pad_len
            target_ids = target_ids + [PAD_INDEX] * pad_len

        attention_mask = [1] * seq_len + [0] * (self.max_seq_length - seq_len)

        return {
            'input_ids': torch.tensor(input_ids, dtype=torch.long),
            'target_ids': torch.tensor(target_ids, dtype=torch.long),
            'task_type_id': torch.tensor(task_type_id, dtype=torch.long),
            'text_input_ids': text_encoded['input_ids'].clone(),
            'text_attention_mask': text_encoded['attention_mask'].clone(),
            'attention_mask': torch.tensor(attention_mask, dtype=torch.long),
            'seq_len': seq_len
        }


# =========================
# Split
# =========================
def load_or_create_dataset_splits(workflows, split_path, train_ratio=0.8, val_ratio=0.1, seed=42):
    total = len(workflows)
    test_ratio = 1.0 - train_ratio - val_ratio
    assert train_ratio > 0 and val_ratio >= 0 and test_ratio >= 0, "比例不合法"
    assert abs(train_ratio + val_ratio + test_ratio - 1.0) < 1e-6, "train/val/test 比例之和必须为 1"

    if split_path.exists():
        with open(split_path, 'r', encoding='utf-8') as f:
            saved = json.load(f)
        if (len(saved.get('train_indices', []))
            + len(saved.get('val_indices', []))
            + len(saved.get('test_indices', [])) == total):
            return saved
        print("  [Split] 现有划分与数据量不匹配，重新生成。")

    labels = [
        ((wf.get('task_metadata', {}) or {}).get('task_type', 'Unknown') or 'Unknown')
        for wf in workflows
    ]
    indices = np.arange(total)

    cnt = Counter(labels)
    min_count = min(cnt.values()) if cnt else 0
    num_classes = len(cnt)

    can_stratify = (
        train_test_split is not None
        and num_classes > 1
        and min_count >= 2
    )

    if can_stratify:
        train_indices, temp_indices, train_labels, temp_labels = train_test_split(
            indices,
            labels,
            test_size=val_ratio + test_ratio,
            random_state=seed,
            stratify=labels
        )

        if val_ratio + test_ratio > 0:
            if val_ratio == 0:
                val_indices = np.array([], dtype=int)
                test_indices = temp_indices
            elif test_ratio == 0:
                val_indices = temp_indices
                test_indices = np.array([], dtype=int)
            else:
                val_indices, test_indices = train_test_split(
                    temp_indices,
                    test_size=test_ratio / (val_ratio + test_ratio),
                    random_state=seed,
                    stratify=temp_labels
                )
        else:
            val_indices = np.array([], dtype=int)
            test_indices = np.array([], dtype=int)

        print(f"  [Split] 使用 stratify 分层划分：classes={num_classes}, min_count={min_count}")

    else:
        rng = np.random.default_rng(seed)
        shuffled = rng.permutation(indices)
        n_train = int(train_ratio * total)
        n_val = int(val_ratio * total)
        train_indices = shuffled[:n_train]
        val_indices = shuffled[n_train:n_train + n_val]
        test_indices = shuffled[n_train + n_val:]

        reason = []
        if train_test_split is None:
            reason.append("sklearn 不可用")
        if num_classes <= 1:
            reason.append("类别数<=1")
        if min_count < 2:
            reason.append(f"存在极小类(min_count={min_count})")
        print("  [Split] 无法分层，降级为随机划分：" + ", ".join(reason))

        rare = [k for k, v in cnt.items() if v < 2]
        if rare:
            print(f"  [Split] 极小类(样本<2)数量: {len(rare)}，示例: {rare[:10]}")

    split_dict = {
        'train_indices': train_indices.tolist(),
        'val_indices': val_indices.tolist(),
        'test_indices': test_indices.tolist()
    }

    with open(split_path, 'w', encoding='utf-8') as f:
        json.dump(split_dict, f, indent=2, ensure_ascii=False)
    print(f"  [Split] 划分已保存到: {split_path}")

    return split_dict


# =========================
# Integrity check（可选）
# =========================
def verify_data_integrity(dataset, model, device):
    print("\n[数据完整性验证]")

    if len(dataset) == 0:
        print("  错误: 数据集为空")
        return False

    sample = dataset[0]
    print(f"  input_ids shape: {tuple(sample['input_ids'].shape)}")
    print(f"  target_ids shape: {tuple(sample['target_ids'].shape)}")
    print(f"  PAD_INDEX: {PAD_INDEX}")
    print(f"  PAD in input_ids: {(sample['input_ids'] == PAD_INDEX).sum().item()}")
    print(f"  PAD in target_ids: {(sample['target_ids'] == PAD_INDEX).sum().item()}")
    print(f"  START_TOKEN_ID: {START_TOKEN_ID}, END_TOKEN_ID: {END_TOKEN_ID}")

    if model is None:
        print("  (跳过前向传播验证：model=None)")
        return True

    model.eval()
    with torch.no_grad():
        try:
            batch = {k: v.unsqueeze(0).to(device) for k, v in sample.items() if isinstance(v, torch.Tensor)}
            logits, task_logits = model(
                batch['input_ids'],
                batch['task_type_id'],
                batch['text_input_ids'],
                batch['text_attention_mask'],
                attention_mask=batch['attention_mask'],
                return_task_logits=True
            )
            print("  模型前向传播成功")
            print(f"  logits: {tuple(logits.shape)} | task_logits: {tuple(task_logits.shape)}")
            return True
        except Exception as e:
            print(f"  模型前向传播失败: {e}")
            return False


# =========================
# Main
# =========================
def main():
    print("=" * 80)
    print("任务条件化L3 Transformer训练 V3.7（Final 稳健版）")
    print("=" * 80)

    # =========================
    # 训练配置
    # =========================
    SEED = 42
    set_seed(SEED)

    # 使用配置文件中的参数（不要硬编码）
    # BATCH_SIZE, LEARNING_RATE, NUM_EPOCHS 等都从 transformer_config.py 导入
    NUM_WORKERS = 0
    WARMUP_EPOCHS = 2  # 学习率预热轮数

    AUX_TASK_WEIGHT = 0.05

    SAMPLING_STRATEGY = 'linear'
    SAMPLING_START_EPOCH = 10
    SAMPLING_END_RATIO = 0.3
    SS_REFINE_STEPS = 1
    SS_KEEP_PREFIX_RATIO = 0.2

    GENERATION_EVAL_BATCHES = 1
    GENERATION_SAMPLE_SIZE = 5

    MAX_TEXT_LENGTH = 128

    # 从头训练配置（使用L3嵌入初始化）
    PRETRAINED = False  # 设置为False表示从头训练，不加载旧的checkpoint
    PRETRAINED_PATH = OUTPUT_DIR / "task_conditioned_checkpoints_v3" / "best_model.pth"
    CHECKPOINT_DIR = TRANSFORMER_CHECKPOINT_DIR  # 使用配置文件中的checkpoint目录

    print(f"\n配置:")
    print(f"  Seed: {SEED}")
    print(f"  Device: {DEVICE}")
    print(f"  Epochs: {NUM_EPOCHS}, LR: {LEARNING_RATE}, Warmup: {WARMUP_EPOCHS}, Batch: {BATCH_SIZE}")
    print(f"  SS start: {SAMPLING_START_EPOCH}, end_ratio: {SAMPLING_END_RATIO}, keep_prefix: {SS_KEEP_PREFIX_RATIO}")
    print(f"  BERT freeze: {FREEZE_BERT}, max_memory_tokens: {MAX_MEMORY_TOKENS}")
    print(f"  从头训练: {not PRETRAINED} (使用L3嵌入初始化)")
    print(f"  Checkpoints: {CHECKPOINT_DIR}")

    # 使用配置文件中的路径
    LABELED_WORKFLOWS_PATH_LOCAL = LABELED_WORKFLOWS_PATH  # 从transformer_config导入
    TASK_TYPE_VOCAB_PATH = OUTPUT_DIR / "task_type_vocabulary.json"
    L3_EMBEDDINGS_PATH_LOCAL = L3_EMBEDDINGS_PATH  # 从transformer_config导入

    # [1] Load data
    print("\n[1] 加载数据...")
    with open(LABELED_WORKFLOWS_PATH_LOCAL, 'r', encoding='utf-8') as f:
        data = json.load(f)
    workflows = data['labeled_workflows']
    print(f"  数据文件: {LABELED_WORKFLOWS_PATH_LOCAL}")
    print(f"  工作流数量: {len(workflows)}")

    # [2] Load vocab + tokenizer
    print("\n[2] 加载词汇表和BERT tokenizer...")
    with open(TASK_TYPE_VOCAB_PATH, 'r', encoding='utf-8') as f:
        task_type_vocab = json.load(f)

    task_vocab_builder = TaskVocabularyBuilder()
    if hasattr(task_vocab_builder, "task_type_to_id"):
        task_vocab_builder.task_type_to_id = task_type_vocab['task_type_to_id']
    if hasattr(task_vocab_builder, "type_to_id"):
        task_vocab_builder.type_to_id = task_type_vocab['task_type_to_id']

    if hasattr(task_vocab_builder, "id_to_task_type"):
        task_vocab_builder.id_to_task_type = {int(k): v for k, v in task_type_vocab['id_to_task_type'].items()}
    if hasattr(task_vocab_builder, "id_to_type"):
        # 注意：这里如果你类里叫 id_to_type，就映射同一份
        task_vocab_builder.id_to_type = {int(k): v for k, v in task_type_vocab['id_to_task_type'].items()}

    print(f"  任务类型数量: {task_type_vocab['num_types']}")
    bert_tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')
    print("  BERT tokenizer加载完成")

    # [3] Split dataset
    print("\n[3] 划分数据集...")
    split_path = OUTPUT_DIR / "dataset_splits_v3.json"
    splits = load_or_create_dataset_splits(workflows, split_path, train_ratio=0.8, val_ratio=0.1, seed=SEED)

    train_indices = [int(i) for i in splits['train_indices']]
    val_indices = [int(i) for i in splits['val_indices']]
    test_indices = [int(i) for i in splits['test_indices']]

    train_workflows = [workflows[i] for i in train_indices]
    val_workflows = [workflows[i] for i in val_indices]
    test_workflows = [workflows[i] for i in test_indices]

    print(f"  Train: {len(train_workflows)}")
    print(f"  Val:   {len(val_workflows)}")
    print(f"  Test:  {len(test_workflows)}")

    # [4] Datasets & Loaders
    print("\n[4] 创建DataLoader...")
    train_dataset = TaskConditionedL3DatasetV3(train_workflows, task_vocab_builder, bert_tokenizer,
                                               max_seq_length=100, max_text_length=MAX_TEXT_LENGTH)
    val_dataset = TaskConditionedL3DatasetV3(val_workflows, task_vocab_builder, bert_tokenizer,
                                             max_seq_length=100, max_text_length=MAX_TEXT_LENGTH)
    test_dataset = TaskConditionedL3DatasetV3(test_workflows, task_vocab_builder, bert_tokenizer,
                                              max_seq_length=100, max_text_length=MAX_TEXT_LENGTH)

    # 数据完整性（不传 model 也能跑）
    verify_data_integrity(train_dataset, None, DEVICE)

    train_loader = DataLoader(
        train_dataset,
        batch_size=BATCH_SIZE,
        shuffle=True,
        num_workers=NUM_WORKERS,
        pin_memory=True if DEVICE.type == 'cuda' else False
    )
    val_loader = DataLoader(
        val_dataset,
        batch_size=BATCH_SIZE,
        shuffle=False,
        num_workers=NUM_WORKERS,
        pin_memory=True if DEVICE.type == 'cuda' else False
    )
    test_loader = DataLoader(
        test_dataset,
        batch_size=BATCH_SIZE,
        shuffle=False,
        num_workers=NUM_WORKERS,
        pin_memory=True if DEVICE.type == 'cuda' else False
    )

    # [5] Model
    print("\n[5] 创建模型...")
    model = TaskConditionedL3TransformerModelV3(
        vocab_size=TOTAL_VOCAB_SIZE,
        num_task_types=task_type_vocab['num_types'],
        d_model=D_MODEL,
        n_heads=N_HEADS,
        n_layers=N_LAYERS,
        dim_feedforward=D_FF,
        dropout=DROPOUT,
        max_seq_length=MAX_SEQ_LENGTH,
        max_memory_tokens=MAX_MEMORY_TOKENS,
        use_l3_embeddings=USE_L3_EMBEDDINGS,
        l3_embeddings_path=L3_EMBEDDINGS_PATH_LOCAL,  # 使用配置文件中的路径
        freeze_bert=FREEZE_BERT,
        embedding_dropout=EMBEDDING_DROPOUT
    )

    # Warm-start（只在PRETRAINED=True时执行）
    if PRETRAINED and PRETRAINED_PATH.exists():
        print(f"\n[Warm-start] 从checkpoint加载: {PRETRAINED_PATH}")
        warmstart_resize_memory_pe_only(model, PRETRAINED_PATH, DEVICE, pe_key="memory_positional_encoding.pe", noise_std=1e-4)
    else:
        if PRETRAINED:
            print(f"\n[WARNING] PRETRAINED=True 但未找到checkpoint: {PRETRAINED_PATH}")
        print("\n[从头训练] 使用L3嵌入初始化，不加载旧checkpoint")

    model = model.to(DEVICE)

    # 前向传播验证（真实 batch）
    print("\n[模型前向传播验证]")
    model.eval()
    with torch.no_grad():
        sample_batch = next(iter(train_loader))
        for key in sample_batch:
            if isinstance(sample_batch[key], torch.Tensor):
                sample_batch[key] = sample_batch[key].to(DEVICE)
        logits, task_logits = model(
            sample_batch['input_ids'],
            sample_batch['task_type_id'],
            sample_batch['text_input_ids'],
            sample_batch['text_attention_mask'],
            attention_mask=sample_batch['attention_mask'],
            return_task_logits=True
        )
        print(f"  logits: {tuple(logits.shape)} (应为 [B, seq_len, vocab])")
        print(f"  task_logits: {tuple(task_logits.shape)} (应为 [B, num_task_types])")

    num_params = sum(p.numel() for p in model.parameters() if p.requires_grad)
    print(f"  可训练参数量: {num_params / 1e6:.2f}M")

    # [6] Trainer
    print("\n[6] 创建训练器...")
    trainer = ScheduledSamplingTrainerV3(
        model=model,
        train_loader=train_loader,
        val_loader=val_loader,
        test_loader=test_loader,
        lr=LEARNING_RATE,
        num_epochs=NUM_EPOCHS,
        warmup_epochs=WARMUP_EPOCHS,
        device=DEVICE,
        checkpoint_dir=CHECKPOINT_DIR,
        aux_task_weight=AUX_TASK_WEIGHT,
        early_stopping_patience=5,
        label_smoothing=LABEL_SMOOTHING,
        sampling_strategy=SAMPLING_STRATEGY,
        sampling_start_epoch=SAMPLING_START_EPOCH,
        sampling_end_ratio=SAMPLING_END_RATIO,
        use_amp=True,
        ss_refine_steps=SS_REFINE_STEPS,
        ss_keep_prefix_ratio=SS_KEEP_PREFIX_RATIO,
        generation_eval_batches=GENERATION_EVAL_BATCHES,
        generation_sample_size=GENERATION_SAMPLE_SIZE,
        decode_use_constraints=True,
        decode_min_length=6,
        decode_repetition_penalty=1.2,
        decode_no_repeat_ngram=3,
        decode_end_length_bias=0.1
    )

    # [7] Train
    training_mode = "Warm-start续训" if PRETRAINED else "从头训练（使用L3嵌入初始化）"
    print(f"\n开始训练（{training_mode}）...")
    print("="*80)
    print(f"训练配置: {NUM_EPOCHS} epochs, LR={LEARNING_RATE}, Batch={BATCH_SIZE}")
    print(f"数据集: {len(workflows)} workflows")
    print("="*80)
    history = trainer.train()

    # [8] Save final
    final_model_path = CHECKPOINT_DIR / "final_model.pth"
    torch.save(model.state_dict(), final_model_path)
    print(f"\n最终模型已保存到: {final_model_path}")

    print("\n" + "=" * 80)
    print("所有任务完成！")
    print("=" * 80)

    return history


if __name__ == "__main__":
    main()
