# -*- coding: utf-8 -*-
"""
V4.6 Training: Gradient Fix + AR Metric Snapshotting

修复代码评审发现的 3 个结构性 bug:
  Bug 1: AR 主损失的梯度被 detach 切断 → 移除 memory/condition detach
  Bug 2: aux loss 在 no_grad 里计算 → 移除 no_grad wrapper
  Bug 3: AR metrics are recorded without selecting checkpoints or stopping training

继承 V4.5 的:
  - WeightedRandomSampler (balanced task sampling)
  - task_cls_loss_weight = 0.3
  - Length-aware improvements from V4.4

Usage:
    python -m gis_recommend.training.train_v4_6
"""

from __future__ import annotations

import json
import math
import random
import sys
from pathlib import Path

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader, Subset
from torch.amp import autocast
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
    V4_2_NUM_WORKERS,
    V4_2_GEN_EVAL_BATCHES, V4_2_GRADIENT_ACCUM_STEPS,
    # V4.6 specific
    V4_6_TRANSFORMER_CHECKPOINT_DIR, V4_6_WARMSTART_PATH,
    V4_6_NUM_EPOCHS, V4_6_TF_PHASE_EPOCHS,
    V4_6_SS_TF_START, V4_6_SS_TF_END,
    V4_6_AR_RATIO_START, V4_6_AR_RATIO_END,
    V4_6_WARMUP_EPOCHS, V4_6_EARLY_STOPPING_PATIENCE,
    V4_6_OTHER_LR, V4_6_BERT_LR, V4_6_BATCH_SIZE,
    V4_6_GRADIENT_ACCUM_STEPS, V4_6_AR_MAX_STEPS,
    V4_6_LENGTH_LOSS_WEIGHT,
    V4_6_EARLY_END_PENALTY, V4_6_EARLY_END_THRESHOLD,
    V4_6_AR_DYNAMIC_MIN_RATIO,
    V4_6_TASK_CLS_LOSS_WEIGHT,
)
from gis_recommend.models.transformer_model_v4 import TaskConditionedL3TransformerModelV4
from gis_recommend.models.task_text_processor import TaskVocabularyBuilder
from gis_recommend.training.loss_utils import weighted_sequence_cross_entropy
from gis_recommend.training.train_v4_2 import (
    TaskConditionedL3DatasetV4,
    compute_token_freq_weights,
    load_or_create_splits,
    set_seed,
    PAD_INDEX, UNK_INDEX, START_INDEX, END_INDEX,
)
from gis_recommend.training.train_v4_4 import load_warmstart_checkpoint
from gis_recommend.training.train_v4_5 import (
    ScheduledSamplingTrainerV4_5,
    build_task_type_sampler,
)

__all__ = [
    "ScheduledSamplingTrainerV4_6",
    "split_ar_logits_for_loss_and_sampling",
    "weighted_sequence_cross_entropy",
]


def _add_to_other_param_group(optimizer, params: list):
    """Add parameters to the 'other' (non-BERT) param group.

    Falls back to the last param group if there is only one group.
    """
    groups = optimizer.param_groups
    target_idx = 1 if len(groups) >= 2 else len(groups) - 1
    groups[target_idx]["params"].extend(params)


def _as_task_type_id_list(task_type_ids) -> list[int]:
    if isinstance(task_type_ids, torch.Tensor):
        return [int(v) for v in task_type_ids.detach().cpu().tolist()]
    return [int(v) for v in task_type_ids]


