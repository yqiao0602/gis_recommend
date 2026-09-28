#!/usr/bin/env python3
"""Build a deterministic bounded audit for QGIS recovery/split rules."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

from gis_recommend.data.qgis_task_description import extract_literal_parameter_facts


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_MANIFEST = (
    ROOT
    / "docs/reports/qgis_mapping_high_impact_blockers_2026-07-24"
    / "stable101_all1442_source_replay_v1/routing_v2/routing_manifest.jsonl"
)
DEFAULT_OUTPUT_DIR = ROOT / "docs/reports/qgis_recovery_split_calibration_v1"
RULES = (
    "recover-control-flow-v1",
    "recover-missing-data-edges-v1",
    "recover-cross-scope-candidate-v1",
    "split-disconnected-scopes-v1",
)
NEXT_ACTION = {
    "recover-control-flow-v1": "recover branch and loop-aware DAG; defer dynamic cardinality",
    "recover-missing-data-edges-v1": "prove implicit/path binding or split independent calls",
    "recover-cross-scope-candidate-v1": "expand helper call graph and recover invocation order",
    "split-disconnected-scopes-v1": "split lexical scopes into connected local DAG units",
}
HUMAN_FIELDS = (
    "source_execution_decision",
    "recovery_boundary_decision",
    "dependency_decision",
    "description_scope_decision",
    "final_rule_decision",
    "reviewer_notes",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rank(seed: int, row: dict[str, Any]) -> str:
    value = f"{seed}|{row['rule_id']}|{row['signature_hash']}|{row['record_id']}"
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _risk_stratum(row: dict[str, Any]) -> str:
    rule = str(row["rule_id"])
    controls = set((row.get("reason") or {}).get("control_flow_kinds") or [])
    if rule == "recover-cross-scope-candidate-v1":
        return "cross_scope_helper_expansion"
    if rule == "split-disconnected-scopes-v1":
        return "disconnected_scope_split"
    if rule == "recover-missing-data-edges-v1":
        return "missing_data_binding"
    if "for" in controls or "while" in controls:
        return "loop_cardinality"
    if "if" in controls:
        return "conditional_branch"
    if "try" in controls:
        return "guarded_execution"
    return "other_control_flow"


def build_review_sample(
    manifest_rows: list[dict[str, Any]], *, quota_per_rule: int = 10, seed: int = 20260726
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    eligible = [row for row in manifest_rows if row.get("rule_id") in RULES]
    selected: list[dict[str, Any]] = []
    for rule in RULES:
        population = [row for row in eligible if row.get("rule_id") == rule]
        if len(population) < quota_per_rule:
            raise ValueError(
                f"insufficient rows for {rule}: {len(population)} < {quota_per_rule}"
            )
        ranked = sorted(population, key=lambda row: _rank(seed, row))
        chosen: list[dict[str, Any]] = []
        used_signatures: set[str] = set()
        for row in ranked:
            signature = str(row["signature_hash"])
            if signature in used_signatures:
                continue
            chosen.append(row)
            used_signatures.add(signature)
            if len(chosen) == quota_per_rule:
                break
        if len(chosen) < quota_per_rule:
            chosen_ids = {str(row["record_id"]) for row in chosen}
            chosen.extend(
                row
                for row in ranked
                if str(row["record_id"]) not in chosen_ids
            )
            chosen = chosen[:quota_per_rule]
        selected.extend(chosen)

    if len({row["source_sha256"] for row in selected}) != len(selected):
        raise ValueError("selected recovery/split audit must be source-disjoint")

    review_rows: list[dict[str, Any]] = []
    for position, source in enumerate(selected, start=1):
        row = dict(source)
        row.update(
            {
                "schema": "gis_recommend.qgis_recovery_split_rule_review.v1",
                "review_position": position,
                "risk_stratum": _risk_stratum(source),
                "proposed_next_action": NEXT_ACTION[source["rule_id"]],
                "review_status": "pending_human_review",
                "training_admission": "not_granted_rule_calibration_only",
                "training_row_emitted": False,
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
            }
        )
        row.update({field: "" for field in HUMAN_FIELDS})
        review_rows.append(row)

    selected_by_rule = Counter(row["rule_id"] for row in review_rows)
    summary = {
        "schema": "gis_recommend.qgis_recovery_split_rule_review_summary.v1",
        "pool_rows": len(eligible),
        "pool_by_rule": dict(sorted(Counter(row["rule_id"] for row in eligible).items())),
        "pool_unique_sources": len({row["source_sha256"] for row in eligible}),
        "pool_unique_signatures": len({row["signature_hash"] for row in eligible}),
        "selected_rows": len(review_rows),
        "selected_by_rule": {rule: selected_by_rule[rule] for rule in RULES},
        "selected_unique_sources": len({row["source_sha256"] for row in review_rows}),
        "selected_unique_signatures": len({row["signature_hash"] for row in review_rows}),
        "selected_by_risk": dict(sorted(Counter(row["risk_stratum"] for row in review_rows).items())),
        "quota_per_rule": quota_per_rule,
        "seed": seed,
        "decision": {
            "purpose": "bounded rule calibration",
            "training_rows_emitted": 0,
            "training_admission": "not_granted_rule_calibration_only",
            "next_gate": "source-backed rule adjudication then support/Wilson evaluation",
        },
    }
    return review_rows, summary


def _enrich_source_parameter_facts(rows: list[dict[str, Any]]) -> None:
    for row in rows:
        path = Path(row["source_path"])
        if not path.is_file():
            row["source_parameter_status"] = "source_file_missing"
            row["parameter_facts"] = []
        elif _sha256(path) != row["source_sha256"]:
            row["source_parameter_status"] = "source_sha256_mismatch"
            row["parameter_facts"] = []
        else:
            row["source_parameter_status"] = "verified_source_ast"
            row["parameter_facts"] = extract_literal_parameter_facts(
                path.read_text(encoding="utf-8"), call_sites=row.get("call_sites") or []
            )


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _atomic_write(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding=encoding, newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def _csv_value(value: Any) -> Any:
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def write_outputs(
    rows: list[dict[str, Any]], summary: dict[str, Any], *, manifest: Path, output_dir: Path
) -> dict[str, Path]:
    jsonl_path = output_dir / "review_40_v1.jsonl"
    csv_path = output_dir / "review_40_v1.csv"
    summary_path = output_dir / "summary_v1.json"
    report_path = output_dir / "README.md"
    hash_path = output_dir / "hash_ledger_v1.json"
    _atomic_write(
        jsonl_path,
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for row in rows
        ),
    )
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows({key: _csv_value(value) for key, value in row.items()} for row in rows)
    _atomic_write(csv_path, output.getvalue(), encoding="utf-8-sig")
    _atomic_write(summary_path, json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    report = """# QGIS recovery/split rule calibration v1

