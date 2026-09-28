#!/usr/bin/env python3
"""Build every mapping-complete stable101 QGIS record from versioned authorities."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _delta_mapping(value: dict) -> dict[str, str]:
    result: dict[str, str] = {}
    for field in ("alias_mappings", "restored_l3_mappings"):
        result.update(
            {
                str(operator).lower(): str(code)
                for operator, code in (value.get(field) or {}).items()
            }
        )
    return result


def _crosswalk_mapping(value: dict) -> dict[str, str]:
    return {
        str(operator).lower(): str(entry["l3_code"])
        for operator, entry in (value.get("entries") or {}).items()
        if isinstance(entry, dict)
        and entry.get("bridge_type") == "l3_bridge"
        and entry.get("status") == "accepted"
        and str(entry.get("l3_code", "")).startswith("L3_")
    }


def build(
    chain_dataset: Path,
    crosswalk_path: Path,
    stable98_delta_path: Path,
    stable101_delta_path: Path,
) -> tuple[list[dict], dict]:
    crosswalk = _read_json(crosswalk_path)
    stable98_delta = _read_json(stable98_delta_path)
    stable101_delta = _read_json(stable101_delta_path)
    mapping = {
        **_crosswalk_mapping(crosswalk),
        **_delta_mapping(stable98_delta),
        **_delta_mapping(stable101_delta),
    }
    records = []
    for record_index, line in enumerate(
        chain_dataset.read_text(encoding="utf-8").splitlines(), start=1
    ):
        if not line.strip():
            continue
        source_row = json.loads(line)
        operators = [
            str(operator).strip().lower()
            for operator in source_row.get("qgis_ops", [])
            if str(operator).strip()
        ]
        if not operators or any(operator not in mapping for operator in operators):
            continue
        identity = json.dumps(
            source_row, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        records.append(
            {
                "record_index": record_index,
                "record_sha256": hashlib.sha256(identity.encode()).hexdigest(),
                "qgis_ops": operators,
                "proposed_l3_sequence": [mapping[operator] for operator in operators],
                "task_text": source_row.get("task_text", ""),
                "source": source_row.get("source", ""),
                "quality": source_row.get("quality", {}),
                "operator_names": source_row.get("operator_names", []),
                "training_targets": source_row.get("training_targets", []),
                "mapping_authority": "stable101_composed_draft_v1",
                "training_admission": "not_granted_source_replay_only",
            }
        )
    summary = {
        "schema": "gis_recommend.qgis_stable101_complete_records.v1",
        "complete_records": len(records),
        "complete_unique_chains": len(
            {tuple(row["qgis_ops"]) for row in records}
        ),
        "complete_unique_record_sha": len(
            {row["record_sha256"] for row in records}
        ),
        "mapping_operator_count": len(mapping),
        "training_admission": "not_granted_source_replay_only",
        "training_rows_emitted": 0,
    }
    return records, summary


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser()
    parser.add_argument("--chain-dataset", type=Path, required=True)
    parser.add_argument("--crosswalk", type=Path, required=True)
    parser.add_argument("--stable98-delta", type=Path, required=True)
    parser.add_argument("--stable101-delta", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-records", type=int, default=1442)
    parser.add_argument("--expected-unique-chains", type=int, default=449)
    args = parser.parse_args(argv)
    rows, summary = build(
        args.chain_dataset,
        args.crosswalk,
        args.stable98_delta,
        args.stable101_delta,
    )
    if (
        summary["complete_records"] != args.expected_records
        or summary["complete_unique_chains"] != args.expected_unique_chains
    ):
        raise ValueError(
            "stable101 complete-pool authority mismatch: "
            f"{summary['complete_records']} records / "
            f"{summary['complete_unique_chains']} chains"
        )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    records_path = args.output_dir / "complete_records.jsonl"
    summary_path = args.output_dir / "complete_summary.json"
    records_path.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    return {"records": records_path, "summary": summary_path}


if __name__ == "__main__":
    main()
