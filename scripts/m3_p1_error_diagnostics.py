#!/usr/bin/env python3
"""M3-P1 error diagnostics on the LOCKED final-100 predictions.

Two blocks, both scorer-side analyses of the already-locked predictions —
no re-inference, no change to any frozen artifact:

Block 1 — error statistics:
  length distribution (pred vs gold), repetition profile (consecutive /
  global), unique-operator counts, first-operator accuracy, set recall,
  prefix-set coverage (how far the prediction stays a subset of the gold
  operator multiset), runaway rows.

Block 2 — post-processing rescoring (frozen score_benchmark verbatim):
  A  original (must reproduce the locked F1 0.1605)
  B  consecutive-dedup        (A B B B C        -> A B C)
  C1 truncate to gold length  (ORACLE — uses gold, never official)
  C2 truncate to fixed len 3  (no gold used)
  D  stop at first repeat     (A B C C / A B A -> A B C / A B)

Interpretation target: separate "cannot plan" from "cannot stop".
"""

from __future__ import annotations

import json
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from score_qgis_planner_benchmark_v01 import score_benchmark  # noqa: E402

EVAL = ROOT / "docs" / "reports" / "qgis_planner_eval_v1"
BRIDGE = {l3: v["operator_id"] for l3, v in json.loads(
    (EVAL / "bridge/l3_operator_bridge_v1.json").read_text(encoding="utf-8"))["l3_to_operator"].items()}


def read_jsonl(p: Path) -> list[dict]:
    return [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]


def chain_to_graph(l3_codes: list[str]) -> dict:
    processes, links = [], []
    for code in l3_codes:
        op = BRIDGE.get(code)
        if op is None:
            continue
        processes.append({"process_id": f"p{len(processes)}", "operator_id": op})
        if len(processes) > 1:
            links.append({"source_process_id": f"p{len(processes)-2}",
                          "target_process_id": f"p{len(processes)-1}"})
    return {"processes": processes, "links": links}


def pct(vals, q):
    vals = sorted(vals)
    if not vals:
        return 0
    i = min(int(q * len(vals)), len(vals) - 1)
    return vals[i]


