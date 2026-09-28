"""Deterministic, read-only GEE source/facts authority inventory."""

from __future__ import annotations

import csv
from collections import defaultdict
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any, Iterable


DEFAULT_BATCHES = tuple(
    [f"data{i}0000" for i in range(1, 28)]
    + ["data280000", "data290000", "data300000", "data400000"]
)
FACT_FIELDS = (
    "File Name",
    "Task Type",
    "Task Name",
    "DataSource",
    "Geospatial Values",
    "Time Ranges",
    "Task Description",
)
_SOURCE_RE = re.compile(r"^script_(\d+)\.txt$", re.IGNORECASE)
_INVALID_SOURCE_RE = re.compile(r"^script_\s*(\d+)\s*\.txt$", re.IGNORECASE)
_FACTS_RE = re.compile(r"^facts_summary(\d+)(?:-(\d+))?\.csv$", re.IGNORECASE)

_PER_BATCH_KEYS = (
    "source_instances",
    "valid_source_filenames",
    "invalid_source_filenames",
    "canonical_sources",
    "duplicate_groups",
    "facts_rows",
    "exact_facts_joins",
    "known_mirror_instances",
    "source_duplicate_instances",
    "facts_conflicts",
    "facts_source_missing",
    "batch_range_mismatch",
    "source_facts_missing",
)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _batch_set(batches: Iterable[str] | None) -> tuple[str, ...]:
    selected = tuple(batches or DEFAULT_BATCHES)
    if not selected or any(batch not in DEFAULT_BATCHES for batch in selected):
        raise ValueError(
            "batches must be a non-empty subset of the explicit GEE batch allowlist"
        )
    requested = set(selected)
    return tuple(batch for batch in DEFAULT_BATCHES if batch in requested)


def _canonical_key(row: dict[str, Any]) -> tuple[Any, ...]:
    return (
        row["filename_status"] != "valid_source_filename",
        row["batch_name"] != "data280000",
        row["batch_name"] == "data290000",
        row["batch_name"],
        row["source_path"],
    )


def discover_source_instances(
    source_root: Path,
    batches: Iterable[str] | None = None,
) -> list[dict[str, Any]]:
    """Hash direct script files from the explicit GEE batch allowlist."""
    root = Path(source_root).resolve()
    selected = _batch_set(batches)
    missing = [batch for batch in selected if not (root / batch).is_dir()]
    if missing:
        raise ValueError(
            f"missing selected source batch directories: {', '.join(missing)}"
        )

    rows: list[dict[str, Any]] = []
    for batch in selected:
        batch_dir = root / batch
        entries = sorted(batch_dir.iterdir(), key=lambda path: path.name)
        nested = [path.name for path in entries if path.is_dir()]
        if nested:
            raise ValueError(
                f"nested source paths are not allowed in {batch}: {', '.join(nested)}"
            )
        for path in entries:
            if not path.is_file():
                continue
            match = _SOURCE_RE.fullmatch(path.name)
            invalid_match = _INVALID_SOURCE_RE.fullmatch(path.name)
            script_id = (match or invalid_match).group(1) if (match or invalid_match) else ""
            normalized_filename = f"script_{script_id}.txt" if script_id else ""
            rows.append(
                {
                    "record_key": f"{batch}/{path.name}",
                    "batch_name": batch,
                    "script_filename": path.name,
                    "script_id": script_id,
                    "normalized_filename": normalized_filename,
                    "size_bytes": path.stat().st_size,
                    "source_sha256": _sha256(path),
                    "source_path": path.relative_to(root).as_posix(),
                    "filename_status": (
                        "valid_source_filename" if match else "invalid_source_filename"
                    ),
                    "instance_status": "unclassified",
                }
            )

    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        groups[row["source_sha256"]].append(row)
    for group in groups.values():
        ordered = sorted(group, key=_canonical_key)
        has_data280000 = any(row["batch_name"] == "data280000" for row in group)
        for index, row in enumerate(ordered):
            if index == 0:
                row["instance_status"] = "canonical_source"
            elif row["batch_name"] == "data290000" and has_data280000:
                row["instance_status"] = "known_mirror_instance"
            else:
                row["instance_status"] = "source_duplicate_content"
    return sorted(rows, key=lambda row: row["source_path"])


