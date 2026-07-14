#!/usr/bin/env python3
"""Build a read-only QGIS source and task-description inventory."""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gis_recommend.data.qgis_pilot import (  # noqa: E402
    PILOT_SCHEMA,
    assert_write_allowed,
    classify_description_source,
    file_sha256,
    parse_qgis_artifact_path,
)


def _stat(path: Path) -> dict:
    stat = path.stat()
    return {"path": str(path.resolve()), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}


def _root_snapshot(path: Path) -> dict:
    stat = path.stat()
    return {
        "path": str(path.resolve()),
        "mode": oct(stat.st_mode & 0o777),
        "mtime_ns": stat.st_mtime_ns,
        "device": stat.st_dev,
        "inode": stat.st_ino,
    }


def _walk_files(root: Path) -> Iterable[Path]:
    for directory, names, files in os.walk(root):
        names.sort()
        files.sort()
        base = Path(directory)
        for name in files:
            yield base / name


def load_facts(path: Path) -> tuple[list[dict], dict]:
    rows = []
    descriptions = Counter()
    filenames = Counter()
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        for index, row in enumerate(reader):
            filename = (row.get("File Name") or "").strip()
            description = (row.get("Task Description") or "").strip()
            task_name = (row.get("Task Name") or "").strip()
            rows.append(
                {
                    "facts_row_id": f"facts:{index}",
                    "source_script": filename,
                    "script_id": Path(filename).stem,
                    "task_type": (row.get("Task Type") or "").strip(),
                    "task_name": task_name,
                    "task_description": description,
                    "data_source": (row.get("DataSource") or "").strip(),
                    "geospatial_values": (row.get("Geospatial Values") or "").strip(),
                    "time_ranges": (row.get("Time Ranges") or "").strip(),
                }
            )
            filenames[filename] += 1
            descriptions[description] += 1
    return rows, {
        "path": str(path.resolve()),
        "sha256": file_sha256(path),
        "rows": len(rows),
        "unique_file_names": len(filenames),
        "duplicate_file_name_rows": sum(count - 1 for count in filenames.values() if count > 1),
        "unique_descriptions": len(descriptions),
        "blank_descriptions": descriptions.get("", 0),
    }


def scan_artifacts(extraction_root: Path) -> tuple[list[dict], list[dict]]:
    artifacts = []
    merged_tables = []
    for path in _walk_files(extraction_root):
        if path.name == "merged_nodes_process.csv":
            merged_tables.append(_stat(path))
            continue
        parsed = parse_qgis_artifact_path(path, extraction_root)
        if parsed is None:
            continue
        parsed.update({"size": path.stat().st_size, "mtime_ns": path.stat().st_mtime_ns})
        artifacts.append(parsed)
    return artifacts, merged_tables


def join_facts_to_artifacts(facts: list[dict], artifacts: list[dict]) -> tuple[list[dict], dict]:
    by_script: dict[str, list[dict]] = defaultdict(list)
    for artifact in artifacts:
        by_script[artifact["script_id"]].append(artifact)
    rows = []
    group_counts = Counter()
    for fact in facts:
        candidates = by_script.get(fact["script_id"], [])
        groups: dict[str, dict[str, list[str]]] = defaultdict(lambda: defaultdict(list))
        for candidate in candidates:
            groups[candidate["extraction_group"]][candidate["artifact_kind"]].append(
                candidate["source_path"]
            )
        group_count = len(groups)
        group_counts[group_count] += 1
        rows.append(
            {
                **fact,
                "candidate_group_count": group_count,
                "collision_state": (
                    "missing" if group_count == 0 else "unique_group" if group_count == 1 else "requires_path_hash_resolution"
                ),
                "artifact_candidates": {
                    group: {kind: sorted(paths) for kind, paths in sorted(kinds.items())}
                    for group, kinds in sorted(groups.items())
                },
            }
        )
    return rows, {
        "matched_rows": sum(count for groups, count in group_counts.items() if groups > 0),
        "missing_rows": group_counts.get(0, 0),
        "unique_group_rows": group_counts.get(1, 0),
        "multi_group_rows": sum(count for groups, count in group_counts.items() if groups > 1),
        "candidate_group_count_distribution": dict(sorted(group_counts.items())),
    }


