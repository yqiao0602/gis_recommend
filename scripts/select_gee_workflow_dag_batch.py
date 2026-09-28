#!/usr/bin/env python3
"""Freeze a source-disjoint GEE DAG batch without invoking the AST parser."""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
from typing import Any

from scripts.build_gee_workflow_dag_calibration import (
    DEFAULT_QUOTAS,
    _atomic_write,
    _json_bytes,
    _jsonl_bytes,
    _load_exact_join_paths,
    _load_fixed_selection_records,
    _parse_quota,
    _select_authority_candidates,
    _sha256,
    _validate_selected_quotas,
)


def freeze_authority_selection(
    *,
    canonical_manifest: Path,
    join_ledger: Path,
    exclude_selection_manifest: Path,
    source_root: Path,
    output_dir: Path,
    quotas: dict[str, int],
) -> dict[str, Any]:
    """Select and hash a fixed batch while leaving semantic rules untouched."""

    quotas = {**DEFAULT_QUOTAS, **dict(quotas)}
    quotas.setdefault("linear_export", DEFAULT_QUOTAS["linear_export"])
    print(f"selection quotas={quotas}", flush=True)

    excluded_rows = _load_fixed_selection_records(
        exclude_selection_manifest, source_root
    )
    excluded_hashes = {row["source_sha256"] for row in excluded_rows}
    selected = _select_authority_candidates(
        canonical_manifest,
        source_root,
        _load_exact_join_paths(join_ledger),
        quotas=quotas,
        exclude_source_sha256=excluded_hashes,
    )
    _validate_selected_quotas(selected, quotas)

    summary = {
        "schema": "gis_recommend.gee_workflow_dag_batch_selection_summary.v1",
        "selected_source_count": len(selected),
        "unique_source_count": len({row["source_sha256"] for row in selected}),
        "excluded_source_count": len(excluded_hashes),
        "strata": dict(
            sorted(Counter(row["calibration_stratum"] for row in selected).items())
        ),
        "selection_status": "frozen_pending_ast_replay",
        "training_admission": "not_granted_selection_only",
        "training_rows_emitted": 0,
    }
    report = (
        "# GEE Source-Disjoint DAG Batch Selection\n\n"
        f"- Selected sources: {summary['selected_source_count']}\n"
        f"- Unique source SHA256: {summary['unique_source_count']}\n"
        f"- Excluded prior sources: {summary['excluded_source_count']}\n"
        f"- Strata: {json.dumps(summary['strata'], sort_keys=True)}\n"
        "- Status: frozen pending AST replay; zero training rows emitted.\n"
    )
    payloads = {
        "selection.jsonl": _jsonl_bytes(selected),
        "summary.json": _json_bytes(summary),
        "report.md": report.encode("utf-8"),
    }
    for name, payload in payloads.items():
        _atomic_write(output_dir / name, payload)

    ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "inputs": {
            "canonical_manifest": {
                "path": str(canonical_manifest),
                "sha256": _sha256(canonical_manifest),
            },
            "join_ledger": {
                "path": str(join_ledger),
                "sha256": _sha256(join_ledger),
            },
            "exclude_selection_manifest": {
                "path": str(exclude_selection_manifest),
                "sha256": _sha256(exclude_selection_manifest),
            },
        },
        "artifacts": {
            name: {
                "sha256": hashlib.sha256(payload).hexdigest(),
                "size_bytes": len(payload),
            }
            for name, payload in sorted(payloads.items())
        },
    }
    _atomic_write(output_dir / "hash_ledger.json", _json_bytes(ledger))
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--canonical-manifest", type=Path, required=True)
    parser.add_argument("--join-ledger", type=Path, required=True)
    parser.add_argument("--exclude-selection-manifest", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--quota", type=_parse_quota, action="append", default=[])
    args = parser.parse_args(argv)
    quotas = dict(DEFAULT_QUOTAS)
    quotas.update(dict(args.quota))
    # Keep the required linear stratum even when older CLI wrappers pass only
    # the two non-linear quotas.
    quotas.setdefault("linear_export", DEFAULT_QUOTAS["linear_export"])
    summary = freeze_authority_selection(
        canonical_manifest=args.canonical_manifest,
        join_ledger=args.join_ledger,
        exclude_selection_manifest=args.exclude_selection_manifest,
        source_root=args.source_root,
        output_dir=args.output_dir,
        quotas=quotas,
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
