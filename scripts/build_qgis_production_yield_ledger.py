"""Build a read-only yield ledger for QGIS data-production lanes.

The ledger compares existing packages and candidate packets without changing
authority, training data, or extractor behavior.  It is deliberately a census
tool: admission decisions remain owned by the existing gates.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable

SCHEMA = "gis_recommend.qgis_production_yield_ledger.v1"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if path.suffix.lower() == ".json":
        value = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(value, list) and all(isinstance(item, dict) for item in value):
            return value
        raise ValueError(f"{path} is metadata JSON, not a row list; pass a JSONL row artifact")
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_no} is not a JSON object")
            rows.append(value)
    return rows


def _first(row: dict[str, Any], *keys: str) -> str:
    for key in keys:
        value = row.get(key)
        if value not in (None, ""):
            return str(value)
    return ""


def _row_metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    quality = Counter()
    admission = Counter()
    task_types = Counter()
    workflow_scopes = Counter()
    source_hashes = {_first(row, "source_sha256", "source_hash", "seed_source_sha256") for row in rows}
    parent_hashes = {
        _first(row, "parent_source_sha256", "split_group_key", "source_sha256", "seed_source_sha256", "parent_workflow_id")
        for row in rows
    }
    sample_ids = {_first(row, "sample_id", "record_id", "candidate_id") for row in rows}
    pair_keys = {_first(row, "training_pair_key") for row in rows}
    dag_keys = {_first(row, "normalized_dag_key", "call_graph_key") for row in rows}
    operator_sequences: list[tuple[str, ...]] = []
    for row in rows:
        training_quality = row.get("_training_quality") or {}
        tier = _first(training_quality, "tier") or "unspecified"
        quality[tier] += 1
        weight = training_quality.get("sample_weight")
        if weight == 1.0:
            quality["Gold"] += 1
        elif weight == 0.7:
            quality["Silver"] += 1
        elif isinstance(weight, (int, float)):
            quality[f"weight_{weight:g}"] += 1
        elif row.get("training_row_emitted") is False:
            quality["not_emitted"] += 1
        state = _first(row, "training_admission", "source_training_admission") or "unspecified"
        admission[state] += 1
        metadata = row.get("task_metadata") or {}
        task_types[_first(row, "task_type") or _first(metadata, "task_type") or "Unknown"] += 1
        workflow_scopes[_first(row, "workflow_scope") or "unspecified"] += 1
        sequence = row.get("operator_sequence") or row.get("qgis_operator_chain") or row.get("chain")
        if isinstance(sequence, list):
            operator_sequences.append(tuple(str(item) for item in sequence))

    def nonempty(values: Iterable[str]) -> set[str]:
        return {value for value in values if value}

    lengths = [len(sequence) for sequence in operator_sequences]
    return {
        "rows": len(rows),
        "unique_source_sha256": len(nonempty(source_hashes)),
        "unique_parent_source_sha256": len(nonempty(parent_hashes)),
        "unique_sample_ids": len(nonempty(sample_ids)),
        "unique_training_pair_keys": len(nonempty(pair_keys)),
        "duplicate_training_pair_rows": (
            len(rows) - len(nonempty(pair_keys))
            if pair_keys
            else None
        ),
        "unique_normalized_dags": len(nonempty(dag_keys)),
        "quality_tiers": dict(sorted(quality.items())),
        "training_admission": dict(sorted(admission.items())),
        "task_types": dict(task_types.most_common()),
        "workflow_scopes": dict(sorted(workflow_scopes.items())),
        "operator_sequence_length": {
            "min": min(lengths) if lengths else None,
            "max": max(lengths) if lengths else None,
            "mean": round(sum(lengths) / len(lengths), 3) if lengths else None,
        },
    }


def build_ledger(
    packages: list[tuple[str, Path]],
    candidates: list[tuple[str, Path]],
) -> dict[str, Any]:
    entries: list[dict[str, Any]] = []
    all_sources: dict[str, set[str]] = {}
    all_pairs: dict[str, set[str]] = {}
    for kind, specs in (("package", packages), ("candidate", candidates)):
        for name, path in specs:
            rows = _read_jsonl(path)
            metrics = _row_metrics(rows)
            sources = {
                _first(row, "source_sha256", "source_hash", "seed_source_sha256")
                for row in rows
                if _first(row, "source_sha256", "source_hash", "seed_source_sha256")
            }
            pairs = {
                _first(row, "training_pair_key")
                for row in rows
                if _first(row, "training_pair_key")
            }
            all_sources[name] = sources
            all_pairs[name] = pairs
            entries.append(
                {
                    "name": name,
                    "kind": kind,
                    "path": str(path),
                    "file_sha256": _sha256(path),
                    "metrics": metrics,
                }
            )
    overlaps = []
    names = sorted(all_sources)
    for index, left in enumerate(names):
        for right in names[index + 1 :]:
            overlaps.append(
                {
                    "left": left,
                    "right": right,
                    "source_sha256_overlap": len(all_sources[left] & all_sources[right]),
                    "training_pair_key_overlap": len(all_pairs[left] & all_pairs[right]),
                }
            )
    return {
        "schema": SCHEMA,
        "scope": "read_only_qgis_production_yield_census",
        "authority_modified": False,
        "training_data_modified": False,
        "entries": entries,
        "cross_entry_overlap": overlaps,
        "next_decision": "select the lane with the best measured accepted-yield and coverage gain per review cost",
    }


def _parse_specs(values: list[str]) -> list[tuple[str, Path]]:
    specs = []
    for value in values:
        if "=" not in value:
            raise ValueError(f"expected NAME=PATH, got {value!r}")
        name, raw_path = value.split("=", 1)
        if not name or not raw_path:
            raise ValueError(f"expected NAME=PATH, got {value!r}")
        path = Path(raw_path)
        if not path.is_file():
            raise FileNotFoundError(path)
        specs.append((name, path))
    return specs


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package", action="append", default=[], metavar="NAME=JSONL")
    parser.add_argument("--candidate", action="append", default=[], metavar="NAME=JSONL")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    ledger = build_ledger(_parse_specs(args.package), _parse_specs(args.candidate))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(ledger, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({"entries": len(ledger["entries"]), "output": str(args.output)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
