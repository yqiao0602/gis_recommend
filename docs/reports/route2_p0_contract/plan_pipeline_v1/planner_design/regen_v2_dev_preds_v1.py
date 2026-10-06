#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Regenerate Planner-v2 formal dev predictions with FULL pred_seq saved.
GPU generation only (no training). Output feeds planner_unified_eval_v1.py.
"""
import json, sys, statistics as st
sys.path.insert(0, "/root/system_redesign")
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from peft import PeftModel

BASE = "/root/models/Qwen3.5-9B-Base"
ADAPTER = "/root/data/stage1_run_planner_v2/stage1_adapter"
EVAL = "/root/data/planner_v2_dev.jsonl"
OUT = "/root/data/planner_v2_dev_full_preds.json"
SEP = "\nWorkflow blueprint: output JSON with keys stages (ordered semantic stages with per-stage repeat counts) and repetition_groups (groups with repeat>1, each with iteration_hint from: per_band, per_class, per_year, per_feature, generic_each, unspecified)."

tok = AutoTokenizer.from_pretrained(BASE, trust_remote_code=True)
bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16,
                         bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True)
model = AutoModelForCausalLM.from_pretrained(BASE, trust_remote_code=True,
        torch_dtype=torch.bfloat16, device_map="cuda:0", quantization_config=bnb)
model = PeftModel.from_pretrained(model, ADAPTER); model.eval()

rows = [json.loads(l) for l in open(EVAL, encoding="utf-8")]
items = []
with torch.no_grad():
    for k, r in enumerate(rows):
        enc = tok(r["task"] + SEP, return_tensors="pt", truncation=True, max_length=1024).to("cuda:0")
        g = model.generate(**enc, max_new_tokens=384, do_sample=False,
                           eos_token_id=[tok.eos_token_id, tok.pad_token_id],
                           pad_token_id=tok.pad_token_id)
        text = tok.decode(g[0][enc["input_ids"].shape[1]:], skip_special_tokens=True)
        items.append({"k": k, "task_head": r["task"][:80], "pred_text": text})
        if (k+1) % 100 == 0: print(f"{k+1}/{len(rows)}", flush=True)
json.dump({"rows": len(rows), "items": items}, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("saved:", OUT)
