# -*- coding: utf-8 -*-
"""
infer_task_conditioned_v3.py

任务条件化 L3 Transformer 推理脚本（对比三种解码）：

1) [FREE greedy]            不加约束
2) [CONS greedy]            你的原始约束（min_len / repetition / no_repeat_ngram / end_length_bias）
3) [CONS beam + TRANS]      ✅ import infer_l3_candidates.L3SequenceInferencer
                            启用“转移矩阵约束 beam”（allowed_next hard mask）
                            + soft length prior + 防短序列早停 + 可选 diversity rerank

运行示例：
python infer_task_conditioned_v3.py \
  --checkpoint outputs/task_conditioned_checkpoints_v3_7_final/best_model.pth \
  --task_type "Waterbody Extraction" \
  --task_name "Extract water bodies" \
  --task_desc "Detect water from satellite imagery and export polygons" \
  --max_len 60 \
  --beam 10 \
  --decode_min_len 10 \
  --end_length_bias 0.0 \
  --enable_transition \
  --transition_min_count 1 \
  --allow_partial_load
"""

import argparse
import json
from pathlib import Path
from typing import Dict, List, Tuple

import torch
from transformers import BertTokenizer

from gis_recommend.config.transformer_config import OUTPUT_DIR, DEVICE, SPECIAL_TOKENS, TOTAL_VOCAB_SIZE, VOCAB_SIZE
from gis_recommend.models.transformer_model_v3 import TaskConditionedL3TransformerModelV3
from gis_recommend.models.task_text_processor import TaskVocabularyBuilder

# ✅ 关键：引入你新写的推理模块（转移矩阵约束beam在里面）
from gis_recommend.inference.infer_l3_candidates import L3SequenceInferencer


# -------------------------
# Special token ids (正数空间)
# -------------------------
SPECIAL_TOKEN_IDS = {name: VOCAB_SIZE + abs(token_id) - 1 for name, token_id in SPECIAL_TOKENS.items()}
PAD_ID = SPECIAL_TOKEN_IDS["<PAD>"]
UNK_ID = SPECIAL_TOKEN_IDS["<UNK>"]
START_ID = SPECIAL_TOKEN_IDS["<START>"]
END_ID = SPECIAL_TOKEN_IDS["<END>"]


def load_task_type_vocab(vocab_path: Path) -> Tuple[TaskVocabularyBuilder, dict]:
    with open(vocab_path, "r", encoding="utf-8") as f:
        vocab = json.load(f)

    builder = TaskVocabularyBuilder()
    if hasattr(builder, "task_type_to_id"):
        builder.task_type_to_id = vocab["task_type_to_id"]
    if hasattr(builder, "type_to_id"):
        builder.type_to_id = vocab["task_type_to_id"]

    id_to = {int(k): v for k, v in vocab["id_to_task_type"].items()}
    if hasattr(builder, "id_to_task_type"):
        builder.id_to_task_type = id_to
    if hasattr(builder, "id_to_type"):
        builder.id_to_type = id_to

    return builder, vocab


