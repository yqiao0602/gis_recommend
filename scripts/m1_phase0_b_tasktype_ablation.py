#!/usr/bin/env python3
"""Phase 0 pre-check B: task_type oracle-vs-Unknown 2x2 ablation (49-row val).

Question: how much of M1-R1's benchmark-side collapse is attributable to the
task_type="Unknown" inference condition (task_type_id embedding + structured
prompt text) versus the expected-length policy, measured on the SAME val rows
that the Sep-9 diagnostic evaluated under Oracle conditions?

Design: 2x2 on the same 49 val rows, same epoch-18 best_gen_composite
checkpoint (SHA-bound to INFERENCE_CONFIG_FREEZE_v1.json), same diverse beam
search, same scorer. The only varying inputs are the task_type string fed to
the model and the expected_length policy:

  oracle_len_type  : task_type = real per-row type; expected_length =
                     per-type mean (capped 15)   [Sep-9 dev-eval replica]
  unknown_len_type : task_type = "Unknown"; expected_length = per-type mean
                     [isolates the task_type model input]
  oracle_len_8     : task_type = real; expected_length = 8, eos_suppress = 2
  unknown_len_8    : task_type = "Unknown"; expected_length = 8,
                     eos_suppress = 2            [frozen benchmark protocol]

task_type enters the model through exactly two channels here: the
task_type_id embedding (FiLM conditioning) and the structured prompt text
("Task type: ..."). The paper_v1 length stats are flat per-type means, so
set_expected_length's by_task_type lookup is empty and the dynamic-median
prior never fires; expected_length is set explicitly per condition.

No retraining, no checkpoint selection, no benchmark-lock change, no
modification of the Sep-9 artifacts. Run on the compute server.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

import torch

from transformers import BertTokenizer  # noqa: F401  (server BertTokenizer caches)

PROJECT_ROOT = Path("/home/qy/system_redesign")
sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

# INFERENCE_CONFIG_FREEZE_v1.json → m1.checkpoint_sha256 (2026-09-11 lock)
FROZEN_CKPT_SHA256 = "97e61fd448d3369f3ef36ce800cffe267a69511a2b418910b9a31a90479d1bea"
# Sep-9 oracle-leg anchor (m1_r1_eval/m1_r1_dev_eval_metrics_v1.json)
SEP9_ANCHOR = {"code_precision": 0.1532, "code_recall": 0.1978,
               "mean_length_error": 1.04, "tolerance": 0.03}
DEFINE_PROJECTION = "L3_01_10_02"

CONDITIONS = ("oracle_len_type", "unknown_len_type", "oracle_len_8", "unknown_len_8")


def prf(pred, gold):
    p, g = Counter(pred), Counter(gold)
    inter = sum((p & g).values())
    return inter / max(sum(p.values()), 1), inter / max(sum(g.values()), 1)


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def derive_task_type(row: dict) -> str:
    """Same signal the trainer saw (mirrors m1_r1_dev_eval.py)."""
    if row["platform"] == "gee":
        return "GEE_COMPLETE_OUTPUT_WORKFLOW"
    rid = row["record_id"]
    for tt in ("qgis_api_pattern_v2", "qgis_api_standalone_v2", "qgis_audited_existing_506"):
        if tt.split("_v")[0] in rid:
            return tt
    return "qgis_audited_existing_506"


def run_condition(inferencer, rows, token_to_code, valid_codes, mean_len, cond):
    tt_mode, len_mode = cond.split("_len_")
    per_row = []
    for r in rows:
        real_tt = derive_task_type(r)
        model_tt = real_tt if tt_mode == "oracle" else "Unknown"
        if len_mode == "type":
            el = min(mean_len.get(real_tt, 8), 15)
            eos_sup = max(1, int(el * 0.3))
        else:  # fixed8 — mirrors the frozen benchmark protocol
            el, eos_sup = 8, 2
        inferencer.expected_length = el
        inferencer.eos_suppress_until = eos_sup

        candidates = inferencer.infer(task_name="", task_description=r["task_text"],
                                      task_type=model_tt)
        cand = candidates[0] if candidates else None
        pred_codes = [token_to_code.get(t, f"UNK{t}") for t in (cand.tokens if cand else [])]
        gold_codes = [c.strip() for c in r["l3_chain_text"].split("->")]

        p, rec = prf(pred_codes, gold_codes)
        f1 = 2 * p * rec / (p + rec) if (p + rec) > 0 else 0.0
        is_exact = pred_codes == gold_codes
        terminated = bool(cand.is_complete) if cand else False
        illegal = sorted({c for c in pred_codes if c not in valid_codes})

        reason = ""
        if not is_exact:
            if len(pred_codes) == 0:
                reason = "empty_prediction"
            elif not terminated:
                reason = "nontermination_no_end"
            elif illegal:
                reason = "illegal_l3_token"
            elif Counter(pred_codes) == Counter(gold_codes):
                reason = "order_only"
            elif set(pred_codes) & set(gold_codes):
                reason = "partial_overlap"
            else:
                reason = "wrong_family"

        per_row.append({
            "record_id": r["record_id"],
            "platform": r["platform"],
            "task_type_real": real_tt,
            "task_type_fed": model_tt,
            "expected_length": el,
            "gold_l3_chain": gold_codes,
            "pred_l3_chain": pred_codes,
            "first_token": pred_codes[0] if pred_codes else None,
            "exact_match": bool(is_exact),
            "code_precision": round(p, 4),
            "code_recall": round(rec, 4),
            "set_f1": round(f1, 4),
            "length_error": len(pred_codes) - len(gold_codes),
            "illegal_l3": illegal,
            "eos_terminated": terminated,
            "failure_reason": reason,
        })

    n = len(per_row)
    first_tokens = Counter(r["first_token"] for r in per_row if r["first_token"])
    pred_lens = [len(r["pred_l3_chain"]) for r in per_row]
    by_platform = {}
    for plat in ("gee", "qgis"):
        sub = [r for r in per_row if r["platform"] == plat]
        by_platform[plat] = {
            "n": len(sub),
            "exact": sum(r["exact_match"] for r in sub),
            "mean_precision": round(sum(r["code_precision"] for r in sub) / max(len(sub), 1), 4),
            "mean_recall": round(sum(r["code_recall"] for r in sub) / max(len(sub), 1), 4),
            "empty": sum(1 for r in sub if not r["pred_l3_chain"]),
        }
    metrics = {
        "condition": cond,
        "task_type_mode": tt_mode,
        "length_mode": len_mode,
        "n": n,
        "exact_chain": sum(r["exact_match"] for r in per_row),
        "exact_chain_rate": round(sum(r["exact_match"] for r in per_row) / n, 4),
        "mean_code_precision": round(sum(r["code_precision"] for r in per_row) / n, 4),
        "mean_code_recall": round(sum(r["code_recall"] for r in per_row) / n, 4),
        "mean_set_f1": round(sum(r["set_f1"] for r in per_row) / n, 4),
        "empty_predictions": sum(1 for r in per_row if not r["pred_l3_chain"]),
        "empty_rate": round(sum(1 for r in per_row if not r["pred_l3_chain"]) / n, 4),
        "eos_terminated": f"{sum(r['eos_terminated'] for r in per_row)}/{n}",
        "mean_pred_length": round(statistics.fmean(pred_lens), 2) if pred_lens else 0,
        "median_pred_length": statistics.median(pred_lens) if pred_lens else 0,
        "mean_length_error": round(sum(r["length_error"] for r in per_row) / n, 2),
        "invalid_l3_token_rows": sum(1 for r in per_row if r["illegal_l3"]),
        "first_token_top": first_tokens.most_common(10),
        "first_token_define_projection_share": round(
            first_tokens.get(DEFINE_PROJECTION, 0) / n, 4),
        "first_token_distinct": len(first_tokens),
        "failure_reasons": dict(Counter(r["failure_reason"] for r in per_row if r["failure_reason"]).most_common()),
        "by_platform": by_platform,
    }
    return per_row, metrics


def build_and_write_summary(all_metrics, ckpt_sha, out_dir, minutes, peak_memory_gb):
    """Build contrasts + summary from the four condition metrics and write summary.json.

    (v1 crashed here on wrong metric keys — "code_precision" vs
    "mean_code_precision" — after all four conditions had already been
    written; --aggregate-only rebuilds from those artifacts.)
    """
    anchor = all_metrics["oracle_len_type"]
    anchor_check = {
        "anchor": SEP9_ANCHOR,
        "observed": {k: anchor[k] for k in ("mean_code_precision", "mean_code_recall",
                                            "mean_length_error")},
        "precision_ok": abs(anchor["mean_code_precision"] - SEP9_ANCHOR["code_precision"]) <= SEP9_ANCHOR["tolerance"],
        "recall_ok": abs(anchor["mean_code_recall"] - SEP9_ANCHOR["code_recall"]) <= SEP9_ANCHOR["tolerance"],
    }

    def contrast(a, b, label):
        ma, mb = all_metrics[a], all_metrics[b]
        return {
            "contrast": f"{a} vs {b}", "meaning": label,
            "delta_exact_rate": round(mb["exact_chain_rate"] - ma["exact_chain_rate"], 4),
            "delta_precision": round(mb["mean_code_precision"] - ma["mean_code_precision"], 4),
            "delta_recall": round(mb["mean_code_recall"] - ma["mean_code_recall"], 4),
            "delta_set_f1": round(mb["mean_set_f1"] - ma["mean_set_f1"], 4),
            "delta_empty_rate": round(mb["empty_rate"] - ma["empty_rate"], 4),
            "delta_define_projection_share": round(
                mb["first_token_define_projection_share"] - ma["first_token_define_projection_share"], 4),
            "delta_mean_pred_length": round(mb["mean_pred_length"] - ma["mean_pred_length"], 2),
        }

    contrasts = [
        contrast("oracle_len_type", "unknown_len_type",
                 "task_type model-input effect (per-type length policy held constant)"),
        contrast("oracle_len_8", "unknown_len_8",
                 "task_type model-input effect (fixed length 8 held constant)"),
        contrast("unknown_len_type", "unknown_len_8",
                 "length-policy effect under task_type=Unknown"),
        contrast("oracle_len_type", "oracle_len_8",
                 "length-policy effect under task_type=Oracle"),
    ]

    summary = {
        "schema": "gis_recommend.m1_phase0_b_tasktype_ablation.v1",
        "question": ("task_type OOD contribution to M1-R1 collapse, isolated on the "
                     "49-row val set: oracle vs Unknown task_type x per-type vs fixed-8 length"),
        "checkpoint_sha256": ckpt_sha,
        "conditions": {c: all_metrics[c] for c in CONDITIONS},
        "contrasts": contrasts,
        "sep9_anchor_reproduction": anchor_check,
        "notes": [
            "task_type reaches the model via task_type_id embedding + structured prompt "
            "text only; per-task-type dynamic median lengths do not exist in the paper_v1 "
            "profile (flat means only, set explicitly per condition).",
            "unknown_len_8 replicates the frozen benchmark inference protocol "
            "(INFERENCE_CONFIG_FREEZE_v1.json m1 block) on val rows.",
            "benchmark empty graphs (88/100) additionally include bridge drops; the "
            "empty_rate here is token-level (no bridge involved).",
        ],
        "minutes": minutes,
        "peak_memory_gb": peak_memory_gb,
    }
    (out_dir / "summary.json").write_text(json.dumps(summary, indent=2, ensure_ascii=False),
                                          encoding="utf-8")
    print("\n[SUMMARY] contrasts:")
    for c in contrasts:
        print(json.dumps(c, ensure_ascii=False))
    print(f"\nwrote {out_dir / 'summary.json'}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", type=Path, required=True)
    ap.add_argument("--val", type=Path, default=Path("/home/qy/gee_llm_smoke/m3_p0_val_49.jsonl"))
    ap.add_argument("--id-mappings", type=Path,
                    default=PROJECT_ROOT / "docs/reports/paper_v1_profile_v1/id_mappings_paper_v1_128.json")
    ap.add_argument("--task-vocab", type=Path,
                    default=Path("/home/qy/gee_llm_smoke/m1_task_vocab_v1.json"))
    ap.add_argument("--length-stats", type=Path,
                    default=PROJECT_ROOT / "docs/reports/paper_v1_profile_v1/task_type_length_stats_paper_v1.json")
    ap.add_argument("--taxonomy", type=Path,
                    default=Path("/home/qy/gee_llm_smoke/taxonomy_128_v1.json"))
    ap.add_argument("--out-dir", type=Path, default=Path("/home/qy/gee_llm_smoke/m1_phase0_b"))
    ap.add_argument("--max-length", type=int, default=40)
    ap.add_argument("--aggregate-only", action="store_true",
                    help="rebuild summary.json from existing gate.json and "
                         "conditions/*.metrics.json without running inference")
    args = ap.parse_args()

    import os
    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "conditions").mkdir(exist_ok=True)
    t0 = time.time()

    if args.aggregate_only:
        gate = json.loads((args.out_dir / "gate.json").read_text(encoding="utf-8"))
        ckpt_sha = gate["checkpoint_sha256"]
        all_metrics = {
            cond: json.loads(
                (args.out_dir / "conditions" / f"{cond}.metrics.json").read_text(encoding="utf-8"))
            for cond in CONDITIONS
        }
        print(f"[AGGREGATE] rebuilt {len(all_metrics)} conditions from {args.out_dir}")
        build_and_write_summary(all_metrics, ckpt_sha, args.out_dir,
                                minutes=round((time.time() - t0) / 60, 1),
                                peak_memory_gb=None)
        return 0

    assert os.environ.get("GIS_VOCAB_PROFILE") == "paper_v1_128", \
        "must run with GIS_VOCAB_PROFILE=paper_v1_128"
    runtime_dir = Path("/home/qy/gee_llm_smoke/m1_r1_profile_runtime")
    os.environ.setdefault("GIS_OUTPUTS_DIR", str(runtime_dir))
    os.environ.setdefault("GIS_ID_MAPPINGS", str(runtime_dir / "id_mappings_v2.json"))
    from gis_recommend.config import transformer_config as cfg  # noqa: F401

    # ── checkpoint SHA binding to the frozen inference config ──
    ckpt_sha = sha256_of(args.checkpoint)
    assert ckpt_sha == FROZEN_CKPT_SHA256, (
        f"checkpoint SHA {ckpt_sha} != frozen INFERENCE_CONFIG_FREEZE "
        f"{FROZEN_CKPT_SHA256} — refusing to run on a non-locked checkpoint")

    rows = [json.loads(l) for l in args.val.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(rows) == 49, f"expected 49 val rows, got {len(rows)}"

    id_mappings = json.loads(args.id_mappings.read_text(encoding="utf-8"))
    code_to_token = {k: int(v) for k, v in id_mappings["l3"].items()}
    token_to_code = {v: k for k, v in code_to_token.items()}
    valid_codes = set(code_to_token)
    taxonomy_codes = {c["l3_code"] for c in json.loads(args.taxonomy.read_text(encoding="utf-8"))["classes"]}
    assert valid_codes == taxonomy_codes, "id mappings vs taxonomy mismatch"

    task_vocab = json.loads(args.task_vocab.read_text(encoding="utf-8"))
    task_type_to_id = task_vocab["task_type_to_id"]
    length_stats = json.loads(args.length_stats.read_text(encoding="utf-8"))
    mean_len = {t: int(round(v["mean"])) for t, v in length_stats.items()
                if isinstance(v, dict) and "mean" in v}

    from gis_recommend.inference.infer_l3_candidates_v4 import L3SequenceInferencerV4
    inferencer = L3SequenceInferencerV4(
        checkpoint_path=args.checkpoint,
        device=torch.device("cuda:0"),
        task_vocab_path=args.task_vocab,
        length_stats_path=args.length_stats,
        max_length=args.max_length,
        min_length=1,
        set_predictor_path=None,
        max_text_length=256,  # matches the trainer's max_text_length
    )
    inferencer.set_prior_mode = "off"
    inferencer.prompt_style = "structured"

    # ── Stage 0: reload gate (mirrors m1_r1_dev_eval) ──
    gate = {
        "checkpoint": str(args.checkpoint),
        "checkpoint_sha256": ckpt_sha,
        "frozen_sha256": FROZEN_CKPT_SHA256,
        "vocab_profile": os.environ["GIS_VOCAB_PROFILE"],
        "model_vocab_size": cfg.TOTAL_VOCAB_SIZE,
        "content_vocab_size": len(code_to_token),
        "n_id_to_l3": len(inferencer.id_to_l3_code),
        "transition_states": len(inferencer.allowed_next),
        "task_types": len(task_type_to_id),
        "val_rows": len(rows),
        "length_policy_means": mean_len,
    }
    assert gate["n_id_to_l3"] == 128, \
        f"inferencer id_to_l3 has {gate['n_id_to_l3']} entries, expected 128"
    assert gate["transition_states"] == 79, \
        f"transition matrix has {gate['transition_states']} states, expected 79 (paper_v1)"

    raw_ckpt = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
    gate["ckpt_epoch"] = raw_ckpt.get("epoch")
    del raw_ckpt
    n_params = sum(p.numel() for p in inferencer.model.parameters())
    gate["params_m"] = round(n_params / 1e6, 1)

    det_input = inferencer._prepare_input(rows[0]["task_text"][:60], rows[0]["task_text"], "Unknown")
    run_a = inferencer.infer_from_model_input(det_input, mode="beam")
    run_b = inferencer.infer_from_model_input(det_input, mode="beam")
    gate["deterministic_beam"] = [c.tokens for c in run_a] == [c.tokens for c in run_b]
    assert gate["deterministic_beam"], "beam search is not deterministic"

    (args.out_dir / "gate.json").write_text(json.dumps(gate, indent=2, ensure_ascii=False),
                                            encoding="utf-8")
    print("[STAGE 0] reload gate:")
    print(json.dumps(gate, indent=2, ensure_ascii=False))

    # ── Stage 1: 2x2 conditions ──
    all_metrics = {}
    for cond in CONDITIONS:
        print(f"\n[COND] {cond}")
        per_row, metrics = run_condition(inferencer, rows, token_to_code,
                                         valid_codes, mean_len, cond)
        (args.out_dir / "conditions" / f"{cond}.rows.jsonl").write_text(
            "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in per_row),
            encoding="utf-8")
        (args.out_dir / "conditions" / f"{cond}.metrics.json").write_text(
            json.dumps(metrics, indent=2, ensure_ascii=False), encoding="utf-8")
        all_metrics[cond] = metrics
        print(json.dumps({k: metrics[k] for k in (
            "exact_chain", "mean_code_precision", "mean_code_recall", "mean_set_f1",
            "empty_predictions", "mean_pred_length", "mean_length_error",
            "first_token_define_projection_share", "first_token_distinct")}, indent=2))

    build_and_write_summary(
        all_metrics, ckpt_sha, args.out_dir,
        minutes=round((time.time() - t0) / 60, 1),
        peak_memory_gb=round(torch.cuda.max_memory_allocated() / 2**30, 2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
