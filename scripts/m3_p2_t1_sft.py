#!/usr/bin/env python3
"""M3-P2-T1: terminal-EOS weighted SFT (single-variable intervention on M3-P1).

Question (frozen 2026-09-14): does strengthening ONLY the terminal-EOS
transition supervision — the last valid L3 token -> EOS, weight lambda=2 —
eliminate M3's runaway generation without losing operator-selection recall?

Everything else is byte-identical to M3-P1's SFT: same base model, same
8,817 rows, same prompt, same LoRA r16/alpha32/qkvo, same NF4, same lr,
same epochs, same sample weighting, same max_len=512 (truncation and its
173 EOS-less rows deliberately untouched — data-side changes belong to a
future T2, not T1).

Audit facts this design rests on (sft_eos_audit, 2026-09-14):
  - EOS = 1 token of ~40-60 response tokens per row (~2% loss mass)
  - 25.2% of training rows contain consecutive duplicate codes (max run 60)
    — repetition is legitimately supervised; T1 must beat this prior
  - 173/8,817 rows (2.0%, mostly 20+ chains) lost terminal EOS to the 512
    truncation; T1 leaves them exactly as P1 had them

Pilot gates (user stop-line, 2026-09-14):
  - 49-row val (EOS-R1 protocol): exact/P/R/lenErr must stay near
    M3-P1-EOS-R1-V2 (41/49, 0.885/0.912, +1.22) — no recall collapse
  - dev-20 runaway probe: runaway rows (>=20 ops) must drop from P1's 3/20
    without empty-graph explosion (P1 dev-20: 4/20 empty... see run log)
  - if runaway drops but recall collapses -> model learned "stop early",
    do NOT tune lambda further (stop-line)
"""

from __future__ import annotations

import argparse
import json
import re
import time
from collections import Counter
from pathlib import Path

import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import LoraConfig, get_peft_model

CODE_RE = re.compile(r"L3_\d{2}_\d{2}_(?:\d{2}[A-Z]?|[A-Z])")  # letter-code safe
PROMPT_TEMPLATE = "Task: {task_text}\nL3 workflow:"
OUT_DIR = Path("/home/qy/gee_llm_smoke/m3_p2_t1")


class SFTSet(Dataset):
    def __init__(self, rows, tok, max_len=512, eos_lambda=2.0):
        self.rows, self.tok, self.max_len = rows, tok, max_len
        self.eos_lambda = eos_lambda

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
        # terminal-EOS weight: lambda only at the final EOS of an UNtruncated row
        tw = torch.ones(len(ids), dtype=torch.float32)
        if len(ids) < self.max_len and int(ids[-1]) == self.tok.eos_token_id:
            tw[-1] = self.eos_lambda
        return {"input_ids": ids, "labels": labels, "weight": r.get("weight", 1.0),
                "token_weights": tw}


def collate(batch):
    tok = collate.tok
    maxlen = max(len(b["input_ids"]) for b in batch)
    pad = tok.pad_token_id
    ids, labels, attn, w, tw = [], [], [], [], []
    for b in batch:
        n = len(b["input_ids"])
        ids.append(torch.cat([b["input_ids"], torch.full((maxlen - n,), pad, dtype=torch.long)]))
        labels.append(torch.cat([b["labels"], torch.full((maxlen - n,), -100, dtype=torch.long)]))
        attn.append(torch.cat([torch.ones(n, dtype=torch.long), torch.zeros(maxlen - n, dtype=torch.long)]))
        tw.append(torch.cat([b["token_weights"], torch.ones(maxlen - n, dtype=torch.float32)]))
        w.append(b["weight"])
    return {"input_ids": torch.stack(ids), "labels": torch.stack(labels),
            "attention_mask": torch.stack(attn), "token_weights": torch.stack(tw),
            "sample_weight": torch.tensor(w, dtype=torch.float32)}