def save_metric_selection_snapshots(checkpoint_dir: Path, payload: dict, gen_m: dict | None, epoch: int, state: dict) -> dict:
    """Save observation-only metric-best snapshots alongside the latest checkpoint."""
    if gen_m is None:
        return state
    next_state = dict(state)
    next_state.setdefault("best_gen_set_f1", float("-inf"))
    next_state.setdefault("best_gen_lcs", float("-inf"))
    next_state.setdefault("best_gen_composite", float("-inf"))
    next_state.setdefault("manifest", {
        "latest_snapshot": "best_model.pth",
        "latest_snapshot_note": "historical compatibility name; overwritten each epoch",
        "selection_snapshots": {},
    })

    gen_set_f1 = gen_m.get("ar_set_f1")
    if gen_set_f1 is not None and gen_set_f1 > next_state["best_gen_set_f1"]:
        next_state["best_gen_set_f1"] = gen_set_f1
        set_path = checkpoint_dir / "best_gen_set_f1_model.pth"
        torch.save(payload, set_path)
        next_state["manifest"]["selection_snapshots"]["gen_set_f1"] = {
            "path": set_path.name,
            "epoch": epoch,
            "value": gen_set_f1,
        }

    gen_lcs = gen_m.get("ar_lcs")
    if gen_lcs is not None and gen_lcs > next_state["best_gen_lcs"]:
        next_state["best_gen_lcs"] = gen_lcs
        lcs_path = checkpoint_dir / "best_gen_lcs_model.pth"
        torch.save(payload, lcs_path)
        next_state["manifest"]["selection_snapshots"]["gen_lcs"] = {
            "path": lcs_path.name,
            "epoch": epoch,
            "value": gen_lcs,
        }

    gen_composite = _compute_composite_metric(gen_m)
    if gen_composite is not None and gen_composite > next_state["best_gen_composite"]:
        next_state["best_gen_composite"] = gen_composite
        comp_path = checkpoint_dir / "best_gen_composite_model.pth"
        torch.save(payload, comp_path)
        next_state["manifest"]["selection_snapshots"]["gen_composite"] = {
            "path": comp_path.name,
            "epoch": epoch,
            "value": gen_composite,
            "formula": "0.5*SetF1 + 0.3*LCS + 0.2*(1 - early_eos_rate)",
        }
    return next_state


def _compute_composite_metric(gen_m: dict) -> float | None:
    set_f1 = gen_m.get("ar_set_f1")
    lcs = gen_m.get("ar_lcs")
    early_eos = gen_m.get("early_eos_rate")
    if set_f1 is None or lcs is None or early_eos is None:
        return None
    return 0.5 * float(set_f1) + 0.3 * float(lcs) + 0.2 * (1.0 - float(early_eos))


def split_ar_logits_for_loss_and_sampling(logits, *, dynamic_min_lengths, step_index,
                                           decoder_input=None, transition_mask=None):
    """Keep CE logits unmasked while applying decode-only constraints to sampling logits.

    Constraints on sampling logits only (mirrors inference _apply_constraints):
      - dynamic min-length END block
      - transition mask (hard -inf for illegal next tokens)
      - special token block (PAD, UNK, START)
    """
    loss_logits = logits
    sampling_logits = logits.clone()
    # dynamic min-length: block END for early steps
    block_end = step_index < dynamic_min_lengths
    if block_end.any():
        sampling_logits[block_end, END_INDEX] = float("-inf")
    # special token block
    sampling_logits[:, PAD_INDEX] = float("-inf")
    sampling_logits[:, UNK_INDEX] = float("-inf")
    sampling_logits[:, START_INDEX] = float("-inf")
    # transition constraint (same as inference)
    if transition_mask and decoder_input is not None:
        _apply_transition_mask_to_logits(sampling_logits, decoder_input, transition_mask, END_INDEX)
    return loss_logits, sampling_logits


def _apply_transition_mask_to_logits(logits, decoder_input, transition_mask, end_index):
    """Apply hard transition constraint to logits in-place (per-sample)."""
    B = logits.size(0)
    if not transition_mask:
        return
    for b in range(B):
        prev_tokens = decoder_input[b, 1:].tolist()  # skip START
        if not prev_tokens:
            continue
        last_tok = prev_tokens[-1]
        if last_tok == end_index:
            continue
        allowed = transition_mask.get(last_tok)
        if allowed is not None:
            mask = torch.full((logits.size(1),), float("-inf"), device=logits.device)
            for tok in allowed:
                if tok < logits.size(1):
                    mask[tok] = 0.0
            mask[end_index] = 0.0
            logits[b] += mask


