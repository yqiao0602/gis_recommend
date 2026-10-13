#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A″ post-training inference: single arm, max_new_tokens=768 (identical to
the frozen pre arm: same host, stack, prompt, greedy) with the A″ adapter.
Server-side run after training completes."""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="/home/qy/models/Qwen3.5/Qwen3.5-9B-Base")
    ap.add_argument("--adapter",
                    default="/home/qy/a1/adprime_run_v1/stage1_adapter")
    ap.add_argument("--dev", default="/home/qy/a1/planner_v2_dev_fix1_loopinv.jsonl")
    ap.add_argument("--sample", default="/home/qy/a1/A1_SAMPLE_131.json")
    ap.add_argument("--out-dir", required=True)
    a = ap.parse_args()
    assert not os.path.exists(a.out_dir), f"refusing overwrite: {a.out_dir}"
    os.makedirs(a.out_dir)

    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM, \
        BitsAndBytesConfig
    from peft import PeftModel

    sample = json.load(open(a.sample, encoding="utf-8"))
    rows = [json.loads(l) for l in open(a.dev, encoding="utf-8") if l.strip()]
    sel = sample["samples"]

    tok = AutoTokenizer.from_pretrained(a.base, trust_remote_code=True)
    bnb = BitsAndBytesConfig(load_in_4bit=True,
                             bnb_4bit_quant_type="nf4",
                             bnb_4bit_compute_dtype=torch.bfloat16,
                             bnb_4bit_use_double_quant=True)
    model = AutoModelForCausalLM.from_pretrained(
        a.base, trust_remote_code=True, torch_dtype=torch.bfloat16,
        device_map="cuda:0", quantization_config=bnb)
    model = PeftModel.from_pretrained(model, a.adapter)
    model.eval()
    eos_ids = {tok.eos_token_id, tok.pad_token_id}
    SEP = ("\nWorkflow blueprint: output JSON with keys stages (ordered "
           "semantic stages with per-stage repeat counts) and "
           "repetition_groups (groups with repeat>1, each with "
           "iteration_hint from: per_band, per_class, per_year, "
           "per_feature, generic_each, unspecified).")

    out = []
    with torch.no_grad():
        for ridx, s in enumerate(sel):
            i = s["idx"]
            enc = tok(rows[i]["task"] + SEP, return_tensors="pt",
                      truncation=True, max_length=1024).to("cuda:0")
            g = model.generate(**enc, max_new_tokens=768, do_sample=False,
                               eos_token_id=list(eos_ids),
                               pad_token_id=tok.pad_token_id)
            gen = g[0][enc["input_ids"].shape[1]:].tolist()
            n = len(gen)
            term = "EOS" if (gen and gen[-1] in eos_ids) else \
                   ("MAX_TOKENS" if n >= 768 else "OTHER_STOP")
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
            out.append({"idx": i, "source_row_id": s.get("source_row_id"),
                        "task_sha256": s.get("task_sha256"),
                        "stratum": s["stratum"], "termination": term,
                        "generated_tokens": n, "parse_ok": st_ is not None,
                        "pred_n_stages": len(st_) if st_ is not None else None,
                        "gold_n_stages": len(t["stages"]),
                        "pred_text": text})
            if (ridx + 1) % 20 == 0:
                print(f"{ridx+1}/{len(sel)}", flush=True)
    json.dump({"arm": "adprime_post_768", "rows": out},
              open(os.path.join(a.out_dir, "adprime_post768_raw.json"),
                   "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("saved:", a.out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
