"""Build a source-only manifest outside the 3,106 GEE strict subset."""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_gee_strict_candidate_source_audit import (  # noqa: E402
    _atomic_write,
    _json_text,
    _load_json,
    _load_jsonl,
    _sha256,
)


PACKAGE_DIR = (
    ROOT
    / "docs/reports/gee_raster_core_v1_review_split_2026-07-24"
    / "gee_raster_core_batch_training_package_v1"
)
DEFAULT_FULL_GATE = PACKAGE_DIR / "audit_full_policy_gate_v1/full_policy_gate_v1.jsonl"
DEFAULT_STRICT = PACKAGE_DIR / "strict_candidate_v1/gee_strict_candidate_v1_train3106.json"
DEFAULT_OUTPUT_DIR = PACKAGE_DIR / "strict_candidate_v1/semantic_pattern_census_remaining_8291_v1"
OUTPUT_PREFIX = "gee_semantic_remaining_8291_manifest_v1"
SOURCE_PREFIX = "/home/yll/GEE/Data/"


def _source_index(rows: list[dict[str, Any]], label: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for index, row in enumerate(rows, start=1):
        source_sha = str(row.get("source_sha256") or "")
        source_path = str(row.get("source_path") or "")
        if len(source_sha) != 64 or not source_path:
            raise ValueError(f"{label} row {index} lacks source authority")
        if source_sha in result:
            raise ValueError(f"duplicate source SHA in {label}: {source_sha}")
        result[source_sha] = row
    return result


def build_remaining_manifest(
    full_rows: list[dict[str, Any]], strict_rows: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    full_by_sha = _source_index(full_rows, "full gate")
    strict_by_sha = _source_index(strict_rows, "strict candidate")
    unknown = sorted(set(strict_by_sha) - set(full_by_sha))
    if unknown:
        raise ValueError(f"strict source SHA is absent from full gate: {unknown[:3]}")

    remaining = [
        {
            "sample_id": row.get("sample_id"),
            "script_id": row.get("script_id"),
            "source_path": row.get("source_path"),
            "source_sha256": row.get("source_sha256"),
            "strict_regeneration_disposition": row.get(
                "strict_regeneration_disposition"
            ),
            "policy_hits": list(row.get("policy_hits") or []),
            "risk_flags": list(row.get("risk_flags") or []),
            "training_admission": "not_granted_gee_semantic_remaining_manifest",
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
            "training_rows_emitted": 0,
        }
        for row in full_rows
        if str(row["source_sha256"]) not in strict_by_sha
    ]
    summary = {
        "schema": "gis_recommend.gee_semantic_remaining_manifest_summary.v1",
        "counts": {
            "full_authoritative_rows": len(full_rows),
            "strict_source_authorities": len(strict_rows),
            "remaining_source_authorities": len(remaining),
            "training_rows_emitted": 0,
        },
        "remaining_disposition_counts": dict(
            sorted(
                Counter(
                    str(row.get("strict_regeneration_disposition") or "")
                    for row in remaining
                ).items()
            )
        ),
        "decision": {
            "status": "source_only_semantic_census_manifest",
            "task_text_carried": False,
            "training_admission": "not_granted_gee_semantic_remaining_manifest",
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
        },
    }
    return remaining, summary


def write_outputs(
    rows: list[dict[str, Any]],
    summary: dict[str, Any],
    *,
    full_gate: Path,
    strict_json: Path,
    output_dir: Path,
) -> dict[str, Path]:
    output_dir = Path(output_dir)
    paths = {
        "manifest": output_dir / f"{OUTPUT_PREFIX}.json",
        "relative_paths": output_dir / f"{OUTPUT_PREFIX}_relative_paths.txt",
        "summary": output_dir / f"{OUTPUT_PREFIX}_summary.json",
        "hash_ledger": output_dir / f"{OUTPUT_PREFIX}_hash_ledger.json",
    }
    inputs = {
        "full_gate_jsonl": str(full_gate),
        "full_gate_jsonl_sha256": _sha256(full_gate),
        "strict_candidate_json": str(strict_json),
        "strict_candidate_json_sha256": _sha256(strict_json),
    }
    payload = {
        "schema": "gis_recommend.gee_semantic_remaining_manifest.v1",
        "labeled_workflows": rows,
        "metadata": {"counts": summary["counts"], "inputs": inputs},
    }
    summary = {**summary, "inputs": inputs}
    relative_paths = []
    for row in rows:
        source_path = str(row["source_path"])
        if not source_path.startswith(SOURCE_PREFIX):
            raise ValueError(f"source path is outside {SOURCE_PREFIX}: {source_path}")
        relative_paths.append(source_path.removeprefix(SOURCE_PREFIX))
    _atomic_write(paths["manifest"], _json_text(payload))
    _atomic_write(paths["relative_paths"], "\n".join(relative_paths) + "\n")
    _atomic_write(paths["summary"], _json_text(summary))
    ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "source_inputs": inputs,
        "artifacts": {
            path.name: {"path": str(path), "sha256": _sha256(path)}
            for key, path in paths.items()
            if key != "hash_ledger"
        },
    }
    _atomic_write(paths["hash_ledger"], _json_text(ledger))
    return paths


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full-gate-jsonl", type=Path, default=DEFAULT_FULL_GATE)
    parser.add_argument("--strict-json", type=Path, default=DEFAULT_STRICT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)
    full_rows = _load_jsonl(args.full_gate_jsonl)
    strict_payload = _load_json(args.strict_json)
    strict_rows = strict_payload.get("labeled_workflows")
    if not isinstance(strict_rows, list):
        raise ValueError("strict candidate JSON lacks labeled_workflows")
    rows, summary = build_remaining_manifest(full_rows, strict_rows)
    return write_outputs(
        rows,
        summary,
        full_gate=args.full_gate_jsonl,
        strict_json=args.strict_json,
        output_dir=args.output_dir,
    )


if __name__ == "__main__":
    main()
