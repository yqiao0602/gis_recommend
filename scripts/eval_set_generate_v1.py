#!/usr/bin/env python3
"""S2 dry-run generation for the RL line (24 tasks x 8 candidates, NO training).

Protocol: RL_LINE_PREREGISTRATION_V1_CANDIDATE.md section 4.4 (S2) + owner
round-4 rulings: provisional_vocab23 diagnostic dry run; no parameter updates.
Decode: do_sample=True (group diversity for GRPO-style diagnostics),
temperature=1.0, top_p=1.0, repetition_penalty=1.15 (protocol-pinned),
max_new_tokens=768, seed 20261013. Prompt = task + SEP, byte-identical to
p0b2_arms.py (the P0-B2 instrument).
"""
import json, random, time, hashlib
from pathlib import Path
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from peft import PeftModel

BASE = "/home/qy/models/Qwen3.5/Qwen3.5-9B-Base"
ADAPTER = "/home/qy/stage1_run_planner_v2_fmt/stage1_adapter"
TRAIN = "/home/qy/rl_eval_set/eval_set_24_tasks.jsonl"
OUT = Path("/home/qy/rl_eval_set")
SEED = 20261013
K = 8
MAX_NEW = 768
REP_PEN = 1.15
TEMP = 1.0
TOP_P = 1.0
SEP = "\nWorkflow blueprint: output JSON with keys stages (ordered semantic stages with per-stage repeat counts) and repetition_groups (groups with repeat>1, each with iteration_hint from: per_band, per_class, per_year, per_feature, generic_each, unspecified)."

random.seed(SEED)
torch.manual_seed(SEED)


def sha256(p):
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ---- task selection: the FROZEN eval set (already stratified at procurement;
# do NOT re-stratify or re-sample here) ----
rows = []
with open(TRAIN) as f:
    for i, line in enumerate(f):
        r = json.loads(line)
        rows.append({"idx": i, "script": r["script"], "task": r["task"],
                     "band": r.get("band", ""),
                     "n_stages": r.get("final_semantic_length", 0)})
bands = {"short_2_4": [r for r in rows if r["band"] == "short_2_4"],
         "mid_5_8": [r for r in rows if r["band"] == "mid_5_8"],
         "long_9plus": [r for r in rows if r["band"] == "long_9plus"]}
selected = list(rows)
print(f"selected {len(selected)} tasks: "
      f"{ {b: len(bands[b]) for b in bands} } pools", flush=True)

# ---- model ----
tok = AutoTokenizer.from_pretrained(BASE, trust_remote_code=True)
if tok.pad_token is None:
    tok.pad_token = tok.eos_token
tok.padding_side = "left"
bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16,
                         bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True)
model = AutoModelForCausalLM.from_pretrained(BASE, trust_remote_code=True,
        torch_dtype=torch.bfloat16, device_map="cuda:0", quantization_config=bnb)
model = PeftModel.from_pretrained(model, ADAPTER)
model.eval()
print("model loaded", flush=True)


def gen_batch(prompts, bs):
    enc = tok(prompts, return_tensors="pt", truncation=True,
              max_length=1024 - MAX_NEW).to("cuda:0")
    with torch.no_grad():
        out = model.generate(**enc, do_sample=True, temperature=TEMP,
                             top_p=TOP_P, repetition_penalty=REP_PEN,
                             max_new_tokens=MAX_NEW,
                             pad_token_id=tok.pad_token_id)
    n_in = enc["input_ids"].shape[1]
    texts = tok.batch_decode(out[:, n_in:], skip_special_tokens=True)
    new_tokens = int((out.shape[1] - n_in) * len(prompts))
    return texts, new_tokens


# ---- generation: one batch = K candidates of one task; OOM -> split to K/2 ----
results = []
t_start = time.time()
gen_tokens_total = 0
for bi, r in enumerate(selected):
    prompt = r["task"] + SEP
    torch.manual_seed(SEED + 1000 + bi)
    t0 = time.time()
    try:
        texts, new_tokens = gen_batch([prompt] * K, K)
    except torch.cuda.OutOfMemoryError:
        torch.cuda.empty_cache()
        print(f"batch {bi+1}: OOM at bs={K}, retry split bs={K//2}", flush=True)
        texts, new_tokens = [], 0
        for half in range(2):
            torch.manual_seed(SEED + 1000 + bi + 100 * (half + 1))
            t2, nt = gen_batch([prompt] * (K // 2), K // 2)
            texts.extend(t2)
            new_tokens += nt
    dt = time.time() - t0
    gen_tokens_total += new_tokens
    for ci, txt in enumerate(texts):
        results.append({"k": r["script"], "cand": ci, "band": r["band"],
                        "n_stages_gold": r["n_stages"],
                        "task_head": r["task"][:80], "pred_text": txt})
    print(f"batch {bi+1}/24 band={r['band']} gold_ns={r['n_stages']} "
          f"{dt:.1f}s new_tok={new_tokens}", flush=True)

wall = time.time() - t_start
peak = torch.cuda.max_memory_allocated() / (1 << 20)
json.dump(results, open(OUT / "preds.json", "w"), ensure_ascii=False)
config = {
    "label": "eval_set_generation_never_trained_tasks_no_training",
    "base": BASE, "adapter": ADAPTER,
    "base_config_sha256": sha256(BASE + "/config.json"),
    "adapter_model_sha256": sha256(ADAPTER + "/adapter_model.safetensors"),
    "tasks_sha256": sha256(TRAIN),
    "seed": SEED, "k": K, "max_new_tokens": MAX_NEW,
    "repetition_penalty": REP_PEN, "temperature": TEMP, "top_p": TOP_P,
    "do_sample": True, "truncation": "max_length 1024-MAX_NEW, right side",
    "prompt_format": "task + SEP (identical to p0b2_arms.py)",
    "n_tasks": len(selected),
    "stratification": {b: 8 for b in ["short_2_4", "mid_5_8", "long_9plus"]},
    "wall_seconds": round(wall, 1),
    "gen_tokens_total": gen_tokens_total,
    "tokens_per_sec_all_candidates": round(gen_tokens_total / wall, 2),
    "peak_cuda_MiB": round(peak, 1),
}
json.dump(config, open(OUT / "config.json", "w"), ensure_ascii=False, indent=2)
print("DONE wall=%.1fs tokens=%d tps=%.2f peakMiB=%.0f"
      % (wall, gen_tokens_total, gen_tokens_total / wall, peak), flush=True)
