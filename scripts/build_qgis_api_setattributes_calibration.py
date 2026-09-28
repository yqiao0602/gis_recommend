#!/usr/bin/env python3
"""Select a source-SHA-disjoint setattributes calibration manifest.

Family: producers=[] mutations=['setattributes'] sink='addfeature'
(the largest mutation-only composite family, 575 source shas / 883 units).
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections import defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

RULE_ID = "qgis-api-setattributes-calibration-selection-v1"
FAMILY_MUTATIONS = ("setattributes",)
FAMILY_SINK = "addfeature"


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
    rows: list[dict[str, Any]], *, sample_size: int, seed: int
) -> list[dict[str, Any]]:
    eligible = [
        row
        for row in rows
        if not (row.get("producer_signature") or [])
        and tuple(sorted(row.get("mutation_signature") or [])) == FAMILY_MUTATIONS
        and row.get("sink_signature") == FAMILY_SINK
    ]
    by_sha: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in eligible:
        source_sha = str(row.get("source_sha256") or "")
        if len(source_sha) != 64:
            raise ValueError("setattributes row has invalid source SHA")
        by_sha[source_sha].append(row)
    representatives = [
        min(
            members,
            key=lambda row: (
                _signature(row),
                str(row.get("unit_id") or ""),
            ),
        )
        for _, members in sorted(by_sha.items())
    ]
    if len(representatives) < sample_size:
        raise ValueError(
            f"setattributes source support {len(representatives)} < {sample_size}"
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
    ordered_signatures = sorted(
        queues,
        key=lambda value: hashlib.sha256(f"{seed}:{value}".encode()).hexdigest(),
    )
    selected: list[dict[str, Any]] = []
    while len(selected) < sample_size:
        progressed = False
        for signature in ordered_signatures:
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
            "schema": "gis_recommend.qgis_api_setattributes_calibration_manifest.v1",
            "setattributes_rule_id": RULE_ID,
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
    _atomic_write(
        path,
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--priority-units", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--sample-size", type=int, default=200)
    parser.add_argument("--seed", type=int, default=20260810)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    selected = select_calibration_rows(
        _read_jsonl(args.priority_units),
        sample_size=args.sample_size,
        seed=args.seed,
    )
    if len({row["source_sha256"] for row in selected}) != len(selected):
        raise AssertionError("selection is not source-SHA disjoint")
    signature_counts: dict[str, int] = defaultdict(int)
    for row in selected:
        signature_counts[str(row["selection_signature"])] += 1
    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest = args.output_dir / "setattributes_calibration_manifest_v1.jsonl"
    _write_jsonl(manifest, selected)
    summary_path = args.output_dir / "summary_v1.json"
    _write_json(
        summary_path,
        {
            "schema": "gis_recommend.qgis_api_setattributes_calibration_selection_summary.v1",
            "setattributes_rule_id": RULE_ID,
            "mutation_signature": list(FAMILY_MUTATIONS),
            "sink_signature": FAMILY_SINK,
            "selected_source_rows": len(selected),
            "selected_source_sha_unique": len({row["source_sha256"] for row in selected}),
            "selection_signature_count": len(signature_counts),
            "selection_signature_counts": dict(sorted(signature_counts.items())),
            "selection_seed": args.seed,
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
                "priority_units": {
                    "path": str(args.priority_units),
                    "sha256": _sha256(args.priority_units),
                }
            },
            "artifacts": {
                path.name: {"bytes": path.stat().st_size, "sha256": _sha256(path)}
                for path in (manifest, summary_path)
            },
        },
    )
    print((args.output_dir / "summary_v1.json").read_text(encoding="utf-8"))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
