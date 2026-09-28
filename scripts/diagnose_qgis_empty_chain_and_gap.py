#!/usr/bin/env python3
"""Server-side diagnosis for step 4 (empty-chain rows) and step 5 (gap support).

Runs the feature extractor over read-only /home/yll sources:
- empty-chain rows: why did the extractor produce zero operators
  (dynamic ID, helper-scoped call, no processing call, parse failure)
- gap operators: source-row support and unique raw-content support
No authority change, no training rows, no LLM.
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gis_recommend.data.qgis_conversion_features import extract_conversion_features  # noqa: E402


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--empty-chain-ids", type=Path)
    parser.add_argument("--gap-operators", type=Path)
    parser.add_argument("--source-root", type=Path, default=Path("/home/yll"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    manifest = [
        json.loads(line)
        for line in args.manifest.read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]
    by_id = {str(row.get("record_id")): row for row in manifest}
    root = str(args.source_root).rstrip("/")

    result: dict[str, Any] = {}

    if args.empty_chain_ids:
        ids = {line.strip() for line in args.empty_chain_ids.read_text(encoding="utf-8").splitlines() if line.strip()}
        reasons: Counter[str] = Counter()
        per_row: list[dict[str, Any]] = []
        for record_id in sorted(ids):
            row = by_id.get(record_id)
            if row is None:
                reasons["not_in_manifest"] += 1
                per_row.append({"record_id": record_id, "reason": "not_in_manifest"})
                continue
            raw = str(row.get("source_path") or "")
            path = Path(raw) if raw.startswith(root) else args.source_root / raw.lstrip("/")
            if not path.is_file():
                reasons["source_missing"] += 1
                per_row.append({"record_id": record_id, "reason": "source_missing"})
                continue
            source = path.read_text(encoding="utf-8-sig", errors="replace")
            try:
                extracted = extract_conversion_features(source, call_sites=None)
                data = extracted.data
            except Exception as exc:  # noqa: BLE001
                reasons["extractor_crash"] += 1
                per_row.append({"record_id": record_id, "reason": f"extractor_crash:{type(exc).__name__}"})
                continue
            ops = data.get("operator_ids") or []
            if ops:
                reasons["has_operators_now"] += 1
                per_row.append({"record_id": record_id, "reason": "has_operators_now", "operator_ids": ops})
                continue
            if data.get("parse_status") != "parsed":
                reasons["unparseable"] += 1
                per_row.append({"record_id": record_id, "reason": "unparseable"})
                continue
            calls = data.get("all_processing_call_count") or data.get("processing_call_count") or 0
            dynamic = data.get("dynamic_operator_id_count") or 0
            if dynamic:
                reasons["dynamic_operator_ids"] += 1
                per_row.append({"record_id": record_id, "reason": "dynamic_operator_ids", "dynamic_count": dynamic})
            elif calls and not ops:
                reasons["calls_but_no_literal_operator"] += 1
                per_row.append({"record_id": record_id, "reason": "calls_but_no_literal_operator", "call_count": calls})
            else:
                reasons["no_processing_call"] += 1
                per_row.append({"record_id": record_id, "reason": "no_processing_call"})
        result["empty_chain"] = {"rows": len(ids), "reasons": dict(reasons), "per_row": per_row}

    if args.gap_operators:
        operators = [line.strip() for line in args.gap_operators.read_text(encoding="utf-8").splitlines() if line.strip()]
        support: dict[str, dict[str, int]] = {}
        content_seen: dict[str, set[str]] = {}
        for row in manifest:
            raw = str(row.get("source_path") or "")
            path = Path(raw) if raw.startswith(root) else args.source_root / raw.lstrip("/")
            if not path.is_file():
                continue
            source = path.read_text(encoding="utf-8", errors="replace")
            try:
                extracted = extract_conversion_features(source, call_sites=None)
                found = set(extracted.data.get("operator_ids") or [])
            except Exception:  # noqa: BLE001
                continue
            content_sha = str(row.get("content_sha256") or row.get("source_sha256") or "")
            for op in operators:
                if op in found:
                    entry = support.setdefault(op, {"source_rows": 0, "unique_content": 0})
                    entry["source_rows"] += 1
                    content_seen.setdefault(op, set()).add(content_sha)
        for op, entry in support.items():
            entry["unique_content"] = len(content_seen.get(op, set()))
        result["gap_support"] = {
            "operators": len(operators),
            "support": dict(sorted(support.items(), key=lambda kv: (-kv[1]["source_rows"], kv[0]))),
        }

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: v for k, v in result.items() if k != "per_row"}, ensure_ascii=False, indent=2)[:3000])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