class ScheduledSamplingTrainerV4_6(ScheduledSamplingTrainerV4_5):
    """V4.6: Gradient fix + AR metrics recorded as checkpoint snapshots.

    Bug fixes over V4.5:
    - _train_step_autoregressive: 移除 memory/condition detach，AR 梯度可回传 BERT
    - _train_step_autoregressive: 移除 aux loss 的 no_grad，length/task loss 有实际梯度
    - train(): AR metrics are report-only and do not select checkpoints
    """

    BUCKET_TO_IDX = {"short": 0, "medium": 1, "long": 2, "very_long": 3}
    IDX_TO_BUCKET = {0: "short", 1: "medium", 2: "long", 3: "very_long"}
    NUM_BUCKETS = 4

    def __init__(
        self,
        *args,
        length_bucket_predictor=None,
        id_to_task_type=None,
        length_bucket_loss_weight: float = 0.0,
        bucket_cls_loss_weight: float = 0.0,
        qgis_unmappable_token_ids=None,
        qgis_unmappable_penalty: float = 0.0,
        ar_max_steps: int = V4_6_AR_MAX_STEPS,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.length_bucket_predictor = length_bucket_predictor
        self.id_to_task_type = dict(id_to_task_type or {})
        self.length_bucket_loss_weight = float(length_bucket_loss_weight)
        self.bucket_cls_loss_weight = float(bucket_cls_loss_weight)
        self.bucket_classifier = None
        self.qgis_unmappable_token_ids = set(qgis_unmappable_token_ids) if qgis_unmappable_token_ids else set()
        self.qgis_unmappable_penalty = float(qgis_unmappable_penalty)
        self.ar_max_steps = max(1, int(ar_max_steps))
        self.final_generation_eval_batches = max(16, int(getattr(self, "generation_eval_batches", 8) or 8))
        if self.qgis_unmappable_penalty > 0.0 and self.qgis_unmappable_token_ids:
            print(
                "  [V4.6] QGIS unmappable token penalty enabled "
                f"(weight={self.qgis_unmappable_penalty}, "
                f"unmappable_tokens={len(self.qgis_unmappable_token_ids)})"
            )
        if self.length_bucket_predictor is not None:
            if self.length_bucket_loss_weight > 0.0:
                print(
                    "  [V4.6] task_type length bucket MSE loss enabled "
                    f"(weight={self.length_bucket_loss_weight})"
                )
            if self.bucket_cls_loss_weight > 0.0:
                from gis_recommend.config.transformer_config import V4_D_MODEL
                self.bucket_classifier = nn.Linear(V4_D_MODEL // 2, self.NUM_BUCKETS).to(self.device)
                _add_to_other_param_group(self.optimizer, list(self.bucket_classifier.parameters()))
                print(
                    "  [V4.6] task_type length bucket CLS loss enabled "
                    f"(weight={self.bucket_cls_loss_weight}, {self.NUM_BUCKETS} classes)"
                )

    def _length_bucket_targets(self, task_type_ids):
        if self.length_bucket_predictor is None or self.length_bucket_loss_weight <= 0.0:
            return None
        expected_lengths = []
        for task_type_id in _as_task_type_id_list(task_type_ids):
            task_type = self.id_to_task_type.get(task_type_id, "Unknown")
            bucket = self.length_bucket_predictor.predict(task_type)
            expected_lengths.append(float(bucket.expected_length))
        return torch.tensor(expected_lengths, dtype=torch.float, device=self.device)

    def _bucket_class_targets(self, task_type_ids):
        """Return [B] tensor of bucket class indices (0-3) for classification loss."""
        if self.length_bucket_predictor is None or self.bucket_cls_loss_weight <= 0.0:
            return None
        indices = []
        for task_type_id in _as_task_type_id_list(task_type_ids):
            task_type = self.id_to_task_type.get(task_type_id, "Unknown")
            bucket = self.length_bucket_predictor.predict(task_type)
            indices.append(self.BUCKET_TO_IDX.get(bucket.bucket, 1))
        return torch.tensor(indices, dtype=torch.long, device=self.device)

    def _bucket_cls_loss(self, contrastive_repr, task_type_ids):
        """Cross-entropy loss for 4-class length bucket prediction."""
        targets = self._bucket_class_targets(task_type_ids)
        if targets is None or self.bucket_classifier is None:
            return torch.tensor(0.0, device=self.device), None
        logits = self.bucket_classifier(contrastive_repr)
        loss = F.cross_entropy(logits, targets)
        with torch.no_grad():
            acc = (logits.argmax(dim=-1) == targets).float().mean().item()
        return loss, acc

    def _length_bucket_loss(self, length_pred, task_type_ids):
        targets = self._length_bucket_targets(task_type_ids)
        if targets is None:
            return torch.tensor(0.0, device=self.device)
        log_targets = torch.log(targets.clamp(min=1))
        return F.mse_loss(length_pred.squeeze(-1), log_targets)

    def _train_step_autoregressive(self, batch, tf_ratio):
        """AR-SS step with full gradient flow (no detach, no no_grad for aux)."""
        target_ids = batch['target_ids'].to(self.device)
        task_type_ids = batch['task_type_id'].to(self.device)
        text_input_ids = batch['text_input_ids'].to(self.device)
        text_attention_mask = batch['text_attention_mask'].to(self.device)
        attention_mask = batch['attention_mask'].to(self.device)
        seq_lens = batch['seq_len']
        sample_weights = batch.get('sample_weight')
        if sample_weights is not None:
            sample_weights = sample_weights.to(self.device)

        B, T = target_ids.shape
        ar_max_steps = min(T, self.ar_max_steps)

        # Convert seq_lens to tensor
        if isinstance(seq_lens, torch.Tensor):
            target_lengths = seq_lens.to(self.device)
        else:
            target_lengths = torch.tensor(seq_lens, dtype=torch.long, device=self.device)

        # Dynamic min_length per sample
        dynamic_min_lengths = torch.clamp(
            (target_lengths.float() * self.ar_dynamic_min_ratio).long(), min=5
        )

        # ═══ Bug 1 Fix: Compute BERT memory WITH gradients, NO detach ═══
        memory_raw, memory_mask, text_pooled = self.model.text_encoder(
            text_input_ids, text_attention_mask
        )
        memory_proj = self.model.text_projection(memory_raw)
        memory = self.model.memory_positional_encoding(memory_proj)
        condition = self.model._fuse_condition(task_type_ids, text_pooled)

        # BERT anchor loss (保留，作为辅助)
        bert_condition_repr = self.model.contrastive_projector(
            self.model.condition_projection(text_pooled)
        )
        bert_task_loss = self._task_cls_loss(bert_condition_repr, task_type_ids)

        # ═══ 关键修复：不再 detach！AR 主损失梯度可以回传到 BERT ═══
        # memory_d = memory.detach()      # ← 删除
        # condition_d = condition.detach() # ← 删除
        memory_pad_mask = ~memory_mask if memory_mask is not None else None

        # Build decoder input token-by-token
        decoder_input = torch.full((B, 1), START_INDEX, dtype=torch.long, device=self.device)
        total_loss = torch.tensor(0.0, device=self.device)
        early_end_loss = torch.tensor(0.0, device=self.device)
        valid_steps = 0
        early_end_count = 0

        # Track generated lengths
        gen_lengths = torch.ones(B, dtype=torch.long, device=self.device)
        finished = torch.zeros(B, dtype=torch.bool, device=self.device)

        with autocast('cuda', enabled=self.use_amp):
            for t in range(ar_max_steps):
                step_mask = attention_mask[:, t]
                if step_mask.sum() == 0:
                    break

                # Embed decoder input — 使用有梯度的 condition（不是 condition_d）
                tok_emb = self.model.token_embedding(decoder_input)
                gamma = self.model.input_film_gamma(condition).unsqueeze(1)
                beta = self.model.input_film_beta(condition).unsqueeze(1)
                tok_emb = gamma * tok_emb + beta
                tok_emb = self.model.positional_encoding(tok_emb)

                cur_len = tok_emb.size(1)
                causal_mask = self.model._generate_causal_mask(cur_len, self.device)

                x = tok_emb
                for layer in self.model.decoder_layers:
                    x = layer(x, memory, condition,  # ← 使用有梯度的 memory/condition
                              tgt_mask=causal_mask,
                              memory_key_padding_mask=memory_pad_mask)
                x = self.model.decoder_norm(x)

                next_logits = self.model.output_projection(x[:, -1, :])
                loss_logits, sampling_logits = split_ar_logits_for_loss_and_sampling(
                    next_logits,
                    dynamic_min_lengths=dynamic_min_lengths,
                    step_index=t,
                    decoder_input=decoder_input,
                    transition_mask=self.transition_mask if self.transition_mask else None,
                )

                # CE loss
                loss_t = weighted_sequence_cross_entropy(
                    loss_logits,
                    target_ids[:, t],
                    sample_weights,
                    weight=self.ce_weight,
                    ignore_index=PAD_INDEX,
                    label_smoothing=self.label_smoothing,
                )
                total_loss = total_loss + loss_t
                valid_steps += 1

                # Early END penalty
                with torch.no_grad():
                    predicted_tokens = loss_logits.argmax(dim=-1)
                for b in range(B):
                    if (predicted_tokens[b].item() == END_INDEX
                            and t < target_lengths[b].item() * self.early_end_threshold
                            and not finished[b]):
                        end_ce = F.cross_entropy(
                            loss_logits[b:b+1], target_ids[b:b+1, t],
                            ignore_index=PAD_INDEX
                        )
                        early_end_loss = early_end_loss + self.early_end_penalty * end_ce
                        early_end_count += 1

                # Nucleus sampling for next token
                if random.random() < tf_ratio:
                    next_token = target_ids[:, t].unsqueeze(1)
                else:
                    with torch.no_grad():
                        next_token = self._nucleus_sample(sampling_logits).unsqueeze(1)
                    for b in range(B):
                        if next_token[b, 0].item() == END_INDEX:
                            finished[b] = True

                decoder_input = torch.cat([decoder_input, next_token], dim=1)
                gen_lengths += step_mask.long() * (~finished).long()

                if decoder_input.size(1) > self.model.max_seq_length:
                    break

            avg_loss = total_loss / max(valid_steps, 1)
            avg_early_end = early_end_loss / max(early_end_count, 1) if early_end_count > 0 else torch.tensor(0.0, device=self.device)

            # ═══ Bug 2 Fix: aux loss 不再用 no_grad ═══
            # gen_input 需要 detach（阻止 AR 梯度回流到 token embedding）
            gen_input = decoder_input[:, :-1].detach() if decoder_input.size(1) > 1 else decoder_input.detach()
            gen_attn = torch.zeros(B, gen_input.size(1), dtype=torch.long, device=self.device)
            for b in range(B):
                valid = min(gen_lengths[b].item(), gen_input.size(1))
                gen_attn[b, :valid] = 1

            # 不再 with torch.no_grad()！aux loss 现在有梯度
            _, aux = self.model(
                gen_input, task_type_ids,
                text_input_ids, text_attention_mask,
                attention_mask=gen_attn, return_aux=True,
            )

            # Length loss — 现在有梯度！
            length_loss_gt = self._length_loss(aux['length_pred'], seq_lens)
            log_gen = torch.log(gen_lengths.float().clamp(min=1))
            log_target = torch.log(target_lengths.float().clamp(min=1))
            length_loss_ar = F.mse_loss(log_gen, log_target)
            length_loss = length_loss_gt + length_loss_ar

            # Length bucket MSE (task-type expected length regression)
            length_bucket_loss = self._length_bucket_loss(aux['length_pred'], task_type_ids)

            # Task loss — 现在有梯度！
            task_loss = self._task_cls_loss(aux['contrastive_repr'], task_type_ids)

            # Bucket classification loss — 4-class short/medium/long/very_long
            bucket_cls_loss, bucket_acc = self._bucket_cls_loss(aux['contrastive_repr'], task_type_ids)

            # Total loss
            total_ar_loss = (avg_loss
                             + self.task_cls_loss_weight * bert_task_loss
                             + self.length_loss_weight * length_loss
                             + self.length_bucket_loss_weight * length_bucket_loss
                             + self.task_cls_loss_weight * task_loss
                             + self.bucket_cls_loss_weight * bucket_cls_loss
                             + avg_early_end)

            backward_loss = total_ar_loss / self.gradient_accum_steps

        if self.use_amp:
            self.scaler.scale(backward_loss).backward()
        else:
            backward_loss.backward()

        # One-time BERT gradient diagnostic (right after backward, before zero_grad)
        if not hasattr(self, '_bert_grad_checked'):
            self._bert_grad_checked = True
            bert_grad_ok = False
            for name, param in self.model.named_parameters():
                if name.startswith("text_encoder.bert.") and param.requires_grad:
                    if param.grad is not None and param.grad.abs().sum() > 0:
                        bert_grad_ok = True
                        break
            print(f"\n  [Diag] BERT top-layer gradients (after backward): "
                  f"{'OK ✓' if bert_grad_ok else 'MISSING ✗'}")

        del decoder_input, total_loss, backward_loss
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        return {
            'total_loss': total_ar_loss.item(),
            'main_loss': avg_loss.item(),
            'length_loss': length_loss.item(),
            'task_cls_loss': task_loss.item(),
            'transition_loss': 0.0,
            'bucket_cls_loss': bucket_cls_loss.item(),
            'bucket_accuracy': bucket_acc if bucket_acc is not None else 0.0,
        }

    # ═══ Override train() with early stopping on composite metric ═══
    def train(self):
        """Training loop with early stopping on composite metric (SetF1+LCS+anti-earlyEOS)."""
        import json

        history = []
        prev_phase = -1
        best_snapshot_state = {}
        best_composite = float("-inf")
        best_epoch = -1
        best_payload = None
        epochs_without_improvement = 0
        patience = getattr(self, "early_stopping_patience", 10)

        print(f"\n{'='*80}")
        print(f"V4.6 Training: Gradient Fix + Early Stopping (composite, patience={patience})")
        print(f"{'='*80}")
        print(f"  Device: {self.device}, AMP: {self.use_amp}")
        print(f"  Batch: {self.batch_size} x {self.gradient_accum_steps} accum = "
              f"{self.batch_size * self.gradient_accum_steps} effective")
        print(f"  LR: BERT={self.optimizer.param_groups[0]['lr']:.1e}, "
              f"Other={self.optimizer.param_groups[-1]['lr']:.1e}")
        print(f"  AR max steps: {self.ar_max_steps}")
        print(f"  Gen eval batches: {self.generation_eval_batches}")
        print(f"  Early stopping: patience={patience} on composite (0.5*SetF1+0.3*LCS+0.2*(1-earlyEOS))")
        print(f"{'='*80}\n")

        for epoch in range(self.num_epochs):
            print(f"\nEpoch {epoch+1}/{self.num_epochs}")
            print("-" * 70)

            # Curriculum phase (inline, same logic as base class)
            if epoch <= self.curriculum_p1_end:
                curr_phase = 0
            elif epoch <= self.curriculum_p2_end:
                curr_phase = 1
            else:
                curr_phase = 2
            if curr_phase != prev_phase and prev_phase >= 0:
                print(f"  [Curriculum] Phase {prev_phase} -> {curr_phase}")
            prev_phase = curr_phase

            if epoch == self.tf_phase_epochs:
                print(f"  [AR-SS] Starting autoregressive scheduled sampling")

            train_m = self.train_epoch(epoch)
            val_m = self.validate()

            # ═══ 关键修复：每个 epoch 都跑 AR 评估 ═══
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
                  f"tcls={train_m.get('task_cls_loss', 0):.3f}"
                  f"{', bktCls=' + str(round(train_m.get('bucket_cls_loss', 0), 3)) if train_m.get('bucket_cls_loss', 0) != 0.0 else ''}"
                  f"{', bktAcc=' + str(round(train_m.get('bucket_accuracy', 0)*100)) + '%' if train_m.get('bucket_accuracy', 0) != 0.0 else ''})")
            print(f"  Val:   Loss={val_m['loss']:.4f} | PPL={val_m['perplexity']:.1f} | "
                  f"Top1={val_m['top1_acc']*100:.1f}% Top5={val_m['top5_acc']*100:.1f}% "
                  f"TF-SeqEM={val_m['tf_sequence_em']*100:.1f}% "
                  f"avglen(ref)={val_m.get('mean_ref_length', 0):.1f}")
            if gen_m:
                print(f"  Gen:   AR-SeqEM={gen_m.get('ar_seq_em',0)*100:.1f}% "
                      f"AR-TokenAcc={gen_m.get('ar_token_acc',0)*100:.1f}%")
                print(f"         AR-LCS={gen_m.get('ar_lcs',0):.3f} "
                      f"AR-SetF1={gen_m.get('ar_set_f1',0):.3f}")
                print(f"         len(pred)={gen_m.get('mean_pred_length',0):.1f} "
                      f"len(ref)={gen_m.get('mean_ref_length',0):.1f} "
                      f"|lenErr|={gen_m.get('length_abs_error',0):.1f} "
                      f"earlyEOS={gen_m.get('early_eos_rate',0)*100:.1f}% "
                      f"empty={gen_m.get('empty_prediction_rate',0)*100:.1f}%")
                print(f"         rep={gen_m.get('repetition_rate',0)*100:.1f}% "
                      f"dup={gen_m.get('consecutive_duplicate_rate',0)*100:.1f}% "
                      f"badTrans={gen_m.get('invalid_transition_rate',0)*100:.1f}%")
                bucket_eos = gen_m.get('early_eos_by_bucket', {})
                if bucket_eos:
                    parts = " ".join(f"{b}={r*100:.0f}%" for b, r in sorted(bucket_eos.items()))
                    print(f"         earlyEOS/bucket: {parts}")
            print(f"  TF={tf_ratio:.3f}, AR={ar_ratio:.0%}, LR={lr:.6f}")

            # Verify BERT gradients on first AR step (right after backward, before zero_grad)
            if epoch == 0:
                print(f"  [Diag] BERT gradient check moved to _train_step_autoregressive (after backward)")

            payload = self._checkpoint_payload(epoch + 1, train_m, val_m, gen_m)

            # Always save latest-epoch snapshot for debugging / warmstart continuity
            latest_path = self.checkpoint_dir / "latest_model.pth"
            torch.save(payload, latest_path)
            print(f"  [SNAPSHOT] Saved latest epoch: {latest_path}")

            # ── Early stopping on composite metric ──
            current_composite = _compute_composite_metric(gen_m) if gen_m else None
            is_improvement = False
            if current_composite is not None and current_composite > best_composite:
                best_composite = current_composite
                best_epoch = epoch + 1
                best_payload = payload
                epochs_without_improvement = 0
                is_improvement = True
                # Save best_model.pth only on improvement
                best_path = self.checkpoint_dir / "best_model.pth"
                torch.save(payload, best_path)
                print(f"  [BEST] New best composite={best_composite:.4f} at epoch {best_epoch} "
                      f"(SetF1={gen_m.get('ar_set_f1',0):.3f} LCS={gen_m.get('ar_lcs',0):.3f} "
                      f"earlyEOS={gen_m.get('early_eos_rate',0)*100:.1f}%) → saved {best_path}")
            else:
                epochs_without_improvement += 1
                if gen_m:
                    print(f"  [EARLY STOP] No improvement for {epochs_without_improvement}/{patience} epochs "
                          f"(current composite={current_composite:.4f}, best={best_composite:.4f} at epoch {best_epoch})")

            # Save additional metric selection snapshots (observation-only)
            before_manifest = best_snapshot_state.get("manifest", {})
            best_snapshot_state = save_metric_selection_snapshots(
                self.checkpoint_dir, payload, gen_m, epoch + 1, best_snapshot_state
            )
            after_manifest = best_snapshot_state.get("manifest", {})
            if after_manifest.get("selection_snapshots", {}).get("gen_set_f1") != before_manifest.get("selection_snapshots", {}).get("gen_set_f1"):
                print(f"  [SNAPSHOT] Saved best Gen SetF1: {self.checkpoint_dir / 'best_gen_set_f1_model.pth'}")
            if after_manifest.get("selection_snapshots", {}).get("gen_lcs") != before_manifest.get("selection_snapshots", {}).get("gen_lcs"):
                print(f"  [SNAPSHOT] Saved best Gen LCS: {self.checkpoint_dir / 'best_gen_lcs_model.pth'}")

            # Check early stopping
            if epochs_without_improvement >= patience:
                print(f"\n  [EARLY STOP] No improvement for {patience} epochs. Stopping at epoch {epoch+1}.")
                break

        # Final test evaluation — load best checkpoint by composite metric
        print("\n" + "=" * 80)
        best_path = self.checkpoint_dir / "best_model.pth"
        latest_path = self.checkpoint_dir / "latest_model.pth"
        if best_path.exists():
            eval_ckpt_path = best_path
            eval_label = f"best (composite={best_composite:.4f}, epoch {best_epoch})"
        else:
            eval_ckpt_path = latest_path if latest_path.exists() else best_path
            eval_label = "latest (no composite improvement recorded)"
        print(f"Training complete! Loading {eval_label} checkpoint for test evaluation...")
        eval_ckpt = torch.load(eval_ckpt_path,
                                map_location=self.device, weights_only=True)
        self.model.load_state_dict(eval_ckpt['model_state_dict'])
        self.task_classifier.load_state_dict(eval_ckpt['task_classifier_state_dict'])

        test_val = self.validate(loader=self.test_loader)
        test_gen = self.evaluate_generation(
            epoch='test',
            num_batches=self.final_generation_eval_batches,
            loader=self.test_loader,
        )
        print(f"\nTest Results:")
        print(f"  Loss={test_val['loss']:.4f} PPL={test_val['perplexity']:.1f}")
        print(f"  Top1={test_val['top1_acc']*100:.1f}% Top5={test_val['top5_acc']*100:.1f}%")
        print(f"  TF-SeqEM={test_val['tf_sequence_em']*100:.1f}% "
              f"avglen(ref)={test_val.get('mean_ref_length',0):.1f}")
        if test_gen:
            print(f"  AR-SeqEM={test_gen.get('ar_seq_em',0)*100:.1f}% "
                  f"AR-TokenAcc={test_gen.get('ar_token_acc',0)*100:.1f}%")
            print(f"  AR-LCS={test_gen.get('ar_lcs',0):.3f} "
                  f"AR-SetF1={test_gen.get('ar_set_f1',0):.3f}")
            print(f"  len(pred)={test_gen.get('mean_pred_length',0):.1f} "
                  f"len(ref)={test_gen.get('mean_ref_length',0):.1f} "
                  f"|lenErr|={test_gen.get('length_abs_error',0):.1f}")
            print(f"  earlyEOS={test_gen.get('early_eos_rate',0)*100:.1f}% "
                  f"empty={test_gen.get('empty_prediction_rate',0)*100:.1f}%")
            print(f"  rep={test_gen.get('repetition_rate',0)*100:.1f}% "
                  f"dup={test_gen.get('consecutive_duplicate_rate',0)*100:.1f}% "
                  f"badTrans={test_gen.get('invalid_transition_rate',0)*100:.1f}%")
            bucket_eos = test_gen.get('early_eos_by_bucket', {})
            if bucket_eos:
                parts = " ".join(f"{b}={r*100:.0f}%" for b, r in sorted(bucket_eos.items()))
                print(f"  earlyEOS/bucket: {parts}")

        self.history['metrics'] = history
        self.history['test'] = {**test_val, **test_gen}
        self.history['checkpoint_policy'] = best_snapshot_state.get("manifest", {
            "best_snapshot": "best_model.pth",
            "latest_snapshot": "latest_model.pth",
            "selection_snapshots": {},
        })
        self.history['early_stopping'] = {
            "best_composite": best_composite,
            "best_epoch": best_epoch,
            "stopped_epoch": len(history),
            "patience": patience,
            "composite_formula": "0.5*SetF1 + 0.3*LCS + 0.2*(1 - early_eos_rate)",
        }
        hist_path = self.checkpoint_dir / "training_history_v4_6.json"
        with open(hist_path, 'w', encoding='utf-8') as f:
            json.dump(self.history, f, indent=2, ensure_ascii=False)
        print(f"\nHistory saved: {hist_path}")
        manifest_path = self.checkpoint_dir / "checkpoint_selection_manifest_v4_6.json"
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(self.history['checkpoint_policy'], f, indent=2, ensure_ascii=False)
        print(f"Checkpoint selection manifest saved: {manifest_path}")

        return history


def main(argv=None):
    """Delegate direct module execution to the quality-gate launcher.

    V4.6 training should not bypass the quality-gate paths, MR registry
    controls, and metric contract exposed by scripts/train_v4_6_quality_gate.py.
    """
    from scripts.train_v4_6_quality_gate import main as quality_gate_main

    return quality_gate_main(argv)


if __name__ == "__main__":
    main()
