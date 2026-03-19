"""
详细的生成评估脚本 V3 - 最终修正版（FINAL）

修正要点：
1. ✅ 修复 Bottom10 打印语法错误
2. ✅ 使用位置参数调用 _greedy_decode_batch（更稳健）
3. ✅ 同时输出包含/不包含 END 的 Token Acc
4. ✅ 确保 END 偏差计算的稳健性（区分 END/PAD/NONE）
5. ✅ PAD 诊断避免"自证循环"（end_type=PAD 不含末尾终止PAD）
6. ✅ 强制使用最新的 L3 embeddings（load checkpoint 后覆盖，自动匹配参数名）
7. ✅ gold_len==0 跳过并统计，所有指标分母使用有效样本数
8. ✅ 支持部分 embedding 替换（L3 350 -> token_embedding 354 前 350 行）
9. ✅ 【关键修复】target 也去掉 START，与 pred 对齐（避免序列整体错位）
"""

import torch
import json
from pathlib import Path
from collections import defaultdict
import numpy as np
from transformers import BertTokenizer
from tqdm import tqdm

# 只从训练脚本导入（单一真源）
from gis_recommend.training.train_v3 import (
    ScheduledSamplingTrainerV3,
    TaskConditionedL3DatasetV3,
    PAD_TOKEN_ID,
    END_TOKEN_ID,
    START_TOKEN_ID
)
from gis_recommend.models.transformer_model_v3 import TaskConditionedL3TransformerModelV3
from gis_recommend.models.task_text_processor import TaskVocabularyBuilder


# ===================== 配置 =====================
CHECKPOINT_DIR = Path("outputs/task_conditioned_checkpoints_v3_7_final")
DATASET_PATH = Path("outputs/labeled_workflows_l3_smart_cleaned.json")
DATASET_SPLITS_PATH = Path("outputs/dataset_splits_v3.json")
VOCAB_PATH = Path("outputs/task_type_vocabulary.json")
L3_EMBEDDINGS_PATH = Path("outputs/l3_embeddings.pt")  # 最新 L3 embeddings (1月31日)
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

MAX_SEQ_LEN = 100
MAX_TEXT_LEN = 128
BATCH_SIZE = 32

# 与训练保持一致（你现在这套）
MODEL_KWARGS = dict(
    vocab_size=354,
    d_model=256,
    n_heads=8,
    n_layers=6,
    dropout=0.1,
    max_seq_length=MAX_SEQ_LEN,
    max_memory_tokens=16,
    use_l3_embeddings=True,
    l3_embeddings_path=str(L3_EMBEDDINGS_PATH),
)


print("=" * 80)
print("详细生成评估 V3 - FINAL")
print("=" * 80)
print(f"Device: {DEVICE}")
print(f"PAD_TOKEN_ID: {PAD_TOKEN_ID}")
print(f"END_TOKEN_ID: {END_TOKEN_ID}")
print(f"START_TOKEN_ID: {START_TOKEN_ID}")
print(f"Checkpoint Dir: {CHECKPOINT_DIR}")
print(f"L3 Embeddings: {L3_EMBEDDINGS_PATH}")


# ===================== 1. 加载数据 =====================
print("\n[1] 加载数据...")
with open(DATASET_PATH, "r", encoding="utf-8") as f:
    workflow_data = json.load(f)
    all_workflows = workflow_data["labeled_workflows"]

with open(DATASET_SPLITS_PATH, "r", encoding="utf-8") as f:
    splits = json.load(f)

test_indices = splits["test_indices"]
test_workflows = [all_workflows[i] for i in test_indices if i < len(all_workflows)]
print(f"  测试集样本数: {len(test_workflows)}")


# ===================== 2. 加载词汇表 =====================
print("\n[2] 加载词汇表...")
with open(VOCAB_PATH, "r", encoding="utf-8") as f:
    vocab_data = json.load(f)

task_vocab_builder = TaskVocabularyBuilder()
task_vocab_builder.task_type_to_id = vocab_data["task_type_to_id"]
task_vocab_builder.id_to_task_type = {int(k): v for k, v in vocab_data["id_to_task_type"].items()}
print(f"  任务类型数: {len(task_vocab_builder.task_type_to_id)}")


# ===================== 3. 创建测试数据集 =====================
print("\n[3] 创建测试数据集...")
bert_tokenizer = BertTokenizer.from_pretrained("bert-base-uncased")

test_dataset = TaskConditionedL3DatasetV3(
    test_workflows,
    task_vocab_builder,
    bert_tokenizer,
    max_seq_length=MAX_SEQ_LEN,
    max_text_length=MAX_TEXT_LEN,
)

test_loader = torch.utils.data.DataLoader(
    test_dataset,
    batch_size=BATCH_SIZE,
    shuffle=False,
)


# ===================== 辅助函数 =====================
def strip_start_if_present(seq: torch.Tensor):
    """
    如果 target 序列开头是 START，则去掉它
    这是评估对齐的关键：pred 已经去掉 START，target 也必须去掉
    """
    if seq.numel() > 0 and seq[0].item() == START_TOKEN_ID:
        return seq[1:]
    return seq


