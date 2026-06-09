"""Compute per-task-type L3 content-token length statistics."""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Sequence

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
SRC = PROJECT_ROOT / "src"
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gis_recommend.config.transformer_config import (  # noqa: E402
    V4_LABELED_WORKFLOWS_PATH,
    V4_QG_DATA_DIR,
    V4_QG_LABELED_WORKFLOWS_PATH,
)

DEFAULT_DATA_PATH = V4_QG_LABELED_WORKFLOWS_PATH
DEFAULT_OUTPUT_PATH = V4_QG_DATA_DIR / "task_type_length_stats.json"
LEGACY_DATA_PATH = V4_LABELED_WORKFLOWS_PATH
LEGACY_OUTPUT_PATH = PROJECT_ROOT / "outputs" / "task_type_length_stats.json"
SPECIAL_TOKEN_IDS = {-1, -2, -3, -4}


def _content_length(sequence: Sequence[int]) -> int:
    return sum(1 for token in sequence if int(token) not in SPECIAL_TOKEN_IDS)


def _percentile(sorted_values: list[int], fraction: float) -> int:
    if not sorted_values:
        return 0
    index = min(int(len(sorted_values) * fraction), len(sorted_values) - 1)
    return int(sorted_values[index])


def compute_length_stats(workflows: Sequence[dict], *, min_task_count: int = 5) -> dict:
    type_lengths: dict[str, list[int]] = defaultdict(list)
    all_lengths: list[int] = []

    for workflow in workflows:
        length = _content_length(workflow.get("l3_sequence", []))
        all_lengths.append(length)

        task_meta = workflow.get("task_metadata", {})
        task_type = task_meta.get("task_type", "Unknown")
        type_lengths[task_type].append(length)

    if not all_lengths:
        return {
            "schema_version": "gis_recommend.task_type_length_stats.v1",
            "sequence_length_definition": "content_l3_tokens_excluding_specials",
            "global": {"mean": 0.0, "median": 0, "p25": 0, "p75": 0, "p90": 0},
            "by_task_type": {},
        }

    all_lengths.sort()
    global_stats = {
        "mean": round(sum(all_lengths) / len(all_lengths), 1),
        "median": int(statistics.median(all_lengths)),
        "p25": _percentile(all_lengths, 0.25),
        "p75": _percentile(all_lengths, 0.75),
        "p90": _percentile(all_lengths, 0.90),
    }

    type_stats = {}
    for task_type, lengths in sorted(type_lengths.items()):
        if len(lengths) < int(min_task_count):
            continue
        lengths.sort()
        type_stats[task_type] = {
            "count": len(lengths),
            "mean": round(sum(lengths) / len(lengths), 1),
            "median": int(statistics.median(lengths)),
            "p25": _percentile(lengths, 0.25),
            "p75": _percentile(lengths, 0.75),
            "p90": _percentile(lengths, 0.90),
        }

    return {
        "schema_version": "gis_recommend.task_type_length_stats.v1",
        "sequence_length_definition": "content_l3_tokens_excluding_specials",
        "global": global_stats,
        "by_task_type": type_stats,
    }


def write_length_stats(output_path: Path, stats: dict) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(stats, ensure_ascii=False, indent=2), encoding="utf-8")


def load_workflows(data_path: Path) -> list[dict]:
    with open(data_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return list(data["labeled_workflows"])


def main(argv: list[str] | None = None) -> dict:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=DEFAULT_DATA_PATH)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT_PATH)
    parser.add_argument("--min-task-count", type=int, default=5)
    parser.add_argument("--legacy-step8", action="store_true", help="Use the legacy V4 Step8 default input/output paths.")
    args = parser.parse_args(argv)

    data_path = LEGACY_DATA_PATH if args.legacy_step8 else args.data
    output_path = LEGACY_OUTPUT_PATH if args.legacy_step8 else args.output
    workflows = load_workflows(data_path)
    print(f"[OK] Loaded {len(workflows)} workflows")

    stats = compute_length_stats(workflows, min_task_count=args.min_task_count)
    stats["provenance"] = {
        "data_path": str(data_path),
        "workflow_count": len(workflows),
        "min_task_count": int(args.min_task_count),
    }
    write_length_stats(output_path, stats)

    global_stats = stats["global"]
    type_stats = stats["by_task_type"]
    print(f"[DONE] Saved to {output_path}")
    print(
        f"  Global: median={global_stats['median']}, "
        f"mean={global_stats['mean']}, p90={global_stats['p90']}"
    )
    print(f"  Task types: {len(type_stats)}")
    for tt, s in list(type_stats.items())[:5]:
        print(f"    {tt}: n={s['count']}, median={s['median']}, mean={s['mean']}")
    return stats


if __name__ == "__main__":
    main()
