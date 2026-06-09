#!/usr/bin/env python3
"""Train a lightweight QGIS chain reranker using facts_summary1000.csv.

Positive: real QGIS chains matched to facts descriptions (good chains).
Negative: corrupted/random chains, modality mismatches, generic templates.

Trains a LogisticRegression model on chain features, outputting a score
for ranking QGIS candidates without L3 mapping dependency.

Usage:
    python scripts/train_qgis_reranker.py
    python scripts/train_qgis_reranker.py --eval-only PATH_TO_WEIGHTS
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import sys
from collections import Counter
from pathlib import Path
from typing import Optional

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import numpy as np

try:
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import accuracy_score, roc_auc_score
    SKLEARN_OK = True
except ImportError:
    SKLEARN_OK = False

FACTS_CSV = ROOT / "爬取GithubQGIS" / "facts_summary1000.csv"
V2_DS = ROOT / "outputs_v2" / "qgis_chain_dataset_v2.jsonl"
OFFICIAL_OPS = ROOT.parent / "operators-json" / "qgis_operators.json"
CROSSWALK = ROOT / "outputs_v2" / "qgis_alg_id_crosswalk.json"
OUTPUT_WEIGHTS = ROOT / "outputs_v2" / "qgis_reranker_weights.json"
OUTPUT_SUMMARY = ROOT / "outputs_v2" / "qgis_reranker_training_summary.json"

VECTOR_KEY_OPS = {
    "buffer", "clip", "dissolve", "intersection", "difference",
    "mergevectorlayers", "extractbyexpression", "extractbylocation",
    "joinattributesbylocation", "joinattributestable",
    "reprojectlayer", "fixgeometries", "simplifygeometries",
    "snapgeometries", "creategrid", "joinbynearest",
    "centroids", "countpointsinpolygon", "polygonstolines",
    "splitwithlines", "refactorfields", "symmetricaldifference",
}

RASTER_KEY_OPS = {
    "cliprasterbymasklayer", "cliprasterbyextent", "rastercalculator",
    "warpreproject", "fillnodata", "zonalstatisticsfb",
    "buildvirtualraster", "reclassifybytable", "translate",
    "rearrange_bands", "merge",
}

# ── Feature extraction ─────────────────────────────────────────────

def extract_features(ops: list[str]) -> np.ndarray:
    """Extract 12-dimensional feature vector from a QGIS chain."""
    n = len(ops)
    vec_kw = sum(1 for op in ops if any(
        kw in op.lower().replace("native:", "").replace("qgis:", "")
        for kw in VECTOR_KEY_OPS))
    rast_kw = sum(1 for op in ops if any(
        kw in op.lower().replace("native:", "").replace("gdal:", "")
        for kw in RASTER_KEY_OPS))
    unique = len(set(ops))
    dup_ratio = 1.0 - unique / max(n, 1) if n > 0 else 0
    consec_dup = sum(1 for i in range(n - 1) if ops[i] == ops[i + 1])
    consec_ratio = consec_dup / max(n - 1, 1) if n > 1 else 0

    return np.array([
        float(n),                    # 0: chain length
        float(vec_kw),               # 1: vector keyword count
        float(rast_kw),              # 2: raster keyword count
        vec_kw / max(n, 1),          # 3: vector ratio
        rast_kw / max(n, 1),         # 4: raster ratio
        dup_ratio,                    # 5: duplicate ratio
        consec_ratio,                 # 6: consecutive duplicate ratio
        float(n >= 3),               # 7: length >= 3
        float(n >= 5),               # 8: length >= 5
        float(vec_kw >= 2),          # 9: has >=2 vector ops
        float(vec_kw > rast_kw),     # 10: vector dominant
        float(rast_kw > vec_kw),     # 11: raster dominant
    ], dtype=np.float64)


def generate_negatives(
    ops: list[str],
    n_neg: int = 3,
) -> list[list[str]]:
    """Generate negative QGIS chains from a positive."""
    negatives = []
    n = len(ops)

    # 1) Drop a middle operator
    if n >= 3:
        idx = random.randint(1, n - 2)
        negatives.append(ops[:idx] + ops[idx + 1:])

    # 2) Swap two operators
    if n >= 3:
        i, j = random.sample(range(n), 2)
        swapped = list(ops)
        swapped[i], swapped[j] = swapped[j], swapped[i]
        if swapped != ops:
            negatives.append(swapped)

    # 3) Replace with generic raster template
    raster_templates = [
        ["gdal:warpreproject", "gdal:cliprasterbymasklayer", "native:zonalstatisticsfb"],
        ["native:buffer", "gdal:cliprasterbymasklayer", "qgis:rastercalculator"],
        ["gdal:buildvirtualraster", "gdal:warpreproject", "gdal:cliprasterbymasklayer",
         "gdal:translate"],
        ["native:fillnodata", "gdal:cliprasterbymasklayer", "native:zonalstatisticsfb"],
    ]
    if random.random() < 0.6:
        negatives.append(random.choice(raster_templates))

    # Pad to reach n_neg
    while len(negatives) < n_neg:
        if n >= 2:
            neg = list(ops)
            neg.insert(random.randint(0, n - 1), neg[random.randint(0, n - 1)])
            negatives.append(neg)
        else:
            negatives.append(["native:reprojectlayer", "native:savefeatures"])

    return negatives[:n_neg]


# ── Data loading ───────────────────────────────────────────────────

def load_official() -> dict[str, dict]:
    with open(OFFICIAL_OPS, "r", encoding="utf-8") as f:
        return {str(o.get("identifier", "")).lower().strip(): o for o in json.load(f)}


def load_dataset() -> list[dict]:
    records = []
    with V2_DS.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line: continue
            r = json.loads(line)
            if len(r.get("qgis_ops", [])) >= 2:
                records.append(r)
    return records


def build_training_data(n_pos: Optional[int] = None, n_neg_per_pos: int = 3, seed: int = 42):
    """Build feature matrix and labels from facts + v2 chains."""
    random.seed(seed)
    official = load_official()
    all_records = load_dataset()
    by_file = {r["source_file"]: r for r in all_records}

    with Path(FACTS_CSV).open("r", encoding="utf-8", errors="replace") as f:
        facts_rows = list(csv.DictReader(f))

    X_pos, X_neg = [], []
    matched = 0

    for row in facts_rows:
        fn = row["File Name"].strip()
        r = by_file.get(fn)
        if not r: continue
        ops = r["qgis_ops"]
        if len(ops) < 2: continue
        matched += 1
        X_pos.append(extract_features(ops))
        for neg_ops in generate_negatives(ops, n_neg_per_pos):
            X_neg.append(extract_features(neg_ops))

        if n_pos and matched >= n_pos: break

    # Balance
    n_neg_use = min(len(X_neg), len(X_pos) * n_neg_per_pos)
    if n_neg_use < len(X_neg):
        X_neg = random.sample(X_neg, n_neg_use)

    X = np.array(X_pos + X_neg, dtype=np.float64)
    y = np.array([1] * len(X_pos) + [0] * len(X_neg), dtype=np.int64)
    return X, y, len(X_pos), len(X_neg)


# ── Main ───────────────────────────────────────────────────────────

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--max-pos", type=int, default=0, help="Limit positive samples (0=all)")
    parser.add_argument("--test-ratio", type=float, default=0.2)
    parser.add_argument("--output", default=str(OUTPUT_WEIGHTS))
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args(argv)

    assert SKLEARN_OK, "scikit-learn required: pip install scikit-learn"

    print("=" * 60)
    print("QGIS Reranker Training")
    print("=" * 60)

    print(f"\n[1] Building training data ...")
    X, y, n_pos, n_neg = build_training_data(
        n_pos=args.max_pos if args.max_pos > 0 else None,
        seed=args.seed,
    )
    print(f"  Positives: {n_pos}, Negatives: {n_neg}, Total: {len(X)}")
    print(f"  Features: {X.shape[1]}")

    # Train/test split
    n_test = int(len(X) * args.test_ratio)
    indices = list(range(len(X)))
    random.Random(args.seed).shuffle(indices)
    test_idx = indices[:n_test]
    train_idx = [i for i in indices if i not in test_idx]
    X_train, y_train = X[train_idx], y[train_idx]
    X_test, y_test = X[test_idx], y[test_idx]

    print(f"\n[2] Training LogisticRegression ...")
    clf = LogisticRegression(
        penalty="l2", C=1.0, max_iter=2000, solver="lbfgs",
        class_weight="balanced",
    )
    clf.fit(X_train, y_train)

    train_acc = clf.score(X_train, y_train)
    test_acc = clf.score(X_test, y_test)
    y_pred = clf.predict_proba(X_test)[:, 1]
    auc = roc_auc_score(y_test, y_pred)

    print(f"  Train acc: {train_acc:.4f}")
    print(f"  Test acc:  {test_acc:.4f}")
    print(f"  ROC AUC:   {auc:.4f}")

    # Save weights
    weights = clf.coef_[0].tolist()
    intercept = float(clf.intercept_[0])
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with Path(args.output).open("w", encoding="utf-8") as f:
        json.dump({
            "coef": weights,
            "intercept": intercept,
            "feature_names": [
                "length", "vec_kw_count", "rast_kw_count", "vec_ratio", "rast_ratio",
                "dup_ratio", "consec_dup_ratio", "len_ge_3", "len_ge_5",
                "has_2plus_vec", "vec_dominant", "rast_dominant",
            ],
            "train": {"n_pos": n_pos, "n_neg": n_neg, "accuracy": train_acc},
            "test": {"n": n_test, "accuracy": test_acc, "auc": auc},
        }, f, indent=2, ensure_ascii=False)
    print(f"\n  Weights: {args.output}")

    # Summary
    with Path(OUTPUT_SUMMARY).open("w", encoding="utf-8") as f:
        json.dump({
            "n_positives": n_pos,
            "n_negatives": n_neg,
            "test_accuracy": test_acc,
            "roc_auc": auc,
            "weights": {name: round(w, 4) for name, w in zip(
                ["length","vec_kw","rast_kw","vec_ratio","rast_ratio",
                 "dup_ratio","consec_dup","len_ge_3","len_ge_5",
                 "has_2plus_vec","vec_dominant","rast_dominant"],
                weights)},
        }, f, indent=2, ensure_ascii=False)

    print(f"  Summary: {OUTPUT_SUMMARY}")


if __name__ == "__main__":
    main()
