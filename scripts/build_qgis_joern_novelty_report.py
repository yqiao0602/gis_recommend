#!/usr/bin/env python3
"""Build source-grounded novelty and promotion evidence for a Joern pilot."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from gis_recommend.data.qgis_joern_novelty import build_novelty_report


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    partial = path.with_suffix(path.suffix + ".partial")
    partial.write_text(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    partial.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage-root", type=Path, required=True)
    args = parser.parse_args()
    authority_rows = _read_jsonl(args.stage_root / "authority_baseline.jsonl")
    joern_rows = _read_jsonl(args.stage_root / "joern_normalized.jsonl")
    authorities = {str(row["record_id"]): row for row in authority_rows}
    joern_ids = {str(row["record_id"]) for row in joern_rows}
    if set(authorities) != joern_ids:
        raise ValueError("authority and Joern record sets differ")
    source_texts = {
        record_id: (
            args.stage_root / "sources" / str(authority["staged_filename"])
        ).read_text(encoding="utf-8", errors="replace")
        for record_id, authority in authorities.items()
    }
    report, promotion = build_novelty_report(
        joern_rows,
        authorities=authorities,
        source_texts=source_texts,
    )
    _write_json(args.stage_root / "novelty_report.json", report)
    _write_json(args.stage_root / "promotion_families.json", promotion)
    print(
        json.dumps(
            {
                "complete_rows": report["complete_rows"],
                "cross_function_novelty_rows": report[
                    "cross_function_novelty_rows"
                ],
                "local_only_complete_rows": report["local_only_complete_rows"],
                "families": promotion["families"],
                "training_rows_emitted": 0,
            },
            sort_keys=True,
            separators=(",", ":"),
        )
    )


if __name__ == "__main__":
    main()
