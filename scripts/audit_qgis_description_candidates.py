#!/usr/bin/env python3
"""Audit existing QGIS task descriptions against extracted operator evidence."""

from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gis_recommend.data.qgis_description_audit import (  # noqa: E402
    analyze_steps,
    classify_candidate,
    normalize_operation,
    summarize_audit,
)
from gis_recommend.data.qgis_pilot import assert_write_allowed, file_sha256  # noqa: E402


def _load_strict_mapping(
    id_mappings_path: Path,
    crosswalk_path: Path,
    *,
    expected_l3_count: int | None = None,
) -> tuple[dict[str, str], int]:
    id_mappings = json.loads(id_mappings_path.read_text(encoding="utf-8"))
    valid_l3 = set((id_mappings.get("l3") or {}).keys())
    if expected_l3_count is not None and len(valid_l3) != expected_l3_count:
        raise ValueError(
            f"L3 authority contains {len(valid_l3)} codes; expected {expected_l3_count}"
        )
    crosswalk = json.loads(crosswalk_path.read_text(encoding="utf-8"))
    mapping = {}
    for operation, entry in (crosswalk.get("entries") or {}).items():
        if str(entry.get("status") or "").lower() != "accepted":
            continue
        l3_code = str(entry.get("l3_code") or "")
        if l3_code in valid_l3:
            mapping[normalize_operation(operation)] = l3_code
    return mapping, len(valid_l3)


def _read_steps(path: Path) -> list[dict]:
    with path.open(encoding="utf-8-sig", errors="replace", newline="") as handle:
        return list(csv.DictReader(handle))


def _group_priority(group_name: str) -> tuple[int, str]:
    name = group_name.lower()
    if "model_tutorial" in name:
        rank = 0
    elif "processing_chained" in name:
        rank = 1
    elif "strict_multistep" in name:
        rank = 2
    elif "l1_near_strict" in name:
        rank = 3
    elif "l2_general" in name:
        rank = 4
    elif "l3_support" in name:
        rank = 6
    else:
        rank = 5
    return rank, group_name


def _resolve_candidate_artifacts(
    record: dict,
    strict_mapping: dict[str, str],
) -> tuple[dict | None, dict]:
    candidates = record.get("artifact_candidates") or {}
    group_analyses = {}
    ast_hashes = {}
    for group_name, artifacts in candidates.items():
        step_paths = artifacts.get("steps") or []
        if len(step_paths) == 1 and Path(step_paths[0]).is_file():
            group_analyses[group_name] = analyze_steps(
                _read_steps(Path(step_paths[0])), strict_mapping
            )
        ast_paths = artifacts.get("ast") or []
        if len(ast_paths) == 1 and Path(ast_paths[0]).is_file():
            ast_hashes[group_name] = file_sha256(Path(ast_paths[0]))

    group_count = int(record.get("candidate_group_count") or 0)
    equivalent_mirrors = (
        group_count > 1
        and len(ast_hashes) == group_count
        and len(set(ast_hashes.values())) == 1
    )
    can_select = group_count == 1 or equivalent_mirrors
    selected_group = None
    if can_select and group_analyses:
        selected_group = min(group_analyses, key=_group_priority)
    return (
        group_analyses.get(selected_group) if selected_group else None,
        {
            "equivalent_mirror_provenance": equivalent_mirrors,
            "selected_extraction_group": selected_group,
            "normalized_ast_sha256s": ast_hashes,
        },
    )


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--id-mappings", type=Path, required=True)
    parser.add_argument("--crosswalk", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--allowed-write-root", type=Path, action="append", required=True)
    parser.add_argument("--max-chain-length", type=int, default=15)
    parser.add_argument("--expected-l3-count", type=int)
    args = parser.parse_args(argv)

    output_dir = assert_write_allowed(args.output_dir, args.allowed_write_root)
    output_dir.mkdir(parents=True, exist_ok=True)
    strict_mapping, l3_profile_size = _load_strict_mapping(
        args.id_mappings,
        args.crosswalk,
        expected_l3_count=args.expected_l3_count,
    )

    audited = []
    with args.candidates.open(encoding="utf-8", errors="replace") as handle:
        for line in handle:
            record = json.loads(line)
            step_analysis, provenance = _resolve_candidate_artifacts(
                record, strict_mapping
            )
            classified_record = {**record, **provenance}
            audit = classify_candidate(
                classified_record,
                step_analysis,
                max_chain_length=args.max_chain_length,
            )
            audited.append(
                {
                    "facts_row_id": record.get("facts_row_id"),
                    "source_script": record.get("source_script"),
                    "task_type": record.get("task_type"),
                    "task_name": record.get("task_name"),
                    "task_description": record.get("task_description"),
                    "normalized_ast_sha256s": provenance["normalized_ast_sha256s"],
                    **audit,
                }
            )

    records_path = assert_write_allowed(output_dir / "candidate_audit.jsonl", args.allowed_write_root)
    summary_path = assert_write_allowed(output_dir / "summary.json", args.allowed_write_root)
    ledger_path = assert_write_allowed(output_dir / "write_ledger.json", args.allowed_write_root)
    _write_jsonl(records_path, audited)
    summary = {
        "schema": "gis_recommend.qgis_description_candidate_audit.v1",
        "l3_profile_size": l3_profile_size,
        "strict_l3_operation_mappings": len(strict_mapping),
        "max_chain_length": args.max_chain_length,
        **summarize_audit(audited),
    }
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    ledger = {
        "source_files": {
            "candidates": {"path": str(args.candidates), "sha256": file_sha256(args.candidates)},
            "id_mappings": {"path": str(args.id_mappings), "sha256": file_sha256(args.id_mappings)},
            "crosswalk": {"path": str(args.crosswalk), "sha256": file_sha256(args.crosswalk)},
        },
        "outputs": [
            {"path": str(path), "sha256": file_sha256(path), "size": path.stat().st_size}
            for path in (records_path, summary_path)
        ],
    }
    ledger_path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
