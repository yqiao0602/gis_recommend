# -*- coding: utf-8 -*-
"""
V4 L3序列推理模块 —— Diverse Beam Search + Temperature Sampling + 多因子候选评分

核心改进（相对V3）：
1. Group Diverse Beam Search（组间Hamming多样性惩罚）
2. Temperature Sampling + Top-p（核采样）
3. 多因子候选评分与排序

使用示例：
    from infer_l3_candidates_v4 import L3SequenceInferencerV4
    inferencer = L3SequenceInferencerV4()
    candidates = inferencer.infer(
        task_name="Land cover classification",
        task_description="Classify land use from satellite imagery",
        task_type="Land use/land cover"
    )
"""

import json
import csv
import math
import torch
import torch.nn.functional as F
from pathlib import Path
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any, Tuple, Set
from transformers import BertTokenizer

from gis_recommend.config.transformer_config import (
    SPECIAL_TOKENS, VOCAB_SIZE, TOTAL_VOCAB_SIZE, OUTPUT_DIR, DEVICE,
    V4_NUM_BEAM_GROUPS, V4_BEAMS_PER_GROUP, V4_DIVERSITY_LAMBDA,
    V4_RETURN_TOP_N, V4_SAMPLING_TEMPERATURE, V4_SAMPLING_TOP_P,
    V4_NUM_SAMPLES, V4_SCORE_LOG_PROB_WEIGHT, V4_SCORE_TRANSITION_WEIGHT,
    V4_SCORE_LENGTH_WEIGHT, V4_SCORE_DIVERSITY_WEIGHT,
    V4_D_MODEL, V4_N_HEADS, V4_N_LAYERS, V4_D_FF, V4_DROPOUT,
    V4_MAX_SEQ_LENGTH, V4_MAX_MEMORY_TOKENS, V4_BERT_UNFREEZE_LAYERS,
    V4_TRANSFORMER_CHECKPOINT_DIR, V4_TASK_TYPE_VOCAB_PATH,
    L3_EMBEDDINGS_PATH,
)
from gis_recommend.models.transformer_model_v4 import TaskConditionedL3TransformerModelV4
from gis_recommend.models.task_text_processor import TaskVocabularyBuilder

# Special token IDs
SPECIAL_TOKEN_MAP = {v: VOCAB_SIZE + abs(v) - 1 for v in SPECIAL_TOKENS.values()}
PAD_INDEX = SPECIAL_TOKEN_MAP[-1]   # 350
UNK_INDEX = SPECIAL_TOKEN_MAP[-2]   # 351
START_INDEX = SPECIAL_TOKEN_MAP[-3]  # 352
END_INDEX = SPECIAL_TOKEN_MAP[-4]   # 353


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
    """A candidate L3 sequence with scoring metadata."""
    tokens: List[int]
    log_prob: float
    length: int
    is_complete: bool
    final_score: float = 0.0
    transition_score: float = 0.0
    length_score: float = 0.0
    diversity_score: float = 0.0

    @property
    def normalized_score(self) -> float:
        """Alias for final_score, for compatibility with V3 API."""
        return self.final_score

    def to_dict(self) -> Dict[str, Any]:
        return {
            'tokens': self.tokens,
            'log_prob': self.log_prob,
            'length': self.length,
            'is_complete': self.is_complete,
            'final_score': self.final_score,
            'transition_score': self.transition_score,
            'length_score': self.length_score,
        }


