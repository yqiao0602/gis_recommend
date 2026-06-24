#!/usr/bin/env python3
"""Smoke eval: SFT warmstart vs DPO v2 baseline on GEE preservation + QGIS vector signal.

Compares:
  1. GEE tasks (50 test samples): strict-vector token rate preservation
  2. QGIS vector seed tasks (50): absorption of QGIS training signal

Note on DPO baseline for QGIS tasks:
  DPO v2 uses a 47-task vocab that lacks "Vector Analysis", so QGIS seed tasks
  fall back to task_type_id=0 (Unknown) for the DPO baseline. Any observed positive
  SFT-DPO delta on QGIS tasks therefore includes both the new task-type embedding
  (id=47) and the SFT weight update — it is not a pure weight-tuning effect.

Usage (server):
    python scripts/evaluate_sft_vector_impact.py

Oversampled SFT example:
    python scripts/evaluate_sft_vector_impact.py \
        --sft-checkpoint outputs_v2/transformer_checkpoints_v4_6_quality_gate_qgis_vector_oversampled_warmstart/best_model.pth \
        --sft-task-vocab outputs_v2/pipeline/step8_quality_gate_qgis_vector_oversampled/task_type_vocabulary_v4_quality_gate_qgis_vector_oversampled.json \
        --sft-length-stats outputs_v2/pipeline/step8_quality_gate_qgis_vector_oversampled/task_type_length_stats.json \
        --report-path outputs_v2/diagnostics/sft_vector_impact_oversampled.json
"""

from __future__ import annotations
import argparse
import json, random, sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path: sys.path.insert(0, str(SRC))

import torch
from gis_recommend.inference.infer_l3_candidates_v4 import L3SequenceInferencerV4
from gis_recommend.config.transformer_config import DEVICE, V4_QG_TASK_TYPE_VOCAB_PATH

SFT_CKPT = ROOT / "outputs_v2/transformer_checkpoints_v4_6_quality_gate_qgis_vector/best_model.pth"
DPO_CKPT = ROOT / "outputs_v2/transformer_checkpoints_v4_6_preference_dpo_v2_quality_cycle_fixed/best_preference_model.pth"
GEE_TEST = ROOT / "outputs_v2/pipeline/step8_quality_gate/labeled_workflows_l3_v4_quality_gate.json"
GEE_SPLIT = ROOT / "outputs_v2/pipeline/step8_quality_gate/dataset_splits_v4_quality_gate.json"
VECTOR_TASKS = ROOT / "outputs_v2/canonical_vector_clean_sft_seed.jsonl"
VOCAB_48 = ROOT / "outputs_v2/pipeline/step8_quality_gate_qgis_vector/task_type_vocabulary_v4_quality_gate_qgis_vector.json"
SFT_LENGTH_STATS = ROOT / "outputs_v2/pipeline/step8_quality_gate_qgis_vector/task_type_length_stats.json"
DPO_LENGTH_STATS = ROOT / "outputs_v2/pipeline/step8_quality_gate/task_type_length_stats.json"
REPORT_PATH = ROOT / "outputs_v2/diagnostics/sft_vector_impact.json"

# Strict vector tokens (L1_02 hierarchy)
STRICT_VECTOR_L3 = {
    "L3_02_01_01","L3_02_02_01","L3_02_02_02","L3_02_02_04","L3_02_02_05","L3_02_02_06",
    "L3_02_03_05","L3_02_04_01","L3_02_05_04","L3_02_05_11","L3_02_05_12",
    "L3_02_06_01","L3_02_06_02","L3_02_06_03","L3_02_07_01",
}

def load_token_sets():
    with open(ROOT / "outputs_v2/id_mappings_v2.json", "r", encoding="utf-8") as f:
        idm = json.load(f)
    l3_to_token = {k: int(v) for k, v in idm.get("l3", {}).items()}
    strict_vec = {l3_to_token[c] for c in STRICT_VECTOR_L3 if c in l3_to_token}
    missing = [c for c in STRICT_VECTOR_L3 if c not in l3_to_token]
    if missing:
        print(f"  [INFO] {len(missing)} STRICT_VECTOR_L3 codes not in 94-L3 vocab: {sorted(missing)}")
    return l3_to_token, strict_vec

