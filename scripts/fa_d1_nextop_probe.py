#!/usr/bin/env python3
"""FA-D1: QGIS output-space probe on route-2 arms (final FA evidence).

Stage NLL (question 1 - "does it know the next operator in context?"):
  teacher-forced full gold target, per-row mean target NLL + top-1 token
  accuracy, on dev+test gold chains (in-distribution target format via the
  trained prompt+target construction). Arms are compared on IDENTICAL token
  positions (paired rows), so scaffold tokens wash out of the A1-C0 delta.

Stage CONT (question 2 - "does it stop when generating on its own?"):
  greedy free continuation from 50% gold prefix, max 256 new tokens, same
  generation recipe as evaluate_dev; measures stopped-by-EOS rate, length,
  operator counts, max run, injected (non-gold) operators, hit-cap.

Bootstrap: row-level 10k resamples, CI on A1-C0 deltas (rng frozen 20260923).
Zero training; read-only checkpoints; ~1h GPU at batch<=4.
"""
import argparse
import json
import random
import sys
import time
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import torch  # noqa: E402  (module-level: decorators below reference it)

REPO = Path(__file__).resolve().parents[1]
BASE = "/home/qy/models/Qwen3.5/Qwen3.5-9B-Base"
ARMS = {"C0": "/home/qy/gee_llm_smoke/route2_C0/qgis_sft_ep20",
        "A1": "/home/qy/gee_llm_smoke/route2_A1/qgis_sft_ep15",
        "B1": "/home/qy/gee_llm_smoke/route2_B1/qgis_sft_ep18"}
SUFFIX = "\nQGIS workflow:"
MAX_NEW = 256
PREFIX_FRAC = 0.5
RNG_SEED = 20260923
N_BOOT = 10000


def load_rows(tok):
    def manifest(split):
        for p in (REPO / f"docs/reports/v2a_manifest/v2a_A_{split}.jsonl",
                  Path(f"/home/qy/gee_llm_smoke/v2a_A_{split}.jsonl")):
            if p.exists():
                return p
        raise FileNotFoundError(f"v2a_A_{split}.jsonl not found")
    train_ops = set()
    rows = []
    for line in manifest("train").read_text(encoding="utf-8").splitlines():
        r = json.loads(line)
        train_ops.add(tuple(p["operator_id"] for p in r["processes"]))
    for split in ("dev", "test"):
        for line in manifest(split).read_text(encoding="utf-8").splitlines():
            r = json.loads(line)
            ops = [p["operator_id"] for p in r["processes"]]
            rows.append({"wid": r["wid"], "split": split, "task": r["task_text"],
                         "ops": ops,
                         "chain_disjoint": tuple(ops) not in train_ops})
    return rows


def target_text(ops):
    return " ".join("P:%d:%s" % (i, op) for i, op in enumerate(ops))


@torch.no_grad()
def nll_pass(model, tok, rows, device):
    out = {}
    eos = tok.eos_token_id
    for i, r in enumerate(rows):
        prompt_ids = tok(r["task"] + SUFFIX, return_tensors="pt")["input_ids"][0]
        tgt_ids = tok(target_text(r["ops"]), add_special_tokens=False)["input_ids"]
        if eos is not None:
            tgt_ids = tgt_ids + [eos]
        ids = torch.cat([prompt_ids, torch.tensor(tgt_ids)])[:1024].unsqueeze(0).to(device)
        n_prompt = min(len(prompt_ids), ids.shape[1] - 1)
        logits = model(ids).logits[0]
        tgt = ids[0, 1:]
        # per-token NLL without a full-vocab float32 upcast (OOM-safe on a
        # shared GPU): cross_entropy keeps logits in bf16
        tok_nll = torch.nn.functional.cross_entropy(
            logits[:-1], tgt, reduction="none")
        tgt_lp = -tok_nll[n_prompt - 1:]
        top1 = logits[:-1].argmax(-1)[n_prompt - 1:]
        out[r["wid"]] = {"nll": float(tgt_lp.mean()),
                         "acc": float((top1 == tgt[n_prompt - 1:]).float().mean()),
                         "n_tgt": int(tgt_lp.numel())}
        if (i + 1) % 40 == 0:
            print("[nll] %d/%d" % (i + 1, len(rows)), flush=True)
    return out


@torch.no_grad()
def cont_pass(model, tok, rows, device):
    res = {}
    eos_list = [x for x in (tok.eos_token_id, tok.pad_token_id) if x is not None]
    for i, r in enumerate(rows):
        k = max(1, int(len(r["ops"]) * PREFIX_FRAC))
        prefix = target_text(r["ops"][:k])
        prompt = r["task"] + SUFFIX + ((" " + prefix) if prefix else "")
        enc = tok(prompt, return_tensors="pt", truncation=True, max_length=768).to(device)
        gen = model.generate(**enc, max_new_tokens=MAX_NEW, do_sample=False,
                             eos_token_id=eos_list, pad_token_id=tok.pad_token_id)
        cont_ids = gen[0][enc["input_ids"].shape[1]:]
        text = tok.decode(cont_ids, skip_special_tokens=True)
        n_gen = int(cont_ids.shape[0])
        units = [u for u in text.split() if u.startswith("P:")]
        cont_ops = []
        for u in units:
            try:
                _, _, op = u.split(":", 2)
                cont_ops.append(op)
            except ValueError:
                continue
        gold_ops = set(r["ops"])
        run = best = 1 if cont_ops else 0
        for a, b in zip(cont_ops, cont_ops[1:]):
            run = run + 1 if a == b else 1
            best = max(best, run)
        res[r["wid"]] = {
            "stopped": bool(n_gen < MAX_NEW),
            "n_gen_tokens": n_gen, "n_units": len(cont_ops),
            "max_run": best if cont_ops else 0,
            "distinct_ops": len(set(cont_ops)),
            "injected_ops": sum(1 for o in cont_ops if o not in gold_ops),
            "repeat_gold_suffix": sum(1 for o in cont_ops if o in gold_ops)}
        if (i + 1) % 30 == 0:
            print("[cont] %d/%d" % (i + 1, len(rows)), flush=True)
    return res