def _expected_batch_from_facts_name(name: str) -> str | None:
    match = _FACTS_RE.fullmatch(name)
    if not match:
        if name.lower().startswith("facts_summary") and name.lower().endswith(".csv"):
            raise ValueError(f"unsupported facts filename: {name}")
        return None

    first = int(match.group(1))
    second = int(match.group(2)) if match.group(2) else None
    if second is not None:
        if (first, second) != (280000, 290000):
            raise ValueError(f"unsupported facts range: {name}")
        return "data280000"
    if first == 290000:
        return "data280000"
    expected = f"data{first}"
    if expected not in DEFAULT_BATCHES:
        raise ValueError(f"facts file is outside the GEE batch allowlist: {name}")
    return expected


def _facts_files(
    root: Path,
    selected: tuple[str, ...],
) -> list[tuple[Path, str]]:
    files: list[tuple[Path, str]] = []
    for path in sorted(root.iterdir(), key=lambda item: item.name):
        if not path.is_file():
            continue
        expected = _expected_batch_from_facts_name(path.name)
        if expected is not None and expected in selected:
            files.append((path, expected))
    return files


def _facts_ledger(
    facts_root: Path,
    selected: tuple[str, ...],
) -> list[dict[str, Any]]:
    root = Path(facts_root).resolve()
    rows: list[dict[str, Any]] = []
    for path, expected_batch in _facts_files(root, selected):
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            if tuple(reader.fieldnames or ()) != FACT_FIELDS:
                raise ValueError(f"{path} must have exact seven facts fields")
            for row_number, raw in enumerate(reader, start=2):
                fields = {field: (raw.get(field) or "") for field in FACT_FIELDS}
                rows.append(
                    {
                        "identity": f"{path.name}:{row_number}",
                        "facts_file": path.name,
                        "row_number": row_number,
                        "expected_batch": expected_batch,
                        **fields,
                    }
                )
    return rows


def _empty_per_batch(selected: tuple[str, ...]) -> dict[str, dict[str, int]]:
    return {
        batch: {key: 0 for key in _PER_BATCH_KEYS}
        for batch in selected
    }