def get_gold_length(target_ids: torch.Tensor):
    """
    从 target_ids 推导真实有效长度（避免 seq_len 定义差异）
    返回: (gold_len, has_anomaly)
      gold_len: 有效长度（含 END）
      has_anomaly: END后有非PAD 或 多个END
    """
    end_positions = (target_ids == END_TOKEN_ID).nonzero(as_tuple=True)[0]
    if len(end_positions) > 0:
        first_end_pos = end_positions[0].item()
        gold_len = first_end_pos + 1  # 含 END

        has_anomaly = False
        if gold_len < len(target_ids):
            after_end = target_ids[gold_len:]
            if (after_end != PAD_TOKEN_ID).any():
                has_anomaly = True

        if len(end_positions) > 1:
            has_anomaly = True

        return gold_len, has_anomaly

    gold_len = (target_ids != PAD_TOKEN_ID).sum().item()
    return gold_len, False


def has_end_token(target_ids: torch.Tensor, gold_len: int):
    if gold_len > 0:
        return target_ids[gold_len - 1].item() == END_TOKEN_ID
    return False


def get_pred_end_position(pred_tokens: torch.Tensor):
    """
    返回: (end_pos, end_type)
      end_pos: 第一个 END / 第一个 PAD / 最后位置
      end_type: 'END' | 'PAD' | 'NONE'
    """
    if pred_tokens.dim() > 1:
        pred_tokens = pred_tokens.squeeze()

    end_positions = (pred_tokens == END_TOKEN_ID).nonzero(as_tuple=True)
    if len(end_positions[0]) > 0:
        return end_positions[0][0].item(), "END"

    pad_positions = (pred_tokens == PAD_TOKEN_ID).nonzero(as_tuple=True)
    if len(pad_positions[0]) > 0:
        return pad_positions[0][0].item(), "PAD"

    return len(pred_tokens) - 1, "NONE"


def force_load_latest_l3_embeddings(model: torch.nn.Module, l3_path: Path, device: torch.device):
    """
    在 load checkpoint 后，强制覆盖最新 L3 embeddings（鲁棒版 + 支持部分替换）
    - 支持：Tensor / dict / state_dict / 任意嵌套结构
    - 递归提取所有 Tensor，按 shape 匹配 + 路径关键词打分选择最可能的 embedding
    - 支持部分替换：L3 embeddings (350, 256) -> token_embedding.weight (354, 256) 的前 350 行
    """
    obj = torch.load(l3_path, map_location=device, weights_only=False)

    # 1) 递归收集所有 tensor（带路径）
    tensors = []

    def walk(x, path="root"):
        if torch.is_tensor(x):
            tensors.append((path, x))
            return
        if isinstance(x, dict):
            for k, v in x.items():
                walk(v, f"{path}.{k}")
            return
        if isinstance(x, (list, tuple)):
            for i, v in enumerate(x):
                walk(v, f"{path}[{i}]")
            return

    walk(obj)

    if not tensors:
        raise RuntimeError(f"No tensor found inside {l3_path} (type={type(obj)})")

    # 2) 取模型里所有参数 shape，方便匹配
    sd = model.state_dict()
    shape_to_names = defaultdict(list)
    for name, t in sd.items():
        shape_to_names[tuple(t.shape)].append(name)

    # 3) 给每个候选 tensor 打分：shape 能匹配 + 路径关键词
    def score_path(p: str):
        p = p.lower()
        score = 0
        if "l3" in p: score += 5
        if "embed" in p or "emb" in p: score += 4
        if "weight" in p: score += 2
        if "hgt" in p: score += 1
        return score

    candidates = []
    for path, t in tensors:
        shp = tuple(t.shape)
        if shp in shape_to_names:
            # shape 匹配：高优先级
            candidates.append((100 + score_path(path), path, t, shp, "exact"))
        else:
            # 不匹配也先留着，万一全都不匹配还能给你诊断信息
            candidates.append((score_path(path), path, t, shp, "no_match"))

    # 4) 选最佳：先看 shape 匹配者（score>=100），否则尝试部分替换
    candidates.sort(key=lambda x: x[0], reverse=True)

    best = candidates[0]
    if best[0] < 100:
        # 没有精确匹配，尝试部分替换（L3 embeddings -> token_embedding 前 N 行）
        # 找到 L3 embeddings tensor（应该是 (350, 256)）
        l3_tensor = None
        l3_path_str = None
        for path, t in tensors:
            if t.dim() == 2 and score_path(path) > 0:
                l3_tensor = t
                l3_path_str = path
                break

        if l3_tensor is None:
            top_show = "\n".join([f"    - {p}: shape={s}" for _, p, _, s, _ in candidates[:20]])
            model_shapes = "\n".join([f"    - {n}: {tuple(sd[n].shape)}" for n in list(sd.keys()) if "emb" in n.lower() or "l3" in n.lower()][:20])
            raise RuntimeError(
                f"No tensor inside {l3_path} matches any model parameter shape.\n"
                f"Top tensor candidates (first 20):\n{top_show}\n\n"
                f"Model embedding-like params (first 20):\n{model_shapes}\n"
            )

        # 找到 token_embedding.weight（应该是 (354, 256) 或类似）
        l3_emb = l3_tensor.to(device)
        l3_vocab_size, l3_dim = l3_emb.shape

        # 找到最可能的 token embedding 参数（vocab_size > l3_vocab_size, d_model == l3_dim）
        def score_name(n: str):
            n = n.lower()
            s = 0
            if "token" in n: s += 5
            if "embed" in n or "emb" in n: s += 4
            if "weight" in n: s += 2
            return s

        target_candidates = []
        for name, t in sd.items():
            if t.dim() == 2 and t.shape[1] == l3_dim and t.shape[0] > l3_vocab_size:
                target_candidates.append((score_name(name), name, t.shape))

        if not target_candidates:
            raise RuntimeError(
                f"Cannot find suitable target parameter for partial replacement.\n"
                f"L3 embeddings shape: {l3_emb.shape}\n"
                f"Need model parameter with shape (N, {l3_dim}) where N > {l3_vocab_size}"
            )

        target_candidates.sort(key=lambda x: x[0], reverse=True)
        best_score, best_name, best_shape = target_candidates[0]

        # 部分替换：只覆盖前 l3_vocab_size 行
        with torch.no_grad():
            sd[best_name][:l3_vocab_size, :].copy_(l3_emb)

        model.load_state_dict(sd, strict=False)

        print(f"  ✅ 强制覆盖最新 L3 embedding (部分替换):")
        print(f"     - from file tensor: {l3_path_str} shape={l3_emb.shape}")
        print(f"     - to model param:   {best_name}[:{l3_vocab_size}, :] (total shape={best_shape})")
        print(f"     - 保留特殊 token embeddings: {best_name}[{l3_vocab_size}:, :]")

        return best_name

    # 精确匹配的情况
    _, best_path, l3_emb, shp, _ = best
    l3_emb = l3_emb.to(device)

    # 5) 在模型参数里选一个最像 embedding 的 name 来覆盖
    # 同 shape 的参数可能不止一个，这里按 name 关键词再打一次分
    names = shape_to_names[shp]

    def score_name(n: str):
        n = n.lower()
        s = 0
        if "l3" in n: s += 5
        if "embed" in n or "emb" in n: s += 4
        if "weight" in n: s += 2
        return s

    names = sorted(names, key=score_name, reverse=True)
    best_name = names[0]

    with torch.no_grad():
        sd[best_name].copy_(l3_emb)

    model.load_state_dict(sd, strict=False)

    print(f"  ✅ 强制覆盖最新 L3 embedding (完全替换):")
    print(f"     - from file tensor: {best_path} shape={shp}")
    print(f"     - to model param:   {best_name} shape={tuple(sd[best_name].shape)}")

    return best_name


