#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R3-PLANNER-V2 SMOKE evaluator (diagnostic, not the frozen gate evaluator).

S1 JSON compliance + schema validity
S2 Ordered stage LCS-F1 / exact / first-stage acc (order sensitivity)
S3 Repetition-presence F1 (per-family signature; no absolute-count scoring)
S4 unspecified rate in predicted hints (abuse check)
S5 hint-family correspondence (per_band<->BAND_*, per_class<->CLASSIFICATION,
   per_year<->TEMPORAL_FILTER; mismatches = shortcut flags)
E4 predicted repeat-number distribution vs gold (diagnostic, unscored)
"""
import json, re, sys, statistics as st
from collections import Counter, defaultdict
sys.path.insert(0, "/root/system_redesign")
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from peft import PeftModel

BASE = "/root/models/Qwen3.5-9B-Base"
ADAPTER = sys.argv[1] if len(sys.argv) > 1 else "/root/data/stage1_run_planner_v2_smoke/stage1_adapter"
EVAL = "/root/data/planner_v2_smoke_eval.jsonl"
OUT = sys.argv[2] if len(sys.argv) > 2 else "/root/data/planner_v2_smoke_eval_metrics.json"
SEP = "\nWorkflow blueprint: output JSON with keys stages (ordered semantic stages with per-stage repeat counts) and repetition_groups (groups with repeat>1, each with iteration_hint from: per_band, per_class, per_year, per_feature, generic_each, unspecified)."
FAMS = {"ATTRIBUTE_FILTER","TEMPORAL_FILTER","SPATIAL_FILTER","BAND_SELECT","BAND_ARITHMETIC",
        "SPECTRAL_INDEX","THRESHOLD_LOGIC","MASKING","AGGREGATION","REGIONAL_STATS",
        "CLASSIFICATION","SPATIAL_CLIP","VECTOR_GEOMETRY","NEIGHBORHOOD","TERRAIN_DERIVED",
        "COMPOSITE","SPATIAL_JOIN","RESAMPLE_REPROJECT","EXPORT_OUTPUT","COLLECTION_MGMT",
        "ITERATIVE_APPLY","SAMPLE_EXTRACTION","RASTER_LOAD","VECTOR_LOAD","GEOMETRY_DEFINE",
        "PROVISION","OTHER"}
HINT_FAM = {"per_band": {"BAND_SELECT","BAND_ARITHMETIC"},
            "per_class": {"CLASSIFICATION"},
            "per_year": {"TEMPORAL_FILTER"}}

def lcs_len(a, b):
    if not a or not b: return 0
    prev = [0]*(len(b)+1)
    for i in range(1, len(a)+1):
        cur = [0]*(len(b)+1); ai = a[i-1]
        for j in range(1, len(b)+1):
            cur[j] = prev[j-1]+1 if ai == b[j-1] else max(prev[j], cur[j-1])
        prev = cur
    return prev[-1]

def ordered_f1(pred, gold):
    L = lcs_len(pred, gold)
    p = L/len(pred) if pred else 0.0
    r = L/len(gold) if gold else 0.0
    return round(2*p*r/(p+r), 3) if p+r else 0.0

def extract_json(text):
    m = re.search(r"\{.*\}", text, re.S)
    if not m: return None
    try: return json.loads(m.group(0))
    except Exception: return None

tok = AutoTokenizer.from_pretrained(BASE, trust_remote_code=True)
bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16,
                         bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True)
model = AutoModelForCausalLM.from_pretrained(BASE, trust_remote_code=True,
        torch_dtype=torch.bfloat16, device_map="cuda:0", quantization_config=bnb)
model = PeftModel.from_pretrained(model, ADAPTER); model.eval()

rows = [json.loads(l) for l in open(EVAL, encoding="utf-8")]
s1_parse = s1_schema = 0
e1_f1 = []; s2_first = 0; s2_exact = 0
s3_f1 = []
s4_unspec_groups = s4_groups = 0
s5_consistent = s5_hinted = 0
rep_pred_all, rep_gold_all = [], []
items = []
with torch.no_grad():
    for k, r in enumerate(rows):
        gold = json.loads(r["target"])
        enc = tok(r["task"] + SEP, return_tensors="pt", truncation=True, max_length=1024).to("cuda:0")
        g = model.generate(**enc, max_new_tokens=384, do_sample=False,
                           eos_token_id=[tok.eos_token_id, tok.pad_token_id],
                           pad_token_id=tok.pad_token_id)
        text = tok.decode(g[0][enc["input_ids"].shape[1]:], skip_special_tokens=True)
        bp = extract_json(text)
        parse_ok = bp is not None
        schema_ok = False
        pred_stages, gold_stages = [], []
        if parse_ok:
            s1_parse += 1
            stg = bp.get("stages")
            if isinstance(stg, list) and stg and all(isinstance(s, dict) and "family" in s for s in stg):
                s1_schema += 1; schema_ok = True
                pred_stages = [str(s.get("family")) for s in stg if str(s.get("family")) in FAMS]
                gold_stages = [str(s.get("family")) for s in gold.get("stages", [])]
                e1_f1.append(ordered_f1(pred_stages, gold_stages))
                if pred_stages and gold_stages and pred_stages[0] == gold_stages[0]: s2_first += 1
                if pred_stages == gold_stages: s2_exact += 1
                pf = {s["family"] for s in stg if s.get("repeat", 1) > 1}
                gf = {s["family"] for s in gold.get("stages", []) if s.get("repeat", 1) > 1}
                tp3 = len(pf & gf)
                p3 = tp3/len(pf) if pf else 0.0
                r3 = tp3/len(gf) if gf else 0.0
                s3_f1.append(round(2*p3*r3/(p3+r3),3) if p3+r3 else 1.0)
                rg = bp.get("repetition_groups")
                if isinstance(rg, list):
                    for grp in rg:
                        if not isinstance(grp, dict): continue
                        s4_groups += 1
                        h = grp.get("iteration_hint") or []
                        if "unspecified" in h and len(h) == 1: s4_unspec_groups += 1
                        fam = str(grp.get("family", ""))
                        for hdim in h:
                            if hdim in HINT_FAM:
                                s5_hinted += 1
                                if fam in HINT_FAM[hdim]: s5_consistent += 1
                for s in stg:
                    if isinstance(s, dict) and isinstance(s.get("repeat"), int):
                        rep_pred_all.append(s["repeat"])
                for s in gold.get("stages", []):
                    rep_gold_all.append(s.get("repeat", 1))
        items.append({"k": k, "parse_ok": parse_ok, "schema_ok": schema_ok,
                      "pred": text[:800], "e1": e1_f1[-1] if e1_f1 else None})
        if (k+1) % 50 == 0:
            print(f"{k+1}/{len(rows)} parse={s1_parse/(k+1):.3f} schema={s1_schema/(k+1):.3f} "
                  f"e1={st.mean(e1_f1):.3f}", flush=True)

n = len(rows)
def hist(xs):
    c = Counter(xs)
    return dict(sorted(c.items())[:12])
res = {
    "rows": n,
    "S1_parse_rate": round(s1_parse/n, 4),
    "S1_schema_rate": round(s1_schema/n, 4),
    "S2_ordered_stage_f1_mean": round(st.mean(e1_f1), 4) if e1_f1 else None,
    "S2_first_stage_acc": round(s2_first/max(1,s1_schema), 4),
    "S2_exact_seq_rate": round(s2_exact/max(1,s1_schema), 4),
    "S3_repetition_presence_f1": round(st.mean(s3_f1), 4) if s3_f1 else None,
    "S4_unspecified_group_rate": round(s4_unspec_groups/max(1,s4_groups), 4) if s4_groups else None,
    "S5_hint_consistency": {"hinted": s5_hinted, "consistent": s5_consistent,
                             "rate": round(s5_consistent/s5_hinted, 3) if s5_hinted else None},
    "E4_repeat_pred_mean": round(st.mean(rep_pred_all), 2) if rep_pred_all else None,
    "E4_repeat_gold_mean": round(st.mean(rep_gold_all), 2) if rep_gold_all else None,
    "E4_repeat_pred_hist_top": hist(rep_pred_all),
    "E4_repeat_gold_hist_top": hist(rep_gold_all),
}
json.dump({"metrics": res, "items": items}, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False, indent=1))
