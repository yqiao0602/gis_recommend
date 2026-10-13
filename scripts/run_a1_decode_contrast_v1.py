#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A1 decode-contrast runner (implements A_EXPERIMENT_PROTOCOL_V1 +
V1_1 verbatim — NO design decisions here).

Server execution (after SHA gate passes):
  python run_a1_decode_contrast_v1.py \
      --base /root/models/Qwen3.5-9B-Base \
      --adapter /root/data/stage1_run_planner_v2/stage1_adapter \
      --dev /path/to/planner_v2_dev_fix1_loopinv.jsonl \
      --sample /path/to/A1_SAMPLE_131.json \
      --out-dir /path/to/a1_results_new

  --dry-run      : validate inputs/outputs without loading the model
  --limit N      : smoke run on first N sample rows (protocol bookkeeping
                   only; NOT protocol results)

Guarantees (per frozen protocol):
  - SHA gate: base+adapter SHA256 recorded into results header; execution
    MUST be preceded by owner-side comparison against p0b_768 artifacts
    (gate enforced procedurally — this script records, not judges).
  - Single variable: arm 768 (baseline re-check) vs arm 2048; everything
    else identical (prompt SEP, truncation 1024, greedy, eos/pad stop).
  - No new stop rules; termination recorded per v1.1 four-way taxonomy.
  - Outputs to a NEW directory; never touches historical artifacts.
