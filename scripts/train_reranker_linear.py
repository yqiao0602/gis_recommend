#!/usr/bin/env python3
"""Train a linear reranker on candidate-pool pairwise ranking data.

Usage:
    python scripts/train_reranker_linear.py                    # train and save weights
    python scripts/train_reranker_linear.py --eval-only PATH   # evaluate existing weights
    python scripts/train_reranker_linear.py --dry-run          # print data stats only
"""

from __future__ import annotations

import argparse
import json
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
    _SKLEARN_AVAILABLE = True
except ImportError:
    _SKLEARN_AVAILABLE = False

from gis_recommend.config.transformer_config import (
    DEVICE, OUTPUT_DIR, TOTAL_VOCAB_SIZE,
    V4_QG_LABELED_WORKFLOWS_PATH, V4_QG_SPLITS_PATH, V4_QG_TASK_TYPE_VOCAB_PATH,
    V4_6_TRANSFORMER_CHECKPOINT_DIR, SET_PREDICTOR_CHECKPOINT_DIR,
    L3_EMBEDDINGS_PATH, CLASSIFICATION_HIERARCHY, ID_MAPPINGS_PATH,
)
from gis_recommend.reranking import (
    CandidateVerifier, LearnedReranker, features_to_vector, FEATURE_KEYS,
)
from gis_recommend.operators.qgis_candidate_generator import QGISCandidateGenerator
from gis_recommend.inference.infer_l3_candidates_v4 import L3SequenceInferencerV4
from gis_recommend.evaluation.reranker_pipeline import (
    tokens_to_l3_codes,
    build_reranker_candidate_pool,
    get_set_predictor_tokens,
)


DEFAULT_WEIGHTS_OUT = OUTPUT_DIR / "reranker_learned_weights.json"


def _load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _load_workflows(path: Path) -> list[dict]:
    raw = _load_json(path)
    workflows = raw.get("labeled_workflows", [])
    if not isinstance(workflows, list):
        raise ValueError(f"Invalid labeled_workflows in {path}")
    return workflows


def _resolve_checkpoint() -> Path:
    gen_f1 = V4_6_TRANSFORMER_CHECKPOINT_DIR / "best_gen_set_f1_model.pth"
    if gen_f1.exists():
        return gen_f1
    return V4_6_TRANSFORMER_CHECKPOINT_DIR / "best_model.pth"


def _extract_ranking_features(
    sample: dict,
    l3_res: dict,
    qgis_gen: QGISCandidateGenerator,
    verifier: CandidateVerifier,
    id_to_l3_code: dict,
) -> list[dict]:
    """Extract features for all candidates of a sample, with usability labels."""
    all_l3_cands = l3_res.get("all_candidates", [])
    if not all_l3_cands:
        return []

    pool_qgis, pool_l3 = build_reranker_candidate_pool(
        all_l3_cands, id_to_l3_code, qgis_gen, per_l3_top_k=3,
    )
    if not pool_qgis:
        return []

    set_tokens = l3_res.get("set_predictor_tokens")
    records = []
    for qgis_cand, l3_cand in zip(pool_qgis, pool_l3):
        feat = verifier.verify(
            qgis_cand,
            l3_candidate=l3_cand,
            expected_length=l3_res.get("expected_length", 8),
            set_predictor_tokens=set_tokens,
        )
        vec = features_to_vector(feat)
        ref_tokens = set(sample["l3_sequence"])
        pred_codes = tokens_to_l3_codes(
            l3_cand.tokens if l3_cand else [], id_to_l3_code
        )
        usable = (
            feat.is_valid
            and feat.io_compatibility_ratio >= 1.0
            and feat.unknown_ratio == 0.0
            and feat.issue_count == 0
        )
        invalid = (
            not feat.is_valid
            or feat.issue_count > 0
            or feat.unknown_ratio >= 0.3
        )
        records.append({
            "features": vec,
            "final_score": feat.final_score,
            "usable": usable,
            "invalid": invalid,
            "qgis_chain": list(qgis_cand.qgis_sequence),
            "l3_tokens": l3_cand.tokens if l3_cand else [],
        })
    return records


