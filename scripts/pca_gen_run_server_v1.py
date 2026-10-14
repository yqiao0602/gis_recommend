#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PCA formal generation run (server-side; frozen instrument v1).

Loads the frozen data pack (tasks + prompt + retrieval cards + manifest),
re-verifies SHAs, then generates for every manifest item:
  arm A_base        : Base model, plain prompt
  arm B_stage1      : Base + P0 adapter, plain prompt
  arm C_stage1_tool : Base + P0 adapter, prompt with [OPERATOR REFERENCE] cards
  arm Bprime_diag   : Base + P0 adapter, training-format separator -> Blueprint JSON
Decode: greedy, max_new_tokens=768, bs=8, left-pad, truncation 1024.
Outputs: outputs/{arm}/{task_id}/run_001.json (raw, read-only after write) +
run_ledger.json (attempt records; hardware retries <= 2; semantic signals never
retried). First successful completion wins; retries never overwrite.
"""
import json, hashlib, os, sys, time, traceback
import torch
from transformers import AutoTokenizer, AutoModelForCausalLM, BitsAndBytesConfig
from peft import PeftModel

PACK = sys.argv[1]           # frozen data pack json
OUTROOT = sys.argv[2]        # output root
BASE = "/home/qy/models/Qwen3.5/Qwen3.5-9B-Base"
ADAPTER = "/home/qy/stage1_run_planner_v2_fmt/stage1_adapter"
MAXNEW, BS, TRUNC = 768, 8, 1024
HARD_RETRY = 2

pack = json.load(open(PACK, encoding="utf-8"))
assert pack["pack_sha_ok"], "data pack SHA verification failed at load"
tasks = {t["task_id"]: t for t in pack["tasks"]}
retr = {r["task_id"]: r for r in pack["retrieval_rows"]}
prompt_tpl = pack["prompt_template"]
arm_c_insert = pack["arm_c_insert"]
bprime_sep = pack["bprime_separator"]
manifest = [m for m in pack["manifest_items"]]

def wait_gpu(min_free_mib=12000):
    import subprocess
    while True:
        out = subprocess.run(["nvidia-smi", "--query-gpu=memory.used",
                              "--format=csv,noheader,nounits"],
                             capture_output=True, text=True).stdout.strip()
        used = int(out.splitlines()[0])
        if used < 23028 - min_free_mib:
            print(f"GPU available (used={used}MiB), starting model load", flush=True)
            return
        print(f"GPU busy (used={used}MiB), waiting 180s (co-tenancy discipline)", flush=True)
        time.sleep(180)

wait_gpu()
tok = AutoTokenizer.from_pretrained(BASE, trust_remote_code=True)
if tok.pad_token is None:
    tok.pad_token = tok.eos_token
tok.padding_side = "left"
bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_compute_dtype=torch.bfloat16,
                         bnb_4bit_quant_type="nf4", bnb_4bit_use_double_quant=True)
model = AutoModelForCausalLM.from_pretrained(BASE, trust_remote_code=True,
        torch_dtype=torch.bfloat16, device_map="cuda:0", quantization_config=bnb)

def build_prompt(item):
    tid, arm = item["task_id"], item["arm"]
    tt = tasks[tid]["task_text"]
    if arm == "Bprime_diag":
        return tt + bprime_sep, False
    p = prompt_tpl.replace("{task_text}", tt)
    if arm == "C_stage1_tool":
        cards = "\n".join(x["card"] for x in retr[tid]["top15"])
        p = p.replace("[Instruction]", arm_c_insert.replace("{cards}", cards) + "\n[Instruction]")
    return p, True

def load_model_for(arm):
    """A: base; B/C/Bprime: base+adapter. Adapter load/unload per arm block."""
    if arm == "A_base":
        return model
    global m_peft
    if m_peft is None:
        m_peft = PeftModel.from_pretrained(model, ADAPTER)
    return m_peft

m_peft = None
ledger = []
t0 = time.time()
by_arm = {}
for m in manifest:
    by_arm.setdefault(m["arm"], []).append(m)

for arm in ["A_base", "B_stage1", "C_stage1_tool", "Bprime_diag"]:
    items = by_arm.get(arm, [])
    if not items:
        continue
    m = load_model_for(arm)
    m.eval()
    for s in range(0, len(items), BS):
        chunk = items[s:s + BS]
        prompts, ok_items = [], []
        for it in chunk:
            p, _ = build_prompt(it)
            prompts.append(p)
            ok_items.append(it)
        encs = [tok(p, return_tensors=None, truncation=True, max_length=TRUNC)["input_ids"]
                for p in prompts]
        maxlen = max(len(e) for e in encs)
        pad = tok.pad_token_id
        inp = {"input_ids": torch.tensor([[pad] * (maxlen - len(e)) + e for e in encs], device="cuda:0"),
               "attention_mask": torch.tensor([[0] * (maxlen - len(e)) + [1] * len(e) for e in encs], device="cuda:0")}
        attempt = 0
        while True:
            attempt += 1
            try:
                with torch.no_grad():
                    g = m.generate(**inp, max_new_tokens=MAXNEW, do_sample=False,
                                   eos_token_id=[tok.eos_token_id, tok.pad_token_id],
                                   pad_token_id=pad)
                break
            except Exception as e:
                ledger.append({"run_key": ok_items[0]["run_key"], "batch_range": s, "attempt": attempt,
                               "error": str(e)[:200], "kind": "hardware"})
                if attempt > HARD_RETRY:
                    for it in ok_items:
                        d = os.path.join(OUTROOT, arm, it["task_id"])
                        os.makedirs(d, exist_ok=True)
                        json.dump({"task_id": it["task_id"], "arm": arm, "status": "HARD_FAILED",
                                   "attempts": attempt}, open(os.path.join(d, "run_001.json"), "w"), indent=1)
                    break
                torch.cuda.empty_cache()
                time.sleep(20)
        if attempt > HARD_RETRY:
            continue
        for j, it in enumerate(ok_items):
            n_new = int(g.shape[1] - maxlen)
            text = tok.decode(g[j][maxlen:], skip_special_tokens=True)
            eol = int(text.count("END OF PLAN") > 0)
            sents = text.split(". ")[:20]
            loop = int(n_new >= MAXNEW and len(set(sents)) < max(len(sents) * 0.5, 1))
            term = "END_OF_PLAN" if eol else ("CAP_TRUNC" if n_new >= MAXNEW else "EOS")
            if term == "EOS" and loop:
                term = "DEGENERATE_LOOP"
            rec = {"task_id": it["task_id"], "arm": arm, "run_id": "run_001",
                   "prompt_sha_prefix": hashlib.sha256(prompts[j].encode()).hexdigest()[:16],
                   "raw_output": text, "gen_tokens": n_new, "hit_cap": int(n_new >= MAXNEW),
                   "termination_status": term, "attempt": attempt,
                   "main_scoring": it["main_scoring"], "status": "OK"}
            d = os.path.join(OUTROOT, arm, it["task_id"])
            os.makedirs(d, exist_ok=True)
            fp = os.path.join(d, "run_001.json")
            assert not os.path.exists(fp), f"refusing to overwrite {fp}"
            json.dump(rec, open(fp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print(f"{arm}: {s + len(chunk)}/{len(items)} rows, "
              f"{(time.time() - t0) / 60:.1f} min elapsed", flush=True)

json.dump({"finished_at": time.strftime("%Y-%m-%d %H:%M:%S"),
           "total_minutes": round((time.time() - t0) / 60, 1),
           "hardware_retry_events": sum(1 for x in ledger if x["kind"] == "hardware"),
           "ledger": ledger},
          open(os.path.join(OUTROOT, "run_ledger.json"), "w", encoding="utf-8"), indent=1)
print("GENERATION COMPLETE", flush=True)
