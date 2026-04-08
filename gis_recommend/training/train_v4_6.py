# -*- coding: utf-8 -*-
"""
V4.6 Training: Gradient Fix + AR-based Model Selection

修复代码评审发现的 3 个结构性 bug:
  Bug 1: AR 主损失的梯度被 detach 切断 → 移除 memory/condition detach
  Bug 2: aux loss 在 no_grad 里计算 → 移除 no_grad wrapper
  Bug 3: best model 按 TF val_loss 选择 → 改为按 AR-TokenAcc 选择

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
from gis_recommend.training.train_v4_2 import (
    TaskConditionedL3DatasetV4,
    compute_token_freq_weights,
    load_or_create_splits,
    set_seed,
    PAD_INDEX, START_INDEX, END_INDEX,
)
from gis_recommend.training.train_v4_4 import load_warmstart_checkpoint
from gis_recommend.training.train_v4_5 import (
    ScheduledSamplingTrainerV4_5,
    build_task_type_sampler,
)


class ScheduledSamplingTrainerV4_6(ScheduledSamplingTrainerV4_5):
    """V4.6: Gradient fix + AR-based model selection.

    Bug fixes over V4.5:
    - _train_step_autoregressive: 移除 memory/condition detach，AR 梯度可回传 BERT
    - _train_step_autoregressive: 移除 aux loss 的 no_grad，length/task loss 有实际梯度
    - train(): best model 按 AR-TokenAcc 选择，不再按 TF val_loss
    """

    def _train_step_autoregressive(self, batch, tf_ratio):
        """AR-SS step with full gradient flow (no detach, no no_grad for aux)."""
        target_ids = batch['target_ids'].to(self.device)
        task_type_ids = batch['task_type_id'].to(self.device)
        text_input_ids = batch['text_input_ids'].to(self.device)
        text_attention_mask = batch['text_attention_mask'].to(self.device)
        attention_mask = batch['attention_mask'].to(self.device)
        seq_lens = batch['seq_len']

        B, T = target_ids.shape
        ar_max_steps = min(T, V4_6_AR_MAX_STEPS)

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

                # Dynamic min_length — block END
                for b in range(B):
                    if t < dynamic_min_lengths[b].item():
                        next_logits[b, END_INDEX] = float('-inf')

                # CE loss
                loss_t = self.criterion(next_logits, target_ids[:, t])
                total_loss = total_loss + loss_t
                valid_steps += 1

                # Early END penalty
                with torch.no_grad():
                    predicted_tokens = next_logits.argmax(dim=-1)
                for b in range(B):
                    if (predicted_tokens[b].item() == END_INDEX
                            and t < target_lengths[b].item() * self.early_end_threshold
                            and not finished[b]):
                        end_ce = F.cross_entropy(
                            next_logits[b:b+1], target_ids[b:b+1, t],
                            ignore_index=PAD_INDEX
                        )
                        early_end_loss = early_end_loss + self.early_end_penalty * end_ce
                        early_end_count += 1

                # Nucleus sampling for next token
                if random.random() < tf_ratio:
                    next_token = target_ids[:, t].unsqueeze(1)
                else:
                    with torch.no_grad():
                        next_token = self._nucleus_sample(next_logits).unsqueeze(1)
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

            # Task loss — 现在有梯度！
            task_loss = self._task_cls_loss(aux['contrastive_repr'], task_type_ids)

            # Total loss
            total_ar_loss = (avg_loss
                             + self.task_cls_loss_weight * bert_task_loss
                             + self.length_loss_weight * length_loss
                             + self.task_cls_loss_weight * task_loss
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
        }

    # ═══ Bug 3 Fix: Override train() to use AR metrics for best model selection ═══
    def train(self):
        """Training loop with AR-based model selection."""
        import json

        history = []
        best_ar_token_acc = -1.0  # 首轮无条件保存
        epochs_no_improve = 0
        prev_phase = -1

        print(f"\n{'='*80}")
        print(f"V4.6 Training: Gradient Fix + AR-based Model Selection")
        print(f"{'='*80}")
        print(f"  Device: {self.device}, AMP: {self.use_amp}")
        print(f"  Batch: {self.batch_size} x {self.gradient_accum_steps} accum = "
              f"{self.batch_size * self.gradient_accum_steps} effective")
        print(f"  LR: BERT={self.optimizer.param_groups[0]['lr']:.1e}, "
              f"Other={self.optimizer.param_groups[-1]['lr']:.1e}")
        print(f"  AR max steps: {V4_6_AR_MAX_STEPS}")
        print(f"  Gen eval batches: {self.generation_eval_batches}")
        print(f"  Best model selection: AR-TokenAcc (not TF val_loss)")
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
                print(f"  [Curriculum] Phase {prev_phase} -> {curr_phase}, resetting patience")
                epochs_no_improve = 0
            prev_phase = curr_phase

            # Reset patience when AR-SS starts
            if epoch == self.tf_phase_epochs:
                print(f"  [AR-SS] Starting autoregressive scheduled sampling, resetting patience")
                epochs_no_improve = 0

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
                  f"tcls={train_m.get('task_cls_loss', 0):.3f})")
            print(f"  Val:   Loss={val_m['loss']:.4f} | PPL={val_m['perplexity']:.1f} | "
                  f"Top1={val_m['top1_acc']*100:.1f}% Top5={val_m['top5_acc']*100:.1f}% "
                  f"TF-SeqEM={val_m['tf_sequence_em']*100:.1f}%")
            print(f"  Gen:   AR-SeqEM={gen_m.get('ar_seq_em',0)*100:.1f}% "
                  f"AR-TokenAcc={gen_m.get('ar_token_acc',0)*100:.1f}%")
            print(f"  TF={tf_ratio:.3f}, AR={ar_ratio:.0%}, LR={lr:.6f}")

            # Verify BERT gradients on first AR step (right after backward, before zero_grad)
            if epoch == 0:
                print(f"  [Diag] BERT gradient check moved to _train_step_autoregressive (after backward)")

            # ═══ Bug 3 Fix: 按 AR-TokenAcc 选 best model ═══
            ar_acc = gen_m.get('ar_token_acc', 0)
            if ar_acc > best_ar_token_acc:
                best_ar_token_acc = ar_acc
                epochs_no_improve = 0
                ckpt_path = self.checkpoint_dir / "best_model.pth"
                torch.save({
                    'model_state_dict': self.model.state_dict(),
                    'task_classifier_state_dict': self.task_classifier.state_dict(),
                    'epoch': epoch + 1,
                    'val_loss': val_m['loss'],
                    'ar_token_acc': ar_acc,
                    'ar_seq_em': gen_m.get('ar_seq_em', 0),
                    'model_config': {
                        'max_memory_tokens': V4_MAX_MEMORY_TOKENS,
                        'd_model': V4_D_MODEL,
                        'n_heads': V4_N_HEADS,
                        'n_layers': V4_N_LAYERS,
                    },
                }, ckpt_path)
                print(f"  [BEST] Saved: {ckpt_path} (ar_token_acc={ar_acc*100:.1f}%)")
            else:
                epochs_no_improve += 1
                print(f"  No improvement for {epochs_no_improve} epoch(s)")

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
        hist_path = self.checkpoint_dir / "training_history_v4_6.json"
        with open(hist_path, 'w', encoding='utf-8') as f:
            json.dump(self.history, f, indent=2, ensure_ascii=False)
        print(f"\nHistory saved: {hist_path}")

        return history


def main():
    print("=" * 80)
    print("V4.6 Training: Gradient Fix + AR-based Model Selection")
    print("  Fixes: no detach, no no_grad for aux, best model by AR-TokenAcc")
    print("  Inherits: V4.5 balanced sampling + strong task signal")
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

    # [3] Split dataset
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
    val_loader = DataLoader(val_dataset, batch_size=V4_6_BATCH_SIZE, shuffle=False,
                            num_workers=V4_2_NUM_WORKERS)
    test_loader = DataLoader(test_dataset, batch_size=V4_6_BATCH_SIZE, shuffle=False,
                             num_workers=V4_2_NUM_WORKERS)

    # [6] Create model
    print("\n[6] Creating model...")
    model = TaskConditionedL3TransformerModelV4(
        vocab_size=TOTAL_VOCAB_SIZE,
        num_task_types=num_task_types,
        d_model=V4_D_MODEL, n_heads=V4_N_HEADS, n_layers=V4_N_LAYERS,
        dim_feedforward=V4_D_FF, dropout=V4_DROPOUT,
        max_seq_length=V4_MAX_SEQ_LENGTH,
        max_memory_tokens=V4_MAX_MEMORY_TOKENS,
        use_l3_embeddings=True, l3_embeddings_path=str(L3_EMBEDDINGS_PATH),
        freeze_bert=False, bert_unfreeze_layers=V4_BERT_UNFREEZE_LAYERS,
    )
    counts = model.count_parameters()
    print(f"  Params: {counts['trainable']/1e6:.1f}M trainable, {counts['total']/1e6:.1f}M total")

    # [7] Warm-start from V4.3
    print("\n[7] Loading warm-start checkpoint...")
    task_cls_state = load_warmstart_checkpoint(model, V4_6_WARMSTART_PATH, DEVICE)

    # [8] Create V4.6 trainer
    print("\n[8] Creating V4.6 trainer...")
    trainer = ScheduledSamplingTrainerV4_6(
        model=model,
        train_dataset=train_dataset,
        val_loader=val_loader,
        test_loader=test_loader,
        num_task_types=num_task_types,
        token_freq_weights=freq_weights,
        checkpoint_dir=V4_6_TRANSFORMER_CHECKPOINT_DIR,
        use_amp=(DEVICE.type == 'cuda'),
        # Schedule
        tf_phase_epochs=V4_6_TF_PHASE_EPOCHS,
        ss_tf_start=V4_6_SS_TF_START,
        ss_tf_end=V4_6_SS_TF_END,
        ar_ratio_start=V4_6_AR_RATIO_START,
        ar_ratio_end=V4_6_AR_RATIO_END,
        num_epochs=V4_6_NUM_EPOCHS,
        warmup_epochs=V4_6_WARMUP_EPOCHS,
        early_stopping_patience=V4_6_EARLY_STOPPING_PATIENCE,
        bert_lr=V4_6_BERT_LR,
        other_lr=V4_6_OTHER_LR,
        batch_size=V4_6_BATCH_SIZE,
        gradient_accum_steps=V4_6_GRADIENT_ACCUM_STEPS,
        generation_eval_batches=8,  # 增大：best model 按 AR 指标选，需要更稳定的评估
        # Length-aware
        length_loss_weight=V4_6_LENGTH_LOSS_WEIGHT,
        early_end_penalty=V4_6_EARLY_END_PENALTY,
        early_end_threshold=V4_6_EARLY_END_THRESHOLD,
        ar_dynamic_min_ratio=V4_6_AR_DYNAMIC_MIN_RATIO,
        # No curriculum
        curriculum_p1_end=-1, curriculum_p1_max=999,
        curriculum_p2_end=-1, curriculum_p2_max=999,
        # V4.5: stronger task signal + balanced sampling
        task_cls_loss_weight=V4_6_TASK_CLS_LOSS_WEIGHT,
    )

    if task_cls_state is not None:
        trainer.task_classifier.load_state_dict(task_cls_state)
        print("  Task classifier weights loaded from warm-start")

    # [9] Train
    print("\n[9] Starting V4.6 training...")
    trainer.train()
    print("\nV4.6 training complete!")


if __name__ == "__main__":
    main()
