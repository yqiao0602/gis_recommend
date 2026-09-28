#!/usr/bin/env python3
"""Select a source-SHA-disjoint polyline-geometry calibration manifest."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

FAMILY = "polyline_geometry_construction"


def _artifact_prefix(family: str) -> str:
    return family.removesuffix("_construction")


def _rule_id(family: str) -> str:
    return f"qgis-api-{_artifact_prefix(family).replace('_', '-')}-calibration-selection-v1"


def _signature(row: dict[str, Any]) -> str:
    return json.dumps(
        {
            "producers": row.get("producer_signature") or [],
            "mutations": row.get("mutation_signature") or [],
            "sink": row.get("sink_signature") or "",
        },
        sort_keys=True,
        separators=(",", ":"),
    )


def select_calibration_rows(
    rows: list[dict[str, Any]], *, sample_size: int, seed: int, family: str = FAMILY
) -> list[dict[str, Any]]:
    """Take one stable terminal-macro representative per source SHA."""
    eligible = [row for row in rows if row.get("semantic_family") == family]
    by_sha: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in eligible:
        source_sha = str(row.get("source_sha256") or "")
        if len(source_sha) != 64:
            raise ValueError("geometry construction row has invalid source SHA")
        by_sha[source_sha].append(row)
    representatives = [
        min(members, key=lambda row: (_signature(row), str(row.get("unit_id") or "")))
        for _, members in sorted(by_sha.items())
    ]
    if len(representatives) < sample_size:
        raise ValueError(
            f"geometry construction source support {len(representatives)} < {sample_size}"
        )
    by_signature: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in representatives:
        by_signature[_signature(row)].append(row)
    queues = {
        signature: sorted(
            members,
            key=lambda row: hashlib.sha256(
                f"{seed}:{row['source_sha256']}:{row['unit_id']}".encode()
            ).hexdigest(),
        )
        for signature, members in by_signature.items()
    }
    signatures = sorted(
        queues, key=lambda value: hashlib.sha256(f"{seed}:{value}".encode()).hexdigest()
    )
    selected: list[dict[str, Any]] = []
    while len(selected) < sample_size:
        progressed = False
        for signature in signatures:
            if not queues[signature]:
                continue
            selected.append(queues[signature].pop(0))
            progressed = True
            if len(selected) == sample_size:
                break
        if not progressed:
            raise AssertionError("selection queues exhausted unexpectedly")
    return [
        {
            **row,
            "schema": f"gis_recommend.qgis_api_{_artifact_prefix(family)}_calibration_manifest.v1",
            "geometry_construction_rule_id": _rule_id(family),
            "target_index": index,
            "selection_signature": _signature(row),
            "selection_stage": "pre_source_replay",
            "normalized_source_body_sha256": "",
            "source_authority_key": "",
            "training_admission": "not_granted_calibration_only",
            "training_row_emitted": False,
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
            "llm_called": False,
        }
        for index, row in enumerate(selected, start=1)
    ]


def build_full_population(
    rows: list[dict[str, Any]], *, family: str = FAMILY
) -> list[dict[str, Any]]:
    """Keep every discovery unit; source deduplication happens after replay."""
    eligible = sorted(
        (row for row in rows if row.get("semantic_family") == family),
        key=lambda row: (str(row.get("source_sha256") or ""), str(row.get("unit_id") or "")),
    )
    if not eligible:
        raise ValueError("geometry construction full population is empty")
    if any(len(str(row.get("source_sha256") or "")) != 64 for row in eligible):
        raise ValueError("geometry construction row has invalid source SHA")
    return [
        {
            **row,
            "schema": f"gis_recommend.qgis_api_{_artifact_prefix(family)}_full_population_manifest.v1",
            "geometry_construction_rule_id": _rule_id(family),
            "target_index": index,
            "selection_signature": _signature(row),
            "selection_stage": "full_population_pre_source_replay",
            "normalized_source_body_sha256": "",
            "source_authority_key": "",
            "training_admission": "not_granted_full_population_source_replay_only",
            "training_row_emitted": False,
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
            "llm_called": False,
        }
        for index, row in enumerate(eligible, start=1)
    ]


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)


def _write_json(path: Path, value: Any) -> None:
    _atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    _atomic_write(path, "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--semantic-priority-units", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--sample-size", type=int, default=200)
    parser.add_argument("--seed", type=int, default=20260805)
    parser.add_argument("--mode", choices=("calibration", "full"), default="calibration")
    parser.add_argument("--family", default=FAMILY)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    input_rows = _read_jsonl(args.semantic_priority_units)
    prefix = _artifact_prefix(args.family)
    selected = (
        select_calibration_rows(
            input_rows, sample_size=args.sample_size, seed=args.seed, family=args.family
        )
        if args.mode == "calibration"
        else build_full_population(input_rows, family=args.family)
    )
    if args.mode == "calibration" and len({row["source_sha256"] for row in selected}) != len(selected):
        raise AssertionError("selection is not source-SHA disjoint")
    counts: dict[str, int] = defaultdict(int)
    for row in selected:
        counts[str(row["selection_signature"])] += 1
    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest = args.output_dir / (
        f"{prefix}_calibration_manifest_v1.jsonl"
        if args.mode == "calibration"
        else f"{prefix}_full_population_manifest_v1.jsonl"
    )
    summary = args.output_dir / "summary_v1.json"
    _write_jsonl(manifest, selected)
    _write_json(
        summary,
        {
            "schema": "gis_recommend.qgis_api_geometry_construction_calibration_selection_summary.v1",
            "geometry_construction_rule_id": _rule_id(args.family),
            "semantic_family": args.family,
            "selection_mode": args.mode,
            "selected_source_rows": len(selected),
            "selected_source_sha_unique": len({row["source_sha256"] for row in selected}),
            "selection_signature_count": len(counts),
            "selection_signature_counts": dict(sorted(counts.items())),
            "selection_seed": args.seed if args.mode == "calibration" else None,
            "normalized_body_authorities": "not_computed_requires_server_source_replay",
            "training_rows_emitted": 0,
            "training_admission": "not_granted_calibration_only",
            "llm_called": False,
        },
    )
    _write_json(
        args.output_dir / "hash_ledger_v1.json",
        {
            "schema": "gis_recommend.hash_ledger.v1",
            "inputs": {
                "semantic_priority_units": {
                    "path": str(args.semantic_priority_units),
                    "sha256": _sha256(args.semantic_priority_units),
                }
            },
            "artifacts": {
                path.name: {"bytes": path.stat().st_size, "sha256": _sha256(path)}
                for path in (manifest, summary)
            },
        },
    )
    print(summary.read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
