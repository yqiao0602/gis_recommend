"""train_adprime_eos_v1.py — A″ endpoint-EOS SFT trainer.

DERIVED from train_stage1.py (frozen P-line trainer). Changes are limited to the marked [ADPRIME] blocks: endpoint-EOS weighted loss (lambda=2, terminal EOS only) + per-batch terminal-EOS fail-fast assertion + ledger fields. Everything else identical to the frozen trainer. Pre-registration: A_DPRIME_PREREGISTRATION v0.3.

Standalone by design: the frozen train.py (C0/A1/B1) is a two-stage
GEE->QGIS trainer and cannot express the ⑦ single-stream mixed objective.
Consumes adprime_train_v1.jsonl (300 evidence-frozen train-split rows, SHA f70b5c78...) through the same Stage1PlanCollator.

Recipe (⑦ frozen, identical hyperparams to the P0 arms):
  QLoRA NF4 double-quant, r16 alpha32, q/k/v/o, bf16, lr 1e-4 cosine,
  1 epoch, effective batch 32 (micro 2 x accum 16), max_len 1024.
Deterministic mid-stage checkpoint/resume every ckpt_every optimizer steps
(adapter + optimizer + scheduler + RNG + rows), same semantics as train.py.

Discipline: --dry-run (default) = preflight report, no GPU model load.
--release performs the run. smoke_rows>0 overfits a small slice first
(engineering gate; expect loss to approach 0).
"""
from __future__ import annotations

import argparse
import json
import math
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from route2_training.plans.stage1_collator import (Stage1PlanCollator,
                                                   TaskTooLongError)

TRAIN_SEED = 20260924          # same family as the dataset builder seed


def load_config(path: str) -> dict:
    import ast
    out = {}
    for line in Path(path).read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        k, _, v = line.partition(":")
        k, v = k.strip(), v.strip()
        if not k:
            continue
        if v.startswith(('"', "'")):
            out[k] = ast.literal_eval(v)
        else:
            try:
                out[k] = ast.literal_eval(v)
            except (ValueError, SyntaxError):
                out[k] = v
    return out


def sha256_file(path: str) -> str:
    import hashlib
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def get_peft_model_state_dict_local(peft_model):
    from peft.utils.save_and_load import get_peft_model_state_dict
    return get_peft_model_state_dict(peft_model)


def load_rows(path: str) -> list[dict]:
    rows = []
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            if line.strip():
                rows.append(json.loads(line))
    return rows


# ── [ADPRIME] endpoint-EOS weighted loss (frozen spec v0.3 §1) ──────────
def endpoint_eos_weighted_loss(logits, labels, eos_id, lam):
    """CE with weight lam on each row's TERMINAL EOS label only.
    Pre-registered formula: sum(ce*w)/sum(w), w=mask, terminal EOS=lam.
    Fail-fast: terminal non-masked label must be EOS in every row."""
    import torch
    import torch.nn.functional as F
    # bf16 CE (same precision/memory profile as the model's internal loss;
    # the fp32 upcast materialized a +1.2GiB copy and OOM'd alongside a
    # co-tenant job)
    shift_logits = logits[:, :-1, :]
    shift_labels = labels[:, 1:]
    ce = F.cross_entropy(shift_logits.transpose(1, 2), shift_labels,
                         ignore_index=-100, reduction="none").float()
    mask = shift_labels != -100
    pos = torch.arange(1, labels.shape[1], device=labels.device)
    last = (mask.float() * pos).argmax(dim=1)
    has = mask.any(dim=1)
    rows = torch.arange(ce.shape[0], device=ce.device)
    if not bool(shift_labels[rows[has], last[has]].eq(eos_id).all()):
        raise AssertionError(
            "[ADPRIME] terminal non-masked label is not EOS — training aborted")
    w = mask.float()
    w[rows[has], last[has]] = float(lam)
    return (ce * w).sum() / w.sum()