This 40-row packet is a bounded, source-disjoint rule audit. It is not training data.

Review the actual execution boundary, recoverable dependencies, local workflow scope, and whether the proposed rule can be generalized. Dynamic loop cardinality, unexpanded helpers, mapping gaps, and data-transforming APIs remain fail-closed.
"""
    _atomic_write(report_path, report)
    hashes = {
        "schema": "gis_recommend.hash_ledger.v1",
        "source_inputs": {manifest.name: {"path": str(manifest), "sha256": _sha256(manifest)}},
        "artifacts": {
            path.name: {"path": str(path), "sha256": _sha256(path), "bytes": path.stat().st_size}
            for path in (jsonl_path, csv_path, summary_path, report_path)
        },
    }
    _atomic_write(hash_path, json.dumps(hashes, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    return {
        "jsonl": jsonl_path,
        "csv": csv_path,
        "summary": summary_path,
        "report": report_path,
        "hash_ledger": hash_path,
    }


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=DEFAULT_MANIFEST)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--quota-per-rule", type=int, default=10)
    parser.add_argument("--seed", type=int, default=20260726)
    args = parser.parse_args(argv)
    rows, summary = build_review_sample(
        _load_jsonl(args.manifest), quota_per_rule=args.quota_per_rule, seed=args.seed
    )
    _enrich_source_parameter_facts(rows)
    summary["selected_source_parameter_status"] = dict(
        sorted(Counter(row["source_parameter_status"] for row in rows).items())
    )
    summary["selected_parameterized_steps"] = sum(
        sum(bool(facts) for facts in row.get("parameter_facts") or []) for row in rows
    )
    return write_outputs(rows, summary, manifest=args.manifest, output_dir=args.output_dir)


if __name__ == "__main__":
    main()
