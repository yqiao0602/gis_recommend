#!/usr/bin/env python3
"""Apply explicit source-audit decisions without exporting training rows."""

from __future__ import annotations

import argparse
import json
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    content = "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in value) if isinstance(value, list) else json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=path.parent, delete=False) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)


def adjudicate(candidates: list[dict[str, Any]], evidence: list[dict[str, Any]], decisions: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    by_id = {str(row.get("candidate_id")): row for row in candidates}
    evidence_by_id = {str(row.get("candidate_id")): row for row in evidence}
    decision_by_id = {str(row.get("candidate_id")): row for row in decisions}
    if set(by_id) != set(evidence_by_id) or set(by_id) != set(decision_by_id):
        raise ValueError("candidate, source evidence, and adjudication IDs do not match")
    output: list[dict[str, Any]] = []
    for candidate_id in sorted(by_id):
        source = evidence_by_id[candidate_id]
        decision = decision_by_id[candidate_id]
        if source.get("source_verification") != "verified_sha256":
            raise ValueError(f"source evidence is not verified: {candidate_id}")
        verdict = str(decision.get("source_audit_verdict") or "")
        if verdict not in {"accept_pending_downstream_gates", "deferred"}:
            raise ValueError(f"invalid source audit verdict: {candidate_id}")
        if not decision.get("reason"):
            raise ValueError(f"source audit reason is required: {candidate_id}")
        description_override = str(decision.get("task_description_override") or "").strip()
        if verdict == "accept_pending_downstream_gates" and not description_override:
            raise ValueError(f"accepted source audit requires a reviewed concise description: {candidate_id}")
        output.append({
            **by_id[candidate_id],
            **({"original_task_description": by_id[candidate_id].get("task_description"), "task_description": description_override} if description_override else {}),
            "source_audit_verdict": verdict,
            "source_audit_reason": decision["reason"],
            "source_audit_reviewer": decision.get("reviewer", "deterministic_qgis_source_audit_v1"),
            "source_audit_evidence_sha256": source.get("actual_source_sha256"),
            "source_audit_snippet_bound": True,
            "training_admission": "not_granted_pending_downstream_gates" if verdict.startswith("accept") else "not_granted_source_audit_deferred",
            "training_row_emitted": False,
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
        })
    summary = {
        "schema": "gis_recommend.qgis_processing_batch3_source_adjudication.v1.summary",
        "input_rows": len(output),
        "verdict_counts": dict(Counter(row["source_audit_verdict"] for row in output)),
        "accepted_pending_downstream_gates": sum(row["source_audit_verdict"] == "accept_pending_downstream_gates" for row in output),
        "training_rows_emitted": 0,
        "training_admission": "not_granted_pending_downstream_gates",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "llm_called": False,
    }
    return output, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--source-evidence", type=Path, required=True)
    parser.add_argument("--decisions", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    rows, summary = adjudicate(_read_jsonl(args.candidates), _read_jsonl(args.source_evidence), _read_jsonl(args.decisions))
    _write(args.output_dir / "source_adjudicated_candidates_v1.jsonl", rows)
    _write(args.output_dir / "summary_v1.json", summary)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
