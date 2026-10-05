#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""C1-2a: Zero-shot cross-platform reasoning transfer assay (no training).

Planner-v2 (GEE-trained) generates semantic stage plans for QGIS task texts
(v2a_A dev+test, 231 rows, all OOD). Gold = QGIS operator sequences mapped to
semantic families via the transfer-audit keyword rules (69.7% coverage).
Three references: trivial modal baseline / in-domain 0.6636 / C0 0.343.
"""
import json, re, sys, statistics as st
from collections import Counter, defaultdict
sys.path.insert(0, "/root/system_redesign")
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from peft import PeftModel

BASE = "/root/models/Qwen3.5-9B-Base"
ADAPTER = sys.argv[1] if len(sys.argv) > 1 else "/root/data/stage1_run_planner_v2/stage1_adapter"
OUT = sys.argv[2] if len(sys.argv) > 2 else "/root/data/c12a_zero_shot_metrics.json"
SEP = "\nWorkflow blueprint: output JSON with keys stages (ordered semantic stages with per-stage repeat counts) and repetition_groups (groups with repeat>1, each with iteration_hint from: per_band, per_class, per_year, per_feature, generic_each, unspecified)."

OP_MAP = [
    (r"reproject|warpreproject|warp", "RESAMPLE_REPROJECT"),
    (r"slope|aspect|\btri\b|tiri|ruggedness|hillshade|relief", "TERRAIN_DERIVED"),
    (r"reclassif", "THRESHOLD_LOGIC"),
    (r"rastercalc|calculator|r\.mapcalc", "BAND_ARITHMETIC"),
    (r"ndvi|ndwi|evi|savi|nbr|index", "SPECTRAL_INDEX"),
    (r"fieldcalc|refactorfields", "VECTOR_GEOMETRY"),
    (r"buffer|dissolve|centroids|simplify|smooth|voronoi|difference\b|intersection\b|union\b|polygonize|polygonstolines|fixgeometries|multipart|singlepart|subdivide|line.?merge|export", "VECTOR_GEOMETRY"),
    (r"\bclip\b|extractbylocation|clipvectorbyraster|extractbyextent", "SPATIAL_CLIP"),
    (r"merge|concatenate|mosaic|buildvrt|pansharp", "COMPOSITE"),
    (r"join\w*by\w*(field|location|attribute)|hublines|nearestneighbour|joinattributestable", "SPATIAL_JOIN"),
    (r"zonal|statistics|r\.stats|sample", "REGIONAL_STATS"),
    (r"classify|randomforest|svm|maxent|train|predict|cluster", "CLASSIFICATION"),
    (r"extractbyexpression|selectbyexpression|extractbyattribute", "ATTRIBUTE_FILTER"),
    (r"temporal|date|time", "TEMPORAL_FILTER"),
    (r"extent|boundary|filterbyextent", "SPATIAL_FILTER"),
    (r"translate|aopleft|aopright|subset_bands|bandselect", "BAND_SELECT"),
    (r"fillnodata|fillna|mask|cloud", "MASKING"),
    (r"interpolate|kriging|idw|triangulation", "NEIGHBORHOOD"),
    (r"resample", "RESAMPLE_REPROJECT"),
    (r"randomselect|randomselection", "SAMPLE_EXTRACTION"),
]
def map_op(op):
    for pat, fam in OP_MAP:
        if re.search(pat, op, re.I): return fam
    return None

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

def bag_f1(pred, gold):
    rest = list(gold); tp = 0
    for x in pred:
        if x in rest: tp += 1; rest.remove(x)
    np_, ng = len(pred), len(gold)
    return 1.0 if np_+ng == 0 else (2*tp/(np_+ng) if tp else 0.0)

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

# load QGIS OOD rows (dev + test)
rows = []
for fn in ("/root/gee_llm_smoke/v2a_A_dev.jsonl", "/root/gee_llm_smoke/v2a_A_test.jsonl"):
    for line in open(fn, encoding="utf-8"):
        r = json.loads(line); r["_src"] = fn.split("/")[-1]
        rows.append(r)

# gold semantic mapping
gold_mapped_f1 = []
n_gold_unmapped = 0
for r in rows:
    mapped = []
    for p in r["processes"]:
        f = map_op(p["operator_id"])
        if f: mapped.append(f)
        else: n_gold_unmapped += 1
    r["_gold_sem"] = mapped
    r["_gold_unmapped_ops"] = len(r["processes"]) - len(mapped)

# trivial baseline: modal family from GEE train distribution (computed from blueprint gold v3)
gmodal = Counter()
for line in open(r"/root/data/planner_v2_train.jsonl", encoding="utf-8"):
    r = json.loads(line)
    bp = json.loads(r["target"])
    gmodal.update(s["family"] for s in bp.get("stages", []))
modal_fam = gmodal.most_common(1)[0][0]
# compute mean stages from train targets
ns = []
for line in open(r"/root/data/planner_v2_train.jsonl", encoding="utf-8"):
    bp = json.loads(line)["target"]
    ns.append(len(json.loads(bp).get("stages", [])))
mean_ns = st.mean(ns)
modal_len = max(1, int(round(mean_ns)))
print(f"modal family: {modal_fam} | mean stages: {mean_ns:.1f} -> modal len {modal_len}")

items = []
s1_parse = s1_schema = 0
zf_bag = []; zf_ord = []; pred_lens = []; gold_lens = []
pred_fams = Counter(); gold_fams = Counter()
with torch.no_grad():
    for k, r in enumerate(rows):
        enc = tok(r["task_text"] + SEP, return_tensors="pt", truncation=True, max_length=1024).to("cuda:0")
        g = model.generate(**enc, max_new_tokens=384, do_sample=False,
                           eos_token_id=[tok.eos_token_id, tok.pad_token_id],
                           pad_token_id=tok.pad_token_id)
        text = tok.decode(g[0][enc["input_ids"].shape[1]:], skip_special_tokens=True)
        bp = extract_json(text)
        parse_ok = bp is not None; schema_ok = False
        pred_seq = []
        if parse_ok:
            s1_parse += 1
            stg = bp.get("stages")
            if isinstance(stg, list) and stg and all(isinstance(s, dict) and "family" in s for s in stg):
                s1_schema += 1; schema_ok = True
                pred_seq = [str(s.get("family")) for s in stg]
        gold_sem = r["_gold_sem"]
        if pred_seq:
            zf_bag.append(bag_f1(pred_seq, gold_sem))
            zf_ord.append(ordered_f1(pred_seq, gold_sem))
            pred_fams.update(pred_seq)
        gold_fams.update(gold_sem)
        pred_lens.append(len(pred_seq)); gold_lens.append(len(gold_sem))
        items.append({"k": k, "src": r["_src"], "parse_ok": parse_ok, "schema_ok": schema_ok,
                      "pred_seq": pred_seq[:30], "gold_sem": gold_sem[:30]})
        if (k+1) % 50 == 0:
            print(f"{k+1}/{len(rows)} parse={s1_parse/(k+1):.3f} bag={st.mean(zf_bag):.3f} ord={st.mean(zf_ord):.3f}", flush=True)

n = len(rows)
res = {
    "experiment": "C1-2a zero-shot cross-platform reasoning transfer",
    "rows": n,
    "S1_parse_rate": round(s1_parse/n, 4),
    "S1_schema_rate": round(s1_schema/n, 4),
    "M_family_bag_f1_mean": round(st.mean(zf_bag), 4) if zf_bag else None,
    "M_ordered_lcs_f1_mean": round(st.mean(zf_ord), 4) if zf_ord else None,
    "M_references": {
        "trivial_modal_baseline_same_rows": round(st.mean([bag_f1([modal_fam]*modal_len, r["_gold_sem"]) for r in rows]), 4),
        "in_domain_gee_dev_reference": 0.6636,
        "C0_qgis_operator_reference": "0.343/0.370 (operator metric, not directly comparable)",
    },
    "M_length": {"pred_mean": round(st.mean(pred_lens), 1), "gold_mapped_mean": round(st.mean(gold_lens), 1)},
    "gold_unmapped_op_share": round(n_gold_unmapped/sum(len(r["processes"]) for r in rows), 3),
    "pred_family_top": pred_fams.most_common(8),
    "gold_family_top": gold_fams.most_common(8),
}
json.dump({"metrics": res, "items": items}, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False, indent=1))
