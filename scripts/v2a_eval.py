#!/usr/bin/env python3
"""V2a evaluation: adapter -> graph predictions -> metrics, with live progress.

Serves both the training-time dev/test check and the later frozen-benchmark
runs (dev-20 -> prediction lock -> final-100), so the prediction format and the
metric computation are identical everywhere.

Decoding (recorded in the output so it is never implicit):
  greedy, max_new_tokens configurable (default 512), explicit EOS stop list.
The 512 cap is chosen because the benchmark gold graph is 2-11 processes
(~150 tokens); the hit-cap rate is reported so a too-small cap can never hide.

Metrics: parse-ok rate, operator P/R/F1, link P/R/F1, graph exact match,
empty-output rate, prediction length stats, distinct operators, operator
support-band recall, and the prediction-side direct/other link split.
"""
from __future__ import annotations

import argparse
import difflib
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import PeftModel

PROMPT_TEMPLATE = "Task: {task_text}\nQGIS workflow:"
REPO = Path("/home/qy/system_redesign")


def _canon_factory(catalog_list):
    catset = set(catalog_list)
    slugs = {c.split(":")[-1]: c for c in catalog_list}

    def canon(op):
        if not isinstance(op, str) or not op:
            return None
        if op in catset:
            return op
        fixed = op.replace("native:gdal:", "gdal:").replace("native:gdal_", "gdal:")
        if fixed in catset:
            return fixed
        close = difflib.get_close_matches(op.split(":")[-1], list(slugs), n=1, cutoff=0.72)
        return slugs[close[0]] if close else op

    return canon