def weighted_ce_loss(model, batch):
    """Per-token CE with terminal-EOS weighting; lambda=1 reproduces HF mean loss."""
    out = model(input_ids=batch["input_ids"], attention_mask=batch["attention_mask"],
                labels=batch["labels"])
    logits = out.logits[:, :-1, :].float()
    tgt = batch["labels"][:, 1:]
    tw = batch["token_weights"][:, 1:]
    mask = tgt != -100
    ce = F.cross_entropy(logits.reshape(-1, logits.size(-1)), tgt.reshape(-1),
                         reduction="none").view(tgt.shape)
    ce = ce * mask
    w = tw * mask
    return (ce.sum() / w.sum()), out


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
    ap.add_argument("--pilot-dev", type=Path, required=True,
                    help="dev-20 tasks jsonl for the runaway probe")
    ap.add_argument("--ledger", type=Path, required=True)
    ap.add_argument("--eos-lambda", type=float, default=2.0)
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

    ds = SFTSet(train_rows, tok, eos_lambda=args.eos_lambda)
    loader = DataLoader(ds, batch_size=args.batch_size, shuffle=True, collate_fn=collate)
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=1e-4)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    losses = []
    sanity_done = False
    model.train()
    step = 0
    for epoch in range(args.epochs):
        running = 0.0
        for i, batch in enumerate(loader):
            batch = {k: v.to("cuda:0") for k, v in batch.items()}
            w = batch.pop("sample_weight")
            loss, out = weighted_ce_loss(model, batch)
            if not sanity_done:
                # lambda=1 check: unweighted token mean must match HF's out.loss
                ones = batch["token_weights"].clone().fill_(1.0)
                b2 = dict(batch); b2["token_weights"] = ones
                l1, _ = weighted_ce_loss(model, b2)
                print(f"[SANITY] weighted-mean(lam=1)={l1.item():.4f} vs HF loss="
                      f"{out.loss.item():.4f} | delta={abs(l1.item()-out.loss.item()):.5f}",
                      flush=True)
                sanity_done = True
            weighted = loss * w.mean()
            (weighted / args.grad_accum).backward()
            running += loss.item()
            if (i + 1) % args.grad_accum == 0:
                opt.step(); opt.zero_grad(set_to_none=True); step += 1
                if step % 50 == 0:
                    avg = running / (i + 1)
                    losses.append(avg)
                    print(f"epoch {epoch} step {step} loss {avg:.4f}", flush=True)
        opt.step(); opt.zero_grad(set_to_none=True)
    train_minutes = (time.time() - t0) / 60

    ckpt = OUT_DIR / f"adapter_lam{args.eos_lambda:g}"
    model.save_pretrained(ckpt)

    # ── pilot gate A: 49-row val, EOS-R1 protocol ──
    model.eval()
    exact = 0; pr_sum = rec_sum = 0.0; len_err = 0
    runaway_val = 0; empty_val = 0
    for r in val_rows:
        text = generate_chain(model, tok, r["task_text"])
        gc, pc = CODE_RE.findall(r["l3_chain_text"]), CODE_RE.findall(text)
        p, rec = (lambda a, b: (sum((Counter(a) & Counter(b)).values()) / max(sum(Counter(a).values()), 1),
                                sum((Counter(a) & Counter(b)).values()) / max(sum(Counter(b).values()), 1)))(pc, gc)
        pr_sum += p; rec_sum += rec
        len_err += len(pc) - len(gc)
        exact += (text == r["l3_chain_text"].strip())
        runaway_val += len(pc) >= 20
        empty_val += len(pc) == 0
    val_metrics = {"n": len(val_rows), "exact_chain": exact,
                   "code_precision": round(pr_sum / len(val_rows), 4),
                   "code_recall": round(rec_sum / len(val_rows), 4),
                   "mean_length_error": round(len_err / len(val_rows), 2),
                   "runaway_rows_ge20": runaway_val, "empty_rows": empty_val}

    # ── pilot gate B: dev-20 runaway probe (no scoring — count modes only) ──
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
        "schema": "gis_recommend.m3_p2_t1_sft.v1",
        "eos_lambda": args.eos_lambda,
        "train_rows": len(train_rows), "epochs": args.epochs,
        "loss_first": losses[0] if losses else None,
        "loss_last": losses[-1] if losses else None,
        "train_minutes": round(train_minutes, 1),
        "peak_memory_gb": round(torch.cuda.max_memory_allocated() / 2**30, 2),
        "pilot_val_vs": {"M3-P1-EOS-R1-V2": {"exact": 41, "P": 0.885, "R": 0.912, "lenErr": 1.22}},
        "pilot_val": val_metrics,
        "pilot_dev20_runaway_probe": dev_stats,
        "p1_dev20_reference": {"runaway": 3, "mean_codes_field": "~7 (139 tokens/20 rows), 4 empty graphs after bridge"},
        "stop_line": "if runaway drops but recall collapses -> early-stopping learned; do not tune lambda",
    }
    (OUT_DIR / f"m3_p2_t1_pilot_lam{args.eos_lambda:g}.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps(result, indent=2, ensure_ascii=False))

    from model_experiment_ledger import ExperimentLedger, sha256_file
    led = ExperimentLedger(args.ledger)
    metrics = dict(val_metrics)
    metrics["dev20_runaway_probe"] = dev_stats
    led.register(f"M3-P2-T1-PILOT-lam{args.eos_lambda:g}", "M3-P1",
                 data_version="paper_v1_train_8817_val_49 + dev-20 probe",
                 model_path=str(ckpt),
                 checkpoint_sha256=sha256_file(ckpt / "adapter_model.safetensors")
                 if (ckpt / "adapter_model.safetensors").exists() else None,
                 params={"eos_lambda": args.eos_lambda, "single_variable": "terminal-EOS loss weight only",
                         "everything_else": "identical to M3-P1 SFT (LoRA r16, NF4, lr 1e-4, 1 epoch, batch 4x8, max_len 512, truncation untouched)"},
                 gpu_seconds=round(time.time() - t0),
                 peak_memory_gb=result["peak_memory_gb"],
                 metrics=metrics,
                 notes="Pilot for terminal-EOS weighted SFT. Gates: 49-row val must hold near P1-EOS-R1-V2 (41/49, R 0.912); dev-20 runaway must drop without empty explosion. Audit context: 25.2% of train rows contain consecutive repeats (max run 60) — T1 fights a data-legitimate repetition prior.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
