# -*- coding: utf-8 -*-
"""
任务条件化Transformer模型 V3.3 - 稳定版

核心改进：
1. BERT少量token作为decoder memory（8个，避免过多噪声）
2. 去掉无效的length prediction任务
3. 修复mask类型警告（统一使用float+additive masking）
4. 条件注入机制

V3.3相比V3.2的调整：
- max_memory_tokens: 32 → 8（减少噪声）
- mask类型: bool → float（解决PyTorch警告）
"""

import torch
import torch.nn as nn
import math
from transformers import BertModel
from pathlib import Path


class BERTTextEncoder(nn.Module):
    """
    BERT文本编码器（V3.4 - 自适应采样memory）

    使用均匀采样而非暴力截断，确保长文本的关键信息不会被忽略
    """

    def __init__(self, freeze_bert=True, max_memory_tokens=32):
        super().__init__()
        self.max_memory_tokens = max_memory_tokens  # 限制memory长度，避免过长

        print("  加载BERT模型 (bert-base-uncased)...")
        try:
            self.bert = BertModel.from_pretrained('bert-base-uncased')
            print("  BERT模型加载成功")
        except Exception as e:
            print(f"  错误：无法加载BERT模型: {e}")
            print("  请确保已安装transformers库并能访问Hugging Face")
            raise

        if freeze_bert:
            for param in self.bert.parameters():
                param.requires_grad = False
            print("  BERT参数已冻结（不参与训练）")
        else:
            print("  BERT参数将参与微调")

        self.hidden_size = 768

    def forward(self, text_input_ids, text_attention_mask):
        """
        前向传播

        Args:
            text_input_ids: [batch, seq_len] BERT token IDs
            text_attention_mask: [batch, seq_len] attention mask

        Returns:
            hidden_states: [batch, memory_len, 768] BERT hidden states序列
            memory_mask: [batch, memory_len] 有效位置mask（bool类型）
        """
        outputs = self.bert(
            input_ids=text_input_ids,
            attention_mask=text_attention_mask
        )

        last_hidden = outputs.last_hidden_state  # [batch, seq_len, 768]
        pooled_output = last_hidden[:, 0, :]  # [CLS]

        batch_size, seq_len, hidden_dim = last_hidden.size()
        hidden_states = last_hidden.new_zeros(batch_size, self.max_memory_tokens, hidden_dim)
        memory_mask = torch.zeros(
            batch_size,
            self.max_memory_tokens,
            dtype=torch.bool,
            device=last_hidden.device
        )

        for b in range(batch_size):
            valid_len = int(text_attention_mask[b].sum().item())
            if valid_len <= 0:
                valid_len = 1
            steps = min(self.max_memory_tokens, valid_len)
            if steps == 1:
                idx = torch.tensor([0], device=last_hidden.device, dtype=torch.long)
            elif steps == 2:
                idx = torch.tensor([0, valid_len - 1], device=last_hidden.device, dtype=torch.long)
            else:
                interior = max(steps - 2, 1)
                interior_idx = torch.linspace(
                    1,
                    valid_len - 2,
                    steps=interior,
                    device=last_hidden.device
                ).round().long()
                idx = torch.cat([
                    torch.tensor([0], device=last_hidden.device, dtype=torch.long),
                    interior_idx,
                    torch.tensor([valid_len - 1], device=last_hidden.device, dtype=torch.long)
                ])
            idx = torch.clamp(idx, 0, valid_len - 1)
            idx = torch.unique_consecutive(idx)
            if idx.size(0) < steps:
                needed = steps - idx.size(0)
                mask = torch.zeros(valid_len, dtype=torch.bool, device=last_hidden.device)
                mask[idx] = True
                extra = torch.arange(valid_len, device=last_hidden.device)[~mask]
                if extra.numel() > 0:
                    idx = torch.cat([idx, extra[:needed]])
            idx = torch.sort(idx[:steps])[0]
            select_len = idx.size(0)
            hidden_states[b, :select_len] = last_hidden[b, idx]
            memory_mask[b, :select_len] = True

        hidden_states = hidden_states[:, :self.max_memory_tokens, :]
        memory_mask = memory_mask[:, :self.max_memory_tokens]

        return hidden_states, memory_mask, pooled_output


