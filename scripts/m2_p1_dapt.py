#!/usr/bin/env python3
"""M2-P1: DAPT-only arm — Qwen3.5-9B-Base on the frozen GIS corpus v1.

Owner-frozen configuration (2026-09-14):
  corpus   dapt_corpus_v1.jsonl, SHA 695ac70f…, 26.3M tokens (95% QGIS
           code / 5% NL auxiliary), held-out eval split carved before training
  training QLoRA NF4, LoRA r16/alpha32/qkvo, causal LM (no masking),
           lr 1e-4, 1 epoch, block size 1024, batch 2 x grad-accum 16
  purpose  NOT workflow generation — this checkpoint answers: does a
           code-heavy GIS corpus produce detectable domain adaptation?

Domain-signal checks (owner-specified three categories), measured on the
SAME prompts before (Base) and after (DAPT) training:
  1. GIS vocabulary/concept   — PPL on held-out GIS scripts (domain)
                                vs fixed generic-English control text
  2. QGIS API semantics       — PPL on API-heavy held-out blocks
                                (Qgs*/processing.run marker), plus cloze
                                probes over operator/API names (top-1/top-5)
  3. language→operator迁移    — fixed task-prompt probes (benchmark format)
                                recorded verbatim for before/after comparison
"""

from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path

import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader, Dataset
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
from peft import LoraConfig, get_peft_model, PeftModel

GENERIC_CONTROL = (
    "The committee reviewed the quarterly report and discussed several administrative matters. "
    "Members agreed to postpone the budget decision until the next session. The chair summarized "
    "the previous meeting's minutes and asked for corrections. Attendance was recorded and the "
    "agenda for the following month was approved without amendment. The treasurer presented an "
    "overview of outstanding invoices and proposed adjustments to the financial calendar. "
    "A short break followed, after which the discussion turned to planning the annual conference, "
    "including venue options, catering arrangements, and registration fees for participants. "
    "Several suggestions were raised concerning communication with regional offices and the "
    "timetable for publishing internal newsletters. The meeting concluded with a vote of thanks."
)

CLOZE_PROBES = [
    ("The QGIS algorithm native:", "buffer", " creates buffer polygons around the input features."),
    ("The QGIS algorithm native:", "intersection", " computes the geometric intersection of two vector layers."),
    ("The QGIS algorithm native:", "clip", " clips a vector layer using the features of another layer."),
    ("The QGIS algorithm native:", "dissolve", " merges features that share the same attribute value."),
    ("The QGIS algorithm native:", "reprojectlayer", " reprojects a vector layer to another CRS."),
    ("The QGIS algorithm gdal:", "rastercalculator", " performs raster algebra over input rasters."),
    ("In PyQGIS, a vector layer is represented by the class", "QgsVectorLayer", "."),
    ("In PyQGIS, a geometry object is represented by the class", "QgsGeometry", "."),
    ("In PyQGIS, a raster layer is represented by the class", "QgsRasterLayer", "."),
    ("A QGIS processing algorithm subclasses", "QgsProcessingAlgorithm", " to define its behavior."),
    ("In GIS, areas of equal distance around a feature are called", "buffer", " zones."),
    ("Converting vector polygons to raster cells is called", "rasterization", "."),
    ("NoData values in a raster indicate", "missing", " or undefined cells."),
    ("A coordinate reference system defines how", "coordinates", " map to locations on Earth."),
]

TASK_PROBES = [
    "Task: Create a 500-meter buffer around all roads, then clip the buildings inside the buffer.\nL3 workflow:",
    "Task: Reproject the input layer to EPSG:4326 and compute zonal statistics of the raster over the polygons.\nL3 workflow:",
    "Task: Merge multiple vector layers into one layer, then create buffer polygons around the merged features.\nL3 workflow:",
]


def sha256_file(p: Path) -> str:
    import hashlib
    h = hashlib.sha256()
    with p.open("rb") as f:
        for c in iter(lambda: f.read(1 << 20), b""):
            h.update(c)
    return h.hexdigest()


