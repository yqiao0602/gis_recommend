#!/usr/bin/env python3
"""Freeze a source-disjoint packet for the raw-source operator pilot.

The packet builder never calls an LLM and never emits training rows. It reads
complete source text from a manifest (or its source_path), excludes prior pilot
SHAs, computes deterministic local facts for audit, and writes a small,
reproducible Processing/API packet.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

try:
    from scripts.run_qgis_llm_raw_operator_extraction_pilot import (
        load_catalog,
        local_facts,
        source_sha256,
    )
except ModuleNotFoundError:  # direct execution from the scripts directory
    from run_qgis_llm_raw_operator_extraction_pilot import (  # type: ignore
        load_catalog,
        local_facts,
        source_sha256,
    )

SCHEMA = "gis_recommend.qgis_llm_raw_operator_packet.v1"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def source_from_row(row: dict[str, Any], replacements: list[tuple[str, str]]) -> str | None:
    value = row.get("source_text")
    if isinstance(value, str):
        return value
    raw = str(row.get("source_path") or "")
    for old, new in replacements:
        if raw.startswith(old):
            raw = new + raw[len(old):]
            break
    path = Path(raw)
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8-sig")


def build_packet(
    manifests: list[tuple[str, Path]],
    exclusion_manifest: Path | list[Path] | None,
    catalogs: dict[str, dict[str, dict[str, Any]]],
    per_pool: int,
    replacements: list[tuple[str, str]],
    max_source_chars: int = 120_000,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    excluded = set()
    exclusion_paths = ([exclusion_manifest] if isinstance(exclusion_manifest, Path) else exclusion_manifest) or []
    for exclusion_path in exclusion_paths:
        if exclusion_path.is_file():
            excluded.update(str(row.get("source_sha256") or row.get("content_sha256")) for row in read_jsonl(exclusion_path))
    skipped: dict[str, int] = {"excluded_prior_pilot": 0, "missing_source": 0, "sha_mismatch": 0, "source_too_large": 0, "unparseable": 0}
    selected: list[dict[str, Any]] = []
    used: set[str] = set(excluded)
    for pool, manifest in manifests:
        valid_rows: list[dict[str, Any]] = []
        target_with = per_pool // 2
        # Selection is deterministic by authority SHA. Parse only the small
        # packet, rather than AST-walking the entire 47k-source population.
        for row in sorted(read_jsonl(manifest), key=lambda item: str(item.get("source_sha256") or "")):
            declared = str(row.get("source_sha256") or "")
            if not declared or declared in used:
                skipped["excluded_prior_pilot"] += 1
                continue
            source = source_from_row(row, replacements)
            if source is None:
                skipped["missing_source"] += 1
                continue
            actual = source_sha256(source)
            if actual != declared:
                skipped["sha_mismatch"] += 1
                continue
            if len(source) > max_source_chars:
                skipped["source_too_large"] += 1
                continue
            try:
                facts = local_facts(source, pool, catalogs[pool])
            except SyntaxError:
                skipped["unparseable"] += 1
                continue
            valid_rows.append({
                "record_id": row.get("record_id"),
                "source_sha256": declared,
                "source_path": row.get("source_path"),
                "pilot_pool": pool,
                "source_text": source,
                "local_gold_facts": facts,
                "local_gold_fact_count": len(facts),
            })
            if (
                sum(row["local_gold_fact_count"] > 0 for row in valid_rows) >= target_with
                and sum(row["local_gold_fact_count"] == 0 for row in valid_rows) >= per_pool - target_with
            ):
                break
        with_facts = [row for row in valid_rows if row["local_gold_fact_count"] > 0]
        without_facts = [row for row in valid_rows if row["local_gold_fact_count"] == 0]
        chosen = with_facts[:target_with] + without_facts[: per_pool - target_with]
        if len(chosen) < per_pool:
            chosen = (with_facts + without_facts)[:per_pool]
        for row in chosen:
            if row["source_sha256"] not in used:
                selected.append(row)
                used.add(row["source_sha256"])
    if len(selected) != per_pool * len(manifests):
        raise ValueError(f"insufficient source-disjoint rows: selected={len(selected)} expected={per_pool * len(manifests)}")
    summary = {
        "schema": f"{SCHEMA}.summary",
        "selected_rows": len(selected),
        "selected_by_pool": {pool: sum(row["pilot_pool"] == pool for row in selected) for pool, _ in manifests},
        "selected_source_sha_unique": len({row["source_sha256"] for row in selected}),
        "excluded_prior_sha_count": len(excluded),
        "skipped": skipped,
        "training_rows_emitted": 0,
        "training_admission": "not_granted_raw_operator_pilot",
    }
    return selected, summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--processing-manifest", type=Path, required=True)
    parser.add_argument("--api-manifest", type=Path, required=True)
    parser.add_argument("--processing-catalog", type=Path, required=True)
    parser.add_argument("--api-catalog", type=Path, required=True)
    parser.add_argument("--exclude-manifest", type=Path, action="append")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--per-pool", type=int, default=10)
    parser.add_argument("--max-source-chars", type=int, default=120_000)
    parser.add_argument("--replace-prefix", action="append", default=[], metavar="OLD=NEW")
    args = parser.parse_args()
    replacements = []
    for item in args.replace_prefix:
        if "=" not in item:
            raise ValueError(f"invalid --replace-prefix: {item}")
        replacements.append(tuple(item.split("=", 1)))
    catalogs = {"processing": load_catalog(args.processing_catalog), "api": load_catalog(args.api_catalog)}
    selected, summary = build_packet(
        [("processing", args.processing_manifest), ("api", args.api_manifest)],
        args.exclude_manifest, catalogs, args.per_pool, replacements, args.max_source_chars,
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    packet = args.output_dir / "raw_source_packet_v1.jsonl"
    packet.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in selected), encoding="utf-8")
    (args.output_dir / "summary_v1.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    hashes = {packet.name: sha256_file(packet), "summary_v1.json": sha256_file(args.output_dir / "summary_v1.json")}
    (args.output_dir / "hash_ledger_v1.json").write_text(json.dumps(hashes, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