def build_authority(
    source_root: Path,
    facts_root: Path,
    batches: Iterable[str] | None = None,
) -> dict[str, Any]:
    selected = _batch_set(batches)
    sources = discover_source_instances(source_root, selected)
    facts = _facts_ledger(facts_root, selected)

    valid_sources = [
        row for row in sources if row["filename_status"] == "valid_source_filename"
    ]
    by_batch_name: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in valid_sources:
        filename = row["normalized_filename"].lower()
        by_batch_name[(row["batch_name"], filename)].append(row)
        by_name[filename].append(row)

    fact_groups: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for fact in facts:
        fact_groups[(fact["expected_batch"], fact["File Name"].lower())].append(fact)
    fact_group_conflicts = {
        key: len(
            {
                json.dumps(
                    {field: item[field] for field in FACT_FIELDS},
                    ensure_ascii=False,
                    sort_keys=True,
                )
                for item in items
            }
        )
        > 1
        for key, items in fact_groups.items()
    }

    joins: list[dict[str, Any]] = []
    connected_hashes: set[str] = set()
    per_batch = _empty_per_batch(selected)
    for row in sources:
        batch_counts = per_batch[row["batch_name"]]
        batch_counts["source_instances"] += 1
        if row["filename_status"] == "valid_source_filename":
            batch_counts["valid_source_filenames"] += 1
        else:
            batch_counts["invalid_source_filenames"] += 1
        if row["instance_status"] == "known_mirror_instance":
            batch_counts["known_mirror_instances"] += 1
        elif row["instance_status"] == "source_duplicate_content":
            batch_counts["source_duplicate_instances"] += 1
    for fact in facts:
        per_batch[fact["expected_batch"]]["facts_rows"] += 1
        filename = fact["File Name"].lower()
        key = (fact["expected_batch"], filename)
        candidates = by_batch_name.get(key, [])
        if fact_group_conflicts[key]:
            status = "facts_conflict"
            authoritative = False
        elif len(candidates) == 1:
            status = "authoritative_exact_batch_join"
            authoritative = True
            connected_hashes.add(candidates[0]["source_sha256"])
        elif by_name.get(filename):
            status = "batch_range_mismatch"
            authoritative = False
        else:
            status = "facts_source_missing"
            authoritative = False

        batch_status_key = {
            "authoritative_exact_batch_join": "exact_facts_joins",
            "facts_conflict": "facts_conflicts",
            "facts_source_missing": "facts_source_missing",
            "batch_range_mismatch": "batch_range_mismatch",
        }[status]
        per_batch[fact["expected_batch"]][batch_status_key] += 1
        basename_matches = by_name.get(filename, [])
        suggestion = (
            basename_matches[0]["source_path"] if len(basename_matches) == 1 else ""
        )
        joins.append(
            {
                "identity": fact["identity"],
                "facts_file": fact["facts_file"],
                "source_path": candidates[0]["source_path"] if len(candidates) == 1 else "",
                "file_name": fact["File Name"],
                "suggested_source_path": suggestion,
                "join_status": status,
                "authoritative": authoritative,
            }
        )

    canonical_groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in sources:
        canonical_groups[row["source_sha256"]].append(row)
    canonical: list[dict[str, Any]] = []
    for source_sha256, group in sorted(canonical_groups.items()):
        ordered = sorted(group, key=_canonical_key)
        representative = ordered[0]
        per_batch[representative["batch_name"]]["canonical_sources"] += 1
        if len(group) > 1:
            per_batch[representative["batch_name"]]["duplicate_groups"] += 1
        canonical.append({**representative, "instances": [dict(item) for item in ordered]})
        if (
            representative["filename_status"] == "valid_source_filename"
            and source_sha256 not in connected_hashes
        ):
            per_batch[representative["batch_name"]]["source_facts_missing"] += 1
            joins.append(
                {
                    "identity": representative["record_key"],
                    "facts_file": "",
                    "source_path": representative["source_path"],
                    "file_name": representative["normalized_filename"],
                    "suggested_source_path": "",
                    "join_status": "source_facts_missing",
                    "authoritative": False,
                }
            )

    joins.sort(key=lambda row: (row["identity"], row["join_status"]))
    status_counts: dict[str, int] = defaultdict(int)
    for row in sources:
        status_counts[row["filename_status"]] += 1
        status_counts[row["instance_status"]] += 1
    for row in joins:
        status_counts[row["join_status"]] += 1

    duplicate_groups = sum(len(group) > 1 for group in canonical_groups.values())
    duplicate_extra_instances = sum(
        len(group) - 1 for group in canonical_groups.values() if len(group) > 1
    )
    exact_facts_joins = status_counts["authoritative_exact_batch_join"]
    summary = {
        "schema": "gis_recommend.gee_corpus_authority_summary.v3",
        "identity_inventory_only": True,
        "facts_coverage_unit": "source_content_sha256_with_exact_instance_join",
        "training_admission": "not_granted",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "batches": list(selected),
        "counts": {
            "source_instances": len(sources),
            "canonical_sources": len(canonical),
            "unique_source_contents": len(canonical),
            "duplicate_groups": duplicate_groups,
            "duplicate_extra_instances": duplicate_extra_instances,
            "facts_rows": len(facts),
            "exact_facts_joins": exact_facts_joins,
            "join_rows": len(joins),
        },
        "status_counts": dict(sorted(status_counts.items())),
        "per_batch": per_batch,
    }
    return {
        "source_instances": sources,
        "canonical_sources": sorted(
            canonical,
            key=lambda row: (row["source_sha256"], row["source_path"]),
        ),
        "facts_ledger": sorted(facts, key=lambda row: row["identity"]),
        "join_ledger": joins,
        "summary": summary,
    }