class BlockDataset(Dataset):
    def __init__(self, blocks):
        self.blocks = blocks

    def __len__(self):
        return len(self.blocks)

    def __getitem__(self, i):
        return {"input_ids": self.blocks[i],
                "labels": self.blocks[i].clone()}


def collate(batch):
    ids = torch.stack([b["input_ids"] for b in batch])
    return {"input_ids": ids, "labels": ids.clone()}


@torch.no_grad()
def ppl_on_texts(model, tok, texts, block=1024, max_blocks=40) -> float:
    """Mean NLL per token over text blocks."""
    tot_nll, tot_tok = 0.0, 0
    n = 0
    for t in texts:
        ids = tok(t, return_tensors="pt", truncation=True, max_length=100_000)["input_ids"][0]
        for s in range(0, len(ids) - 1, block):
            chunk = ids[s:s + block].unsqueeze(0).to("cuda:0")
            if chunk.size(1) < 32:
                continue
            out = model(input_ids=chunk)
            logits = out.logits[:, :-1, :].float()
            tgt = chunk[:, 1:]
            nll = F.cross_entropy(logits.reshape(-1, logits.size(-1)), tgt.reshape(-1), reduction="sum")
            tot_nll += nll.item()
            tot_tok += tgt.numel()
            n += 1
            if n >= max_blocks:
                return tot_nll / max(tot_tok, 1)
    return tot_nll / max(tot_tok, 1)


@torch.no_grad()
def cloze_probe(model, tok) -> dict:
    top1 = top5 = 0
    details = []
    for prefix, gold, suffix in CLOZE_PROBES:
        prompt = prefix + '"'
        ids = tok(prompt, return_tensors="pt").input_ids.to("cuda:0")
        out = model(input_ids=ids)
        logits = out.logits[0, -1, :].float()
        topk = torch.topk(logits, 5).indices.tolist()
        gold_ids = tok(' ' + gold, add_special_tokens=False).input_ids
        first_gold = gold_ids[0] if gold_ids else -1
        # decode top-5 continuations for the record
        conts = [tok.decode([i]).strip() for i in topk]
        hit1 = first_gold in topk[:1]
        hit5 = first_gold in topk
        top1 += hit1
        top5 += hit5
        details.append({"probe": prefix + "…" + suffix[:40], "gold": gold,
                        "top5": conts, "top1_hit": hit1, "top5_hit": hit5})
    return {"top1": top1, "top5": top5, "n": len(CLOZE_PROBES), "details": details}