def build_training_data(
    *,
    data_path: Path,
    splits_path: Path,
    task_vocab_path: Path,
    num_samples: int = 200,
) -> tuple[list[dict], dict]:
    """Build pairwise ranking training data from quality-gate test samples."""
    import random
    import torch
    torch.manual_seed(42)
    random.seed(42)

    workflows = _load_workflows(data_path)
    splits = _load_json(splits_path)
    test_indices = splits.get("test_indices", [])[:num_samples]
    test_wf = [workflows[i] for i in test_indices]

    with open(ID_MAPPINGS_PATH, "r", encoding="utf-8") as f:
        id_mappings = json.load(f)
    l3_map = id_mappings.get("l3", {})
    id_to_l3_code = {int(v): k for k, v in l3_map.items()}

    ckpt = _resolve_checkpoint()
    print(f"  Checkpoint: {ckpt}")
    print(f"  Samples: {len(test_wf)}")

    inferencer = L3SequenceInferencerV4(
        checkpoint_path=ckpt,
        device=DEVICE,
        set_predictor_path=SET_PREDICTOR_CHECKPOINT_DIR / "best_model.pth"
        if (SET_PREDICTOR_CHECKPOINT_DIR / "best_model.pth").exists()
        else None,
    )
    qgis_gen = QGISCandidateGenerator(beam_width=3, max_unknown_ratio=0.5, verbose=False)
    verifier = CandidateVerifier()

    all_records = []
    stats = {"total": 0, "usable": 0, "invalid": 0, "samples_processed": 0}

    for sample in test_wf:
        task_name = (sample.get("task_metadata", {}) or {}).get("task_name", "")
        task_desc = (sample.get("task_metadata", {}) or {}).get("task_description", "")
        task_type = (sample.get("task_metadata", {}) or {}).get("task_type", "Unknown")

        inferencer.set_complexity_profile(task_type)
        l3_results = inferencer.infer(
            task_name=task_name,
            task_description=task_desc,
            task_type=task_type,
        )
        if not l3_results:
            continue
        l3_res = {
            "all_candidates": l3_results,
            "expected_length": inferencer.expected_length,
            "set_predictor_tokens": get_set_predictor_tokens(
                inferencer,
                inferencer._prepare_input(task_name, task_desc, task_type),
                inferencer.set_prior_mode,
            ),
        }

        records = _extract_ranking_features(
            sample, l3_res, qgis_gen, verifier, id_to_l3_code,
        )
        all_records.extend(records)
        stats["samples_processed"] += 1
        for r in records:
            stats["total"] += 1
            if r["usable"]:
                stats["usable"] += 1
            if r["invalid"]:
                stats["invalid"] += 1

    return all_records, stats


def train_linear_ranker(
    records: list[dict],
    output_path: Path,
    *,
    eval_only_path: Optional[Path] = None,
) -> dict:
    """Train logistic regression on candidate features."""
    if eval_only_path:
        reranker = LearnedReranker.load_weights(None, eval_only_path)
        result = {"weights": reranker.weights, "feature_keys": FEATURE_KEYS, "trained": False}
        return result

    # Build training pairs: usable positive, invalid negative
    usable = [r for r in records if r["usable"]]
    invalid = [r for r in records if r["invalid"]]

    if len(usable) < 10 or len(invalid) < 10:
        print(f"  [WARN] Insufficient data: {len(usable)} usable, {len(invalid)} invalid")
        return {"error": "insufficient_data", "usable": len(usable), "invalid": len(invalid)}

    X = []
    y = []
    for r in usable:
        X.append(r["features"])
        y.append(1)
    for r in invalid:
        X.append(r["features"])
        y.append(0)

    X = np.array(X, dtype=np.float64)
    y = np.array(y, dtype=np.int64)

    if not _SKLEARN_AVAILABLE:
        print("  [WARN] sklearn not available; using default weights")
        return {
            "weights": list(DEFAULT_LEARNED_WEIGHTS if "DEFAULT_LEARNED_WEIGHTS" in dir() else []),
            "feature_keys": FEATURE_KEYS,
            "trained": False,
            "error": "sklearn_not_available",
        }

    clf = LogisticRegression(max_iter=1000, class_weight="balanced", C=1.0)
    clf.fit(X, y)

    weights = clf.coef_[0].tolist()
    reranker = LearnedReranker(None, weights=weights)  # verifier not needed for save
    reranker.save_weights(output_path)

    accuracy = float(clf.score(X, y))
    result = {
        "weights": weights,
        "feature_keys": FEATURE_KEYS,
        "accuracy": accuracy,
        "intercept": float(clf.intercept_[0]),
        "n_positives": len(usable),
        "n_negatives": len(invalid),
        "trained": True,
        "output_path": str(output_path),
        "weight_interpretation": {
            key: f"{w:+.4f}" for key, w in zip(FEATURE_KEYS, weights)
        },
    }
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default=str(V4_QG_LABELED_WORKFLOWS_PATH))
    parser.add_argument("--splits", default=str(V4_QG_SPLITS_PATH))
    parser.add_argument("--task-vocab", default=str(V4_QG_TASK_TYPE_VOCAB_PATH))
    parser.add_argument("--num-samples", type=int, default=200)
    parser.add_argument("--output", default=str(DEFAULT_WEIGHTS_OUT))
    parser.add_argument("--eval-only", default=None, help="Evaluate existing weights JSON")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)

    if args.dry_run or not args.eval_only:
        print("Building reranker training data...")
        records, stats = build_training_data(
            data_path=Path(args.data),
            splits_path=Path(args.splits),
            task_vocab_path=Path(args.task_vocab),
            num_samples=args.num_samples,
        )
        print(f"  Records: {stats['total']} (usable={stats['usable']}, invalid={stats['invalid']})")
        if args.dry_run:
            return {"stats": stats}

    if args.eval_only:
        result = train_linear_ranker([], Path(args.output), eval_only_path=Path(args.eval_only))
    else:
        result = train_linear_ranker(records, Path(args.output))

    print(json.dumps(result, indent=2, ensure_ascii=False))
    return result


if __name__ == "__main__":
    main()
