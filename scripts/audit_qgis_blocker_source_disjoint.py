#!/usr/bin/env python3
"""Run a bounded source-backed audit for recovery and API-sidecar blockers.

The audit is intentionally candidate-only.  Gold/Silver are measured against a
small deterministic rubric; no training rows or authority files are modified.
"""
from __future__ import annotations

import argparse
import ast
import hashlib
import json
import os
from collections import Counter
from pathlib import Path
from typing import Any


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _index_local_sources(root: Path, wanted_names: set[str]) -> dict[tuple[str, str], Path]:
    index: dict[tuple[str, str], Path] = {}
    for base, dirs, files in os.walk(root):
        dirs[:] = [d for d in dirs if d not in {".git", "node_modules", "outputs", "outputs_v2", ".mypy_cache", ".pytest_cache"}]
        for name in files:
            if name not in wanted_names:
                continue
            path = Path(base) / name
            try:
                digest = _sha256(path)
            except OSError:
                continue
            index.setdefault((name, digest), path)
    return index


def _operator_tokens(operator_id: str) -> tuple[str, ...]:
    algorithm = operator_id.split(":", 1)[-1].lower()
    return (operator_id.lower(), algorithm, algorithm.replace("_", ""))


def _site_evidence(text_lines: list[str], row: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    sites = list(row.get("call_sites") or [])
    operators = list(row.get("operator_ids") or [])
    if len(sites) != len(operators) or not sites:
        return False, ["call_site_operator_count_mismatch"]
    for site, operator in zip(sites, operators):
        start = int(site.get("line_start", 0))
        end = int(site.get("line_end", start))
        if start < 1 or end < start or end > len(text_lines):
            reasons.append(f"invalid_call_site:{start}-{end}")
            continue
        window = "\n".join(text_lines[start - 1 : end]).lower()
        if not any(token in window for token in _operator_tokens(str(operator))):
            reasons.append(f"operator_not_in_call_site:{operator}")
    return not reasons, reasons


def _audit_row(row: dict[str, Any], source: Path | None) -> dict[str, Any]:
    out = dict(row)
    out["training_admission"] = "not_granted_blocker_audit"
    out["training_row_emitted"] = False
    out["production_merge"] = "not_granted"
    if source is None:
        out.update({
            "source_replay_status": "deferred_source_unavailable",
            "source_replay_decision": "deferred",
            "audit_decision": "deferred",
            "audit_reason": "source_file_unavailable_in_local_mirror",
        })
        return out
    try:
        raw = source.read_bytes()
        text = raw.decode("utf-8-sig", errors="replace")
        ast.parse(text)
    except (OSError, SyntaxError, UnicodeError) as exc:
        out.update({
            "source_replay_status": "deferred_source_unparseable",
            "source_replay_decision": "deferred",
            "audit_decision": "deferred",
            "audit_reason": f"source_replay_unparseable:{type(exc).__name__}",
            "source_path_resolved": str(source),
        })
        return out
    lines = text.splitlines()
    evidence_ok, evidence_reasons = _site_evidence(lines, row)
    out.update({
        "source_replay_status": "verified_sha256_ast",
        "source_replay_decision": "pass" if evidence_ok else "reject",
        "source_path_resolved": str(source),
        "source_replay_call_site_evidence": evidence_ok,
        "source_replay_reasons": evidence_reasons,
    })
    if not evidence_ok:
        out.update({"audit_decision": "reject", "audit_reason": ";".join(evidence_reasons)})
        return out

    lane = str(row.get("audit_lane") or "")
    op_count = len(row.get("operator_ids") or [])
    downstream = bool(row.get("downstream_data_transform_calls"))
    intermediate = bool(row.get("intermediate_data_transform_calls"))
    scope = str(row.get("workflow_unit_scope") or "")
    # Gold requires a bounded, source-confirmed multi-step workflow with no
    # unmodelled data mutation.  Silver admits weaker but still source-backed
    # chains; unresolved task scope remains explicitly documented.
    if lane == "recover_call_graph":
        if 2 <= op_count <= 6 and not downstream and not intermediate and scope == "whole_processing_scope":
            decision, reason = "gold", "source_confirmed_bounded_recovery_chain"
        elif 1 <= op_count <= 6:
            decision, reason = "silver", "source_confirmed_recovery_chain_with_weaker_scope_or_transforms"
        else:
            decision, reason = "reject", "recovered_operator_chain_outside_training_bounds"
    elif lane == "review_api_sidecar":
        if 2 <= op_count <= 6 and not downstream and not intermediate and scope == "whole_processing_scope":
            decision, reason = "gold", "source_confirmed_sidecar_chain_without_unmodelled_transforms"
        elif 1 <= op_count <= 6 and not downstream:
            decision, reason = "silver", "source_confirmed_sidecar_chain_with_intermediate_or_scope_weakness"
        else:
            decision, reason = "reject", "sidecar_contains_unmodelled_downstream_or_oversized_chain"
    else:
        decision, reason = "deferred", "unknown_audit_lane"
    out.update({"audit_decision": decision, "audit_reason": reason})
    return out


def audit(packet: list[dict[str, Any]], source_root: Path) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    wanted = {Path(str(row.get("source_path") or "")).name for row in packet}
    index = _index_local_sources(source_root, wanted)
    audited: list[dict[str, Any]] = []
    for row in packet:
        name = Path(str(row.get("source_path") or "")).name
        source = index.get((name, str(row.get("source_sha256") or "")))
        audited.append(_audit_row(row, source))
    counts = Counter(row["audit_decision"] for row in audited)
    by_lane = {
        lane: dict(Counter(row["audit_decision"] for row in audited if row.get("audit_lane") == lane))
        for lane in ("recover_call_graph", "review_api_sidecar")
    }
    summary = {
        "schema": "gis_recommend.qgis_processing_blocker_audit.v1.result",
        "packet_rows": len(audited),
        "source_replay_status_counts": dict(Counter(row["source_replay_status"] for row in audited)),
        "audit_decision_counts": dict(counts),
        "audit_decision_by_lane": by_lane,
        "gold_rows": counts["gold"],
        "silver_rows": counts["silver"],
        "reject_rows": counts["reject"],
        "deferred_rows": counts["deferred"],
        "accepted_rows": counts["gold"] + counts["silver"],
        "training_rows_emitted": 0,
        "training_admission": "not_granted_blocker_audit",
        "source_disjoint_preserved": True,
        "deferred_low_evidence_population_touched": False,
    }
    return audited, summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packet", type=Path, required=True)
    parser.add_argument("--source-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    rows, summary = audit(_load(args.packet), args.source_root)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    (args.output_dir / "audit_result_v1.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    (args.output_dir / "audit_summary_v1.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
