from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional, Sequence

import torch
import torch.nn as nn
import torch.nn.functional as F

from .config import V5FinalConfig
from .diagnostics import alpha_trace_step
from .io_mask import IOMaskBuilder
from .pvm import PVMCache


@dataclass
class V5ForwardOutput:
    logits_op: torch.Tensor
    logits_end: torch.Tensor
    alpha: torch.Tensor
    hidden_states: torch.Tensor


@dataclass
class DecodeResult:
    operator_ids: list[int]
    operator_names: list[str] = field(default_factory=list)
    beam_candidates: list[dict] = field(default_factory=list)
    decode_trace: list[dict] = field(default_factory=list)
    alpha_trace: list[dict] = field(default_factory=list)
    token_probabilities: list[dict] = field(default_factory=list)
    end_timing: dict = field(default_factory=dict)
    repetition_statistics: dict = field(default_factory=dict)
    termination_reason: str = "max_len"


class FrozenBertEncoder(nn.Module):
    """Frozen BERT encoder wrapper used by production callers when desired."""

    def __init__(self, model_name: str = "bert-base-uncased", *, local_files_only: bool = True) -> None:
        super().__init__()
        from transformers import BertModel

        self.bert = BertModel.from_pretrained(model_name, local_files_only=local_files_only)
        for param in self.bert.parameters():
            param.requires_grad = False
        self.hidden_size = int(self.bert.config.hidden_size)

    def forward(self, input_ids: torch.Tensor, attention_mask: torch.Tensor) -> torch.Tensor:
        with torch.no_grad():
            return self.bert(input_ids=input_ids, attention_mask=attention_mask).last_hidden_state