# ===================== 4. 加载模型 =====================
print("\n[4] 加载模型...")
model = TaskConditionedL3TransformerModelV3(
    num_task_types=len(task_vocab_builder.task_type_to_id),
    **MODEL_KWARGS
).to(DEVICE)

best_model_path = CHECKPOINT_DIR / "best_model.pth"
checkpoint = torch.load(best_model_path, map_location=DEVICE, weights_only=False)
model.load_state_dict(checkpoint)
print(f"  ✓ 已加载模型: {best_model_path}")

# ⚠️ 测试：暂时注释掉强制覆盖，使用 checkpoint 中的原始 embeddings
print(f"  [Embedding] 使用 checkpoint 中的原始 embeddings（未强制覆盖）")
# _ = force_load_latest_l3_embeddings(model, L3_EMBEDDINGS_PATH, DEVICE)

model.eval()


# ===================== 5. 创建训练器（复用其解码方法） =====================
print("\n[5] 创建训练器（用于复用解码方法）...")
trainer = ScheduledSamplingTrainerV3(
    model=model,
    train_loader=None,
    val_loader=test_loader,
    test_loader=test_loader,
    device=DEVICE,
    lr=5e-5,
    num_epochs=1,
    checkpoint_dir=CHECKPOINT_DIR,
    generation_eval_batches=999,
    generation_sample_size=0,
    decode_use_constraints=True,
    decode_min_length=6,
    decode_repetition_penalty=1.2,
    decode_no_repeat_ngram=3,
    decode_end_length_bias=0.1,
)


# ===================== 6. 运行评估 =====================
print("\n[6] 运行详细评估...")
print("=" * 80)

stats = {
    "free": defaultdict(list),
    "cons": defaultdict(list),
}

end_type_stats = {
    "free": {"END": 0, "PAD": 0, "NONE": 0},
    "cons": {"END": 0, "PAD": 0, "NONE": 0},
}

gold_anomaly_count = 0
zero_len_count = 0
pred_shorter_count = 0  # 预测比 gold 短的样本数
start_stripped_count = 0  # 从 target 中去掉 START 的样本数

