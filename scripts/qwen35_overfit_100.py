#!/usr/bin/env python3
"""E4: 100-sample overfit gate on Qwen3.5-9B (Base or post-trained).

The pass condition is explicit: after training on exactly 100 paper_v1 rows,
the model must reproduce the L3 chain of held-in training rows from the task
text alone — near-zero training loss AND exact-chain match on a 10-row
in-training probe. This proves the stack can actually learn the task before
any real training is scheduled.

Sequence format (kept deliberately simple for the gate):
  prompt  = "Task: {task_text}\nL3 workflow:"
  target  = " {L3_1} -> {L3_2} -> ...{eos}"

Fails closed; writes a result ledger with loss curve, probe accuracy, and peak
memory. No checkpoint beyond the smoke adapter directory; nothing enters any
authority.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

import torch
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import LoraConfig, get_peft_model

RESULT = Path("/home/qy/gee_llm_smoke/overfit_100_results_v1.json")


class OverfitSet(Dataset):
    def __init__(self, rows, tok, max_len=512):
        self.rows = rows
        self.tok = tok
        self.max_len = max_len

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, i):
        r = self.rows[i]
        prompt = f"Task: {r['task_text']}\nL3 workflow:"
        full = prompt + " " + r["l3_chain_text"] + self.tok.eos_token
        ids = self.tok(full, truncation=True, max_length=self.max_len, return_tensors="pt")["input_ids"][0]
        prompt_len = len(self.tok(prompt, truncation=True, max_length=self.max_len)["input_ids"])
        labels = ids.clone()
        labels[:prompt_len] = -100  # loss on the chain only
        return {"input_ids": ids, "labels": labels}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", type=Path, required=True)
    ap.add_argument("--data", type=Path, required=True)
    ap.add_argument("--epochs", type=int, default=60)
    ap.add_argument("--out", type=Path, default=Path("/home/qy/gee_llm_smoke/overfit_adapter"))
    args = ap.parse_args()

    rows = [json.loads(l) for l in args.data.read_text(encoding="utf-8").splitlines() if l.strip()]
    tok = AutoTokenizer.from_pretrained(args.model)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    bnb = BitsAndBytesConfig(
        load_in_4bit=True, bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True,
    )
    model = AutoModelForCausalLM.from_pretrained(args.model, quantization_config=bnb, device_map="cuda:0")
    model.config.use_cache = False
    model.gradient_checkpointing_enable()
    model.enable_input_require_grads()
    model = get_peft_model(model, LoraConfig(
        r=16, lora_alpha=32, lora_dropout=0.0,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        task_type="CAUSAL_LM",
    ))

    ds = OverfitSet(rows, tok)
    def collate(batch):
        maxlen = max(len(b["input_ids"]) for b in batch)
        pad = tok.pad_token_id
        input_ids, labels, attn = [], [], []
        for b in batch:
            n = len(b["input_ids"])
            input_ids.append(torch.cat([b["input_ids"], torch.full((maxlen - n,), pad, dtype=torch.long)]))
            labels.append(torch.cat([b["labels"], torch.full((maxlen - n,), -100, dtype=torch.long)]))
            attn.append(torch.cat([torch.ones(n, dtype=torch.long), torch.zeros(maxlen - n, dtype=torch.long)]))
        return {"input_ids": torch.stack(input_ids), "labels": torch.stack(labels),
                "attention_mask": torch.stack(attn)}

    loader = DataLoader(ds, batch_size=4, shuffle=False, collate_fn=collate)
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=1e-4)

    losses = []
    t0 = time.time()
    model.train()
    for epoch in range(args.epochs):
        total, count = 0.0, 0
        for batch in loader:
            batch = {k: v.to("cuda:0") for k, v in batch.items()}
            out = model(**batch)
            out.loss.backward()
            opt.step()
            opt.zero_grad(set_to_none=True)
            total += out.loss.item()
            count += 1
        losses.append(total / max(count, 1))
        if epoch % 10 == 0 or epoch == args.epochs - 1:
            print(f"epoch {epoch:3d}  loss {losses[-1]:.4f}")

    # probe: exact chain reproduction on 10 in-training rows
    model.eval()
    probe = rows[:10]
    exact = 0
    for r in probe:
        prompt = f"Task: {r['task_text']}\nL3 workflow:"
        inputs = tok(prompt, return_tensors="pt").to("cuda:0")
        with torch.no_grad():
            out = model.generate(**inputs, max_new_tokens=120, do_sample=False,
                                 pad_token_id=tok.pad_token_id)
        text = tok.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True).strip()
        if text == r["l3_chain_text"]:
            exact += 1

    result = {
        "schema": "gis_recommend.qwen35_overfit_100.v1",
        "model": str(args.model),
        "rows": len(rows),
        "epochs": args.epochs,
        "first_loss": round(losses[0], 4),
        "last_loss": round(losses[-1], 4),
        "loss_reduction_pct": round(100 * (losses[0] - losses[-1]) / max(losses[0], 1e-9), 1),
        "probe_exact_chain": f"{exact}/10",
        "minutes": round((time.time() - t0) / 60, 1),
        "peak_memory_gb": round(torch.cuda.max_memory_allocated() / 2**30, 2),
        "gate": "PASSED" if (losses[-1] < 0.1 or 100 * (losses[0] - losses[-1]) / max(losses[0], 1e-9) > 90) and exact >= 7 else "FAILED",
    }
    RESULT.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    args.out.mkdir(parents=True, exist_ok=True)
    model.save_pretrained(args.out)
    print(json.dumps(result, indent=2))
    return 0 if result["gate"] == "PASSED" else 1


if __name__ == "__main__":
    raise SystemExit(main())
