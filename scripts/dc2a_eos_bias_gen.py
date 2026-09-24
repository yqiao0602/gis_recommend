#!/usr/bin/env python3
"""DC-2A: state-conditioned EOS logit bias (spec 9a23c13, single variable).

z_EOS' = z_EOS + beta * 1[state = link-phase]
state = >=1 complete L: unit in the generated text (regex, incremental).
Everything else untouched: no trie, no repetition penalty, no beam/length.

Stages:
  calibrate  CPU+GPU: C0 teacher-forced over the 111 gold targets; margin =
             max_{t!=EOS} logit_t - logit_EOS at each chain's terminal EOS
             position; beta = median(margin) + 0.5. LOCKED to
             gate2_eval/dc2a_beta.json — the generate stage refuses to run
             without it (no post-hoc beta adjustment path exists).
  generate   GPU: A1 ep15 greedy generation with the bias processor.
             --limit 8 = smoke.
"""
import argparse
import json
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

REPO = Path(__file__).resolve().parents[1]
BASE = "/home/qy/models/Qwen3.5/Qwen3.5-9B-Base"
SUFFIX = "\nQGIS workflow:"
LUNIT_RE = re.compile(r"L:[A-Za-z0-9_\-]+>[A-Za-z0-9_\-]+")
PUNIT_RE = re.compile(r"P:[A-Za-z0-9_\-]+:(\S+)")


def state_triggered(text):
    """DC-2A-R1 state (spec transfer_phase2_dc2a_r1_spec):
    link-phase OR P-unit repetition run >= 3. The repetition detection runs
    at the COMPLETE P-unit level (operator = non-space segment after the
    second colon), never on raw token substrings."""
    if LUNIT_RE.search(text):
        return True
    ops = PUNIT_RE.findall(text)
    run = best = 1 if ops else 0
    for a, b in zip(ops, ops[1:]):
        run = run + 1 if a == b else 1
        best = max(best, run)
    return best >= 3


def gold_rows():
    path = None
    for p in (REPO / "docs/reports/v2a_manifest/v2a_A_test.jsonl",
              Path("/home/qy/gee_llm_smoke/v2a_A_test.jsonl")):
        if p.exists():
            path = p
            break
    return [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines()]


def build_model(adapter):
    import torch
    from transformers import AutoModelForCausalLM, BitsAndBytesConfig
    from peft import PeftModel
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                             bnb_4bit_compute_dtype=torch.bfloat16,
                             bnb_4bit_use_double_quant=True)
    model = AutoModelForCausalLM.from_pretrained(BASE, quantization_config=bnb,
                                                 device_map="cuda:0")
    if adapter:
        model = PeftModel.from_pretrained(model, adapter)
    model.eval()
    return model