def try_load_l3_id_to_name(output_dir: Path) -> Dict[int, str]:
    """
    尽力在 outputs 里找一个 “id->name/code” 的映射文件。
    找不到就返回空 dict，推理时会降级显示 L3_<id>.
    """
    candidates = [
        output_dir / "l3_id_to_name.json",
        output_dir / "l3_token_id_to_name.json",
        output_dir / "l3_vocab.json",
        output_dir / "l3_vocabulary.json",
        output_dir / "l3_codebook.json",
        output_dir / "l3_mapping.json",
        output_dir / "id_mappings.json",  # 你项目里常见：{"l3": {"L3_xx": id}}
    ]
    for p in candidates:
        if not p.exists():
            continue
        try:
            with open(p, "r", encoding="utf-8") as f:
                obj = json.load(f)

            # 情况A：{ "id_to_name": {"0": "..."} }
            if isinstance(obj, dict) and "id_to_name" in obj and isinstance(obj["id_to_name"], dict):
                return {int(k): str(v) for k, v in obj["id_to_name"].items()}

            # 情况B：直接 { "0": "RasterClip", ... }
            if isinstance(obj, dict):
                numeric_keys = 0
                for k in obj.keys():
                    try:
                        int(k)
                        numeric_keys += 1
                    except Exception:
                        pass
                if numeric_keys >= max(5, len(obj) // 4):
                    return {int(k): str(v) for k, v in obj.items() if str(k).lstrip("-").isdigit()}

            # 情况C：id_mappings.json：{"l3": {"L3_123": 10, ...}}
            if isinstance(obj, dict) and "l3" in obj and isinstance(obj["l3"], dict):
                # 这里没有“name”，只有code，先把 code 当 name 用（至少能显示 L3_code）
                inv = {int(v): str(k) for k, v in obj["l3"].items()}
                if len(inv) > 0:
                    return inv

        except Exception:
            pass
    return {}


def ids_to_l3_names(ids: List[int], id_to_name: Dict[int, str]) -> List[str]:
    names = []
    for tid in ids:
        if tid in (PAD_ID, UNK_ID, START_ID, END_ID):
            if tid == PAD_ID:
                names.append("<PAD>")
            elif tid == UNK_ID:
                names.append("<UNK>")
            elif tid == START_ID:
                names.append("<START>")
            else:
                names.append("<END>")
            continue

        if tid in id_to_name:
            names.append(id_to_name[tid])
        else:
            names.append(f"L3_{tid}")
    return names


def build_text_inputs(tokenizer: BertTokenizer, task_name: str, task_desc: str, max_text_len: int = 128):
    text = " ".join([x.strip() for x in [task_name or "", task_desc or ""] if x and x.strip()])
    enc = tokenizer(
        text,
        max_length=max_text_len,
        padding="max_length",
        truncation=True,
        return_tensors="pt"
    )
    return enc["input_ids"].squeeze(0), enc["attention_mask"].squeeze(0)


def apply_constraints_to_logits(
    logits: torch.Tensor,
    generated_tokens: List[int],
    step: int,
    min_len: int,
    repetition_penalty: float,
    no_repeat_ngram: int,
    end_length_bias: float,
) -> torch.Tensor:
    """
    你的原始约束：不包含“转移矩阵约束”，用于和 TRANS-beam 做对比
    """
    logits = logits.clone()
    logits[UNK_ID] = float("-inf")
    logits[PAD_ID] = float("-inf")
    logits[START_ID] = float("-inf")
    if step < min_len:
        logits[END_ID] = float("-inf")

    # repetition penalty
    if repetition_penalty != 1.0 and len(generated_tokens) > 0:
        for tok in set(generated_tokens):
            if 0 <= tok < logits.numel() and logits[tok] != float("-inf"):
                if logits[tok] > 0:
                    logits[tok] /= repetition_penalty
                else:
                    logits[tok] *= repetition_penalty

    # no_repeat_ngram
    if no_repeat_ngram and no_repeat_ngram > 0 and len(generated_tokens) >= no_repeat_ngram - 1:
        prefix = tuple(generated_tokens[-(no_repeat_ngram - 1):])
        for i in range(len(generated_tokens) - no_repeat_ngram + 1):
            prev_prefix = tuple(generated_tokens[i:i + no_repeat_ngram - 1])
            if prev_prefix == prefix:
                blocked = generated_tokens[i + no_repeat_ngram - 1]
                if 0 <= blocked < logits.numel():
                    logits[blocked] = float("-inf")

    # end bias
    if step >= min_len and end_length_bias and end_length_bias > 0:
        logits[END_ID] += (step - min_len) * end_length_bias

    return logits


@torch.no_grad()
def greedy_decode(
    model,
    task_type_id: int,
    text_input_ids: torch.Tensor,
    text_attention_mask: torch.Tensor,
    max_len: int,
    use_constraints: bool,
    min_len: int,
    repetition_penalty: float,
    no_repeat_ngram: int,
    end_length_bias: float,
    device: torch.device,
) -> List[int]:
    """
    返回：包含 START 和（可能包含）END 的 token ids
    """
    task_type_ids = torch.tensor([task_type_id], dtype=torch.long, device=device)
    text_input_ids = text_input_ids.to(device).unsqueeze(0)
    text_attention_mask = text_attention_mask.to(device).unsqueeze(0)

    generated = [START_ID]
    history = []  # 不含 START

    for step in range(1, max_len):
        input_ids = torch.full((1, max_len), PAD_ID, dtype=torch.long, device=device)
        attn = torch.zeros((1, max_len), dtype=torch.long, device=device)
        input_ids[0, :len(generated)] = torch.tensor(generated, dtype=torch.long, device=device)
        attn[0, :len(generated)] = 1

        logits = model(
            input_ids,
            task_type_ids,
            text_input_ids,
            text_attention_mask,
            attention_mask=attn,
            return_task_logits=False
        )
        step_logits = logits[0, step - 1, :]

        if use_constraints:
            step_logits = apply_constraints_to_logits(
                step_logits, history, step, min_len,
                repetition_penalty, no_repeat_ngram, end_length_bias
            )

        next_id = int(torch.argmax(step_logits).item())
        generated.append(next_id)
        history.append(next_id)

        if next_id == END_ID:
            break

    return generated


def pretty_ids(seq: List[int]) -> str:
    out = []
    for t in seq:
        out.append(t)
        if t == END_ID:
            break
    return " ".join(map(str, out))


def pretty_names(seq: List[int], id_to_name: Dict[int, str]) -> str:
    out = []
    for t in seq:
        out.append(t)
        if t == END_ID:
            break
    return " -> ".join(ids_to_l3_names(out, id_to_name))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", type=str, required=True, help="best_model.pth 路径")
    ap.add_argument("--task_type", type=str, default="Unknown", help="任务类型（必须在 task_type_vocabulary.json 中）")
    ap.add_argument("--task_name", type=str, default="", help="任务名称")
    ap.add_argument("--task_desc", type=str, default="", help="任务描述")
    ap.add_argument("--max_len", type=int, default=60, help="最大生成长度（含 START）")
    ap.add_argument("--max_text_len", type=int, default=128)

    # beam / 输出
    ap.add_argument("--beam", type=int, default=10)
    ap.add_argument("--top_n", type=int, default=1, help="TRANS beam 输出前N条候选（默认只取第1条用于对比）")

    # greedy约束参数（你原逻辑）
    ap.add_argument("--decode_min_len", type=int, default=10)
    ap.add_argument("--repetition_penalty", type=float, default=1.2)
    ap.add_argument("--no_repeat_ngram", type=int, default=3)
    ap.add_argument("--end_length_bias", type=float, default=0.0, help="建议先 0，避免过早结束")

    # ✅ TRANS beam 相关（走 L3SequenceInferencer）
    ap.add_argument("--enable_transition", action="store_true", help="启用转移矩阵约束beam")
    ap.add_argument("--transition_path", type=str, default="", help="默认 outputs/transition_allowed_next.json")
    ap.add_argument("--transition_min_count", type=int, default=1)
    ap.add_argument("--expected_length", type=int, default=9)
    ap.add_argument("--length_margin", type=int, default=2)
    ap.add_argument("--early_end_penalty", type=float, default=3.5)
    ap.add_argument("--late_end_bonus", type=float, default=0.5)
    ap.add_argument("--enable_diversity_rerank", action="store_true")
    ap.add_argument("--diversity_lambda", type=float, default=0.35)

    # checkpoint加载兼容
    ap.add_argument("--allow_partial_load", action="store_true", help="strict=False 兼容加载（遇到 missing/unexpected keys 就开）")

    args = ap.parse_args()

    ckpt = Path(args.checkpoint)
    if not ckpt.exists():
        raise FileNotFoundError(f"checkpoint not found: {ckpt}")

    # vocab / tokenizer
    task_vocab_builder, task_vocab = load_task_type_vocab(OUTPUT_DIR / "task_type_vocabulary.json")
    tokenizer = BertTokenizer.from_pretrained("bert-base-uncased")

    # task type id
    type_to_id = getattr(task_vocab_builder, "type_to_id", None) or getattr(task_vocab_builder, "task_type_to_id", {})
    if args.task_type not in type_to_id:
        task_type_id = task_vocab_builder.encode("Unknown")
        task_type = "Unknown"
    else:
        task_type_id = task_vocab_builder.encode(args.task_type)
        task_type = args.task_type

    # optional L3 mapping
    id_to_name = try_load_l3_id_to_name(OUTPUT_DIR)

    # text inputs
    text_ids, text_mask = build_text_inputs(tokenizer, args.task_name, args.task_desc, args.max_text_len)

    print("=" * 80)
    print("Task Conditioned L3 Inference (v3) - 3 modes compare")
    print(f"  Device: {DEVICE}")
    print(f"  Checkpoint: {ckpt}")
    print(f"  TaskType: {task_type} (id={task_type_id})")
    print(f"  Text: {args.task_name} | {args.task_desc}")
    print("=" * 80)

    # ------------------------------------------------------------------
    # ✅ 模型：FREE greedy / CONS greedy 也用“推理模块同款配置”的模型，避免结构不一致
    #    这里直接用 L3SequenceInferencer 内部加载的 model 来做 greedy
    # ------------------------------------------------------------------
    inferencer_for_model = L3SequenceInferencer(
        checkpoint_path=ckpt,
        beam_size=args.beam,
        max_length=args.max_len,
        length_penalty=1.0,
        expected_length=args.expected_length,
        length_margin=args.length_margin,
        early_end_penalty=args.early_end_penalty,
        late_end_bonus=args.late_end_bonus,
        repetition_penalty=args.repetition_penalty,
        no_repeat_ngram=args.no_repeat_ngram,
        return_top_n=max(args.top_n, 10),
        enable_diversity_rerank=args.enable_diversity_rerank,
        diversity_lambda=args.diversity_lambda,
        enable_transition_constraint=args.enable_transition,
        transition_path=(Path(args.transition_path) if args.transition_path.strip() else None),
        transition_min_count=args.transition_min_count,
        allow_partial_load=args.allow_partial_load,
    )

    model = inferencer_for_model.model  # ✅ 同款模型
    model.eval()

    # 1) free greedy
    free = greedy_decode(
        model, task_type_id, text_ids, text_mask,
        max_len=args.max_len,
        use_constraints=False,
        min_len=args.decode_min_len,
        repetition_penalty=args.repetition_penalty,
        no_repeat_ngram=args.no_repeat_ngram,
        end_length_bias=args.end_length_bias,
        device=DEVICE
    )

    # 2) constrained greedy（你的原约束）
    cons_g = greedy_decode(
        model, task_type_id, text_ids, text_mask,
        max_len=args.max_len,
        use_constraints=True,
        min_len=args.decode_min_len,
        repetition_penalty=args.repetition_penalty,
        no_repeat_ngram=args.no_repeat_ngram,
        end_length_bias=args.end_length_bias,
        device=DEVICE
    )

    # 3) constrained beam + transition constraint（走 inferencer）
    cons_beam_seq = [START_ID]
    cons_beam_all = []
    if args.enable_transition:
        cands = inferencer_for_model.infer(
            task_name=args.task_name,
            task_description=args.task_desc,
            task_type=task_type
        )
        cons_beam_all = cands[:max(1, args.top_n)]
        # 取第一条用于对比展示（跟你原输出结构一致）
        best = cons_beam_all[0]
        cons_beam_seq = [START_ID] + best.tokens + ([END_ID] if best.is_complete else [])
    else:
        # 如果你没开 enable_transition，就仍然用 inferencer 的 beam（无转移mask也能跑）
        cands = inferencer_for_model.infer(
            task_name=args.task_name,
            task_description=args.task_desc,
            task_type=task_type
        )
        cons_beam_all = cands[:max(1, args.top_n)]
        best = cons_beam_all[0]
        cons_beam_seq = [START_ID] + best.tokens + ([END_ID] if best.is_complete else [])

    print("\n[FREE greedy]")
    print("ids :", pretty_ids(free))
    print("l3  :", pretty_names(free, id_to_name))

    print("\n[CONS greedy]")
    print("ids :", pretty_ids(cons_g))
    print("l3  :", pretty_names(cons_g, id_to_name))

    print("\n[CONS beam{}]".format(" + TRANS" if args.enable_transition else ""))
    print("ids :", pretty_ids(cons_beam_seq))
    print("l3  :", pretty_names(cons_beam_seq, id_to_name))

    # 如果需要输出更多beam候选
    if args.top_n and args.top_n > 1:
        print("\n[Top-{} beam candidates]".format(args.top_n))
        for i, c in enumerate(cons_beam_all, 1):
            seq = [START_ID] + c.tokens + ([END_ID] if c.is_complete else [])
            print(f"  ({i}) score={c.normalized_score:.4f} len={c.length} complete={c.is_complete}")
            print("      ids:", pretty_ids(seq))
            print("      l3 :", pretty_names(seq, id_to_name))

    print("\nTips:")
    print("- greedy 容易一步错全错：优先看 beam 输出")
    print("- 若 CONS greedy 太短：提高 --decode_min_len (12/15)，并保持 --end_length_bias 先为 0")
    print("- TRANS-beam 想更“保守”：把 --transition_min_count 调到 2/3（会更贴训练分布，但可能更死板）")
    print("=" * 80)


if __name__ == "__main__":
    main()
