#!/usr/bin/env python3
"""Train a query-grouped pairwise learned reranker from selector traces.

Reads the selector_report.json produced by evaluate_execution_aware_selector.py.
Each sample is a query group containing N candidates with features + usable labels.

Training:
    - Query-level train/test split (candidates from same query stay together)
    - Pairwise: for each query, (pos, neg) pairs where pos=usable, neg=unusable
    - Logistic regression: P(pos > neg | feature_diff)
    - Evaluation: group-level Top-1 usable rate, not per-candidate accuracy

Usage:
    python scripts/train_learned_reranker.py \
        --report outputs_v2/diagnostics/execution_aware_selector/selector_report.json \
        --output outputs_v2/reranker_learned_weights_v1.json

    python scripts/train_learned_reranker.py --eval-only PATH_TO_WEIGHTS
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import numpy as np

try:
    from sklearn.linear_model import LogisticRegression
    SKLEARN_OK = True
except ImportError:
    SKLEARN_OK = False


FEATURE_KEYS = [
    "qgis_mapping_rate",
    "io_compatibility",
    "transition_validity",
    "set_predictor_coverage",
    "length_bucket_fit",
    "repetition_rate",
    "early_eos_risk",
    "candidate_source",
    "model_logprob",
]


def _load_report(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _ci(rate: float, n: int) -> str:
    if n == 0:
        return "N/A"
    se = math.sqrt(rate * (1 - rate) / max(n, 1))
    lo = max(0.0, rate - 1.96 * se)
    hi = min(1.0, rate + 1.96 * se)
    return f"[{lo:.4f}, {hi:.4f}]"


# ═══════════════════════════════════════════════════════════════════════
# Data extraction
# ═══════════════════════════════════════════════════════════════════════

def extract_query_groups(report: dict) -> list[dict]:
    """Extract query groups from per_sample records.

    Returns: list of {task_type, candidates: [{features, usable}]}
    """
    groups = []
    for sample in report.get("per_sample", []):
        pool = sample.get("pool_candidates", [])
        if not pool:
            continue
        candidates = []
        for c in pool:
            feats = c.get("features", {})
            vec = [float(feats.get(k, 0.0)) for k in FEATURE_KEYS]
            candidates.append({
                "features": vec,
                "usable": bool(c.get("usable", False)),
                "usability_score": float(c.get("usability_score", 0.0)),
                "source": c.get("source", ""),
                "tokens": c.get("tokens", []),
            })
        groups.append({
            "task_type": sample.get("task_type", "Unknown"),
            "candidates": candidates,
        })
    return groups


# ═══════════════════════════════════════════════════════════════════════
# Query-level split
# ═══════════════════════════════════════════════════════════════════════

def query_level_split(
    groups: list[dict], test_ratio: float = 0.2, seed: int = 42,
) -> tuple[list[dict], list[dict]]:
    """Split query groups, keeping all candidates of a query together."""
    rng = random.Random(seed)
    # Shuffle groups deterministically
    indices = list(range(len(groups)))
    rng.shuffle(indices)
    n_test = max(1, int(len(groups) * test_ratio))
    test_idx = set(indices[:n_test])
    train = [g for i, g in enumerate(groups) if i not in test_idx]
    test = [g for i, g in enumerate(groups) if i in test_idx]
    return train, test


# ═══════════════════════════════════════════════════════════════════════
# Pairwise training data
# ═══════════════════════════════════════════════════════════════════════

def build_pairwise_data(groups: list[dict]) -> tuple[np.ndarray, np.ndarray]:
    """Build (feature_diff, label) pairs for pairwise logistic regression.

    For each query group:
        positives = candidates with usable=True
        negatives = candidates with usable=False
        For each (pos, neg) pair: diff = pos_features - neg_features, label = 1

    Returns (X_diff, y) as numpy arrays.
    """
    X_diffs = []
    y_vals = []
    for g in groups:
        pos = [c for c in g["candidates"] if c["usable"]]
        neg = [c for c in g["candidates"] if not c["usable"]]
        if not pos or not neg:
            continue
        for p in pos:
            for n in neg:
                # pos > neg: label=1
                X_diffs.append(np.array(p["features"]) - np.array(n["features"]))
                y_vals.append(1)
                # neg < pos: label=0 (symmetry for binary LR)
                X_diffs.append(np.array(n["features"]) - np.array(p["features"]))
                y_vals.append(0)
    if not X_diffs:
        return np.array([]).reshape(0, len(FEATURE_KEYS)), np.array([])
    return np.array(X_diffs, dtype=np.float64), np.array(y_vals, dtype=np.int64)


# ═══════════════════════════════════════════════════════════════════════
# Group-level evaluation
# ═══════════════════════════════════════════════════════════════════════

def evaluate_weights(
    groups: list[dict], weights: list[float],
) -> dict:
    """Evaluate learned weights on held-out query groups.

    Returns group-level metrics: Top-1 usable rate, MRR, oracle gap.
    """
    top1_correct = 0
    total = 0
    reciprocal_ranks = []
    usable_available = 0

    for g in groups:
        candidates = g["candidates"]
        has_usable = any(c["usable"] for c in candidates)
        if not has_usable:
            continue  # oracle can't help here
        usable_available += 1

        # Score all candidates
        scored = []
        for c in candidates:
            score = sum(w * v for w, v in zip(weights, c["features"]))
            scored.append((score, c["usable"], c))

        scored.sort(key=lambda x: -x[0])

        # Top-1 usable
        if scored[0][1]:
            top1_correct += 1

        # MRR: rank of first usable
        for rank, (_, usable, _) in enumerate(scored, 1):
            if usable:
                reciprocal_ranks.append(1.0 / rank)
                break

        total += 1

    top1_rate = top1_correct / max(total, 1)
    mrr = sum(reciprocal_ranks) / max(len(reciprocal_ranks), 1)

    return {
        "top1_usable_rate": top1_rate,
        "mrr": mrr,
        "n_queries_with_usable": usable_available,
        "n_queries_total": len(groups),
        "n_queries_evaluated": total,
    }


# ═══════════════════════════════════════════════════════════════════════
# Training
# ═══════════════════════════════════════════════════════════════════════

def train(
    train_groups: list[dict],
    test_groups: list[dict],
    baseline_weights: list[float] | None = None,
    output_path: Path | None = None,
) -> dict:
    if not SKLEARN_OK:
        return {"error": "sklearn not installed", "trained": False}

    X_train, y_train = build_pairwise_data(train_groups)
    if len(X_train) < 10:
        return {"error": f"insufficient training data ({len(X_train)} pairs)", "trained": False}

    # Balance: downsample majority class pairs to at most 10x minority
    n_pos = int(y_train.sum())
    if n_pos > 0:
        # All pairs are label=1 (pos>neg), no explicit 0 class in pairwise
        # But for robustness, add small L2 regularization
        pass

    C_VALUES = [0.03, 0.1, 0.3, 1.0]
    SEEDS = [42, 123, 456]

    sweep = []
    best_test_top1 = -1.0
    best_weights = None
    best_C = None

    for C_val in C_VALUES:
        seed_top1s = []
        seed_mrrs = []
        for seed in SEEDS:
            train_g, test_g = query_level_split(train_groups + test_groups, test_ratio=0.2, seed=seed)
            X_tr, y_tr = build_pairwise_data(train_g)
            if len(X_tr) < 10:
                continue
            clf = LogisticRegression(
                penalty="l2", C=C_val, max_iter=2000, solver="lbfgs",
            )
            clf.fit(X_tr, y_tr)
            w = clf.coef_[0].tolist()
            ev = evaluate_weights(test_g, w)
            seed_top1s.append(ev["top1_usable_rate"])
            seed_mrrs.append(ev["mrr"])

        if seed_top1s:
            mean_top1 = sum(seed_top1s) / len(seed_top1s)
            mean_mrr = sum(seed_mrrs) / len(seed_mrrs)
            std_top1 = (sum((s - mean_top1) ** 2 for s in seed_top1s) / len(seed_top1s)) ** 0.5
            sweep.append({
                "C": C_val, "mean_top1": round(mean_top1, 4), "std_top1": round(std_top1, 4),
                "mean_mrr": round(mean_mrr, 4),
            })
            if mean_top1 > best_test_top1:
                best_test_top1 = mean_top1
                best_C = C_val
                # Train on full data with best C for final weights
                X_full, y_full = build_pairwise_data(train_groups + test_groups)
                clf_best = LogisticRegression(
                    penalty="l2", C=C_val, max_iter=2000, solver="lbfgs",
                )
                clf_best.fit(X_full, y_full)
                best_weights = clf_best.coef_[0].tolist()

    if best_weights is None:
        return {"error": "no valid sweep results", "trained": False}

    # Evaluate best weights on all groups
    all_eval = evaluate_weights(train_groups + test_groups, best_weights)
    base_all = evaluate_weights(train_groups + test_groups, baseline_weights) if baseline_weights else {}

    result = {
        "trained": True,
        "learned_weights": best_weights,
        "feature_keys": FEATURE_KEYS,
        "selected_C": best_C,
        "C_sweep": sweep,
        "weight_interpretation": {
            k: f"{w:+.4f}" for k, w in zip(FEATURE_KEYS, best_weights)
        },
        "all_groups_eval": all_eval,
        "baseline_all_groups": base_all,
        "delta_vs_baseline": {
            "top1_usable_rate": round(all_eval["top1_usable_rate"] - base_all.get("top1_usable_rate", 0), 4),
            "mrr": round(all_eval["mrr"] - base_all.get("mrr", 0), 4),
        } if base_all else {},
    }

    # Save weights
    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as f:
            json.dump({
                "feature_keys": FEATURE_KEYS,
                "weights": best_weights,
                "selected_C": best_C,
                "C_sweep": sweep,
                "training_metadata": {
                    "n_queries": len(train_groups) + len(test_groups),
                    "n_pairs": len(X_full),
                },
            }, f, indent=2, ensure_ascii=False)
        result["output_path"] = str(output_path)

    return result


# ═══════════════════════════════════════════════════════════════════════
# Reporting
# ═══════════════════════════════════════════════════════════════════════

def print_results(result: dict) -> None:
    if result.get("error"):
        print(f"\n  ERROR: {result['error']}")
        return

    print(f"\n{'='*60}")
    print("Learned Reranker Results")
    print(f"{'='*60}")

    if result.get("C_sweep"):
        print("\nC-Sweep (3 seeds x 4 C values):")
        print(f"  {'C':>6}  {'Mean Top-1':>10}  {'Std':>6}  {'Mean MRR':>9}")
        print(f"  {'-'*40}")
        for row in result["C_sweep"]:
            print(f"  {row['C']:>6.2f}  {row['mean_top1']*100:>9.1f}%  +/-{row['std_top1']*100:>4.1f}%  {row['mean_mrr']:>9.4f}")

    if result.get("selected_C") is not None:
        print(f"\nSelected C: {result['selected_C']}")

    print("\nWeights (selected C, refit on all data):")
    for k, w in zip(result["feature_keys"], result["learned_weights"]):
        sig = "!" if abs(w) > 5.0 else ("." if abs(w) < 0.01 else " ")
        print(f"  {k:30s} {sig} {w:+.4f}")

    eval_data = result.get("all_groups_eval", result.get("test", {}))
    n_q = eval_data.get("n_queries_evaluated", 0)
    print(f"\nAll Groups diagnostic ({n_q} queries, in-sample after final refit):")
    print(f"  Top-1 Usable: {eval_data['top1_usable_rate']*100:.1f}%  "
          f"{_ci(eval_data['top1_usable_rate'], n_q)}")
    print(f"  MRR:         {eval_data['mrr']:.4f}")

    if result.get("delta_vs_baseline"):
        d = result["delta_vs_baseline"]
        print(f"\n  vs Rule Baseline:")
        print(f"    Delta Top-1: {d['top1_usable_rate']*100:+.1f}pp")
        print(f"    Delta MRR:   {d['mrr']:+.4f}")

    if result.get("output_path"):
        print(f"\n  Weights saved to: {result['output_path']}")


# ═══════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════

def main(argv: list[str] | None = None) -> dict:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--report", type=str,
        default="outputs_v2/diagnostics/execution_aware_selector/selector_report.json",
        help="Path to selector_report.json from evaluate_execution_aware_selector.py",
    )
    parser.add_argument(
        "--output", type=str,
        default="outputs_v2/reranker_learned_weights_v1.json",
        help="Output path for learned weights JSON",
    )
    parser.add_argument("--test-ratio", type=float, default=0.2)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--eval-only", type=str, default=None, help="Evaluate existing weights JSON")
    args = parser.parse_args(argv)

    assert SKLEARN_OK, "sklearn required: pip install scikit-learn"

    report_path = Path(args.report)
    if not report_path.exists():
        raise FileNotFoundError(f"Report not found: {report_path}")
    report = _load_report(report_path)

    groups = extract_query_groups(report)
    print(f"Loaded {len(groups)} query groups from {report_path}")
    print(f"  Total candidates: {sum(len(g['candidates']) for g in groups)}")

    if args.eval_only:
        weights_path = Path(args.eval_only)
        with weights_path.open("r") as f:
            wdata = json.load(f)
        weights = wdata["weights"]
        print(f"Evaluating weights from {weights_path}...")
        metrics = evaluate_weights(groups, weights)
        n = metrics["n_queries_evaluated"]
        print(f"  Top-1 Usable: {metrics['top1_usable_rate']*100:.1f}% ({metrics['n_queries_with_usable']} / {metrics['n_queries_total']} with usable)")
        print(f"  MRR: {metrics['mrr']:.4f}")
        return {"weights": weights, "metrics": metrics}

    # Split
    random.seed(args.seed)
    train_groups, test_groups = query_level_split(groups, test_ratio=args.test_ratio, seed=args.seed)
    print(f"Train queries: {len(train_groups)}, Test queries: {len(test_groups)}")

    # Baseline: default rule weights from ExecutionAwareSelector.DEFAULT_WEIGHTS
    baseline = [
        0.22,   # qgis_mapping_rate
        0.18,   # io_compatibility
        0.15,   # transition_validity
        0.10,   # set_predictor_coverage
        0.10,   # length_bucket_fit
        -0.08,  # repetition_rate
        -0.07,  # early_eos_risk
        0.05,   # candidate_source
        0.05,   # model_logprob
    ]

    result = train(
        train_groups, test_groups,
        baseline_weights=baseline,
        output_path=Path(args.output),
    )
    print_results(result)
    return result


if __name__ == "__main__":
    main()
