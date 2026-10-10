#!/usr/bin/env python3
"""Planner-v2 P0-B decode-only sweep; one variable: max_new_tokens."""
import argparse, json, time
from pathlib import Path
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from peft import PeftModel

ap = argparse.ArgumentParser()
ap.add_argument('--base', required=True)
ap.add_argument('--adapter', required=True)
ap.add_argument('--eval', required=True)
ap.add_argument('--out', required=True)
ap.add_argument('--max-new-tokens', type=int, required=True)
a = ap.parse_args()
out = Path(a.out); out.mkdir(parents=True, exist_ok=True)
sep = "\nWorkflow blueprint: output JSON with keys stages (ordered semantic stages with per-stage repeat counts) and repetition_groups (groups with repeat>1, each with iteration_hint from: per_band, per_class, per_year, per_feature, generic_each, unspecified)."
tok = AutoTokenizer.from_pretrained(a.base, trust_remote_code=True)
bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16,
                         bnb_4bit_quant_type='nf4', bnb_4bit_use_double_quant=True)
model = AutoModelForCausalLM.from_pretrained(a.base, trust_remote_code=True,
        torch_dtype=torch.bfloat16, device_map='cuda:0', quantization_config=bnb)
model = PeftModel.from_pretrained(model, a.adapter); model.eval()
rows = [json.loads(l) for l in open(a.eval, encoding='utf-8')]
items=[]; t0=time.time()
with torch.no_grad():
    for k,r in enumerate(rows):
        enc=tok(r['task']+sep, return_tensors='pt', truncation=True, max_length=1024).to('cuda:0')
        g=model.generate(**enc, max_new_tokens=a.max_new_tokens, do_sample=False,
                         eos_token_id=[tok.eos_token_id, tok.pad_token_id], pad_token_id=tok.pad_token_id)
        text=tok.decode(g[0][enc['input_ids'].shape[1]:], skip_special_tokens=True)
        items.append({'k':k,'task_head':r['task'][:80],'pred_text':text,
                      'generated_tokens':int(g.shape[1]-enc['input_ids'].shape[1]),
                      'hit_max_new_tokens':int(g.shape[1]-enc['input_ids'].shape[1] >= a.max_new_tokens)})
        if (k+1)%100==0: print(f'{k+1}/{len(rows)}',flush=True)
json.dump({'rows':len(rows),'max_new_tokens':a.max_new_tokens,'do_sample':False,
           'items':items,'elapsed_s':round(time.time()-t0,1)},
          open(out/'predictions.json','w',encoding='utf-8'),ensure_ascii=False,indent=1)
print('saved',out/'predictions.json',flush=True)
