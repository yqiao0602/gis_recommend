#!/usr/bin/env python3
"""Freeze the source-reviewed stable106 taxonomy and mapping authority."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
import sys
from typing import Any, Iterable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_qgis_processing_mapping_gap_stable106 import (
    CORE_MAPPINGS,
    EXISTING_ALIASES,
)


def adjudicate(
    adjudications: list[dict[str, Any]],
    extension: dict[str, Any],
    replay: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    expected = {**CORE_MAPPINGS, **EXISTING_ALIASES}
    reviewed = {str(row.get("operator_id")): row for row in adjudications}
    additions = {
        str(code): int(token)
        for code, token in (extension.get("proposed_code_to_id_additions") or {}).items()
    }
    restored = {str(row.get("code")): row for row in extension.get("restored_l3") or []}

    if extension.get("proposed_taxonomy") != "stable106":
        raise ValueError("expected stable106 extension")
    if set(additions) != set(CORE_MAPPINGS.values()) or set(restored) != set(additions):
        raise ValueError("stable106 extension does not match the five reviewed classes")
    if set(additions.values()) != set(range(101, 106)):
        raise ValueError("stable106 additions must use contiguous token IDs 101..105")

    replayed_operators = {
        str(operator)
        for row in replay
        if row.get("source_verification") == "verified_sha256"
        and row.get("call_span_verification") == "verified_processing_calls"
        for operator in row.get("operator_ids") or []
    }
    rows: list[dict[str, Any]] = []
    for operator, code in expected.items():
        source = reviewed.get(operator)
        decision = (
            "existing_stable101_alias"
            if operator in EXISTING_ALIASES
            else "core_taxonomy_candidate"
        )
        if not source or source.get("decision") != decision:
            raise ValueError(f"missing reviewed decision for {operator}")
        if source.get("candidate_l3_code") != code:
            raise ValueError(f"reviewed L3 mismatch for {operator}")
        verified_samples = [
            sample
            for sample in source.get("source_samples") or []
            if sample.get("source_verification") == "verified_sha256"
        ]
        if len(verified_samples) < 3:
            raise ValueError(f"fewer than three verified samples for {operator}")
        if operator in CORE_MAPPINGS and operator not in replayed_operators:
            raise ValueError(f"no canonical source replay contains {operator}")
        rows.append(
            {
                "schema": "gis_recommend.qgis_stable106_mapping_authority.v1",
                "operator_id": operator,
                "candidate_l3_code": code,
                "token_id": additions.get(code),
                "authority_kind": "new_stable106_class" if operator in CORE_MAPPINGS else "stable101_alias",
                "source_sample_count": len(verified_samples),
                "taxonomy_admission": "granted",
                "mapping_admission": "granted",
                "training_admission": "not_granted",
                "production_merge": "not_granted",
            }
        )
    rows.sort(key=lambda row: row["operator_id"])
    summary = {
        "schema": "gis_recommend.qgis_stable106_taxonomy_authority_summary.v1",
        "taxonomy_profile": "stable106_authority_v1",
        "accepted_mapping_count": len(rows),
        "accepted_new_class_count": len(CORE_MAPPINGS),
        "accepted_alias_count": len(EXISTING_ALIASES),
        "content_token_count": 106,
        "taxonomy_admission": "granted",
        "training_admission": "not_granted",
        "production_merge": "not_granted",
        "training_rows_emitted": 0,
    }
    return rows, summary


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", dir=path.parent, delete=False) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def _write_json(path: Path, value: Any) -> None:
    _atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    _atomic_write(path, "".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--adjudications", type=Path, required=True)
    parser.add_argument("--extension", type=Path, required=True)
    parser.add_argument("--source-replay", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    rows, summary = adjudicate(
        _read_jsonl(args.adjudications), _read_json(args.extension), _read_jsonl(args.source_replay)
    )
    authority_path = args.output_dir / "stable106_mapping_authority_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    hash_path = args.output_dir / "hash_ledger_v1.json"
    _write_jsonl(authority_path, rows)
    _write_json(summary_path, summary)
    _write_json(
        hash_path,
        {
            "schema": "gis_recommend.hash_ledger.v1",
            "inputs": {
                name: {"path": str(path), "sha256": _sha256(path)}
                for name, path in {
                    "adjudications": args.adjudications,
                    "extension": args.extension,
                    "source_replay": args.source_replay,
                }.items()
            },
            "artifacts": {
                authority_path.name: _sha256(authority_path),
                summary_path.name: _sha256(summary_path),
            },
        },
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
