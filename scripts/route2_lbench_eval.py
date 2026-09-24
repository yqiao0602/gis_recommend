#!/usr/bin/env python3
"""Route-2 L-bench: P0-6 final-100 + refusal-12 for the three arms.

Generation: route-2 frozen recipe (task_text + "\\nQGIS workflow:", greedy,
512, eos list) -> text_to_graph -> benchmark graph rows.
Refusal decision policy: the arms are SFT-only (no abstention training) and
always plan; the adapter therefore emits decision="generate" with whatever
graph parsed (empty processes if unparseable). Their refusal metrics are the
honest measurement of that behavior, expected ~0.
Scoring: score_benchmark imported verbatim from
score_qgis_planner_benchmark_v01.py — zero metric reimplementation.
"""
import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from route2_training.harness import text_to_graph  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
BASE = "/home/qy/models/Qwen3.5/Qwen3.5-9B-Base"
SUFFIX = "\nQGIS workflow:"
ARMS = {"C0": "/home/qy/gee_llm_smoke/route2_C0/qgis_sft_ep20",
        "A1": "/home/qy/gee_llm_smoke/route2_A1/qgis_sft_ep15",
        "B1": "/home/qy/gee_llm_smoke/route2_B1/qgis_sft_ep18"}
TASK_FILES = {"final_100": "final_100.tasks.jsonl",
              "refusal_12": "refusal_12.tasks.jsonl"}
TASK_DIRS = [REPO / "docs/reports/qgis_planner_eval_v1/materialized",
             Path("/home/qy/system_redesign/docs/reports/qgis_planner_eval_v1/materialized")]
GOLD_DIR = REPO / "docs/reports/qgis_planner_eval_v1/gold"


def tasks_path(name):
    for d in TASK_DIRS:
        p = d / TASK_FILES[name]
        if p.exists():
            return p
    raise FileNotFoundError(name)


def stage_generate(args, tok):
    import torch
    from transformers import AutoModelForCausalLM, BitsAndBytesConfig
    from peft import PeftModel
    adapter = ARMS[args.arm]
    bnb = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4",
                             bnb_4bit_compute_dtype=torch.bfloat16,
                             bnb_4bit_use_double_quant=True)
    model = AutoModelForCausalLM.from_pretrained(BASE, quantization_config=bnb,
                                                 device_map="cuda:0")
    model = PeftModel.from_pretrained(model, adapter)
    model.eval()
    eos_ids = [x for x in (tok.eos_token_id, tok.pad_token_id) if x is not None]
    out = Path(args.out_dir) / args.arm
    out.mkdir(parents=True, exist_ok=True)
    for set_name in ("final_100", "refusal_12"):
        rows = [json.loads(l) for l in
                tasks_path(set_name).read_text(encoding="utf-8").splitlines()
                if l.strip()]
        preds = []
        t0 = time.time()
        for i, r in enumerate(rows):
            enc = tok(r["task_text"] + SUFFIX, return_tensors="pt",
                      truncation=True, max_length=768).to("cuda:0")
            gen = model.generate(**enc, max_new_tokens=args.max_new_tokens,
                                 do_sample=False, eos_token_id=eos_ids,
                                 pad_token_id=tok.pad_token_id)
            text = tok.decode(gen[0][enc["input_ids"].shape[1]:],
                              skip_special_tokens=True)
            row = {"sample_id": r["sample_id"], "decision": "generate",
                   "processes": [], "links": [], "raw": text}
            for line in text.strip().splitlines():
                line = line.strip()
                if not line:
                    continue
                try:
                    procs, links = text_to_graph(line)
                    row["processes"] = [
                        {"process_id": p["process_id"],
                         "operator_id": p["operator_id"]} for p in procs]
                    row["links"] = [
                        {"source_process_id": l["source_process_id"],
                         "target_process_id": l["target_process_id"]}
                        for l in links]
                    break
                except ValueError:
                    continue
            preds.append(row)
            if (i + 1) % 25 == 0:
                print("[%s/%s] %d/%d (%.1f min)"
                      % (args.arm, set_name, i + 1, len(rows),
                         (time.time() - t0) / 60), flush=True)
        dest = out / ("%s_%s_predictions.jsonl" % (args.arm, set_name))
        dest.write_text("".join(json.dumps(p, ensure_ascii=False) + "\n"
                                for p in preds), encoding="utf-8")
        print("wrote", dest, flush=True)


