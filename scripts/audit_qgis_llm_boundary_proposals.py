"""Build an independent, source-backed audit packet for LLM boundary proposals."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def load(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--initial-ledger", type=Path, required=True)
    parser.add_argument("--retry-ledger", type=Path, required=True)
    parser.add_argument("--calibration-review", type=Path, required=True)
    parser.add_argument("--holdout-review", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    initial_rows = load(args.initial_ledger)
    initial_by_sha = {str(r["source_sha256"]): r for r in initial_rows}
    proposals = {sha: row for sha, row in initial_by_sha.items() if row.get("status") == "validated_candidate"}
    proposals.update({
        str(r["source_sha256"]): r
        for r in load(args.retry_ledger)
        if r.get("status") == "validated_candidate"
        and initial_by_sha.get(str(r["source_sha256"]), {}).get("status") == "deferred_request_failure"
    })
    source_rows = load(args.calibration_review) + load(args.holdout_review)
    sources = {str(r["source_sha256"]): r for r in source_rows}
    rows: list[dict[str, Any]] = []
    for sha, proposal_row in sorted(proposals.items()):
        source = sources[sha]
        proposal = proposal_row["proposal"]
        selected = proposal.get("selected_step_indices", [])
        expected_indices = [int(step["step_index"]) for step in source.get("steps", [])]
        expected = [tuple(edge) for edge in source.get("dependency_edges", [])]
        # Candidate DAG edges are occasionally serialized as local positions
        # even when their retained AST step indices start at a nonzero value.
        # Normalize those positions before comparing them to LLM step IDs.
        local_positions = list(range(len(expected_indices)))
        edge_nodes = sorted({node for edge in expected for node in edge})
        if edge_nodes and edge_nodes == local_positions and expected_indices != local_positions:
            expected = [
                (expected_indices[from_step], expected_indices[to_step])
                for from_step, to_step in expected
            ]
        step_by_index = {int(step["step_index"]): step for step in source.get("steps", [])}
        proposed_edges = [(edge["from_step"], edge["to_step"]) for edge in proposal.get("dependency_edges", [])]
        unsupported_edges = []
        reverse_edges = []
        for edge in proposal.get("dependency_edges", []):
            from_step = step_by_index.get(edge["from_step"], {})
            to_step = step_by_index.get(edge["to_step"], {})
            variable = edge.get("via_variable")
            if variable not in (from_step.get("produced_names") or []) or variable not in (to_step.get("consumed_names") or []):
                unsupported_edges.append([edge["from_step"], edge["to_step"], variable])
            if edge["from_step"] >= edge["to_step"]:
                reverse_edges.append([edge["from_step"], edge["to_step"]])
        selected_lines = [
            line
            for index in selected
            for line in [step_by_index[index].get("line_start"), step_by_index[index].get("line_end")]
            if isinstance(line, int)
        ]
        span_start, span_end = proposal.get("unit_start_line"), proposal.get("unit_end_line")
        rows.append({
            "schema": "gis_recommend.qgis_llm_boundary_audit_packet.v1",
            "source_sha256": sha,
            "record_id": source.get("record_id"),
            "review_split": proposal_row.get("review_split"),
            "source_span": source.get("source_span"),
            "source_windows": source.get("source_windows"),
            "steps": source.get("steps"),
            "llm_proposal": proposal,
            "deterministic_dependency_edges": expected,
            "mechanical_flags": {
                "selected_steps_omit_baseline_step": bool(set(expected_indices) - set(selected)),
                "edge_set_differs_from_baseline": proposed_edges != expected,
                "single_sink": len(proposal.get("sink_step_indices", [])) == 1,
                "unsupported_dataflow_edges": unsupported_edges,
                "reverse_edges": reverse_edges,
                "selected_steps_without_sink": not set(proposal.get("sink_step_indices", [])).intersection(selected),
                "boundary_span_does_not_cover_selected_steps": not isinstance(span_start, int) or not isinstance(span_end, int) or any(line < span_start or line > span_end for line in selected_lines),
            },
            "human_wrong_chain": "",
            "human_chain_truncated": "",
            "human_boundary_correct": "",
            "human_notes": "",
            "training_rows_emitted": 0,
            "training_admission": "not_granted_llm_boundary_audit",
        })
    args.output_dir.mkdir(parents=True, exist_ok=True)
    output = args.output_dir / "audit_packet_v1.jsonl"
    output.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows), encoding="utf-8")
    summary = {"rows": len(rows), "split_counts": {split: sum(row["review_split"] == split for row in rows) for split in sorted({row["review_split"] for row in rows})}, "omits_baseline_step": sum(row["mechanical_flags"]["selected_steps_omit_baseline_step"] for row in rows), "edge_differs_from_baseline": sum(row["mechanical_flags"]["edge_set_differs_from_baseline"] for row in rows), "unsupported_dataflow_edge_rows": sum(bool(row["mechanical_flags"]["unsupported_dataflow_edges"]) for row in rows), "reverse_edge_rows": sum(bool(row["mechanical_flags"]["reverse_edges"]) for row in rows), "selected_steps_without_sink": sum(row["mechanical_flags"]["selected_steps_without_sink"] for row in rows), "boundary_span_mismatch_rows": sum(row["mechanical_flags"]["boundary_span_does_not_cover_selected_steps"] for row in rows), "training_rows_emitted": 0}
    (args.output_dir / "summary_v1.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
