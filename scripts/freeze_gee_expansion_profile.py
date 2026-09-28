"""Freeze deterministic GEE expansion census and audit authorities."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_gee_complete_workflow_expansion_batch import (  # noqa: E402
    freeze_expansion_batch_profile,
)


def _profile_bytes(payload: dict[str, Any]) -> bytes:
    return (
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def main(argv: list[str] | None = None) -> dict[str, Any]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fact-bundles", type=Path, required=True)
    parser.add_argument("--task-text-candidates", type=Path, required=True)
    parser.add_argument("--reviewed-packet", type=Path, required=True)
    parser.add_argument("--existing-semantic-rows", type=Path, required=True)
    parser.add_argument("--id-mappings", type=Path, required=True)
    parser.add_argument("--profile-name", required=True)
    parser.add_argument("--audit-name", required=True)
    parser.add_argument("--audit-sample-size", type=int, default=30)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)

    payload = freeze_expansion_batch_profile(
        fact_bundles_path=args.fact_bundles,
        task_text_candidates_path=args.task_text_candidates,
        reviewed_packet_path=args.reviewed_packet,
        existing_semantic_rows_path=args.existing_semantic_rows,
        id_mappings_path=args.id_mappings,
        name=args.profile_name,
        audit_name=args.audit_name,
        audit_sample_size=args.audit_sample_size,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("xb") as output:
        output.write(_profile_bytes(payload))
    print(json.dumps(payload, ensure_ascii=False, sort_keys=True))
    return payload


if __name__ == "__main__":
    main()
