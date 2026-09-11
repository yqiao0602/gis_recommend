#!/usr/bin/env python3
"""M3-P1-EOS-R1: protocol-compatibility re-evaluation of the M3-P1 checkpoint.

Not a retraining. The only change is generation termination handling: the
frozen M3-P0/M3-P1 protocol remains identical (same prompt template, greedy
decode, same 49-row val split) except that generation stops at the first EOS
or repetition boundary. The 120-token truncation artifact in M3-P1-v1 is
preserved untouched in the ledger; this run registers as M3-P1-EOS-R1 against
the SAME checkpoint, explicitly marked as a protocol-compatibility fix.

Termination fix (minimal, no training change): pass the tokenizer's full EOS
set (eos + pad) to generate as stopping criteria, and cap at 300 tokens so
chains are never cut mid-sequence.
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
from peft import PeftModel

# L3 code format: L3_XX_YY_ZZ where ZZ is two digits OR a single letter
# (letter codes L3_03_03_A/L, L3_03_10_R, L3_08_05_C exist in taxonomy_128 and
# are bridged in the benchmark; the old regex dropped them silently).
CODE_RE = re.compile(r"L3_\d{2}_\d{2}_(?:\d{2}[A-Z]?|[A-Z])")
PROMPT_TEMPLATE = "Task: {task_text}\nL3 workflow:"
MAX_NEW_TOKENS = 300


def prf(pred, gold):
    p, g = Counter(pred), Counter(gold)
    inter = sum((p & g).values())
    return inter / max(sum(p.values()), 1), inter / max(sum(g.values()), 1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", type=Path, required=True)
    ap.add_argument("--adapter", type=Path, required=True)
    ap.add_argument("--val", type=Path, required=True)
    ap.add_argument("--taxonomy", type=Path, required=True)
    ap.add_argument("--ledger", type=Path, required=True)
    ap.add_argument("--tag", default="v2",
                    help="output/ledger tag; v1 originals are never overwritten")
    args = ap.parse_args()

    valid_l3 = {c["l3_code"] for c in json.loads(args.taxonomy.read_text(encoding="utf-8"))["classes"]}
    rows = [json.loads(l) for l in args.val.read_text(encoding="utf-8").splitlines() if l.strip()]

    tok = AutoTokenizer.from_pretrained(args.model)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                             bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
    base = AutoModelForCausalLM.from_pretrained(args.model, quantization_config=bnb, device_map="cuda:0")
    model = PeftModel.from_pretrained(base, args.adapter)
    model.eval()

    t0 = time.time()
    exact = lenient = 0
    pr_sum = rec_sum = 0.0
    len_err = 0
    order_err = 0
    invalid_rows = 0
    by_platform = {"gee": [0, 0], "qgis": [0, 0]}
    preds = []
    for r in rows:
        prompt = PROMPT_TEMPLATE.format(task_text=r["task_text"])
        inputs = tok(prompt, return_tensors="pt", truncation=True, max_length=1024).to("cuda:0")
        eos_ids = [i for i in {tok.eos_token_id, tok.pad_token_id} if i is not None]
        with torch.no_grad():
            out = model.generate(
                **inputs, max_new_tokens=MAX_NEW_TOKENS, do_sample=False,
                eos_token_id=eos_ids, pad_token_id=tok.pad_token_id,
            )
        text = tok.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True).strip()
        # first block: the answer up to the first repetition boundary (blank line / second chain start)
        first_block = text.split("\n\n")[0].split("\n")[0].strip()
        gold = r["l3_chain_text"].strip()
        gc, pc = CODE_RE.findall(gold), CODE_RE.findall(first_block)
        p, rec = prf(pc, gc)
        pr_sum += p; rec_sum += rec
        len_err += len(pc) - len(gc)
        is_exact = first_block == gold
        is_lenient = first_block.replace(" ", "") == gold.replace(" ", "")
        exact += is_exact
        lenient += is_lenient
        if Counter(pc) == Counter(gc) and pc != gc and pc:
            order_err += 1
        if pc and any(c not in valid_l3 for c in pc):
            invalid_rows += 1
        by_platform[r["platform"]][0] += 1
        by_platform[r["platform"]][1] += is_exact
        preds.append({"record_id": r["record_id"], "platform": r["platform"], "gold": gold,
                      "pred": first_block[:400], "raw_tail": text[len(first_block):][:120],
                      "exact": is_exact, "n_pred_codes": len(pc), "n_gold_codes": len(gc)})

    n = len(rows)
    metrics = {
        "n": n, "exact_chain": exact, "exact_chain_rate": round(exact / n, 4),
        "lenient_exact": lenient,
        "code_precision": round(pr_sum / n, 4), "code_recall": round(rec_sum / n, 4),
        "mean_length_error": round(len_err / n, 2),
        "order_errors_multiset_correct": order_err,
        "invalid_l3_token_rows": invalid_rows,
        "by_platform": {k: {"n": v[0], "exact": v[1]} for k, v in by_platform.items()},
    }
    out_dir = Path("/home/qy/gee_llm_smoke/m3_p1")
    (out_dir / f"m3_p1_eos_r1_metrics_{args.tag}.json").write_text(
        json.dumps({"schema": "gis_recommend.m3_p1_eos_r1.v1",
                    "protocol_change": "eos stop handling (as v1) + code-extraction regex fix (letter-format L3 codes L3_XX_YY_Z now parsed); prompt, decode, data, checkpoint identical",
                    "metrics": metrics,
                    "minutes": round((time.time() - t0) / 60, 1),
                    "peak_memory_gb": round(torch.cuda.max_memory_allocated() / 2**30, 2)},
                   indent=2, ensure_ascii=False), encoding="utf-8")
    (out_dir / f"m3_p1_eos_r1_predictions_{args.tag}.jsonl").write_text(
        "".join(json.dumps(p, ensure_ascii=False, sort_keys=True) + "\n" for p in preds), encoding="utf-8")

    from model_experiment_ledger import ExperimentLedger, sha256_file
    led = ExperimentLedger(args.ledger)
    led.register(
        f"M3-P1-EOS-R1-{args.tag.upper()}", "M3-P1",
        data_version="paper_v1_val_49",
        model_path=str(args.model),
        checkpoint_sha256=sha256_file(args.adapter / "adapter_model.safetensors"),
        params={"reeval_only": True, "protocol_change": "eos_token_id stop list, max_new_tokens 300",
                "checkpoint_same_as": "M3-P1-v1"},
        gpu_seconds=round(time.time() - t0),
        peak_memory_gb=round(torch.cuda.max_memory_allocated() / 2**30, 2),
        metrics=metrics,
        notes="same checkpoint as M3-P1-v1; protocol-compatibility fix for the 120-token truncation artifact; original M3-P1-v1 results preserved unchanged",
    )
    print(json.dumps(metrics, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
