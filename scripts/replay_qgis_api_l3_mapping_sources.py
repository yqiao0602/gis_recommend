#!/usr/bin/env python3
"""Replay exact QGIS API L3 proposals against hash-verified source files."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

from scripts.recover_qgis_api_random_point_workflows import recover_row


def _expr_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Call):
        return _expr_name(node.func)
    if isinstance(node, ast.Attribute):
        base = _expr_name(node.value)
        return f"{base}.{node.attr}" if base else node.attr
    return ""


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _failed(row: dict[str, Any], reason: str) -> dict[str, Any]:
    return {
        **row,
        "source_replay_status": "failed",
        "source_replay_reason": reason,
        "semantic_call_replay_status": "not_verified",
        "replayed_semantic_calls": [],
        "semantic_call_sites": [],
        "source_snippet": "",
        "description_fidelity": "not_started",
        "deduplication": "not_started",
        "training_admission": "not_granted_source_replay_failed",
        "training_row_emitted": False,
    }


def replay_proposal(proposal: dict[str, Any]) -> dict[str, Any]:
    source_path = Path(str(proposal.get("source_path") or ""))
    if not source_path.is_file():
        return _failed(proposal, "source_missing")
    if _sha256(source_path) != proposal.get("source_sha256"):
        return _failed(proposal, "source_sha256_mismatch")
    try:
        source_text = source_path.read_text(encoding="utf-8-sig")
        tree = ast.parse(source_text)
    except UnicodeDecodeError:
        return _failed(proposal, "source_utf8_decode_error")
    except SyntaxError:
        return _failed(proposal, "source_ast_parse_error")

    source_span = proposal.get("source_span") or []
    if len(source_span) != 2:
        return _failed(proposal, "invalid_source_span")
    span_start, span_end = (int(source_span[0]), int(source_span[1]))
    expected_calls = [str(call) for call in proposal.get("semantic_calls") or []]
    if expected_calls == ["random_point_sampling"]:
        if (
            proposal.get("random_point_recovery_rule_id")
            != "lexical-scope-random-point-sampling-v1"
            or proposal.get("random_point_recovery_status")
            != "resolved_complete_lexical_scope_workflow"
            or proposal.get("candidate_l3_sequence") != ["L3_02_06_06"]
        ):
            return _failed(proposal, "unverified_composite_pattern_provenance")
        recovered, deferred = recover_row(proposal)
        if recovered is None:
            labels = (deferred or {}).get("failure_labels") or []
            reason = "composite_pattern_recovery_failed"
            if labels:
                reason += ":" + ",".join(str(label) for label in labels)
            return _failed(proposal, reason)
        if (
            recovered.get("source_span") != proposal.get("source_span")
            or recovered.get("sampling_loop_span")
            != proposal.get("sampling_loop_span")
            or recovered.get("random_point_facts")
            != proposal.get("random_point_facts")
        ):
            return _failed(proposal, "composite_pattern_fact_mismatch")
        loop_start, loop_end = (int(value) for value in proposal["sampling_loop_span"])
        return {
            **proposal,
            "source_replay_status": "verified",
            "source_replay_reason": "",
            "semantic_call_replay_status": "verified",
            "replayed_semantic_calls": expected_calls,
            "semantic_call_sites": [
                {
                    "call_name": "random_point_sampling",
                    "line_start": loop_start,
                    "line_end": loop_end,
                    "arguments": [],
                    "keyword_arguments": {},
                    "source_segment": str(proposal.get("sampling_loop_snippet") or ""),
                    "composite_facts": proposal["random_point_facts"],
                }
            ],
            "source_snippet": str(proposal.get("evidence_snippet") or ""),
            "description_fidelity": "not_started",
            "deduplication": "not_started",
            "training_admission": "not_granted_source_replay_only",
            "training_row_emitted": False,
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
        }
    calls = sorted(
        (
            node
            for node in ast.walk(tree)
            if isinstance(node, ast.Call)
            and span_start <= int(getattr(node, "lineno", 0)) <= span_end
        ),
        key=lambda node: (int(node.lineno), int(node.col_offset)),
    )
    positions: list[int] = []
    next_index = 0
    for expected in expected_calls:
        found = next(
            (
                index
                for index in range(next_index, len(calls))
                if _expr_name(calls[index].func) == expected
            ),
            None,
        )
        if found is None:
            return _failed(proposal, "semantic_call_span_mismatch")
        positions.append(found)
        next_index = found + 1

    call_sites = []
    for expected, position in zip(expected_calls, positions):
        node = calls[position]
        call_sites.append(
            {
                "call_name": expected,
                "line_start": int(node.lineno),
                "line_end": int(getattr(node, "end_lineno", node.lineno)),
                "arguments": [ast.unparse(argument) for argument in node.args],
                "keyword_arguments": {
                    str(keyword.arg): ast.unparse(keyword.value)
                    for keyword in node.keywords
                    if keyword.arg is not None
                },
                "source_segment": ast.get_source_segment(source_text, node) or "",
            }
        )
    lines = source_text.splitlines()
    snippet_start = max(1, span_start - 5)
    snippet_end = min(len(lines), span_end + 5)
    snippet = "\n".join(
        f"{line_number} | {lines[line_number - 1]}"
        for line_number in range(snippet_start, snippet_end + 1)
    )
    return {
        **proposal,
        "source_replay_status": "verified",
        "source_replay_reason": "",
        "semantic_call_replay_status": "verified",
        "replayed_semantic_calls": expected_calls,
        "semantic_call_sites": call_sites,
        "source_snippet": snippet,
        "description_fidelity": "not_started",
        "deduplication": "not_started",
        "training_admission": "not_granted_source_replay_only",
        "training_row_emitted": False,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)


def _write_json(path: Path, value: Any) -> None:
    _atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    _atomic_write(
        path,
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proposals", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")

    proposals = _read_jsonl(args.proposals)
    replayed = [replay_proposal(proposal) for proposal in proposals]
    verified = [row for row in replayed if row["source_replay_status"] == "verified"]
    failed = [row for row in replayed if row["source_replay_status"] != "verified"]
    verified_path = args.output_dir / "source_verified_proposals_v1.jsonl"
    failed_path = args.output_dir / "source_replay_failures_v1.jsonl"
    _write_jsonl(verified_path, verified)
    _write_jsonl(failed_path, failed)
    summary = {
        "schema": "gis_recommend.qgis_api_l3_source_replay_summary.v1",
        "input_proposals": len(proposals),
        "source_verified_proposals": len(verified),
        "source_replay_failures": len(failed),
        "source_replay_failure_reasons": dict(
            sorted(Counter(row["source_replay_reason"] for row in failed).items())
        ),
        "verified_source_authorities": len(
            {str(row.get("source_authority_key") or "") for row in verified}
        ),
        "description_fidelity_rows": 0,
        "dedup_rows": 0,
        "training_admission": "not_granted_source_replay_only",
        "training_rows_emitted": 0,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }
    summary_path = args.output_dir / "summary_v1.json"
    _write_json(summary_path, summary)
    artifacts = [verified_path, failed_path, summary_path]
    _write_json(
        args.output_dir / "hash_ledger_v1.json",
        {
            "schema": "gis_recommend.hash_ledger.v1",
            "inputs": {
                args.proposals.name: {
                    "path": str(args.proposals),
                    "sha256": _sha256(args.proposals),
                }
            },
            "artifacts": {
                path.name: {"bytes": path.stat().st_size, "sha256": _sha256(path)}
                for path in artifacts
            },
        },
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