def main() -> int:
    preds = read_jsonl(EVAL / "predictions/m3_final_100_predictions.jsonl")
    golds = {g["sample_id"]: g for g in read_jsonl(EVAL / "gold/final_100.gold.jsonl")}
    refusal_gold = read_jsonl(EVAL / "gold/refusal_12.gold.jsonl")
    refusal_pred = read_jsonl(EVAL / "predictions/m3_refusal_12_predictions.jsonl")

    # ── Block 1: error statistics ──
    pred_lens, gold_lens = [], []
    consec_max, global_repeat_ratio, uniq_ops = [], [], []
    first_op_correct = 0
    set_recall_rows = []
    prefix_cov_rows = []
    runaway = 0
    for p in preds:
        ops = [q["operator_id"] for q in p["processes"]]
        gold = golds[p["sample_id"]]
        gold_ops = Counter(q["operator_id"] for q in gold["processes"])
        pred_lens.append(len(ops))
        gold_lens.append(len(gold_ops))
        if len(ops) >= 20:
            runaway += 1
        # repetition profile
        cmax, run = 0, 1
        for a, b in zip(ops, ops[1:]):
            run = run + 1 if a == b else 1
            cmax = max(cmax, run)
        consec_max.append(cmax)
        cnt = Counter(ops)
        global_repeat_ratio.append(1 - len(cnt) / len(ops) if ops else 0.0)
        uniq_ops.append(len(cnt))
        # first operator: is it one of gold's source-node operators?
        sources = {l["source_process_id"] for l in gold["links"]}
        source_ops = {q["operator_id"] for q in gold["processes"] if q["process_id"] in sources}
        if not sources:  # single-node gold
            source_ops = {q["operator_id"] for q in gold["processes"]}
        if ops and ops[0] in source_ops:
            first_op_correct += 1
        # set recall
        inter = sum((cnt & gold_ops).values())
        set_recall_rows.append(inter / max(sum(gold_ops.values()), 1))
        # prefix-set coverage: longest prefix of pred whose multiset stays inside gold
        acc = Counter()
        cov = 0
        for op in ops:
            if acc[op] < gold_ops.get(op, 0):
                acc[op] += 1
                cov += 1
            else:
                break
        prefix_cov_rows.append(cov / max(sum(gold_ops.values()), 1))

    n = len(preds)
    stats = {
        "n": n,
        "pred_len_mean": round(statistics.mean(pred_lens), 2),
        "pred_len_median": statistics.median(pred_lens),
        "pred_len_p90": pct(pred_lens, 0.90),
        "pred_len_p95": pct(pred_lens, 0.95),
        "pred_len_max": max(pred_lens),
        "gold_len_mean": round(statistics.mean(gold_lens), 2),
        "gold_len_median": statistics.median(gold_lens),
        "gold_len_p95": pct(gold_lens, 0.95),
        "gold_len_max": max(gold_lens),
        "runaway_rows_ge20ops": runaway,
        "max_consecutive_repeat_median": statistics.median(consec_max),
        "max_consecutive_repeat_p90": pct(consec_max, 0.90),
        "global_repeat_ratio_mean": round(statistics.mean(global_repeat_ratio), 3),
        "unique_ops_mean": round(statistics.mean(uniq_ops), 2),
        "first_operator_in_gold_sources": f"{first_op_correct}/{n}",
        "operator_set_recall_mean": round(statistics.mean(set_recall_rows), 3),
        "set_recall_ge50pct_rows": sum(1 for r in set_recall_rows if r >= 0.5),
        "prefix_coverage_mean": round(statistics.mean(prefix_cov_rows), 3),
        "prefix_coverage_ge50pct_rows": sum(1 for r in prefix_cov_rows if r >= 0.5),
    }
    print("===== Block 1: M3-P1 error statistics =====")
    print(json.dumps(stats, indent=2, ensure_ascii=False))

    # ── Block 2: post-processing rescoring ──
    def transform(chain, mode, gold_n=None):
        if mode == "A":
            return chain
        if mode == "B":
            out = []
            for c in chain:
                if not out or c != out[-1]:
                    out.append(c)
            return out
        if mode == "C1":
            return chain[: gold_n]
        if mode == "C2":
            return chain[:3]
        if mode == "D":
            seen, out = set(), []
            for c in chain:
                if c in seen:
                    break
                seen.add(c)
                out.append(c)
            return out
        raise ValueError(mode)

    def rescore(mode):
        graph_rows = []
        for p in preds:
            gold = golds[p["sample_id"]]
            gold_n = sum(1 for _ in gold["processes"])
            chain = transform(p["diagnostics"]["l3_chain"], mode, gold_n)
            g = chain_to_graph(chain)
            graph_rows.append({"sample_id": p["sample_id"], **g})
        result = score_benchmark(
            [golds[p["sample_id"]] for p in preds], graph_rows,
            refusal_gold, refusal_pred)
        return result["graph"]

    variants = {}
    for mode, label, oracle in (
        ("A", "original (locked)", False),
        ("B", "consecutive-dedup", False),
        ("C1", "truncate-to-gold-length", True),
        ("C2", "truncate-to-3", False),
        ("D", "stop-at-first-repeat", False),
    ):
        g = rescore(mode)
        variants[mode] = {"label": label, "oracle": oracle,
                          "operator_micro_f1": round(g["operator_micro_f1"], 4),
                          "operator_micro_precision": round(g["operator_micro_precision"], 4),
                          "operator_micro_recall": round(g["operator_micro_recall"], 4),
                          "edge_micro_f1": round(g["edge_micro_f1"], 4),
                          "graph_exact_match_rate": g["graph_exact_match_rate"],
                          "harmful_extra_operator_rate": round(g["harmful_extra_operator_rate"], 4)}
        print(f"  {mode} {label:28s} F1={variants[mode]['operator_micro_f1']:.4f} "
              f"P={variants[mode]['operator_micro_precision']:.4f} "
              f"R={variants[mode]['operator_micro_recall']:.4f} "
              f"edgeF1={variants[mode]['edge_micro_f1']:.4f} "
              f"EM={g['graph_exact_match_rate']:.2f}")

    out = {
        "schema": "gis_recommend.m3_p1_error_diagnostics.v1",
        "subject": "M3-P1 locked final-100 predictions (PREDICTION_LOCK_v1, no re-inference)",
        "decoding_note": "M3-P1 official inference is GREEDY (eos stop, max_new_tokens 300) — "
                         "the repetition runaways are model behavior under greedy, not a beam artifact",
        "block1_statistics": stats,
        "block2_postprocessing_rescoring": variants,
        "oracle_warning": "C1 uses gold length — diagnostic only, can never be an official score",
    }
    (EVAL / "M3_P1_ERROR_DIAGNOSTICS_v1.json").write_text(
        json.dumps(out, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote {EVAL / 'M3_P1_ERROR_DIAGNOSTICS_v1.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
