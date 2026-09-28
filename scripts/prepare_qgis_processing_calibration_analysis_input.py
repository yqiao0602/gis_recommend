#!/usr/bin/env python3
"""Adapt a verified calibration packet to existing Processing boundary analyzers."""

from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path
from typing import Any


def prepare(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    prepared: list[dict[str, Any]] = []
    for source in rows:
        row = dict(source)
        lane = str(
            row.get("calibration_lane")
            or row.get("precalibration_lane")
            or row.get("route_action")
            or ""
        )
        operators = list(row.get("operator_sequence") or [])
        l3_codes = list(row.get("l3_code_sequence") or [])
        if lane not in {"recover_call_graph", "split_subworkflow", "defer_operator_resolution"}:
            raise ValueError(f"unsupported calibration lane: {lane!r}")
        if not operators or len(operators) != len(l3_codes):
            raise ValueError(f"unaligned operator/L3 evidence: {row.get('record_id')!r}")
        row["action"] = lane
        row["rule_id"] = str(row.get("route_rule_id") or "")
        row["operator_ids"] = operators
        row["mapped_l3_chain"] = l3_codes
        prepared.append(row)
    return prepared


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    rows = [json.loads(line) for line in args.input.read_text(encoding="utf-8").splitlines() if line.strip()]
    output = prepare(rows)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    content = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in output)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", dir=args.output.parent, delete=False) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
