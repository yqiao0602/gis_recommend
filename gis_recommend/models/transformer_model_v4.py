# -*- coding: utf-8 -*-
"""
V4 任务条件化 Transformer 模型

改进点（相对V3）：
1. FiLM 条件注入（替换简单加法注入）—— 每层 Decoder 后都注入条件
2. 解冻 BERT 顶层 2 层 —— 适应 GIS 领域语义
3. 新辅助任务头：序列长度预测（回归）+ 对比学习（InfoNCE）
4. 保持与 V3 checkpoint 的 warm-start 兼容性
"""

import math
import torch
import torch.nn as nn
import torch.nn.functional as F
from transformers import BertModel

from gis_recommend.config.transformer_config import (
    TOTAL_VOCAB_SIZE,
    V4_D_MODEL, V4_N_HEADS, V4_N_LAYERS, V4_D_FF,
    V4_DROPOUT, V4_MAX_SEQ_LENGTH, V4_MAX_MEMORY_TOKENS,
    V4_BERT_UNFREEZE_LAYERS, V4_CONTRASTIVE_TEMPERATURE,
)


class PositionalEncoding(nn.Module):
    """Sinusoidal positional encoding"""

    def __init__(self, d_model: int, max_len: int = 5000, dropout: float = 0.1):
        super().__init__()
        self.dropout = nn.Dropout(p=dropout)
        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(
            torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model)
        )
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        pe = pe.unsqueeze(0)  # [1, max_len, d_model]
        self.register_buffer("pe", pe)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        x = x + self.pe[:, : x.size(1)]
        return self.dropout(x)


# =========================================================================
# BERT Text Encoder（支持部分解冻）
# =========================================================================
class BERTTextEncoderV4(nn.Module):
    """BERT encoder with optional top-layer unfreezing and adaptive sampling."""

    def __init__(
        self,
        unfreeze_layers: int = 2,
        max_memory_tokens: int = 16,
        freeze_bert: bool = False,
    ):
        super().__init__()
        self.bert = BertModel.from_pretrained("bert-base-uncased")
        self.max_memory_tokens = max_memory_tokens
        self.bert_hidden = self.bert.config.hidden_size  # 768

        # Freeze / unfreeze strategy
        if freeze_bert:
            for p in self.bert.parameters():
                p.requires_grad = False
        else:
            # Freeze all, then unfreeze top N layers + pooler
            for p in self.bert.parameters():
                p.requires_grad = False
            total_layers = self.bert.config.num_hidden_layers  # 12
            for i in range(total_layers - unfreeze_layers, total_layers):
                for p in self.bert.encoder.layer[i].parameters():
                    p.requires_grad = True
            if hasattr(self.bert, "pooler") and self.bert.pooler is not None:
                for p in self.bert.pooler.parameters():
                    p.requires_grad = True

    def _adaptive_sample(
        self, hidden: torch.Tensor, mask: torch.Tensor
    ) -> tuple:
        """Sample max_memory_tokens from BERT output."""
        B, S, D = hidden.shape
        M = self.max_memory_tokens
        sampled = torch.zeros(B, M, D, device=hidden.device)
        sampled_mask = torch.zeros(B, M, dtype=torch.bool, device=hidden.device)

        for b in range(B):
            valid_len = mask[b].sum().item()
            if valid_len == 0:
                continue
            if valid_len <= M:
                sampled[b, :valid_len] = hidden[b, :valid_len]
                sampled_mask[b, :valid_len] = True
            else:
                indices = torch.linspace(0, valid_len - 1, M, device=hidden.device).long()
                indices[0] = 0
                indices[-1] = valid_len - 1
                sampled[b] = hidden[b, indices]
                sampled_mask[b] = True

        return sampled, sampled_mask

    def forward(self, input_ids, attention_mask):
        """
        Returns:
            memory: [B, M, 768]
            memory_mask: [B, M] bool (True=valid)
            pooled: [B, 768]
        """
        outputs = self.bert(input_ids=input_ids, attention_mask=attention_mask)
        hidden = outputs.last_hidden_state  # [B, S, 768]
        pooled = outputs.pooler_output       # [B, 768]
        memory, memory_mask = self._adaptive_sample(hidden, attention_mask.bool())
        return memory, memory_mask, pooled


