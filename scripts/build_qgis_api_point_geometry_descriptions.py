#!/usr/bin/env python3
"""Build source-fact Chinese descriptions for point-coordinate macro proposals."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections.abc import Iterable
from pathlib import Path
from typing import Any

DESCRIPTION_BY_ORIGIN = {
    "iterated_record_coordinate_fields": "从迭代记录的坐标字段创建点要素并写入目标图层。",
    "literal_coordinate_pair": "根据源码中的固定坐标创建点要素并写入目标图层。",
    "derived_or_unresolved_coordinates": "根据源码中的坐标对创建点要素并写入目标图层。",
}


def build_descriptions(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    descriptions = []
    for row in rows:
        if row.get("training_row_emitted") is not False:
            raise ValueError("description input must not emit training rows")
        origin = str(row.get("coordinate_origin_kind") or "")
        text = DESCRIPTION_BY_ORIGIN.get(origin)
        if text is None:
            raise ValueError(f"unsupported coordinate origin: {origin}")
        descriptions.append(
            {
                **row,
                "schema": "gis_recommend.qgis_api_point_geometry_description_candidate.v1",
                "task_description_zh": text,
                "description_fact_basis": origin,
                "description_fidelity": "passed_source_fact_only",
                "llm_called": False,
                "training_admission": "not_granted_taxonomy_proposal_only",
                "training_row_emitted": False,
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
            }
        )
    return descriptions


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
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    descriptions = build_descriptions(_read_jsonl(args.candidates))
    args.output_dir.mkdir(parents=True, exist_ok=True)
    description_path = args.output_dir / "point_geometry_description_candidates_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    _write_jsonl(description_path, descriptions)
    _write_json(
        summary_path,
        {
            "schema": "gis_recommend.qgis_api_point_geometry_description_summary.v1",
            "description_candidates": len(descriptions),
            "description_fidelity_passed": len(descriptions),
            "description_fact_basis_counts": {
                origin: sum(row["description_fact_basis"] == origin for row in descriptions)
                for origin in sorted({row["description_fact_basis"] for row in descriptions})
            },
            "llm_called": False,
            "l3_mapping_rows": 0,
            "training_rows_emitted": 0,
            "training_admission": "not_granted_taxonomy_proposal_only",
        },
    )
    _write_json(
        args.output_dir / "hash_ledger_v1.json",
        {
            "schema": "gis_recommend.hash_ledger.v1",
            "inputs": {"candidates": {"path": str(args.candidates), "sha256": _sha256(args.candidates)}},
            "artifacts": {
                path.name: {"bytes": path.stat().st_size, "sha256": _sha256(path)}
                for path in (description_path, summary_path)
            },
        },
    )
    print(summary_path.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
