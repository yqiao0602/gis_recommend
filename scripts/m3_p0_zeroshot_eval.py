#!/usr/bin/env python3
"""M3-P0: zero-shot baseline of post-trained Qwen3.5-9B on paper_v1 val.

Route M3-P0 (frozen definition): the official post-trained Qwen3.5-9B, no
training, evaluated task-text -> L3 chain. This establishes the Qwen-prior
floor. The zero-shot protocol is FROZEN before the run — prompt template,
decoding, and all parameters are fixed here and hash-recorded; no prompt
iteration after seeing results (that would be tuning on the eval set).

Evaluated on the paper_v1 validation split (49 rows: 41 GEE + 8 QGIS), which is
allowed data under the experiment discipline (final/refusal benchmark gold
remains sealed). Metrics: exact full-chain match, chain-level precision/recall
(multiset of L3 codes), and length error — all computed by code, never by eye.

Evaluation protocol (frozen):
  prompt   = "Task: {task_text}\nL3 workflow:"  (identical to E4/SFT format)
  decode   = greedy (do_sample=False), max_new_tokens=120
  match    = exact string equality against " {L3_1} -> {L3_2} ..." plus a
             lenient-tokens variant (whitespace-normalized, tolerant of the
             arrow spacing) reported separately
The model is loaded NF4 (same quantization as all M3/M2 training, so the P0
floor is measured under the deployment quantization).
"""

from __future__ import annotations

import argparse
import json
import re
import time
from collections import Counter
from pathlib import Path

import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

RESULT = Path("/home/qy/gee_llm_smoke/m3_p0_results_v1.json")

PROMPT_TEMPLATE = "Task: {task_text}\nL3 workflow:"
MAX_NEW_TOKENS = 120
# L3 code format: L3_XX_YY_ZZ where ZZ is two digits OR a single letter (letter codes
# L3_03_03_A/L, L3_03_10_R, L3_08_05_C; the old regex dropped them silently).
CODE_RE = re.compile(r"L3_\d{2}_\d{2}_(?:\d{2}[A-Z]?|[A-Z])")


def _chain_pred(text: str) -> list[str]:
    return CODE_RE.findall(text)


def _multiset_prf(pred: list[str], gold: list[str]) -> tuple[float, float]:
    p, g = Counter(pred), Counter(gold)
    inter = sum((p & g).values())
    precision = inter / max(sum(p.values()), 1)
    recall = inter / max(sum(g.values()), 1)
    return precision, recall


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", type=Path, required=True)
    ap.add_argument("--val", type=Path, required=True)
    ap.add_argument("--ledger", type=Path, required=True)
    args = ap.parse_args()

    rows = [json.loads(l) for l in args.val.read_text(encoding="utf-8").splitlines() if l.strip()]
    tok = AutoTokenizer.from_pretrained(args.model)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    bnb = BitsAndBytesConfig(
        load_in_4bit=True, bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True,
    )
    model = AutoModelForCausalLM.from_pretrained(args.model, quantization_config=bnb, device_map="cuda:0")
    model.eval()

    t0 = time.time()
    results = []
    exact = lenient = 0
    pr_sum = rec_sum = 0.0
    len_err_sum = 0
    by_platform = {"gee": [0, 0], "qgis": [0, 0]}  # [n, exact]
    for r in rows:
        prompt = PROMPT_TEMPLATE.format(task_text=r["task_text"])
        inputs = tok(prompt, return_tensors="pt", truncation=True, max_length=1024).to("cuda:0")
        with torch.no_grad():
            out = model.generate(
                **inputs, max_new_tokens=MAX_NEW_TOKENS, do_sample=False,
                temperature=None, top_p=None, pad_token_id=tok.pad_token_id,
            )
        text = tok.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True).strip()
        gold_text = r["l3_chain_text"].strip()
        gold_codes = _chain_pred(gold_text)
        pred_codes = _chain_pred(text)
        p, rec = _multiset_prf(pred_codes, gold_codes)
        is_exact = text == gold_text
        is_lenient = text.replace(" ", "") == gold_text.replace(" ", "")
        exact += is_exact
        lenient += is_lenient
        pr_sum += p
        rec_sum += rec
        len_err_sum += len(pred_codes) - len(gold_codes)
        by_platform[r["platform"]][0] += 1
        by_platform[r["platform"]][1] += is_exact
        results.append({
            "record_id": r["record_id"], "platform": r["platform"],
            "gold": gold_text, "pred": text[:400],
            "exact": is_exact, "pred_codes": len(pred_codes), "gold_codes": len(gold_codes),
        })

    n = len(rows)
    metrics = {
        "n": n,
        "exact_chain": exact,
        "exact_chain_rate": round(exact / n, 4),
        "lenient_exact": lenient,
        "code_precision": round(pr_sum / n, 4),
        "code_recall": round(rec_sum / n, 4),
        "mean_length_error": round(len_err_sum / n, 2),
        "by_platform": {k: {"n": v[0], "exact": v[1]} for k, v in by_platform.items()},
    }
    summary = {
        "schema": "gis_recommend.m3_p0_zeroshot.v1",
        "model": str(args.model),
        "protocol": {
            "prompt_template": PROMPT_TEMPLATE,
            "decode": "greedy", "max_new_tokens": MAX_NEW_TOKENS,
            "quantization": "nf4-double",
            "frozen_before_run": True,
        },
        "metrics": metrics,
        "minutes": round((time.time() - t0) / 60, 1),
        "peak_memory_gb": round(torch.cuda.max_memory_allocated() / 2**30, 2),
    }
    RESULT.write_text(json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8")
    Path(str(RESULT).replace("results_v1.json", "predictions_v1.jsonl")).write_text(
        "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in results), encoding="utf-8")

    # experiment ledger entry
    import sys
    sys.path.insert(0, "/home/qy/system_redesign" if Path("/home/qy/system_redesign/scripts/model_experiment_ledger.py").exists() else ".")
    from scripts.model_experiment_ledger import ExperimentLedger
    led = ExperimentLedger(args.ledger)
    led.register(
        "M3-P0-v1", "M3-P0",
        data_version="paper_v1_val_49",
        model_path=str(args.model),
        params={"prompt": PROMPT_TEMPLATE, "decode": "greedy", "max_new_tokens": MAX_NEW_TOKENS, "quant": "nf4"},
        gpu_seconds=round((time.time() - t0), 1),
        peak_memory_gb=summary["peak_memory_gb"],
        metrics=metrics,
        notes="zero-shot, protocol frozen before run; val split only, benchmark gold untouched",
    )
    print(json.dumps(summary["metrics"], indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
