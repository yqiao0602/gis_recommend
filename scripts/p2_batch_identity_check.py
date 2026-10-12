#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Batched-vs-bs1 identity check on first 16 dev rows (same adapter).
Pass criterion: pred_text identical for all rows; report GPU peak."""
import json, argparse
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from peft import PeftModel

ap = argparse.ArgumentParser()
ap.add_argument("--adapter", required=True)
ap.add_argument("--n", type=int, default=16)
ap.add_argument("--bs", type=int, default=8)
a = ap.parse_args()

BASE = "/home/qy/models/Qwen3.5/Qwen3.5-9B-Base"
EVAL = "/home/qy/planner_v2_dev.jsonl"
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

rows = [json.loads(l) for l in open(EVAL, encoding="utf-8")][:a.n]

def gen_bs1(enc_ids):
    ids = torch.tensor([enc_ids], device="cuda:0")
    g = model.generate(input_ids=ids, attention_mask=torch.ones_like(ids),
                       max_new_tokens=384, do_sample=False,
                       eos_token_id=[tok.eos_token_id, tok.pad_token_id],
                       pad_token_id=tok.pad_token_id)
    return g[0][ids.shape[1]:]

def gen_batch(enc_list):
    maxlen = max(len(e) for e in enc_list)
    pad_id = tok.pad_token_id
    input_ids = [[pad_id] * (maxlen - len(e)) + e for e in enc_list]
    attn = [[0] * (maxlen - len(e)) + [1] * len(e) for e in enc_list]
    batch = {"input_ids": torch.tensor(input_ids, device="cuda:0"),
             "attention_mask": torch.tensor(attn, device="cuda:0")}
    g = model.generate(**batch, max_new_tokens=384, do_sample=False,
                       eos_token_id=[tok.eos_token_id, tok.pad_token_id],
                       pad_token_id=pad_id)
    return g, maxlen

encs = [tok(r["task"] + SEP, truncation=True, max_length=1024)["input_ids"]
        for r in rows]
out1, outb = [], []
with torch.no_grad():
    for e in encs:
        out1.append(tok.decode(gen_bs1(e), skip_special_tokens=True))
    for s in range(0, len(encs), a.bs):
        g, ml = gen_batch(encs[s:s + a.bs])
        for j in range(g.shape[0]):
            outb.append(tok.decode(g[j][ml:], skip_special_tokens=True))

mism = [i for i in range(len(rows)) if out1[i] != outb[i]]
peak = torch.cuda.max_memory_allocated() / 2**30
json.dump({"out_bs1": out1, "out_batch": outb},
          open("/home/qy/identity_check_preds.json", "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
res = {"n": len(rows), "bs": a.bs, "mismatches": len(mism),
       "mismatch_idx": mism, "gpu_peak_gib": round(peak, 2)}
print(json.dumps(res, indent=1))
