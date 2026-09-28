#!/usr/bin/env python3
"""M1-R1 development evaluation: 49-row frozen val set, unified metric contract.

Protocol (frozen, mirrors M3-P1-EOS-R1 exactly on the metric side):
  checkpoint (epoch-18 best_gen_* per selection manifest, unchanged rule)
    → V4.6 formal inference path: L3SequenceInferencerV4 diverse beam search
      + length constraint + transition constraint (+ no set predictor: not
      trained in this run)
    → top-1 candidate L3 token chain → L3 codes
    → unified evaluator: exact chain, code P/R, length error, order error,
      illegal L3, EOS termination status — per-row and aggregate, by platform.

Same 49 rows, same record_ids, same gold chains as m3_p0_val_49.jsonl.
The training-time greedy AR diagnostics (SetF1=0.181 etc.) are NOT used here.

Stage 0 (checkpoint reload gate):
  - schema check, strict state_dict load, vocab profile check (132 model vocab
    = 128 content + 4 special), determinism (two runs identical), no training.
"""

from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from pathlib import Path

import torch

from transformers import BertTokenizer  # noqa: F401  (server BertTokenizer caches)

PROJECT_ROOT = Path("/home/qy/system_redesign")
import sys

sys.path.insert(0, str(PROJECT_ROOT))
sys.path.insert(0, str(PROJECT_ROOT / "src"))

CODE_RE_JOKER = None  # tokens are ids; codes come from id mappings


