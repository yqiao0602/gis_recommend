# Qwen3.5-9B-Base on A10: E3 smoke + E4 overfit gate — both PASSED

## E3: QLoRA smoke 9/9 (Qwen3.5-9B-Base, HF original weights)

Environment: new isolated `qwen35` conda env — torch 2.5.1+cu121, transformers
5.16.1 (has `qwen3_5` model class incl. pure-torch GatedDeltaNet fallback), peft
0.20.0, bitsandbytes 0.50.2. The two 2.2.2-era environments are untouched.

| Step | Time | Detail |
|---|---:|---|
| 1 HF safetensors load | 0.0s | 4 shards, 19.3 GB |
| 2 tokenizer | 0.7s | vocab 248,044 |
| 3 NF4 4-bit load | 25.9s | 7.19 GB weights on cuda:0 |
| 4 forward | 1.67s | logits [1,11,248320] |
| 5 backward | 1.03s | loss 3.905 finite, 179 grad tensors |
| 6 gradient accumulation | 2.09s | finite |
| 7 LoRA save | 0.22s | adapter saved |
| 8 checkpoint reload | 3.93s | 32 lora_A tensors byte-identical |
| 9 generation | 1.34s | 50 chars |
| **peak** | | **18.13 GB / 23 GB** |

## E4: 100-sample overfit gate — PASSED

100 paper_v1 train rows (60 GEE + 40 QGIS, seed 20260907), task text → L3 chain,
NF4 + r16 LoRA (q/k/v/o) + gradient checkpointing, 40 epochs:

- **first loss 0.788 → last loss 0.0000 (100% reduction)**
- **probe: exact L3-chain reproduction 10/10 in-training rows**
- 28.6 minutes wall, peak 12.74 GB
- Verdict: the model demonstrably learns the task format through the full
  QLoRA stack — the M3/M2 training gates are open.

## Fixes applied during setup (recorded for provenance)

- transformers 5.16.1 requires bitsandbytes ≥0.46.1 → upgraded to 0.50.2 (wheel
  transferred locally; server PyPI mirror was serving at 38 KB/s).
- Download set corrections: the correct shard-index filename is
  `model.safetensors.index.json` (dot, not hyphen); `generation_config.json` /
  `special_tokens_map.json` / `added_tokens.json` do not exist in these repos
  (hf-mirror 404 bodies had been saved as those files by the download script);
  `preprocessor_config.json`, `video_preprocessor_config.json`, and
  `chat_template.jinja` (post-trained only) were added. All 8 safetensors shards
  (2 models × 4) match index sizes exactly.
- Two parallel pip processes overwrote each other's bnb install — resolved by
  a forced reinstall after both finished.

## Downloads (complete, 04:57)

`/home/qy/models/Qwen3.5/Qwen3.5-9B-Base` and `/home/qy/models/Qwen3.5/Qwen3.5-9B`
— original HF safetensors (BF16, 19.3 GB each) via hf-mirror with resume/retry;
the local ollama GGUF remains inference-only. The auto-pipeline watcher fired
early (before the env was ready) and failed; smoke and overfit were rerun
manually after the environment completed.
