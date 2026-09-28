#!/usr/bin/env python3
"""Build a deterministic source-disjoint audit for the 507-row QGIS aggregate."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

AUDIT_ID = "qgis-train-only-aggregate-507-stratified-audit-v1"
DEFAULT_QUOTAS = {
    "qgis_processing_delivery_293_v1_source_verified": 10,
    "qgis_api_train_only_v1": 4,
    "qgis_api_random_point_train_only_v1": 4,
    "qgis_api_create_feature_class_train_only_v1": 5,
    "qgis_api_vector_file_export_train_only_v1": 5,
    "qgis_api_add_calculate_field_train_only_v1": 5,
    "qgis_api_raster_calculator_train_only_v1": 6,
    "qgis_api_set_crs_train_only_v1": 6,
    "qgis_api_add_field_existing_layer_train_only_v1": 5,
}


def classify_risk(row: dict[str, Any]) -> str:
    steps = int(row.get("n") or len(row.get("operator_sequence") or []))
    if steps >= 10:
        return "very_long_chain_ge_10"
    if steps >= 5:
        return "long_chain_5_9"
    if steps >= 2:
        return "multistep_chain_2_4"
    if row.get("whole_function_semantics_admission") == "not_granted":
        return "local_macro_boundary"
    return "single_step_source_verified"


def _rank(seed: int, row: dict[str, Any]) -> str:
    sample_id = str(row.get("sample_id") or "")
    return hashlib.sha256(f"{seed}:{sample_id}".encode()).hexdigest()


def _identities(row: dict[str, Any]) -> tuple[str, str]:
    return (
        str(row.get("source_sha256") or ""),
        str(row.get("source_authority_key") or ""),
    )


def select_stratified_audit(
    rows: list[dict[str, Any]],
    *,
    quotas: dict[str, int],
    seed: int,
) -> list[dict[str, Any]]:
    by_pool: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        pool = str(row.get("aggregate_source_pool") or "")
        source_sha, authority = _identities(row)
        if not pool or not source_sha or not authority:
            raise ValueError("aggregate row is missing pool or source identity")
        by_pool[pool].append(row)
    if set(by_pool) != set(quotas):
        raise ValueError("aggregate source pools do not match the frozen audit profile")

    selected: list[dict[str, Any]] = []
    used_sources: set[str] = set()
    used_authorities: set[str] = set()
    covered_risks: set[str] = set()
    covered_l3: set[str] = set()
    covered_operators: set[tuple[str, ...]] = set()
    pool_order = sorted(quotas, key=lambda pool: (len(by_pool[pool]), pool))
    for pool in pool_order:
        quota = int(quotas[pool])
        if quota < 1:
            raise ValueError(f"invalid quota for {pool}")
        pool_selected = 0
        candidates = list(by_pool[pool])
        while pool_selected < quota:
            eligible = [
                row
                for row in candidates
                if _identities(row)[0] not in used_sources
                and _identities(row)[1] not in used_authorities
            ]
            if not eligible:
                raise ValueError(f"insufficient source-disjoint support for {pool}")

            def score(row: dict[str, Any]) -> tuple[int, int, int, int, str]:
                risk = classify_risk(row)
                l3_codes = {str(code) for code in row.get("l3_code_sequence") or []}
                operators = tuple(str(value) for value in row.get("operator_sequence") or [])
                risk_weight = {
                    "very_long_chain_ge_10": 4,
                    "long_chain_5_9": 3,
                    "multistep_chain_2_4": 2,
                    "local_macro_boundary": 1,
                    "single_step_source_verified": 0,
                }[risk]
                return (
                    int(risk not in covered_risks),
                    len(l3_codes - covered_l3),
                    int(operators not in covered_operators),
                    risk_weight,
                    _rank(seed, row),
                )

            chosen = max(eligible, key=score)
            candidates.remove(chosen)
            source_sha, authority = _identities(chosen)
            risk = classify_risk(chosen)
            selected.append({**chosen, "audit_risk_stratum": risk})
            used_sources.add(source_sha)
            used_authorities.add(authority)
            covered_risks.add(risk)
            covered_l3.update(str(code) for code in chosen.get("l3_code_sequence") or [])
            covered_operators.add(
                tuple(str(value) for value in chosen.get("operator_sequence") or [])
            )
            pool_selected += 1
    return selected


def assign_source_disjoint_splits(
    rows: list[dict[str, Any]], seed: int
) -> list[dict[str, Any]]:
    splits: list[list[dict[str, Any]]] = [[], []]
    capacities = [(len(rows) + 1) // 2, len(rows) // 2]
    pool_counts: list[Counter[str]] = [Counter(), Counter()]
    risk_counts: list[Counter[str]] = [Counter(), Counter()]
    for row in sorted(rows, key=lambda value: _rank(seed + 1, value)):
        pool = str(row["aggregate_source_pool"])
        risk = str(row["audit_risk_stratum"])
        available = [
            index for index in range(2) if len(splits[index]) < capacities[index]
        ]
        target = min(
            available,
            key=lambda index: (
                pool_counts[index][pool],
                risk_counts[index][risk],
                len(splits[index]),
                index,
            ),
        )
        split = "calibration" if target == 0 else "holdout"
        splits[target].append(
            {
                **row,
                "audit_id": AUDIT_ID,
                "audit_split": split,
                "audit_status": "pending_semantic_review",
                "training_rows_emitted": 0,
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
            }
        )
        pool_counts[target][pool] += 1
        risk_counts[target][risk] += 1
    return [*splits[0], *splits[1]]


def build_summary(
    population: list[dict[str, Any]],
    audit_rows: list[dict[str, Any]],
    quotas: dict[str, int],
    seed: int,
) -> dict[str, Any]:
    calibration = [row for row in audit_rows if row["audit_split"] == "calibration"]
    holdout = [row for row in audit_rows if row["audit_split"] == "holdout"]
    cal_sources = {str(row["source_sha256"]) for row in calibration}
    hold_sources = {str(row["source_sha256"]) for row in holdout}
    cal_authorities = {str(row["source_authority_key"]) for row in calibration}
    hold_authorities = {str(row["source_authority_key"]) for row in holdout}
    if cal_sources & hold_sources or cal_authorities & hold_authorities:
        raise ValueError("audit splits are not source-disjoint")
    if len(audit_rows) != sum(quotas.values()):
        raise ValueError("audit row count does not match frozen quotas")
    return {
        "schema": "gis_recommend.qgis_train_only_aggregate_audit_summary.v1",
        "audit_id": AUDIT_ID,
        "seed": seed,
        "population_rows": len(population),
        "audit_rows": len(audit_rows),
        "calibration_rows": len(calibration),
        "holdout_rows": len(holdout),
        "source_sha_overlap": 0,
        "source_authority_overlap": 0,
        "unique_audit_sources": len(
            {str(row["source_sha256"]) for row in audit_rows}
        ),
        "unique_audit_authorities": len(
            {str(row["source_authority_key"]) for row in audit_rows}
        ),
        "source_pool_quotas": dict(sorted(quotas.items())),
        "source_pool_counts": dict(
            sorted(Counter(str(row["aggregate_source_pool"]) for row in audit_rows).items())
        ),
        "risk_stratum_counts": dict(
            sorted(Counter(str(row["audit_risk_stratum"]) for row in audit_rows).items())
        ),
        "unique_l3_codes": len(
            {str(code) for row in audit_rows for code in row.get("l3_code_sequence") or []}
        ),
        "max_chain_length": max(int(row.get("n") or 0) for row in audit_rows),
        "semantic_review_status": "pending",
        "training_rows_emitted": 0,
        "training_admission": "not_modified_by_audit_packet",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    fields = [
        "audit_split",
        "audit_risk_stratum",
        "aggregate_source_pool",
        "sample_id",
        "source_path",
        "source_sha256",
        "source_authority_key",
        "task_name",
        "task_description",
        "operator_sequence",
        "l3_code_sequence",
        "n",
        "evidence_snippet",
        "human_boundary_decision",
        "human_description_decision",
        "human_l3_decision",
        "human_notes",
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    **row,
                    "operator_sequence": json.dumps(
                        row.get("operator_sequence") or [], ensure_ascii=False
                    ),
                    "l3_code_sequence": json.dumps(
                        row.get("l3_code_sequence") or [], ensure_ascii=False
                    ),
                    "human_boundary_decision": "",
                    "human_description_decision": "",
                    "human_l3_decision": "",
                    "human_notes": "",
                }
            )
        temporary = Path(handle.name)
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aggregate", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-population", type=int, default=507)
    parser.add_argument("--seed", type=int, default=20260805)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    population = _read_jsonl(args.aggregate)
    if len(population) != args.expected_population:
        raise ValueError("aggregate population size mismatch")
    selected = select_stratified_audit(
        population, quotas=DEFAULT_QUOTAS, seed=args.seed
    )
    audit_rows = assign_source_disjoint_splits(selected, args.seed)
    summary = build_summary(population, audit_rows, DEFAULT_QUOTAS, args.seed)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    packet_path = args.output_dir / "audit_packet_v1.jsonl"
    csv_path = args.output_dir / "audit_review_v1.csv"
    summary_path = args.output_dir / "summary_v1.json"
    _write_jsonl(packet_path, audit_rows)
    _write_csv(csv_path, audit_rows)
    _write_json(summary_path, summary)
    _write_json(
        args.output_dir / "hash_ledger_v1.json",
        {
            "schema": "gis_recommend.hash_ledger.v1",
            "inputs": {
                "aggregate": {"path": str(args.aggregate), "sha256": _sha256(args.aggregate)}
            },
            "artifacts": {
                path.name: {"bytes": path.stat().st_size, "sha256": _sha256(path)}
                for path in (packet_path, csv_path, summary_path)
            },
        },
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
