#!/usr/bin/env python3
"""Build a bounded, source-disjoint intake for one partial Processing operator.

This is for a fully enumerated sub-threshold family.  It is calibration-only:
passing it can at most justify a bounded review of this frozen population, not
automatic taxonomy, parser-rule, or training-family promotion.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path
from typing import Any

SCHEMA = "gis_recommend.qgis_processing_bounded_partial_operator_intake.v1"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _source_hashes(rows: list[dict[str, Any]]) -> set[str]:
    return {str(row["source_sha256"]) for row in rows if row.get("source_sha256")}


def _rank(seed: int, operator_id: str, source_sha256: str) -> str:
    return hashlib.sha256(
        f"{seed}\x1f{operator_id}\x1f{source_sha256}".encode()
    ).hexdigest()


def _has_target_call_evidence(row: dict[str, Any], operator_id: str) -> bool:
    call_ids = {
        str(site.get("operator_id") or "").lower()
        for site in row.get("call_sites") or []
    }
    sequence_ids = {str(value).lower() for value in row.get("operator_sequence") or []}
    return operator_id in call_ids or operator_id in sequence_ids


def build_intake(
    ledger: list[dict[str, Any]],
    *,
    operator_id: str,
    excluded_source_sha256: set[str],
    minimum_source_support: int,
    seed: int,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    operator_id = operator_id.lower()
    candidates: dict[str, dict[str, Any]] = {}
    for row in ledger:
        source_sha = str(row.get("source_sha256") or "")
        unresolved = list(
            dict.fromkeys(
                str(value).lower()
                for value in row.get("unresolved_operator_ids") or []
                if value
            )
        )
        if (
            not source_sha
            or not row.get("source_path")
            or source_sha in excluded_source_sha256
            or row.get("status") != "deferred_mapping"
            or row.get("normalization_status") != "partially_normalized"
            or unresolved != [operator_id]
            or not _has_target_call_evidence(row, operator_id)
        ):
            continue
        current = candidates.get(source_sha)
        if current is None or str(row.get("record_id") or "") < str(
            current.get("record_id") or ""
        ):
            candidates[source_sha] = dict(row)
    if len(candidates) < minimum_source_support:
        raise ValueError(
            f"insufficient independent source support for {operator_id}: "
            f"{len(candidates)} < {minimum_source_support}"
        )
    selected = sorted(
        candidates.values(),
        key=lambda row: _rank(seed, operator_id, str(row["source_sha256"])),
    )
    split = (len(selected) + 1) // 2
    for index, row in enumerate(selected):
        row.update(
            {
                "schema": SCHEMA,
                "bounded_operator_id": operator_id,
                "bounded_population": "all_source_sha_representatives",
                "bounded_source_support": len(selected),
                "calibration_role": "calibration" if index < split else "holdout",
                "calibration_seed": seed,
                "intake_status": "pending_server_sha_and_normalized_body_verification",
                "normalized_source_body_sha256": "",
                "source_authority_key": "",
                "automatic_family_promotion": "not_granted_support_below_30",
                "taxonomy_admission": "not_granted_pending_bounded_source_review",
                "training_admission": "not_granted_pending_bounded_source_review",
                "training_row_emitted": False,
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
                "llm_called": False,
            }
        )
    calibration = {
        row["source_sha256"]
        for row in selected
        if row["calibration_role"] == "calibration"
    }
    holdout = {
        row["source_sha256"] for row in selected if row["calibration_role"] == "holdout"
    }
    if calibration & holdout:
        raise AssertionError("source SHA leakage in bounded calibration packet")
    return selected, {
        "schema": f"{SCHEMA}.summary",
        "operator_id": operator_id,
        "bounded_source_support": len(selected),
        "calibration_rows": len(calibration),
        "holdout_rows": len(holdout),
        "source_sha256_overlap": len(calibration & holdout),
        "automatic_family_promotion": "not_granted_support_below_30",
        "training_rows_emitted": 0,
        "training_admission": "not_granted_pending_bounded_source_review",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "llm_called": False,
        "next_gate": "server_sha_and_normalized_body_verification_then_boundary_and_taxonomy_calibration",
    }


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
        temporary = Path(handle.name)
    temporary.replace(path)


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, sort_keys=True)
        handle.write("\n")
        temporary = Path(handle.name)
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ledger", type=Path, required=True)
    parser.add_argument("--operator-id", required=True)
    parser.add_argument("--existing-authority", type=Path, required=True)
    parser.add_argument(
        "--exclude-source-manifest", type=Path, action="append", default=[]
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--minimum-source-support", type=int, default=20)
    parser.add_argument("--seed", type=int, default=20260807)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    excluded = _source_hashes(_read_jsonl(args.existing_authority))
    for path in args.exclude_source_manifest:
        excluded.update(_source_hashes(_read_jsonl(path)))
    selected, summary = build_intake(
        _read_jsonl(args.ledger),
        operator_id=args.operator_id,
        excluded_source_sha256=excluded,
        minimum_source_support=args.minimum_source_support,
        seed=args.seed,
    )
    intake_path = args.output_dir / "bounded_intake_selection_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    _write_jsonl(intake_path, selected)
    _write_json(summary_path, summary)
    _write_json(
        args.output_dir / "hash_ledger_v1.json",
        {
            "schema": "gis_recommend.hash_ledger.v1",
            "inputs": {
                args.ledger.name: _sha256(args.ledger),
                args.existing_authority.name: _sha256(args.existing_authority),
                **{path.name: _sha256(path) for path in args.exclude_source_manifest},
            },
            "artifacts": {
                intake_path.name: _sha256(intake_path),
                summary_path.name: _sha256(summary_path),
            },
        },
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
