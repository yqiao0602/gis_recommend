#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""DX stage runner V2 (P2-R instrument fix).

Identical GENERATION behaviour to dx_run_stage_v1 (frozen): same model, prompt,
greedy decode, repetition_penalty 1.15, TRUNC 4096, batch 4, eos/pad handling.
The ONLY change is bookkeeping per owner ruling:
  - per-ITEM generated length (scan of that row's tail up to its first
    eos/pad token) instead of the batch-level shape difference;
  - per-item term via dx_termination_v2.classify_item (END_MARK / CAP_TRUNC /
    EOS / IMMEDIATE_EOS) plus output_state (empty / non_empty);
  - the batch-level length is still recorded for traceability.
v1 remains frozen and untouched.
"""
import json
import os
import sys
import time

BASE = "/home/qy/models/Qwen3.5/Qwen3.5-9B-Base"
BS, TRUNC, HARD_RETRY = 4, 4096, 2


def _load_pack(path):
    pack = json.loads(open(path, encoding="utf-8").read())
    items = pack["items"]
    keys = [item.get("item_key") for item in items]
    if not all(isinstance(k, str) and k for k in keys) or len(set(keys)) != len(keys):
        raise ValueError("pack items require unique nonempty item_key values")
    return pack


def _wait_gpu():
    import subprocess
    while True:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used",
                              "--format=csv,noheader,nounits"],
                             capture_output=True, text=True).stdout.strip()
        if int(out.splitlines()[0]) < 11028:
            print(f"GPU available (used={out.splitlines()[0]}MiB)", flush=True)
            return
        print("GPU busy, waiting 180s (co-tenancy)", flush=True)
        time.sleep(180)


def main(pack_path=None, out_root=None):
    pack_path = pack_path or sys.argv[1]
    out_root = out_root or sys.argv[2]
    pack = _load_pack(pack_path)
    items = pack["items"]
    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
    from dx_termination_v2 import classify_item, first_stop_index
    from dx_recorder_v1 import write_item

    tok = AutoTokenizer.from_pretrained(BASE, trust_remote_code=True)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    tok.padding_side = "left"
    plens = {it["item_key"]: len(tok(it["prompt"], return_tensors=None,
                                      truncation=False)["input_ids"]) for it in items}
    too_long = {k: v for k, v in plens.items() if v >= TRUNC}
    print(f"prompt tokens: min={min(plens.values())} max={max(plens.values())} "
          f"n_over_TRUNC={len(too_long)}", flush=True)
    if too_long:
        raise SystemExit(f"FATAL: prompts at/over TRUNC={TRUNC}: {sorted(too_long.items())[:5]}")

    _wait_gpu()
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16,
                             bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True)
    model = AutoModelForCausalLM.from_pretrained(BASE, trust_remote_code=True,
            torch_dtype=torch.bfloat16, device_map="cuda:0", quantization_config=bnb)
    model.eval()
    t0 = time.time()
    for start in range(0, len(items), BS):
        chunk = items[start:start + BS]
        prompts = [it["prompt"] for it in chunk]
        encs = [tok(p, return_tensors=None, truncation=True, max_length=TRUNC)["input_ids"]
                for p in prompts]
        maxlen, pad = max(map(len, encs)), tok.pad_token_id
        inp = {"input_ids": torch.tensor([[pad] * (maxlen - len(e)) + e for e in encs],
                                           device="cuda:0"),
               "attention_mask": torch.tensor([[0] * (maxlen - len(e)) + [1] * len(e)
                                                for e in encs], device="cuda:0")}
        attempt, last_error = 0, None
        while attempt <= HARD_RETRY:
            attempt += 1
            try:
                with torch.no_grad():
                    generated = model.generate(**inp,
                        max_new_tokens=max(it["maxnew"] for it in chunk), do_sample=False,
                        repetition_penalty=1.15,
                        eos_token_id=[tok.eos_token_id, tok.pad_token_id], pad_token_id=pad)
                last_error = None
                break
            except Exception as exc:
                last_error = exc
                print(f"batch {start} attempt {attempt} error: {str(exc)[:150]}", flush=True)
                if attempt <= HARD_RETRY:
                    torch.cuda.empty_cache()
                    time.sleep(20)
        if last_error is not None:
            for item in chunk:
                write_item(out_root, item, b"", {
                    "prompt_sha16": __import__("hashlib").sha256(
                        item["prompt"].encode()).hexdigest()[:16],
                    "status": "HARD_FAILED", "attempts": attempt,
                    "error": str(last_error)[:300]})
            continue
        n_batch = int(generated.shape[1] - maxlen)
        stop_ids = {tok.eos_token_id, pad}
        for j, item in enumerate(chunk):
            tail = generated[j][maxlen:]
            n_item = first_stop_index(tail.tolist(), stop_ids, len(tail))
            text = tok.decode(tail[:n_item], skip_special_tokens=True)
            cls = classify_item(text, n_item, item["maxnew"])
            write_item(out_root, item, text, {
                "prompt_sha16": __import__("hashlib").sha256(
                    item["prompt"].encode()).hexdigest()[:16],
                "status": "OK",
                "term": cls["term"],
                "term_rule": "v2_per_item",
                "output_state": cls["output_state"],
                "gen_tokens_item": cls["n_item"],
                "gen_tokens_batch": n_batch,
                "maxnew": item["maxnew"]})
        print(f"{chunk[0]['stage']}: {start + len(chunk)}/{len(items)} items, "
              f"{(time.time()-t0)/60:.1f} min", flush=True)
    from dx_recorder_v1 import audit_pack
    audit = audit_pack(pack, out_root)
    ledger = {"finished_at": time.strftime("%Y-%m-%d %H:%M:%S"),
              "total_minutes": round((time.time()-t0)/60, 1),
              "runner": "dx_run_stage_v2 (v1 generation + per-item termination bookkeeping)",
              "item_audit_complete": audit["complete"],
              "committed_items": audit["committed"],
              "expected_items": audit["expected"],
              "incomplete_item_keys": audit["incomplete_item_keys"]}
    os.makedirs(out_root, exist_ok=True)
    with open(os.path.join(out_root, "run_ledger.json"), "x", encoding="utf-8") as f:
        json.dump(ledger, f, indent=1)
    print("GENERATION COMPLETE" if audit["complete"] else "GENERATION INCOMPLETE",
          flush=True)


if __name__ == "__main__":
    main()
