#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R3-PLANNER-P0 evaluator (diagnostic tool, NOT the frozen gate evaluator).

Generates blueprints for the held-out eval rows with the trained adapter, then:
  M1 blueprint parse rate
  M2 family bag-F1 vs gold (evaluator-replicated overlap_counts/f1_from_counts)
  M3 per-family count exact-match rate (over gold-present families)
  M4 length exact / +-1 accuracy
Run on the rented server with /root/venv_qwen35/bin/python.
"""
import json, re, sys, statistics as st
from collections import Counter
sys.path.insert(0, "/root/system_redesign")
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM
from peft import PeftModel

BASE = "/root/models/Qwen3.5-9B-Base"
ADAPTER = sys.argv[1] if len(sys.argv) > 1 else "/root/data/stage1_run_planner_p0/stage1_adapter"
EVAL = "/root/data/planner_p0_eval.jsonl"
OUT = "/root/data/planner_p0_eval_metrics.json"
SEP = "\nWorkflow blueprint: output JSON with keys families (first-use order), counts (times each family is used), length (total steps)."

def overlap_counts(pred, gold):
    rest = list(gold); tp = 0
    for x in pred:
        if x in rest: tp += 1; rest.remove(x)
    return tp, len(pred), len(gold)

def bag_f1(pred, gold):
    tp, np_, ng = overlap_counts(pred, gold)
    return 1.0 if np_ + ng == 0 else (2*tp/(np_+ng) if tp else 0.0)

def extract_json(text):
    m = re.search(r"\{.*\}", text, re.S)
    if not m: return None
    try: return json.loads(m.group(0))
    except Exception: return None

tok = AutoTokenizer.from_pretrained(BASE, trust_remote_code=True)
from transformers import BitsAndBytesConfig
bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16,
                         bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True)
model = AutoModelForCausalLM.from_pretrained(BASE, trust_remote_code=True,
        torch_dtype=torch.bfloat16, device_map="cuda:0", quantization_config=bnb)
model = PeftModel.from_pretrained(model, ADAPTER)
model.eval()

rows = [json.loads(l) for l in open(EVAL, encoding="utf-8")]
m1_parse = 0; f1s = []; cnt_exact = cnt_gold_fam = 0; len_exact = len_pm1 = 0
pred_len_list = []
parsed_blueprints = []
with torch.no_grad():
    for k, r in enumerate(rows):
        enc = tok(r["task"] + SEP, return_tensors="pt", truncation=True, max_length=1024).to("cuda:0")
        g = model.generate(**enc, max_new_tokens=192, do_sample=False,
                           eos_token_id=[tok.eos_token_id, tok.pad_token_id],
                           pad_token_id=tok.pad_token_id)
        text = tok.decode(g[0][enc["input_ids"].shape[1]:], skip_special_tokens=True)
        bp = extract_json(text)
        if bp is None:
            parsed_blueprints.append({"probe_id": k, "parse_ok": False}); continue
        m1_parse += 1
        fams = bp.get("families") or []
        counts = bp.get("counts") or {}
        length = bp.get("length")
        pred_seq = []
        for f in fams if isinstance(fams, list) else []:
            pred_seq += [f] * int(counts.get(f, 1)) if isinstance(counts, dict) else []
        gold_seq = []
        for f, c in json.loads(r["target"]).get("counts", {}).items():
            gold_seq += [f] * int(c)
        f1s.append(bag_f1(pred_seq, gold_seq))
        gp = json.loads(r["target"]).get("counts", {})
        for f, c in gp.items():
            cnt_gold_fam += 1
            cnt_exact += int(int(counts.get(f, 0)) == int(c))
        if isinstance(length, int):
            pred_len_list.append(length)
            len_exact += int(length == int(json.loads(r["target"])["length"]))
            len_pm1 += int(abs(length - int(json.loads(r["target"])["length"])) <= 1)
        parsed_blueprints.append({"probe_id": k, "parse_ok": True, "pred_seq": pred_seq,
                                  "pred_length": length, "f1": f1s[-1]})
        if (k+1) % 400 == 0:
            print(f"{k+1}/{len(rows)} done, running parse={m1_parse/(k+1):.3f} f1={st.mean(f1s):.3f}", flush=True)

res = {
    "rows": len(rows),
    "M1_parse_rate": round(m1_parse/len(rows), 4),
    "M2_family_bag_f1": round(st.mean(f1s), 4) if f1s else None,
    "M3_count_exact_rate": round(cnt_exact/cnt_gold_fam, 4) if cnt_gold_fam else None,
    "M4_length_exact": round(len_exact/len(rows), 4),
    "M4_length_pm1": round(len_pm1/len(rows), 4),
    "pred_length_mean": round(st.mean(pred_len_list), 2) if pred_len_list else None,
}
json.dump({"metrics": res, "items": parsed_blueprints}, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False, indent=1))