def stage_score(args):
    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
    from score_qgis_planner_benchmark_v01 import score_benchmark

    def read_jsonl(p):
        return [json.loads(l) for l in Path(p).read_text(encoding="utf-8").splitlines()
                if l.strip()]

    gold_dir = GOLD_DIR if GOLD_DIR.exists() else \
        Path("/home/qy/system_redesign/docs/reports/qgis_planner_eval_v1/gold")
    graph_gold = read_jsonl(gold_dir / "final_100.gold.jsonl")
    refusal_gold = read_jsonl(gold_dir / "refusal_12.gold.jsonl")
    results = {}
    for arm in ARMS:
        g = read_jsonl(Path(args.out_dir) / arm / f"{arm}_final_100_predictions.jsonl")
        r = read_jsonl(Path(args.out_dir) / arm / f"{arm}_refusal_12_predictions.jsonl")
        scored = score_benchmark(graph_gold, g, refusal_gold, r)
        results[arm] = {"graph": scored["graph"], "refusal": scored["refusal"]}
        print("\n===== %s =====" % arm)
        print(json.dumps({"graph": scored["graph"], "refusal": scored["refusal"]},
                         indent=1, ensure_ascii=False))
    out = Path(args.out_dir) / "ROUTE2_LBENCH_SCORES_v1.json"
    out.write_text(json.dumps({
        "schema": "gis_recommend.route2.lbench.scores.v1",
        "benchmark": "qgis-planner-benchmark-v0.2.1",
        "scorer": "score_benchmark (verbatim import)",
        "results": results}, indent=1, ensure_ascii=False), encoding="utf-8")
    print("wrote", out)


def stage_lock(args):
    out = Path(args.out_dir)
    files = {}
    for arm in ARMS:
        for set_name in ("final_100", "refusal_12"):
            p = out / arm / ("%s_%s_predictions.jsonl" % (arm, set_name))
            files["%s/%s" % (arm, set_name)] = {
                "sha256": hashlib.sha256(p.read_bytes()).hexdigest(),
                "n_rows": sum(1 for l in p.read_text(encoding="utf-8").splitlines()
                              if l.strip())}
    config = {"base": BASE, "adapters": ARMS, "decoding": "greedy",
              "max_new_tokens": args.max_new_tokens, "prompt": "task_text + '\\nQGIS workflow:'",
              "parse": "route2_training.harness.text_to_graph first-line fail-closed",
              "refusal_policy": "always-plan arms: decision=generate with parsed graph"}
    lock = {"schema": "gis_recommend.route2.lbench.lock.v1",
            "inference": config, "predictions": files}
    dest = out / "ROUTE2_LBENCH_LOCK_v1.json"
    dest.write_text(json.dumps(lock, indent=1, ensure_ascii=False), encoding="utf-8")
    print("wrote", dest)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--stage", choices=["generate", "score", "lock"], required=True)
    ap.add_argument("--arm", choices=sorted(ARMS), required=False)
    ap.add_argument("--out-dir", default=str(REPO / "gate2_eval" / "lbench"))
    ap.add_argument("--max-new-tokens", type=int, default=512)
    args = ap.parse_args()
    if args.stage == "generate" and not args.arm:
        ap.error("--arm required for generate")
    if args.stage == "generate":
        from transformers import AutoTokenizer
        tok = AutoTokenizer.from_pretrained(BASE)
        if tok.pad_token is None:
            tok.pad_token = tok.eos_token
        tok.padding_side = "left"
        return stage_generate(args, tok)
    if args.stage == "lock":
        return stage_lock(args)
    return stage_score(args)


if __name__ == "__main__":
    raise SystemExit(main())
