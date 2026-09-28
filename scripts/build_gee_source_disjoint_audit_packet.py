#!/usr/bin/env python3
"""Verify and materialize the stratified audit packet for a replay selection."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import tempfile

from scripts.build_gee_complete_workflow_expansion_batch import (
    FrozenAuditSamplingProfile,
    RISK_STRATA,
    _load_jsonl,
    _source_representatives,
    build_stratified_audit_packet,
    largest_remainder_quotas,
)


def _jsonl(rows: list[dict]) -> bytes:
    return b"".join(
        (json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
        for row in rows
    )


def build_packet(
    *, selection_manifest: Path, reviewed_packet: Path, source_root: Path, sample_size: int = 30
) -> tuple[list[dict], list[dict], dict]:
    proposals = _load_jsonl(selection_manifest)
    if not proposals:
        raise ValueError("selection manifest is empty")
    representatives = _source_representatives(proposals)
    support = {stratum: 0 for stratum in RISK_STRATA}
    from scripts.build_gee_complete_workflow_expansion_batch import classify_risk_stratum

    for row in representatives:
        support[classify_risk_stratum(row)] += 1
    bounded = min(sample_size, len(representatives))
    profile = FrozenAuditSamplingProfile(
        name="gee_source_disjoint_replay_audit_v1",
        sample_size=bounded,
        expected_source_support=support,
        quotas=largest_remainder_quotas(support, sample_size=bounded),
    )
    result = build_stratified_audit_packet(
        proposal_rows=proposals,
        reviewed_packet_path=reviewed_packet,
        source_root=source_root,
        profile=profile,
    )
    return result.audit_rows, result.source_manifest, result.summary


def write_packet(*, audit_rows: list[dict], source_manifest: list[dict], summary: dict, output_dir: Path) -> None:
    output_dir = Path(output_dir)
    if output_dir.exists():
        raise FileExistsError(f"output directory already exists: {output_dir}")
    artifacts = {
        "audit_packet.jsonl": _jsonl(audit_rows),
        "source_manifest.jsonl": _jsonl(source_manifest),
        "summary.json": (json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8"),
    }
    ledger = {
        "schema": "gis_recommend.gee_source_disjoint_audit_hash_ledger.v1",
        "artifact_sha256": {name: hashlib.sha256(data).hexdigest() for name, data in sorted(artifacts.items())},
        "training_rows_emitted": 0,
        "training_admission": "not_granted_pending_sampling_audit",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }
    artifacts["hash_ledger.json"] = (json.dumps(ledger, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    output_dir.parent.mkdir(parents=True, exist_ok=True)
    staging = Path(tempfile.mkdtemp(prefix=f".{output_dir.name}.staging-", dir=output_dir.parent))
    try:
        for name, data in artifacts.items():
            (staging / name).write_bytes(data)
        staging.replace(output_dir)
    except BaseException:
        for path in staging.iterdir():
            path.unlink()
        staging.rmdir()
        raise


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--selection-manifest", type=Path, required=True)
    parser.add_argument("--reviewed-packet", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--sample-size", type=int, default=30)
    args = parser.parse_args(argv)
    rows, manifest, summary = build_packet(
        selection_manifest=args.selection_manifest,
        reviewed_packet=args.reviewed_packet,
        source_root=args.source_root,
        sample_size=args.sample_size,
    )
    write_packet(audit_rows=rows, source_manifest=manifest, summary=summary, output_dir=args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
