#!/usr/bin/env python3
"""Build a V2 transition matrix from the quality-gated V4 train split."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gis_recommend.config.transformer_config import (  # noqa: E402
    OUTPUT_DIR,
    SPECIAL_TOKENS,
    TOTAL_VOCAB_SIZE,
    VOCAB_SIZE,
)
from gis_recommend.training.splits import validate_split_indices  # noqa: E402


SPECIAL_TOKEN_MAP = {v: VOCAB_SIZE + abs(v) - 1 for v in SPECIAL_TOKENS.values()}


def default_paths() -> dict[str, Path]:
    candidate_dir = OUTPUT_DIR / "pipeline" / "step8_quality_gate"
    return {
        "data": candidate_dir / "labeled_workflows_l3_v4_quality_gate.json",
        "splits": candidate_dir / "dataset_splits_v4_quality_gate.json",
        "output": OUTPUT_DIR / "transition_allowed_next.json",
    }


def _load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        data = json.load(f)
    if not isinstance(data, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return data


def _load_workflows(path: Path) -> list[dict]:
    raw = _load_json(path)
    workflows = raw.get("labeled_workflows", [])
    if not isinstance(workflows, list):
        raise ValueError(f"Invalid labeled_workflows in {path}")
    return workflows


def _convert_token(token: int) -> int:
    if token < 0:
        return SPECIAL_TOKEN_MAP.get(token, SPECIAL_TOKEN_MAP[-2])
    return token


def build_transition_matrix(
    *,
    data_path: Path,
    splits_path: Path,
    output_path: Path,
    split_name: str = "train",
) -> dict:
    workflows = _load_workflows(data_path)
    splits = _load_json(splits_path)
    validate_split_indices(splits, len(workflows))
    split_key = f"{split_name}_indices"
    if split_key not in splits:
        raise ValueError(f"Split file missing {split_key}: {splits_path}")

    selected = [workflows[index] for index in splits[split_key]]
    counts: dict[int, Counter] = defaultdict(Counter)
    invalid_tokens = set()
    invalid_transition_count = 0
    token_count = 0
    transition_count = 0

    for workflow in selected:
        converted = [_convert_token(int(token)) for token in workflow.get("l3_sequence", [])]
        token_count += len(converted)
        for previous, current in zip(converted, converted[1:]):
            previous_valid = 0 <= previous < TOTAL_VOCAB_SIZE
            current_valid = 0 <= current < TOTAL_VOCAB_SIZE
            if not previous_valid:
                invalid_tokens.add(previous)
            if not current_valid:
                invalid_tokens.add(current)
            if not previous_valid or not current_valid:
                invalid_transition_count += 1
                continue
            counts[previous][current] += 1
            transition_count += 1

    allowed_next = {
        str(previous): {
            str(current): int(count)
            for current, count in sorted(next_counts.items())
        }
        for previous, next_counts in sorted(counts.items())
    }
    payload = {
        "allowed_next": allowed_next,
        "metadata": {
            "source": "quality_gate_train_split",
            "data_path": str(data_path),
            "splits_path": str(splits_path),
            "split_name": split_name,
            "workflow_count": len(selected),
            "token_count": token_count,
            "transition_count": transition_count,
            "invalid_transition_count": invalid_transition_count,
            "invalid_tokens": sorted(invalid_tokens),
            "vocab_size": VOCAB_SIZE,
            "total_vocab_size": TOTAL_VOCAB_SIZE,
            "special_token_map": {str(k): int(v) for k, v in SPECIAL_TOKEN_MAP.items()},
        },
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    return payload


def main(argv: list[str] | None = None) -> dict:
    defaults = default_paths()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", default=str(defaults["data"]))
    parser.add_argument("--splits", default=str(defaults["splits"]))
    parser.add_argument("--output", default=str(defaults["output"]))
    parser.add_argument("--split-name", default="train", choices=["train", "val", "test"])
    args = parser.parse_args(argv)

    payload = build_transition_matrix(
        data_path=Path(args.data),
        splits_path=Path(args.splits),
        output_path=Path(args.output),
        split_name=args.split_name,
    )
    metadata = payload["metadata"]
    print("Quality-gate transition matrix:")
    print(f"  output: {args.output}")
    print(f"  workflows: {metadata['workflow_count']}")
    print(f"  states: {len(payload['allowed_next'])}")
    print(f"  transitions: {metadata['transition_count']}")
    print(f"  invalid transitions skipped: {metadata['invalid_transition_count']}")
    if metadata["invalid_tokens"]:
        print(f"  invalid tokens: {metadata['invalid_tokens']}")
    return payload


if __name__ == "__main__":
    main()
