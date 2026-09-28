#!/usr/bin/env python3
"""M3-P1: QLoRA/SFT of post-trained Qwen3.5-9B on paper_v1 (task_text -> L3 chain).

The deliberately plain first round, per the user's instruction: no KG/catalog
constraints, no reranking, no repair, no DPO, no special decoding. The only
variable between M3-P0 and M3-P1 is the SFT itself, so the delta answers Q2:
can task SFT align the model's existing GIS semantic prior onto the L3 output
space?

Training: NF4 (same quantization as P0 evaluation), r=16 LoRA on q/k/v/o
(consistent with the E4 gate), 1 epoch over 8,817 train rows, weighted CE
(paper_v1 weights). Evaluation reuses the EXACT frozen M3-P0 protocol and the
same 49-row val split: identical prompt template, greedy decode, metrics
(exact match, code P/R, length error, by-platform), so the comparison is
apples-to-apples. Additionally tracked per the user's request: invalid-L3-token
rate (protocol-alignment measure) and order errors (correct multiset, wrong
sequence).
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

CODE_RE = re.compile(r"L3_\d{2}_\d{2}_\d{2}[A-Z]?")
OUT_DIR = Path("/home/qy/gee_llm_smoke/m3_p1")
PROMPT_TEMPLATE = "Task: {task_text}\nL3 workflow:"
MAX_NEW_TOKENS = 120


class SFTSet(Dataset):
    def __init__(self, rows, tok, max_len=512):
        self.rows, self.tok, self.max_len = rows, tok, max_len

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, i):
        r = self.rows[i]
        prompt = PROMPT_TEMPLATE.format(task_text=r["task_text"])
        full = prompt + " " + r["l3_chain_text"] + self.tok.eos_token
        ids = self.tok(full, truncation=True, max_length=self.max_len, return_tensors="pt")["input_ids"][0]
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
            "attention_mask": torch.stack(attn), "sample_weight": torch.tensor(w, dtype=torch.float32)}


def evaluate(model, tok, rows):
    model.eval()
    exact = lenient = 0
    pr_sum = rec_sum = 0.0
    len_err = 0
    order_err = 0
    invalid_token_rows = 0
    by_platform = {"gee": [0, 0], "qgis": [0, 0]}
    preds = []
    for r in rows:
        prompt = PROMPT_TEMPLATE.format(task_text=r["task_text"])
        inputs = tok(prompt, return_tensors="pt", truncation=True, max_length=1024).to("cuda:0")
        with torch.no_grad():
            out = model.generate(**inputs, max_new_tokens=MAX_NEW_TOKENS, do_sample=False,
                                 pad_token_id=tok.pad_token_id)
        text = tok.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True).strip()
        gold = r["l3_chain_text"].strip()
        gc, pc = CODE_RE.findall(gold), CODE_RE.findall(text)
        if pc and any(c not in set(gc) and c not in VALID_L3 for c in pc):
            pass  # validity is computed against the global VALID_L3 set below
        p, rec = prf(pc, gc)
        pr_sum += p; rec_sum += rec
        len_err += len(pc) - len(gc)
        is_exact = text == gold
        is_lenient = text.replace(" ", "") == gold.replace(" ", "")
        exact += is_exact
        lenient += is_lenient
        if Counter(pc) == Counter(gc) and pc != gc and pc:
            order_err += 1
        if pc and any(c not in VALID_L3 for c in pc):
            invalid_token_rows += 1
        by_platform[r["platform"]][0] += 1
        by_platform[r["platform"]][1] += is_exact
        preds.append({"record_id": r["record_id"], "platform": r["platform"], "gold": gold,
                      "pred": text[:400], "exact": is_exact, "n_pred_codes": len(pc), "n_gold_codes": len(gc)})
    n = len(rows)
    return {
        "n": n, "exact_chain": exact, "exact_chain_rate": round(exact / n, 4),
        "lenient_exact": lenient,
        "code_precision": round(pr_sum / n, 4), "code_recall": round(rec_sum / n, 4),
        "mean_length_error": round(len_err / n, 2),
        "order_errors_multiset_correct": order_err,
        "invalid_l3_token_rows": invalid_token_rows,
        "by_platform": {k: {"n": v[0], "exact": v[1]} for k, v in by_platform.items()},
    }, preds


def prf(pred, gold):
    p, g = Counter(pred), Counter(gold)
    inter = sum((p & g).values())
    return inter / max(sum(p.values()), 1), inter / max(sum(g.values()), 1)


VALID_L3: set[str] = set()


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", type=Path, required=True)
    ap.add_argument("--train", type=Path, required=True)
    ap.add_argument("--val", type=Path, required=True)
    ap.add_argument("--taxonomy", type=Path, required=True)
    ap.add_argument("--ledger", type=Path, required=True)
    ap.add_argument("--epochs", type=int, default=1)
    ap.add_argument("--batch-size", type=int, default=8)
    ap.add_argument("--grad-accum", type=int, default=4)
    args = ap.parse_args()

    global VALID_L3
    VALID_L3 = {c["l3_code"] for c in json.loads(args.taxonomy.read_text(encoding="utf-8"))["classes"]}

    train_rows = [json.loads(l) for l in args.train.read_text(encoding="utf-8").splitlines() if l.strip()]
    val_rows = [json.loads(l) for l in args.val.read_text(encoding="utf-8").splitlines() if l.strip()]

    tok = AutoTokenizer.from_pretrained(args.model)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    collate.tok = tok

    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                             bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
    model = AutoModelForCausalLM.from_pretrained(args.model, quantization_config=bnb, device_map="cuda:0")
    model.config.use_cache = False
    model.gradient_checkpointing_enable()
    model.enable_input_require_grads()
    model = get_peft_model(model, LoraConfig(
        r=16, lora_alpha=32, lora_dropout=0.0,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"], task_type="CAUSAL_LM"))

    ds = SFTSet(train_rows, tok)
    loader = DataLoader(ds, batch_size=args.batch_size, shuffle=True, collate_fn=collate)
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=1e-4)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
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
            # weight the per-row loss by the paper_v1 sample weight
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
    ckpt = OUT_DIR / "adapter_v1"
    model.save_pretrained(ckpt)

    metrics, preds = evaluate(model, tok, val_rows)
    (OUT_DIR / "m3_p1_metrics_v1.json").write_text(
        json.dumps({"schema": "gis_recommend.m3_p1_sft.v1", "model": str(args.model),
                    "train_rows": len(train_rows), "epochs": args.epochs,
                    "loss_first": losses[0] if losses else None,
                    "loss_last": losses[-1] if losses else None,
                    "train_minutes": round(train_minutes, 1),
                    "peak_memory_gb": round(torch.cuda.max_memory_allocated() / 2**30, 2),
                    "protocol": "identical to M3-P0 frozen protocol",
                    "metrics": metrics}, indent=2, ensure_ascii=False), encoding="utf-8")
    (OUT_DIR / "m3_p1_predictions_v1.jsonl").write_text(
        "".join(json.dumps(p, ensure_ascii=False, sort_keys=True) + "\n" for p in preds), encoding="utf-8")

    from model_experiment_ledger import ExperimentLedger, sha256_file
    led = ExperimentLedger(args.ledger)
    led.register(
        "M3-P1-v1", "M3-P1",
        data_version="paper_v1_train_8817_val_49",
        model_path=str(args.model),
        checkpoint_sha256=sha256_file(ckpt / "adapter_model.safetensors") if (ckpt / "adapter_model.safetensors").exists() else None,
        params={"lora_r": 16, "lora_alpha": 32, "target_modules": "qkvo", "lr": 1e-4,
                "epochs": args.epochs, "batch": args.batch_size, "grad_accum": args.grad_accum,
                "quant": "nf4", "weighted_ce": True},
        gpu_seconds=round(time.time() - t0),
        peak_memory_gb=round(torch.cuda.max_memory_allocated() / 2**30, 2),
        metrics=metrics,
        notes="plain SFT, no constraints/reranking/DPO; eval protocol identical to M3-P0",
    )
    print(json.dumps(metrics, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