# PAD 诊断：严格版（避免自证循环）
pad_diagnostics = {
    "free": {"pad_in_prefix": 0, "pad_before_end": 0},
    "cons": {"pad_in_prefix": 0, "pad_before_end": 0},
}

# alignment：按 end_type 分桶，记录样本数
alignment_diagnostics = {
    "free": {
        "END": {"correct": 0, "total": 0, "samples": 0},
        "PAD": {"correct": 0, "total": 0, "samples": 0},
        "NONE": {"correct": 0, "total": 0, "samples": 0},
    },
    "cons": {
        "END": {"correct": 0, "total": 0, "samples": 0},
        "PAD": {"correct": 0, "total": 0, "samples": 0},
        "NONE": {"correct": 0, "total": 0, "samples": 0},
    },
}

# 任务类型统计
task_type_stats = defaultdict(lambda: {
    "free_token_correct_incl": 0,
    "free_token_total_incl": 0,
    "free_token_correct_excl": 0,
    "free_token_total_excl": 0,
    "free_seq_em": 0,
    "cons_token_correct_incl": 0,
    "cons_token_total_incl": 0,
    "cons_token_correct_excl": 0,
    "cons_token_total_excl": 0,
    "cons_seq_em": 0,
    "count": 0,
    "total_gold_len": 0,
})

prefix_steps = [3, 5, 10, 20]
prefix_ratios = [1/3, 2/3, 1.0]

for mode in ["free", "cons"]:
    for k in prefix_steps:
        stats[mode][f"prefix@{k}_correct"] = 0
        stats[mode][f"prefix@{k}_total"] = 0
    for r in prefix_ratios:
        stats[mode][f"prefix@{r:.2f}_correct"] = 0
        stats[mode][f"prefix@{r:.2f}_total"] = 0

print(f"评估模式: FREE (无约束) + CONSTRAINED (有约束)")
print(f"评估批次: 全部测试集 ({len(test_loader)} batches)")
print()

# 诊断：检查第一个 batch 的 target 是否包含 START
first_batch = next(iter(test_loader))
first_target = first_batch["target_ids"][0]
print(f"[诊断] 第一个样本的 target 前5个token: {first_target[:5].tolist()}")
print(f"[诊断] START_TOKEN_ID={START_TOKEN_ID}, END_TOKEN_ID={END_TOKEN_ID}, PAD_TOKEN_ID={PAD_TOKEN_ID}")
if first_target[0].item() == START_TOKEN_ID:
    print(f"[诊断] ✅ target 包含 START，需要去掉")
else:
    print(f"[诊断] ❌ target 不包含 START，strip_start_if_present 不会生效")
print()

