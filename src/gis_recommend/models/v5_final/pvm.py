from __future__ import annotations

import math

import torch
import torch.nn as nn
import torch.nn.functional as F


class PVMCache(nn.Module):
    """Position-indexed representation cache with retrieval attention."""

    def __init__(self, d_model: int, d_key: int, *, gamma: float = 0.3, rho: float = 1.5) -> None:
        super().__init__()
        self.d_model = int(d_model)
        self.d_key = int(d_key)
        self.gamma = float(gamma)
        self.rho = float(rho)
        self.w_struct = nn.Linear(d_model, d_model, bias=False)
        self.w_key = nn.Linear(d_model, d_key, bias=False)
        self.w_proj = nn.Linear(d_model, d_model, bias=False)
        self.struct_norm = nn.LayerNorm(d_model)
        self.reset_parameters()

    def reset_parameters(self) -> None:
        nn.init.xavier_uniform_(self.w_struct.weight)
        nn.init.xavier_uniform_(self.w_key.weight)
        nn.init.xavier_uniform_(self.w_proj.weight)

    def write_operator(self, token_embedding: torch.Tensor) -> torch.Tensor:
        return self.w_proj(token_embedding)

    def compute_alpha(
        self,
        query_state: torch.Tensor,
        pvm_slots: torch.Tensor,
        *,
        training: bool,
        alpha_noise_p: float,
        use_qk_decoupling: bool = True,
        use_temporal_decay: bool = True,
    ) -> torch.Tensor:
        """Return retrieval attention over existing PVM slots.

        Args:
            query_state: [B, D]
            pvm_slots: [B, T_slots, D]
        """
        if pvm_slots.ndim != 3:
            raise ValueError("pvm_slots must have shape [B, T_slots, D]")
        slot_count = pvm_slots.shape[1]
        if use_qk_decoupling:
            query_hidden = self.struct_norm(self.w_struct(query_state))
            query = query_hidden[:, : self.d_key]
            keys = self.w_key(pvm_slots)
        else:
            query = query_state[:, : self.d_key]
            keys = pvm_slots[:, :, : self.d_key]
        logits = torch.einsum("bd,btd->bt", query, keys) / math.sqrt(self.d_key)
        if use_temporal_decay:
            positions = torch.arange(slot_count, device=pvm_slots.device, dtype=logits.dtype)
            step_index = torch.full_like(positions, fill_value=float(slot_count))
            decay = self.gamma * torch.abs(step_index - positions).pow(self.rho)
            logits = logits - decay.unsqueeze(0)
        alpha = F.softmax(logits, dim=-1)
        if training and alpha_noise_p > 0.0 and slot_count > 0:
            random_index = torch.randint(slot_count, (alpha.shape[0],), device=alpha.device)
            one_hot = F.one_hot(random_index, num_classes=slot_count).to(alpha.dtype)
            alpha = (1.0 - alpha_noise_p) * alpha + alpha_noise_p * one_hot
            alpha = alpha / alpha.sum(dim=-1, keepdim=True).clamp_min(1e-12)
        return alpha

    def read(
        self,
        query_state: torch.Tensor,
        pvm_slots: torch.Tensor,
        *,
        training: bool,
        alpha_noise_p: float,
        use_qk_decoupling: bool = True,
        use_temporal_decay: bool = True,
    ) -> tuple[torch.Tensor, torch.Tensor]:
        alpha = self.compute_alpha(
            query_state,
            pvm_slots,
            training=training,
            alpha_noise_p=alpha_noise_p,
            use_qk_decoupling=use_qk_decoupling,
            use_temporal_decay=use_temporal_decay,
        )
        context = torch.einsum("bt,btd->bd", alpha, pvm_slots)
        return context, alpha


def alpha_entropy(alpha: torch.Tensor) -> torch.Tensor:
    alpha = alpha.clamp_min(1e-12)
    return -(alpha * alpha.log()).sum(dim=-1)


def recency_concentration(alpha: torch.Tensor) -> torch.Tensor:
    if alpha.shape[-1] == 0:
        return torch.zeros(alpha.shape[:-1], dtype=alpha.dtype, device=alpha.device)
    return alpha[..., -1]
