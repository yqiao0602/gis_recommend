"""
噪声诊断测试：判断 Transformer 模型是否存在过拟合（容量过大）

原理：用随机噪声数据训练同一模型架构，如果能学到远超随机基线的准确率，
说明模型容量过大，在"死记硬背"噪声。

判断标准（词表 354 类，随机基线 = 1/354 ≈ 0.28%）：
  Top-1 ≈ 0.28% → 模型容量合适
  Top-1 > 5%    → 模型容量过大
  Top-1 > 20%   → 严重过拟合
"""

import sys
import random
import time
from pathlib import Path

import torch
import torch.nn as nn
from torch.utils.data import Dataset, DataLoader

# ── project imports ──────────────────────────────────────────────
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from gis_recommend.models.transformer_model_v4 import TaskConditionedL3TransformerModelV4
from gis_recommend.config.transformer_config import (
    VOCAB_SIZE, TOTAL_VOCAB_SIZE,
    V4_D_MODEL, V4_N_HEADS, V4_N_LAYERS, V4_D_FF, V4_DROPOUT,
    V4_MAX_SEQ_LENGTH, V4_MAX_MEMORY_TOKENS,
    V4_GRADIENT_CLIP, V4_LABEL_SMOOTHING,
)

# ── special token indices ────────────────────────────────────────
PAD_INDEX = VOCAB_SIZE + 0   # 350
UNK_INDEX = VOCAB_SIZE + 1   # 351
START_INDEX = VOCAB_SIZE + 2 # 352
END_INDEX = VOCAB_SIZE + 3   # 353

# ── hyperparameters ──────────────────────────────────────────────
NUM_SAMPLES = 44000
NUM_EPOCHS = 15
BATCH_SIZE = 32
LR = 1e-4
MAX_SEQ_LENGTH = V4_MAX_SEQ_LENGTH      # 100
MAX_TEXT_LENGTH = 128
NUM_TASK_TYPES = 87
SEED = 42


# ═════════════════════════════════════════════════════════════════
# NoiseDataset
# ═════════════════════════════════════════════════════════════════
class NoiseDataset(Dataset):
    """生成与真实训练数据完全相同格式的纯随机噪声。

    数据在 __init__ 中预生成并固定，这样模型有机会"记住"这些
    固定的噪声样本——如果容量足够大的话。
    """

    def __init__(self, num_samples: int, seed: int):
        rng = random.Random(seed)
        self.samples = [self._generate_one(rng) for _ in range(num_samples)]

    @staticmethod
    def _generate_one(rng: random.Random) -> dict:
        # 随机 L3 序列，长度 5-20
        seq_len = rng.randint(5, 20)
        tokens = (
            [START_INDEX]
            + [rng.randint(0, VOCAB_SIZE - 1) for _ in range(seq_len)]
            + [END_INDEX]
        )
        # shifted input / target
        input_ids = tokens[:-1]
        target_ids = tokens[1:]

        actual_len = len(input_ids)
        pad_len = MAX_SEQ_LENGTH - actual_len
        attention_mask = [1] * actual_len + [0] * pad_len
        input_ids = input_ids + [PAD_INDEX] * pad_len
        target_ids = target_ids + [PAD_INDEX] * pad_len

        # 随机 BERT 输入（模拟无意义文本）
        text_input_ids = [rng.randint(1, 30000) for _ in range(MAX_TEXT_LENGTH)]
        text_attention_mask = [1] * MAX_TEXT_LENGTH

        task_type_id = rng.randint(0, NUM_TASK_TYPES - 1)

        return {
            "input_ids": torch.tensor(input_ids, dtype=torch.long),
            "target_ids": torch.tensor(target_ids, dtype=torch.long),
            "attention_mask": torch.tensor(attention_mask, dtype=torch.long),
            "text_input_ids": torch.tensor(text_input_ids, dtype=torch.long),
            "text_attention_mask": torch.tensor(text_attention_mask, dtype=torch.long),
            "task_type_id": torch.tensor(task_type_id, dtype=torch.long),
            "seq_len": actual_len,
        }

    def __len__(self):
        return len(self.samples)

    def __getitem__(self, idx):
        return self.samples[idx]


# ═════════════════════════════════════════════════════════════════
# Evaluation
# ═════════════════════════════════════════════════════════════════
@torch.no_grad()
def evaluate(model, loader, device):
    """计算 Top-1 / Top-5 token accuracy（忽略 PAD）。"""
    model.eval()
    correct_1 = 0
    correct_5 = 0
    total = 0

    for batch in loader:
        input_ids = batch["input_ids"].to(device)
        target_ids = batch["target_ids"].to(device)
        task_type_ids = batch["task_type_id"].to(device)
        text_input_ids = batch["text_input_ids"].to(device)
        text_attn = batch["text_attention_mask"].to(device)
        attn_mask = batch["attention_mask"].to(device)

        logits = model(input_ids, task_type_ids, text_input_ids,
                       text_attn, attention_mask=attn_mask)

        # mask out PAD positions
        mask = target_ids != PAD_INDEX                   # [B, T]
        logits_flat = logits[mask]                       # [N, V]
        targets_flat = target_ids[mask]                  # [N]

        if targets_flat.numel() == 0:
            continue

        # top-1
        preds = logits_flat.argmax(dim=-1)
        correct_1 += (preds == targets_flat).sum().item()

        # top-5
        _, top5 = logits_flat.topk(5, dim=-1)
        correct_5 += (top5 == targets_flat.unsqueeze(-1)).any(dim=-1).sum().item()

        total += targets_flat.numel()

    top1 = correct_1 / total * 100 if total else 0.0
    top5 = correct_5 / total * 100 if total else 0.0
    return top1, top5


