# -*- coding: utf-8 -*-
"""
L3 Set Predictor V3 — Rich Cross-Attention + Token-Token Self-Attention

V3 改进（相对 V2）:
  1. Cross-Attention 的 K/V 使用 BERT 完整序列（而非单个 [CLS]）
     → 每个 token query 可以从任务描述的不同词语中提取相关信息
  2. Task type 通过 FiLM 条件化注入 K/V（而非简单 concat+fusion）
  3. Token-Token Self-Attention 让 77 个 token 互相通信，学习共现模式
  4. num_self_attn_layers=0 时回退为无 self-attention 行为

架构:
    Task Text → BERT → full_seq [B,128,768] → Linear(768→256) → memory [B,128,256]
    Task Type → Embedding → FiLM(γ,β) 条件化 memory
    Token Queries [N,256] ── Cross-Attention(Q=queries, K=V=memory) ──→ [B,N,256]
    [可选] ── TransformerEncoder(Self-Attention × L 层) ──→ [B,N,256]
    Binary Head: Linear(256→1) → P(present)
    Count Head:  Linear(256→3) → P(count=1|2|3+)
"""

import torch
import torch.nn as nn
from typing import List, Dict, Optional
from transformers import BertModel


class L3SetPredictor(nn.Module):
    """预测 L3 token 集合 (binary) 及各 token 出现次数 (count)。"""

    def __init__(
        self,
        num_task_types: int = 72,
        d_condition: int = 256,
        d_hidden: int = 512,
        head_hidden_dim: Optional[int] = None,
        num_count_classes: int = 3,  # V2: {1, 2, 3+}，不含 0
        active_token_ids: Optional[List[int]] = None,
        bert_unfreeze_layers: int = 2,
        dropout: float = 0.2,
        num_attn_heads: int = 4,
        # V3 新增
        num_self_attn_layers: int = 0,        # 0 = 无 self-attention
        self_attn_dim_feedforward: int = 512,  # Self-Attention FFN 宽度
        use_rich_cross_attn: bool = False,     # True = full_seq+FiLM, False = CLS+fusion (V2兼容)
    ):
        super().__init__()
        self.num_task_types = num_task_types
        self.d_condition = d_condition
        self.d_hidden = d_hidden
        self.head_hidden_dim = head_hidden_dim or d_hidden
        self.num_count_classes = num_count_classes
        self.dropout_rate = dropout
        self.num_attn_heads = num_attn_heads
        self.use_rich_cross_attn = use_rich_cross_attn

        # Active token mapping: index in output → real token ID
        if active_token_ids is not None:
            self.register_buffer(
                'active_token_ids',
                torch.tensor(active_token_ids, dtype=torch.long),
            )
        else:
            self.active_token_ids = None
        self.num_active_tokens = len(active_token_ids) if active_token_ids else 0

        # ── BERT encoder (独立实例，不与 AR 模型共享) ──
        self.bert = BertModel.from_pretrained('bert-base-uncased')
        for param in self.bert.parameters():
            param.requires_grad = False
        if bert_unfreeze_layers > 0:
            for layer in self.bert.encoder.layer[-bert_unfreeze_layers:]:
                for param in layer.parameters():
                    param.requires_grad = True
            for param in self.bert.pooler.parameters():
                param.requires_grad = True

        if use_rich_cross_attn:
            # V3 Rich: 投影 BERT 完整序列 + FiLM 条件化
            self.text_seq_proj = nn.Linear(768, d_condition)
            self.film_gamma = nn.Linear(d_condition, d_condition)
            self.film_beta = nn.Linear(d_condition, d_condition)
            self._init_rich_cross_attn_identity()
        else:
            # V2 兼容: CLS + fusion
            self.text_proj = nn.Linear(768, d_condition)
            self.fusion = nn.Sequential(
                nn.Linear(d_condition * 2, d_condition),
                nn.LayerNorm(d_condition),
                nn.GELU(),
                nn.Dropout(dropout),
            )

        # ── Task type embedding ──
        self.task_type_emb = nn.Embedding(num_task_types, d_condition)

        # ── Per-token cross-attention ──
        # 每个活跃 token 有独立的 query embedding
        self.token_queries = nn.Embedding(self.num_active_tokens, d_condition)
        self.cross_attn = nn.MultiheadAttention(
            embed_dim=d_condition,
            num_heads=num_attn_heads,
            dropout=dropout,
            batch_first=True,
        )
        self.attn_norm = nn.LayerNorm(d_condition)

        # ── V3: Token-token self-attention ──
        self.num_self_attn_layers = num_self_attn_layers
        self.self_attn_dim_feedforward = self_attn_dim_feedforward
        if num_self_attn_layers > 0:
            encoder_layer = nn.TransformerEncoderLayer(
                d_model=d_condition,
                nhead=num_attn_heads,
                dim_feedforward=self_attn_dim_feedforward,
                dropout=dropout,
                activation='gelu',
                batch_first=True,
                norm_first=True,  # Pre-LN for stable training
            )
            self.self_attn_block = nn.TransformerEncoder(
                encoder_layer,
                num_layers=num_self_attn_layers,
            )
        else:
            self.self_attn_block = None

        # ── Binary presence head: P(present) per token ──
        self.binary_head = nn.Sequential(
            nn.Linear(d_condition, self.head_hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(self.head_hidden_dim, 1),
        )

        # ── Count head: P(count=1|2|3+) per token (只在 present 时有意义) ──
        self.count_head = nn.Sequential(
            nn.Linear(d_condition, self.head_hidden_dim),
            nn.ReLU(),
            nn.Dropout(dropout),
            nn.Linear(self.head_hidden_dim, num_count_classes),
        )

    def _init_rich_cross_attn_identity(self):
        """Initialize FiLM close to identity for stabler early training."""
        nn.init.zeros_(self.film_gamma.weight)
        nn.init.ones_(self.film_gamma.bias)
        nn.init.zeros_(self.film_beta.weight)
        nn.init.zeros_(self.film_beta.bias)

    def forward(
        self,
        task_type_ids: torch.Tensor,
        text_input_ids: torch.Tensor,
        text_attention_mask: torch.Tensor,
    ) -> tuple:
        """
        Args:
            task_type_ids: [B] int
            text_input_ids: [B, seq_len] int
            text_attention_mask: [B, seq_len] int

        Returns:
            binary_logits: [B, N] — raw logits for present/absent
            count_logits:  [B, N, 3] — raw logits for count class {1, 2, 3+}
        """
        B = task_type_ids.size(0)

        # BERT 输出
        bert_out = self.bert(
            input_ids=text_input_ids,
            attention_mask=text_attention_mask,
        )

        if self.use_rich_cross_attn:
            # V3 Rich: 完整序列 + FiLM 条件化
            bert_seq = bert_out.last_hidden_state  # [B, seq_len, 768]
            memory = self.text_seq_proj(bert_seq)  # [B, seq_len, d]
            type_feat = self.task_type_emb(task_type_ids)  # [B, d]
            gamma = self.film_gamma(type_feat).unsqueeze(1)
            beta = self.film_beta(type_feat).unsqueeze(1)
            memory = gamma * memory + beta
            memory_key_padding_mask = (text_attention_mask == 0)
        else:
            # V2 兼容: CLS + fusion → single vector K/V
            cls_repr = bert_out.last_hidden_state[:, 0, :]  # [B, 768]
            text_feat = self.text_proj(cls_repr)  # [B, d]
            type_feat = self.task_type_emb(task_type_ids)  # [B, d]
            fused = self.fusion(torch.cat([text_feat, type_feat], dim=-1))  # [B, d]
            memory = fused.unsqueeze(1)  # [B, 1, d]
            memory_key_padding_mask = None

        # Per-token cross-attention
        query_indices = torch.arange(self.num_active_tokens, device=memory.device)
        queries = self.token_queries(query_indices).unsqueeze(0).expand(B, -1, -1)  # [B, N, d]

        attn_out, _ = self.cross_attn(
            queries, memory, memory,
            key_padding_mask=memory_key_padding_mask,
        )  # [B, N, d]
        token_repr = self.attn_norm(queries + attn_out)  # [B, N, d] residual

        # V3: Token-token self-attention
        if self.self_attn_block is not None:
            token_repr = self.self_attn_block(token_repr)  # [B, N, d]

        # Binary head
        binary_logits = self.binary_head(token_repr).squeeze(-1)  # [B, N]

        # Count head
        count_logits = self.count_head(token_repr)  # [B, N, 3]

        return binary_logits, count_logits

    @torch.no_grad()
    def predict_token_scores(
        self,
        task_type_ids: torch.Tensor,
        text_input_ids: torch.Tensor,
        text_attention_mask: torch.Tensor,
    ) -> List[Dict[int, float]]:
        """返回每个 active token 的 presence 概率（用于软约束）。

        Returns:
            List[Dict[int, float]]: 每个样本 {real_token_id: p_present}
        """
        self.eval()
        binary_logits, _ = self.forward(
            task_type_ids, text_input_ids, text_attention_mask
        )
        binary_probs = torch.sigmoid(binary_logits)  # [B, N]

        B = binary_logits.size(0)
        results = []
        for b in range(B):
            scores = {}
            for i in range(self.num_active_tokens):
                real_token_id = self.active_token_ids[i].item()
                scores[real_token_id] = binary_probs[b, i].item()
            results.append(scores)
        return results

    @torch.no_grad()
    def predict_token_counts(
        self,
        task_type_ids: torch.Tensor,
        text_input_ids: torch.Tensor,
        text_attention_mask: torch.Tensor,
        confidence_threshold: float = 0.5,
        top_k: int = 0,
    ) -> List[Dict[int, int]]:
        """
        推理：返回每个样本的 {token_id: predicted_count} 字典。

        Args:
            task_type_ids: [B]
            text_input_ids: [B, seq_len]
            text_attention_mask: [B, seq_len]
            confidence_threshold: binary sigmoid 阈值 (top_k=0 时使用)
            top_k: 若 >0，取概率最高的 K 个 token，忽略 threshold

        Returns:
            List[Dict[int, int]]: 每个样本一个字典, {real_token_id: count}
        """
        self.eval()
        binary_logits, count_logits = self.forward(
            task_type_ids, text_input_ids, text_attention_mask
        )
        # binary_logits: [B, N], count_logits: [B, N, 3]
        binary_probs = torch.sigmoid(binary_logits)  # [B, N]
        count_probs = torch.softmax(count_logits, dim=-1)  # [B, N, 3]

        B = binary_logits.size(0)
        results = []
        for b in range(B):
            token_counts = {}

            if top_k > 0:
                # Top-K 模式：取概率最高的 K 个 token
                k = min(top_k, self.num_active_tokens)
                topk_probs, topk_indices = binary_probs[b].topk(k)
                for idx in topk_indices:
                    i = idx.item()
                    count = count_probs[b, i].argmax().item() + 1
                    real_token_id = self.active_token_ids[i].item()
                    token_counts[real_token_id] = count
            else:
                # Threshold 模式（原逻辑）
                for i in range(self.num_active_tokens):
                    p_present = binary_probs[b, i].item()
                    if p_present > confidence_threshold:
                        count = count_probs[b, i].argmax().item() + 1
                        real_token_id = self.active_token_ids[i].item()
                        token_counts[real_token_id] = count

            results.append(token_counts)

        return results

    def get_parameter_groups(self, bert_lr: float, other_lr: float) -> list:
        """Return parameter groups with different learning rates."""
        bert_params = []
        other_params = []
        for name, param in self.named_parameters():
            if not param.requires_grad:
                continue
            if name.startswith('bert.'):
                bert_params.append(param)
            else:
                other_params.append(param)
        return [
            {'params': bert_params, 'lr': bert_lr},
            {'params': other_params, 'lr': other_lr},
        ]

    @classmethod
    def from_checkpoint(
        cls,
        checkpoint_path: str,
        device: torch.device = torch.device('cpu'),
    ) -> 'L3SetPredictor':
        """Load model from checkpoint. Auto-detects V2 vs V3 architecture."""
        checkpoint = torch.load(checkpoint_path, map_location=device, weights_only=False)
        config = checkpoint.get('config', {})
        active_token_ids = checkpoint['active_token_ids']
        state_dict = checkpoint['model_state_dict']

        # Prefer explicit config, then arch tag, then state-dict auto-detection.
        use_rich = config.get('use_rich_cross_attn')
        if use_rich is None:
            if 'text_seq_proj.weight' in state_dict:
                use_rich = True
            elif 'text_proj.weight' in state_dict:
                use_rich = False
            else:
                use_rich = (config.get('arch_version') == 'v3')

        head_hidden_dim = config.get('head_hidden_dim')
        if head_hidden_dim is None:
            head_hidden_weight = state_dict.get('binary_head.0.weight')
            if head_hidden_weight is not None:
                head_hidden_dim = head_hidden_weight.shape[0]
            else:
                head_hidden_dim = config.get('d_hidden', config.get('d_condition', 256))

        num_count_classes = config.get('num_count_classes')
        if num_count_classes is None:
            count_head_weight = state_dict.get('count_head.3.weight')
            num_count_classes = count_head_weight.shape[0] if count_head_weight is not None else 3

        model = cls(
            num_task_types=config.get('num_task_types', 72),
            d_condition=config.get('d_condition', 256),
            d_hidden=config.get('d_hidden', 512),
            head_hidden_dim=head_hidden_dim,
            num_count_classes=num_count_classes,
            active_token_ids=active_token_ids,
            bert_unfreeze_layers=config.get('bert_unfreeze_layers', 2),
            dropout=config.get('dropout', 0.2),
            num_attn_heads=config.get('num_attn_heads', 4),
            num_self_attn_layers=config.get('num_self_attn_layers', 0),
            self_attn_dim_feedforward=config.get('self_attn_dim_feedforward', 512),
            use_rich_cross_attn=use_rich,
        )
        model.load_state_dict(state_dict)
        model = model.to(device)
        model.eval()
        return model
