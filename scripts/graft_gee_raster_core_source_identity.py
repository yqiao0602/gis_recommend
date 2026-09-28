#!/usr/bin/env python3
"""Graft replay-manifest source identities onto a bounded GEE raster-core proposal.

The script writes sidecar proposal artifacts only. It does not overwrite the
selected proposal rows, does not mutate outputs_v2, and does not grant training
or validation/test admission.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
import re
import sys
import tempfile
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


DEFAULT_INPUT = (
    ROOT
    / "docs/reports/gee_raster_core_v1_proposal_2026-07-24/selected_rows.jsonl"
)
DEFAULT_OUTPUT_DIR = (
    ROOT
    / "docs/reports/gee_raster_core_v1_source_identity_graft_2026-07-24"
)
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
SCRIPT_NAME_RE = re.compile(r"^(script_\d+)(?:\.[A-Za-z0-9]+)?$")


@dataclass(slots=True)
class GraftResult:
    report: dict[str, Any]
    rows: list[dict[str, Any]]
    unmatched_rows: list[dict[str, Any]]
    conflict_rows: list[dict[str, Any]]


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for line_number, line in enumerate(Path(path).read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        if not isinstance(row, dict):
            raise ValueError(f"{path}:{line_number} must contain a JSON object")
        rows.append(row)
    return rows


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            if text and not text.endswith("\n"):
                handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_path, path)
    except BaseException:
        temp_path.unlink(missing_ok=True)
        raise


def _jsonl_text(rows: Iterable[dict[str, Any]]) -> str:
    return "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for row in rows
    )


def _script_stem(script_name: str) -> str | None:
    match = SCRIPT_NAME_RE.match(Path(script_name).name)
    if not match:
        return None
    return match.group(1)


def _manifest_record_keys(record: dict[str, Any], manifest_path: Path) -> set[str]:
    keys: set[str] = set()
    for field in ("script_id", "record_id"):
        value = record.get(field)
        if isinstance(value, str) and value:
            keys.add(value)
    script_name = record.get("script_name")
    if isinstance(script_name, str):
        stem = _script_stem(script_name)
        if stem:
            keys.add(f"{manifest_path.stem}_{stem}")
    return keys


def _load_manifest_index(manifest_paths: Iterable[Path]) -> dict[str, list[dict[str, Any]]]:
    index: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for manifest_path in manifest_paths:
        path = Path(manifest_path)
        for record in _load_jsonl(path):
            for key in _manifest_record_keys(record, path):
                index[key].append(
                    {
                        "manifest_path": str(path),
                        "source_path": record.get("source_path"),
                        "source_sha256": record.get("source_sha256"),
                        "status": record.get("status"),
                        "script_name": record.get("script_name"),
                    }
                )
    return index


def _unique_valid_match(records: list[dict[str, Any]]) -> tuple[str, dict[str, Any] | list[dict[str, Any]] | None]:
    if not records:
        return "unmatched", None
    valid_records = [
        record
        for record in records
        if isinstance(record.get("source_sha256"), str)
        and SHA256_RE.fullmatch(str(record.get("source_sha256")))
    ]
    if not valid_records:
        return "invalid", records
    unique_pairs = {
        (str(record.get("source_sha256")).lower(), str(record.get("source_path") or ""))
        for record in valid_records
    }
    if len(unique_pairs) != 1:
        return "conflict", valid_records
    representative = dict(valid_records[0])
    representative["source_sha256"] = str(representative["source_sha256"]).lower()
    return "matched", representative


def _row_hash(row: dict[str, Any]) -> str:
    payload = json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _batch_from_script_id(script_id: str) -> str:
    return script_id.rsplit("_script_", 1)[0] if "_script_" in script_id else "unknown"


def _grafted_row(row: dict[str, Any], match: dict[str, Any]) -> dict[str, Any]:
    source_sha256 = str(match["source_sha256"]).lower()
    updated = dict(row)
    updated.update(
        {
            "source_identity_status": "authoritative_grafted",
            "source_identity_authority": "source_content_sha256",
            "source_sha256": source_sha256,
            "source_path": match.get("source_path"),
            "source_identity": {"content_hash": source_sha256},
            "source_identity_graft": {
                "authority": "replay_manifest",
                "manifest_path": match.get("manifest_path"),
                "manifest_status": match.get("status"),
                "script_name": match.get("script_name"),
            },
            "validation_eligible": False,
            "test_eligible": False,
        }
    )
    reasons = list(updated.get("selection_reason", []) or [])
    if "source_identity_grafted" not in reasons:
        reasons.append("source_identity_grafted")
    updated["selection_reason"] = reasons
    return updated


def _unmatched_row(row: dict[str, Any]) -> dict[str, Any]:
    updated = dict(row)
    updated["source_identity_status"] = "source_identity_unmatched"
    updated["validation_eligible"] = False
    updated["test_eligible"] = False
    return updated


def _conflict_row(row: dict[str, Any], status: str, records: Any) -> dict[str, Any]:
    updated = dict(row)
    updated["source_identity_status"] = (
        "source_identity_conflict" if status == "conflict" else "source_identity_invalid"
    )
    updated["source_identity_graft_error"] = {
        "status": status,
        "candidate_manifest_records": records,
    }
    updated["validation_eligible"] = False
    updated["test_eligible"] = False
    return updated


def graft_source_identity(
    *,
    selected_rows_path: Path,
    manifest_paths: list[Path],
    output_dir: Path,
    manifest_origin: str | None = None,
) -> GraftResult:
    selected_rows = _load_jsonl(selected_rows_path)
    manifest_index = _load_manifest_index(manifest_paths)
    rows: list[dict[str, Any]] = []
    unmatched: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    status_counts: Counter[str] = Counter()
    source_hash_counts: Counter[str] = Counter()
    unmatched_by_batch: Counter[str] = Counter()
    conflict_by_batch: Counter[str] = Counter()
    invalid_by_batch: Counter[str] = Counter()

    for row in selected_rows:
        script_id = str(row.get("script_id") or "")
        status, match_or_records = _unique_valid_match(manifest_index.get(script_id, []))
        if status == "matched":
            grafted = _grafted_row(row, match_or_records)  # type: ignore[arg-type]
            rows.append(grafted)
            status_counts["authoritative_grafted"] += 1
            source_hash_counts[grafted["source_sha256"]] += 1
        elif status == "unmatched":
            updated = _unmatched_row(row)
            rows.append(updated)
            unmatched.append(updated)
            status_counts["source_identity_unmatched"] += 1
            unmatched_by_batch[_batch_from_script_id(script_id)] += 1
        else:
            updated = _conflict_row(row, status, match_or_records)
            rows.append(updated)
            conflicts.append(updated)
            status_counts[updated["source_identity_status"]] += 1
            if status == "conflict":
                conflict_by_batch[_batch_from_script_id(script_id)] += 1
            else:
                invalid_by_batch[_batch_from_script_id(script_id)] += 1

    report = {
        "schema": "gis_recommend.gee_raster_core_source_identity_graft.v1",
        "inputs": {
            "selected_rows": str(Path(selected_rows_path)),
            "manifests": [str(Path(path)) for path in manifest_paths],
            "manifest_origin": manifest_origin,
        },
        "outputs": {
            "output_dir": str(Path(output_dir)),
        },
        "counts": {
            "selected_rows": len(selected_rows),
            "manifest_files": len(manifest_paths),
            "manifest_keys": len(manifest_index),
            "grafted_rows": status_counts["authoritative_grafted"],
            "unmatched_rows": status_counts["source_identity_unmatched"],
            "conflict_rows": status_counts["source_identity_conflict"],
            "invalid_rows": status_counts["source_identity_invalid"],
            "unique_source_hashes": len(source_hash_counts),
        },
        "status_counts": dict(sorted(status_counts.items())),
        "unmatched_by_batch": dict(sorted(unmatched_by_batch.items())),
        "conflict_by_batch": dict(sorted(conflict_by_batch.items())),
        "invalid_by_batch": dict(sorted(invalid_by_batch.items())),
        "decision": {
            "training_admission": "not_granted",
            "validation_eligible": False,
            "test_eligible": False,
            "promotion_gate": (
                "human text/chain review and source-disjoint split rebuild required "
                "before validation/test use"
            ),
        },
        "hashes": {
            "selected_rows_input_sha256": _file_sha256(Path(selected_rows_path)),
            "grafted_rows_content_sha256": _rows_sha256(rows),
        },
    }
    return GraftResult(
        report=report,
        rows=rows,
        unmatched_rows=unmatched,
        conflict_rows=conflicts,
    )


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _rows_sha256(rows: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for row in rows:
        digest.update(_row_hash(row).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _render_markdown(report: dict[str, Any]) -> str:
    counts = report["counts"]
    decision = report["decision"]
    lines = [
        "# GEE Raster Core Source Identity Graft",
        "",
        "This sidecar attempts to graft replay-manifest source hashes onto the bounded GEE raster-core proposal.",
        "It does not grant training, validation, or test admission.",
        "",
        "## Summary",
        "",
        f"- Selected rows: {counts['selected_rows']:,}",
        f"- Manifest files: {counts['manifest_files']:,}",
        f"- Manifest keys: {counts['manifest_keys']:,}",
        f"- Grafted rows: {counts['grafted_rows']:,}",
        f"- Unmatched rows: {counts['unmatched_rows']:,}",
        f"- Conflict rows: {counts['conflict_rows']:,}",
        f"- Invalid rows: {counts['invalid_rows']:,}",
        f"- Unique source hashes: {counts['unique_source_hashes']:,}",
        "",
        "## Unmatched By Batch",
        "",
    ]
    for batch, count in report.get("unmatched_by_batch", {}).items():
        lines.append(f"- `{batch}`: {count:,}")
    if not report.get("unmatched_by_batch"):
        lines.append("- None")
    lines.extend([
        "",
        "## Decision",
        "",
        f"- Training admission: `{decision['training_admission']}`",
        f"- Validation eligible: `{decision['validation_eligible']}`",
        f"- Test eligible: `{decision['test_eligible']}`",
        f"- Promotion gate: {decision['promotion_gate']}",
        "",
    ])
    return "\n".join(lines)


def write_outputs(result: GraftResult, output_dir: Path) -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "source_identity_graft_report.json"
    markdown_path = output_dir / "source_identity_graft_report.md"
    jsonl_path = output_dir / "grafted_selected_rows.jsonl"
    unmatched_path = output_dir / "unmatched_rows.jsonl"
    conflict_path = output_dir / "conflict_rows.jsonl"
    _atomic_write_text(
        json_path,
        json.dumps(result.report, ensure_ascii=False, indent=2, sort_keys=True),
    )
    _atomic_write_text(markdown_path, _render_markdown(result.report))
    _atomic_write_text(jsonl_path, _jsonl_text(result.rows))
    _atomic_write_text(unmatched_path, _jsonl_text(result.unmatched_rows))
    _atomic_write_text(conflict_path, _jsonl_text(result.conflict_rows))
    return {
        "json": json_path,
        "markdown": markdown_path,
        "jsonl": jsonl_path,
        "unmatched_jsonl": unmatched_path,
        "conflict_jsonl": conflict_path,
    }


def _manifest_paths_from_args(args: argparse.Namespace) -> list[Path]:
    paths: list[Path] = []
    for path in args.manifest or []:
        paths.append(Path(path))
    if args.manifest_dir:
        paths.extend(sorted(Path(args.manifest_dir).glob("*.jsonl")))
    unique: dict[str, Path] = {}
    for path in paths:
        resolved = Path(path).resolve()
        unique[str(resolved)] = resolved
    return list(unique.values())


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selected-rows", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--manifest", type=Path, action="append", default=[])
    parser.add_argument("--manifest-dir", type=Path)
    parser.add_argument("--manifest-origin")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)

    manifest_paths = _manifest_paths_from_args(args)
    if not manifest_paths:
        raise ValueError("provide at least one --manifest or --manifest-dir containing *.jsonl")
    result = graft_source_identity(
        selected_rows_path=args.selected_rows,
        manifest_paths=manifest_paths,
        output_dir=args.output_dir,
        manifest_origin=args.manifest_origin,
    )
    return write_outputs(result, args.output_dir)


if __name__ == "__main__":
    main()
