#!/usr/bin/env python3
"""Build the deterministic GEE source/facts authority manifest."""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.gis_recommend.data.gee_corpus_authority import (  # noqa: E402
    DEFAULT_BATCHES,
    build_authority,
    write_manifest_atomic,
)


def _inside(path: Path, root: Path) -> bool:
    try:
        return os.path.commonpath([str(path.resolve()), str(root.resolve())]) == str(root.resolve())
    except ValueError:
        return False


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--facts-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--batch", action="append", dest="batches", help="Allowlisted dataNNNNN batch; repeatable")
    args = parser.parse_args(argv)
    source_root = args.source_root.resolve()
    output_dir = args.output_dir.resolve()
    facts_root = args.facts_root.resolve()
    if _inside(output_dir, source_root) or _inside(output_dir, facts_root):
        parser.error("--output-dir must not be inside --source-root or --facts-root")
    batches = tuple(args.batches) if args.batches else DEFAULT_BATCHES
    result = build_authority(source_root, args.facts_root, batches=batches)
    write_manifest_atomic(result, output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
