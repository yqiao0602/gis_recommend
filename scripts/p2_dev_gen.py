#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2 eval generation: dev-1852, frozen instrument (same SEP / greedy 384 /
max_length 1024 truncation as P0 & P1 dev runs). Only addition: per-row
gen_tokens + hit_cap recording (owner reporting requirement). No change to
generation or parsing logic.

Usage: p2_dev_gen.py --adapter DIR --out FILE
"""
import json, argparse
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from peft import PeftModel

ap = argparse.ArgumentParser()
ap.add_argument("--adapter", required=True)
ap.add_argument("--out", required=True)
a = ap.parse_args()

BASE = "/home/qy/models/Qwen3.5/Qwen3.5-9B-Base"
EVAL = "/home/qy/planner_v2_dev.jsonl"
SEP = "\nWorkflow blueprint: output JSON with keys stages (ordered semantic stages with per-stage repeat counts) and repetition_groups (groups with repeat>1, each with iteration_hint from: per_band, per_class, per_year, per_feature, generic_each, unspecified)."

tok = AutoTokenizer.from_pretrained(BASE, trust_remote_code=True)
bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16,
                         bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True)
model = AutoModelForCausalLM.from_pretrained(BASE, trust_remote_code=True,
        torch_dtype=torch.bfloat16, device_map="cuda:0", quantization_config=bnb)
model = PeftModel.from_pretrained(model, a.adapter); model.eval()

rows = [json.loads(l) for l in open(EVAL, encoding="utf-8")]
items = []
with torch.no_grad():
    for k, r in enumerate(rows):
        enc = tok(r["task"] + SEP, return_tensors="pt", truncation=True,
                  max_length=1024).to("cuda:0")
        g = model.generate(**enc, max_new_tokens=384, do_sample=False,
                           eos_token_id=[tok.eos_token_id, tok.pad_token_id],
                           pad_token_id=tok.pad_token_id)
        n_new = int(g.shape[1] - enc["input_ids"].shape[1])
        text = tok.decode(g[0][enc["input_ids"].shape[1]:],
                          skip_special_tokens=True)
        items.append({"k": k, "task_head": r["task"][:80], "pred_text": text,
                      "gen_tokens": n_new, "hit_cap": int(n_new >= 384)})
        if (k + 1) % 100 == 0:
            print(f"{k+1}/{len(rows)}", flush=True)
json.dump({"rows": len(rows), "adapter": a.adapter, "max_new_tokens": 384,
           "items": items}, open(a.out, "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("saved:", a.out)
