#!/usr/bin/env python3
"""M2-C0: Qwen3.5-9B-Base + plain SFT (the no-DAPT control, owner-frozen 2026-09-14).

Arm definition: Base -> SFT. The SFT recipe is byte-identical to M3-P1's
(LoRA r16/alpha32/qkvo, NF4, lr 1e-4, 1 epoch, batch 4x8, max_len 512,
paper_v1 sample weights, same 8,817 rows). The ONLY differences from
M3-P1 are: (a) base checkpoint (Base vs post-trained), (b) the eval
protocol uses the fixed EOS-aware decode (max_new_tokens=300 + eos stop
list) instead of M3-P1's original 120-token eval.

M3-P2-T1's terminal-EOS weighting is deliberately NOT used (owner ruling:
sequence control is M3's variable space, not M2's).

Evaluation: 49-row val (EOS-R1 protocol) + dev-20 runaway probe, then the
formal final-100/refusal-12 run happens under the frozen benchmark stack
(qgis_planner_predict.py) after this script's pilot gates.
"""

from __future__ import annotations

import argparse
import json
import re
import time
from collections import Counter
from pathlib import Path

import torch
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import LoraConfig, get_peft_model

CODE_RE = re.compile(r"L3_\d{2}_\d{2}_(?:\d{2}[A-Z]?|[A-Z])")  # letter-code safe
PROMPT_TEMPLATE = "Task: {task_text}\nL3 workflow:"


class SFTSet(Dataset):
    def __init__(self, rows, tok, max_len=512):
        self.rows, self.tok, self.max_len = rows, tok, max_len

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, i):
        r = self.rows[i]
        prompt = PROMPT_TEMPLATE.format(task_text=r["task_text"])
        full = prompt + " " + r["l3_chain_text"] + self.tok.eos_token
        ids = self.tok(full, truncation=True, max_length=self.max_len,
                       return_tensors="pt")["input_ids"][0]
        plen = len(self.tok(prompt, truncation=True, max_length=self.max_len)["input_ids"])
        labels = ids.clone()
        labels[:plen] = -100
        return {"input_ids": ids, "labels": labels, "weight": r.get("weight", 1.0)}


def collate(batch):
    tok = collate.tok
    maxlen = max(len(b["input_ids"]) for b in batch)
    pad = tok.pad_token_id
    ids, labels, attn, w = [], [], [], []
    for b in batch:
        n = len(b["input_ids"])
        ids.append(torch.cat([b["input_ids"], torch.full((maxlen - n,), pad, dtype=torch.long)]))
        labels.append(torch.cat([b["labels"], torch.full((maxlen - n,), -100, dtype=torch.long)]))
        attn.append(torch.cat([torch.ones(n, dtype=torch.long), torch.zeros(maxlen - n, dtype=torch.long)]))
        w.append(b["weight"])
    return {"input_ids": torch.stack(ids), "labels": torch.stack(labels),
            "attention_mask": torch.stack(attn),
            "sample_weight": torch.tensor(w, dtype=torch.float32)}