class TaskConditionedL3TransformerModelV3(nn.Module):
    """
    任务条件化L3 Transformer模型 V3.2

    核心架构改进：
    1. BERT多token作为decoder的memory（cross-attention真正有效）
    2. 条件向量（任务类型+文本CLS）加到token embedding上
    3. 去掉无效的length prediction
    4. 修复mask类型（使用bool）
    """

    def __init__(
        self,
        vocab_size,
        num_task_types,
        d_model=256,
        n_heads=8,
        n_layers=6,
        dim_feedforward=1024,
        dropout=0.1,
        max_seq_length=100,
        max_memory_tokens=8,  # BERT memory长度（保守设置，避免过多noise）
        use_l3_embeddings=False,
        l3_embeddings_path=None,
        freeze_bert=True,
        embedding_dropout=0.1
    ):
        super().__init__()

        self.vocab_size = vocab_size
        self.d_model = d_model
        self.max_seq_length = max_seq_length
        self.max_memory_tokens = max_memory_tokens
        self.embedding_dropout = nn.Dropout(embedding_dropout)

        # 1. BERT文本编码器（返回完整序列）
        self.text_encoder = BERTTextEncoder(
            freeze_bert=freeze_bert,
            max_memory_tokens=max_memory_tokens
        )

        # 2. 文本投影层（768 → d_model）- 用于memory
        self.text_projection = nn.Linear(768, d_model)

        # 3. 条件投影层（768 → d_model）- 用于条件注入
        self.condition_projection = nn.Linear(768, d_model)

        # 4. 任务类型嵌入
        self.task_type_embedding = nn.Embedding(num_task_types, d_model)

        # 5. L3序列嵌入
        self.token_embedding = nn.Embedding(vocab_size, d_model)
        self.embedding_layernorm = nn.LayerNorm(d_model)

        # 标记是否已使用预训练嵌入初始化
        self.pretrained_l3_loaded = False
        if use_l3_embeddings and l3_embeddings_path:
            self.pretrained_l3_loaded = self._load_l3_embeddings(l3_embeddings_path)

        # 6. 位置编码
        self.positional_encoding = PositionalEncoding(d_model, max_seq_length, dropout)

        # 7. Memory位置编码（为BERT序列添加位置信息）
        self.memory_positional_encoding = PositionalEncoding(d_model, max_memory_tokens, dropout=0.0)

        # 8. 条件融合层（文本CLS + 任务类型 → 条件向量）
        self.condition_fusion = nn.Sequential(
            nn.Linear(d_model * 2, d_model),
            nn.LayerNorm(d_model),
            nn.GELU(),  # 使用GELU替代ReLU
            nn.Dropout(dropout)
        )

        # 9. 条件注入层（将条件加到token embedding上）
        self.condition_injection = nn.Sequential(
            nn.Linear(d_model, d_model),
            nn.Tanh()  # 限制范围
        )

        # 10. Transformer解码器
        decoder_layer = nn.TransformerDecoderLayer(
            d_model=d_model,
            nhead=n_heads,
            dim_feedforward=dim_feedforward,
            dropout=dropout,
            batch_first=True
        )
        self.transformer_decoder = nn.TransformerDecoder(decoder_layer, num_layers=n_layers)

        # 11. 输出层
        self.output_projection = nn.Linear(d_model, vocab_size, bias=False)
        self.output_projection.weight = self.token_embedding.weight

        # 12. 辅助任务：任务类型分类（保留，有效的辅助任务）
        self.task_classifier = nn.Linear(d_model, num_task_types)

        # 初始化自定义层
        self._init_weights()

    def _load_l3_embeddings(self, embeddings_path):
        """加载预训练的L3嵌入"""
        embeddings_path = Path(embeddings_path)
        if embeddings_path.exists():
            pretrained = torch.load(embeddings_path, map_location='cpu', weights_only=True)

            if isinstance(pretrained, dict):
                pretrained_embeddings = pretrained.get('embeddings', None)
            else:
                pretrained_embeddings = pretrained

            if pretrained_embeddings is None:
                print(f"  [WARNING] 无法在{embeddings_path}中找到'embeddings'键")
                return False

            vocab_size_l3 = min(350, pretrained_embeddings.shape[0])
            with torch.no_grad():
                self.token_embedding.weight[:vocab_size_l3] = pretrained_embeddings[:vocab_size_l3]
            print(f"  [OK] 已从HGT嵌入初始化 {vocab_size_l3} 个L3 tokens")
            return True

        print(f"  [WARNING] 未找到L3嵌入文件: {embeddings_path}")
        return False

    def _init_weights(self):
        """初始化模型参数"""
        nn.init.normal_(self.task_type_embedding.weight, mean=0.0, std=0.02)

        if not self.pretrained_l3_loaded:
            nn.init.normal_(self.token_embedding.weight, mean=0.0, std=0.02)
        else:
            with torch.no_grad():
                if self.token_embedding.weight.size(0) > 350:
                    nn.init.normal_(self.token_embedding.weight[350:], mean=0.0, std=0.02)

        # 初始化线性层
        for module in [self.text_projection, self.condition_projection,
                       self.task_classifier]:
            if isinstance(module, nn.Linear):
                nn.init.xavier_uniform_(module.weight)
                if module.bias is not None:
                    nn.init.zeros_(module.bias)

        # 初始化条件融合和注入层
        for seq in [self.condition_fusion, self.condition_injection]:
            for module in seq:
                if isinstance(module, nn.Linear):
                    nn.init.xavier_uniform_(module.weight)
                    if module.bias is not None:
                        nn.init.zeros_(module.bias)

        # 初始化Transformer层
        for layer in self.transformer_decoder.layers:
            for param in layer.parameters():
                if param.dim() > 1:
                    nn.init.xavier_uniform_(param)

        self.register_buffer('_causal_mask', None, persistent=False)

    def forward(
        self,
        input_ids,
        task_type_ids,
        text_input_ids,
        text_attention_mask,
        attention_mask=None,
        return_task_logits=False
    ):
        """
        前向传播

        Args:
            input_ids: [batch, seq_len] L3序列
            task_type_ids: [batch] 任务类型ID
            text_input_ids: [batch, text_len] BERT token IDs
            text_attention_mask: [batch, text_len] BERT attention mask
            attention_mask: [batch, seq_len] 序列mask（可选）
            return_task_logits: 是否返回辅助任务logits

        Returns:
            logits: [batch, seq_len, vocab_size] 输出logits
            task_type_logits: [batch, num_task_types] 任务分类logits（如果return_task_logits=True）
        """
        batch_size, seq_len = input_ids.shape
        device = input_ids.device

        # 1. BERT编码任务描述（返回完整序列）
        bert_hidden, bert_mask, bert_pooled = self.text_encoder(text_input_ids, text_attention_mask)
        # bert_hidden: [batch, memory_len, 768]
        # bert_mask: [batch, memory_len]
        # bert_pooled: [batch, 768] (CLS token)

        # 2. 投影BERT hidden states作为decoder memory
        memory = self.text_projection(bert_hidden)  # [batch, memory_len, d_model]
        memory = self.memory_positional_encoding(memory)  # 添加位置编码

        # 3. 投影CLS token用于条件注入
        text_condition = self.condition_projection(bert_pooled)  # [batch, d_model]

        # 4. 任务类型嵌入
        task_type_embeddings = self.task_type_embedding(task_type_ids)  # [batch, d_model]

        # 5. 条件融合（文本CLS + 任务类型）
        condition_input = torch.cat([text_condition, task_type_embeddings], dim=-1)  # [batch, d_model*2]
        condition_embeddings = self.condition_fusion(condition_input)  # [batch, d_model]

        # 6. L3序列嵌入
        token_embeddings = self.token_embedding(input_ids)  # [batch, seq_len, d_model]

        # 7. 条件注入：将条件向量加到每个token embedding上
        condition_for_injection = self.condition_injection(condition_embeddings)  # [batch, d_model]
        condition_for_injection = condition_for_injection.unsqueeze(1)  # [batch, 1, d_model]
        token_embeddings = token_embeddings + condition_for_injection  # 广播加法
        token_embeddings = self.embedding_layernorm(token_embeddings)
        token_embeddings = self.embedding_dropout(token_embeddings)

        # 8. 位置编码
        token_embeddings = self.positional_encoding(token_embeddings)

        # 9. 创建causal mask（float类型，-inf表示masked）
        causal_mask = self._generate_square_subsequent_mask(seq_len, device)

        # 10. 创建padding mask（使用bool类型，True表示mask）
        tgt_key_padding_mask = (attention_mask == 0) if attention_mask is not None else None
        memory_key_padding_mask = (bert_mask == 0)

        # 11. Transformer解码（使用多token memory）
        decoder_output = self.transformer_decoder(
            tgt=token_embeddings,
            memory=memory,  # [batch, memory_len, d_model] - 多个token！
            tgt_mask=causal_mask,
            tgt_key_padding_mask=tgt_key_padding_mask,
            memory_key_padding_mask=memory_key_padding_mask
        )  # [batch, seq_len, d_model]

        # 12. 输出投影
        logits = self.output_projection(decoder_output)  # [batch, seq_len, vocab_size]
        decoder_device = decoder_output.device

        # 13. 辅助任务（只保留任务类型分类）
        if return_task_logits:
            # 任务类型分类
            if attention_mask is not None:
                lengths = attention_mask.sum(dim=1).clamp(min=1)
                last_indices = (lengths - 1).long()
                seq_representation = decoder_output[
                    torch.arange(decoder_output.size(0), device=decoder_device),
                    last_indices
                ]
            else:
                seq_representation = decoder_output[:, -1, :]

            task_type_logits = self.task_classifier(seq_representation)

            return logits, task_type_logits

        return logits

    def _generate_square_subsequent_mask(self, sz, device):
        """生成causal mask（bool类型，True表示禁止关注）"""
        if (
            self._causal_mask is None
            or self._causal_mask.size(0) < sz
            or self._causal_mask.device != device
        ):
            # 使用 bool 类型，与 key_padding_mask 保持一致
            mask = torch.triu(torch.ones(sz, sz, device=device, dtype=torch.bool), diagonal=1)
            self._causal_mask = mask
        return self._causal_mask[:sz, :sz]


class PositionalEncoding(nn.Module):
    """位置编码"""

    def __init__(self, d_model, max_len, dropout=0.1):
        super().__init__()
        self.dropout = nn.Dropout(p=dropout)

        pe = torch.zeros(max_len, d_model)
        position = torch.arange(0, max_len, dtype=torch.float).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2).float() * (-math.log(10000.0) / d_model))

        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)

        pe = pe.unsqueeze(0)
        self.register_buffer('pe', pe)

    def forward(self, x):
        x = x + self.pe[:, :x.size(1), :]
        return self.dropout(x)
