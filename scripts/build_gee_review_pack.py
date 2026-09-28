#!/usr/bin/env python3
"""Build a deterministic source-disjoint GEE extractor review pack."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from gis_recommend.data.gee_review_pack import (
    DEFAULT_QUOTAS,
    load_manifest_records,
    write_review_artifacts,
)


def _parse_quota(value: str) -> tuple[str, int]:
    try:
        name, count = value.split("=", 1)
        parsed = int(count)
    except (ValueError, TypeError) as exc:
        raise argparse.ArgumentTypeError("quota must use STRATUM=COUNT") from exc
    if parsed < 0:
        raise argparse.ArgumentTypeError("quota count must be non-negative")
    return name, parsed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--quota", type=_parse_quota, action="append", default=[])
    parser.add_argument("--forbidden-root", type=Path, action="append", default=[])
    args = parser.parse_args(argv)

    quotas = dict(DEFAULT_QUOTAS)
    quotas.update(dict(args.quota))
    records = load_manifest_records(args.manifest)
    summary = write_review_artifacts(
        records,
        args.output_dir,
        quotas=quotas,
        forbidden_roots=args.forbidden_root,
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