@torch.no_grad()
def generate_chain(model, tok, task_text):
    prompt = PROMPT_TEMPLATE.format(task_text=task_text)
    inputs = tok(prompt, return_tensors="pt", truncation=True, max_length=1024).to("cuda:0")
    eos_ids = [x for x in {tok.eos_token_id, tok.pad_token_id} if x is not None]
    out = model.generate(**inputs, max_new_tokens=300, do_sample=False,
                         eos_token_id=eos_ids, pad_token_id=tok.pad_token_id)
    text = tok.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True).strip()
    return text.split("\n\n")[0].split("\n")[0].strip()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", type=Path, required=True)
    ap.add_argument("--train", type=Path, required=True)
    ap.add_argument("--val", type=Path, required=True)
    ap.add_argument("--pilot-dev", type=Path, required=True)
    ap.add_argument("--ledger", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--experiment-id", default="M2-C0-v1")
    ap.add_argument("--epochs", type=int, default=1)
    ap.add_argument("--batch-size", type=int, default=4)
    ap.add_argument("--grad-accum", type=int, default=8)
    args = ap.parse_args()

    train_rows = [json.loads(l) for l in args.train.read_text(encoding="utf-8").splitlines() if l.strip()]
    val_rows = [json.loads(l) for l in args.val.read_text(encoding="utf-8").splitlines() if l.strip()]
    dev_rows = [json.loads(l) for l in args.pilot_dev.read_text(encoding="utf-8").splitlines() if l.strip()]

    tok = AutoTokenizer.from_pretrained(args.model)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    print(f"tokenizer: eos={tok.eos_token!r} pad={tok.pad_token!r} eos_id={tok.eos_token_id} pad_id={tok.pad_token_id}")
    collate.tok = tok

    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                             bnb_4bit_compute_dtype=torch.bfloat16,
                             bnb_4bit_use_double_quant=True)
    model = AutoModelForCausalLM.from_pretrained(args.model, quantization_config=bnb,
                                                 device_map="cuda:0")
    model.config.use_cache = False
    model.gradient_checkpointing_enable()
    model.enable_input_require_grads()
    model = get_peft_model(model, LoraConfig(
        r=16, lora_alpha=32, lora_dropout=0.0,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"], task_type="CAUSAL_LM"))

    ds = SFTSet(train_rows, tok)
    loader = DataLoader(ds, batch_size=args.batch_size, shuffle=True, collate_fn=collate)
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=1e-4)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    losses = []
    model.train()
    step = 0
    for epoch in range(args.epochs):
        running = 0.0
        for i, batch in enumerate(loader):
            batch = {k: v.to("cuda:0") for k, v in batch.items()}
            w = batch.pop("sample_weight")
            out = model(**batch)
            weighted = out.loss * w.mean()
            (weighted / args.grad_accum).backward()
            running += out.loss.item()
            if (i + 1) % args.grad_accum == 0:
                opt.step(); opt.zero_grad(set_to_none=True); step += 1
                if step % 50 == 0:
                    avg = running / (i + 1)
                    losses.append(avg)
                    print(f"epoch {epoch} step {step} loss {avg:.4f}", flush=True)
        opt.step(); opt.zero_grad(set_to_none=True)
    train_minutes = (time.time() - t0) / 60

    ckpt = args.out_dir / "adapter_v1"
    model.save_pretrained(ckpt)

    # ── pilot: 49-row val (EOS-R1 protocol) ──
    model.eval()
    exact = 0; pr_sum = rec_sum = 0.0; len_err = 0
    runaway_val = 0; empty_val = 0
    for r in val_rows:
        text = generate_chain(model, tok, r["task_text"])
        gc, pc = CODE_RE.findall(r["l3_chain_text"]), CODE_RE.findall(text)
        inter = sum((Counter(pc) & Counter(gc)).values())
        pr_sum += inter / max(len(pc), 1)
        rec_sum += inter / max(len(gc), 1)
        len_err += len(pc) - len(gc)
        exact += (text == r["l3_chain_text"].strip())
        runaway_val += len(pc) >= 20
        empty_val += len(pc) == 0
    val_metrics = {"n": len(val_rows), "exact_chain": exact,
                   "code_precision": round(pr_sum / len(val_rows), 4),
                   "code_recall": round(rec_sum / len(val_rows), 4),
                   "mean_length_error": round(len_err / len(val_rows), 2),
                   "runaway_rows_ge20": runaway_val, "empty_rows": empty_val}

    # ── pilot: dev-20 runaway probe ──
    dev_stats = {"n": len(dev_rows), "runaway_ge20ops_tokens": 0,
                 "empty_token_rows": 0, "mean_codes": 0.0, "max_codes": 0}
    total_codes = 0
    for r in dev_rows:
        text = generate_chain(model, tok, r["task_text"])
        codes = CODE_RE.findall(text)
        total_codes += len(codes)
        dev_stats["runaway_ge20ops_tokens"] += len(codes) >= 20
        dev_stats["empty_token_rows"] += len(codes) == 0
        dev_stats["max_codes"] = max(dev_stats["max_codes"], len(codes))
    dev_stats["mean_codes"] = round(total_codes / len(dev_rows), 2)

    result = {
        "schema": "gis_recommend.m2_c0_sft.v1",
        "arm": "M2-C0 (Base + plain SFT, no DAPT)",
        "base_model": str(args.model),
        "train_rows": len(train_rows), "epochs": args.epochs,
        "loss_first": losses[0] if losses else None,
        "loss_last": losses[-1] if losses else None,
        "train_minutes": round(train_minutes, 1),
        "peak_memory_gb": round(torch.cuda.max_memory_allocated() / 2**30, 2),
        "pilot_val": val_metrics,
        "pilot_dev20_runaway_probe": dev_stats,
        "references": {"M3-P1-EOS-R1-V2_val": {"exact": 41, "P": 0.885, "R": 0.912, "lenErr": 1.22},
                        "M3-P1_dev20": {"runaway": 3, "mean_codes": 6.95},
                        "M3-P2-T1_dev20": {"runaway": 2, "mean_codes": 4.95}},
    }
    (args.out_dir / "m2_c0_pilot_v1.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))

    from model_experiment_ledger import ExperimentLedger, sha256_file
    led = ExperimentLedger(args.ledger)
    metrics = dict(val_metrics)
    metrics["dev20_runaway_probe"] = dev_stats
    led.register(args.experiment_id, "M2-C0",
                 data_version="paper_v1_train_8817_val_49 + dev-20 probe",
                 model_path=str(args.model),
                 checkpoint_sha256=sha256_file(ckpt / "adapter_model.safetensors")
                 if (ckpt / "adapter_model.safetensors").exists() else None,
                 params={"sft_recipe": "byte-identical to M3-P1 (LoRA r16 a32 qkvo, NF4, lr 1e-4, 1 epoch, batch 4x8, max_len 512, sample weights)",
                         "base": "Qwen3.5-9B-Base (vs M3-P1 post-trained)",
                         "eval_protocol": "EOS-aware (max_new 300 + eos stop list), not M3-P1's original 120-token eval"},
                 gpu_seconds=round(time.time() - t0),
                 peak_memory_gb=result["peak_memory_gb"],
                 metrics=metrics,
                 notes="M2 control arm: isolates the post-training effect (M2-C0 vs M3-P1). No DAPT, no T1 EOS weighting.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