def bootstrap(rows, m_a1, m_c0, key=None):
    rng = random.Random(RNG_SEED)
    wids = [r["wid"] for r in rows]

    def mean(arm, s):
        vals = [m_a1[w] if arm == "A1" else m_c0[w] for w in s]
        vals = [v[key] if key else v for v in vals]
        return sum(vals) / len(vals)
    point = mean("A1", wids) - mean("C0", wids)
    deltas = []
    for _ in range(N_BOOT):
        s = [wids[rng.randrange(len(wids))] for _ in wids]
        deltas.append(mean("A1", s) - mean("C0", s))
    deltas.sort()
    return {"point": round(point, 4),
            "ci95": [round(deltas[int(0.025 * N_BOOT)], 4),
                     round(deltas[int(0.975 * N_BOOT)], 4)]}


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--device", default="cuda:0")
    ap.add_argument("--out", default=str(
        REPO / "docs/reports/transfer_phase2/fa/fa_d1_results.json"))
    args = ap.parse_args()
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig
    from peft import PeftModel

    tok = AutoTokenizer.from_pretrained(BASE)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    tok.padding_side = "left"
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                             bnb_4bit_compute_dtype=torch.bfloat16,
                             bnb_4bit_use_double_quant=True)
    rows = load_rows(tok)
    print("rows:", len(rows), "disjoint:",
          sum(r["chain_disjoint"] for r in rows), flush=True)
    res = {"schema": "gis_recommend.transfer.fa.d1", "n_rows": len(rows),
           "n_boot": N_BOOT, "prefix_frac": PREFIX_FRAC, "max_new": MAX_NEW}
    t0 = time.time()
    for arm, adapter in ARMS.items():
        model = AutoModelForCausalLM.from_pretrained(
            BASE, quantization_config=bnb, device_map=args.device)
        model = PeftModel.from_pretrained(model, adapter)
        model.eval()
        print("[arm %s] loaded (%.1f min)" % (arm, (time.time() - t0) / 60), flush=True)
        nll = nll_pass(model, tok, rows, args.device)
        cont = cont_pass(model, tok, rows, args.device)
        # per-arm aggregates
        def agg(d, k):
            return round(sum(v[k] for v in d.values()) / max(len(d), 1), 4)
        res[arm] = {
            "nll_mean": agg(nll, "nll"), "tgt_tok_acc": agg(nll, "acc"),
            "stopped_rate": round(sum(v["stopped"] for v in cont.values())
                                  / max(len(cont), 1), 4),
            "cont_tokens_mean": agg(cont, "n_gen_tokens"),
            "cont_units_mean": agg(cont, "n_units"),
            "max_run_mean": agg(cont, "max_run"),
            "injected_ops_mean": agg(cont, "injected_ops")}
        if arm == "C0":
            res["_c0_nll"], res["_c0_cont"] = nll, cont
        if arm == "A1":
            res["delta_A1-C0"] = {
                "nll": bootstrap(rows, nll, res["_c0_nll"], "nll"),
                "acc": bootstrap(rows, nll, res["_c0_nll"], "acc"),
                "stopped": bootstrap(rows, cont, res["_c0_cont"], "stopped"),
                "cont_tokens": bootstrap(rows, cont, res["_c0_cont"],
                                         "n_gen_tokens"),
                "injected": bootstrap(rows, cont, res["_c0_cont"],
                                      "injected_ops")}
        if arm == "B1":
            res["delta_B1-C0"] = {
                "nll": bootstrap(rows, nll, res["_c0_nll"], "nll"),
                "acc": bootstrap(rows, nll, res["_c0_nll"], "acc"),
                "stopped": bootstrap(rows, cont, res["_c0_cont"], "stopped"),
                "cont_tokens": bootstrap(rows, cont, res["_c0_cont"],
                                         "n_gen_tokens"),
                "injected": bootstrap(rows, cont, res["_c0_cont"],
                                      "injected_ops")}
            del res["_c0_nll"], res["_c0_cont"]
        print("[arm %s] done: %s (%.1f min)" % (
            arm, json.dumps(res[arm]), (time.time() - t0) / 60), flush=True)
        del model
        torch.cuda.empty_cache()
    Path(args.out).parent.mkdir(parents=True, exist_ok=True)
    Path(args.out).write_text(json.dumps(res, indent=1, ensure_ascii=False),
                              encoding="utf-8")
    print("wrote", args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