# =========================================================================
# FiLM Conditioned Decoder Layer
# =========================================================================
class FiLMConditionedDecoderLayer(nn.Module):
    """Transformer Decoder Layer + FiLM condition injection after each layer."""

    def __init__(self, d_model: int, n_heads: int, d_ff: int, dropout: float):
        super().__init__()
        self.decoder_layer = nn.TransformerDecoderLayer(
            d_model=d_model,
            nhead=n_heads,
            dim_feedforward=d_ff,
            dropout=dropout,
            batch_first=True,
            norm_first=True,
        )
        # FiLM: gamma * x + beta
        self.film_gamma = nn.Linear(d_model, d_model)
        self.film_beta = nn.Linear(d_model, d_model)
        # Initialize gamma≈identity, beta≈0 for stable start
        nn.init.zeros_(self.film_gamma.weight)
        self.film_gamma.weight.data.fill_diagonal_(1.0)
        nn.init.zeros_(self.film_gamma.bias)
        nn.init.zeros_(self.film_beta.weight)
        nn.init.zeros_(self.film_beta.bias)

    def forward(self, tgt, memory, condition, tgt_mask=None,
                tgt_key_padding_mask=None, memory_key_padding_mask=None):
        """
        Args:
            tgt: [B, T, D]
            memory: [B, M, D]
            condition: [B, D]
        """
        x = self.decoder_layer(
            tgt, memory,
            tgt_mask=tgt_mask,
            tgt_key_padding_mask=tgt_key_padding_mask,
            memory_key_padding_mask=memory_key_padding_mask,
        )
        # FiLM modulation
        gamma = self.film_gamma(condition).unsqueeze(1)  # [B, 1, D]
        beta = self.film_beta(condition).unsqueeze(1)    # [B, 1, D]
        x = gamma * x + beta
        return x


