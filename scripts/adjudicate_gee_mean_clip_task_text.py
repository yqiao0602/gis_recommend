#!/usr/bin/env python3
"""Validate the bounded technical review of GEE mean/clip task text."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_gee_mean_clip_task_text import DEFAULT_OUTPUT_DIR as TASK_TEXT_DIR  # noqa: E402
from scripts.build_gee_strict_candidate_source_audit import (  # noqa: E402
    _atomic_write,
    _json_text,
    _jsonl_text,
    _load_jsonl,
    _sha256,
)


DEFAULT_CANDIDATES = TASK_TEXT_DIR / "gee_mean_clip_task_text_candidate_v1.jsonl"
DEFAULT_OUTPUT_DIR = TASK_TEXT_DIR / "technical_review_v1"
DEFAULT_DECISIONS = DEFAULT_OUTPUT_DIR / "gee_mean_clip_task_text_review_decisions_v1.jsonl"


def summarize_review(
    candidates: list[dict[str, Any]], decisions: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    candidate_by_index = {int(row["source_review_index"]): row for row in candidates}
    decision_by_index = {int(row["review_index"]): row for row in decisions}
    if len(candidate_by_index) != len(candidates) or len(decision_by_index) != len(decisions):
        raise ValueError("duplicate review index")
    if set(candidate_by_index) != set(decision_by_index):
        raise ValueError("review decisions must cover every candidate")

    rollup: list[dict[str, Any]] = []
    for review_index in sorted(candidate_by_index):
        candidate = candidate_by_index[review_index]
        decision = decision_by_index[review_index]
        if (
            decision.get("cluster_id") != candidate.get("cluster_id")
            or decision.get("source_sha256") != candidate.get("source_sha256")
        ):
            raise ValueError(f"identity mismatch at review index {review_index}")
        final_decision = str(decision.get("final_decision") or "")
        if final_decision not in {"pass", "needs_edit"}:
            raise ValueError(f"invalid final decision at review index {review_index}")
        component_values = [
            str(decision.get("dataset_fidelity") or ""),
            str(decision.get("temporal_fidelity") or ""),
            str(decision.get("chain_fidelity") or ""),
        ]
        if final_decision == "pass" and any(not value.startswith("pass") for value in component_values):
            raise ValueError(f"passing row has a failed component at review index {review_index}")
        rollup.append(
            {
                **candidate,
                "technical_review": decision,
                "training_admission": "not_granted_task_text_review",
                "production_merge": "not_granted",
                "training_rows_emitted": 0,
            }
        )

    passed = sum(row["technical_review"]["final_decision"] == "pass" for row in rollup)
    corrected = sum(
        row["technical_review"]["temporal_fidelity"] == "pass_after_correction"
        for row in rollup
    )
    summary = {
        "schema": "gis_recommend.gee_mean_clip_task_text_technical_review_summary.v1",
        "reviewed_candidates": len(rollup),
        "passed": passed,
        "passed_after_temporal_correction": corrected,
        "needs_edit": len(rollup) - passed,
        "exporter_replay_eligible": bool(rollup) and passed == len(rollup),
        "training_admission": "not_granted_task_text_review",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "training_rows_emitted": 0,
    }
    return rollup, summary


def write_outputs(
    rollup: list[dict[str, Any]],
    summary: dict[str, Any],
    candidates_path: Path,
    decisions_path: Path,
    output_dir: Path,
) -> dict[str, Path]:
    paths = {
        "rollup": output_dir / "gee_mean_clip_task_text_technical_review_v1.jsonl",
        "summary": output_dir / "gee_mean_clip_task_text_technical_review_v1_summary.json",
        "report": output_dir / "gee_mean_clip_task_text_technical_review_v1_report.md",
        "hash_ledger": output_dir / "gee_mean_clip_task_text_technical_review_v1_hash_ledger.json",
    }
    _atomic_write(paths["rollup"], _jsonl_text(rollup))
    _atomic_write(paths["summary"], _json_text(summary))
    _atomic_write(
        paths["report"],
        (
            "# GEE Mean/Clip Task-Text Technical Review v1\n\n"
            f"- Reviewed: {summary['reviewed_candidates']}\n"
            f"- Passed: {summary['passed']}\n"
            f"- Passed after temporal correction: {summary['passed_after_temporal_correction']}\n"
            f"- Needs edit: {summary['needs_edit']}\n"
            f"- Exporter replay eligible: {str(summary['exporter_replay_eligible']).lower()}\n"
            "- Training/validation/test/production admission: not granted\n"
            "- Training rows emitted: 0\n"
        ),
    )
    ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "source_inputs": {
            str(candidates_path): _sha256(candidates_path),
            str(decisions_path): _sha256(decisions_path),
        },
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
    parser.add_argument("--candidates", type=Path, default=DEFAULT_CANDIDATES)
    parser.add_argument("--decisions", type=Path, default=DEFAULT_DECISIONS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)
    rollup, summary = summarize_review(
        _load_jsonl(args.candidates), _load_jsonl(args.decisions)
    )
    return write_outputs(
        rollup, summary, args.candidates, args.decisions, args.output_dir
    )


if __name__ == "__main__":
    main()