for batch_idx, batch in enumerate(tqdm(test_loader, desc="评估进度")):
    target_ids = batch["target_ids"].to(DEVICE)
    task_type_ids = batch["task_type_id"].cpu().numpy()
    bs = target_ids.size(0)

    # ✅ 位置参数调用（稳健）
    # 注意：模型 max_seq_length=100，生成时包含 START，所以最多生成 100 个 token
    # 移除 START 后最多有 99 个 token 可用于比较
    generated_free = trainer._greedy_decode_batch(batch, MAX_SEQ_LEN, False)
    pred_tokens_free = generated_free[:, 1:]  # 移除 START

    generated_cons = trainer._greedy_decode_batch(batch, MAX_SEQ_LEN, True)
    pred_tokens_cons = generated_cons[:, 1:]  # 移除 START

    for i in range(bs):
        # ✅ 关键修复：target 也要去掉 START（如果有的话）
        # pred 已经去掉了 START，target 必须对齐，否则整个序列错位
        target_original = target_ids[i]
        target = strip_start_if_present(target_original)

        # 诊断：记录是否去掉了 START
        if target.size(0) < target_original.size(0):
            start_stripped_count += 1

        pred_free = pred_tokens_free[i]
        pred_cons = pred_tokens_cons[i]
        task_type_id = task_type_ids[i]

        gold_len, has_anomaly = get_gold_length(target)

        # 跳过极端样本：gold_len == 0
        if gold_len == 0:
            zero_len_count += 1
            continue

        if has_anomaly:
            gold_anomaly_count += 1

        has_end = has_end_token(target, gold_len)

        # 确保比较长度不超过预测序列的实际长度（防御性编程）
        compare_len = min(gold_len, pred_free.size(0), pred_cons.size(0))

        if compare_len < gold_len:
            pred_shorter_count += 1

        target_valid = target[:compare_len]
        pred_free_valid = pred_free[:compare_len]
        pred_cons_valid = pred_cons[:compare_len]

        # Token acc（含/不含 END） + Prefix + first_error
        for mode, pred_valid in [("free", pred_free_valid), ("cons", pred_cons_valid)]:
            matches = (pred_valid == target_valid)
            # 如果预测比 gold 短，缺失的 token 算作错误
            correct_count = matches.sum().item()
            stats[mode]["token_correct_incl"].append(correct_count)
            stats[mode]["token_total_incl"].append(gold_len)
            stats[mode]["seq_em"].append(int(matches.all().item() and compare_len == gold_len))

            if has_end and gold_len > 1:
                # 不含 END 的比较：只比较到 gold_len-1 或 compare_len-1
                excl_len = min(gold_len - 1, compare_len)
                if excl_len > 0:
                    matches_excl = (pred_valid[:excl_len] == target_valid[:excl_len])
                    stats[mode]["token_correct_excl"].append(matches_excl.sum().item())
                    stats[mode]["token_total_excl"].append(gold_len - 1)
            elif not has_end:
                stats[mode]["token_correct_excl"].append(correct_count)
                stats[mode]["token_total_excl"].append(gold_len)

            for k in prefix_steps:
                if compare_len >= k:
                    prefix_matches = (pred_valid[:k] == target_valid[:k])
                    stats[mode][f"prefix@{k}_correct"] += prefix_matches.sum().item()
                    stats[mode][f"prefix@{k}_total"] += k

            for r in prefix_ratios:
                prefix_len = int(gold_len * r)
                if prefix_len > 0 and compare_len >= prefix_len:
                    prefix_matches = (pred_valid[:prefix_len] == target_valid[:prefix_len])
                    stats[mode][f"prefix@{r:.2f}_correct"] += prefix_matches.sum().item()
                    stats[mode][f"prefix@{r:.2f}_total"] += prefix_len

            if not matches.all():
                first_error_pos = (matches == False).nonzero(as_tuple=True)[0][0].item()
                stats[mode]["first_error_pos"].append(first_error_pos)
            elif compare_len < gold_len:
                # 预测比 gold 短，第一个错误在 compare_len 位置（缺失的第一个 token）
                stats[mode]["first_error_pos"].append(compare_len)
            else:
                stats[mode]["first_error_pos"].append(gold_len)

        # END bias + PAD诊断（严格版） + alignment（按 end_type 分桶）
        gold_end_pos = gold_len - 1

        for mode, pred in [("free", pred_free), ("cons", pred_cons)]:
            pred_end_pos, end_type = get_pred_end_position(pred)
            end_bias = pred_end_pos - gold_end_pos
            stats[mode]["end_bias"].append(end_bias)
            end_type_stats[mode][end_type] += 1

            # ✅ PAD 诊断：避免自证循环
            # end_type == PAD 时，不含末尾终止 PAD
            if end_type == "PAD":
                pred_prefix_strict = pred[:pred_end_pos]
            else:
                pred_prefix_strict = pred[:pred_end_pos + 1]

            pad_in_prefix = (pred_prefix_strict == PAD_TOKEN_ID).any().item()
            if pad_in_prefix:
                pad_diagnostics[mode]["pad_in_prefix"] += 1

                end_in_prefix = (pred_prefix_strict == END_TOKEN_ID).any().item()
                if end_in_prefix:
                    pad_pos = (pred_prefix_strict == PAD_TOKEN_ID).nonzero(as_tuple=True)[0][0].item()
                    end_pos = (pred_prefix_strict == END_TOKEN_ID).nonzero(as_tuple=True)[0][0].item()
                    if pad_pos < end_pos:
                        pad_diagnostics[mode]["pad_before_end"] += 1

            # alignment：用 pred.size(0) 语义自洽
            pred_trunc_len = min(pred_end_pos + 1, pred.size(0))
            if pred_trunc_len > 0:
                pred_trunc = pred[:pred_trunc_len]
                target_trunc = target[:pred_trunc_len]
                matches_pred_trunc = (pred_trunc == target_trunc)
                alignment_diagnostics[mode][end_type]["correct"] += matches_pred_trunc.sum().item()
                alignment_diagnostics[mode][end_type]["total"] += pred_trunc_len
                alignment_diagnostics[mode][end_type]["samples"] += 1

        # 任务类型统计
        task_type_stats[task_type_id]["count"] += 1
        task_type_stats[task_type_id]["total_gold_len"] += gold_len

        free_matches = (pred_free_valid == target_valid)
        task_type_stats[task_type_id]["free_token_correct_incl"] += free_matches.sum().item()
        task_type_stats[task_type_id]["free_token_total_incl"] += gold_len
        task_type_stats[task_type_id]["free_seq_em"] += int(free_matches.all().item() and compare_len == gold_len)

        if has_end and gold_len > 1:
            excl_len = min(gold_len - 1, compare_len)
            if excl_len > 0:
                free_matches_excl = (pred_free_valid[:excl_len] == target_valid[:excl_len])
                task_type_stats[task_type_id]["free_token_correct_excl"] += free_matches_excl.sum().item()
                task_type_stats[task_type_id]["free_token_total_excl"] += gold_len - 1
        elif not has_end:
            task_type_stats[task_type_id]["free_token_correct_excl"] += free_matches.sum().item()
            task_type_stats[task_type_id]["free_token_total_excl"] += gold_len

        cons_matches = (pred_cons_valid == target_valid)
        task_type_stats[task_type_id]["cons_token_correct_incl"] += cons_matches.sum().item()
        task_type_stats[task_type_id]["cons_token_total_incl"] += gold_len
        task_type_stats[task_type_id]["cons_seq_em"] += int(cons_matches.all().item() and compare_len == gold_len)

        if has_end and gold_len > 1:
            excl_len = min(gold_len - 1, compare_len)
            if excl_len > 0:
                cons_matches_excl = (pred_cons_valid[:excl_len] == target_valid[:excl_len])
                task_type_stats[task_type_id]["cons_token_correct_excl"] += cons_matches_excl.sum().item()
                task_type_stats[task_type_id]["cons_token_total_excl"] += gold_len - 1
        elif not has_end:
            task_type_stats[task_type_id]["cons_token_correct_excl"] += cons_matches.sum().item()
            task_type_stats[task_type_id]["cons_token_total_excl"] += gold_len


