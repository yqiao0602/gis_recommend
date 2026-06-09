# -*- coding: utf-8 -*-
"""
L3序列推理模块 - Beam Search + 约束解码（软长度先验 + 防短序列早停 + 可选多样性rerank）
+ ✅ 转移矩阵约束 beam（allowed_next hard mask）

你要的“转移矩阵约束 beam”已经完整嵌入：
- 读取 outputs/transition_allowed_next.json
- 在每一步扩展 beam 前，对不允许的 next token 直接 logits=-inf
- 支持 transition_min_count 过滤罕见转移
- 支持在长度下界前硬禁 END（避免短序列早停）
- 具备 fallback：如果 last_token 没有转移表或 allowed 为空，则不启用 mask（防死路）

可选文件：
  outputs/task_type_expected_length.json
  outputs/transition_allowed_next.json

注意：
- checkpoint 加载只接受包装式 payload 中的 model_state_dict，并始终 strict=True。
- allow_partial_load 参数仅为旧 API 兼容保留，不再改变加载行为。
"""

import json
import csv
import torch
import torch.nn.functional as F
from pathlib import Path
from dataclasses import dataclass
from typing import List, Optional, Dict, Any, Tuple
from transformers import BertTokenizer

from gis_recommend.config.transformer_config import (
    SPECIAL_TOKENS,
    VOCAB_SIZE,
    TOTAL_VOCAB_SIZE,
    OUTPUT_DIR,
    DEVICE,
    V4_MAX_MEMORY_TOKENS,
)
from gis_recommend.models.transformer_model_v3 import TaskConditionedL3TransformerModelV3
from gis_recommend.models.task_text_processor import TaskVocabularyBuilder

CHECKPOINT_SCHEMA = "gis_recommend.checkpoint.v1"


# ---------------------------
# Special Token IDs
# ---------------------------
SPECIAL_TOKEN_IDS = {
    name: VOCAB_SIZE + abs(token_id) - 1
    for name, token_id in SPECIAL_TOKENS.items()
}
PAD_TOKEN_ID = SPECIAL_TOKEN_IDS["<PAD>"]
UNK_TOKEN_ID = SPECIAL_TOKEN_IDS["<UNK>"]
START_TOKEN_ID = SPECIAL_TOKEN_IDS["<START>"]
END_TOKEN_ID = SPECIAL_TOKEN_IDS["<END>"]


def _resolve_project_root() -> Path:
    """Find the project root (directory containing 'outputs/')."""
    p = Path(__file__).resolve()
    for parent in [p.parent, p.parent.parent, p.parent.parent.parent,
                   p.parent.parent.parent.parent]:
        if (parent / "outputs").is_dir():
            return parent
    return p.parent


@dataclass
class L3Candidate:
    tokens: List[int]
    log_prob: float
    normalized_score: float
    length: int
    end_pos: int
    unk_count: int
    is_complete: bool
    task_expected_len: int = -1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tokens": self.tokens,
            "log_prob": self.log_prob,
            "normalized_score": self.normalized_score,
            "length": self.length,
            "end_pos": self.end_pos,
            "unk_count": self.unk_count,
            "is_complete": self.is_complete,
            "task_expected_len": self.task_expected_len,
        }


class BeamSearchState:
    def __init__(self, tokens: List[int], log_prob: float, finished: bool = False):
        self.tokens = tokens
        self.log_prob = log_prob
        self.finished = finished
        self.generated_tokens = tokens[1:]  # 不含START

    def score(self, length_penalty: float = 1.0) -> float:
        length = max(len(self.tokens), 1)
        return self.log_prob / (length ** length_penalty)


