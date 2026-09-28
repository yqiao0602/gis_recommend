#!/usr/bin/env python3
"""Stage hash-verified QGIS sources for the external-analysis pilot."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from gis_recommend.data.qgis_source_authority import source_authority


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _json_line(row: Mapping[str, Any]) -> str:
    return json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _atomic_write(path: Path, content: str) -> None:
    partial = path.with_suffix(path.suffix + ".partial")
    partial.write_text(content, encoding="utf-8", newline="\n")
    partial.replace(path)


def _resolve_source(
    declared: Path, prefix_aliases: Sequence[tuple[Path, Path]]
) -> tuple[Path, str]:
    if declared.is_file():
        return declared, "declared_path"
    matches: list[Path] = []
    for old_root, new_root in prefix_aliases:
        try:
            relative = declared.relative_to(old_root)
        except ValueError:
            continue
        candidate = new_root / relative
        if candidate.is_file():
            matches.append(candidate)
    if len(matches) != 1:
        raise ValueError(
            f"source path resolution failed for {declared}: matches={matches}"
        )
    return matches[0], "fixed_prefix_alias"


def stage_sources(
    manifest_rows: Sequence[Mapping[str, Any]],
    *,
    stage_root: Path,
    expected_count: int,
    prefix_aliases: Sequence[tuple[Path, Path]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    if len(manifest_rows) != expected_count:
        raise ValueError(
            f"expected exactly {expected_count} pilot rows, got {len(manifest_rows)}"
        )
    rows = sorted(manifest_rows, key=lambda row: int(row["target_index"]))
    if [int(row["target_index"]) for row in rows] != list(
        range(1, expected_count + 1)
    ):
        raise ValueError("target_index values must be contiguous and one-based")
    record_ids = [str(row.get("record_id") or "") for row in rows]
    bodies = [str(row.get("normalized_source_body_sha256") or "") for row in rows]
    if any(not record_id for record_id in record_ids) or len(set(record_ids)) != len(
        record_ids
    ):
        raise ValueError("record_id values must be non-empty and unique")
    if any(len(body) != 64 for body in bodies) or len(set(bodies)) != len(bodies):
        raise ValueError("normalized source authorities must be valid and unique")

    stage_root.mkdir(parents=True, exist_ok=True)
    partial_sources = stage_root / "sources.partial"
    final_sources = stage_root / "sources"
    if partial_sources.exists():
        shutil.rmtree(partial_sources)
    if final_sources.exists():
        raise ValueError(f"staged source directory already exists: {final_sources}")
    partial_sources.mkdir()

    staged_rows: list[dict[str, Any]] = []
    alias_count = 0
    for row in rows:
        declared = Path(str(row["source_path"]))
        source_path, resolution = _resolve_source(declared, prefix_aliases)
        source_sha256 = _sha256(source_path)
        if source_sha256 != str(row["source_sha256"]):
            raise ValueError(f"source hash mismatch: {row['record_id']}")
        authority = source_authority(source_path, source_sha256=source_sha256)
        if authority["normalized_source_body_sha256"] != str(
            row["normalized_source_body_sha256"]
        ):
            raise ValueError(f"normalized authority mismatch: {row['record_id']}")

        filename = (
            f"{int(row['target_index']):03d}_{row['corpus_kind']}_"
            f"{row['record_id']}.py"
        )
        staged_path = partial_sources / filename
        shutil.copyfile(source_path, staged_path)
        if _sha256(staged_path) != source_sha256:
            raise ValueError(f"staged source hash mismatch: {row['record_id']}")
        enriched = dict(row)
        enriched.update(
            {
                "authority_verdict": "unresolved",
                "provenance_complete": True,
                "resolved_source_path": str(source_path),
                "source_path_resolution": resolution,
                "staged_filename": filename,
                "staged_source_path": str(final_sources / filename),
                "training_admission": (
                    "not_granted_external_analysis_pilot_only"
                ),
                "training_row_emitted": False,
            }
        )
        staged_rows.append(enriched)
        alias_count += resolution == "fixed_prefix_alias"

    partial_sources.replace(final_sources)
    manifest_path = stage_root / "checkpoint_manifest_v1.jsonl"
    content = "".join(f"{_json_line(row)}\n" for row in staged_rows)
    _atomic_write(manifest_path, content)
    _atomic_write(stage_root / "authority_baseline.jsonl", content)
    summary = {
        "schema": "gis_recommend.qgis_external_pilot_staging.v1",
        "source_count": len(staged_rows),
        "processing_count": sum(
            row["corpus_kind"] == "processing" for row in staged_rows
        ),
        "api_count": sum(row["corpus_kind"] == "api" for row in staged_rows),
        "source_sha_verified": len(staged_rows),
        "unique_normalized_bodies": len(set(bodies)),
        "prefix_alias_count": alias_count,
        "manifest_sha256": _sha256(manifest_path),
        "training_rows_emitted": 0,
        "yll_mount_mode": "read_only",
    }
    _atomic_write(stage_root / "staging_summary_v1.json", _json_line(summary) + "\n")
    return staged_rows, summary


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _prefix_alias(value: str) -> tuple[Path, Path]:
    old, separator, new = value.partition("=")
    if not separator or not old or not new:
        raise argparse.ArgumentTypeError("prefix alias must be OLD=NEW")
    return Path(old), Path(new)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--stage-root", type=Path, required=True)
    parser.add_argument("--expected-count", type=int, required=True)
    parser.add_argument(
        "--prefix-alias", type=_prefix_alias, action="append", default=[]
    )
    args = parser.parse_args()
    if str(args.stage_root).startswith("/home/yll"):
        raise SystemExit("stage root must not be under /home/yll")
    _, summary = stage_sources(
        _read_jsonl(args.manifest),
        stage_root=args.stage_root,
        expected_count=args.expected_count,
        prefix_aliases=tuple(args.prefix_alias),
    )
    print(_json_line(summary))


if __name__ == "__main__":
    main()