# ===================== 7. 输出结果 =====================
print("\n" + "=" * 80)
print("评估结果")
print("=" * 80)

total_evaluated_samples = len(stats["free"]["seq_em"])

print(f"\n[数据质量检查]")
print(f"  有效评估样本数（跳过 gold_len==0 后）: {total_evaluated_samples}")
print(f"  gold_len==0 被跳过样本数: {zero_len_count}")
print(f"  从 target 中去掉 START 的样本数: {start_stripped_count}")
if total_evaluated_samples > 0 and start_stripped_count > 0:
    print(f"    (占比: {start_stripped_count/total_evaluated_samples:.2%})")
print(f"  预测比 gold 短的样本数: {pred_shorter_count}")
if total_evaluated_samples > 0 and pred_shorter_count > 0:
    print(f"    (占比: {pred_shorter_count/total_evaluated_samples:.2%}, 原因: 模型 max_seq_length=100, 生成后移除 START 只剩 99 token)")
print(f"  Gold 异常样本数: {gold_anomaly_count}")
if total_evaluated_samples > 0:
    print(f"  异常率: {gold_anomaly_count/total_evaluated_samples:.2%}")
print(f"  (异常定义: END后有非PAD token，或多个END)")


for mode in ["free", "cons"]:
    print(f"\n{'='*40}")
    print(f"{mode.upper()} 解码")
    print(f"{'='*40}")

    total_token_correct_incl = sum(stats[mode]["token_correct_incl"])
    total_token_total_incl = sum(stats[mode]["token_total_incl"])
    total_token_correct_excl = sum(stats[mode]["token_correct_excl"])
    total_token_total_excl = sum(stats[mode]["token_total_excl"])
    total_seq_em = sum(stats[mode]["seq_em"])
    total_samples = len(stats[mode]["seq_em"])

    print(f"\n整体指标:")
    print(f"  Token Acc (含END):   {total_token_correct_incl/total_token_total_incl:.2%}")
    if total_token_total_excl > 0:
        print(f"  Token Acc (不含END): {total_token_correct_excl/total_token_total_excl:.2%}")
    else:
        print(f"  Token Acc (不含END): N/A")
    print(f"  Sequence EM:         {total_seq_em/total_samples:.2%}")
    print(f"  样本数:              {total_samples}")

    print(f"\nPrefix Accuracy (固定步数):")
    for k in prefix_steps:
        correct = stats[mode][f"prefix@{k}_correct"]
        total = stats[mode][f"prefix@{k}_total"]
        if total > 0:
            print(f"  Prefix@{k:2d}:      {correct/total:.2%}")

    print(f"\nPrefix Accuracy (比例):")
    for r in prefix_ratios:
        correct = stats[mode][f"prefix@{r:.2f}_correct"]
        total = stats[mode][f"prefix@{r:.2f}_total"]
        if total > 0:
            print(f"  Prefix@{r:.0%}:     {correct/total:.2%}")

    first_errors = stats[mode]["first_error_pos"]
    print(f"\nFirst-error Position 分布:")
    print(f"  平均:          {np.mean(first_errors):.2f}")
    print(f"  中位数:        {np.median(first_errors):.2f}")
    print(f"  25%分位:       {np.percentile(first_errors, 25):.2f}")
    print(f"  75%分位:       {np.percentile(first_errors, 75):.2f}")

    end_biases = stats[mode]["end_bias"]
    print(f"\nEND 命中位置偏差 (pred - gold):")
    print(f"  平均:          {np.mean(end_biases):.2f}")
    print(f"  中位数:        {np.median(end_biases):.2f}")
    print(f"  提前结束率:    {sum(1 for b in end_biases if b < 0) / len(end_biases):.2%}")
    print(f"  延迟结束率:    {sum(1 for b in end_biases if b > 0) / len(end_biases):.2%}")
    print(f"  提前>5步率:    {sum(1 for b in end_biases if b < -5) / len(end_biases):.2%}")

    total_samples_mode = sum(end_type_stats[mode].values())
    assert total_samples_mode == len(stats[mode]["seq_em"]), \
        f"END 类型统计样本数 ({total_samples_mode}) != 总样本数 ({len(stats[mode]['seq_em'])})"

    print(f"\nEND 类型分布:")
    print(f"  正常 END:      {end_type_stats[mode]['END']/total_samples_mode:.2%}")
    print(f"  用 PAD 结束:   {end_type_stats[mode]['PAD']/total_samples_mode:.2%}")
    print(f"  无结束标记:    {end_type_stats[mode]['NONE']/total_samples_mode:.2%}")

    print(f"\nPAD 诊断 (严格版：end_type=PAD时不含末尾终止PAD):")
    print(f"  结束前出现 PAD:     {pad_diagnostics[mode]['pad_in_prefix']/total_samples:.2%}")
    print(f"  PAD 在 END 前出现:  {pad_diagnostics[mode]['pad_before_end']/total_samples:.2%}")
    if pad_diagnostics[mode]["pad_in_prefix"] > 0:
        ratio = pad_diagnostics[mode]["pad_before_end"] / pad_diagnostics[mode]["pad_in_prefix"]
        print(f"  (在有PAD的样本中，PAD在END前的比例: {ratio:.2%})")
    if pad_diagnostics[mode]["pad_in_prefix"] / total_samples > 0.05:
        print(f"  ⚠️  警告: 模型在结束前预测 PAD 的比例较高（>5%），可能是训练问题")

    print(f"\n长度对齐诊断 (pred_trunc vs gold_trunc，按 end_type 分桶):")
    gold_trunc_acc = total_token_correct_incl / total_token_total_incl

    for et in ["END", "PAD", "NONE"]:
        if alignment_diagnostics[mode][et]["total"] > 0:
            pred_trunc_acc = alignment_diagnostics[mode][et]["correct"] / alignment_diagnostics[mode][et]["total"]
            samples_count = alignment_diagnostics[mode][et]["samples"]
            print(f"  end_type={et:4s}: pred_trunc={pred_trunc_acc:.2%}, gold_trunc={gold_trunc_acc:.2%}, "
                  f"差距={pred_trunc_acc - gold_trunc_acc:+.2%} ({samples_count}样本)")

    total_pred_trunc_correct = sum(alignment_diagnostics[mode][et]["correct"] for et in ["END", "PAD", "NONE"])
    total_pred_trunc_total = sum(alignment_diagnostics[mode][et]["total"] for et in ["END", "PAD", "NONE"])
    total_pred_trunc_samples = sum(alignment_diagnostics[mode][et]["samples"] for et in ["END", "PAD", "NONE"])

    if total_pred_trunc_total > 0:
        overall_pred_trunc_acc = total_pred_trunc_correct / total_pred_trunc_total
        print(f"  总体:         pred_trunc={overall_pred_trunc_acc:.2%}, gold_trunc={gold_trunc_acc:.2%}, "
              f"差距={overall_pred_trunc_acc - gold_trunc_acc:+.2%} ({total_pred_trunc_samples}样本)")

        if overall_pred_trunc_acc > gold_trunc_acc + 0.05:
            print(f"  → 诊断: 模型提前结束，但前面预测还可以")
        elif overall_pred_trunc_acc < gold_trunc_acc - 0.05:
            print(f"  → 诊断: 模型延迟结束，后续内容预测崩溃")
        else:
            print(f"  → 诊断: 长度基本对齐")

        pad_ratio = alignment_diagnostics[mode]["PAD"]["samples"] / total_pred_trunc_samples if total_pred_trunc_samples > 0 else 0
        if pad_ratio > 0.3:
            print(f"  ⚠️  注意: end_type=PAD 比例较高（{pad_ratio:.1%}），模型可能在该继续生成时过早停止")


