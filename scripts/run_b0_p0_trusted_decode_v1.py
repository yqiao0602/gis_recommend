#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""B0: same-host pure-P0 decode over the FULL trusted subset (1,276 rows).

Pure P0 (no guardrail), max_new_tokens=768, greedy, same prompt/stack as the
A1 768 arm — the canonical same-host P0 baseline for the whole B line.
Resume-capable: partial results flushed every 25 rows; restart skips done rows.
Termination typed per R1_DEPLOY_CONFIG vocabulary (no guardrail active:
EOS / MAX_TOKENS / OTHER).
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

BASE = "/home/qy/models/Qwen3.5/Qwen3.5-9B-Base"
ADAPTER = "/home/qy/planner_v2_adapter_staging"
DEV = "/home/qy/a1/planner_v2_dev_fix1_loopinv.jsonl"
LIST = "/home/qy/a1/B0_TRUSTED_EVAL_LIST_V1.json"
OUT_DIR = "/home/qy/a1/b0_p0_trusted_decode"


def tsha(s):
    import hashlib
    return hashlib.sha256((s or "").encode("utf-8")).hexdigest()[:16]


def main():
    assert not os.path.exists(OUT_DIR), f"refuse overwrite: {OUT_DIR}"
    os.makedirs(OUT_DIR)
    trusted = json.load(open(
        "/home/qy/a1/B0_TRUSTED_EVAL_LIST_V1.json",
        encoding="utf-8"))["rows"]
    rows = [json.loads(l) for l in open(DEV, encoding="utf-8") if l.strip()]

    partial_path = os.path.join(OUT_DIR, "partial_rows.json")
    done = {}
    if os.path.exists(partial_path):
        done = {r["idx"]: r for r in json.load(open(partial_path,
                                                    encoding="utf-8"))}
        print(f"[resume] {len(done)} rows already done", flush=True)

    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM, \
        BitsAndBytesConfig
    from peft import PeftModel

    tok = AutoTokenizer.from_pretrained(BASE, trust_remote_code=True)
    if tok.pad_token is None and tok.eos_token is not None:
        tok.pad_token = tok.eos_token
    bnb = BitsAndBytesConfig(load_in_4bit=True,
                             bnb_4bit_quant_type="nf4",
                             bnb_4bit_compute_dtype=torch.bfloat16,
                             bnb_4bit_use_double_quant=True)
    model = AutoModelForCausalLM.from_pretrained(
        BASE, trust_remote_code=True, torch_dtype=torch.bfloat16,
        device_map="cuda:0", quantization_config=bnb)
    model = PeftModel.from_pretrained(model, ADAPTER)
    model.eval()
    eos_ids = {tok.eos_token_id, tok.pad_token_id}
    SEP = ("\nWorkflow blueprint: output JSON with keys stages (ordered "
           "semantic stages with per-stage repeat counts) and "
           "repetition_groups (groups with repeat>1, each with "
           "iteration_hint from: per_band, per_class, per_year, "
           "per_feature, generic_each, unspecified).")

    with torch.no_grad():
        for k, x in enumerate(trusted):
            i = x["idx"]
            if i in done:
                continue
            enc = tok(rows[i]["task"] + SEP, return_tensors="pt",
                      truncation=True, max_length=1024).to("cuda:0")
            g = model.generate(**enc, max_new_tokens=768, do_sample=False,
                               eos_token_id=list(eos_ids),
                               pad_token_id=tok.pad_token_id)
            gen = g[0][enc["input_ids"].shape[1]:].tolist()
            n = len(gen)
            if gen and gen[-1] in eos_ids:
                term = "EOS"
            elif n >= 768:
                term = "MAX_TOKENS"
            else:
                term = "OTHER_STOP"
            text = tok.decode(gen, skip_special_tokens=True)
            t = rows[i]["target"]
            if isinstance(t, str):
                t = json.loads(t)
            st_ = None
            try:
                o = json.loads(text)
                if isinstance(o, dict) and o.get("stages"):
                    st_ = o["stages"]
            except Exception:
                pass
            done[i] = {"idx": i, "task_sha256": x["task_sha256"],
                       "termination": term, "generated_tokens": n,
                       "parse_ok": st_ is not None,
                       "pred_n_stages": len(st_) if st_ is not None else None,
                       "gold_n_stages": len(t["stages"]),
                       "pred_text": text}
            if len(done) % 25 == 0:
                json.dump(list(done.values()), open(partial_path, "w",
                          encoding="utf-8"), ensure_ascii=False, indent=1)
                print(f"{len(done)}/{len(trusted)}", flush=True)
    json.dump(list(done.values()), open(
        os.path.join(OUT_DIR, "b0_p0_trusted_raw.json"), "w",
        encoding="utf-8"), ensure_ascii=False, indent=1)
    json.dump(list(done.values()), open(partial_path, "w",
              encoding="utf-8"), ensure_ascii=False, indent=1)
    print("saved:", OUT_DIR, f"({len(done)} rows)", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
