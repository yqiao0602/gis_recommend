#!/usr/bin/env python3
"""CLI for the proposal-only GEE source-disjoint replay selection."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from scripts.build_gee_complete_workflow_expansion_batch import (
    build_source_disjoint_replay_selection,
    write_source_disjoint_selection,
)


def main(argv: list[str] | None = None) -> dict[str, object]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate-proposals", type=Path, required=True)
    parser.add_argument("--reviewed-packet", type=Path, required=True)
    parser.add_argument("--prior-proposals", type=Path, required=True)
    parser.add_argument("--id-mappings", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--target-source-count", type=int, default=100)
    parser.add_argument("--audit-sample-size", type=int, default=30)
    args = parser.parse_args(argv)
    result = build_source_disjoint_replay_selection(
        candidate_proposals_path=args.candidate_proposals,
        reviewed_packet_path=args.reviewed_packet,
        prior_proposals_path=args.prior_proposals,
        id_mappings_path=args.id_mappings,
        target_source_count=args.target_source_count,
        audit_sample_size=args.audit_sample_size,
    )
    ledger = write_source_disjoint_selection(result, output_dir=args.output_dir)
    payload = {"summary": result.summary, "hash_ledger": ledger}
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return payload


if __name__ == "__main__":
    main()
