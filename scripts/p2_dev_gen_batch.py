#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P2 eval generation, BATCHED (left padding). Same frozen instrument as the
bs=1 runs: task+SEP prompt, per-row truncation max_length 1024, greedy,
max_new_tokens 384, eos=[eos,pad]. Change vs p2_dev_gen.py: batching for
throughput (all arms use this same script — instrument symmetric across
P0/P1/P2). Records gen_tokens + hit_cap per row.

Usage: p2_dev_gen_batch.py --adapter DIR --out FILE [--bs 8]
"""
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

rows = [json.loads(l) for l in open(EVAL, encoding="utf-8")]
items = []
t0 = time.time()
done = 0
with torch.no_grad():
    for s in range(0, len(rows), a.bs):
        chunk = rows[s:s + a.bs]
        encs = [tok(r["task"] + SEP, return_tensors=None, truncation=True,
                    max_length=1024)["input_ids"] for r in chunk]
        maxlen = max(len(e) for e in encs)
        # manual LEFT padding to batch max (identical per-row tokenization
        # to the bs=1 instrument; no re-truncation from padding)
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
            items.append({"k": s + j, "task_head": r["task"][:80],
                          "pred_text": text, "gen_tokens": n_new,
                          "hit_cap": int(n_new >= 384)})
        done += len(chunk)
        if done % 400 < a.bs:
            rate = done / (time.time() - t0)
            print(f"{done}/{len(rows)} rows, {rate:.2f} rows/s, "
                  f"eta {(len(rows) - done) / rate / 60:.0f} min", flush=True)

json.dump({"rows": len(rows), "adapter": a.adapter, "max_new_tokens": 384,
           "batch_size": a.bs, "instrument": "batched-left-pad",
           "items": items}, open(a.out, "w", encoding="utf-8"),
          ensure_ascii=False, indent=1)
print("saved:", a.out)
