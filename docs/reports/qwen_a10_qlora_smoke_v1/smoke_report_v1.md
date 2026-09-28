# A10 QLoRA smoke — 9/9 passed (Qwen2.5-7B stand-in)

Stage ③ of the model-experiment ladder: prove the training stack end-to-end
before any real training. All nine steps passed on the compute server's A10
(23 GB, fully free at start).

## Critical finding: Qwen3.5-9B cannot serve as the QLoRA base

The local `qwen3.5:9b` ollama weight (6.6 GB GGUF) is **not a standard
transformer**: its tensor layout (`ssm_a/alpha/beta/conv1d/dt` state-space
layers interleaved with attention, an `mtp.*` multi-token-prediction head, and
a `v.blk.*` vision tower) is a hybrid SSM+attention multimodal architecture.
`transformers` 4.57.5 has no `qwen35` model class (verified:
`ValueError: GGUF model with architecture qwen35 is not supported yet`), and
supporting it would mean implementing the SSM scan, MTP head, and vision tower
from scratch. The experiment matrix's "Qwen3.5-9B" therefore needs a
replacement base; this smoke validates the stack on the standard-architecture
**Qwen2.5-7B** already on disk (`/data/llms/Qwen2.5/7b`, 15 GB HF safetensors).
The QLoRA pipeline itself (NF4 + peft + A10) is model-agnostic, so everything
proven here transfers to whichever base the user selects.

## Results (Qwen2.5-7B, NF4, r=16 LoRA on q/k/v/o)

| Step | Time | Detail |
|---|---:|---|
| 1 HF-format load | 0.0s | already HF safetensors |
| 2 tokenizer round-trip | 0.26s | vocab 151,643, CJK OK |
| 3 NF4 4-bit load | 7.13s | 6.59 GB weights on cuda:0 |
| 4 forward | 0.41s | logits [1,11,152064] |
| 5 backward | 0.24s | loss 4.19 finite, 143 grad tensors |
| 6 gradient accumulation | 0.58s | 3-step accumulated grads finite |
| 7 LoRA checkpoint save | 0.92s | adapter saved |
| 8 checkpoint reload | 7.54s | 112 lora_A tensors, byte-identical after reload |
| 9 generation | 1.37s | 55 chars generated |

**Peak memory 12.86 GB of 23 GB** — comfortable headroom for longer sequences
and larger LoRA ranks. Environment: torch 2.2.2+cu121, transformers 4.57.5,
peft 0.20.0, bitsandbytes 0.45.0 (wheel transferred locally because the
server's mirror was timing out on the 43 MB download).

Script: `scripts/qwen_a10_qlora_smoke.py` (uploaded to
`/home/qy/gee_llm_smoke/` on the server). Result ledger:
`smoke_results_v1.json`, hash-pinned in this directory.

## Next

- **Base-model decision (user)**: Qwen2.5-7B (validated here, on disk),
  Qwen2.5-14B (on disk, needs an NF4 memory check), or a download of
  Qwen3-8B from HF. Qwen3.5-9B is not usable with the standard stack.
- **④ 100-sample overfit** on paper_v1 rows — ready to run on whichever base is
  chosen; the data path and LoRA config are proven.