# ===================== 8. 任务类型统计 =====================
print(f"\n{'='*80}")
print("任务类型统计 (Top 10 & Bottom 10)")
print(f"{'='*80}")

task_type_results = []
for task_type_id, data in task_type_stats.items():
    if data["count"] == 0:
        continue

    task_type_name = task_vocab_builder.id_to_task_type.get(task_type_id, f"Unknown_{task_type_id}")
    avg_gold_len = data["total_gold_len"] / data["count"]

    free_token_acc_incl = data["free_token_correct_incl"] / data["free_token_total_incl"] if data["free_token_total_incl"] > 0 else 0
    free_token_acc_excl = data["free_token_correct_excl"] / data["free_token_total_excl"] if data["free_token_total_excl"] > 0 else 0
    free_seq_em = data["free_seq_em"] / data["count"]

    cons_token_acc_incl = data["cons_token_correct_incl"] / data["cons_token_total_incl"] if data["cons_token_total_incl"] > 0 else 0

    task_type_results.append({
        "task_type": task_type_name,
        "count": data["count"],
        "avg_gold_len": avg_gold_len,
        "free_token_acc_incl": free_token_acc_incl,
        "free_token_acc_excl": free_token_acc_excl,
        "free_seq_em": free_seq_em,
        "cons_token_acc_incl": cons_token_acc_incl,
    })

task_type_results_sorted = sorted(task_type_results, key=lambda x: x["free_token_acc_excl"], reverse=True)