def build_inferencer(ckpt_path, vocab_path, length_stats_path, *, prompt_style="legacy"):
    return L3SequenceInferencerV4(
        checkpoint_path=ckpt_path,
        device=DEVICE,
        task_vocab_path=vocab_path,
        length_stats_path=length_stats_path,
        prompt_style=prompt_style,
    )

def require_path(path, label):
    if not Path(path).exists():
        raise FileNotFoundError(f"{label} not found: {path}")
    return Path(path)

def run_tasks(inferencer, tasks, task_type="Unknown"):
    results = []
    for t in tasks:
        desc = t.get("task_text","") or t.get("task_description","") or ""
        meta = t.get("task_metadata") or {}
        tt = meta.get("task_type_normalized", meta.get("task_type", task_type))
        cands = inferencer.infer(task_name="", task_description=str(desc)[:200], task_type=str(tt))
        pred = cands[0].tokens if cands else []
        pred_content = [tok for tok in pred if tok >= 0]
        results.append(pred_content)
    return results

def compute_rates(all_preds, strict_set):
    rates = []
    for pred in all_preds:
        n = len(pred)
        if n == 0:
            rates.append(0.0)
        else:
            rates.append(sum(1 for t in pred if t in strict_set) / n)
    return sum(rates)/max(len(rates),1), rates

