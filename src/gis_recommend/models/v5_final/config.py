from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class V5FinalConfig:
    """Runtime config for the converged V5_final model.

    This is a direct runtime config, not a governance profile.  The fixed
    temporal-decay and alpha-noise values are ordinary scalar inputs and are not
    trainable model parameters.
    """

    vocab_size: int
    d_model: int = 256
    d_key: int = 64
    n_layers: int = 6
    n_heads: int = 8
    d_ff: int = 1024
    max_seq_len: int = 16
    bert_hidden_size: int = 768
    dropout: float = 0.1
    gamma: float = 0.3
    rho: float = 1.5
    alpha_noise_p: float = 0.05
    graph_threshold_tau: float = 0.15
    start_token_id: int = 0
    end_token_id: int = -1
    pad_token_id: int = -1
    lambda_end: float = 0.3

    no_pvm: bool = False
    no_qk_decoupling: bool = False
    no_fixed_gamma: bool = False
    no_alpha_noise: bool = False
    greedy_decode_vs_beam: bool = False

    model_version: str = "v5_final"
    architecture: str = "memory_augmented_ar_planner"

    def __post_init__(self) -> None:
        if self.vocab_size <= 0:
            raise ValueError("vocab_size must be positive")
        if self.d_model <= 0 or self.d_key <= 0:
            raise ValueError("d_model and d_key must be positive")
        if self.n_heads <= 0 or self.d_model % self.n_heads != 0:
            raise ValueError("d_model must be divisible by n_heads")
        if self.max_seq_len <= 0:
            raise ValueError("max_seq_len must be positive")
        if not 0.0 <= self.alpha_noise_p <= 1.0:
            raise ValueError("alpha_noise_p must be in [0, 1]")
        if self.gamma != 0.3:
            raise ValueError("V5_final uses fixed gamma=0.3")
        if self.rho != 1.5:
            raise ValueError("V5_final uses fixed rho=1.5")

    @property
    def resolved_end_token_id(self) -> int:
        return self.end_token_id if self.end_token_id >= 0 else self.vocab_size - 1

    @property
    def resolved_pad_token_id(self) -> int:
        return self.pad_token_id if self.pad_token_id >= 0 else self.vocab_size - 2

    def to_dict(self) -> dict:
        payload = asdict(self)
        payload["end_token_id"] = self.resolved_end_token_id
        payload["pad_token_id"] = self.resolved_pad_token_id
        return payload

    @classmethod
    def from_dict(cls, payload: dict) -> "V5FinalConfig":
        allowed = {field for field in cls.__dataclass_fields__}
        return cls(**{key: value for key, value in dict(payload).items() if key in allowed})

    def checkpoint_v5_config(self) -> dict:
        payload = self.to_dict()
        return {
            **payload,
            "gamma": 0.3,
            "rho": 1.5,
            "alpha_noise_p": self.alpha_noise_p,
            "graph_threshold_tau": self.graph_threshold_tau,
            "d_k": self.d_key,
        }
