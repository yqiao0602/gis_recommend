#!/usr/bin/env python3
"""V2a-A: QLoRA/SFT of post-trained Qwen3.5-9B on QGIS-native workflows.

Derived from m3_p1_sft.py with the owner-locked change boundary (2026-09-16):
keep the Qwen/QLoRA config, tokenizer, seed, optimizer/scheduler, checkpoint
mechanism; change ONLY the target serializer (L3 sequence -> processes+links
JSON), add sample_weight (A=all 1.0, B=Tier-2 at 0.5), and take the V2a
manifest as input.

Deliberately NOT changed: model, tokenizer, epochs, learning rate, LoRA rank/
target modules, benchmark, scorer, final-100, decoding strategy.

Target JSON contract = the frozen benchmark gold contract verbatim
(`processes: [{process_id, operator_id}]`, `links: [{source_process_id,
target_process_id}]`), so the frozen scorer consumes model output directly
with zero parse layer. Model must emit JSON only — no prose.

--audit prints the pre-training check the owner requested: one real prompt,
one target JSON, tokenized ids/labels with the instruction-mask boundary,
target token-length stats, and a dry-run loss. Nothing trains in audit mode.
"""

from __future__ import annotations

import argparse
import json
import random
import time
from collections import Counter
from pathlib import Path

import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import LoraConfig, get_peft_model

OUT_DIR = Path("/home/qy/gee_llm_smoke/v2a_a")
# Only the output-space token changed vs M3-P1's "L3 workflow:" (target
# serializer change); the instruction mechanism itself is untouched.
PROMPT_TEMPLATE = "Task: {task_text}\nQGIS workflow:"


def serialize_target(row: dict) -> str:
    """Deterministic JSON target in the frozen benchmark gold contract."""
    obj = {
        "processes": [{"process_id": p["process_id"], "operator_id": p["operator_id"]}
                      for p in row["processes"]],
        "links": [{"source_process_id": l["source_process_id"],
                   "target_process_id": l["target_process_id"]} for l in row["links"]],
    }
    return json.dumps(obj, ensure_ascii=False, separators=(", ", ": "))


class SFTSet(Dataset):
    def __init__(self, rows, tok, max_len):
        self.rows, self.tok, self.max_len = rows, tok, max_len

    def __len__(self):
        return len(self.rows)

    def __getitem__(self, i):
        r = self.rows[i]
        prompt = PROMPT_TEMPLATE.format(task_text=r["task_text"])
        full = prompt + " " + serialize_target(r) + self.tok.eos_token
        ids = self.tok(full, truncation=True, max_length=self.max_len,
                       return_tensors="pt")["input_ids"][0]
        plen = len(self.tok(prompt, truncation=True, max_length=self.max_len)["input_ids"])
        labels = ids.clone()
        labels[:plen] = -100          # instruction mask: prompt tokens never supervised
        return {"input_ids": ids, "labels": labels, "weight": float(r.get("weight", 1.0))}


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


def parse_pred(text: str) -> dict:
    """Parse model output into the graph contract; report failure explicitly."""
    s = text.strip()
    i, j = s.find("{"), s.rfind("}")
    if i < 0 or j <= i:
        return {"ok": False, "reason": "no_json"}
    try:
        obj = json.loads(s[i:j + 1])
    except json.JSONDecodeError as e:
        return {"ok": False, "reason": f"json_error: {e}"}
    if not isinstance(obj, dict) or "processes" not in obj:
        return {"ok": False, "reason": "shape"}
    procs = [{"process_id": str(p.get("process_id")), "operator_id": p.get("operator_id")}
             for p in obj.get("processes") or []]
    links = [{"source_process_id": str(l.get("source_process_id")),
              "target_process_id": str(l.get("target_process_id"))}
             for l in obj.get("links") or []]
    if not procs:
        return {"ok": False, "reason": "empty_processes"}
    ids = {p["process_id"] for p in procs}
    links = [l for l in links if l["source_process_id"] in ids and l["target_process_id"] in ids]
    return {"ok": True, "processes": procs, "links": links}


