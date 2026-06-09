"""Analyze length bucket distribution across task types.

Uses LengthBucketPredictor to classify each task type and reports:
- Per-bucket task type counts and sample counts
- Per-task-type median/mean/p90 length
- Bucket assignment rationale
"""

from __future__ import annotations

import json
import sys
import argparse
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(SRC))

from gis_recommend.data.length_bucket_predictor import LengthBucketPredictor, default_length_stats_path  # noqa: E402


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stats", type=Path, default=default_length_stats_path(ROOT))
    args = parser.parse_args(argv)

    stats_path = args.stats
    predictor = LengthBucketPredictor(stats_path)

    raw = json.loads(stats_path.read_text(encoding="utf-8"))
    by_type = raw.get("by_task_type", {})

    bucket_tasks: dict[str, list[tuple[str, dict]]] = defaultdict(list)
    for task_type, stats in sorted(by_type.items()):
        bucket = predictor.predict(task_type)
        bucket_tasks[bucket.bucket].append((task_type, stats))

    print("=== Length Bucket Distribution ===\n")
    bucket_order = ["short", "medium", "long", "very_long"]
    for bucket_name in bucket_order:
        tasks = bucket_tasks.get(bucket_name, [])
        total_samples = sum(s["count"] for _, s in tasks)
        print(f"## {bucket_name}")
        print(f"   Task types: {len(tasks)}, Total samples: {total_samples}")
        print(f"   {'Task Type':<50} {'Count':>6} {'Median':>7} {'Mean':>7} {'P90':>7}")
        print(f"   {'-'*50} {'-'*6} {'-'*7} {'-'*7} {'-'*7}")
        for task_type, stats in tasks:
            print(f"   {task_type[:50]:<50} {stats['count']:>6} {stats['median']:>7} {stats['mean']:>7} {stats.get('p90', 'N/A'):>7}")
        print()

    print("=== Summary ===")
    print(f"Total task types: {len(by_type)}")
    print(f"Total buckets: {len(bucket_tasks)}")
    for bucket_name in bucket_order:
        tasks = bucket_tasks.get(bucket_name, [])
        if tasks:
            total = sum(s["count"] for _, s in tasks)
            print(f"  {bucket_name}: {len(tasks)} types, {total} samples")


if __name__ == "__main__":
    main()
