"""evaluate_dev.py — QGIS dev-120 evaluation (checkpoint selection metric).

Loads base+adapter, generates greedy on the 120 dev rows, parses generated
text back into graphs (fail-closed: parse error -> empty graph, counted),
and computes the primary task metric:
  operator set F1 (mean over rows)  <- checkpoint selection metric (P0-5)
plus diagnostics: exact-graph EM, link F1, parse-failure rate.

Final evaluation (final-100 + refusal-12) uses the frozen benchmark scorer
(scripts/score_qgis_planner_v021.py imports it verbatim) and is NOT run
here — dev is for checkpoint selection only, per P0 contract.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import torch

from route2_training.harness import text_to_graph


def op_set_f1(pred_ops: set, gold_ops: set) -> float:
    if not pred_ops and not gold_ops:
        return 1.0
    inter = len(pred_ops & gold_ops)
    if inter == 0:
        return 0.0
    return 2 * inter / (len(pred_ops) + len(gold_ops))


def link_f1(pred_links: set, gold_links: set) -> float:
    if not pred_links and not gold_links:
        return 1.0
    inter = len(pred_links & gold_links)
    if inter == 0:
        return 0.0
    return 2 * inter / (len(pred_links) + len(gold_links))


def parse_generation(text: str) -> tuple[list[dict], list[dict]]:
    """First non-empty line of the generation is the graph text (fail-closed)."""
    for line in text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            return text_to_graph(line)
        except ValueError:
            continue
    return [], []


@torch.no_grad()
def evaluate_dev(base_model: str, adapter: str | None, dev_path: str,
                 out_json: str, max_new_tokens: int = 512,
                 batch_size: int = 4) -> dict:
    from transformers import (AutoModelForCausalLM, AutoTokenizer,
                              BitsAndBytesConfig)
    from peft import PeftModel

    tok = AutoTokenizer.from_pretrained(base_model)
    if tok.pad_token is None:
        tok.pad_token = tok.eos_token
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                             bnb_4bit_compute_dtype=torch.bfloat16,
                             bnb_4bit_use_double_quant=True)
    model = AutoModelForCausalLM.from_pretrained(base_model, quantization_config=bnb,
                                                 device_map="cuda:0")
    if adapter:
        model = PeftModel.from_pretrained(model, adapter)
    model.eval()

    rows = [json.loads(l) for l in open(dev_path, encoding="utf-8") if l.strip()]
    f1s, ems, link_f1s, parse_fail = [], [], [], 0
    for i in range(0, len(rows), batch_size):
        batch = rows[i:i + batch_size]
        prompts = [r["task_text"] + "\nQGIS workflow:" for r in batch]
        enc = tok(prompts, return_tensors="pt", padding=True,
                  truncation=True, max_length=768).to("cuda:0")
        gen = model.generate(**enc, max_new_tokens=max_new_tokens,
                             do_sample=False,
                             eos_token_id=[tok.eos_token_id, tok.pad_token_id],
                             pad_token_id=tok.pad_token_id)
        for j, r in enumerate(batch):
            text = tok.decode(gen[j][enc["input_ids"].shape[1]:],
                              skip_special_tokens=True)
            pred_p, pred_l = parse_generation(text)
            if not pred_p:
                parse_fail += 1
            gold_ops = set(p["operator_id"] for p in r["processes"])
            pred_ops = set(p["operator_id"] for p in pred_p)
            gold_links = set((l["source_process_id"], l["target_process_id"])
                             for l in r["links"])
            pred_links = set((l["source_process_id"], l["target_process_id"])
                             for l in pred_l)
            f1s.append(op_set_f1(pred_ops, gold_ops))
            link_f1s.append(link_f1(pred_links, gold_links))
            ems.append(1.0 if (pred_ops == gold_ops and pred_links == gold_links) else 0.0)
        print(f"[dev] {min(i + batch_size, len(rows))}/{len(rows)} "
              f"opF1={sum(f1s) / len(f1s):.4f}", flush=True)

    metrics = {
        "n": len(rows),
        "operator_set_f1": sum(f1s) / len(f1s),
        "exact_graph_em": sum(ems) / len(ems),
        "link_f1": sum(link_f1s) / len(link_f1s),
        "parse_failure_rate": parse_fail / len(rows),
    }
    Path(out_json).parent.mkdir(parents=True, exist_ok=True)
    Path(out_json).write_text(json.dumps(metrics, indent=2), encoding="utf-8")
    print(json.dumps(metrics, indent=2))
    return metrics


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-model", required=True)
    ap.add_argument("--adapter", default=None)
    ap.add_argument("--dev", required=True, help="v2a_A_dev.jsonl (120 rows)")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()
    evaluate_dev(args.base_model, args.adapter, args.dev, args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