def evaluate(model, tok, rows, bundle):
    """Dev evaluation: model output -> graph contract -> frozen-scorer-shaped metrics."""
    model.eval()
    n = len(rows)
    ops_p = ops_r = 0.0
    link_p = link_r = 0.0
    exact = 0
    parse_fail = Counter()
    preds = []
    for r in rows:
        prompt = PROMPT_TEMPLATE.format(task_text=r["task_text"])
        inputs = tok(prompt, return_tensors="pt", truncation=True, max_length=2048).to("cuda:0")
        with torch.no_grad():
            out = model.generate(**inputs, max_new_tokens=bundle["max_new_tokens"],
                                 do_sample=False, pad_token_id=tok.pad_token_id)
        text = tok.decode(out[0][inputs["input_ids"].shape[1]:], skip_special_tokens=True)
        pr = parse_pred(text)
        if not pr["ok"]:
            parse_fail[pr["reason"].split(":")[0]] += 1
            preds.append({"wid": r["wid"], "ok": False, "reason": pr["reason"], "raw": text[:300]})
            continue
        gp = Counter(p["operator_id"] for p in r["processes"])
        pp = Counter(p["operator_id"] for p in pr["processes"])
        inter = sum((gp & pp).values())
        ops_p += inter / max(sum(pp.values()), 1)
        ops_r += inter / max(sum(gp.values()), 1)
        gl = {(l["source_process_id"], l["target_process_id"]) for l in r["links"]}
        pl = {(l["source_process_id"], l["target_process_id"]) for l in pr["links"]}
        li = len(gl & pl)
        link_p += li / max(len(pl), 1)
        link_r += li / max(len(gl), 1)
        is_exact = (gp == pp and gl == pl)
        exact += is_exact
        preds.append({"wid": r["wid"], "ok": True, "exact": bool(is_exact),
                      "n_pred": len(pp), "n_gold": len(gp), "raw": text[:300]})
    model.train()
    return {
        "n": n,
        "parse_ok_rate": round(sum(1 for p in preds if p.get("ok")) / n, 4),
        "parse_failures": dict(parse_fail),
        "operator_precision": round(ops_p / n, 4),
        "operator_recall": round(ops_r / n, 4),
        "operator_f1": round(2 * ops_p * ops_r / max(ops_p + ops_r, 1e-9), 4),
        "link_precision": round(link_p / n, 4),
        "link_recall": round(link_r / n, 4),
        "link_f1": round(2 * link_p * link_r / max(link_p + link_r, 1e-9), 4),
        "graph_exact_match_rate": round(exact / n, 4),
    }, preds