class L3SequenceInferencerV4:
    """V4 inference engine with Diverse Beam Search and Temperature Sampling."""

    def __init__(
        self,
        checkpoint_path: Optional[Path] = None,
        device: torch.device = DEVICE,
        num_beam_groups: int = V4_NUM_BEAM_GROUPS,
        beams_per_group: int = V4_BEAMS_PER_GROUP,
        diversity_lambda: float = V4_DIVERSITY_LAMBDA,
        return_top_n: int = V4_RETURN_TOP_N,
        sampling_temperature: float = V4_SAMPLING_TEMPERATURE,
        sampling_top_p: float = V4_SAMPLING_TOP_P,
        num_samples: int = V4_NUM_SAMPLES,
        max_length: int = 25,
        min_length: int = 5,
        repetition_penalty: float = 1.2,
        no_repeat_ngram: int = 3,
    ):
        self.device = device
        self.num_beam_groups = num_beam_groups
        self.beams_per_group = beams_per_group
        self.diversity_lambda = diversity_lambda
        self.return_top_n = return_top_n
        self.sampling_temperature = sampling_temperature
        self.sampling_top_p = sampling_top_p
        self.num_samples = num_samples
        self.max_length = max_length
        self.min_length = min_length
        self.repetition_penalty = repetition_penalty
        self.no_repeat_ngram = no_repeat_ngram

        self.allowed_next: Dict[int, Set[int]] = {}
        self.id_to_l3_code: Dict[int, str] = {}
        self.l3_code_to_name: Dict[str, str] = {}
        self.l3_code_to_l2: Dict[str, str] = {}
        self.expected_length = 8
        self._length_stats = self._load_length_stats()

        self._load_model(checkpoint_path)
        self._load_vocab()
        self._load_transition_matrix()

    def _load_length_stats(self) -> dict:
        """Load pre-computed per-task-type length stats."""
        from gis_recommend.config.transformer_config import OUTPUT_DIR
        path = OUTPUT_DIR / "task_type_length_stats.json"
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            print(f"  [OK] Length stats loaded ({len(data.get('by_task_type', {}))} task types)")
            return data
        print(f"  [INFO] No length stats file found, using default expected_length=12")
        return {}

    def set_expected_length(self, task_type: str):
        """Set expected_length based on task type. Falls back to default 8."""
        if not self._length_stats:
            return
        by_type = self._length_stats.get("by_task_type", {})
        if task_type in by_type:
            median = by_type[task_type]["median"]
            # Cap at reasonable maximum to prevent long-tail inflation
            self.expected_length = min(median, 15)
        else:
            # Keep default (8) — global median (11) is inflated by long-tail types
            self.expected_length = 8

    def _load_model(self, checkpoint_path: Optional[Path] = None):
        if checkpoint_path is None:
            checkpoint_path = V4_TRANSFORMER_CHECKPOINT_DIR / "best_model.pth"
        print(f"[V4 Inferencer] Loading model: {checkpoint_path}")

        with open(V4_TASK_TYPE_VOCAB_PATH, 'r', encoding='utf-8') as f:
            task_type_vocab = json.load(f)

        self.model = TaskConditionedL3TransformerModelV4(
            vocab_size=TOTAL_VOCAB_SIZE,
            num_task_types=task_type_vocab['num_types'],
            d_model=V4_D_MODEL, n_heads=V4_N_HEADS, n_layers=V4_N_LAYERS,
            dim_feedforward=V4_D_FF, dropout=0.0,
            max_seq_length=V4_MAX_SEQ_LENGTH,
            max_memory_tokens=V4_MAX_MEMORY_TOKENS,
            use_l3_embeddings=False, freeze_bert=True,
            bert_unfreeze_layers=V4_BERT_UNFREEZE_LAYERS,
        )
        raw = torch.load(checkpoint_path, map_location=self.device)

        # V4.2 checkpoint wraps weights: {'model_state_dict': ..., 'epoch': ..., ...}
        if isinstance(raw, dict) and 'model_state_dict' in raw:
            state_dict = raw['model_state_dict']
            epoch = raw.get('epoch', '?')
            val_loss = raw.get('val_loss', '?')
            print(f"  Checkpoint info: epoch={epoch}, val_loss={val_loss}")
        else:
            state_dict = raw

        try:
            self.model.load_state_dict(state_dict, strict=True)
            print("  [OK] state_dict strict=True loaded successfully")
        except RuntimeError as e:
            print(f"  [WARN] strict=True failed: {e}")
            missing, unexpected = self.model.load_state_dict(state_dict, strict=False)
            print(f"  Loaded with strict=False: missing={len(missing)}, unexpected={len(unexpected)}")
        self.model = self.model.to(self.device)
        self.model.eval()
        print(f"  Model loaded on {self.device}")

    def _load_vocab(self):
        with open(V4_TASK_TYPE_VOCAB_PATH, 'r', encoding='utf-8') as f:
            task_type_vocab = json.load(f)

        self.task_vocab_builder = TaskVocabularyBuilder()
        self.task_vocab_builder.task_type_to_id = task_type_vocab['task_type_to_id']
        self.task_vocab_builder.id_to_task_type = {
            int(k): v for k, v in task_type_vocab['id_to_task_type'].items()
        }

        # id -> l3_code mapping
        id_mappings_path = OUTPUT_DIR / "id_mappings.json"
        if id_mappings_path.exists():
            with open(id_mappings_path, 'r', encoding='utf-8') as f:
                id_mappings = json.load(f)
            l3_map = id_mappings.get('l3', {})
            self.id_to_l3_code = {int(v): k for k, v in l3_map.items()}

        # L3 hierarchy
        hierarchy_path = _resolve_project_root() / "classification_hierarchy.csv"
        if hierarchy_path.exists():
            with open(hierarchy_path, 'r', encoding='utf-8') as f:
                for row in csv.DictReader(f):
                    code = (row.get('l3_code') or '').strip()
                    if code:
                        self.l3_code_to_name[code] = (row.get('l3_name') or '').strip()
                        l2 = (row.get('l2_code') or '').strip()
                        if l2:
                            self.l3_code_to_l2[code] = l2

        self.bert_tokenizer = BertTokenizer.from_pretrained('bert-base-uncased')
        print(f"  Vocab loaded: {len(self.id_to_l3_code)} L3 codes, "
              f"{len(self.l3_code_to_name)} with names")

    def _load_transition_matrix(self):
        path = OUTPUT_DIR / "transition_allowed_next.json"
        if not path.exists():
            print("  [Warn] No transition matrix found")
            return
        with open(path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        for a_str, nxt in data.get('allowed_next', {}).items():
            a = int(a_str)
            allowed = set(int(b) for b in nxt.keys())
            if allowed:
                self.allowed_next[a] = allowed
        print(f"  Transition matrix: {len(self.allowed_next)} states")

    def _prepare_input(self, task_name: str, task_description: str, task_type: str):
        """Prepare model input tensors from task text."""
        task_type_id = self.task_vocab_builder.task_type_to_id.get(task_type, 0)
        text = f"{task_name} {task_description}".strip() or "unknown task"
        enc = self.bert_tokenizer(
            text, max_length=128, padding='max_length',
            truncation=True, return_tensors='pt',
        )
        return {
            'task_type_id': torch.tensor([task_type_id], dtype=torch.long, device=self.device),
            'text_input_ids': enc['input_ids'].to(self.device),
            'text_attention_mask': enc['attention_mask'].to(self.device),
        }

    def _apply_constraints(self, logits, gen_tokens_list, step):
        """Apply decoding constraints to logits [B, V]."""
        B = logits.size(0)
        # Block special tokens
        logits[:, PAD_INDEX] = float('-inf')
        logits[:, UNK_INDEX] = float('-inf')
        logits[:, START_INDEX] = float('-inf')
        if step < self.min_length:
            logits[:, END_INDEX] = float('-inf')

        for b in range(B):
            gen = gen_tokens_list[b]
            # Repetition penalty
            if self.repetition_penalty != 1.0 and gen:
                for tok in set(gen):
                    if tok < logits.size(1):
                        if logits[b, tok] > 0:
                            logits[b, tok] /= self.repetition_penalty
                        else:
                            logits[b, tok] *= self.repetition_penalty
            # No-repeat ngram
            ng = self.no_repeat_ngram
            if ng > 0 and len(gen) >= ng - 1:
                prefix = tuple(gen[-(ng - 1):])
                for s in range(len(gen) - ng + 1):
                    if tuple(gen[s:s + ng - 1]) == prefix:
                        blocked = gen[s + ng - 1]
                        if blocked < logits.size(1):
                            logits[b, blocked] = float('-inf')
            # Transition constraint
            if gen and self.allowed_next:
                last_tok = gen[-1]
                allowed = self.allowed_next.get(last_tok)
                if allowed:
                    mask = torch.full((logits.size(1),), float('-inf'), device=logits.device)
                    idx = torch.tensor(list(allowed), dtype=torch.long, device=logits.device)
                    mask[idx] = 0.0
                    mask[END_INDEX] = 0.0  # Always allow END
                    logits[b] += mask
            # Consecutive token dedup: block same token as last generated
            # Placed after transition constraints; absolute assignment overrides additive mask
            if gen and len(gen) > 0:
                last_token = gen[-1]
                if last_token < logits.size(1):
                    logits[b, last_token] = float('-inf')

        # END token progressive boost: encourage stopping after expected_length
        if step > self.expected_length:
            overshoot = step - self.expected_length
            bonus = 1.0 * overshoot
            logits[:, END_INDEX] += bonus

        return logits

    @torch.no_grad()
    def diverse_beam_search(self, inputs: Dict) -> List[L3Candidate]:
        """Group Diverse Beam Search with Hamming diversity penalty."""
        G = self.num_beam_groups
        B = self.beams_per_group
        total_beams = G * B

        task_type_ids = inputs['task_type_id']
        text_input_ids = inputs['text_input_ids']
        text_attention_mask = inputs['text_attention_mask']

        # Each beam: (tokens_list, log_prob, finished)
        beams = [([START_INDEX], 0.0, False) for _ in range(total_beams)]
        # Track which tokens each group selected at each step (for diversity)
        group_selected_tokens: List[List[Set[int]]] = [[] for _ in range(G)]

        for step in range(1, self.max_length):
            all_candidates = []

            for g in range(G):
                group_beams = beams[g * B: (g + 1) * B]
                group_cands = []

                for beam_idx, (tokens, lp, finished) in enumerate(group_beams):
                    if finished:
                        group_cands.append((tokens, lp, True))
                        continue

                    # Per-beam length cutoff
                    if len(tokens) - 1 > self.expected_length * 1.5:
                        group_cands.append((tokens, lp, True))
                        continue

                    # Build input tensors for this beam
                    seq = torch.tensor([tokens], dtype=torch.long, device=self.device)
                    attn = torch.ones(1, len(tokens), dtype=torch.long, device=self.device)

                    logits = self.model(
                        seq, task_type_ids, text_input_ids, text_attention_mask,
                        attention_mask=attn, return_aux=False,
                    )
                    next_logits = logits[0, -1, :].clone()  # [V]

                    # Apply constraints
                    gen_tokens = tokens[1:]  # exclude START
                    expanded = next_logits.unsqueeze(0)
                    self._apply_constraints(expanded, [gen_tokens], step)
                    next_logits = expanded[0]

                    # Diversity penalty: penalize tokens selected by previous groups
                    for prev_g in range(g):
                        if step - 1 < len(group_selected_tokens[prev_g]):
                            prev_selected = group_selected_tokens[prev_g][step - 1]
                            for tok in prev_selected:
                                if tok < next_logits.size(0):
                                    next_logits[tok] -= self.diversity_lambda

                    log_probs = F.log_softmax(next_logits, dim=-1)
                    topk_lp, topk_idx = log_probs.topk(B)

                    for k in range(B):
                        tok = topk_idx[k].item()
                        new_lp = lp + topk_lp[k].item()
                        new_tokens = tokens + [tok]
                        new_finished = (tok == END_INDEX)
                        group_cands.append((new_tokens, new_lp, new_finished))

                # Select top-B candidates for this group
                group_cands.sort(key=lambda x: x[1] / max(len(x[0]), 1), reverse=True)
                selected = group_cands[:B]

                # Record selected tokens for diversity
                step_tokens = set()
                for tokens_list, _, _ in selected:
                    if len(tokens_list) > step:
                        step_tokens.add(tokens_list[step])
                if step - 1 < len(group_selected_tokens[g]):
                    group_selected_tokens[g][step - 1] = step_tokens
                else:
                    group_selected_tokens[g].append(step_tokens)

                all_candidates.extend(selected)

            beams = all_candidates

            # Check if all beams finished
            if all(f for _, _, f in beams):
                break

        # Convert to candidates (take best from each group)
        candidates = []
        for g in range(G):
            group_beams = beams[g * B: (g + 1) * B]
            # Prefer finished beams
            finished_beams = [(t, lp) for t, lp, f in group_beams if f]
            if finished_beams:
                best = max(finished_beams, key=lambda x: x[1] / max(len(x[0]), 1))
            else:
                best = max(group_beams, key=lambda x: x[1] / max(len(x[0]), 1))[:2]
            tokens, lp = best[0], best[1]
            # Strip START and END
            content = [t for t in tokens if t not in (START_INDEX, END_INDEX, PAD_INDEX)]
            candidates.append(L3Candidate(
                tokens=content, log_prob=lp,
                length=len(content),
                is_complete=(END_INDEX in tokens),
            ))

        return candidates

    @torch.no_grad()
    def temperature_sample(self, inputs: Dict) -> List[L3Candidate]:
        """Generate candidates via temperature sampling + top-p nucleus."""
        task_type_ids = inputs['task_type_id']
        text_input_ids = inputs['text_input_ids']
        text_attention_mask = inputs['text_attention_mask']

        candidates = []
        for _ in range(self.num_samples):
            tokens = [START_INDEX]
            total_lp = 0.0

            for step in range(1, self.max_length):
                # Early stop if past expected length cutoff
                if step > self.expected_length * 1.5:
                    break

                seq = torch.tensor([tokens], dtype=torch.long, device=self.device)
                attn = torch.ones(1, len(tokens), dtype=torch.long, device=self.device)

                logits = self.model(
                    seq, task_type_ids, text_input_ids, text_attention_mask,
                    attention_mask=attn, return_aux=False,
                )
                next_logits = logits[0, -1, :].clone()

                # Apply constraints
                gen = tokens[1:]
                expanded = next_logits.unsqueeze(0)
                self._apply_constraints(expanded, [gen], step)
                next_logits = expanded[0]

                # Temperature scaling
                next_logits = next_logits / max(self.sampling_temperature, 1e-8)

                # Top-p (nucleus) sampling
                sorted_logits, sorted_idx = torch.sort(next_logits, descending=True)
                cumulative_probs = torch.cumsum(F.softmax(sorted_logits, dim=-1), dim=-1)
                # Remove tokens with cumulative prob above threshold
                remove_mask = cumulative_probs - F.softmax(sorted_logits, dim=-1) >= self.sampling_top_p
                sorted_logits[remove_mask] = float('-inf')
                # Scatter back
                next_logits = torch.zeros_like(next_logits).scatter_(0, sorted_idx, sorted_logits)

                probs = F.softmax(next_logits, dim=-1)
                tok = torch.multinomial(probs, 1).item()
                total_lp += F.log_softmax(next_logits, dim=-1)[tok].item()
                tokens.append(tok)

                if tok == END_INDEX:
                    break

            content = [t for t in tokens if t not in (START_INDEX, END_INDEX, PAD_INDEX)]
            candidates.append(L3Candidate(
                tokens=content, log_prob=total_lp,
                length=len(content),
                is_complete=(tokens[-1] == END_INDEX),
            ))

        return candidates

    def _compute_transition_score(self, tokens: List[int]) -> float:
        """Fraction of transitions that are in the allowed_next matrix."""
        if not self.allowed_next or len(tokens) < 2:
            return 1.0
        valid = 0
        total = 0
        for i in range(len(tokens) - 1):
            allowed = self.allowed_next.get(tokens[i])
            if allowed is not None:
                total += 1
                if tokens[i + 1] in allowed:
                    valid += 1
        return valid / max(total, 1)

    def _compute_length_score(self, length: int) -> float:
        """Asymmetric length score: mild penalty for short, strong penalty for long."""
        diff = length - self.expected_length
        if diff <= 0:
            # At or below expected: mild penalty
            return math.exp(-0.05 * abs(diff))
        else:
            # Above expected: strong penalty
            return math.exp(-0.2 * diff)

    def _compute_diversity_score(self, tokens: List[int], all_candidates: List[L3Candidate]) -> float:
        """Average Jaccard distance to other candidates."""
        if not all_candidates:
            return 1.0
        token_set = set(tokens)
        distances = []
        for c in all_candidates:
            other_set = set(c.tokens)
            union = token_set | other_set
            if not union:
                continue
            jaccard = len(token_set & other_set) / len(union)
            distances.append(1.0 - jaccard)
        return sum(distances) / max(len(distances), 1)

    def _postprocess_sequence(self, tokens: List[int]) -> List[int]:
        """Remove consecutive duplicates, ABAB patterns, and tail loops."""
        if not tokens:
            return tokens

        # 1. Remove consecutive duplicates
        deduped = [tokens[0]]
        for t in tokens[1:]:
            if t != deduped[-1]:
                deduped.append(t)

        # 2. Collapse ABAB oscillation: if a token appears 3+ times,
        #    keep only its first occurrence and the tokens between
        from collections import Counter
        counts = Counter(deduped)
        if any(c >= 3 for c in counts.values()):
            seen_twice = set()
            result = []
            for t in deduped:
                if counts[t] >= 3 and t in seen_twice:
                    continue  # Skip 3rd+ occurrence
                result.append(t)
                if counts[t] >= 3:
                    seen_twice.add(t)
            deduped = result

        # 3. Truncate tail loops: if 3+ consecutive tokens at the end
        #    are all previously-seen, cut the repeated tail
        if len(deduped) > 4:
            seen = set()
            repeat_streak = 0
            cut_point = len(deduped)
            for i, t in enumerate(deduped):
                if t in seen:
                    repeat_streak += 1
                    if repeat_streak >= 3:
                        cut_point = i - 2
                        break
                else:
                    repeat_streak = 0
                seen.add(t)
            deduped = deduped[:cut_point]

        return deduped

    def _score_and_rank(self, candidates: List[L3Candidate]) -> List[L3Candidate]:
        """Multi-factor scoring and ranking."""
        if not candidates:
            return []

        # Compute individual scores
        for c in candidates:
            c.transition_score = self._compute_transition_score(c.tokens)
            c.length_score = self._compute_length_score(c.length)

        # Normalize log_prob to [0, 1]
        lps = [c.log_prob / max(c.length, 1) for c in candidates]
        min_lp, max_lp = min(lps), max(lps)
        lp_range = max(max_lp - min_lp, 1e-8)

        for i, c in enumerate(candidates):
            norm_lp = (lps[i] - min_lp) / lp_range
            c.diversity_score = self._compute_diversity_score(c.tokens, candidates[:i])
            c.final_score = (
                V4_SCORE_LOG_PROB_WEIGHT * norm_lp
                + V4_SCORE_TRANSITION_WEIGHT * c.transition_score
                + V4_SCORE_LENGTH_WEIGHT * c.length_score
                + V4_SCORE_DIVERSITY_WEIGHT * c.diversity_score
            )
            # Penalize incomplete sequences (did not generate END)
            if not c.is_complete:
                c.final_score *= 0.8

        candidates.sort(key=lambda c: c.final_score, reverse=True)

        # Deduplicate by token sequence
        seen = set()
        unique = []
        for c in candidates:
            key = tuple(c.tokens)
            if key not in seen:
                seen.add(key)
                unique.append(c)

        return unique[:self.return_top_n]

    def decode_tokens(self, tokens: List[int], use_name: bool = True) -> List[str]:
        """Decode token IDs to L3 codes or names."""
        out = []
        for t in tokens:
            if t in self.id_to_l3_code:
                code = self.id_to_l3_code[t]
                if use_name and code in self.l3_code_to_name:
                    out.append(self.l3_code_to_name[code])
                else:
                    out.append(code)
            elif t == PAD_INDEX:
                out.append("<PAD>")
            elif t == UNK_INDEX:
                out.append("<UNK>")
            elif t == START_INDEX:
                out.append("<START>")
            elif t == END_INDEX:
                out.append("<END>")
            else:
                out.append(f"[{t}]")
        return out

    def infer_from_model_input(
        self,
        model_input: Dict[str, torch.Tensor],
        task_type: Optional[str] = None,
        mode: str = "both",
    ) -> List[L3Candidate]:
        """
        Infer using pre-encoded model_input from the LLM pipeline.

        Args:
            model_input: {
                "task_type_id": Tensor([id]),
                "text_input_ids": Tensor([1, seq_len]),
                "text_attention_mask": Tensor([1, seq_len])
            }
            task_type: Optional task type string (unused, kept for API compat)
            mode: 'beam', 'sample', or 'both'
        """
        inputs = {
            'task_type_id': model_input['task_type_id'].to(self.device),
            'text_input_ids': model_input['text_input_ids'].to(self.device),
            'text_attention_mask': model_input['text_attention_mask'].to(self.device),
        }
        candidates = []

        if mode in ('beam', 'both'):
            beam_cands = self.diverse_beam_search(inputs)
            candidates.extend(beam_cands)

        if mode in ('sample', 'both'):
            sample_cands = self.temperature_sample(inputs)
            candidates.extend(sample_cands)

        # Post-process sequences before scoring
        for c in candidates:
            c.tokens = self._postprocess_sequence(c.tokens)
            c.length = len(c.tokens)

        return self._score_and_rank(candidates)

    def infer(
        self,
        task_name: str = "",
        task_description: str = "",
        task_type: str = "Unknown",
        mode: str = "both",
    ) -> List[L3Candidate]:
        """
        Main inference API.

        Args:
            task_name: Task name
            task_description: Task description
            task_type: Task type string
            mode: 'beam', 'sample', or 'both'

        Returns:
            Ranked list of L3Candidate objects
        """
        inputs = self._prepare_input(task_name, task_description, task_type)
        candidates = []

        if mode in ('beam', 'both'):
            beam_cands = self.diverse_beam_search(inputs)
            candidates.extend(beam_cands)

        if mode in ('sample', 'both'):
            sample_cands = self.temperature_sample(inputs)
            candidates.extend(sample_cands)

        # Post-process sequences before scoring
        for c in candidates:
            c.tokens = self._postprocess_sequence(c.tokens)
            c.length = len(c.tokens)

        return self._score_and_rank(candidates)

    def infer_and_print(
        self,
        task_name: str = "",
        task_description: str = "",
        task_type: str = "Unknown",
        mode: str = "both",
    ):
        """Infer and pretty-print results."""
        print(f"\n{'='*70}")
        print(f"Task: {task_name}")
        print(f"Description: {task_description[:80]}...")
        print(f"Type: {task_type}")
        print(f"{'='*70}")

        candidates = self.infer(task_name, task_description, task_type, mode)

        for i, c in enumerate(candidates):
            print(f"\n  Candidate #{i+1} (score={c.final_score:.3f}, "
                  f"len={c.length}, complete={c.is_complete})")
            # Map tokens to L3 codes and names
            parts = []
            for tok in c.tokens:
                code = self.id_to_l3_code.get(tok, f"?{tok}")
                name = self.l3_code_to_name.get(code, "")
                parts.append(f"{code}({name})" if name else str(code))
            print(f"    Tokens: {c.tokens}")
            print(f"    L3: {' → '.join(parts)}")
            print(f"    Scores: log_prob={c.log_prob:.2f}, "
                  f"trans={c.transition_score:.2f}, "
                  f"len={c.length_score:.2f}, "
                  f"div={c.diversity_score:.2f}")

            # Show L2 coverage
            l2_set = set()
            for tok in c.tokens:
                code = self.id_to_l3_code.get(tok, "")
                l2 = self.l3_code_to_l2.get(code, "")
                if l2:
                    l2_set.add(l2)
            if l2_set:
                print(f"    L2 coverage: {len(l2_set)} families: {sorted(l2_set)}")

        return candidates


def main():
    """Demo: run inference on sample tasks."""
    print("V4 L3 Sequence Inferencer Demo")
    print("=" * 70)

    inferencer = L3SequenceInferencerV4()

    test_tasks = [
        ("Land cover classification",
         "Classify land use types from Landsat satellite imagery",
         "Land use/land cover"),
        ("Flood mapping",
         "Map flood extent using SAR imagery after heavy rainfall",
         "Disaster monitoring"),
        ("Vegetation index calculation",
         "Calculate NDVI from Sentinel-2 multispectral data",
         "Vegetation analysis"),
    ]

    for name, desc, ttype in test_tasks:
        inferencer.infer_and_print(name, desc, ttype)


if __name__ == "__main__":
    main()
