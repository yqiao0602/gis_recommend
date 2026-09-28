#!/usr/bin/env python3
"""Census source-backed payload facts for strict point-geometry macros."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

RULE_ID = "qgis-api-point-geometry-payload-census-v1"
POINT_CONSTRUCTORS = {"qgspoint", "qgspointxy"}


def payload_family(row: dict[str, Any]) -> str:
    calls = {
        str(value).rsplit(".", 1)[-1].lower()
        for value in row.get("point_factory_argument_call_names") or []
    }
    if calls.intersection(POINT_CONSTRUCTORS):
        return "coordinate_constructor"
    return "prebuilt_point_object"


def build_census(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    complete = [row for row in rows if row.get("macro_status") == "complete"]
    if any(row.get("source_verification") != "verified_sha256" for row in complete):
        raise ValueError("complete point macros must be source-SHA verified")
    groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for row in complete:
        groups[(payload_family(row), str(row.get("point_factory_call") or ""))].append(row)
    census = []
    for (family, factory), members in sorted(groups.items()):
        census.append(
            {
                "schema": "gis_recommend.qgis_api_point_geometry_payload_family.v1",
                "point_geometry_rule_id": RULE_ID,
                "payload_family": family,
                "point_factory_call": factory,
                "unit_count": len(members),
                "source_sha_support": len({str(row["source_sha256"]) for row in members}),
                "normalized_body_authority_support": len(
                    {str(row["source_authority_key"]) for row in members}
                ),
                "payload_expression_examples": sorted(
                    {str(row.get("point_factory_argument_expression") or "") for row in members}
                )[:10],
                "l3_mapping_status": "not_started_payload_semantics_required",
                "training_admission": "not_granted_payload_census_only",
                "training_rows_emitted": 0,
                "llm_called": False,
            }
        )
    summary = {
        "schema": "gis_recommend.qgis_api_point_geometry_payload_census_summary.v1",
        "point_geometry_rule_id": RULE_ID,
        "input_replay_rows": len(rows),
        "complete_macro_units": len(complete),
        "complete_normalized_body_authorities": len(
            {str(row["source_authority_key"]) for row in complete}
        ),
        "payload_family_counts": {
            family: sum(1 for row in complete if payload_family(row) == family)
            for family in sorted({payload_family(row) for row in complete})
        },
        "l3_mapping_rows": 0,
        "training_rows_emitted": 0,
        "training_admission": "not_granted_payload_census_only",
        "llm_called": False,
    }
    return census, summary


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", dir=path.parent, delete=False) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)


def _write_json(path: Path, value: Any) -> None:
    _atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    _atomic_write(path, "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    census, summary = build_census(_read_jsonl(args.replay))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    census_path = args.output_dir / "payload_family_census_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    _write_jsonl(census_path, census)
    _write_json(summary_path, summary)
    _write_json(
        args.output_dir / "hash_ledger_v1.json",
        {
            "schema": "gis_recommend.hash_ledger.v1",
            "inputs": {"replay": {"path": str(args.replay), "sha256": _sha256(args.replay)}},
            "artifacts": {
                path.name: {"bytes": path.stat().st_size, "sha256": _sha256(path)}
                for path in (census_path, summary_path)
            },
        },
    )
    print(summary_path.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