def prf(pred, gold):
    p, g = Counter(pred), Counter(gold)
    inter = sum((p & g).values())
    return inter / max(sum(p.values()), 1), inter / max(sum(g.values()), 1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--checkpoint", type=Path, required=True)
    ap.add_argument("--val", type=Path, default=Path("/home/qy/gee_llm_smoke/m3_p0_val_49.jsonl"))
    ap.add_argument("--id-mappings", type=Path,
                    default=PROJECT_ROOT / "docs/reports/paper_v1_profile_v1/id_mappings_paper_v1_128.json")
    ap.add_argument("--task-vocab", type=Path,
                    default=Path("/home/qy/gee_llm_smoke/m1_task_vocab_v1.json"))
    ap.add_argument("--transition", type=Path,
                    default=PROJECT_ROOT / "docs/reports/paper_v1_profile_v1/transition_allowed_next_paper_v1.json")
    ap.add_argument("--length-stats", type=Path,
                    default=PROJECT_ROOT / "docs/reports/paper_v1_profile_v1/task_type_length_stats_paper_v1.json")
    ap.add_argument("--taxonomy", type=Path,
                    default=PROJECT_ROOT / "docs/reports/qgis_taxonomy_128_authority_v1/taxonomy_128_v1.json")
    ap.add_argument("--out-dir", type=Path, default=Path("/home/qy/gee_llm_smoke/m1_r1_eval"))
    ap.add_argument("--checkpoint-name", default="epoch18_best_gen_composite")
    ap.add_argument("--max-length", type=int, default=40,
                    help="beam max_length; mirrors ar_max_steps=40 of the frozen protocol")
    args = ap.parse_args()

    import os
    assert os.environ.get("GIS_VOCAB_PROFILE") == "paper_v1_128", \
        "must run with GIS_VOCAB_PROFILE=paper_v1_128"
    # The inferencer reads ID_MAPPINGS_PATH / transition matrix from config's
    # OUTPUT_DIR. Point both at the paper_v1 profile runtime dir so the legacy
    # 94/107-token assets in outputs_v2 can never leak into this evaluation.
    runtime_dir = Path("/home/qy/gee_llm_smoke/m1_r1_profile_runtime")
    os.environ.setdefault("GIS_OUTPUTS_DIR", str(runtime_dir))
    os.environ.setdefault("GIS_ID_MAPPINGS", str(runtime_dir / "id_mappings_v2.json"))
    from gis_recommend.config import transformer_config as cfg  # noqa: F401

    args.out_dir.mkdir(parents=True, exist_ok=True)
    t0 = time.time()

    # ── gold rows (identical file to M3) ──
    rows = [json.loads(l) for l in args.val.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(rows) == 49

    # ── token maps ──
    id_mappings = json.loads(args.id_mappings.read_text(encoding="utf-8"))
    code_to_token = {k: int(v) for k, v in id_mappings["l3"].items()}
    token_to_code = {v: k for k, v in code_to_token.items()}
    valid_codes = set(code_to_token)
    taxonomy_codes = {c["l3_code"] for c in json.loads(args.taxonomy.read_text(encoding="utf-8"))["classes"]}
    assert valid_codes == taxonomy_codes, "id mappings vs taxonomy mismatch"

    task_vocab = json.loads(args.task_vocab.read_text(encoding="utf-8"))
    task_type_to_id = task_vocab["task_type_to_id"]

    length_stats = json.loads(args.length_stats.read_text(encoding="utf-8"))
    mean_len = {t: int(round(v["mean"])) for t, v in length_stats.items()}

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
    # The paper_v1 profile stats are flat {type: {mean}} (no by_task_type/median),
    # so the bucket predictor falls back to medium for everything; the trainer
    # consumed the same flat stats. Use per-task-type mean directly.
    inferencer.set_prior_mode = "off"

    # ── Stage 0: reload gate ──
    gate = {}
    gate["checkpoint"] = str(args.checkpoint)
    gate["checkpoint_name"] = args.checkpoint_name
    gate["checkpoint_schema"] = "checked in _load_model (strict=True, raises on mismatch)"
    gate["vocab_profile"] = os.environ["GIS_VOCAB_PROFILE"]
    gate["model_vocab_size"] = cfg.TOTAL_VOCAB_SIZE
    gate["content_vocab_size"] = len(code_to_token)
    gate["n_id_to_l3"] = len(inferencer.id_to_l3_code)
    assert gate["n_id_to_l3"] == 128, \
        f"inferencer id_to_l3 has {gate['n_id_to_l3']} entries, expected 128 — " \
        "legacy id_mappings leaked in (check GIS_ID_MAPPINGS / GIS_OUTPUTS_DIR)"
    gate["transition_states"] = len(inferencer.allowed_next)
    assert gate["transition_states"] == 79, \
        f"transition matrix has {gate['transition_states']} states, expected 79 (paper_v1)"
    gate["task_types"] = len(task_type_to_id)

    raw_ckpt = torch.load(args.checkpoint, map_location="cpu", weights_only=False)
    gate["ckpt_epoch"] = raw_ckpt.get("epoch")
    gate["has_task_classifier"] = "task_classifier_state_dict" in raw_ckpt
    mc = raw_ckpt.get("model_config") or {}
    gate["model_config_vocab"] = mc.get("vocab_size")
    n_params = sum(p.numel() for p in inferencer.model.parameters())
    gate["params_m"] = round(n_params / 1e6, 1)
    del raw_ckpt

    # determinism: same input twice → identical candidate tokens
    det_input = inferencer._prepare_input(
        rows[0]["task_text"][:60], rows[0]["task_text"], "Unknown")
    run_a = inferencer.infer_from_model_input(det_input, mode="beam")
    run_b = inferencer.infer_from_model_input(det_input, mode="beam")
    det_ok = ([c.tokens for c in run_a] == [c.tokens for c in run_b])
    gate["deterministic_beam"] = det_ok
    gate["determinism_check_top1"] = [token_to_code.get(t, t) for t in run_a[0].tokens] if run_a else []

    (args.out_dir / "reload_gate.json").write_text(
        json.dumps(gate, indent=2, ensure_ascii=False), encoding="utf-8")
    print("[STAGE 0] reload gate:")
    print(json.dumps(gate, indent=2, ensure_ascii=False))

    # ── Stage 1: 49-row evaluation ──
    # The trainer encoded text as build_task_prompt(task_type, task_name,
    # task_description) — 'Task type: ...\nTask name: ...\nGoal: ...'. The
    # inferencer's structured prompt_style produces exactly this. Use it so
    # the eval input distribution matches training (a bare task_text would
    # systematically shift the eval, not measure the model).
    inferencer.prompt_style = "structured"
    per_row = []
    exact = 0
    lenient = 0
    pr_sum = rec_sum = 0.0
    len_err = 0
    order_err = 0
    illegal_rows = 0
    eos_term = 0
    by_platform = {}
    failure_reasons = Counter()

    for idx, r in enumerate(rows):
        task_text = r["task_text"]
        # task_type from the val workflow's own metadata (same signal the
        # trainer saw); map to the trained task_type_id
        platform = r["platform"]
        task_type = ("GEE_COMPLETE_OUTPUT_WORKFLOW" if platform == "gee"
                     else None)
        if task_type is None:
            # QGIS: recover task type from record_id provenance tag
            rid = r["record_id"]
            for tt in ("qgis_api_pattern_v2", "qgis_api_standalone_v2", "qgis_audited_existing_506"):
                if tt.split("_v")[0] in rid:
                    task_type = tt
                    break
            task_type = task_type or "qgis_audited_existing_506"

        # mirror trainer's per-task-type expected length (mean, capped 15)
        inferencer.expected_length = min(mean_len.get(task_type, 8), 15)
        inferencer.eos_suppress_until = max(1, int(inferencer.expected_length * 0.3))

        candidates = inferencer.infer(task_name="", task_description=task_text, task_type=task_type)
        cand = candidates[0] if candidates else None
        pred_tokens = list(cand.tokens) if cand else []
        pred_codes = [token_to_code.get(t, f"UNK{t}") for t in pred_tokens]

        gold_codes = [c.strip() for c in r["l3_chain_text"].split("->")]

        p, rec = prf(pred_codes, gold_codes)
        pr_sum += p
        rec_sum += rec
        len_err_row = len(pred_codes) - len(gold_codes)
        len_err += len_err_row
        is_exact = pred_codes == gold_codes
        is_lenient = [c.replace(" ", "") for c in pred_codes] == [c.replace(" ", "") for c in gold_codes]
        exact += is_exact
        lenient += is_lenient

        # order error: multiset correct but sequence differs (M3 definition)
        order_row = 0
        if Counter(pred_codes) == Counter(gold_codes) and pred_codes != gold_codes and pred_codes:
            order_err += 1
            order_row = 1

        illegal = sorted({c for c in pred_codes if c not in valid_codes})
        if illegal:
            illegal_rows += 1

        terminated = bool(cand.is_complete) if cand else False
        eos_term += terminated

        if not is_exact:
            if not terminated:
                failure_reasons["nontermination_no_end"] += 1
            elif len(pred_codes) == 0:
                failure_reasons["empty_prediction"] += 1
            elif illegal:
                failure_reasons["illegal_l3_token"] += 1
            elif Counter(pred_codes) == Counter(gold_codes):
                failure_reasons["order_only"] += 1
            elif set(pred_codes) & set(gold_codes):
                failure_reasons["partial_overlap"] += 1
            else:
                failure_reasons["wrong_family"] += 1

        row_rec = {
            "record_id": r["record_id"],
            "task_text": task_text,
            "platform": platform,
            "task_type": task_type,
            "gold_l3_chain": gold_codes,
            "pred_l3_chain": pred_codes,
            "pred_tokens": pred_tokens,
            "exact_match": bool(is_exact),
            "lenient_exact": bool(is_lenient),
            "code_precision": round(p, 4),
            "code_recall": round(rec, 4),
            "length_error": len_err_row,
            "order_error": order_row,
            "illegal_l3": illegal,
            "eos_terminated": terminated,
            "termination_reason": ("END" if terminated else
                                   ("max_steps" if pred_tokens else "empty")),
            "beam_score": round(cand.final_score, 4) if cand else None,
            "n_candidates": len(candidates),
        }
        per_row.append(row_rec)
        print(f"[{idx+1:2d}/49] {'OK ' if is_exact else 'FAIL'} {r['record_id'][:44]} "
              f"p={p:.2f} r={rec:.2f} lenErr={len_err_row:+d} eos={terminated} "
              f"| {len(pred_codes)} tokens")

    n = len(rows)
    platform_agg = {}
    for plat in ("gee", "qgis"):
        sub = [r for r in per_row if r["platform"] == plat]
        platform_agg[plat] = {
            "n": len(sub),
            "exact": sum(r["exact_match"] for r in sub),
            "mean_len_err": round(sum(r["length_error"] for r in sub) / max(len(sub), 1), 2),
            "mean_precision": round(sum(r["code_precision"] for r in sub) / max(len(sub), 1), 4),
            "mean_recall": round(sum(r["code_recall"] for r in sub) / max(len(sub), 1), 4),
        }

    metrics = {
        "n": n,
        "checkpoint": args.checkpoint_name,
        "exact_chain": exact,
        "exact_chain_rate": round(exact / n, 4),
        "lenient_exact": lenient,
        "code_precision": round(pr_sum / n, 4),
        "code_recall": round(rec_sum / n, 4),
        "mean_length_error": round(len_err / n, 2),
        "order_errors_multiset_correct": order_err,
        "invalid_l3_token_rows": illegal_rows,
        "eos_terminated": f"{eos_term}/{n}",
        "by_platform": platform_agg,
        "failure_reasons": dict(failure_reasons.most_common()),
    }

    out = {
        "schema": "gis_recommend.m1_r1_dev_eval.v1",
        "route": "M1",
        "run": "M1-R1",
        "inference": "V4.6 diverse beam search + transition/length constraints (top-1 candidate)",
        "eval_set": str(args.val),
        "n_val_rows": n,
        "protocol": {
            "max_length": args.max_length,
            "mode": "beam",
            "set_predictor": "off (not trained in this run)",
            "expected_length": "per-task-type mean from task_type_length_stats_paper_v1.json, capped 15",
        },
        "metrics": metrics,
        "minutes": round((time.time() - t0) / 60, 1),
        "peak_memory_gb": round(torch.cuda.max_memory_allocated() / 2**30, 2),
    }
    (args.out_dir / "m1_r1_dev_eval_metrics_v1.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    (args.out_dir / "m1_r1_dev_eval_rows_v1.jsonl").write_text(
        "".join(json.dumps(r, ensure_ascii=False, sort_keys=True) + "\n" for r in per_row),
        encoding="utf-8")

    print("\n[STAGE 1] aggregate:")
    print(json.dumps(metrics, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