"""

import argparse
import hashlib
import json
import math
import os
import sys
from collections import Counter

SEP = ("\nWorkflow blueprint: output JSON with keys stages (ordered "
       "semantic stages with per-stage repeat counts) and repetition_groups "
       "(groups with repeat>1, each with iteration_hint from: per_band, "
       "per_class, per_year, per_feature, generic_each, unspecified).")
ARMS = [768, 2048]
WATCH_IDX = 1024  # mechanical-inflation-risk control row


def sha256_path(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def sha256_dir(d):
    """Stable fingerprint of a model/adapter directory (file hash + relpath)."""
    entries = []
    for root, _, files in os.walk(d):
        for fn in sorted(files):
            p = os.path.join(root, fn)
            rel = os.path.relpath(p, d)
            entries.append((rel.replace("\\", "/"), sha256_path(p)))
    entries.sort()
    h = hashlib.sha256()
    for rel, fh in entries:
        h.update(rel.encode())
        h.update(fh.encode())
    return {"dir_sha256": h.hexdigest(), "n_files": len(entries)}


def classify_termination(gen_ids, eos_ids, max_new):
    """v1.1 taxonomy: EOS / MAX_TOKENS / OTHER_STOP (record alongside
    PARSE_FAIL, which is decided separately by the parser)."""
    if not gen_ids:
        return "OTHER_STOP", 0
    n = len(gen_ids)
    tail = gen_ids[-1]
    if tail in eos_ids:
        return "EOS", n
    if n >= max_new:
        return "MAX_TOKENS", n
    return "OTHER_STOP", n


def parse_stages(text):
    try:
        o = json.loads(text or "")
        if isinstance(o, dict) and isinstance(o.get("stages"), list) \
                and o["stages"]:
            return o["stages"]
    except Exception:
        pass
    return None


def wilson_ci(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return (round(p, 4), round(center - half, 4), round(center + half, 4))


def bag_f1(pred_stages, gold_stages):
    from collections import defaultdict
    pc, gc = defaultdict(int), defaultdict(int)
    for s in pred_stages or []:
        pc[s["family"]] += int(s.get("repeat", 1))
    for s in gold_stages:
        gc[s["family"]] += int(s.get("repeat", 1))
    keys = set(pc) | set(gc)
    tp = sum(min(pc[k], gc[k]) for k in keys)
    np_, ng = sum(pc.values()), sum(gc.values())
    return round(2 * tp / (np_ + ng), 4) if (np_ + ng) else 0.0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", required=True)
    ap.add_argument("--adapter", required=True)
    ap.add_argument("--dev", required=True)
    ap.add_argument("--sample", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    assert not os.path.exists(a.out_dir), \
        f"refusing to overwrite existing dir: {a.out_dir}"
    os.makedirs(a.out_dir)

    sample = json.load(open(a.sample, encoding="utf-8"))
    assert sample["schema"] == "a1_decode_contrast_sample_v1_1"
    rows_all = [json.loads(l) for l in open(a.dev, encoding="utf-8")
                if l.strip()]
    sel = sample["samples"]
    if a.limit:
        sel = sel[:a.limit]

    def gold_of(i):
        t = rows_all[i]["target"]
        if isinstance(t, str):
            t = json.loads(t)
        return t

    header = {
        "protocol": "A_EXPERIMENT_PROTOCOL_V1 + V1_1",
        "arms": ARMS,
        "baseline_config_from": "p0b_768/predictions.json (768, greedy)",
        "artifacts": {"base": a.base, "adapter": a.adapter,
                      "base_fingerprint": sha256_dir(a.base),
                      "adapter_fingerprint": sha256_dir(a.adapter)},
        "n_rows": len(sel),
        "sample_schema": sample["schema"],
        "watch_idx": WATCH_IDX,
    }
    print(json.dumps(header["artifacts"], indent=2))
    if a.dry_run:
        header["dry_run"] = True
        json.dump({"header": header}, open(
            os.path.join(a.out_dir, "dry_run_header.json"), "w",
            encoding="utf-8"), indent=2)
        print("DRY-RUN OK — artifacts fingerprinted, sample validated:",
              len(sel), "rows")
        return 0

    import torch
    from transformers import AutoTokenizer, AutoModelForCausalLM, \
        BitsAndBytesConfig
    from peft import PeftModel

    tok = AutoTokenizer.from_pretrained(a.base, trust_remote_code=True)
    bnb = BitsAndBytesConfig(load_in_4bit=True,
                             bnb_4bit_compute_dtype=torch.bfloat16,
                             bnb_4bit_quant_type="nf4",
                             bnb_4bit_use_double_quant=True)
    model = AutoModelForCausalLM.from_pretrained(
        a.base, trust_remote_code=True, torch_dtype=torch.bfloat16,
        device_map="cuda:0", quantization_config=bnb)
    model = PeftModel.from_pretrained(model, a.adapter)
    model.eval()
    eos_ids = {tok.eos_token_id, tok.pad_token_id}

    results = {arm: [] for arm in ARMS}
    with torch.no_grad():
        for arm in ARMS:
            print(f"=== ARM max_new_tokens={arm} ===", flush=True)
            for ridx, s in enumerate(sel):
                i = s["idx"]
                text_in = rows_all[i]["task"] + SEP
                enc = tok(text_in, return_tensors="pt", truncation=True,
                          max_length=1024).to("cuda:0")
                g = model.generate(**enc, max_new_tokens=arm,
                                   do_sample=False,
                                   eos_token_id=list(eos_ids),
                                   pad_token_id=tok.pad_token_id)
                gen_ids = g[0][enc["input_ids"].shape[1]:].tolist()
                term, ntok = classify_termination(gen_ids, eos_ids, arm)
                text = tok.decode(gen_ids, skip_special_tokens=True)
                st_ = parse_stages(text)
                gold = gold_of(i)
                rec = {
                    "idx": i,
                    "source_row_id": s.get("source_row_id"),
                    "task_sha256": s.get("task_sha256"),
                    "stratum": s["stratum"],
                    "arm_max_new_tokens": arm,
                    "termination": term,          # v1.1 taxonomy
                    "generated_tokens": ntok,
                    "parse_ok": st_ is not None,
                    "parse_fail_underlying_term": (term if st_ is None
                                                   else None),
                    "pred_n_stages": len(st_) if st_ is not None else None,
                    "gold_n_stages": len(gold["stages"]),
                    "bag_f1_vs_trusted_gold": (bag_f1(st_, gold["stages"])
                                               if st_ is not None else None),
                    "pred_text": text,
                }
                results[arm].append(rec)
                if (ridx + 1) % 20 == 0:
                    print(f"  {ridx+1}/{len(sel)}", flush=True)

    for arm in ARMS:
        json.dump({"header": header, "rows": results[arm]},
                  open(os.path.join(a.out_dir,
                                    f"a1_arm{arm}_raw.json"), "w",
                       encoding="utf-8"), ensure_ascii=False, indent=1)

    # ---------- v1.1 pre-registered summary ----------
    base_by_idx = {r["idx"]: r for r in results[ARMS[0]]}
    exp_by_idx = {r["idx"]: r for r in results[ARMS[1]]}
    strata = sorted({s["stratum"] for s in sel})
    summary = {"by_stratum": {}, "paired": [], "watch_1024": None,
               "gate_metrics": {}}
    for stname in strata:
        idxs = [s["idx"] for s in sel if s["stratum"] == stname]
        n = len(idxs)
        trunc_b = sum(1 for i in idxs if base_by_idx[i]["termination"]
                      == "MAX_TOKENS")
        trunc_e = sum(1 for i in idxs if exp_by_idx[i]["termination"]
                      == "MAX_TOKENS")
        parse_b = sum(1 for i in idxs if base_by_idx[i]["parse_ok"])
        parse_e = sum(1 for i in idxs if exp_by_idx[i]["parse_ok"])
        over = sum(1 for i in idxs
                   if exp_by_idx[i]["pred_n_stages"] is not None and
                   exp_by_idx[i]["pred_n_stages"]
                   > exp_by_idx[i]["gold_n_stages"] * 1.5)
        bag_b = [base_by_idx[i]["bag_f1_vs_trusted_gold"] or 0 for i in idxs]
        bag_e = [exp_by_idx[i]["bag_f1_vs_trusted_gold"] or 0 for i in idxs]
        tok_e = [exp_by_idx[i]["generated_tokens"] for i in idxs]
        summary["by_stratum"][stname] = {
            "n": n,
            "truncation_baseline": trunc_b, "truncation_experiment": trunc_e,
            "truncation_delta_ci": wilson_ci(trunc_b - trunc_e, n),
            "parse_baseline": parse_b, "parse_experiment": parse_e,
            "over_emission_rows_exp": over,
            "bag_mean_baseline": round(sum(bag_b) / n, 4),
            "bag_mean_experiment": round(sum(bag_e) / n, 4),
            "mean_gen_tokens_experiment": round(sum(tok_e) / n, 1),
        }
        for i in idxs:
            summary["paired"].append({
                "idx": i, "stratum": stname,
                "term_b": base_by_idx[i]["termination"],
                "term_e": exp_by_idx[i]["termination"],
                "tokens_b": base_by_idx[i]["generated_tokens"],
                "tokens_e": exp_by_idx[i]["generated_tokens"],
                "bag_b": base_by_idx[i]["bag_f1_vs_trusted_gold"],
                "bag_e": exp_by_idx[i]["bag_f1_vs_trusted_gold"],
            })
    if WATCH_IDX in exp_by_idx:
        w = {"idx": WATCH_IDX,
             "baseline": {k: base_by_idx[WATCH_IDX][k] for k in
                          ("termination", "generated_tokens", "parse_ok",
                           "pred_n_stages", "gold_n_stages")},
             "experiment": {k: exp_by_idx[WATCH_IDX][k] for k in
                            ("termination", "generated_tokens", "parse_ok",
                             "pred_n_stages", "gold_n_stages")},
             "note": "mechanical-inflation-risk control: longer output "
                     "is NOT progress; check length jump / stage count / "
                     "structural deviation"}
        summary["watch_1024"] = w

    t2 = summary["by_stratum"].get("T2_truncated_long", {})
    summary["gate_metrics"] = {
        "T2_truncation_improved_count": t2.get("truncation_baseline", 0)
                                        - t2.get("truncation_experiment", 0),
        "T2_n": t2.get("n"),
        "note": ("census stratum: report counts/proportion change with CI, "
                 "NOT random-sample significance; truncation drop alone "
                 "does NOT pass the gate — coverage gain must not be "
                 "offset by over-emission or cost"),
    }
    json.dump(summary, open(os.path.join(a.out_dir, "a1_summary_v1_1.json"),
                            "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print(json.dumps(summary["by_stratum"], indent=2, ensure_ascii=False))
    print(json.dumps(summary["gate_metrics"], indent=2))
    print("saved in:", a.out_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