def stage_calibrate(args, tok):
    import torch
    lock_path = Path(args.out_dir) / "dc2a_beta.json"
    if lock_path.exists():                      # LOCK is LOCK: never recompute
        print("[cal] beta already locked:", lock_path.read_text(encoding="utf-8"))
        return 0
    rows = gold_rows()
    model = build_model(None)                      # C0 = base, no adapter
    eos_id = tok.eos_token_id
    margins = []
    excluded = 0
    skipped_oom = 0
    CAP = 768          # forward-length cap: peak buffers scale with T; rows
    for i, r in enumerate(rows):   # beyond it are skipped (median is robust)
        prompt_ids = tok(r["task_text"] + SUFFIX, return_tensors="pt")["input_ids"][0]
        tgt_ids = tok(" ".join("P:%d:%s" % (j, p["operator_id"])
                               for j, p in enumerate(r["processes"]))
                      + " " + " ".join("L:%s>%s" % (l["source_process_id"],
                                                    l["target_process_id"])
                                       for l in r["links"]),
                      add_special_tokens=False)["input_ids"] + [eos_id]
        full = torch.cat([prompt_ids, torch.tensor(tgt_ids)])
        if full.numel() > CAP:
            excluded += 1          # a truncated forward would give a WRONG margin
            continue
        ids = full.unsqueeze(0).to("cuda:0")
        # only the second-to-last position's logits are needed (it predicts the
        # terminal EOS): logits_to_keep=2 avoids the full (T,V) logits tensor
        try:
            out = model(ids, use_cache=False, logits_to_keep=2).logits[0]
        except torch.OutOfMemoryError:
            torch.cuda.empty_cache()
            skipped_oom += 1
            continue
        row_logits = out[0].clone()          # predicts the terminal EOS token
        del out
        others = torch.cat([row_logits[:eos_id], row_logits[eos_id + 1:]])
        margins.append(float(others.max() - row_logits[eos_id]))
        del ids, prompt_ids, tgt_ids, row_logits, others
        if (i + 1) % 5 == 0:
            torch.cuda.empty_cache()   # return segments: shared-GPU coexistence
        if (i + 1) % 20 == 0:
            print("[cal] %d/%d (excluded %d, oom %d)"
                  % (i + 1, len(rows), excluded, skipped_oom), flush=True)
    margins.sort()
    import statistics
    beta = round(statistics.median(margins) + 0.5, 4)
    lock = {"schema": "gis_recommend.transfer.dc2a.beta", "beta": beta,
            "median_margin": round(statistics.median(margins), 4),
            "margin_p25": round(margins[len(margins) // 4], 4),
            "margin_p75": round(margins[len(margins) * 3 // 4], 4),
            "n_rows": len(margins), "excluded_over_cap": excluded,
            "skipped_oom": skipped_oom, "cap": CAP,
            "rule": "median(margin)+0.5 nat, LOCKED"}
    dest = Path(args.out_dir) / "dc2a_beta.json"
    dest.write_text(json.dumps(lock, indent=1), encoding="utf-8")
    print(json.dumps(lock, indent=1))
    print("BETA LOCKED:", beta, "->", dest)
    return 0


def stage_generate(args, tok):
    import torch
    from transformers import LogitsProcessor
    lock_path = Path(args.out_dir) / "dc2a_beta.json"
    if not lock_path.exists():
        print("REFUSING: beta not locked (run --stage calibrate first)")
        return 1
    beta = json.loads(lock_path.read_text(encoding="utf-8"))["beta"]
    print("[dc2a] beta =", beta, "(locked)", flush=True)
    rows = gold_rows()
    if args.limit:
        rows = rows[:args.limit]
    model = build_model(args.adapter)
    eos_ids = [x for x in (tok.eos_token_id, tok.pad_token_id) if x is not None]

    class EOSBias(LogitsProcessor):
        def __init__(self):
            self.plen = None
            self.boost_steps = 0
            self.steps = 0

        def __call__(self, input_ids, scores):
            if self.plen is None:
                self.plen = input_ids.shape[1]
            self.steps += 1
            text = tok.decode(input_ids[0][self.plen:], skip_special_tokens=True)
            if state_triggered(text):
                self.boost_steps += 1
                for eid in eos_ids:
                    scores[0, eid] += beta
            return scores

    preds = []
    t0 = time.time()
    for i, r in enumerate(rows):
        proc = EOSBias()
        enc = tok(r["task_text"] + SUFFIX, return_tensors="pt", truncation=True,
                  max_length=768).to("cuda:0")
        gen = model.generate(**enc, max_new_tokens=args.max_new_tokens,
                             do_sample=False,
                             eos_token_id=eos_ids,
                             pad_token_id=tok.pad_token_id,
                             logits_processor=[proc])
        cont = gen[0][enc["input_ids"].shape[1]:]
        preds.append({"wid": r["wid"],
                      "raw": tok.decode(cont, skip_special_tokens=True),
                      "n_gen_tokens": int(cont.shape[0]),
                      "boost_frac": round(proc.boost_steps / max(proc.steps, 1), 4)})
        if (i + 1) % 20 == 0:
            print("[gen] %d/%d (%.1f min)" % (i + 1, len(rows),
                                              (time.time() - t0) / 60), flush=True)
    out = Path(args.out_dir)
    out.mkdir(parents=True, exist_ok=True)
    dest = out / ("v2a_%s_predictions.jsonl" % args.tag)
    dest.write_text("".join(json.dumps(p, ensure_ascii=False) + "\n"
                            for p in preds), encoding="utf-8")
    bf = [p["boost_frac"] for p in preds]
    print("boost_frac mean:", round(sum(bf) / len(bf), 4),
          "| rows never boosted:", sum(1 for x in bf if x == 0))
    print("wrote", dest)
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["calibrate", "generate"], required=True)
    ap.add_argument("--adapter",
                    default="/home/qy/gee_llm_smoke/route2_A1/qgis_sft_ep15")
    ap.add_argument("--tag", default="dc2a_a1")
    ap.add_argument("--out-dir", default=str(REPO / "gate2_eval"))
    ap.add_argument("--max-new-tokens", type=int, default=512)
    ap.add_argument("--limit", type=int, default=0)
    args = ap.parse_args()
    from transformers import AutoTokenizer
    tok = AutoTokenizer.from_pretrained(BASE)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    tok.padding_side = "left"
    if args.stage == "calibrate":
        return stage_calibrate(args, tok)
    return stage_generate(args, tok)


if __name__ == "__main__":
    raise SystemExit(main())