class V5FinalModel(nn.Module):
    """Memory-augmented autoregressive workflow planner."""

    def __init__(
        self,
        config: V5FinalConfig,
        *,
        text_encoder: Optional[nn.Module] = None,
    ) -> None:
        super().__init__()
        self.config = config
        self.text_encoder = text_encoder
        self.task_projection = nn.Linear(config.bert_hidden_size, config.d_model)
        self.task_norm = nn.LayerNorm(config.d_model)
        self.token_embedding = nn.Embedding(config.vocab_size, config.d_model)
        self.pvm = PVMCache(config.d_model, config.d_key, gamma=config.gamma, rho=config.rho)

        encoder_layer = nn.TransformerEncoderLayer(
            d_model=config.d_model,
            nhead=config.n_heads,
            dim_feedforward=config.d_ff,
            dropout=config.dropout,
            batch_first=True,
        )
        self.decoder = nn.TransformerEncoder(encoder_layer, num_layers=config.n_layers)
        self.decoder_norm = nn.LayerNorm(config.d_model)
        self.condition_gamma = nn.Linear(config.d_model, config.d_model)
        self.condition_beta = nn.Linear(config.d_model, config.d_model)
        self.op_head = nn.Linear(config.d_model, config.vocab_size)
        self.end_head = nn.Linear(config.d_model, 1)
        self._init_parameters()

    def _init_parameters(self) -> None:
        nn.init.zeros_(self.condition_gamma.weight)
        self.condition_gamma.weight.data.fill_diagonal_(1.0)
        nn.init.zeros_(self.condition_gamma.bias)
        nn.init.zeros_(self.condition_beta.weight)
        nn.init.zeros_(self.condition_beta.bias)

    def encode_task(
        self,
        *,
        task_embeddings: Optional[torch.Tensor] = None,
        task_input_ids: Optional[torch.Tensor] = None,
        task_attention_mask: Optional[torch.Tensor] = None,
    ) -> torch.Tensor:
        if task_embeddings is None:
            if self.text_encoder is None:
                raise ValueError("task_embeddings are required when no text_encoder is configured")
            if task_input_ids is None or task_attention_mask is None:
                raise ValueError("task_input_ids and task_attention_mask are required for text_encoder")
            task_embeddings = self.text_encoder(task_input_ids, task_attention_mask)
        pooled = task_embeddings.mean(dim=1)
        return self.task_norm(self.task_projection(pooled))

    def _decoder_step(self, q_history: torch.Tensor, condition: torch.Tensor) -> torch.Tensor:
        length = q_history.shape[1]
        mask = torch.triu(
            torch.ones(length, length, device=q_history.device, dtype=torch.bool),
            diagonal=1,
        )
        decoded = self.decoder(q_history, mask=mask)
        q = self.decoder_norm(decoded[:, -1, :])
        gamma = self.condition_gamma(condition)
        beta = self.condition_beta(condition)
        return gamma * q + beta

    def _step(
        self,
        *,
        q_prev: torch.Tensor,
        pvm_slots: torch.Tensor,
        q_history: list[torch.Tensor],
        condition: torch.Tensor,
    ) -> tuple[torch.Tensor, torch.Tensor, torch.Tensor]:
        if self.config.no_pvm:
            c_mem = torch.zeros_like(q_prev)
            alpha = torch.zeros(
                pvm_slots.shape[0],
                pvm_slots.shape[1],
                device=pvm_slots.device,
                dtype=pvm_slots.dtype,
            )
            alpha[:, -1] = 1.0
        else:
            c_mem, alpha = self.pvm.read(
                q_prev,
                pvm_slots,
                training=self.training,
                alpha_noise_p=0.0 if self.config.no_alpha_noise else self.config.alpha_noise_p,
                use_qk_decoupling=not self.config.no_qk_decoupling,
                use_temporal_decay=not self.config.no_fixed_gamma,
            )
        q_in = q_prev + c_mem
        q_history.append(q_in)
        q_stack = torch.stack(q_history, dim=1)
        q_next = self._decoder_step(q_stack, condition)
        return q_next, alpha, q_in

    def forward(
        self,
        *,
        operator_input_ids: torch.Tensor,
        task_embeddings: Optional[torch.Tensor] = None,
        task_input_ids: Optional[torch.Tensor] = None,
        task_attention_mask: Optional[torch.Tensor] = None,
        return_diagnostics: bool = False,
    ) -> V5ForwardOutput:
        batch_size, seq_len = operator_input_ids.shape
        condition = self.encode_task(
            task_embeddings=task_embeddings,
            task_input_ids=task_input_ids,
            task_attention_mask=task_attention_mask,
        )
        pvm_slots: list[torch.Tensor] = [condition]
        q_prev = condition
        q_history: list[torch.Tensor] = []
        logits_op = []
        logits_end = []
        hidden_states = []
        alpha_padded = operator_input_ids.new_zeros(
            (batch_size, seq_len, seq_len + 1),
            dtype=condition.dtype,
        )

        for t in range(seq_len):
            pvm_stack = torch.stack(pvm_slots, dim=1)
            q_next, alpha, _ = self._step(
                q_prev=q_prev,
                pvm_slots=pvm_stack,
                q_history=q_history,
                condition=condition,
            )
            logits_op.append(self.op_head(q_next))
            logits_end.append(self.end_head(q_next))
            hidden_states.append(q_next)
            alpha_padded[:, t, : alpha.shape[1]] = alpha

            token_ids = operator_input_ids[:, t].clamp(0, self.config.vocab_size - 1)
            pvm_slots.append(self.pvm.write_operator(self.token_embedding(token_ids)))
            q_prev = q_next

        return V5ForwardOutput(
            logits_op=torch.stack(logits_op, dim=1),
            logits_end=torch.stack(logits_end, dim=1),
            alpha=alpha_padded if return_diagnostics else alpha_padded.detach(),
            hidden_states=torch.stack(hidden_states, dim=1),
        )

    @torch.no_grad()
    def decode_greedy(
        self,
        *,
        task_embeddings: Optional[torch.Tensor] = None,
        task_input_ids: Optional[torch.Tensor] = None,
        task_attention_mask: Optional[torch.Tensor] = None,
        io_mask_builder: Optional[IOMaskBuilder] = None,
        token_names: Optional[dict[int, str]] = None,
        max_len: Optional[int] = None,
        end_probability_threshold: float = 0.95,
    ) -> DecodeResult:
        was_training = self.training
        self.eval()
        try:
            condition = self.encode_task(
                task_embeddings=task_embeddings,
                task_input_ids=task_input_ids,
                task_attention_mask=task_attention_mask,
            )
            if condition.shape[0] != 1:
                raise ValueError("decode_greedy currently expects batch size 1")
            max_steps = int(max_len or self.config.max_seq_len)
            end_id = self.config.resolved_end_token_id
            names = token_names or {}
            pvm_slots: list[torch.Tensor] = [condition]
            q_prev = condition
            q_history: list[torch.Tensor] = []
            ops: list[int] = []
            alpha_trace: list[dict] = []
            decode_trace: list[dict] = []
            token_probabilities: list[dict] = []
            termination_reason = "max_len"

            for step in range(1, max_steps + 1):
                pvm_stack = torch.stack(pvm_slots, dim=1)
                q_next, alpha, _ = self._step(
                    q_prev=q_prev,
                    pvm_slots=pvm_stack,
                    q_history=q_history,
                    condition=condition,
                )
                logits = self.op_head(q_next).squeeze(0)
                previous = ops[-1] if ops else None
                if io_mask_builder is not None:
                    logits = io_mask_builder.apply_to_logits(logits, previous)
                probs = F.softmax(logits, dim=-1)
                selected = int(torch.argmax(probs).item())
                selected_prob = float(probs[selected].item())
                p_end = float(torch.sigmoid(self.end_head(q_next)).squeeze().item())
                decode_trace.append(
                    {
                        "step": step,
                        "selected_token": selected,
                        "probability": round(selected_prob, 8),
                        "p_end": round(p_end, 8),
                    }
                )
                if selected == end_id:
                    termination_reason = "end_token"
                    break
                if p_end > end_probability_threshold:
                    decode_trace[-1]["selected_token"] = end_id
                    termination_reason = "end_probability"
                    break

                ops.append(selected)
                alpha_values = alpha.squeeze(0).detach().cpu().tolist()
                alpha_trace.append(
                    alpha_trace_step(
                        step=step,
                        alpha=alpha_values,
                        predicted_op=selected,
                        predicted_op_name=names.get(selected),
                        p_end=p_end,
                    )
                )
                token_probabilities.append(
                    {
                        "position": step - 1,
                        "token": selected,
                        "probability": round(selected_prob, 8),
                    }
                )
                token_tensor = torch.tensor([selected], device=condition.device, dtype=torch.long)
                pvm_slots.append(self.pvm.write_operator(self.token_embedding(token_tensor)))
                q_prev = q_next

            result = DecodeResult(
                operator_ids=ops,
                operator_names=[names.get(token, str(token)) for token in ops],
                beam_candidates=[{"rank": 0, "tokens": list(ops), "score": _sequence_logprob(token_probabilities)}],
                decode_trace=decode_trace,
                alpha_trace=alpha_trace,
                token_probabilities=token_probabilities,
                end_timing=_end_timing(ops, decode_trace, termination_reason),
                repetition_statistics=_repetition_statistics(ops),
                termination_reason=termination_reason,
            )
            return result
        finally:
            self.train(was_training)

    @torch.no_grad()
    def decode_beam(
        self,
        *,
        task_embeddings: Optional[torch.Tensor] = None,
        task_input_ids: Optional[torch.Tensor] = None,
        task_attention_mask: Optional[torch.Tensor] = None,
        io_mask_builder: Optional[IOMaskBuilder] = None,
        token_names: Optional[dict[int, str]] = None,
        beam_width: int = 5,
        max_len: Optional[int] = None,
        end_probability_threshold: float = 0.95,
    ) -> list[DecodeResult]:
        was_training = self.training
        self.eval()
        try:
            condition = self.encode_task(
                task_embeddings=task_embeddings,
                task_input_ids=task_input_ids,
                task_attention_mask=task_attention_mask,
            )
            if condition.shape[0] != 1:
                raise ValueError("decode_beam currently expects batch size 1")
            max_steps = int(max_len or self.config.max_seq_len)
            end_id = self.config.resolved_end_token_id
            names = token_names or {}
            initial = {
                "ops": [],
                "pvm_slots": [condition],
                "q_prev": condition,
                "q_history": [],
                "alpha_trace": [],
                "decode_trace": [],
                "token_probabilities": [],
                "score": 0.0,
                "termination_reason": "max_len",
                "terminated": False,
            }
            active = [initial]
            completed: list[dict] = []

            for step in range(1, max_steps + 1):
                expanded: list[dict] = []
                for beam in active:
                    if beam["terminated"]:
                        completed.append(beam)
                        continue
                    pvm_stack = torch.stack(beam["pvm_slots"], dim=1)
                    q_history = list(beam["q_history"])
                    q_next, alpha, _ = self._step(
                        q_prev=beam["q_prev"],
                        pvm_slots=pvm_stack,
                        q_history=q_history,
                        condition=condition,
                    )
                    logits = self.op_head(q_next).squeeze(0)
                    previous = beam["ops"][-1] if beam["ops"] else None
                    if io_mask_builder is not None:
                        logits = io_mask_builder.apply_to_logits(logits, previous)
                    log_probs = F.log_softmax(logits, dim=-1)
                    top_k = min(max(int(beam_width), 1), log_probs.numel())
                    values, indices = torch.topk(log_probs, k=top_k)
                    p_end = float(torch.sigmoid(self.end_head(q_next)).squeeze().item())
                    for value, index in zip(values.tolist(), indices.tolist()):
                        selected = int(index)
                        probability = float(torch.exp(torch.tensor(value)).item())
                        child = {
                            "ops": list(beam["ops"]),
                            "pvm_slots": list(beam["pvm_slots"]),
                            "q_prev": q_next,
                            "q_history": list(q_history),
                            "alpha_trace": list(beam["alpha_trace"]),
                            "decode_trace": list(beam["decode_trace"]),
                            "token_probabilities": list(beam["token_probabilities"]),
                            "score": float(beam["score"]) + float(value),
                            "termination_reason": "max_len",
                            "terminated": False,
                        }
                        child["decode_trace"].append(
                            {
                                "step": step,
                                "selected_token": selected,
                                "probability": round(probability, 8),
                                "p_end": round(p_end, 8),
                            }
                        )
                        if selected == end_id:
                            child["terminated"] = True
                            child["termination_reason"] = "end_token"
                            completed.append(child)
                            continue
                        if p_end > end_probability_threshold:
                            child["decode_trace"][-1]["selected_token"] = end_id
                            child["terminated"] = True
                            child["termination_reason"] = "end_probability"
                            completed.append(child)
                            continue

                        child["ops"].append(selected)
                        alpha_values = alpha.squeeze(0).detach().cpu().tolist()
                        child["alpha_trace"].append(
                            alpha_trace_step(
                                step=step,
                                alpha=alpha_values,
                                predicted_op=selected,
                                predicted_op_name=names.get(selected),
                                p_end=p_end,
                            )
                        )
                        child["token_probabilities"].append(
                            {
                                "position": step - 1,
                                "token": selected,
                                "probability": round(probability, 8),
                            }
                        )
                        token_tensor = torch.tensor([selected], device=condition.device, dtype=torch.long)
                        child["pvm_slots"].append(self.pvm.write_operator(self.token_embedding(token_tensor)))
                        expanded.append(child)
                if not expanded:
                    break
                expanded.sort(key=lambda row: (float(row["score"]), -len(row["ops"])), reverse=True)
                active = expanded[: max(int(beam_width), 1)]
            completed.extend(active)
            completed.sort(key=lambda row: (float(row["score"]), -len(row["ops"])), reverse=True)
            return [
                _beam_to_result(row, names, rank)
                for rank, row in enumerate(completed[: max(int(beam_width), 1)])
            ]
        finally:
            self.train(was_training)