def preflight(cfg: dict, rows: list[dict]) -> dict:
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(cfg["base_model"])
    if tok.pad_token is None and tok.eos_token is not None:
        tok.pad_token = tok.eos_token
    col = Stage1PlanCollator(tok, cfg["max_len"])

    rng = random.Random(cfg["seed"])
    sample = rng.sample(rows, min(500, len(rows)))
    n_task_too_long = 0
    stat = {"task": [], "ctx": [], "tgt": [], "eff": [],
            "ctx_trunc_rows": 0, "tgt_trunc_rows": 0,
            "ctx_trunc_tokens": 0, "tgt_trunc_tokens": 0}
    for r in sample:
        try:
            e = col.encode_example(r)
        except TaskTooLongError:
            n_task_too_long += 1
            continue
        stat["task"].append(e["task_tokens"])
        stat["ctx"].append(e["context_tokens"])
        stat["tgt"].append(e["target_tokens"])
        stat["eff"].append(len(e["input_ids"]))
        stat["ctx_trunc_rows"] += e["context_truncated_tokens"] > 0
        stat["tgt_trunc_rows"] += e["target_truncated_tokens"] > 0
        stat["ctx_trunc_tokens"] += e["context_truncated_tokens"]
        stat["tgt_trunc_tokens"] += e["target_truncated_tokens"]

    def q(vals, p):
        s = sorted(vals)
        return s[min(len(s) - 1, int(p * (len(s) - 1)))] if s else 0

    cats = {}
    for r in rows:
        cats[r["cat"]] = cats.get(r["cat"], 0) + 1
    by_cat_rows = {c: [r for r in sample if r["cat"] == c][:40] for c in cats}
    cat_roundtrip = {}
    for c, rs in by_cat_rows.items():
        if not rs:
            continue
        b = col(rs)
        cat_roundtrip[c] = {
            "batch": len(b["input_ids"]),
            "max_len": max(len(x) for x in b["input_ids"]),
            "loss_tokens": sum(sum(1 for t in lab if t != -100) for lab in b["labels"]),
        }
    report = {
        "arm": cfg["name"], "base_model": cfg["base_model"],
        "train_data": cfg["train_data"], "train_data_sha256": sha256_file(cfg["train_data"]),
        "rows": len(rows), "cats": cats,
        "sample_n": len(sample), "sample_task_too_long": n_task_too_long,
        "token_stats": {
            "task_p50_p90_max": [q(stat["task"], .5), q(stat["task"], .9), max(stat["task"] or [0])],
            "ctx_p50_p90_max": [q(stat["ctx"], .5), q(stat["ctx"], .9), max(stat["ctx"] or [0])],
            "tgt_p50_p90_max": [q(stat["tgt"], .5), q(stat["tgt"], .9), max(stat["tgt"] or [0])],
            "eff_p50_p90_max": [q(stat["eff"], .5), q(stat["eff"], .9), max(stat["eff"] or [0])],
            "ctx_truncated_rows": stat["ctx_trunc_rows"],
            "tgt_truncated_rows": stat["tgt_trunc_rows"],
            "ctx_truncated_tokens": stat["ctx_trunc_tokens"],
            "tgt_truncated_tokens": stat["tgt_trunc_tokens"],
        },
        "collator_batch_roundtrip": cat_roundtrip,
        "max_len": cfg["max_len"],
        "seed": cfg["seed"],
        "epochs": cfg["epochs"], "smoke_rows": cfg.get("smoke_rows", 0),
        "effective_batch": cfg["batch_size"] * cfg["grad_accum"],
        "est_optimizer_steps_full": math.ceil(
            (cfg.get("smoke_rows", 0) or len(rows)) * cfg["epochs"]
            / (cfg["batch_size"] * cfg["grad_accum"])),
    }
    return report


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--release", action="store_true")
    ap.add_argument("--init-adapter", default=None,
                    help="Peft adapter dir to load as starting weights "
                         "(fresh optimizer/step counter); P1 rep-pivot use")
    a = ap.parse_args()
    if a.dry_run == a.release:
        print("pass exactly one of --dry-run / --release")
        return 2
    cfg = load_config(a.config)
    if getattr(a, "init_adapter", None) is None and cfg.get("init_adapter"):
        a.init_adapter = cfg["init_adapter"]
    t0 = time.time()
    rows = load_rows(cfg["train_data"])
    print(f"[data] {len(rows)} rows from {cfg['train_data']}", flush=True)

    report = preflight(cfg, rows)
    out = Path(cfg["output_dir"])
    out.mkdir(parents=True, exist_ok=True)
    (out / "preflight_stage1.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps({k: report[k] for k in
                      ("arm", "rows", "cats", "sample_task_too_long",
                       "token_stats", "est_optimizer_steps_full")},
                     ensure_ascii=False, indent=1))
    if a.dry_run:
        print(f"[dry-run] preflight written to {out / 'preflight_stage1.json'} "
              f"({time.time() - t0:.1f}s); no GPU model load.")
        return 0

    # ── release path ──────────────────────────────────────────────────────
    import torch
    from transformers import (AutoModelForCausalLM, AutoTokenizer,
                              BitsAndBytesConfig)
    from peft import LoraConfig, get_peft_model

    torch.manual_seed(cfg["seed"])
    random.seed(cfg["seed"])
    torch.cuda.manual_seed_all(cfg["seed"])

    tok = AutoTokenizer.from_pretrained(cfg["base_model"])
    if tok.pad_token is None and tok.eos_token is not None:
        tok.pad_token = tok.eos_token
    col = Stage1PlanCollator(tok, cfg["max_len"])

    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                             bnb_4bit_compute_dtype=torch.bfloat16,
                             bnb_4bit_use_double_quant=True)
    model = AutoModelForCausalLM.from_pretrained(
        cfg["base_model"], quantization_config=bnb, device_map="cuda:0")
    model.config.use_cache = False
    model.gradient_checkpointing_enable()
    model = get_peft_model(model, LoraConfig(
        r=16, lora_alpha=32, lora_dropout=0.05, bias="none",
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"],
        task_type="CAUSAL_LM"))
    if getattr(a, "init_adapter", None):
        from safetensors.torch import load_file
        from peft.utils.save_and_load import set_peft_model_state_dict
        sd = load_file(str(Path(a.init_adapter) / "adapter_model.safetensors"))
        set_peft_model_state_dict(model, sd)
        print(f"[init-adapter] weights loaded from {a.init_adapter} "
              "(fresh optimizer, step 0)", flush=True)

    smoke = int(cfg.get("smoke_rows", 0) or 0)
    epochs = int(cfg["epochs"])
    if smoke:
        rng = random.Random(cfg["seed"])
        idx = list(range(len(rows)))
        rng.shuffle(idx)
        rows = [rows[i] for i in idx[:smoke]]
        epochs = int(cfg.get("smoke_epochs", 3))
        print(f"[smoke] overfitting first {len(rows)} shuffled rows x {epochs} epochs", flush=True)
    else:
        rng = random.Random(cfg["seed"])
        rng.shuffle(rows)
        print(f"[release] full run: {len(rows)} rows x {epochs} epoch", flush=True)

    bs, accum = int(cfg["batch_size"]), int(cfg["grad_accum"])
    steps_per_epoch = math.ceil(len(rows) / bs)
    total_steps = epochs * steps_per_epoch
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],
                            lr=float(cfg["max_lr"]))
    sched = torch.optim.lr_scheduler.LambdaLR(
        opt, lambda s: 0.5 * (1 + math.cos(math.pi * min(s / max(total_steps, 1), 1.0))))

    ckpt_dir = out / "stage1_ckpt"
    ckpt_dir.mkdir(parents=True, exist_ok=True)
    latest = ckpt_dir / "latest.pt"
    start_step = 0
    rows_done = 0
    if latest.exists():
        from peft.utils.save_and_load import set_peft_model_state_dict
        ck = torch.load(latest, map_location="cpu", weights_only=False)
        set_peft_model_state_dict(model, ck["peft"])
        opt.load_state_dict(ck["optim"])
        sched.load_state_dict(ck["sched"])
        start_step, rows_done = ck["step"], ck["rows_consumed"]
        torch.set_rng_state(ck["rng_cpu"])
        torch.cuda.set_rng_state_all(ck["rng_cuda"])
        random.setstate(ck["rng_py"])
        print(f"  [resume] step {start_step} (rows {rows_done})", flush=True)

    order = list(range(len(rows)))
    random.shuffle(order)          # continues from restored RNG state on resume

    log_every = int(cfg.get("log_every", 20))
    ckpt_every = int(cfg.get("ckpt_every", 150))
    accum_loss, accum_tokens = 0.0, 0
    stats = {"examples": 0, "tokens": 0, "target_truncated": 0,
             "context_truncated": 0, "task_too_long": 0}
    model.train()
    step = start_step
    t0 = time.time()
    micro_bs = bs

    done = False
    for epoch in range(epochs):
        if done:
            break
        for k in range(0, len(order), micro_bs):
            chunk = [rows[i] for i in order[k:k + micro_bs]]
            try:
                batch = col(chunk)
            except TaskTooLongError as e:
                stats["task_too_long"] += 1
                print(f"  [skip] TaskTooLongError: {e}", flush=True)
                continue
            inputs = {"input_ids": torch.tensor(batch["input_ids"], device="cuda:0"),
                      "labels": torch.tensor(batch["labels"], device="cuda:0"),
                      "attention_mask": torch.tensor(batch["attention_mask"], device="cuda:0")}
            # [ADPRIME] endpoint-EOS weighted loss (lambda from config)
            lam = float(cfg.get("endpoint_eos_lambda", 2.0))
            raw = endpoint_eos_weighted_loss(
                model(**inputs).logits, inputs["labels"],
                tok.eos_token_id, lam)
            loss = raw / accum
            loss.backward()
            accum_loss += loss.item()
            accum_tokens += sum(batch["target_tokens"])
            stats["examples"] += len(chunk)
            stats["tokens"] += sum(batch["target_tokens"])
            stats["target_truncated"] += sum(1 for t in batch["target_truncated_tokens"] if t > 0)
            # context_truncated_tokens is computed in encode_example but not
            # returned by the frozen collator's __call__; preflight reports it.
            rows_done += len(chunk)
            if (k // micro_bs) % accum == accum - 1:
                torch.nn.utils.clip_grad_norm_(
                    [p for p in model.parameters() if p.requires_grad], 1.0)
                opt.step()
                sched.step()
                opt.zero_grad(set_to_none=True)
                step += 1
                if step % log_every == 0:
                    print(f"  step {step}/{total_steps} loss={accum_loss * accum / log_every:.4f} "
                          f"lr={sched.get_last_lr()[0]:.2e} rows={rows_done} "
                          f"tgt_trunc={stats['target_truncated']} "
                          f"({time.time() - t0:.0f}s)", flush=True)
                    accum_loss = 0.0
                if step % ckpt_every == 0:
                    from peft.utils.save_and_load import get_peft_model_state_dict
                    torch.save({"peft": get_peft_model_state_dict(model),
                                "optim": opt.state_dict(), "sched": sched.state_dict(),
                                "step": step, "rows_consumed": rows_done,
                                "rng_cpu": torch.get_rng_state(),
                                "rng_cuda": torch.cuda.get_rng_state_all(),
                                "rng_py": random.getstate()}, latest)
                    print(f"  [ckpt] step {step} saved", flush=True)
                if step >= total_steps:
                    done = True
                    break
        if done:
            break

    from peft.utils.save_and_load import get_peft_model_state_dict
    model.save_pretrained(str(out / "stage1_adapter"))
    tok.save_pretrained(str(out / "stage1_adapter"))
    torch.save({"peft": get_peft_model_state_dict(model),
                "optim": opt.state_dict(), "sched": sched.state_dict(),
                "step": step, "rows_consumed": rows_done,
                "rng_cpu": torch.get_rng_state(),
                "rng_cuda": torch.cuda.get_rng_state_all(),
                "rng_py": random.getstate()}, latest)
    ledger = {
        "arm": cfg["name"], "mode": "smoke" if smoke else "release",
        "endpoint_eos_lambda": float(cfg.get("endpoint_eos_lambda", 2.0)),
        "preregistration": "A_DPRIME_PREREGISTRATION v0.3",
        "config": cfg, "train_data_sha256": sha256_file(cfg["train_data"]),
        "rows": len(rows), "epochs": epochs, "steps": step,
        "stats": stats, "final_loss_window": accum_loss,
        "elapsed_s": round(time.time() - t0, 1),
        "adapter": str(out / "stage1_adapter"),
    }
    name = "run_ledger_smoke.json" if smoke else "run_ledger.json"
    (out / name).write_text(json.dumps(ledger, ensure_ascii=False, indent=1),
                            encoding="utf-8")
    print(f"[done] mode={ledger['mode']} steps={step} examples={stats['examples']} "
          f"tokens={stats['tokens']} tgt_trunc={stats['target_truncated']} "
          f"task_too_long={stats['task_too_long']} elapsed={ledger['elapsed_s']}s",
          flush=True)
    print(f"[done] ledger -> {out / name}; adapter -> {out / 'stage1_adapter'}",
          flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
