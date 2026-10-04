#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R3-PLANNER-V2 formal dev evaluator (diagnostic hierarchy per owner ruling).

L1  E1 Ordered Stage-F1 (LCS) + first-stage acc + exact-seq rate   [core]
L2  E2 Repetition-presence F1 (per-family signature)               [new capability]
L3  E3 Iteration-hint F1 micro/macro/per-class + emission rate     [conditional semantics]
FMT S1 JSON/schema validity                                        [necessary condition]
DIAG E4 repeat bias mean/hist                                      [diagnostic only]
OBS S4 unspecified-group rate; S5 hint-family correspondence
Optionally subsample via argv[3] for speed.
"""
import json, re, sys, statistics as st
from collections import Counter, defaultdict
sys.path.insert(0, "/root/system_redesign")
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from peft import PeftModel

BASE = "/root/models/Qwen3.5-9B-Base"
ADAPTER = sys.argv[1] if len(sys.argv) > 1 else "/root/data/stage1_run_planner_v2/stage1_adapter"
EVAL = sys.argv[2] if len(sys.argv) > 2 else "/root/data/planner_v2_dev.jsonl"
OUT = sys.argv[3] if len(sys.argv) > 3 else "/root/data/planner_v2_dev_metrics.json"
SUB = int(sys.argv[4]) if len(sys.argv) > 4 else 0
SEP = "\nWorkflow blueprint: output JSON with keys stages (ordered semantic stages with per-stage repeat counts) and repetition_groups (groups with repeat>1, each with iteration_hint from: per_band, per_class, per_year, per_feature, generic_each, unspecified)."
HINT_FAM = {"per_band": {"BAND_SELECT", "BAND_ARITHMETIC"},
            "per_class": {"CLASSIFICATION"},
            "per_year": {"TEMPORAL_FILTER"}}

def lcs(a, b):
    if not a or not b: return 0
    prev = [0]*(len(b)+1)
    for i in range(1, len(a)+1):
        cur = [0]*(len(b)+1); ai = a[i-1]
        for j in range(1, len(b)+1):
            cur[j] = prev[j-1]+1 if ai == b[j-1] else max(prev[j], cur[j-1])
        prev = cur
    return prev[-1]

def ordered_f1(pred, gold):
    L = lcs(pred, gold)
    p = L/len(pred) if pred else 0.0
    r = L/len(gold) if gold else 0.0
    return p, r, (2*p*r/(p+r) if p+r else 0.0)

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
if SUB: rows = rows[:SUB]
e1 = []; e1_first = 0; e1_exact = 0
e2 = []
hint_tp = hint_all = 0
hint_cls = defaultdict(lambda: {"tp": 0, "all": 0})
hint_emission_groups = hint_emission_hinted = 0
s1_parse = s1_schema = 0
s4_unspec_pred = s4_unspec_gold = s4_groups = 0
e3_group_exact = e3_groups = 0
e3_group_exact_all = []; e3_groups_all = []
rep_pred, rep_gold = [], []
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
        parse_ok = bp is not None; schema_ok = False
        if parse_ok:
            s1_parse += 1
            stg = bp.get("stages")
            if isinstance(stg, list) and stg and all(isinstance(s, dict) and "family" in s for s in stg):
                s1_schema += 1; schema_ok = True
                ps = [str(s.get("family")) for s in stg if str(s.get("family"))]
                gs = [str(s.get("family")) for s in gold.get("stages", [])]
                p_, r_, f_ = ordered_f1(ps, gs)
                e1.append(f_)
                if ps and gs and ps[0] == gs[0]: e1_first += 1
                if ps == gs: e1_exact += 1
                pf = {s["family"] for s in stg if isinstance(s.get("repeat"), int) and s["repeat"] > 1}
                gf = {s["family"] for s in gold.get("stages", []) if s.get("repeat", 1) > 1}
                tp2 = len(pf & gf)
                p2 = tp2/len(pf) if pf else 0.0
                r2 = tp2/len(gf) if gf else 0.0
                e2.append(round(2*p2*r2/(p2+r2),3) if p2+r2 else 1.0)
                # S4 gold-side reference: unspecified rate in gold groups
                for gg in gold.get("repetition_groups", []):
                    if isinstance(gg, dict):
                        s4_groups += 1
                        gh = gg.get("iteration_hint") or []
                        if "unspecified" in gh and len(gh) == 1: s4_unspec_gold += 1
                rg = bp.get("repetition_groups")
                gold_groups = gold.get("repetition_groups", [])
                if isinstance(rg, list):
                    hint_emission_groups += len(rg)
                    for grp in rg:
                        if not isinstance(grp, dict): continue
                        h = grp.get("iteration_hint") or []
                        if h and h != ["unspecified"]: hint_emission_hinted += 1
                        fam = str(grp.get("family", ""))
                        if "unspecified" in h and len(h) == 1: s4_unspec_pred += 1
                        for hd in h:
                            hint_all += 1
                            fams = HINT_FAM.get(hd)
                            if fams:
                                hint_tp += int(fam in fams)
                    # E3 v2: gold-aligned hint-set comparison.
                    # Match pred groups to gold groups by family+position-in-family
                    # (grouping is per family run, so identical family keys align 1:1
                    # when counts match; extras counted once as FP/miss respectively).
                    gold_by_key = {}
                    for gg in gold_groups:
                        if not isinstance(gg, dict): continue
                        key = (str(gg.get("family")), gold_groups.count(gg.get("family")))
                        gold_by_key.setdefault(key, []).append(gg)
                    pred_by_key = {}
                    for pg in rg:
                        if not isinstance(pg, dict): continue
                        key = (str(pg.get("family")), rg.count(pg.get("family")))
                        pred_by_key.setdefault(key, []).append(pg)
                    for key, plist in pred_by_key.items():
                        glist = gold_by_key.get(key, [])
                        for gi, pg in enumerate(plist):
                            ph = set(str(x) for x in (pg.get("iteration_hint") or []))
                            s4_unspec_pred += int(ph == {"unspecified"})
                            if gi < len(glist):
                                gh = set(str(x) for x in (glist[gi].get("iteration_hint") or []))
                                for hd in ph | gh:
                                    hint_cls[hd]["all"] += 1
                                    if hd in ph and hd in gh:
                                        hint_cls[hd]["tp"] += 1
                                if ph == gh:
                                    e3_group_exact += 1
                                e3_groups += 1
                    e3_group_exact_all.append(e3_group_exact)
                    e3_groups_all.append(e3_groups)
                    e3_groups = e3_group_exact = 0
                for s in stg:
                    if isinstance(s.get("repeat"), int): rep_pred.append(s["repeat"])
                for s in gold.get("stages", []):
                    rep_gold.append(s.get("repeat", 1))
        items.append({"k": k, "parse_ok": parse_ok, "schema_ok": schema_ok, "e1": e1[-1] if e1 else None})
        if (k+1) % 100 == 0:
            print(f"{k+1}/{len(rows)} parse={s1_parse/(k+1):.3f} schema={s1_schema/(k+1):.3f} e1={st.mean(e1):.3f}", flush=True)

n = len(rows); ns = max(1, s1_schema)
e3_exact_rate = (round(sum(e3_group_exact_all)/max(1, sum(e3_groups_all)), 4)
                 if sum(e3_groups_all) else None)
gold_unspec_rate = round(s4_unspec_gold/max(1, s4_groups), 4) if s4_groups else None
pred_unspec_rate = round(s4_unspec_pred/max(1, s4_unspec_pred + hint_all), 4) if (s4_groups or hint_all) else None
per_class = {h: {"precision": round(v["tp"]/v["all"],3) if v["all"] else None,
                 "n": v["all"]} for h, v in sorted(hint_cls.items())}
res = {
    "rows": n, "subsample": SUB or None,
    "S1_parse_rate": round(s1_parse/n, 4), "S1_schema_rate": round(s1_schema/n, 4),
    "E1_ordered_stage_f1": round(st.mean(e1), 4) if e1 else None,
    "E1_first_stage_acc": round(e1_first/ns, 4),
    "E1_exact_seq_rate": round(e1_exact/ns, 4),
    "E2_repetition_presence_f1": round(st.mean(e2), 4) if e2 else None,
    "E3_hint_emission_rate_groups": round(hint_emission_hinted/max(1,hint_emission_groups), 4) if hint_emission_groups else 0.0,
    "E3_group_exact_rate": e3_exact_rate,
    "E3_hint_fam_consistency": round(hint_tp/max(1,hint_all), 4) if hint_all else None,
    "E3_hint_per_class": per_class,
    "S4_unspecified_rate_pred_vs_gold": {"pred": pred_unspec_rate, "gold": gold_unspec_rate,
        "note": "deviation diagnostic: pred >> gold = unspecified collapse; pred << gold = hint over-emission"},
    "E4_repeat_pred_mean": round(st.mean(rep_pred), 2) if rep_pred else None,
    "E4_repeat_gold_mean": round(st.mean(rep_gold), 2) if rep_gold else None,
    "E4_repeat_hist_pred_top": dict(Counter(rep_pred).most_common(10)),
    "E4_repeat_hist_gold_top": dict(Counter(rep_gold).most_common(10)),
}
json.dump({"metrics": res, "items": items}, open(OUT, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False, indent=1))