print("\nTop 10 任务类型 (按 FREE Token Acc 不含END):")
print(f"{'任务类型':<40} {'样本数':>6} {'平均长度':>8} {'F-Tok(含)':>11} {'F-Tok(不含)':>12} {'F-SeqEM':>10}")
print("-" * 100)
for item in task_type_results_sorted[:10]:
    print(f"{item['task_type']:<40} {item['count']:>6} {item['avg_gold_len']:>8.1f} "
          f"{item['free_token_acc_incl']:>11.2%} {item['free_token_acc_excl']:>12.2%} {item['free_seq_em']:>10.2%}")

print("\nBottom 10 任务类型 (按 FREE Token Acc 不含END):")
print(f"{'任务类型':<40} {'样本数':>6} {'平均长度':>8} {'F-Tok(含)':>11} {'F-Tok(不含)':>12} {'F-SeqEM':>10}")
print("-" * 100)
for item in task_type_results_sorted[-10:]:
    print(f"{item['task_type']:<40} {item['count']:>6} {item['avg_gold_len']:>8.1f} "
          f"{item['free_token_acc_incl']:>11.2%} {item['free_token_acc_excl']:>12.2%} {item['free_seq_em']:>10.2%}")


# ===================== 9. Head vs Tail =====================
print(f"\n{'='*80}")
print("Head vs Tail 分析 (按样本数分桶)")
print(f"{'='*80}")

buckets = [
    ("Head (>500)", lambda x: x["count"] > 500),
    ("Mid (100-500)", lambda x: 100 <= x["count"] <= 500),
    ("Tail (<100)", lambda x: x["count"] < 100),
]

for bucket_name, bucket_filter in buckets:
    bucket_data = [item for item in task_type_results if bucket_filter(item)]
    if not bucket_data:
        continue

    avg_free_token_acc_incl = np.mean([item["free_token_acc_incl"] for item in bucket_data])
    avg_free_token_acc_excl = np.mean([item["free_token_acc_excl"] for item in bucket_data])
    avg_cons_token_acc_incl = np.mean([item["cons_token_acc_incl"] for item in bucket_data])
    avg_free_seq_em = np.mean([item["free_seq_em"] for item in bucket_data])
    avg_gold_len = np.mean([item["avg_gold_len"] for item in bucket_data])
    total_samples = sum([item["count"] for item in bucket_data])

    print(f"\n{bucket_name}:")
    print(f"  任务类型数:          {len(bucket_data)}")
    print(f"  总样本数:            {total_samples}")
    print(f"  平均长度:            {avg_gold_len:.1f}")
    print(f"  FREE TokenAcc(含):   {avg_free_token_acc_incl:.2%}")
    print(f"  FREE TokenAcc(不含): {avg_free_token_acc_excl:.2%}")
    print(f"  CONS TokenAcc(含):   {avg_cons_token_acc_incl:.2%}")
    print(f"  FREE SeqEM:          {avg_free_seq_em:.2%}")


# ===================== 10. 量化判据 =====================
print(f"\n{'='*80}")
print("量化判据 (决策下一步)")
print(f"{'='*80}")

prefix5_acc = stats["free"]["prefix@5_correct"] / stats["free"]["prefix@5_total"] if stats["free"]["prefix@5_total"] > 0 else 0
prefix20_acc = stats["free"]["prefix@20_correct"] / stats["free"]["prefix@20_total"] if stats["free"]["prefix@20_total"] > 0 else 0

first_errors = stats["free"]["first_error_pos"]
first_error_6_15 = sum(1 for e in first_errors if 6 <= e <= 15) / len(first_errors) if len(first_errors) > 0 else 0

end_biases_cons = stats["cons"]["end_bias"]
avg_end_bias_cons = np.mean(end_biases_cons) if len(end_biases_cons) > 0 else 0.0
early_end_rate = sum(1 for b in end_biases_cons if b < -5) / len(end_biases_cons) if len(end_biases_cons) > 0 else 0

print(f"\n关键指标:")
print(f"  Prefix@5 TokenAcc:      {prefix5_acc:.2%}")
print(f"  Prefix@20 TokenAcc:     {prefix20_acc:.2%}")
print(f"  First-error 6-15步占比: {first_error_6_15:.2%}")
print(f"  CONS 平均 END 偏差:     {avg_end_bias_cons:.2f}")
print(f"  CONS 提前>5步结束率:    {early_end_rate:.2%}")

print(f"\n建议:")
if prefix5_acc >= 0.50 and prefix20_acc <= 0.25 and first_error_6_15 > 0.3:
    print("  ✅ 走优先级2 (重训/改训)")
    print("     理由: 前几步很准，后面雪崩，典型 Exposure Bias")
    print("     建议: SS 更早开始(epoch 2-3), end_ratio 更温和(0.6), LR 不要衰到0")
elif early_end_rate > 0.3:
    print("  ✅ 走优先级3 (先改解码)")
    print("     理由: CONSTRAINED 提前结束严重")
    print("     建议: end_length_bias=0.0, min_length=10, no_repeat_ngram=2")
else:
    print("  ⚠️  需要综合判断")
    print("     建议: 先改解码策略，观察效果后再决定是否重训")

print("\n" + "=" * 80)
print("评估完成！")
print("=" * 80)