def parse_args(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sft-checkpoint", type=Path, default=SFT_CKPT)
    parser.add_argument("--dpo-checkpoint", type=Path, default=DPO_CKPT)
    parser.add_argument("--gee-test", type=Path, default=GEE_TEST)
    parser.add_argument("--gee-split", type=Path, default=GEE_SPLIT)
    parser.add_argument("--vector-tasks", type=Path, default=VECTOR_TASKS)
    parser.add_argument("--sft-task-vocab", type=Path, default=VOCAB_48)
    parser.add_argument("--dpo-task-vocab", type=Path, default=V4_QG_TASK_TYPE_VOCAB_PATH)
    parser.add_argument("--sft-length-stats", type=Path, default=SFT_LENGTH_STATS)
    parser.add_argument("--dpo-length-stats", type=Path, default=DPO_LENGTH_STATS)
    parser.add_argument("--sft-prompt-style", choices=["legacy", "structured"], default="legacy")
    parser.add_argument("--dpo-prompt-style", choices=["legacy", "structured"], default="legacy")
    parser.add_argument("--report-path", type=Path, default=REPORT_PATH)
    return parser.parse_args(argv)

def main(argv=None):
    args = parse_args(argv)
    random.seed(42); torch.manual_seed(42)
    l3_to_token, strict_vec = load_token_sets()
    print(f"Strict vector tokens: {len(strict_vec)}")

    # Load GEE test
    with open(require_path(args.gee_test, "GEE test workflows"),"r",encoding="utf-8") as f:
        gee_all = json.load(f)["labeled_workflows"]
    with open(require_path(args.gee_split, "GEE split"),"r",encoding="utf-8") as f:
        gee_split = json.load(f)
    gee_tasks = [{"task_metadata": gee_all[i].get("task_metadata",{}),
                  "task_description": (gee_all[i].get("task_metadata",{}) or {}).get("task_description","")}
                 for i in gee_split["test_indices"][:50]]
    print(f"GEE tasks: {len(gee_tasks)}")

    # Load QGIS vector seed
    vec_tasks = []
    with open(require_path(args.vector_tasks, "QGIS vector seed tasks"),"r",encoding="utf-8") as f:
        for line in f:
            if line.strip(): vec_tasks.append(json.loads(line))
    vec_tasks = random.sample(vec_tasks, min(50, len(vec_tasks)))
    print(f"QGIS seed tasks: {len(vec_tasks)}")

    # Load both inferencers. Keep paths explicit to avoid silently mixing
    # 48-task SFT checkpoints with 47-task quality-gate length priors.
    vocab_sft = require_path(args.sft_task_vocab, "48-task SFT vocab")
    vocab_dpo = require_path(args.dpo_task_vocab, "47-task DPO vocab")
    sft_ckpt = require_path(args.sft_checkpoint, "SFT checkpoint")
    dpo_ckpt = require_path(args.dpo_checkpoint, "DPO checkpoint")
    sft_length_stats = require_path(args.sft_length_stats, "48-task SFT length stats")
    dpo_length_stats = require_path(args.dpo_length_stats, "47-task DPO length stats")
    print(f"\nLoading SFT model ({sft_ckpt}) ...")
    inf_sft = build_inferencer(
        sft_ckpt,
        vocab_sft,
        sft_length_stats,
        prompt_style=args.sft_prompt_style,
    )
    print(f"Loading DPO v2 model ({dpo_ckpt}) ...")
    inf_dpo = build_inferencer(
        dpo_ckpt,
        vocab_dpo,
        dpo_length_stats,
        prompt_style=args.dpo_prompt_style,
    )

    # Run
    print("\nRunning GEE tasks ...")
    sft_gee = run_tasks(inf_sft, gee_tasks)
    dpo_gee = run_tasks(inf_dpo, gee_tasks)

    print("Running QGIS seed tasks ...")
    sft_vec = run_tasks(inf_sft, vec_tasks, "Vector Analysis")
    dpo_vec = run_tasks(inf_dpo, vec_tasks, "Vector Analysis")

    # Compute
    sft_gee_rate, _ = compute_rates(sft_gee, strict_vec)
    dpo_gee_rate, _ = compute_rates(dpo_gee, strict_vec)
    sft_vec_rate, _ = compute_rates(sft_vec, strict_vec)
    dpo_vec_rate, _ = compute_rates(dpo_vec, strict_vec)

    sft_gee_len = sum(len(p) for p in sft_gee)/max(len(sft_gee),1)
    dpo_gee_len = sum(len(p) for p in dpo_gee)/max(len(dpo_gee),1)
    sft_vec_len = sum(len(p) for p in sft_vec)/max(len(sft_vec),1)
    dpo_vec_len = sum(len(p) for p in dpo_vec)/max(len(dpo_vec),1)

    print(f"\n{'='*70}")
    print(f"{'Task set':20s} {'Model':12s} {'Strict vector rate':>18s} {'Avg len':>10s}")
    print(f"{'='*70}")
    print(f"{'GEE test':20s} {'DPO v2':12s} {dpo_gee_rate*100:>17.1f}% {dpo_gee_len:>10.1f}")
    print(f"{'GEE test':20s} {'SFT':12s} {sft_gee_rate*100:>17.1f}% {sft_gee_len:>10.1f}")
    print(f"{'QGIS seed':20s} {'DPO v2':12s} {dpo_vec_rate*100:>17.1f}% {dpo_vec_len:>10.1f}")
    print(f"{'QGIS seed':20s} {'SFT':12s} {sft_vec_rate*100:>17.1f}% {sft_vec_len:>10.1f}")

    delta_vec = sft_vec_rate - dpo_vec_rate
    delta_gee = sft_gee_rate - dpo_gee_rate
    print(f"\nSFT - DPO delta:")
    print(f"  GEE:    {delta_gee*100:+.1f}pp  (want ~0, preservation)")
    print(f"  QGIS:   {delta_vec*100:+.1f}pp  (want >0, signal absorption)")

    # Save
    out = args.report_path
    out.parent.mkdir(parents=True, exist_ok=True)
    json.dump({
        "paths": {
            "gee_test": str(args.gee_test),
            "gee_split": str(args.gee_split),
            "vector_tasks": str(args.vector_tasks),
            "sft_checkpoint": str(sft_ckpt),
            "dpo_checkpoint": str(dpo_ckpt),
            "sft_task_vocab": str(vocab_sft),
            "dpo_task_vocab": str(vocab_dpo),
            "sft_length_stats": str(sft_length_stats),
            "dpo_length_stats": str(dpo_length_stats),
            "sft_prompt_style": args.sft_prompt_style,
            "dpo_prompt_style": args.dpo_prompt_style,
        },
        "gee": {"sft_rate": sft_gee_rate, "dpo_rate": dpo_gee_rate, "delta": delta_gee, "n": len(gee_tasks)},
        "qgis_seed": {"sft_rate": sft_vec_rate, "dpo_rate": dpo_vec_rate, "delta": delta_vec, "n": len(vec_tasks)},
    }, open(out,"w"), indent=2, ensure_ascii=False)
    print(f"\nReport: {out}")

if __name__ == "__main__":
    main()
