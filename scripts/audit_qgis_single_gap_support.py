#!/usr/bin/env python3
"""Normalized-body support audit for single-missing-operator rows.

For each row with exactly one unmapped operator, compute the normalized-source-
body SHA256 on the read-only /home/yll tree and cluster per operator. Output is
the minimal-extension support evidence (unique normalized bodies) - statistics
only, no L3 admission.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gis_recommend.data.qgis_source_authority import source_authority  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--rows", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, default=Path("/home/yll"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    rows = [json.loads(line) for line in args.rows.read_text(encoding="utf-8").splitlines() if line.strip()]
    root = str(args.source_root).rstrip("/")
    per_op: dict[str, dict[str, int]] = defaultdict(lambda: {"rows": 0, "unique_bodies": 0})
    bodies: dict[str, set[str]] = defaultdict(set)
    failures = 0
    for row in rows:
        raw = str(row.get("source_path") or "")
        path = Path(raw) if raw.startswith(root) else args.source_root / raw.lstrip("/")
        op = row["missing_op"]
        per_op[op]["rows"] += 1
        if not path.is_file():
            failures += 1
            continue
        authority = source_authority(path, source_sha256=str(row.get("source_sha256") or ""))
        body_sha = str(authority.get("normalized_source_body_sha256") or "")
        if not body_sha:
            failures += 1
            continue
        bodies[op].add(body_sha)
    for op, entry in per_op.items():
        entry["unique_bodies"] = len(bodies.get(op, set()))
    payload = {
        "schema": "gis_recommend.qgis_single_gap_support.v1",
        "rows": len(rows),
        "source_failures": failures,
        "support": {
            op: entry
            for op, entry in sorted(per_op.items(), key=lambda kv: (-kv[1]["unique_bodies"], kv[0]))
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"rows": len(rows), "failures": failures, "operators": len(per_op)}, ensure_ascii=False))
    for op, entry in list(payload["support"].items())[:20]:
        print(f"  {op}: {entry['rows']} rows / {entry['unique_bodies']} unique bodies")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