# ═════════════════════════════════════════════════════════════════
# Main
# ═════════════════════════════════════════════════════════════════
def main():
    torch.manual_seed(SEED)
    random.seed(SEED)
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    random_baseline = 1.0 / TOTAL_VOCAB_SIZE * 100

    print("=" * 60)
    print("噪声诊断测试 (Noise Diagnostic Test)")
    print("=" * 60)

    # ── 1. 数据 ──────────────────────────────────────────────────
    print(f"\n[1] 生成噪声数据 ({NUM_SAMPLES} samples) ...")
    dataset = NoiseDataset(NUM_SAMPLES, seed=SEED)
    loader = DataLoader(dataset, batch_size=BATCH_SIZE, shuffle=True,
                        num_workers=0, pin_memory=(device.type == "cuda"))

    # ── 2. 模型（从头初始化） ────────────────────────────────────
    print("[2] 初始化模型（随机权重，冻结全部 BERT）...")
    model = TaskConditionedL3TransformerModelV4(
        vocab_size=TOTAL_VOCAB_SIZE,
        num_task_types=NUM_TASK_TYPES,
        d_model=V4_D_MODEL,
        n_heads=V4_N_HEADS,
        n_layers=V4_N_LAYERS,
        dim_feedforward=V4_D_FF,
        dropout=V4_DROPOUT,
        max_seq_length=MAX_SEQ_LENGTH,
        max_memory_tokens=V4_MAX_MEMORY_TOKENS,
        use_l3_embeddings=False,
        freeze_bert=True,           # 冻结全部 BERT
        bert_unfreeze_layers=0,     # 不解冻任何层
    ).to(device)

    counts = model.count_parameters()
    print(f"  参数量: {counts['trainable']/1e6:.1f}M (可训练), "
          f"{counts['total']/1e6:.1f}M (总计)")
    print(f"  词表大小: {TOTAL_VOCAB_SIZE}")
    print(f"  随机基线: {random_baseline:.2f}%")
    print(f"  Device: {device}")

    # ── 3. 优化器 & 损失 ─────────────────────────────────────────
    optimizer = torch.optim.AdamW(
        [p for p in model.parameters() if p.requires_grad],
        lr=LR, weight_decay=0.01,
    )
    criterion = nn.CrossEntropyLoss(
        ignore_index=PAD_INDEX,
        label_smoothing=V4_LABEL_SMOOTHING,
    )

    # ── 4. 训练 ──────────────────────────────────────────────────
    print(f"\n{'Epoch':>8}  {'Loss':>10}  {'Top-1':>8}  {'Top-5':>8}  {'Time':>7}")
    print("-" * 50)

    # pre-train baseline
    top1, top5 = evaluate(model, loader, device)
    print(f"{'init':>8}  {'—':>10}  {top1:7.2f}%  {top5:7.2f}%")

    history = []

    for epoch in range(1, NUM_EPOCHS + 1):
        model.train()
        epoch_loss = 0.0
        num_batches = 0
        t0 = time.time()

        for batch in loader:
            input_ids = batch["input_ids"].to(device)
            target_ids = batch["target_ids"].to(device)
            task_type_ids = batch["task_type_id"].to(device)
            text_input_ids = batch["text_input_ids"].to(device)
            text_attn = batch["text_attention_mask"].to(device)
            attn_mask = batch["attention_mask"].to(device)

            logits = model(input_ids, task_type_ids, text_input_ids,
                           text_attn, attention_mask=attn_mask)

            loss = criterion(logits.view(-1, logits.size(-1)),
                             target_ids.view(-1))

            optimizer.zero_grad()
            loss.backward()
            nn.utils.clip_grad_norm_(
                [p for p in model.parameters() if p.requires_grad],
                V4_GRADIENT_CLIP,
            )
            optimizer.step()

            epoch_loss += loss.item()
            num_batches += 1

        avg_loss = epoch_loss / num_batches
        top1, top5 = evaluate(model, loader, device)
        elapsed = time.time() - t0
        history.append((epoch, avg_loss, top1, top5))

        print(f"{epoch:>5}/{NUM_EPOCHS}  {avg_loss:10.4f}  {top1:7.2f}%  {top5:7.2f}%  {elapsed:5.1f}s")

    # ── 5. 诊断结论 ──────────────────────────────────────────────
    final_top1 = history[-1][2]
    delta = final_top1 - random_baseline

    print("\n" + "=" * 60)
    print("诊断结论")
    print("=" * 60)
    print(f"  最终 Top-1: {final_top1:.2f}%  (随机基线: {random_baseline:.2f}%)")
    print(f"  偏离基线:   {'+' if delta >= 0 else ''}{delta:.2f}%")

    if final_top1 > 20:
        verdict = "严重过拟合 — 模型容量远超数据复杂度，必须缩小模型"
        symbol = "!!"
    elif final_top1 > 5:
        verdict = "过拟合 — 模型容量偏大，能记住噪声"
        symbol = "!"
    else:
        verdict = "模型容量合适 — Top-1 接近随机基线，问题不在架构"
        symbol = "OK"

    print(f"  结论: [{symbol}] {verdict}")
    print()


if __name__ == "__main__":
    main()