class L3SequenceInferencer:
    def __init__(
        self,
        checkpoint_path: Optional[Path] = None,
        device: torch.device = DEVICE,

        # Beam Search
        beam_size: int = 10,
        max_length: int = 50,
        length_penalty: float = 1.0,

        # 软长度先验（全局默认）
        expected_length: int = 9,
        length_margin: int = 2,
        early_end_penalty: float = 3.5,  # 对 log_probs 的惩罚
        late_end_bonus: float = 0.5,     # 对 log_probs 的奖励

        # 其他约束
        repetition_penalty: float = 1.2,
        no_repeat_ngram: int = 3,

        # 输出控制
        return_top_n: int = 10,

        # 多样性 rerank
        enable_diversity_rerank: bool = True,
        diversity_lambda: float = 0.35,

        # ✅ 转移矩阵约束
        enable_transition_constraint: bool = True,
        transition_path: Optional[Path] = None,
        transition_min_count: int = 1,

        # Deprecated compatibility parameter. It is ignored under the Phase 15C
        # execution contract: partial checkpoint loads are never runtime-safe.
        allow_partial_load: bool = False,
    ):
        self.device = device
        self.beam_size = beam_size
        self.max_length = max_length
        self.length_penalty = length_penalty

        self.global_expected_length = expected_length
        self.length_margin = length_margin
        self.early_end_penalty = early_end_penalty
        self.late_end_bonus = late_end_bonus

        self.repetition_penalty = repetition_penalty
        self.no_repeat_ngram = no_repeat_ngram
        self.return_top_n = return_top_n

        self.enable_diversity_rerank = enable_diversity_rerank
        self.diversity_lambda = diversity_lambda

        # transition constraint
        self.enable_transition_constraint = enable_transition_constraint
        self.transition_min_count = max(1, int(transition_min_count))
        self.allowed_next: Dict[int, Dict[int, int]] = {}

        if allow_partial_load:
            print("  [INFO] allow_partial_load is ignored; strict checkpoint loading is enforced")
        self.allow_partial_load = False

        self._load_model(checkpoint_path)
        self._load_vocab()
        self._load_expected_len_map()
        self._load_transition_matrix(transition_path)

    # ---------------------------
    # Model / Vocab
    # ---------------------------
    def _load_model(self, checkpoint_path: Optional[Path] = None):
        if checkpoint_path is None:
            checkpoint_path = OUTPUT_DIR / "task_conditioned_checkpoints_v3" / "best_model.pth"

        print(f"[Inferencer] 加载模型: {checkpoint_path}")

        task_vocab_path = OUTPUT_DIR / "task_type_vocabulary.json"
        with open(task_vocab_path, "r", encoding="utf-8") as f:
            task_type_vocab = json.load(f)

        checkpoint = torch.load(checkpoint_path, map_location=self.device, weights_only=True)
        if not isinstance(checkpoint, dict) or not isinstance(checkpoint.get("model_state_dict"), dict):
            raise KeyError("checkpoint must be a wrapped payload with model_state_dict")
        schema = checkpoint.get("checkpoint_schema")
        if schema is None:
            provenance = checkpoint.get("provenance") or {}
            schema = provenance.get("format_version")
        if schema != CHECKPOINT_SCHEMA:
            raise ValueError(f"Unsupported checkpoint schema/format_version: {schema!r}")
        max_mem = V4_MAX_MEMORY_TOKENS

        self.model = TaskConditionedL3TransformerModelV3(
            vocab_size=TOTAL_VOCAB_SIZE,
            num_task_types=task_type_vocab["num_types"],
            d_model=256,
            n_heads=8,
            n_layers=6,
            dim_feedforward=1024,
            dropout=0.0,
            max_seq_length=100,
            max_memory_tokens=max_mem,
            use_l3_embeddings=False,
            freeze_bert=True
        )

        weights = checkpoint["model_state_dict"]
        self.model.load_state_dict(weights, strict=True)
        print("  [OK] state_dict strict=True 完整加载，无 missing / unexpected keys")

        self.model = self.model.to(self.device)
        self.model.eval()
        print(f"[Inferencer] 模型加载完成，设备: {self.device}")

    def _load_vocab(self):
        task_vocab_path = OUTPUT_DIR / "task_type_vocabulary.json"
        with open(task_vocab_path, "r", encoding="utf-8") as f:
            task_type_vocab = json.load(f)

        self.task_vocab_builder = TaskVocabularyBuilder()
        # 兼容不同字段名
        if hasattr(self.task_vocab_builder, "type_to_id"):
            self.task_vocab_builder.type_to_id = task_type_vocab["task_type_to_id"]
        if hasattr(self.task_vocab_builder, "task_type_to_id"):
            self.task_vocab_builder.task_type_to_id = task_type_vocab["task_type_to_id"]

        id_to = {int(k): v for k, v in task_type_vocab["id_to_task_type"].items()}
        if hasattr(self.task_vocab_builder, "id_to_type"):
            self.task_vocab_builder.id_to_type = id_to
        if hasattr(self.task_vocab_builder, "id_to_task_type"):
            self.task_vocab_builder.id_to_task_type = id_to

        # id -> l3_code
        id_mappings_path = OUTPUT_DIR / "id_mappings.json"
        if id_mappings_path.exists():
            with open(id_mappings_path, "r", encoding="utf-8") as f:
                id_mappings = json.load(f)
            l3_mapping = id_mappings.get("l3", {})
            self.id_to_l3_code = {int(v): k for k, v in l3_mapping.items()}
        else:
            self.id_to_l3_code = {}

        # l3_code -> name/desc/l2_code（l2_code可选）
        # 你项目里路径可能不同，这里保留原逻辑
        hierarchy_path = _resolve_project_root() / "classification_hierarchy.csv"
        self.l3_code_to_name: Dict[str, str] = {}
        self.l3_code_to_desc: Dict[str, str] = {}
        self.l3_code_to_l2: Dict[str, str] = {}

        if hierarchy_path.exists():
            with open(hierarchy_path, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    code = (row.get("l3_code") or "").strip()
                    name = (row.get("l3_name") or "").strip()
                    desc = (row.get("l3_description") or "").strip()
                    l2_code = (row.get("l2_code") or "").strip()
                    if code:
                        self.l3_code_to_name[code] = name
                        self.l3_code_to_desc[code] = desc
                        if l2_code:
                            self.l3_code_to_l2[code] = l2_code
            print(f"  L3语义信息: {len(self.l3_code_to_name)} 条")
        else:
            print("  [Warn] 未找到 classification_hierarchy.csv（将无法显示L3名称/做L2多样性）")

        self.bert_tokenizer = BertTokenizer.from_pretrained("bert-base-uncased")

        print("[Inferencer] 词汇表加载完成")
        print(f"  任务类型数: {len(getattr(self.task_vocab_builder, 'type_to_id', {})) or len(getattr(self.task_vocab_builder, 'task_type_to_id', {}))}")
        print(f"  L3词汇数: {len(self.id_to_l3_code)}")

    def _load_expected_len_map(self):
        self.task_type_expected_len: Dict[str, int] = {}
        self.expected_len_json = OUTPUT_DIR / "task_type_expected_length.json"
        if self.expected_len_json.exists():
            try:
                with open(self.expected_len_json, "r", encoding="utf-8") as f:
                    data = json.load(f)
                self.global_expected_length = int(data.get("global_expected", self.global_expected_length))
                mapping = data.get("task_type_to_expected", {})
                for k, v in mapping.items():
                    try:
                        self.task_type_expected_len[str(k)] = int(v)
                    except Exception:
                        pass
                print(f"[Inferencer] 已加载 expected_length 映射: {len(self.task_type_expected_len)} 个 task_type")
                print(f"  global_expected = {self.global_expected_length}")
            except Exception as e:
                print(f"[Warn] 读取 {self.expected_len_json} 失败: {e}")
        else:
            print("[Inferencer] 未发现 task_type_expected_length.json，将使用全局 expected_length")

    # ---------------------------
    # ✅ Transition matrix loader
    # ---------------------------
    def _load_transition_matrix(self, transition_path: Optional[Path]):
        if not self.enable_transition_constraint:
            print("[Inferencer] 转移矩阵约束: OFF")
            return

        if transition_path is None:
            transition_path = OUTPUT_DIR / "transition_allowed_next.json"

        if not transition_path.exists():
            print(f"[Warn] 未找到转移矩阵文件: {transition_path}，转移约束将关闭")
            self.enable_transition_constraint = False
            return

        try:
            with open(transition_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            raw = data.get("allowed_next", {})

            loaded = 0
            for a_str, nxt in raw.items():
                a = int(a_str)
                # nxt: { b_str: count }
                filtered = {int(b): int(c) for b, c in nxt.items() if int(c) >= self.transition_min_count}
                if filtered:
                    self.allowed_next[a] = filtered
                    loaded += 1

            print(f"[Inferencer] 转移矩阵约束: ON | states={loaded} | file={transition_path}")
            if self.transition_min_count > 1:
                print(f"  transition_min_count={self.transition_min_count}")
        except Exception as e:
            print(f"[Warn] 读取转移矩阵失败: {e}，转移约束将关闭")
            self.enable_transition_constraint = False

    # ---------------------------
    # Text Encoding
    # ---------------------------
    def _encode_text(self, task_name: str, task_description: str) -> Dict[str, torch.Tensor]:
        combined_text = " ".join(filter(None, [task_name, task_description]))
        encoded = self.bert_tokenizer(
            combined_text,
            max_length=128,
            padding="max_length",
            truncation=True,
            return_tensors="pt"
        )
        return {
            "input_ids": encoded["input_ids"].to(self.device),
            "attention_mask": encoded["attention_mask"].to(self.device)
        }

    def _get_expected_length_for_task(self, task_type: str) -> int:
        return self.task_type_expected_len.get(task_type, self.global_expected_length)

    # ---------------------------
    # Constraints helpers
    # ---------------------------
    def _block_no_repeat_ngram(self, vec: torch.Tensor, generated_tokens: List[int]) -> None:
        n = self.no_repeat_ngram
        if n <= 0 or len(generated_tokens) < n - 1:
            return
        prefix = tuple(generated_tokens[-(n - 1):])
        for prev_start in range(len(generated_tokens) - n + 1):
            prev_ng = tuple(generated_tokens[prev_start: prev_start + n - 1])
            if prev_ng == prefix:
                blocked = generated_tokens[prev_start + n - 1]
                if blocked < vec.numel():
                    vec[blocked] = float("-inf")

    def _apply_hard_constraints_on_logits(
        self,
        logits: torch.Tensor,
        generated_tokens: List[int],
        force_end: bool,
        last_token: int,
        step: int,
        expected_length: int
    ) -> torch.Tensor:
        """
        logits: 当前step的logits向量（未softmax）
        last_token: 当前beam序列最后一个token（含START/中间token）
        step: 当前序列长度（含START），即 cur_step
        expected_length: 该任务期望长度（用于“下界前禁END”）
        """
        x = logits.clone()

        if force_end:
            x[:] = float("-inf")
            x[END_TOKEN_ID] = 0.0
            return x

        # ✅ 0) 转移矩阵硬约束（allowed_next mask）
        if self.enable_transition_constraint:
            nxt = self.allowed_next.get(int(last_token))
            if nxt:
                allowed = set(nxt.keys())

                # 在长度下界前硬禁 END（比 soft prior 更强）
                lower = max(expected_length - self.length_margin, 1)
                gen_len = max(step - 1, 0)  # 不含START的长度
                if gen_len < lower and END_TOKEN_ID in allowed:
                    allowed.remove(END_TOKEN_ID)

                # 保底：allowed为空则不mask（避免死路）
                if allowed:
                    mask = torch.full_like(x, float("-inf"))
                    idx = torch.tensor(list(allowed), device=x.device, dtype=torch.long)
                    mask[idx] = x[idx]
                    x = mask

        # 1) 禁用特殊token
        x[UNK_TOKEN_ID] = float("-inf")
        x[PAD_TOKEN_ID] = float("-inf")
        x[START_TOKEN_ID] = float("-inf")

        # 2) 禁连续重复（上一token不能立刻再来一次）
        if generated_tokens:
            last = generated_tokens[-1]
            if last < x.numel():
                x[last] = float("-inf")

        # 3) repetition penalty（logits近似）
        if self.repetition_penalty != 1.0 and generated_tokens:
            for tok in set(generated_tokens):
                if tok < x.numel() and x[tok] != float("-inf"):
                    if x[tok] > 0:
                        x[tok] /= self.repetition_penalty
                    else:
                        x[tok] *= self.repetition_penalty

        # 4) no_repeat_ngram
        self._block_no_repeat_ngram(x, generated_tokens)

        return x

    def _apply_soft_length_prior_on_logprobs(
        self,
        log_probs: torch.Tensor,
        step: int,
        expected_length: int
    ) -> torch.Tensor:
        lp = log_probs.clone()

        lower = max(expected_length - self.length_margin, 1)
        upper = expected_length + self.length_margin

        # gen_len：已生成 L3 token 数（不含START）
        gen_len = max(step - 1, 0)

        if gen_len < lower:
            penalty = (lower - gen_len) * self.early_end_penalty
            lp[END_TOKEN_ID] -= penalty
        elif gen_len > upper:
            bonus = (gen_len - upper) * self.late_end_bonus
            lp[END_TOKEN_ID] += bonus

        return lp

    # ---------------------------
    # Beam Search
    # ---------------------------
    def beam_search(
        self,
        task_type_id: int,
        text_input_ids: torch.Tensor,
        text_attention_mask: torch.Tensor,
        expected_length: int
    ) -> List[L3Candidate]:
        with torch.no_grad():
            beams = [BeamSearchState(tokens=[START_TOKEN_ID], log_prob=0.0)]
            completed: List[BeamSearchState] = []

            task_type_ids = torch.tensor([task_type_id], dtype=torch.long, device=self.device)

            lower_bound = max(expected_length - self.length_margin, 1)

            for outer_step in range(1, self.max_length):
                if not beams:
                    break

                all_candidates: List[BeamSearchState] = []

                for beam in beams:
                    if beam.finished:
                        completed.append(beam)
                        continue

                    input_len = len(beam.tokens)
                    input_ids = torch.full((1, self.max_length), PAD_TOKEN_ID, dtype=torch.long, device=self.device)
                    input_ids[0, :input_len] = torch.tensor(beam.tokens, dtype=torch.long, device=self.device)

                    attention_mask = torch.zeros((1, self.max_length), dtype=torch.bool, device=self.device)
                    attention_mask[0, :input_len] = True

                    logits = self.model(
                        input_ids,
                        task_type_ids,
                        text_input_ids,
                        text_attention_mask,
                        attention_mask=attention_mask,
                        return_task_logits=False
                    )

                    step_logits = logits[0, input_len - 1]
                    cur_step = input_len  # 当前beam长度（含START）

                    force_end = (cur_step >= self.max_length - 1)

                    # hard constraints on logits（✅ 加了 last_token/step/expected_length）
                    step_logits = self._apply_hard_constraints_on_logits(
                        logits=step_logits,
                        generated_tokens=beam.generated_tokens,
                        force_end=force_end,
                        last_token=beam.tokens[-1],
                        step=cur_step,
                        expected_length=expected_length
                    )

                    # logits -> log_probs
                    log_probs = F.log_softmax(step_logits, dim=-1)

                    # soft length prior on log_probs
                    log_probs = self._apply_soft_length_prior_on_logprobs(
                        log_probs, step=cur_step, expected_length=expected_length
                    )

                    topk_log_probs, topk_indices = log_probs.topk(self.beam_size * 2)

                    for log_p, token_id in zip(topk_log_probs.tolist(), topk_indices.tolist()):
                        if log_p == float("-inf"):
                            continue
                        new_tokens = beam.tokens + [token_id]
                        new_log_prob = beam.log_prob + log_p
                        finished = (token_id == END_TOKEN_ID)
                        all_candidates.append(BeamSearchState(new_tokens, new_log_prob, finished))

                all_candidates.sort(key=lambda x: x.score(self.length_penalty), reverse=True)

                beams = []
                for cand in all_candidates:
                    if cand.finished:
                        completed.append(cand)
                    else:
                        if len(beams) < self.beam_size:
                            beams.append(cand)

                # 防短序列早停：必须 outer_step >= lower_bound 才允许 break
                if len(completed) >= self.return_top_n * 2 and outer_step >= lower_bound:
                    break

            completed.extend(beams)

            finished = [b for b in completed if b.finished]
            unfinished = [b for b in completed if not b.finished]
            finished.sort(key=lambda x: x.score(self.length_penalty), reverse=True)
            unfinished.sort(key=lambda x: x.score(self.length_penalty), reverse=True)

            picked = finished[:self.return_top_n]
            if len(picked) < self.return_top_n:
                picked += unfinished[: (self.return_top_n - len(picked))]

            candidates: List[L3Candidate] = []
            for beam in picked:
                tokens = beam.tokens[1:]  # 去掉START
                end_pos = len(tokens)
                if END_TOKEN_ID in tokens:
                    end_pos = tokens.index(END_TOKEN_ID)
                    tokens = tokens[:end_pos]
                unk_count = sum(1 for t in tokens if t == UNK_TOKEN_ID)

                candidates.append(
                    L3Candidate(
                        tokens=tokens,
                        log_prob=beam.log_prob,
                        normalized_score=beam.score(self.length_penalty),
                        length=len(tokens),
                        end_pos=end_pos,
                        unk_count=unk_count,
                        is_complete=beam.finished,
                        task_expected_len=expected_length
                    )
                )

            if self.enable_diversity_rerank and len(candidates) > 1:
                candidates = self._diversity_rerank(candidates)

            return candidates

    # ---------------------------
    # Decoding / Diversity rerank
    # ---------------------------
    def decode_tokens(self, tokens: List[int], use_name: bool = True) -> List[str]:
        out = []
        for t in tokens:
            if t in self.id_to_l3_code:
                code = self.id_to_l3_code[t]
                if use_name and code in self.l3_code_to_name:
                    out.append(self.l3_code_to_name[code])
                else:
                    out.append(code)
            elif t == UNK_TOKEN_ID:
                out.append("<UNK>")
            elif t == PAD_TOKEN_ID:
                out.append("<PAD>")
            elif t == START_TOKEN_ID:
                out.append("<START>")
            elif t == END_TOKEN_ID:
                out.append("<END>")
            else:
                out.append(f"[{t}]")
        return out

    def _l3_family_key(self, token_id: int) -> str:
        code = self.id_to_l3_code.get(token_id, "")
        if not code:
            return f"ID_{token_id}"

        l2 = self.l3_code_to_l2.get(code)
        if l2:
            return l2

        parts = code.split("_")
        if len(parts) >= 3:
            return "_".join(parts[:3])
        return code

    def _diversity_rerank(self, candidates: List[L3Candidate]) -> List[L3Candidate]:
        def diversity_penalty(tokens: List[int]) -> float:
            counts: Dict[str, int] = {}
            for tid in tokens:
                fam = self._l3_family_key(tid)
                counts[fam] = counts.get(fam, 0) + 1
            dup = sum(max(0, c - 1) for c in counts.values())
            return float(dup)

        scored: List[Tuple[float, L3Candidate]] = []
        for c in candidates:
            dup = diversity_penalty(c.tokens)
            new_score = c.normalized_score - self.diversity_lambda * dup
            scored.append((new_score, c))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [c for _, c in scored]

    # ---------------------------
    # Public API
    # ---------------------------
    def infer(self, task_name: str, task_description: str = "", task_type: str = "Unknown") -> List[L3Candidate]:
        type_to_id = getattr(self.task_vocab_builder, "type_to_id", None) or getattr(self.task_vocab_builder, "task_type_to_id", {})
        if task_type not in type_to_id:
            print(f"[Warn] task_type='{task_type}' 不在词表中，将使用 Unknown")
            task_type = "Unknown"

        task_type_id = self.task_vocab_builder.encode(task_type)
        expected_length = self._get_expected_length_for_task(task_type)

        text_encoded = self._encode_text(task_name, task_description)

        return self.beam_search(
            task_type_id=task_type_id,
            text_input_ids=text_encoded["input_ids"],
            text_attention_mask=text_encoded["attention_mask"],
            expected_length=expected_length
        )

    def infer_from_model_input(
        self,
        model_input: Dict[str, torch.Tensor],
        task_type: Optional[str] = None
    ) -> List[L3Candidate]:
        """
        直接使用LLM入口产生的model_input进行推理（避免重复编码）

        Args:
            model_input: {
                "task_type_id": Tensor([id]),
                "text_input_ids": Tensor([1, seq_len]),
                "text_attention_mask": Tensor([1, seq_len])
            }
            task_type: 可选，若提供则用于期望长度先验
        """
        task_type_id = int(model_input["task_type_id"].item())
        expected_length = self._get_expected_length_for_task(task_type) if task_type else self.global_expected_length

        text_input_ids = model_input["text_input_ids"].to(self.device)
        text_attention_mask = model_input["text_attention_mask"].to(self.device)

        return self.beam_search(
            task_type_id=task_type_id,
            text_input_ids=text_input_ids,
            text_attention_mask=text_attention_mask,
            expected_length=expected_length
        )

    def infer_and_print(self, task_name: str, task_description: str = "", task_type: str = "Unknown"):
        print("\n" + "=" * 70)
        print(f"任务: {task_name}")
        print(f"描述: {task_description}")
        print(f"类型: {task_type}")
        print("=" * 70)

        cands = self.infer(task_name, task_description, task_type)

        print(f"\nTop-{len(cands)} L3序列候选:")
        print("-" * 70)

        for i, c in enumerate(cands):
            names = self.decode_tokens(c.tokens, use_name=True)
            codes = self.decode_tokens(c.tokens, use_name=False)
            status = "[OK]" if c.is_complete else "[...]"
            print(
                f"\n[{i+1}] Score: {c.normalized_score:.4f} | "
                f"LogP: {c.log_prob:.2f} | Len: {c.length} | ExpLen: {c.task_expected_len} | {status}"
            )
            print(f"    IDs:   {c.tokens}")
            print(f"    Codes: {' → '.join(codes)}")
            print(f"    Names: {' → '.join(names)}")

        print("\n" + "=" * 70)
        return cands


def main():
    print("=" * 70)
    print("L3序列推理测试 (Beam + 软长度先验 + 防早停 + 多样性rerank + ✅转移矩阵约束)")
    print("=" * 70)

    inferencer = L3SequenceInferencer(
        beam_size=10,
        max_length=50,
        length_penalty=1.0,
        expected_length=9,
        length_margin=2,
        early_end_penalty=3.5,
        late_end_bonus=0.5,
        no_repeat_ngram=3,
        repetition_penalty=1.2,
        return_top_n=5,
        enable_diversity_rerank=True,
        diversity_lambda=0.35,

        # ✅ 转移矩阵
        enable_transition_constraint=True,
        transition_path=None,        # 默认 outputs/transition_allowed_next.json
        transition_min_count=1,      # 先别收紧；想更“保守”再调到2/3

        allow_partial_load=False,    # deprecated no-op; loader is always strict
    )

    test_cases = [
        {
            "task_name": "Land cover classification",
            "task_description": "Classify land use and land cover from satellite imagery",
            "task_type": "Land use/land cover"
        },
        {
            "task_name": "NDVI calculation",
            "task_description": "Calculate normalized difference vegetation index from Landsat bands",
            "task_type": "Vegetation"
        },
        {
            "task_name": "Water body extraction",
            "task_description": "Extract surface water bodies from Sentinel-2 imagery",
            "task_type": "Surface water"
        }
    ]

    for case in test_cases:
        inferencer.infer_and_print(**case)

    print("\n推理测试完成！")


if __name__ == "__main__":
    main()