def _sequence_logprob(token_probabilities: Sequence[dict]) -> float:
    score = 0.0
    for row in token_probabilities:
        prob = max(float(row.get("probability", 0.0)), 1e-12)
        score += float(torch.log(torch.tensor(prob)).item())
    return round(score, 8)


def _beam_to_result(row: dict, names: dict[int, str], rank: int) -> DecodeResult:
    ops = [int(token) for token in row["ops"]]
    score = round(float(row["score"]), 8)
    return DecodeResult(
        operator_ids=ops,
        operator_names=[names.get(token, str(token)) for token in ops],
        beam_candidates=[{"rank": rank, "tokens": list(ops), "score": score}],
        decode_trace=list(row["decode_trace"]),
        alpha_trace=list(row["alpha_trace"]),
        token_probabilities=list(row["token_probabilities"]),
        end_timing=_end_timing(ops, row["decode_trace"], row["termination_reason"]),
        repetition_statistics=_repetition_statistics(ops),
        termination_reason=row["termination_reason"],
    )


def _end_timing(ops: Sequence[int], decode_trace: Sequence[dict], reason: str) -> dict:
    return {
        "predicted_content_length": len(ops),
        "generated_end_step": len(decode_trace),
        "early_end": False,
        "overlong": False,
        "termination_reason": reason,
    }


def _repetition_statistics(ops: Sequence[int]) -> dict:
    if not ops:
        return {
            "length": 0,
            "unique_count": 0,
            "unique_ratio": 0.0,
            "repeated_token_events": 0,
            "max_run": 0,
            "repeated_bigram_events": 0,
        }
    counts: dict[int, int] = {}
    for op in ops:
        counts[int(op)] = counts.get(int(op), 0) + 1
    max_run = 1
    run = 1
    for prev, cur in zip(ops, ops[1:]):
        if cur == prev:
            run += 1
        else:
            run = 1
        max_run = max(max_run, run)
    bigrams: dict[tuple[int, int], int] = {}
    for pair in zip(ops, ops[1:]):
        bigrams[(int(pair[0]), int(pair[1]))] = bigrams.get((int(pair[0]), int(pair[1])), 0) + 1
    return {
        "length": len(ops),
        "unique_count": len(counts),
        "unique_ratio": round(len(counts) / len(ops), 6),
        "repeated_token_events": sum(count - 1 for count in counts.values() if count > 1),
        "max_run": max_run,
        "repeated_bigram_events": sum(count - 1 for count in bigrams.values() if count > 1),
    }
