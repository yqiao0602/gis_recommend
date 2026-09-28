#!/usr/bin/env python3
"""Audit the stable106 direct-row increment through fidelity and four-layer dedup."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


def _json_key(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _normalize_text(value: Any) -> str:
    return "".join(str(value or "").lower().split())


def evidence_keys(row: dict[str, Any]) -> tuple[str, str, str]:
    spans = [
        {"line_start": int(site["line_start"]), "line_end": int(site["line_end"])}
        for site in row.get("call_sites") or []
    ]
    calls = [
        {
            "ordinal": int(site.get("ordinal") or index + 1),
            "operator_id": str(site["operator_id"]),
            "line_start": int(site["line_start"]),
            "line_end": int(site["line_end"]),
        }
        for index, site in enumerate(row.get("call_sites") or [])
    ]
    source_region = _json_key(
        {"source_sha256": row["source_sha256"], "call_spans": spans}
    )
    call_graph = _json_key(
        {
            "source_sha256": row["source_sha256"],
            "calls": calls,
            "dependency_edges": row.get("dependency_edges") or [],
        }
    )
    training_pair = _json_key(
        {
            "task_name": _normalize_text(row.get("task_name")),
            "task_description": _normalize_text(row.get("task_description")),
            "operator_sequence": row.get("operator_ids") or [],
            "l3_code_sequence": row.get("mapped_l3_chain") or [],
        }
    )
    return source_region, call_graph, training_pair


def _index_unique(rows: list[dict[str, Any]], field: str) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row.get(field) or "")
        if not key or key in result:
            raise ValueError(f"missing or duplicate {field}: {key!r}")
        result[key] = row
    return result


def merge_existing_train_groups(
    groups: list[list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    rows = [row for group in groups for row in group]
    _index_unique(rows, "sample_id")
    return rows


def build_incremental_ledger(
    baseline_manifest_rows: list[dict[str, Any]],
    candidate_rows: list[dict[str, Any]],
    fidelity_rows: list[dict[str, Any]],
    *,
    existing_train_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    baseline_ids = {
        str(row["record_id"])
        for row in baseline_manifest_rows
        if row.get("action") == "auto_accept_candidate"
    }
    candidates = _index_unique(candidate_rows, "record_id")
    fidelity = _index_unique(fidelity_rows, "record_id")
    if set(candidates) != set(fidelity):
        raise ValueError("candidate/fidelity coverage mismatch")
    new_ids = sorted(
        (record_id for record_id in candidates if record_id not in baseline_ids),
        key=lambda record_id: candidates[record_id].get("parameter_evidence_status")
        != "verified_source_ast",
    )

    existing_regions = {
        str(row["source_region_key"]): str(row["sample_id"])
        for row in existing_train_rows
    }
    existing_graphs = {
        str(row["call_graph_key"]): str(row["sample_id"])
        for row in existing_train_rows
    }
    existing_pairs = {
        str(row.get("unified_training_pair_key") or ""): str(row["sample_id"])
        for row in existing_train_rows
        if row.get("unified_training_pair_key")
    }
    canonical_regions = dict(existing_regions)
    canonical_graphs = dict(existing_graphs)
    canonical_pairs = dict(existing_pairs)

    ledger: list[dict[str, Any]] = []
    for record_id in new_ids:
        candidate = candidates[record_id]
        if fidelity[record_id].get("description_fidelity_passed") is not True:
            ledger.append(
                {
                    "schema": "gis_recommend.qgis_stable106_increment_dedup.v1",
                    "record_id": record_id,
                    "operator_ids": candidate.get("operator_ids") or [],
                    "mapped_l3_chain": candidate.get("mapped_l3_chain") or [],
                    "dedup_decision": "fidelity_deferred",
                    "canonical_id": "",
                    "training_admission": "not_granted_description_fidelity_failed",
                    "training_row_emitted": False,
                }
            )
            continue

        if candidate.get("parameter_evidence_status") == "source_file_missing":
            ledger.append(
                {
                    "schema": "gis_recommend.qgis_stable106_increment_dedup.v1",
                    "record_id": record_id,
                    "source_sha256": candidate["source_sha256"],
                    "operator_ids": candidate.get("operator_ids") or [],
                    "mapped_l3_chain": candidate.get("mapped_l3_chain") or [],
                    "dedup_decision": "source_replay_deferred",
                    "canonical_id": "",
                    "training_admission": "not_granted_source_file_missing",
                    "training_row_emitted": False,
                }
            )
            continue

        region, graph, pair = evidence_keys(candidate)
        if region in canonical_regions:
            decision = "existing_source_region_suppressed"
            canonical_id = canonical_regions[region]
        elif graph in canonical_graphs:
            decision = "existing_call_graph_suppressed"
            canonical_id = canonical_graphs[graph]
        elif pair in canonical_pairs:
            decision = "exact_training_pair_suppressed"
            canonical_id = canonical_pairs[pair]
        else:
            decision = "canonical_keep_candidate"
            canonical_id = record_id
            canonical_regions[region] = record_id
            canonical_graphs[graph] = record_id
            canonical_pairs[pair] = record_id
        ledger.append(
            {
                "schema": "gis_recommend.qgis_stable106_increment_dedup.v1",
                "record_id": record_id,
                "source_sha256": candidate["source_sha256"],
                "operator_ids": candidate.get("operator_ids") or [],
                "mapped_l3_chain": candidate.get("mapped_l3_chain") or [],
                "task_name": candidate.get("task_name", ""),
                "task_description": candidate.get("task_description", ""),
                "source_region_key": region,
                "call_graph_key": graph,
                "normalized_dag_key": _json_key(
                    {
                        "operator_ids": candidate.get("operator_ids") or [],
                        "dependency_edges": candidate.get("dependency_edges") or [],
                        "workflow_unit_scope": candidate.get("workflow_unit_scope"),
                    }
                ),
                "training_pair_key": pair,
                "dedup_decision": decision,
                "canonical_id": canonical_id,
                "training_admission": "not_granted_stable106_report_only",
                "training_row_emitted": False,
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
            }
        )

    decisions = Counter(row["dedup_decision"] for row in ledger)
    passed = [row for row in ledger if row["dedup_decision"] != "fidelity_deferred"]
    canonical = [
        row for row in ledger if row["dedup_decision"] == "canonical_keep_candidate"
    ]
    summary = {
        "schema": "gis_recommend.qgis_stable106_increment_dedup_summary.v1",
        "baseline_direct_rows": len(baseline_ids),
        "new_direct_rows": len(ledger),
        "fidelity_passed_rows": len(passed),
        "fidelity_deferred_rows": len(ledger) - len(passed),
        "source_replay_deferred_rows": decisions["source_replay_deferred"],
        "canonical_candidate_rows": len(canonical),
        "decision_counts": dict(sorted(decisions.items())),
        "unique_candidate_sources": len({row["source_sha256"] for row in canonical}),
        "unique_candidate_dags": len({row["normalized_dag_key"] for row in canonical}),
        "existing_unified_authority_rows": len(existing_train_rows),
        "taxonomy_admission": "not_granted",
        "training_admission": "not_granted_stable106_report_only",
        "training_rows_emitted": 0,
        "next_gate": "source-authority replay for canonical candidates and taxonomy adjudication",
    }
    return ledger, summary


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def _write_json(path: Path, value: Any) -> None:
    _atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    _atomic_write(
        path,
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
            for row in rows
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline-manifest", type=Path, required=True)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--fidelity", type=Path, required=True)
    parser.add_argument("--existing-train", type=Path, action="append", required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    ledger, summary = build_incremental_ledger(
        _read_jsonl(args.baseline_manifest),
        _read_jsonl(args.candidates),
        _read_jsonl(args.fidelity),
        existing_train_rows=merge_existing_train_groups(
            [_read_jsonl(path) for path in args.existing_train]
        ),
    )
    ledger_path = args.output_dir / "incremental_dedup_ledger_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    report_path = args.output_dir / "report_v1.md"
    hash_path = args.output_dir / "hash_ledger_v1.json"
    _write_jsonl(ledger_path, ledger)
    _write_json(summary_path, summary)
    _atomic_write(
        report_path,
        "# QGIS stable106 direct increment audit v1\n\n"
        f"- New direct rows: {summary['new_direct_rows']}\n"
        f"- Fidelity passed: {summary['fidelity_passed_rows']}\n"
        f"- Canonical report-only candidates: {summary['canonical_candidate_rows']}\n"
        "- Training rows emitted: 0\n",
    )
    inputs = {
        "baseline_manifest": args.baseline_manifest,
        "candidates": args.candidates,
        "fidelity": args.fidelity,
        **{
            f"existing_train_{index}": path
            for index, path in enumerate(args.existing_train, start=1)
        },
    }
    _write_json(
        hash_path,
        {
            "schema": "gis_recommend.hash_ledger.v1",
            "inputs": {
                name: {"path": str(path), "sha256": _sha256(path)}
                for name, path in inputs.items()
            },
            "artifacts": {
                path.name: _sha256(path)
                for path in (ledger_path, summary_path, report_path)
            },
        },
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