def _jsonl(rows: list[dict[str, Any]]) -> str:
    return "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
        for row in rows
    )


def _render_report(summary: dict[str, Any]) -> str:
    lines = [
        "# GEE Corpus Authority Manifest",
        "",
        "Identity inventory only; no training, validation, test, or production admission is granted.",
        "",
        "## Counts",
        "",
    ]
    lines.extend(f"- {key}: {value}" for key, value in summary["counts"].items())
    lines.extend(["", "## Status Counts", ""])
    lines.extend(
        f"- {key}: {value}" for key, value in summary["status_counts"].items()
    )
    lines.extend(["", "## Per Batch", ""])
    for batch, counts in summary["per_batch"].items():
        rendered = ", ".join(f"{key}={value}" for key, value in counts.items())
        lines.append(f"- {batch}: {rendered}")
    return "\n".join(lines) + "\n"


def write_manifest_atomic(
    result: dict[str, Any],
    output_dir: Path,
) -> dict[str, Path]:
    output = Path(output_dir).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    temp = Path(tempfile.mkdtemp(prefix=f".{output.name}.tmp-", dir=output.parent))
    backup: Path | None = None
    published = False
    try:
        payloads = {
            "source_instances.jsonl": _jsonl(result["source_instances"]),
            "canonical_sources.jsonl": _jsonl(result["canonical_sources"]),
            "facts_ledger.jsonl": _jsonl(result["facts_ledger"]),
            "join_ledger.jsonl": _jsonl(result["join_ledger"]),
            "summary.json": json.dumps(
                result["summary"], ensure_ascii=False, indent=2, sort_keys=True
            )
            + "\n",
            "report.md": _render_report(result["summary"]),
        }
        for name, text in payloads.items():
            (temp / name).write_text(text, encoding="utf-8", newline="\n")
        artifacts = {
            name: hashlib.sha256((temp / name).read_bytes()).hexdigest()
            for name in sorted(payloads)
        }
        artifacts["source_ledger_content_sha256"] = hashlib.sha256(
            payloads["source_instances.jsonl"].encode("utf-8")
        ).hexdigest()
        artifacts["facts_ledger_content_sha256"] = hashlib.sha256(
            payloads["facts_ledger.jsonl"].encode("utf-8")
        ).hexdigest()
        (temp / "hash_ledger.json").write_text(
            json.dumps(
                {"schema": "gis_recommend.hash_ledger.v3", "artifacts": artifacts},
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
            newline="\n",
        )

        if output.exists():
            if not output.is_dir():
                raise ValueError(f"output path exists and is not a directory: {output}")
            backup = Path(
                tempfile.mkdtemp(prefix=f".{output.name}.backup-", dir=output.parent)
            )
            backup.rmdir()
            os.replace(output, backup)
        try:
            os.replace(temp, output)
            published = True
        except BaseException as publish_error:
            if backup is not None and backup.exists() and not output.exists():
                try:
                    os.replace(backup, output)
                    backup = None
                except BaseException as restore_error:
                    raise RuntimeError(
                        f"manifest publish failed; backup preserved at {backup}"
                    ) from restore_error
            raise publish_error
        if backup is not None:
            shutil.rmtree(backup)
            backup = None
        return {path.stem: path for path in sorted(output.iterdir())}
    finally:
        if not published:
            shutil.rmtree(temp, ignore_errors=True)
        if published and backup is not None and backup.exists():
            shutil.rmtree(backup, ignore_errors=True)


build_manifest = build_authority
write_outputs_atomic = write_manifest_atomic
