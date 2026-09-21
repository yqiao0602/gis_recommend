"""train.py — the single trainer behind C0/A1/B1.

One implementation, three arms via config (P0 ruling: no separate training
logics). Arms differ ONLY in the GEE stage:

  C0: Base ---------------------------------> QGIS SFT -> dev-120 -> best ckpt
  A1: Base -> GEE DAPT (causal LM) --merge--> QGIS SFT -> dev-120 -> best ckpt
  B1: Base -> GEE Semantic SFT -----merge--> QGIS SFT -> dev-120 -> best ckpt

Recipe (M2-comparable, frozen this round): Qwen base + QLoRA NF4 double-quant,
r16 alpha32, qkvo targets, bf16, lr 1e-4 cosine, effective batch 32.
GEE stage: 1 epoch, fixed (no QGIS dev peeking).
QGIS SFT: 20 epochs, dev-120 operator-set-F1 checkpoint selection per P0-5.
Merge-then-new-LoRA handoff between stages (bf16), as in M2.

Discipline: --dry-run (default) emits the preflight report and touches no
GPU. Training requires --release after owner review of the preflight pack.
Forbidden and absent by construction: aux GEE loss in B1, DPO/RL, curriculum,
dynamic sampling, ratio tuning, any new split, any edit to frozen data.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from route2_training.harness import ArmConfig, sha256_file
from route2_training.data.gee_stage_datasets import GeeSemanticDataset, GeeDaptCorpus
from route2_training.collators.qgis_graph_collator import (QgisGraphDataset,
                                                           QgisGraphCollator)
from route2_training.collators.causal_lm_collator import CausalLMCollator

LORA_TARGET = ["q_proj", "k_proj", "v_proj", "o_proj"]
B1_SUFFIX = "\nGIS workflow:"


def load_config(path: str) -> ArmConfig:
    text = Path(path).read_text(encoding="utf-8")
    try:
        import yaml
        d = yaml.safe_load(text)
    except ImportError:
        d = _mini_yaml(text)          # no PyYAML dependency; flat key: value files
    return ArmConfig(**d)


def _mini_yaml(text: str) -> dict:
    """Flat `key: value` parser for the arm configs (no nesting needed)."""
    import ast
    out = {}
    for line in text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        k, _, v = line.partition(":")
        k, v = k.strip(), v.strip()
        if v.startswith(('"', "'")):
            out[k] = ast.literal_eval(v)
        else:
            try:
                out[k] = ast.literal_eval(v)
            except (ValueError, SyntaxError):
                out[k] = v
    return out


# ── preflight ──────────────────────────────────────────────────────────────

def preflight(cfg: ArmConfig, tokenizer) -> dict:
    report: dict = {"arm": cfg.name, "base_model": cfg.base_model}

    qds = QgisGraphDataset(cfg.qgis_train)
    qcol = QgisGraphCollator(tokenizer, cfg.max_len)
    q_tok = q_trunc_t = q_trunc_p = 0
    q_tlen = []
    for i in range(len(qds)):
        prompt, target = qds.prompt_target(i)
        e = qcol.encode_pair(prompt, target)
        q_tok += len(e["input_ids"])
        q_trunc_t += e["n_target_truncated"] > 0
        q_trunc_p += e["n_prompt_truncated"] > 0
        q_tlen.append(len(e["input_ids"]))
    q_tlen.sort()
    report["qgis_sft"] = {
        "rows": len(qds), "train_sha": qds.sha,
        "tokens": q_tok,
        "rows_target_truncated": q_trunc_t, "rows_prompt_truncated": q_trunc_p,
        "len_p50": q_tlen[len(q_tlen) // 2], "len_p90": q_tlen[int(len(q_tlen) * 0.9)],
    }

    if cfg.gee_stage == "dapt":
        corp = GeeDaptCorpus(cfg.gee_data, split="train")
        col = CausalLMCollator(tokenizer, cfg.max_len)
        g_tok = g_trunc = 0
        gl = []
        for i in range(len(corp)):
            e = col.encode_text(corp.domain_text(i))
            g_tok += len(e["input_ids"])
            g_trunc += e["n_truncated"] > 0
            gl.append(len(e["input_ids"]))
        gl.sort()
        report["gee_stage"] = {
            "kind": "dapt", "rows": len(corp), "data_sha": corp.sha,
            "tokens": g_tok, "rows_truncated": g_trunc,
            "len_p50": gl[len(gl) // 2], "len_p90": gl[int(len(gl) * 0.9)],
        }
    elif cfg.gee_stage == "semantic_sft":
        gds = GeeSemanticDataset(cfg.gee_data, split="train")
        gcol = QgisGraphCollator(tokenizer, cfg.max_len, prompt_suffix=B1_SUFFIX)
        g_tok = g_trunc_t = g_trunc_p = 0
        gl, raw_l, fin_l = [], [], []
        for i in range(len(gds)):
            prompt, target = gds.prompt_target(i)
            e = gcol.encode_pair(prompt, target)
            g_tok += len(e["input_ids"])
            g_trunc_t += e["n_target_truncated"] > 0
            g_trunc_p += e["n_prompt_truncated"] > 0
            gl.append(len(e["input_ids"]))
            fin_l.append(gds.rows[i]["final_semantic_length"])
            raw_l.append(gds.rows[i]["original_semantic_length"])
        gl.sort(); raw_l.sort(); fin_l.sort()
        report["gee_stage"] = {
            "kind": "semantic_sft", "rows": len(gds), "data_sha": gds.sha,
            "tokens": g_tok,
            "rows_target_truncated": g_trunc_t, "rows_prompt_truncated": g_trunc_p,
            "len_p50": gl[len(gl) // 2], "len_p90": gl[int(len(gl) * 0.9)],
            "truncation_report": {
                "n_total": len(gds), "n_truncated": g_trunc_t,
                "truncation_rate": round(g_trunc_t / max(len(gds), 1), 4),
                "raw_length_p50": raw_l[len(raw_l) // 2],
                "raw_length_p90": raw_l[int(len(raw_l) * 0.9)],
                "final_length_p50": fin_l[len(fin_l) // 2],
                "final_length_p90": fin_l[int(len(fin_l) * 0.9)],
                "max_length": cfg.max_len,
                "max_observed": gl[-1],
            },
        }
    else:
        report["gee_stage"] = {"kind": "none", "rows": 0, "tokens": 0}

    report["sha"] = {
        "qgis_train": sha256_file(cfg.qgis_train),
        "qgis_dev": sha256_file(cfg.qgis_dev),
        "qgis_test": sha256_file(cfg.qgis_test),
    }
    return report


# ── training (release-gated) ───────────────────────────────────────────────

def build_lora(model):
    from peft import LoraConfig, get_peft_model
    lcfg = LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05,
                      target_modules=LORA_TARGET,
                      task_type="CAUSAL_LM")
    model = get_peft_model(model, lcfg)
    # A10 shares with a 4.4GB resident kernel; checkpointing keeps
    # 9B batch8x1024 activations in a few GB instead of >12GB
    model.gradient_checkpointing_enable()
    model.enable_input_require_grads()
    return model


def load_base_4bit(base_model: str):
    import torch
    from transformers import (AutoModelForCausalLM, BitsAndBytesConfig)
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                             bnb_4bit_compute_dtype=torch.bfloat16,
                             bnb_4bit_use_double_quant=True)
    return AutoModelForCausalLM.from_pretrained(base_model, quantization_config=bnb,
                                                device_map="cuda:0")


def examples_from(ds, collator, suffix_col=None):
    out = []
    for i in range(len(ds)):
        prompt, target = ds.prompt_target(i)
        if suffix_col is not None:
            out.append(suffix_col.encode_pair(prompt, target))
        else:
            out.append(collator(collator_batch(prompt, target)))
    return out


def collator_batch(prompt, target):
    return {"prompt": prompt, "target": target}


def train_stage(model, ds, collator, epochs, lr, bs, accum, log_every=50,
                masked=True, ckpt_dir=None, ckpt_every=150):
    """Training with deterministic mid-stage checkpoint/resume.

    Every ckpt_every optimizer steps: adapter weights + optimizer state +
    scheduler state + RNG states + rows-consumed are saved, so a crash or
    reboot resumes the SAME trajectory (identical shuffled order, LR
    position, RNG). Near-exact continuation (GPU matmul nondeterminism
    aside). Resumes automatically if ckpt_dir/latest.pt exists.
    """
    import torch
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad],
                            lr=lr)
    total = epochs * math.ceil(len(ds) / bs)
    sched = torch.optim.lr_scheduler.LambdaLR(
        opt, lambda step: 0.5 * (1 + math.cos(math.pi * min(step / max(total, 1), 1.0))))

    start_step, rows_consumed = 0, 0
    if ckpt_dir:
        ckpt_dir = Path(ckpt_dir)
        ckpt_dir.mkdir(parents=True, exist_ok=True)
        latest = ckpt_dir / "latest.pt"
        if latest.exists():
            from peft.utils.save_and_load import set_peft_model_state_dict
            ck = torch.load(latest, map_location="cpu", weights_only=False)
            set_peft_model_state_dict(model, ck["peft"])
            opt.load_state_dict(ck["optim"])
            sched.load_state_dict(ck["sched"])
            start_step = ck["step"]
            rows_consumed = ck["rows_consumed"]
            torch.set_rng_state(ck["rng_cpu"])
            torch.cuda.set_rng_state_all(ck["rng_cuda"])
            import random as _r
            _r.setstate(ck["rng_py"])
            print(f"  [resume] stage checkpoint at step {start_step} "
                  f"(rows {rows_consumed})", flush=True)

    def make_batches(skip_rows=0):
        idx = list(range(len(ds)))
        random.Random(20260917).shuffle(idx)
        for k in range(skip_rows - skip_rows % bs, len(idx), bs):
            chunk = idx[k:k + bs]
            if masked:
                batch = [{"prompt": ds.prompt_target(i)[0],
                          "target": ds.prompt_target(i)[1]} for i in chunk]
            else:
                batch = [{"text": ds.domain_text(i)} for i in chunk]
            c = collator(batch)
            c["trunc_target"] = [e["n_target_truncated"] > 0 for e in
                                 (collator.encode_pair(b["prompt"], b["target"]) for b in batch)] if masked else [False] * len(chunk)
            c["trunc_prompt"] = [e["n_prompt_truncated"] > 0 for e in
                                 (collator.encode_pair(b["prompt"], b["target"]) for b in batch)] if masked else [False] * len(chunk)
            c["trunc_text"] = [collator.encode_text(b["text"])["n_truncated"] > 0
                               for b in batch] if not masked else [False] * len(chunk)
            yield c

    stats = {"n_examples": 0, "n_tokens": 0,
             "n_target_truncated": 0, "n_prompt_truncated": 0, "n_text_truncated": 0}
    model.train()
    step = start_step
    from peft.utils.save_and_load import get_peft_model_state_dict

    def save_ckpt(step_now, rows_now):
        if not ckpt_dir:
            return
        torch.save({
            "peft": get_peft_model_state_dict(model),
            "optim": opt.state_dict(), "sched": sched.state_dict(),
            "step": step_now, "rows_consumed": rows_now,
            "rng_cpu": torch.get_rng_state(),
            "rng_cuda": torch.cuda.get_rng_state_all(),
            "rng_py": random.getstate(),
        }, Path(ckpt_dir) / "latest.pt")

    done_epochs = start_step // max(math.ceil(len(ds) / (bs * accum)), 1)
    skipped_in_epoch = rows_consumed
    for ep in range(epochs):
        if ep < done_epochs:
            continue
        skip = skipped_in_epoch if ep == done_epochs else 0
        skipped_in_epoch = 0
        running = 0.0
        for bi, batch in enumerate(make_batches(skip)):
            skip = 0
            stats["n_examples"] += len(batch["input_ids"])
            stats["n_tokens"] += sum(len(x) for x in batch["input_ids"])
            stats["n_target_truncated"] += sum(1 for t in batch.get("trunc_target", []) if t)
            stats["n_prompt_truncated"] += sum(1 for t in batch.get("trunc_prompt", []) if t)
            stats["n_text_truncated"] += sum(1 for t in batch.get("trunc_text", []) if t)
            out = model(input_ids=torch.tensor(batch["input_ids"]).to("cuda:0"),
                        attention_mask=torch.tensor(batch["attention_mask"]).to("cuda:0"),
                        labels=torch.tensor(batch["labels"]).to("cuda:0"))
            (out.loss / accum).backward()
            running += out.loss.item()
            if (bi + 1) % accum == 0:
                torch.nn.utils.clip_grad_norm_(
                    [p for p in model.parameters() if p.requires_grad], 1.0)
                opt.step()
                sched.step()
                opt.zero_grad()
                step += 1
                rows_consumed += bs * accum
                if ckpt_dir and step % ckpt_every == 0:
                    save_ckpt(step, rows_consumed)
                    print(f"  [ckpt] step {step} saved", flush=True)
                if step % log_every == 0:
                    print(f"  step {step}: loss {running / (accum * log_every):.4f}",
                          flush=True)
                    running = 0.0
    if ckpt_dir:
        save_ckpt(step, rows_consumed)
    return model, stats


def run_release(cfg: ArmConfig, config_path: str) -> int:
    import torch
    from transformers import AutoTokenizer
    from route2_training.evaluate_dev import evaluate_dev

    out = Path(cfg.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    tok = AutoTokenizer.from_pretrained(cfg.base_model)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    ledger = {"arm": cfg.name, "base_model": cfg.base_model,
              "config_path": config_path, "config_sha": sha256_file(config_path),
              "sha": {"qgis_train": sha256_file(cfg.qgis_train),
                      "qgis_dev": sha256_file(cfg.qgis_dev),
                      "qgis_test": sha256_file(cfg.qgis_test)}}

    # ── stage 1: GEE (A1 dapt / B1 semantic), C0 skips ──
    current_base = cfg.base_model
    if cfg.gee_stage != "none":
        model = load_base_4bit(cfg.base_model)
        model = build_lora(model)
        if cfg.gee_stage == "dapt":
            ds = GeeDaptCorpus(cfg.gee_data, split="train")
            col = CausalLMCollator(tok, cfg.max_len)
            model, gstats = train_stage(model, ds, col, cfg.gee_epochs, cfg.max_lr,
                                         cfg.batch_size, cfg.grad_accum, masked=False,
                                         ckpt_dir=out / "stage1_ckpt", ckpt_every=150)
            stage_tag = "gee_dapt"
        else:
            ds = GeeSemanticDataset(cfg.gee_data, split="train")
            col = QgisGraphCollator(tok, cfg.max_len, prompt_suffix=B1_SUFFIX)
            model, gstats = train_stage(model, ds, col, cfg.gee_epochs, cfg.max_lr,
                                         cfg.batch_size, cfg.grad_accum, masked=True,
                                         ckpt_dir=out / "stage1_ckpt", ckpt_every=150)
            stage_tag = "gee_semantic"
        adapter = out / f"{stage_tag}_adapter"
        model.save_pretrained(str(adapter))
        merged_dir = out / f"{stage_tag}_merged"
        merged_dir.mkdir(parents=True, exist_ok=True)
        merged = model.merge_and_unload()
        merged.save_pretrained(str(merged_dir), safe_serialization=True)
        tok.save_pretrained(str(merged_dir))
        del model, merged
        torch.cuda.empty_cache()
        current_base = str(merged_dir)
        ledger["gee_stage"] = {"kind": cfg.gee_stage, "adapter": str(adapter),
                               "merged": current_base,
                               "data_sha": sha256_file(cfg.gee_data),
                               "actual": gstats}

    # ── stage 2: QGIS SFT (identical for all arms) ──
    model = load_base_4bit(current_base)
    model = build_lora(model)
    ds = QgisGraphDataset(cfg.qgis_train)
    col = QgisGraphCollator(tok, cfg.max_len)
    best_f1, best_dir = -1.0, None
    history, qstats = [], {"n_examples": 0, "n_tokens": 0,
                           "n_target_truncated": 0, "n_prompt_truncated": 0}
    for ep in range(cfg.qgis_epochs):
        model, estats = train_stage(model, ds, col, epochs=1, lr=cfg.max_lr,
                                    bs=cfg.batch_size, accum=cfg.grad_accum, masked=True)
        for k in qstats: qstats[k] += estats[k]
        ckpt = out / f"qgis_sft_ep{ep + 1}"
        model.save_pretrained(str(ckpt))
        # release cached blocks so the eval subprocess can co-load a second
        # 4-bit model next to the live training tensors
        import gc
        gc.collect()
        torch.cuda.empty_cache()
        import subprocess, sys as _sys
        r = subprocess.run(
            [_sys.executable, str(Path(__file__).parent / "evaluate_dev.py"),
             "--base-model", current_base, "--adapter", str(ckpt),
             "--dev", cfg.qgis_dev, "--out", str(out / f"dev_ep{ep + 1}.json"),
             "--batch-size", "2"],
            capture_output=True, text=True)
        if r.returncode != 0:
            print("[dev] eval subprocess failed: " + r.stderr[-2000:], flush=True)
            m = {"operator_set_f1": -1.0, "exact_graph_em": 0, "link_f1": 0,
                 "parse_failure_rate": 1.0, "n": 0}
        else:
            m = json.loads((out / f"dev_ep{ep + 1}.json").read_text(encoding="utf-8"))
        history.append({"epoch": ep + 1, **m})
        if m["operator_set_f1"] > best_f1:
            best_f1 = m["operator_set_f1"]
            best_dir = ckpt
        print(f"[epoch {ep + 1}] dev opF1={m['operator_set_f1']:.4f} "
              f"(best {best_f1:.4f})", flush=True)
    ledger["qgis_sft"] = {"best_epoch_dir": str(best_dir),
                          "best_operator_set_f1": best_f1,
                          "history": history, "actual": qstats}
    (out / "run_ledger.json").write_text(
        json.dumps(ledger, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"done. best checkpoint: {best_dir} (dev opF1 {best_f1:.4f})")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--release", action="store_true",
                    help="actually train (owner-gated after preflight review)")
    args = ap.parse_args()
    cfg = load_config(args.config)

    if args.dry_run or not args.release:
        from transformers import AutoTokenizer
        tok = AutoTokenizer.from_pretrained(cfg.base_model)
        report = preflight(cfg, tok)
        outp = Path(cfg.output_dir) / "preflight_report.json"
        outp.parent.mkdir(parents=True, exist_ok=True)
        outp.write_text(json.dumps(report, indent=2, ensure_ascii=False),
                        encoding="utf-8")
        print(json.dumps(report, indent=2, ensure_ascii=False))
        print(f"\nwrote {outp}")
        print("DRY-RUN ONLY — GPU not started. Awaiting owner release.")
        return 0
    return run_release(cfg, args.config)


if __name__ == "__main__":
    raise SystemExit(main())
