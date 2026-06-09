#!/usr/bin/env python3
"""Build generation preference pairs from execution-aware selector traces.

The output is JSONL consumed by scripts/train_v4_6_preference.py. This script
does not run inference, train a model, or mutate checkpoints.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

SCHEMA_VERSION = "gis_recommend.preference_pairs.v1"


def load_report(path: Path) -> dict:
    with Path(path).open("r", encoding="utf-8") as f:
        return json.load(f)


def _load_token_names(id_mappings_path: Path, hierarchy_path: Path) -> dict[int, str]:
    import csv

    id_mappings = load_report(id_mappings_path)
    code_to_id = {str(k): int(v) for k, v in (id_mappings.get("l3", {}) or {}).items()}
    token_names: dict[int, str] = {}
    with Path(hierarchy_path).open("r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            code = row.get("l3_code", "")
            if code in code_to_id:
                token_names[int(code_to_id[code])] = row.get("l3_name", "")
    return token_names


def _candidate_quality_penalty(candidate: dict, token_names: dict[int, str] | None = None) -> float:
    tokens = [int(t) for t in candidate.get("tokens", [])]
    duplicate_extra = max(0, len(tokens) - len(set(tokens)))
    consecutive_duplicates = sum(
        1 for i in range(max(len(tokens) - 1, 0)) if tokens[i] == tokens[i + 1]
    )
    warnings = list(candidate.get("failure_taxonomy", []) or [])

    penalty = 0.0
    penalty += min(0.30, 0.08 * duplicate_extra)
    penalty += min(0.35, 0.15 * consecutive_duplicates)

    if token_names:
        names = [str(token_names.get(t, "")) for t in tokens]
        loop_count = 0
        for i in range(max(len(names) - 2, 0)):
            a, b, c = [str(n).lower() for n in names[i:i + 3]]
            if (
                "train" in a and "apply" in b and "train" in c
            ) or (
                "apply" in a and "train" in b and "apply" in c
            ):
                loop_count += 1
        penalty += min(0.45, 0.25 * loop_count)

    warning_penalties = {
        "FP04:consecutive_duplicate": 0.25,
        "consecutive_duplicate": 0.25,
        "FP02:export_before_processing": 0.20,
        "export_before_processing": 0.20,
        "harmful_steps": 0.20,
        "missing_critical_steps": 0.12,
        "length_anomaly": 0.08,
        "FP05:length_anomaly": 0.08,
    }
    for warning in warnings:
        for marker, value in warning_penalties.items():
            if marker in str(warning):
                penalty += value
                break

    return min(1.0, penalty)


def _candidate_reward(
    candidate: dict,
    *,
    reward_mode: str = "base",
    token_names: dict[int, str] | None = None,
) -> float:
    """Reward used to rank candidates for preference-pair construction."""
    usability = float(candidate.get("usability_score", 0.0))
    features = candidate.get("features", {}) or {}
    qgis = float(features.get("qgis_mapping_rate", 0.0))
    transition = float(features.get("transition_validity", 0.0))
    length_fit = float(features.get("length_bucket_fit", 0.0))
    repetition = float(features.get("repetition_rate", 0.0))
    usable_bonus = 0.25 if bool(candidate.get("usable", False)) else 0.0
    reward = (
        0.55 * usability
        + 0.15 * qgis
        + 0.15 * transition
        + 0.10 * length_fit
        - 0.10 * repetition
        + usable_bonus
    )
    if reward_mode == "quality":
        reward -= _candidate_quality_penalty(candidate, token_names)
    return reward


def _candidate_key(candidate: dict) -> tuple[int, ...]:
    return tuple(int(t) for t in candidate.get("tokens", []))


def _best_positive(
    candidates: list[dict],
    *,
    reward_mode: str = "base",
    token_names: dict[int, str] | None = None,
) -> dict | None:
    positives = [
        c for c in candidates
        if c.get("tokens") and bool(c.get("usable", False))
    ]
    if not positives:
        return None
    return max(
        positives,
        key=lambda c: _candidate_reward(c, reward_mode=reward_mode, token_names=token_names),
    )


def _hard_negatives(
    candidates: list[dict],
    *,
    pos: dict,
    max_negatives_per_positive: int,
    min_reward_margin: float,
    reward_mode: str = "base",
    token_names: dict[int, str] | None = None,
) -> list[dict]:
    pos_key = _candidate_key(pos)
    pos_reward = _candidate_reward(pos, reward_mode=reward_mode, token_names=token_names)
    negatives = []
    for c in candidates:
        if not c.get("tokens"):
            continue
        if _candidate_key(c) == pos_key:
            continue
        reward = _candidate_reward(c, reward_mode=reward_mode, token_names=token_names)
        margin = pos_reward - reward
        if margin < min_reward_margin:
            continue
        if (
            reward_mode != "quality"
            and bool(c.get("usable", False))
            and float(c.get("usability_score", 0.0)) >= float(pos.get("usability_score", 0.0))
        ):
            continue
        negatives.append(c)
    negatives.sort(
        key=lambda c: _candidate_reward(c, reward_mode=reward_mode, token_names=token_names),
        reverse=True,
    )
    return negatives[:max_negatives_per_positive]


def build_preference_pairs(
    report: dict,
    *,
    source: str = "beam",
    min_reward_margin: float = 0.15,
    max_negatives_per_positive: int = 2,
    reward_mode: str = "base",
    token_names: dict[int, str] | None = None,
) -> list[dict]:
    """Build query-local positive/negative candidate pairs.

    By default only beam candidates are used, because the objective is to
    improve the generator's own ranking rather than teach it to imitate
    retrieval outputs.
    """
    pairs: list[dict] = []
    for sample in report.get("per_sample", []):
        pool = sample.get("pool_candidates", []) or []
        candidates = [c for c in pool if c.get("source") == source]
        if len(candidates) < 2:
            continue
        pos = _best_positive(candidates, reward_mode=reward_mode, token_names=token_names)
        if pos is None:
            continue
        negatives = _hard_negatives(
            candidates,
            pos=pos,
            max_negatives_per_positive=max_negatives_per_positive,
            min_reward_margin=min_reward_margin,
            reward_mode=reward_mode,
            token_names=token_names,
        )
        if not negatives:
            continue

        task_meta = sample.get("task_metadata", {}) or {}
        pos_reward = _candidate_reward(pos, reward_mode=reward_mode, token_names=token_names)
        for neg in negatives:
            neg_reward = _candidate_reward(neg, reward_mode=reward_mode, token_names=token_names)
            pairs.append({
                "schema": SCHEMA_VERSION,
                "sample_index": sample.get("sample_index"),
                "split": sample.get("split"),
                "source": source,
                "reward_mode": reward_mode,
                "task_type": sample.get("task_type") or task_meta.get("task_type", "Unknown"),
                "task_name": task_meta.get("task_name", ""),
                "task_description": task_meta.get("task_description", sample.get("task_description", "")),
                "pos_tokens": [int(t) for t in pos.get("tokens", [])],
                "neg_tokens": [int(t) for t in neg.get("tokens", [])],
                "pos_reward": round(pos_reward, 6),
                "neg_reward": round(neg_reward, 6),
                "reward_margin": round(pos_reward - neg_reward, 6),
                "pos_usable": bool(pos.get("usable", False)),
                "neg_usable": bool(neg.get("usable", False)),
                "pos_usability_score": float(pos.get("usability_score", 0.0)),
                "neg_usability_score": float(neg.get("usability_score", 0.0)),
                "pos_quality_penalty": round(_candidate_quality_penalty(pos, token_names), 6),
                "neg_quality_penalty": round(_candidate_quality_penalty(neg, token_names), 6),
                "pos_features": pos.get("features", {}),
                "neg_features": neg.get("features", {}),
            })
    return pairs


def write_jsonl(rows: Iterable[dict], path: Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def main(argv: list[str] | None = None) -> dict:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report", required=True, help="selector_report.json")
    parser.add_argument("--output", required=True, help="Output JSONL path")
    parser.add_argument("--source", default="beam", choices=["beam", "retrieval", "mr_equivalent", "local_edit"])
    parser.add_argument("--min-reward-margin", type=float, default=0.15)
    parser.add_argument("--max-negatives-per-positive", type=int, default=2)
    parser.add_argument("--reward-mode", choices=["base", "quality"], default="base",
                        help="base preserves v1 rewards; quality penalizes usable-but-redundant candidates")
    parser.add_argument("--id-mappings", default="outputs_v2/id_mappings_v2.json",
                        help="Used only by --reward-mode quality for token-name loop penalties")
    parser.add_argument("--hierarchy", default="outputs_v2/classification_hierarchy_v2.csv",
                        help="Used only by --reward-mode quality for token-name loop penalties")
    args = parser.parse_args(argv)

    report = load_report(Path(args.report))
    token_names = None
    if args.reward_mode == "quality":
        token_names = _load_token_names(Path(args.id_mappings), Path(args.hierarchy))
    pairs = build_preference_pairs(
        report,
        source=args.source,
        min_reward_margin=args.min_reward_margin,
        max_negatives_per_positive=args.max_negatives_per_positive,
        reward_mode=args.reward_mode,
        token_names=token_names,
    )
    write_jsonl(pairs, Path(args.output))

    summary = {
        "schema": SCHEMA_VERSION + ".summary",
        "report": str(args.report),
        "output": str(args.output),
        "source": args.source,
        "reward_mode": args.reward_mode,
        "id_mappings": str(args.id_mappings) if args.reward_mode == "quality" else None,
        "hierarchy": str(args.hierarchy) if args.reward_mode == "quality" else None,
        "num_pairs": len(pairs),
        "min_reward_margin": args.min_reward_margin,
        "max_negatives_per_positive": args.max_negatives_per_positive,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return summary


if __name__ == "__main__":
    main()