def parse_pred(text: str) -> dict:
    s = text.strip()
    i, j = s.find("{"), s.rfind("}")
    if i < 0 or j <= i:
        return {"ok": False, "reason": "no_json"}
    try:
        obj = json.loads(s[i:j + 1])
    except json.JSONDecodeError as e:
        return {"ok": False, "reason": "json_error"}
    if not isinstance(obj, dict) or "processes" not in obj:
        return {"ok": False, "reason": "shape"}
    procs = [{"process_id": str(p.get("process_id")), "operator_id": p.get("operator_id")}
             for p in (obj.get("processes") or []) if isinstance(p, dict)]
    if not procs:
        return {"ok": False, "reason": "empty_processes"}
    ids = {p["process_id"] for p in procs}
    links = []
    for l in (obj.get("links") or []):
        if not isinstance(l, dict):
            continue
        a, b = str(l.get("source_process_id")), str(l.get("target_process_id"))
        if a in ids and b in ids and a != b:
            links.append({"source_process_id": a, "target_process_id": b})
    return {"ok": True, "processes": procs, "links": links}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", type=Path, required=True)
    ap.add_argument("--adapter", type=Path, required=True)
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--tag", default="dev")
    ap.add_argument("--max-new-tokens", type=int, default=512)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--canonicalize", action="store_true",
                    help="also report the canonicalized diagnostic block (secondary)")
    ap.add_argument("--repetition-penalty", type=float, default=1.0,
                    help="decoding-layer repetition penalty (1.0 = none, frozen default)")
    ap.add_argument("--no-repeat-ngram-size", type=int, default=0,
                    help="decoding-layer n-gram blocking (0 = disabled, frozen default)")
    args = ap.parse_args()
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

    rows = [json.loads(l) for l in args.data.read_text(encoding="utf-8").splitlines() if l.strip()]
    if args.limit:
        rows = rows[:args.limit]
    catalog = {o["operator_id"] for o in json.load(
        open(REPO / "benchmarks/qgis_planner_v1/authority/qgis_catalog.json", encoding="utf-8"))["operators"]}

    tok = AutoTokenizer.from_pretrained(str(args.model))
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_quant_type="nf4",
                             bnb_4bit_compute_dtype=torch.bfloat16,
                             bnb_4bit_use_double_quant=True)
    base = AutoModelForCausalLM.from_pretrained(str(args.model), quantization_config=bnb,
                                                device_map="cuda:0")
    model = PeftModel.from_pretrained(base, str(args.adapter))
    model.eval()
    eos_ids = [x for x in {tok.eos_token_id, tok.pad_token_id} if x is not None]

    t0 = time.time()
    preds = []
    op_tp = op_fp = op_fn = link_tp = link_fp = link_fn = 0
    total_op_gold = total_link_gold = 0   # gold in ALL rows incl. unparseable
    row_opf1 = []                          # per-row F1 for every row (0 if no usable pred)
    row_linkf1 = []
    n_usable_rows = 0                      # rows with a non-empty predicted op set
    exact = empty = hit_cap = 0
    parse_fail = Counter()
    op_inst = Counter()
    pred_direct_like = 0
    tgt_op_inst = Counter()
    for i, r in enumerate(rows):
        prompt = PROMPT_TEMPLATE.format(task_text=r["task_text"])
        inputs = tok(prompt, return_tensors="pt", truncation=True, max_length=2560).to("cuda:0")
        with torch.no_grad():
            gen = model.generate(**inputs, max_new_tokens=args.max_new_tokens,
                                 do_sample=False, eos_token_id=eos_ids,
                                 repetition_penalty=args.repetition_penalty,
                                 no_repeat_ngram_size=args.no_repeat_ngram_size,
                                 pad_token_id=tok.pad_token_id)
        out_ids = gen[0][inputs["input_ids"].shape[1]:]
        text = tok.decode(out_ids, skip_special_tokens=True)
        if len(out_ids) >= args.max_new_tokens:
            hit_cap += 1
        pr = parse_pred(text)
        gm = Counter(p["operator_id"] for p in r["processes"])
        gl = {(l["source_process_id"], l["target_process_id"]) for l in r["links"]}
        tgt_op_inst.update(gm)
        total_op_gold += sum(gm.values())
        total_link_gold += len(gl)
        if not pr["ok"]:
            parse_fail[pr["reason"]] += 1
            row_opf1.append(0.0)      # unparseable row scores zero end-to-end
            row_linkf1.append(0.0)
            preds.append({"wid": r["wid"], "ok": False, "reason": pr["reason"],
                          "n_gen_tokens": int(len(out_ids)), "raw": text})
        else:
            pm = Counter(p["operator_id"] for p in pr["processes"])
            op_inst.update(pm)
            inter = sum((gm & pm).values())
            op_tp += inter
            op_fp += sum(pm.values()) - inter
            op_fn += sum(gm.values()) - inter
            if pm:
                n_usable_rows += 1
                row_opf1.append(2 * inter / max(sum(pm.values()) + sum(gm.values()), 1))
            else:
                empty += 1
                row_opf1.append(0.0)
            pl = {(l["source_process_id"], l["target_process_id"]) for l in pr["links"]}
            li = len(gl & pl)
            link_tp += li
            link_fp += len(pl) - li
            link_fn += len(gl) - li
            row_linkf1.append(2 * li / max(len(pl) + len(gl), 1))
            if not pm:
                empty += 1
            if gm == pm and gl == pl:
                exact += 1
            preds.append({"wid": r["wid"], "ok": True, "exact": bool(gm == pm and gl == pl),
                          "n_proc_pred": len(pm), "n_proc_gold": len(gm),
                          "n_link_pred": len(pl), "n_link_gold": len(gl),
                          "n_gen_tokens": int(len(out_ids)),
                          "ops_p": round(inter / max(sum(pm.values()), 1), 3),
                          "ops_r": round(inter / max(sum(gm.values()), 1), 3),
                          "raw": text})
        if (i + 1) % 10 == 0:
            micro = 2 * op_tp / max(2 * op_tp + op_fp + op_fn, 1)
            print(f"[{i+1}/{len(rows)}] elapsed {(time.time()-t0)/60:.1f}m "
                  f"parse_ok={sum(1 for p in preds if p.get('ok'))}/{i+1} "
                  f"hit_cap={hit_cap} op_microF1={micro:.3f}", flush=True)

    n = len(rows)
    parse_ok = sum(1 for p in preds if p.get("ok"))
    # (support-band breakdown computed offline from predictions)

    def f1(p, r):
        return round(2 * p * r / max(p + r, 1e-9), 4)

    metrics = {
        "schema": "gis_recommend.v2a.eval.v1", "tag": args.tag, "n": n,
        "adapter": str(args.adapter), "decoding": {
            "greedy": True, "max_new_tokens": args.max_new_tokens,
            "repetition_penalty": args.repetition_penalty,
            "no_repeat_ngram_size": args.no_repeat_ngram_size,
            "eos_stop_ids": eos_ids, "hit_cap_rows": hit_cap},
        "parse_ok_rate": round(parse_ok / n, 4),
        "parse_failures": dict(parse_fail),
        # PRIMARY: end-to-end. Unparseable rows contribute zero TP/FP and all
        # their gold as FN — this is the usable result, not the optimistic one.
        "operator_end_to_end": {
            "tp": op_tp, "fp": op_fp, "fn": total_op_gold - op_tp,
            "precision": round(op_tp / max(op_tp + op_fp, 1), 4),
            "recall": round(op_tp / max(total_op_gold, 1), 4),
            "f1": round(2 * op_tp / max(2 * op_tp + op_fp + (total_op_gold - op_tp), 1), 4)},
        "operator_macro_end_to_end_f1": round(sum(row_opf1) / max(len(row_opf1), 1), 4),
        "link_end_to_end": {
            "tp": link_tp, "fp": link_fp, "fn": total_link_gold - link_tp,
            "precision": round(link_tp / max(link_tp + link_fp, 1), 4),
            "recall": round(link_tp / max(total_link_gold, 1), 4),
            "f1": round(2 * link_tp / max(2 * link_tp + link_fp + (total_link_gold - link_tp), 1), 4)},
        "link_macro_end_to_end_f1": round(sum(row_linkf1) / max(len(row_linkf1), 1), 4),
        # SECONDARY: conditional-on-parse (optimistic). Only rows with a
        # non-empty predicted op set contribute; gold of unparseable rows is
        # excluded from FN. Never quote this as the usability number.
        "operator_conditional_on_parse": {
            "note": "optimistic; excludes unparseable rows from both numerator and denominator",
            "tp": op_tp, "fp": op_fp, "fn": op_fn,
            "n_usable_rows": n_usable_rows,
            "precision": round(op_tp / max(op_tp + op_fp, 1), 4),
            "recall": round(op_tp / max(op_tp + op_fn, 1), 4),
            "f1": round(2 * op_tp / max(2 * op_tp + op_fp + op_fn, 1), 4)},
        "link_conditional_on_parse": {
            "tp": link_tp, "fp": link_fp, "fn": link_fn,
            "n_usable_rows": n_usable_rows,
            "precision": round(link_tp / max(link_tp + link_fp, 1), 4),
            "recall": round(link_tp / max(link_tp + link_fn, 1), 4),
            "f1": round(2 * link_tp / max(2 * link_tp + link_fp + link_fn, 1), 4)},
        "graph_exact_match_rate": round(exact / n, 4),
        "empty_operator_rows": empty,
        "distinct_operators_predicted": len(op_inst),
        "distinct_operators_gold": len(tgt_op_inst),
        "out_of_catalog_operator_instances": sum(v for k, v in op_inst.items() if k not in catalog),
        "gold_operator_instances": sum(tgt_op_inst.values()),
        "pred_operator_instances": sum(op_inst.values()),
        "minutes": round((time.time() - t0) / 60, 1),
    }
    if args.canonicalize:
        canon = _canon_factory(sorted(catalog))
        ctp = cfp = cfn = cltp = clfp = clfn = 0
        for r, g in zip(preds, rows):
            if not r.get("ok"):
                continue
            pr = parse_pred(r["raw"])
            if not pr["ok"]:
                continue
            ops = []
            for proc in pr["processes"]:
                o = canon(proc["operator_id"])
                if o and (not ops or ops[-1] != o):
                    ops.append(o)
            if not ops:
                continue
            gm = Counter(p["operator_id"] for p in g["processes"])
            pm = Counter(ops)
            i = sum((gm & pm).values())
            ctp += i; cfp += sum(pm.values()) - i; cfn += sum(gm.values()) - i
            gl = {(l["source_process_id"], l["target_process_id"]) for l in g["links"]}
            pl = {(l["source_process_id"], l["target_process_id"]) for l in pr["links"]}
            li = len(gl & pl)
            cltp += li; clfp += len(pl) - li; clfn += len(gl) - li
        cp = ctp / max(ctp + cfp, 1); cr = ctp / max(ctp + cfn, 1)
        lp = cltp / max(cltp + clfp, 1); lr = cltp / max(cltp + clfn, 1)
        metrics["canonicalized_secondary"] = {
            "note": "diagnostic only: catalog name canonicalization (alias+nearest) and "
                    "consecutive-duplicate collapse applied post-hoc; NOT the primary metric",
            "operator": {"tp": ctp, "fp": cfp, "fn": cfn,
                         "precision": round(cp, 4), "recall": round(cr, 4),
                         "f1": round(2 * cp * cr / max(cp + cr, 1e-9), 4)},
            "link": {"tp": cltp, "fp": clfp, "fn": clfn,
                     "precision": round(lp, 4), "recall": round(lr, 4),
                     "f1": round(2 * lp * lr / max(lp + lr, 1e-9), 4)},
        }

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / f"v2a_{args.tag}_eval_metrics.json").write_text(
        json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
    (args.out_dir / f"v2a_{args.tag}_predictions.jsonl").write_text(
        "".join(json.dumps(p, ensure_ascii=False, sort_keys=True) + "\n" for p in preds),
        encoding="utf-8")
    print(json.dumps(metrics, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
