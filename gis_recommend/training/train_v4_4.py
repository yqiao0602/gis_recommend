# -*- coding: utf-8 -*-
"""
V4.4 Training: Length-Aware Warm-start from V4.2

Root cause of short-sequence bias in V4.2:
  1. Curriculum phases 1/2 train only on short sequences (≤8, ≤15)
  2. Length loss weight=0.1 too weak, applied to START token only
  3. No penalty for early END token prediction
  4. AR training min_length=4 too short

V4.4 fixes:
  - No curriculum (all data from epoch 1)
  - Length loss weight 0.1 → 0.5, with AR-generated length feedback
  - Early END penalty: extra loss when END predicted before 70% of target
  - Dynamic min_length: block END before 50% of target length in AR
  - Warm-start from V4.2 best checkpoint, lower LR

Usage:
    python -m gis_recommend.training.train_v4_4
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
    V4_1_TASK_CLS_LOSS_WEIGHT,
    V4_TRANSITION_LOSS_WEIGHT,
    L3_EMBEDDINGS_PATH,
    V4_2_BATCH_SIZE, V4_2_NUM_WORKERS, V4_2_AR_MAX_STEPS,
    V4_2_GEN_EVAL_BATCHES, V4_2_GRADIENT_ACCUM_STEPS,
    # V4.4 specific
    V4_4_TRANSFORMER_CHECKPOINT_DIR, V4_4_WARMSTART_PATH,
    V4_4_NUM_EPOCHS, V4_4_TF_PHASE_EPOCHS,
    V4_4_SS_TF_START, V4_4_SS_TF_END,
    V4_4_AR_RATIO_START, V4_4_AR_RATIO_END,
    V4_4_WARMUP_EPOCHS, V4_4_EARLY_STOPPING_PATIENCE,
    V4_4_OTHER_LR, V4_4_BERT_LR, V4_4_BATCH_SIZE,
    V4_4_LENGTH_LOSS_WEIGHT,
    V4_4_EARLY_END_PENALTY, V4_4_EARLY_END_THRESHOLD,
    V4_4_AR_DYNAMIC_MIN_RATIO,
)
from gis_recommend.models.transformer_model_v4 import TaskConditionedL3TransformerModelV4
from gis_recommend.models.task_text_processor import TaskVocabularyBuilder
from gis_recommend.training.train_v4_2 import (
    ScheduledSamplingTrainerV4_2,
    TaskConditionedL3DatasetV4,
    compute_token_freq_weights,
    load_or_create_splits,
    set_seed,
    PAD_INDEX, START_INDEX, END_INDEX,
)


def load_warmstart_checkpoint(model, checkpoint_path, device):
    """Load V4.2 best checkpoint weights into model."""
    if not Path(checkpoint_path).exists():
        print(f"  [WARN] Warm-start checkpoint not found: {checkpoint_path}")
        return None

    print(f"  Loading warm-start from {checkpoint_path} ...")
    ckpt = torch.load(checkpoint_path, map_location=device, weights_only=True)
    model.load_state_dict(ckpt['model_state_dict'])
    val_loss = ckpt.get('val_loss')
    print(f"  Model loaded (epoch {ckpt.get('epoch', '?')}, "
          f"val_loss={val_loss:.4f}" if val_loss else ")")
    return ckpt.get('task_classifier_state_dict')


class ScheduledSamplingTrainerV4_4(ScheduledSamplingTrainerV4_2):
    """V4.4: Length-aware warm-start training.

    Overrides from V4.2:
    - _build_train_loader: no curriculum, always uses all data
    - _train_step_ar: adds early END penalty + dynamic min_length + AR length loss
    """

    def __init__(self, *args,
                 early_end_penalty=V4_4_EARLY_END_PENALTY,
                 early_end_threshold=V4_4_EARLY_END_THRESHOLD,
                 ar_dynamic_min_ratio=V4_4_AR_DYNAMIC_MIN_RATIO,
                 **kwargs):
        super().__init__(*args, **kwargs)
        self.early_end_penalty = early_end_penalty
        self.early_end_threshold = early_end_threshold
        self.ar_dynamic_min_ratio = ar_dynamic_min_ratio

    # ---- Override: No curriculum ----
    def _build_train_loader(self, epoch):
        """Use ALL training data from epoch 1 — no curriculum filtering."""
        indices = list(range(len(self.train_dataset)))
        subset = Subset(self.train_dataset, indices)
        loader = DataLoader(subset, batch_size=self.batch_size, shuffle=True,
                            num_workers=self.num_workers, drop_last=True)
        return loader, len(indices)

    # ---- Override: AR step with length-aware improvements ----
    def _train_step_ar(self, batch, tf_ratio):
        """AR-SS step with: early END penalty, dynamic min_length, AR length loss."""
        target_ids = batch['target_ids'].to(self.device)
        task_type_ids = batch['task_type_id'].to(self.device)
        text_input_ids = batch['text_input_ids'].to(self.device)
        text_attention_mask = batch['text_attention_mask'].to(self.device)
        attention_mask = batch['attention_mask'].to(self.device)
        seq_lens = batch['seq_len']

        B, T = target_ids.shape
        ar_max_steps = min(T, V4_2_AR_MAX_STEPS)

        # Convert seq_lens to tensor for per-sample operations
        if isinstance(seq_lens, torch.Tensor):
            target_lengths = seq_lens.to(self.device)
        else:
            target_lengths = torch.tensor(seq_lens, dtype=torch.long, device=self.device)

        # Compute dynamic min_length per sample: 50% of target length, min 5
        dynamic_min_lengths = torch.clamp(
            (target_lengths.float() * self.ar_dynamic_min_ratio).long(), min=5
        )

        # [Fix D] Compute BERT memory WITH gradients
        memory_raw, memory_mask, text_pooled = self.model.text_encoder(
            text_input_ids, text_attention_mask
        )
        memory_proj = self.model.text_projection(memory_raw)
        memory = self.model.memory_positional_encoding(memory_proj)
        condition = self.model._fuse_condition(task_type_ids, text_pooled)

        # BERT anchor loss
        bert_condition_repr = self.model.contrastive_projector(
            self.model.condition_projection(text_pooled)
        )
        bert_task_loss = self._task_cls_loss(bert_condition_repr, task_type_ids)

        # Detach for AR loop
        memory_d = memory.detach()
        condition_d = condition.detach()
        memory_mask_d = memory_mask.detach() if memory_mask is not None else None

        # Build decoder input token-by-token
        decoder_input = torch.full((B, 1), START_INDEX, dtype=torch.long, device=self.device)
        total_loss = torch.tensor(0.0, device=self.device)
        early_end_loss = torch.tensor(0.0, device=self.device)
        valid_steps = 0
        early_end_count = 0

        # Track generated lengths
        gen_lengths = torch.ones(B, dtype=torch.long, device=self.device)
        # Track which samples have finished (generated END)
        finished = torch.zeros(B, dtype=torch.bool, device=self.device)

        with autocast('cuda', enabled=self.use_amp):
            for t in range(ar_max_steps):
                step_mask = attention_mask[:, t]
                if step_mask.sum() == 0:
                    break

                # Embed decoder input
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

                # V4.4: Dynamic min_length — block END for samples that haven't
                # reached their per-sample minimum
                for b in range(B):
                    if t < dynamic_min_lengths[b].item():
                        next_logits[b, END_INDEX] = float('-inf')

                # CE loss
                loss_t = self.criterion(next_logits, target_ids[:, t])
                total_loss = total_loss + loss_t
                valid_steps += 1

                # V4.4: Early END penalty
                # If model predicts END before early_end_threshold of target length
                with torch.no_grad():
                    predicted_tokens = next_logits.argmax(dim=-1)
                for b in range(B):
                    if (predicted_tokens[b].item() == END_INDEX
                            and t < target_lengths[b].item() * self.early_end_threshold
                            and not finished[b]):
                        # Add weighted CE loss as penalty for this early END
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
                    # Track finished samples
                    for b in range(B):
                        if next_token[b, 0].item() == END_INDEX:
                            finished[b] = True

                decoder_input = torch.cat([decoder_input, next_token], dim=1)
                gen_lengths += step_mask.long() * (~finished).long()

                if decoder_input.size(1) > self.model.max_seq_length:
                    break

            avg_loss = total_loss / max(valid_steps, 1)
            avg_early_end = early_end_loss / max(early_end_count, 1) if early_end_count > 0 else torch.tensor(0.0, device=self.device)

            # Compute aux losses from clean forward pass
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

            # V4.4: Enhanced length loss — on ground truth + AR-generated lengths
            length_loss_gt = self._length_loss(aux['length_pred'], seq_lens)
            # Additional: penalize difference between generated and target lengths
            log_gen = torch.log(gen_lengths.float().clamp(min=1))
            log_target = torch.log(target_lengths.float().clamp(min=1))
            length_loss_ar = F.mse_loss(log_gen, log_target)
            length_loss = length_loss_gt + length_loss_ar

            task_loss = self._task_cls_loss(aux['contrastive_repr'], task_type_ids)

            # Total loss composition
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

        del decoder_input, total_loss, avg_loss, backward_loss
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        return {
            'total_loss': total_ar_loss.item(),
            'main_loss': (total_ar_loss - avg_early_end).item(),
            'length_loss': length_loss.item(),
            'early_end_penalty': avg_early_end.item(),
            'early_end_count': early_end_count,
        }


def main():
    print("=" * 80)
    print("V4.4 Training: Length-Aware Warm-start from V4.2")
    print("  Fixes: no curriculum, length loss 0.5, early END penalty, dynamic min_length")
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
    val_loader = DataLoader(val_dataset, batch_size=V4_4_BATCH_SIZE, shuffle=False,
                            num_workers=V4_2_NUM_WORKERS)
    test_loader = DataLoader(test_dataset, batch_size=V4_4_BATCH_SIZE, shuffle=False,
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
    task_cls_state = load_warmstart_checkpoint(model, V4_4_WARMSTART_PATH, DEVICE)
    warm_started = task_cls_state is not None

    # [8] Create V4.4 trainer
    print("\n[8] Creating V4.4 trainer...")
    trainer = ScheduledSamplingTrainerV4_4(
        model=model,
        train_dataset=train_dataset,
        val_loader=val_loader,
        test_loader=test_loader,
        num_task_types=num_task_types,
        token_freq_weights=freq_weights,
        checkpoint_dir=V4_4_TRANSFORMER_CHECKPOINT_DIR,
        use_amp=(DEVICE.type == 'cuda'),
        # V4.4 schedule
        tf_phase_epochs=V4_4_TF_PHASE_EPOCHS,
        ss_tf_start=V4_4_SS_TF_START,
        ss_tf_end=V4_4_SS_TF_END,
        ar_ratio_start=V4_4_AR_RATIO_START,
        ar_ratio_end=V4_4_AR_RATIO_END,
        num_epochs=V4_4_NUM_EPOCHS,
        warmup_epochs=V4_4_WARMUP_EPOCHS,
        early_stopping_patience=V4_4_EARLY_STOPPING_PATIENCE,
        bert_lr=V4_4_BERT_LR,
        other_lr=V4_4_OTHER_LR,
        batch_size=V4_4_BATCH_SIZE,
        # V4.4 length-aware
        length_loss_weight=V4_4_LENGTH_LOSS_WEIGHT,
        early_end_penalty=V4_4_EARLY_END_PENALTY,
        early_end_threshold=V4_4_EARLY_END_THRESHOLD,
        ar_dynamic_min_ratio=V4_4_AR_DYNAMIC_MIN_RATIO,
        # No curriculum — pass impossible values so curriculum never activates
        curriculum_p1_end=-1,
        curriculum_p1_max=999,
        curriculum_p2_end=-1,
        curriculum_p2_max=999,
    )

    # Load task classifier weights
    if task_cls_state is not None:
        trainer.task_classifier.load_state_dict(task_cls_state)
        print("  Task classifier weights loaded from V4.2")

    # [9] Schedule preview
    print("\n[9] V4.4 Schedule Preview:")
    print(f"  Warm-start: {'YES' if warm_started else 'NO'}")
    print(f"  Length loss weight: {V4_4_LENGTH_LOSS_WEIGHT}")
    print(f"  Early END penalty: {V4_4_EARLY_END_PENALTY} (threshold={V4_4_EARLY_END_THRESHOLD})")
    print(f"  Dynamic min_length ratio: {V4_4_AR_DYNAMIC_MIN_RATIO}")
    for ep in [0, 2, 5, 10, 15, 20, 24]:
        if ep >= V4_4_NUM_EPOCHS:
            break
        tf = trainer.get_tf_ratio(ep)
        ar = trainer.get_ar_ratio(ep)
        print(f"  Epoch {ep+1:3d}: tf_ratio={tf:.3f}, ar_ratio={ar:.0%}")

    # [10] Train
    print("\n[10] Starting V4.4 training...")
    trainer.train()
    print("\nV4.4 training complete!")


if __name__ == "__main__":
    main()