def scan_description_sources(roots: list[Path]) -> tuple[list[dict], dict]:
    rows = []
    counts = Counter()
    for root in roots:
        for path in _walk_files(root):
            source_type = classify_description_source(path)
            if source_type == "other":
                continue
            item = _stat(path)
            item.update({"source_type": source_type, "source_root": str(root.resolve())})
            if item["size"] <= 25 * 1024 * 1024:
                item["sha256"] = file_sha256(path)
            else:
                item["sha256"] = None
            rows.append(item)
            counts[source_type] += 1
    return rows, {"total": len(rows), "by_type": dict(sorted(counts.items()))}


def _write_jsonl(path: Path, rows: Iterable[dict]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def build_inventory(
    *,
    facts_path: Path,
    extraction_root: Path,
    description_roots: list[Path],
    output_dir: Path,
    allowed_write_roots: list[Path],
) -> dict:
    source_roots = [facts_path.parent, extraction_root, *description_roots]
    before = [_root_snapshot(root) for root in source_roots]
    output_dir = assert_write_allowed(output_dir, allowed_write_roots)
    output_dir.mkdir(parents=True, exist_ok=True)

    facts, facts_summary = load_facts(facts_path)
    artifacts, merged_tables = scan_artifacts(extraction_root)
    joined, join_summary = join_facts_to_artifacts(facts, artifacts)
    descriptions, description_summary = scan_description_sources(description_roots)

    artifact_path = assert_write_allowed(output_dir / "artifact_index.jsonl", allowed_write_roots)
    joined_path = assert_write_allowed(output_dir / "facts_artifact_candidates.jsonl", allowed_write_roots)
    descriptions_path = assert_write_allowed(output_dir / "description_sources.jsonl", allowed_write_roots)
    report_path = assert_write_allowed(output_dir / "inventory_report.json", allowed_write_roots)
    ledger_path = assert_write_allowed(output_dir / "write_ledger.json", allowed_write_roots)
    _write_jsonl(artifact_path, artifacts)
    _write_jsonl(joined_path, joined)
    _write_jsonl(descriptions_path, descriptions)

    kind_counts = Counter(row["artifact_kind"] for row in artifacts)
    group_counts = Counter(row["extraction_group"] for row in artifacts)
    after = [_root_snapshot(root) for root in source_roots]
    source_unchanged = before == after
    report = {
        "schema": PILOT_SCHEMA,
        "kind": "phase1_qgis_source_inventory",
        "facts": facts_summary,
        "artifacts": {
            "total": len(artifacts),
            "by_kind": dict(sorted(kind_counts.items())),
            "by_extraction_group": dict(sorted(group_counts.items())),
            "merged_nodes_process_tables": merged_tables,
        },
        "facts_artifact_join": join_summary,
        "description_sources": description_summary,
        "source_roots_before": before,
        "source_roots_after": after,
        "source_root_metadata_unchanged": source_unchanged,
        "writes_confined_to_allowlist": True,
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    ledger = {
        "schema": PILOT_SCHEMA,
        "allowed_write_roots": [str(Path(root).resolve()) for root in allowed_write_roots],
        "created_or_replaced": [
            {"path": str(path), "sha256": file_sha256(path), "size": path.stat().st_size}
            for path in [artifact_path, joined_path, descriptions_path, report_path]
        ],
        "source_root_metadata_unchanged": source_unchanged,
    }
    ledger_path.write_text(json.dumps(ledger, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--facts", type=Path, required=True)
    parser.add_argument("--extraction-root", type=Path, required=True)
    parser.add_argument("--description-root", type=Path, action="append", default=[])
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--allowed-write-root", type=Path, action="append", required=True)
    args = parser.parse_args(argv)
    report = build_inventory(
        facts_path=args.facts.resolve(),
        extraction_root=args.extraction_root.resolve(),
        description_roots=[path.resolve() for path in args.description_root],
        output_dir=args.output_dir,
        allowed_write_roots=args.allowed_write_root,
    )
    print(json.dumps({
        "facts": report["facts"]["rows"],
        "artifacts": report["artifacts"]["total"],
        "matched": report["facts_artifact_join"]["matched_rows"],
        "description_sources": report["description_sources"],
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