# =========================================================================
# V4 Main Model
# =========================================================================
class TaskConditionedL3TransformerModelV4(nn.Module):
    """
    V4 Task-Conditioned Transformer for L3 sequence generation.

    Key improvements over V3:
    - FiLM conditioning at every decoder layer (not just input)
    - Partial BERT unfreezing for domain adaptation
    - Length prediction head (regression)
    - Contrastive learning head (InfoNCE)
    """

    def __init__(
        self,
        vocab_size: int = TOTAL_VOCAB_SIZE,
        num_task_types: int = 72,
        d_model: int = V4_D_MODEL,
        n_heads: int = V4_N_HEADS,
        n_layers: int = V4_N_LAYERS,
        dim_feedforward: int = V4_D_FF,
        dropout: float = V4_DROPOUT,
        max_seq_length: int = V4_MAX_SEQ_LENGTH,
        max_memory_tokens: int = V4_MAX_MEMORY_TOKENS,
        use_l3_embeddings: bool = False,
        l3_embeddings_path: str = None,
        freeze_bert: bool = False,
        bert_unfreeze_layers: int = V4_BERT_UNFREEZE_LAYERS,
        contrastive_temperature: float = V4_CONTRASTIVE_TEMPERATURE,
    ):
        super().__init__()
        self.vocab_size = vocab_size
        self.d_model = d_model
        self.n_layers = n_layers
        self.max_seq_length = max_seq_length
        self.contrastive_temperature = contrastive_temperature

        # ---- BERT Text Encoder ----
        self.text_encoder = BERTTextEncoderV4(
            unfreeze_layers=bert_unfreeze_layers,
            max_memory_tokens=max_memory_tokens,
            freeze_bert=freeze_bert,
        )
        bert_hidden = self.text_encoder.bert_hidden  # 768

        # ---- Projections ----
        self.text_projection = nn.Linear(bert_hidden, d_model)
        self.condition_projection = nn.Linear(bert_hidden, d_model)

        # ---- Task Type Embedding ----
        self.task_type_embedding = nn.Embedding(num_task_types, d_model)

        # ---- Condition Fusion (text_cls + task_type → condition) ----
        self.condition_fusion = nn.Sequential(
            nn.Linear(2 * d_model, d_model),
            nn.LayerNorm(d_model),
            nn.GELU(),
            nn.Dropout(dropout),
        )

        # ---- FiLM input injection (for token embeddings) ----
        self.input_film_gamma = nn.Linear(d_model, d_model)
        self.input_film_beta = nn.Linear(d_model, d_model)
        nn.init.zeros_(self.input_film_gamma.weight)
        self.input_film_gamma.weight.data.fill_diagonal_(1.0)
        nn.init.zeros_(self.input_film_gamma.bias)
        nn.init.zeros_(self.input_film_beta.weight)
        nn.init.zeros_(self.input_film_beta.bias)

        # ---- Token Embedding ----
        self.token_embedding = nn.Embedding(vocab_size, d_model)

        # ---- Positional Encoding ----
        self.positional_encoding = PositionalEncoding(d_model, max_seq_length, dropout)
        self.memory_positional_encoding = PositionalEncoding(
            d_model, max_memory_tokens + 32, dropout
        )

        # ---- FiLM Conditioned Decoder Layers ----
        self.decoder_layers = nn.ModuleList([
            FiLMConditionedDecoderLayer(d_model, n_heads, dim_feedforward, dropout)
            for _ in range(n_layers)
        ])
        self.decoder_norm = nn.LayerNorm(d_model)

        # ---- Output Projection (weight-tied with token embedding) ----
        self.output_projection = nn.Linear(d_model, vocab_size, bias=False)
        self.output_projection.weight = self.token_embedding.weight

        # ---- Auxiliary Head: Length Prediction (regression) ----
        self.length_predictor = nn.Sequential(
            nn.Linear(d_model, d_model // 2),
            nn.ReLU(),
            nn.Linear(d_model // 2, 1),
        )

        # ---- Auxiliary Head: Contrastive Projection ----
        self.contrastive_projector = nn.Sequential(
            nn.Linear(d_model, d_model),
            nn.ReLU(),
            nn.Linear(d_model, d_model // 2),
        )

        # ---- Load pretrained L3 embeddings ----
        if use_l3_embeddings and l3_embeddings_path:
            self._load_l3_embeddings(l3_embeddings_path)

    def _load_l3_embeddings(self, path: str):
        """Load pretrained L3 embeddings into token_embedding."""
        try:
            embeddings = torch.load(path, map_location="cpu")
            if isinstance(embeddings, dict):
                embeddings = embeddings.get("embeddings", embeddings.get("weight"))
            if embeddings is not None and embeddings.shape[1] == self.d_model:
                n = min(embeddings.shape[0], self.vocab_size)
                self.token_embedding.weight.data[:n] = embeddings[:n]
                print(f"  [V4] Loaded L3 embeddings: {n} tokens from {path}")
        except Exception as e:
            print(f"  [V4] Warning: Could not load L3 embeddings: {e}")

    def _generate_causal_mask(self, sz: int, device: torch.device) -> torch.Tensor:
        """Upper-triangular causal mask (True = masked)."""
        return torch.triu(torch.ones(sz, sz, device=device, dtype=torch.bool), diagonal=1)

    def _fuse_condition(self, task_type_ids, text_pooled):
        """Fuse task type embedding + BERT CLS → condition vector [B, D]."""
        task_emb = self.task_type_embedding(task_type_ids)       # [B, D]
        text_cond = self.condition_projection(text_pooled)       # [B, D]
        fused = self.condition_fusion(
            torch.cat([text_cond, task_emb], dim=-1)
        )  # [B, D]
        return fused

    def forward(
        self,
        input_ids: torch.Tensor,
        task_type_ids: torch.Tensor,
        text_input_ids: torch.Tensor,
        text_attention_mask: torch.Tensor,
        attention_mask: torch.Tensor = None,
        return_aux: bool = False,
    ):
        """
        Args:
            input_ids: [B, T] L3 token IDs
            task_type_ids: [B] task type IDs
            text_input_ids: [B, S_text] BERT input IDs
            text_attention_mask: [B, S_text] BERT attention mask
            attention_mask: [B, T] (1=valid, 0=pad) or None
            return_aux: if True, also return length_pred and contrastive_repr

        Returns:
            logits: [B, T, vocab_size]
            aux_dict: dict with 'length_pred' and 'contrastive_repr'
                      (only if return_aux=True)
        """
        B, T = input_ids.shape
        device = input_ids.device

        # ---- BERT encoding ----
        memory_raw, memory_mask, text_pooled = self.text_encoder(
            text_input_ids, text_attention_mask
        )
        memory = self.text_projection(memory_raw)  # [B, M, D]
        memory = self.memory_positional_encoding(memory)

        # ---- Condition fusion ----
        condition = self._fuse_condition(task_type_ids, text_pooled)  # [B, D]

        # ---- Token embedding + FiLM input injection ----
        tok_emb = self.token_embedding(input_ids)  # [B, T, D]
        gamma = self.input_film_gamma(condition).unsqueeze(1)  # [B, 1, D]
        beta = self.input_film_beta(condition).unsqueeze(1)
        tok_emb = gamma * tok_emb + beta
        tok_emb = self.positional_encoding(tok_emb)

        # ---- Masks ----
        causal_mask = self._generate_causal_mask(T, device)
        pad_mask = (attention_mask == 0) if attention_mask is not None else None
        memory_pad_mask = ~memory_mask if memory_mask is not None else None

        # ---- Decoder layers with FiLM ----
        x = tok_emb
        for layer in self.decoder_layers:
            x = layer(
                x, memory, condition,
                tgt_mask=causal_mask,
                tgt_key_padding_mask=pad_mask,
                memory_key_padding_mask=memory_pad_mask,
            )
        x = self.decoder_norm(x)

        # ---- Output logits ----
        logits = self.output_projection(x)  # [B, T, vocab_size]

        if not return_aux:
            return logits

        # ---- Auxiliary: Length prediction from START token repr ----
        start_repr = x[:, 0, :]  # [B, D]
        length_pred = self.length_predictor(start_repr)  # [B, 1]

        # ---- Auxiliary: Contrastive representation ----
        if attention_mask is not None:
            mask_f = attention_mask.unsqueeze(-1).float()  # [B, T, 1]
            seq_repr = (x * mask_f).sum(1) / mask_f.sum(1).clamp(min=1)
        else:
            seq_repr = x.mean(dim=1)
        contrastive_repr = self.contrastive_projector(seq_repr)  # [B, D//2]

        return logits, {"length_pred": length_pred, "contrastive_repr": contrastive_repr}

    def get_parameter_groups(self, bert_lr: float, other_lr: float):
        """Return parameter groups with different learning rates."""
        bert_params = []
        other_params = []
        for name, param in self.named_parameters():
            if not param.requires_grad:
                continue
            if name.startswith("text_encoder.bert."):
                bert_params.append(param)
            else:
                other_params.append(param)
        return [
            {"params": bert_params, "lr": bert_lr},
            {"params": other_params, "lr": other_lr},
        ]

    def count_parameters(self):
        """Count trainable and total parameters."""
        total = sum(p.numel() for p in self.parameters())
        trainable = sum(p.numel() for p in self.parameters() if p.requires_grad)
        bert_trainable = sum(
            p.numel() for n, p in self.named_parameters()
            if p.requires_grad and n.startswith("text_encoder.bert.")
        )
        return {
            "total": total,
            "trainable": trainable,
            "bert_trainable": bert_trainable,
            "other_trainable": trainable - bert_trainable,
        }