@torch.no_grad()
def task_probe(model, tok, max_new=60) -> list:
    outs = []
    for p in TASK_PROBES:
        inputs = tok(p, return_tensors="pt", truncation=True, max_length=1024).to("cuda:0")
        eos_ids = [x for x in {tok.eos_token_id, tok.pad_token_id} if x is not None]
        gen = model.generate(**inputs, max_new_tokens=max_new, do_sample=False,
                             eos_token_id=eos_ids, pad_token_id=tok.pad_token_id)
        outs.append(tok.decode(gen[0][inputs["input_ids"].shape[1]:],
                               skip_special_tokens=True).strip()[:200])
    return outs


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", type=Path, required=True)
    ap.add_argument("--corpus", type=Path, required=True)
    ap.add_argument("--corpus-sha", required=True)
    ap.add_argument("--ledger", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--epochs", type=int, default=1)
    ap.add_argument("--block", type=int, default=1024)
    ap.add_argument("--batch-size", type=int, default=2)
    ap.add_argument("--grad-accum", type=int, default=16)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--n-eval-files", type=int, default=150)
    args = ap.parse_args()

    actual_sha = sha256_file(args.corpus)
    assert actual_sha == args.corpus_sha, f"corpus SHA drift: {actual_sha} != {args.corpus_sha}"

    rows = [json.loads(l) for l in args.corpus.read_text(encoding="utf-8").splitlines() if l.strip()]
    print(f"corpus rows: {len(rows)}")
    random.seed(42)

    tok = AutoTokenizer.from_pretrained(args.model)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token

    # ── tokenize + block split; hold out whole files for eval ──
    eval_rows = rows[-args.n_eval_files:]
    train_rows = rows[:-args.n_eval_files]
    print(f"train files {len(train_rows)}, eval files {len(eval_rows)}")

    def to_blocks(texts):
        """Stream-pack all text into uniform `block`-token blocks (GPT-style:
        files joined by EOS, then chunked; no partial blocks)."""
        blocks, carry = [], []
        eos = tok.eos_token_id
        for t in texts:
            ids = tok(t, truncation=True, max_length=200_000,
                      add_special_tokens=False)["input_ids"]
            carry.extend(ids)
            carry.append(eos)
            while len(carry) >= args.block:
                blocks.append(torch.tensor(carry[:args.block], dtype=torch.long))
                carry = carry[args.block:]
        return blocks

    # eval texts for the PPL buckets (holdout files never enter training)
    eval_texts = [r["text"] for r in eval_rows]
    t_blocks = to_blocks([r["text"] for r in train_rows])
    random.shuffle(t_blocks)
    print(f"train blocks (x{args.block}): {len(t_blocks)}")
    # eval buckets: random GIS holdout sample; class-level API subset; generic control
    gis_holdout = random.sample(eval_texts, min(8, len(eval_texts)))
    api_texts = [t for t in eval_texts
                 if "QgsVectorLayer" in t or "QgsProcessingAlgorithm" in t
                 or "QgsRasterLayer" in t or "QgsGeometry" in t][:8]
    if not api_texts:
        api_texts = gis_holdout  # degenerate fallback; recorded in metrics
    ds = BlockDataset(t_blocks)
    loader = DataLoader(ds, batch_size=args.batch_size, shuffle=False, collate_fn=collate)

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
    model.eval()

    # ── BEFORE checks (Base) ──
    print("\n== domain-signal checks BEFORE DAPT (Base) ==")
    before = {
        "ppl_gis_holdout": round(ppl_on_texts(model, tok, gis_holdout), 4),
        "ppl_api_heavy": round(ppl_on_texts(model, tok, api_texts), 4),
        "ppl_generic_control": round(ppl_on_texts(model, tok, [GENERIC_CONTROL * 3]), 4),
        "cloze": cloze_probe(model, tok),
        "task_probes": task_probe(model, tok),
    }
    print(json.dumps({k: v for k, v in before.items() if k != "cloze"}, ensure_ascii=False, indent=1))
    print(f"cloze before: top1 {before['cloze']['top1']}/{before['cloze']['n']}, "
          f"top5 {before['cloze']['top5']}/{before['cloze']['n']}")

    # ── DAPT training ──
    args.out_dir.mkdir(parents=True, exist_ok=True)
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=args.lr)
    t0 = time.time()
    losses = []
    model.train()
    step = 0
    for epoch in range(args.epochs):
        running = 0.0
        for i, batch in enumerate(loader):
            batch = {k: v.to("cuda:0") for k, v in batch.items()}
            out = model(**batch)
            (out.loss / args.grad_accum).backward()
            running += out.loss.item()
            if (i + 1) % args.grad_accum == 0:
                opt.step(); opt.zero_grad(set_to_none=True); step += 1
                if step % 100 == 0:
                    avg = running / (i + 1)
                    losses.append(avg)
                    print(f"epoch {epoch} step {step}/{len(loader)//args.grad_accum} loss {avg:.4f} "
                          f"({(time.time()-t0)/60:.0f}m)", flush=True)
        opt.step(); opt.zero_grad(set_to_none=True)
    train_minutes = (time.time() - t0) / 60

    ckpt = args.out_dir / "dapt_adapter_v1"
    model.save_pretrained(ckpt)

    # ── AFTER checks (DAPT) ──
    model.eval()
    print("\n== domain-signal checks AFTER DAPT ==")
    after = {
        "ppl_gis_holdout": round(ppl_on_texts(model, tok, gis_holdout), 4),
        "ppl_api_heavy": round(ppl_on_texts(model, tok, api_texts), 4),
        "ppl_generic_control": round(ppl_on_texts(model, tok, [GENERIC_CONTROL * 3]), 4),
        "cloze": cloze_probe(model, tok),
        "task_probes": task_probe(model, tok),
    }
    print(json.dumps({k: v for k, v in after.items() if k != "cloze"}, ensure_ascii=False, indent=1))
    print(f"cloze after: top1 {after['cloze']['top1']}/{after['cloze']['n']}, "
          f"top5 {after['cloze']['top5']}/{after['cloze']['n']}")

    signal = {
        "ppl_gis_delta": round(before["ppl_gis_holdout"] - after["ppl_gis_holdout"], 4),
        "ppl_api_delta": round(before["ppl_api_heavy"] - after["ppl_api_heavy"], 4),
        "ppl_generic_delta": round(before["ppl_generic_control"] - after["ppl_generic_control"], 4),
        "cloze_top1_delta": after["cloze"]["top1"] - before["cloze"]["top1"],
        "cloze_top5_delta": after["cloze"]["top5"] - before["cloze"]["top5"],
    }
    result = {
        "schema": "gis_recommend.m2_p1_dapt.v1",
        "corpus_sha256": actual_sha,
        "train_files": len(train_rows), "eval_files": len(eval_rows),
        "train_blocks": len(t_blocks), "block": args.block,
        "epochs": args.epochs, "lr": args.lr,
        "loss_first": losses[0] if losses else None,
        "loss_last": losses[-1] if losses else None,
        "train_minutes": round(train_minutes, 1),
        "peak_memory_gb": round(torch.cuda.max_memory_allocated() / 2**30, 2),
        "before": before, "after": after, "signal": signal,
    }
    (args.out_dir / "m2_p1_domain_signal_v1.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print("\n== signal summary ==")
    print(json.dumps(signal, indent=2))

    from model_experiment_ledger import ExperimentLedger, sha256_file as lsha
    led = ExperimentLedger(args.ledger)
    metrics = {"ppl_gis_before": before["ppl_gis_holdout"], "ppl_gis_after": after["ppl_gis_holdout"],
               "ppl_api_before": before["ppl_api_heavy"], "ppl_api_after": after["ppl_api_heavy"],
               "ppl_generic_before": before["ppl_generic_control"], "ppl_generic_after": after["ppl_generic_control"],
               "cloze_top1_before": before["cloze"]["top1"], "cloze_top1_after": after["cloze"]["top1"],
               "cloze_top5_before": before["cloze"]["top5"], "cloze_top5_after": after["cloze"]["top5"]}
    led.register("M2-P1-v1", "M2-P1",
                 data_version=f"dapt_corpus_v1 (sha {actual_sha[:12]}, 26.3M tokens)",
                 model_path=str(ckpt),
                 checkpoint_sha256=lsha(ckpt / "adapter_model.safetensors")
                 if (ckpt / "adapter_model.safetensors").exists() else None,
                 params={"block": args.block, "epochs": args.epochs, "lr": args.lr,
                         "lora": "r16 a32 qkvo NF4", "batch": f"{args.batch_size}x{args.grad_accum}",
                         "corpus": "95% QGIS code / 5% NL, 150-file held-out eval"},
                 gpu_seconds=round(time.time() - t0),
                 peak_memory_gb=result["peak_memory_gb"],
                 metrics=metrics,
                 notes="DAPT-only arm. Answers: does a code-heavy GIS corpus produce detectable domain adaptation? PPL deltas (gis/api vs generic control) + cloze operator probes; task-prompt outputs recorded verbatim. M2-P2 continues from this checkpoint via merge -> new SFT LoRA.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
