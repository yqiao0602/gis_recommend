#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""R1 deployment verification: P0 + R1 decode-time regression run.

True decode-time guardrail via transformers StoppingCriteria: every
CHECK_EVERY generated tokens, the guardrail scans the generated text's
completed stage objects; fires -> generation stops for the row.

Frozen config: P0 adapter (staging), 768 budget, greedy, same prompt/stack
as the A1 pre arm. Regression set = the 131 A1 rows (superset of every
owner-listed subset: 52 runaway, 47 C2, 32 C3, idx 1503/1181, 4 no-cycle).
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from r1_guardrail_v1 import extract_stages, rule_fire  # noqa: E402

CHECK_EVERY = 16
BUDGET = 768


def main():
    import torch
    from transformers import (AutoTokenizer, AutoModelForCausalLM,
                              BitsAndBytesConfig, StoppingCriteria)
    from peft import PeftModel

    BASE = "/home/qy/models/Qwen3.5/Qwen3.5-9B-Base"
    ADAPTER = "/home/qy/planner_v2_adapter_staging"
    DEV = "/home/qy/a1/planner_v2_dev_fix1_loopinv.jsonl"
    SAMPLE = "/home/qy/a1/A1_SAMPLE_131.json"
    OUT_DIR = "/home/qy/a1/p0_r1_regression_131"

    assert not os.path.exists(OUT_DIR), f"refuse overwrite: {OUT_DIR}"
    os.makedirs(OUT_DIR)

    sample = json.load(open(SAMPLE, encoding="utf-8"))
    rows = [json.loads(l) for l in open(DEV, encoding="utf-8") if l.strip()]
    sel = sample["samples"]

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

    class R1Stopping(StoppingCriteria):
        """Decode-time guardrail: scans the GENERATED text every
        CHECK_EVERY steps; fires -> stops generation for the row."""
        def __init__(self, tok, prompt_len):
            self.tok = tok
            self.prompt_len = prompt_len
            self.checks = 0
            self.fired = False

        def __call__(self, input_ids, scores, **kwargs):
            self.checks += 1
            if self.fired or self.checks % CHECK_EVERY != 0:
                return self.fired
            gen_ids = input_ids[0].tolist()[self.prompt_len:]
            text = self.tok.decode(gen_ids, skip_special_tokens=True)
            fired, _, _ = rule_fire(extract_stages(text))
            self.fired = bool(fired)
            return self.fired

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
            plen = enc["input_ids"].shape[1]
            sc = R1Stopping(tok, plen)
            g = model.generate(**enc, max_new_tokens=BUDGET, do_sample=False,
                               eos_token_id=list(eos_ids),
                               pad_token_id=tok.pad_token_id,
                               stopping_criteria=[sc])
            gen = g[0][plen:].tolist()
            n = len(gen)
            if sc.fired:
                term = "R1_GUARDRAIL"
            elif gen and gen[-1] in eos_ids:
                term = "EOS"
            elif n >= BUDGET:
                term = "MAX_TOKENS"
            else:
                term = "OTHER_STOP"
            text = tok.decode(gen, skip_special_tokens=True)
            # canonical offline cut on the (possibly post-trigger) text
            from r1_guardrail_v1 import cut_text
            fired, cut, kept_n = cut_text(text)
            t = rows[i]["target"]
            if isinstance(t, str):
                t = json.loads(t)
            closure_ok = None
            if fired and cut is not None:
                try:
                    json.loads(cut + "]}")
                    closure_ok = True
                except Exception:
                    closure_ok = False
            out.append({"idx": i, "stratum": s["stratum"],
                        "termination": term, "generated_tokens": n,
                        "r1_fired_online": term == "R1_GUARDRAIL",
                        "offline_fired": fired, "kept_stages": kept_n,
                        "closure_parse": closure_ok,
                        "gold_n_stages": len(t["stages"]),
                        "pred_text": text})
            if (ridx + 1) % 20 == 0:
                print(f"{ridx+1}/{len(sel)}", flush=True)

    json.dump({"config": {"budget": BUDGET, "check_every": CHECK_EVERY,
                          "adapter": ADAPTER, "greedy": True},
               "rows": out},
              open(os.path.join(OUT_DIR, "p0_r1_regression_raw.json"),
                   "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("saved:", OUT_DIR)
    return 0


if __name__ == "__main__":
    sys.exit(main())
