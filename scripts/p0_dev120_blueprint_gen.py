#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Step 1 of the end-to-end mainline: generate and FREEZE P0 blueprint
predictions on dev-120 (v2a_A_dev.jsonl task_text). Frozen instrument:
task + SEP prompt, per-row truncation 1024, greedy, max_new_tokens 384,
batched left-padding (same as the three-way instrument). Records
gen_tokens + hit_cap. Output frozen by SHA256 after generation."""
import json, argparse, time
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from peft import PeftModel

ap = argparse.ArgumentParser()
ap.add_argument("--adapter", required=True)
ap.add_argument("--out", required=True)
ap.add_argument("--bs", type=int, default=8)
a = ap.parse_args()

BASE = "/home/qy/models/Qwen3.5/Qwen3.5-9B-Base"
EVAL = "/home/qy/gee_llm_smoke/v2a_A_dev.jsonl"
SEP = "\nWorkflow blueprint: output JSON with keys stages (ordered semantic stages with per-stage repeat counts) and repetition_groups (groups with repeat>1, each with iteration_hint from: per_band, per_class, per_year, per_feature, generic_each, unspecified)."

tok = AutoTokenizer.from_pretrained(BASE, trust_remote_code=True)
if tok.pad_token is None:
    tok.pad_token = tok.eos_token
tok.padding_side = "left"
bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16,
                         bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True)
model = AutoModelForCausalLM.from_pretrained(BASE, trust_remote_code=True,
        torch_dtype=torch.bfloat16, device_map="cuda:0", quantization_config=bnb)
model = PeftModel.from_pretrained(model, a.adapter); model.eval()

rows = [json.loads(l) for l in open(EVAL, encoding="utf-8")]
items = []
t0 = time.time()
with torch.no_grad():
    for s in range(0, len(rows), a.bs):
        chunk = rows[s:s + a.bs]
        encs = [tok(r["task_text"] + SEP, return_tensors=None, truncation=True,
                    max_length=1024)["input_ids"] for r in chunk]
        maxlen = max(len(e) for e in encs)
        pad_id = tok.pad_token_id
        input_ids = [[pad_id] * (maxlen - len(e)) + e for e in encs]
        attn = [[0] * (maxlen - len(e)) + [1] * len(e) for e in encs]
        batch = {"input_ids": torch.tensor(input_ids, device="cuda:0"),
                 "attention_mask": torch.tensor(attn, device="cuda:0")}
        g = model.generate(**batch, max_new_tokens=384, do_sample=False,
                           eos_token_id=[tok.eos_token_id, tok.pad_token_id],
                           pad_token_id=pad_id)
        for j, r in enumerate(chunk):
            n_new = int(g.shape[1] - maxlen)
            text = tok.decode(g[j][maxlen:], skip_special_tokens=True)
            items.append({"k": s + j, "wid": r["wid"],
                          "task_head": r["task_text"][:80],
                          "pred_text": text, "gen_tokens": n_new,
                          "hit_cap": int(n_new >= 384)})
        print(f"{s + len(chunk)}/{len(rows)} rows, "
              f"{(s + len(chunk)) / (time.time() - t0):.2f} rows/s", flush=True)

json.dump({"rows": len(rows), "adapter": a.adapter,
           "max_new_tokens": 384, "batch_size": a.bs,
           "instrument": "batched-left-pad", "source": EVAL,
           "items": items}, open(a.out, "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("saved:", a.out)