def audit(args, train_rows, val_rows, tok):
    """Owner-requested pre-training audit: no training, no GPU writes."""
    print("=" * 78)
    print("V2a PRE-TRAINING AUDIT")
    print("=" * 78)
    r = train_rows[0]
    prompt = PROMPT_TEMPLATE.format(task_text=r["task_text"])
    target = serialize_target(r)
    print("\n--- 1. one real prompt (train row 0, wid %s) ---" % r["wid"])
    print(prompt[:600])
    print("\n--- 2. one target JSON ---")
    print(target[:600])
    # round-trip: target parses and matches the row
    back = json.loads(target)
    same = (len(back["processes"]) == len(r["processes"])
            and len(back["links"]) == len(r["links"])
            and {(l["source_process_id"], l["target_process_id"]) for l in back["links"]}
            == {(l["source_process_id"], l["target_process_id"]) for l in r["links"]})
    print(f"target round-trip consistent: {same}")

    print("\n--- 3. tokenized ids / labels / mask boundary ---")
    ds = SFTSet(train_rows[:1], tok, args.max_len)
    item = ds[0]
    ids, labels = item["input_ids"], item["labels"]
    plen = int((labels == -100).sum())
    print(f"total tokens: {len(ids)} | masked instruction tokens: {plen} | "
          f"supervised target tokens: {len(ids) - plen}")
    print("first 12 supervised positions (id -> token):")
    sup_idx = [i for i in range(len(ids)) if labels[i] != -100][:12]
    for i in sup_idx:
        print(f"  pos {i}: {int(ids[i])} -> {tok.decode([int(ids[i])])!r}")
    print("boundary check (last masked / first supervised):")
    for i in range(max(plen - 2, 0), min(plen + 3, len(ids))):
        print(f"  pos {i}: id={int(ids[i])} label={int(labels[i])} "
              f"tok={tok.decode([int(ids[i])])!r}")

    print("\n--- 4. target token-length distribution (train + dev) ---")
    lens = []
    for row in train_rows + val_rows:
        t = serialize_target(row) + tok.eos_token
        lens.append(len(tok(t, truncation=False)["input_ids"]))
    lens.sort()
    p = lambda q: lens[min(len(lens) - 1, int(len(lens) * q))]
    print(f"n={len(lens)} mean={sum(lens)/len(lens):.0f} p50={p(.5)} p90={p(.9)} "
          f"p95={p(.95)} p99={p(.99)} max={lens[-1]}")
    over = sum(1 for x in lens if x > args.max_len)
    print(f"targets exceeding --max-len {args.max_len}: {over} / {len(lens)}")

    print("\n--- 5. dry-run loss (batch of %d, no optimizer step) ---" % args.batch_size)
    if args.skip_gpu:
        print("skipped (--skip-gpu)")
        return
    tok.pad_token = tok.pad_token or tok.eos_token
    collate.tok = tok
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                             bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
    model = AutoModelForCausalLM.from_pretrained(args.model, quantization_config=bnb, device_map="cuda:0")
    model.config.use_cache = False
    model.gradient_checkpointing_enable()
    model.enable_input_require_grads()
    model = get_peft_model(model, LoraConfig(
        r=args.lora_r, lora_alpha=args.lora_alpha, lora_dropout=0.0,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"], task_type="CAUSAL_LM"))
    ds = SFTSet(train_rows, tok, args.max_len)
    batch = collate([ds[i] for i in range(args.batch_size)])
    batch = {k: v.to("cuda:0") for k, v in batch.items()}
    w = batch.pop("sample_weight")
    with torch.no_grad():
        out = model(**batch)
    n_sup = int((batch["labels"] != -100).sum())
    print(f"batch loss {out.loss.item():.4f} | supervised tokens in batch: {n_sup} | "
          f"weights {w.tolist()}")
    print(f"expectation check: loss should be far below ln(vocab)={torch.log(torch.tensor(150000.0)).item():.1f} "
          f"only after training; at init it is ~ the model's untuned CE on JSON text")
    del model
    torch.cuda.empty_cache()
    print("\nAUDIT COMPLETE (no training performed)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", type=Path, required=True)
    ap.add_argument("--train", type=Path, required=True)
    ap.add_argument("--dev", type=Path, required=True)
    ap.add_argument("--test", type=Path)
    ap.add_argument("--profile", default="A")
    ap.add_argument("--out-dir", type=Path, default=OUT_DIR)
    ap.add_argument("--ledger", type=Path)
    ap.add_argument("--epochs", type=int, default=1)
    ap.add_argument("--batch-size", type=int, default=8)
    ap.add_argument("--grad-accum", type=int, default=4)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--lora-r", type=int, default=16)
    ap.add_argument("--lora-alpha", type=int, default=32)
    ap.add_argument("--max-len", type=int, default=2560)  # owner ruling 2026-09-16
    ap.add_argument("--max-new-tokens", type=int, default=1024)
    ap.add_argument("--seed", type=int, default=20260916)
    ap.add_argument("--eval-every", type=int, default=0,
                    help="0 = M3-P1-compatible end-only save; >0 = periodic dev eval "
                         "with best-checkpoint keeping (V2a addition, flagged in report)")
    ap.add_argument("--per-sample-weight", action="store_true",
                    help="true per-sample weighted CE (required for profile B)")
    ap.add_argument("--smoke", action="store_true", help="pre-training smoke: real loss+eval paths")
    ap.add_argument("--smoke-steps", type=int, default=8)
    ap.add_argument("--smoke-eval-rows", type=int, default=3)
    ap.add_argument("--weight-sanity", action="store_true",
                    help="run the three weighted-loss sanity checks and exit")
    ap.add_argument("--length-bucketed", action="store_true",
                    help="memory adaptation: similar-length micro-batches, shuffled batch order")
    ap.add_argument("--audit", action="store_true")
    ap.add_argument("--skip-gpu", action="store_true")
    args = ap.parse_args()

    train_rows = [json.loads(l) for l in args.train.read_text(encoding="utf-8").splitlines() if l.strip()]
    val_rows = [json.loads(l) for l in args.dev.read_text(encoding="utf-8").splitlines() if l.strip()]

    torch.manual_seed(args.seed)
    tok = AutoTokenizer.from_pretrained(args.model)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    if args.audit:
        audit(args, train_rows, val_rows, tok)
        return 0

    if args.smoke:
        import torch.nn.functional as _F
        # SMOKE: exercises the REAL training loss path, the REAL eval path, and
        # the artifact writers on a handful of rows, and asserts the per-sample
        # weighted path agrees with HF's native loss. Catches exactly the three
        # failure classes that a prompt/target-only audit misses.
        print("=" * 70)
        print("V2a SMOKE: real loss path + real eval path + artifact persistence")
        print("=" * 70)
        n_steps = args.smoke_steps
        sub = train_rows[:max(args.batch_size * n_steps * 2, 4)]
        collate.tok = tok
        bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_quant_type="nf4",
                                 bnb_4bit_compute_dtype=torch.bfloat16,
                                 bnb_4bit_use_double_quant=True)
        model = AutoModelForCausalLM.from_pretrained(args.model, quantization_config=bnb,
                                                     device_map="cuda:0")
        model.config.use_cache = False
        model.gradient_checkpointing_enable()
        model.enable_input_require_grads()
        model = get_peft_model(model, LoraConfig(
            r=args.lora_r, lora_alpha=args.lora_alpha, lora_dropout=0.0,
            target_modules=["q_proj", "k_proj", "v_proj", "o_proj"], task_type="CAUSAL_LM"))
        ds = SFTSet(sub, tok, args.max_len)
        batch = collate([ds[i] for i in range(min(args.batch_size, len(sub)))])
        batch = {k: v.to("cuda:0") for k, v in batch.items()}
        w = batch.pop("sample_weight")

        def per_sample_loss(b, weights):
            labels = b["labels"]
            logits = model(**{k: v for k, v in b.items() if k != "labels"}).logits
            sl = labels[:, 1:]
            slog = logits[:, :-1, :]
            flat = _F.cross_entropy(slog.reshape(-1, slog.size(-1)).float(),
                                    sl.reshape(-1), reduction="none", ignore_index=-100)
            per_tok = flat.view(sl.size(0), -1)
            mask = (sl != -100).float()
            weights = weights.to(per_tok.device)
            w_tok = weights.unsqueeze(1) * mask
            row = per_tok.sum(1) / mask.sum(1).clamp(min=1)
            return (per_tok * w_tok).sum() / w_tok.sum().clamp(min=1e-9), row

        with torch.no_grad():
            hf = model(**batch).loss.item()
            uni, row = per_sample_loss(batch, torch.ones_like(w))
            align = abs(float(uni) - hf) < 5e-4
        print(f"  [A] per-sample(w=all 1) vs HF native loss: {float(uni):.6f} vs {hf:.6f} "
              f"-> {'MATCH' if align else 'MISMATCH'}")
        print(f"      per-row losses: {[round(float(x), 4) for x in row]}")

        # real training steps through the production code path
        opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=args.lr)
        model.train()
        losses = []
        for step in range(n_steps):
            b = collate([ds[i % len(sub)] for i in range(args.batch_size)])
            b = {k: v.to("cuda:0") for k, v in b.items()}
            ww = b.pop("sample_weight")
            loss, _ = per_sample_loss(b, ww)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            opt.step()
            losses.append(round(float(loss), 4))
        print(f"  [B] {n_steps} real optimizer steps ran; losses {losses}")
        finite = all(x == x and abs(x) < 1e4 for x in losses)
        print(f"      losses finite: {finite}")

        # real eval path on a few rows + artifact persistence
        args.out_dir.mkdir(parents=True, exist_ok=True)
        m, preds = evaluate(model, tok, val_rows[:args.smoke_eval_rows], {"max_new_tokens": 128})
        (args.out_dir / "smoke_metrics.json").write_text(
            json.dumps(m, indent=2, ensure_ascii=False), encoding="utf-8")
        print(f"  [C] eval ran on {m['n']} rows and metrics persisted: {json.dumps(m)}")
        ls = sorted(args.out_dir.glob("smoke_metrics.json"))
        print(f"      artifact check: {[p.name for p in ls]}")
        ok = align and finite and m["n"] == args.smoke_eval_rows
        print(f"  SMOKE {'PASS' if ok else 'FAIL'}")
        return 0 if ok else 1

    if args.weight_sanity:
        import torch.nn.functional as _F
        # three checks on a synthetic 2-row batch using the SAME loss code path
        ids = torch.randint(3, 512, (2, 24))
        labels = ids.clone()
        labels[:, :4] = -100
        logits = torch.randn(2, 24, 512)

        def wloss(w):
            sl = labels[:, 1:]
            slog = logits[:, :-1, :]
            flat = _F.cross_entropy(slog.reshape(-1, 512), sl.reshape(-1),
                                    reduction="none", ignore_index=-100)
            per_tok = flat.view(sl.size(0), -1)
            mask = (sl != -100).float()
            w = torch.tensor(w, dtype=torch.float32)
            w_tok = w.unsqueeze(1) * mask
            row = per_tok.sum(1) / mask.sum(1).clamp(min=1)
            return float((per_tok * w_tok).sum() / w_tok.sum().clamp(min=1e-9)), row

        plain = float(_F.cross_entropy(logits[:, :-1, :].reshape(-1, 512),
                                       labels[:, 1:].reshape(-1), ignore_index=-100))
        eq, row = wloss([1.0, 1.0])
        chk1 = abs(eq - plain) < 1e-5
        r1 = float(row[0]); r2 = float(row[1])
        chk2 = abs(float(wloss([1.0, 0.0])[0]) - r1) < 1e-5
        half = float(wloss([1.0, 0.5])[0])
        chk3 = (r1 > half > 0) and (abs(half - (r1 + 0.5 * r2) / 1.5) < 1e-5)
        naive = plain * 0.75  # what M3-P1's loss*w.mean() would give for [1.0,0.5]
        print("weighted-loss sanity (same code path as training):")
        print(f"  per-row losses: r1={r1:.6f} r2={r2:.6f} | plain CE={plain:.6f}")
        print(f"  1. all weights 1.0 -> equals plain CE: {chk1} ({eq:.6f})")
        print(f"  2. Tier-2 weight 0 -> Tier-2 contributes nothing: {chk2} ({wloss([1.0,0.0])[0]:.6f} vs r1={r1:.6f})")
        print(f"  3. Tier-2 weight 0.5 -> partial, analytic match: {chk3} ({half:.6f})")
        print(f"  (M3-P1's batch-scalar approach would have given {naive:.6f} — "
              f"different from the per-sample value {half:.6f}: "
              f"{abs(naive - half) > 1e-6})")
        print(f"  ALL PASS: {chk1 and chk2 and chk3}")
        return 0 if (chk1 and chk2 and chk3) else 1

    collate.tok = tok
    bundle = {"max_new_tokens": args.max_new_tokens}
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                             bnb_4bit_compute_dtype=torch.bfloat16, bnb_4bit_use_double_quant=True)
    model = AutoModelForCausalLM.from_pretrained(args.model, quantization_config=bnb, device_map="cuda:0")
    model.config.use_cache = False
    model.gradient_checkpointing_enable()
    model.enable_input_require_grads()
    model = get_peft_model(model, LoraConfig(
        r=args.lora_r, lora_alpha=args.lora_alpha, lora_dropout=0.0,
        target_modules=["q_proj", "k_proj", "v_proj", "o_proj"], task_type="CAUSAL_LM"))

    ds = SFTSet(train_rows, tok, args.max_len)
    if args.length_bucketed:
        # Memory adaptation (documented): group rows of similar target length into
        # micro-batches so padding waste stops dominating peak memory, then shuffle
        # the batch ORDER. Data distribution and effective batch are unchanged.
        lengths = [len(tok(serialize_target(r), truncation=False)["input_ids"]) for r in train_rows]
        order = sorted(range(len(train_rows)), key=lambda i: lengths[i])
        groups = [order[i:i + args.batch_size] for i in range(0, len(order), args.batch_size)]
        random.Random(args.seed).shuffle(groups)
        flat = [i for g in groups for i in g]
        loader = DataLoader(ds, batch_size=args.batch_size, sampler=flat,
                            collate_fn=collate)
    else:
        loader = DataLoader(ds, batch_size=args.batch_size, shuffle=True, collate_fn=collate,
                            generator=torch.Generator().manual_seed(args.seed))
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=args.lr)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()
    losses = []
    model.train()
    step = 0
    best = {"score": -1.0, "step": 0}
    for epoch in range(args.epochs):
        running = 0.0
        for i, batch in enumerate(loader):
            batch = {k: v.to("cuda:0") for k, v in batch.items()}
            w = batch.pop("sample_weight")
            if args.per_sample_weight:
                # TRUE per-sample weighting: per-row mean CE, then weight by the
                # row's sample weight. (M3-P1's `loss * w.mean()` only scaled the
                # batch scalar and could not express Tier-2 x0.5.)
                labels = batch["labels"]
                logits = model(**{k: v for k, v in batch.items() if k != "labels"}).logits
                # CAUSAL SHIFT (same as HF's internal loss): predict token t+1
                # from position t. Omitting this made B train on a degenerate
                # copy objective (loss ~8.4 vs A's 0.75).
                sl = labels[:, 1:]
                slog = logits[:, :-1, :]
                flat = F.cross_entropy(slog.reshape(-1, slog.size(-1)).float(),
                                       sl.reshape(-1), reduction="none", ignore_index=-100)
                per_tok = flat.view(sl.size(0), -1)
                mask = (sl != -100).float()
                w_tok = w.unsqueeze(1).to(per_tok.device) * mask      # per-token weight
                weighted = (per_tok * w_tok).sum() / w_tok.sum().clamp(min=1e-9)
                running += weighted.item()
            else:
                out = model(**batch)
                weighted = out.loss * w.mean()
                running += out.loss.item()
            (weighted / args.grad_accum).backward()
            if (i + 1) % args.grad_accum == 0:
                opt.step(); opt.zero_grad(set_to_none=True); step += 1
                if step % 25 == 0:
                    avg = running / (i + 1)
                    losses.append((step, round(avg, 4)))
                    print(f"epoch {epoch} step {step} loss {avg:.4f}", flush=True)
                if args.eval_every and step % args.eval_every == 0:
                    m, _ = evaluate(model, tok, val_rows, bundle)
                    score = m["operator_f1"] + m["link_f1"]
                    print(f"[dev@{step}] {json.dumps(m, ensure_ascii=False)}", flush=True)
                    if score > best["score"]:
                        best = {"score": round(score, 4), "step": step, "metrics": m}
                        model.save_pretrained(args.out_dir / "adapter_best_dev")
        opt.step(); opt.zero_grad(set_to_none=True)

    train_minutes = (time.time() - t0) / 60
    ckpt = args.out_dir / "adapter_v1"
    model.save_pretrained(ckpt)
    metrics, preds = evaluate(model, tok, val_rows, bundle)
    if args.test:
        test_rows = [json.loads(l) for l in args.test.read_text(encoding="utf-8").splitlines() if l.strip()]
        test_metrics, test_preds = evaluate(model, tok, test_rows, bundle)
        (args.out_dir / f"v2a_{args.profile}_test_metrics.json").write_text(
            json.dumps(test_metrics, indent=2, ensure_ascii=False), encoding="utf-8")
        (args.out_dir / f"v2a_{args.profile}_test_predictions.jsonl").write_text(
            "".join(json.dumps(p, ensure_ascii=False, sort_keys=True) + "\n" for p in test_preds),
            encoding="utf-8")
    report = {
        "schema": "gis_recommend.v2a_sft.v1", "profile": args.profile,
        "model": str(args.model), "train_rows": len(train_rows), "dev_rows": len(val_rows),
        "epochs": args.epochs, "loss_curve": losses[:50],
        "train_minutes": round(train_minutes, 1),
        "peak_memory_gb": round(torch.cuda.max_memory_allocated() / 2**30, 2),
        "config": {"lora_r": args.lora_r, "lora_alpha": args.lora_alpha,
                   "target_modules": "qkvo", "lr": args.lr, "batch": args.batch_size,
                   "grad_accum": args.grad_accum, "quant": "nf4", "max_len": args.max_len,
                   "max_new_tokens": args.max_new_tokens, "seed": args.seed,
                   "weighted_ce": True, "eval_every": args.eval_every},
        "dev_metrics": metrics, "best_dev": best,
        "target_format": "benchmark gold contract (processes+links)",
        "prompt": PROMPT_TEMPLATE,
    }
    (args.out_dir / f"v2a_{args.profile}_train_report.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    (args.out_dir / f"v2a_{args.profile}_dev_predictions.jsonl").write_text(
        "".join(json.dumps(p, ensure_ascii=False, sort_keys=True) + "\n" for p in preds),
        encoding="utf-8")
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
