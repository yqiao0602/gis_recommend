from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable, Mapping, Optional

import torch


class IOMaskBuilder:
    """Deterministic IO feasibility mask.

    The builder consumes only direct runtime inputs: vocabulary size, END token,
    and a compatibility lookup.  It does not read provenance, metrics, reports,
    or validation output.
    """

    def __init__(
        self,
        *,
        vocab_size: int,
        end_token_id: int,
        allowed_next: Optional[Mapping[int | str, Iterable[int | str] | Mapping[int | str, object]]] = None,
        blocked_token_ids: Optional[Iterable[int]] = None,
    ) -> None:
        self.vocab_size = int(vocab_size)
        self.end_token_id = int(end_token_id)
        self.blocked_token_ids = {int(token) for token in (blocked_token_ids or [])}
        self.allowed_next: dict[int, set[int]] = {}
        for prev, values in dict(allowed_next or {}).items():
            if isinstance(values, Mapping):
                tokens = values.keys()
            else:
                tokens = values
            self.allowed_next[int(prev)] = {int(token) for token in tokens}

    @classmethod
    def from_transition_matrix(
        cls,
        path: Path | str,
        *,
        vocab_size: int,
        end_token_id: int,
        blocked_token_ids: Optional[Iterable[int]] = None,
    ) -> "IOMaskBuilder":
        with Path(path).open("r", encoding="utf-8") as f:
            payload = json.load(f)
        allowed = payload.get("allowed_next", payload)
        if not isinstance(allowed, Mapping):
            raise ValueError(f"Invalid transition matrix format: {path}")
        return cls(
            vocab_size=vocab_size,
            end_token_id=end_token_id,
            allowed_next=allowed,
            blocked_token_ids=blocked_token_ids,
        )

    def allowed_tokens(self, previous_token: Optional[int]) -> set[int]:
        if previous_token is None:
            allowed = set(range(self.vocab_size))
        else:
            allowed = set(self.allowed_next.get(int(previous_token), set()))
            allowed.add(self.end_token_id)
        return {token for token in allowed if 0 <= token < self.vocab_size and token not in self.blocked_token_ids}

    def are_compatible(self, previous_token: int, next_token: int) -> bool:
        if int(next_token) == self.end_token_id:
            return True
        if not self.allowed_next:
            return True
        allowed = self.allowed_next.get(int(previous_token))
        return allowed is not None and int(next_token) in allowed

    def mask_for_previous(
        self,
        previous_token: Optional[int],
        *,
        device: Optional[torch.device] = None,
        dtype: torch.dtype = torch.float32,
    ) -> torch.Tensor:
        mask = torch.full((self.vocab_size,), float("-inf"), device=device, dtype=dtype)
        allowed = self.allowed_tokens(previous_token)
        if allowed:
            indices = torch.tensor(sorted(allowed), device=device, dtype=torch.long)
            mask[indices] = 0.0
        return mask

    def apply_to_logits(self, logits: torch.Tensor, previous_token: Optional[int]) -> torch.Tensor:
        mask = self.mask_for_previous(previous_token, device=logits.device, dtype=logits.dtype)
        return logits + mask
