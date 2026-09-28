#!/usr/bin/env python3
"""Build the source-disjoint QGIS Processing Batch-3 calibration manifest.

This is a rule-calibration artifact, not a training-data exporter.  It selects
unadmitted Processing blockers once by normalized source body and source SHA,
then separates each recovery stratum into calibration and holdout partitions.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import tempfile
from collections import Counter
from collections.abc import Iterable
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "gis_recommend.qgis_processing_batch3_calibration.v1"
POLICY_VERSION = "qgis-processing-batch3-calibration-v1"
STRATA = (
    "control_flow_if",
    "control_flow_for",
    "helper_alias_missing_edges",
    "split_local_subworkflow",
    "dynamic_or_custom_operator_resolution",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _rank(seed: int, stratum: str, row: dict[str, Any]) -> str:
    value = "|".join(
        (
            str(seed),
            stratum,
            str(row["source_authority_key"]),
            str(row["source_sha256"]),
            str(row["record_id"]),
        )
    )
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _stratum(row: dict[str, Any]) -> str:
    evidence = row.get("structure_evidence") or {}
    controls = {str(value) for value in evidence.get("control_flow_kinds") or []}
    action = str(row.get("action") or "")
    if action == "defer_operator_resolution":
        return "dynamic_or_custom_operator_resolution"
    if "for" in controls:
        return "control_flow_for"
    if "if" in controls:
        return "control_flow_if"
    if action == "recover_call_graph":
        return "helper_alias_missing_edges"
    if action == "split_subworkflow":
        return "split_local_subworkflow"
    raise ValueError(f"unclassified blocker action: {action!r}")


def _validate_source(row: dict[str, Any]) -> None:
    for field in (
        "record_id",
        "source_authority_key",
        "source_sha256",
        "source_path",
    ):
        if not str(row.get(field) or ""):
            raise ValueError(f"blocker row missing {field}: {row.get('record_id')!r}")


def build_manifest(
    blockers: Iterable[dict[str, Any]], *, quota_per_stratum: int = 40, seed: int = 20260805
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Return an exactly balanced, globally source-disjoint calibration manifest."""

    if quota_per_stratum < 2 or quota_per_stratum % 2:
        raise ValueError("quota_per_stratum must be an even integer >= 2")

    candidates: dict[str, list[dict[str, Any]]] = {stratum: [] for stratum in STRATA}
    for raw in blockers:
        _validate_source(raw)
        candidates[_stratum(raw)].append(raw)

    selected: list[dict[str, Any]] = []
    used_authorities: set[str] = set()
    used_sha256: set[str] = set()
    selection_counts: Counter[str] = Counter()
    for stratum in STRATA:
        ranked = sorted(candidates[stratum], key=lambda row: _rank(seed, stratum, row))
        for row in ranked:
            authority = str(row["source_authority_key"])
            source_sha = str(row["source_sha256"])
            if authority in used_authorities or source_sha in used_sha256:
                continue
            selected.append(
                {
                    "schema": SCHEMA,
                    "policy_version": POLICY_VERSION,
                    "batch": "processing_batch3",
                    "stratum": stratum,
                    "record_id": str(row["record_id"]),
                    "source_authority_key": authority,
                    "source_authority_basis": str(row.get("source_authority_basis") or ""),
                    "normalized_source_body_sha256": str(
                        row.get("normalized_source_body_sha256") or ""
                    ),
                    "source_sha256": source_sha,
                    "source_path": str(row["source_path"]),
                    "source_root_id": str(row.get("source_root_id") or ""),
                    "relative_path": str(row.get("relative_path") or ""),
                    "route_action": str(row.get("action") or ""),
                    "rule_id": str(row.get("rule_id") or ""),
                    "structure_rule_id": str(row.get("structure_rule_id") or ""),
                    "signature_hash": str(row.get("signature_hash") or ""),
                    "feature_signature_hash": str(row.get("feature_signature_hash") or ""),
                    "call_sites": list(row.get("call_sites") or []),
                    "dependency_edges": [list(edge) for edge in row.get("dependency_edges") or []],
                    "provider_migrations": list(row.get("provider_migrations") or []),
                    "resolution_status": str(row.get("resolution_status") or ""),
                    "structure_evidence": dict(row.get("structure_evidence") or {}),
                    "control_flow_kinds": list(
                        (row.get("structure_evidence") or {}).get("control_flow_kinds")
                        or []
                    ),
                    "unresolved_operator_ids": list(row.get("unresolved_operator_ids") or []),
                    "operator_ids": list(row.get("ordered_operator_ids") or []),
                    "mapped_l3_chain": list(row.get("mapped_l3_chain") or []),
                    "source_reverification": "required_on_server",
                    "calibration_role": "pending_assignment",
                    "rule_decision": "pending_batch_calibration",
                    "training_admission": "not_granted_batch3_calibration_only",
                    "training_row_emitted": False,
                    "validation_eligible": False,
                    "test_eligible": False,
                    "production_merge": "not_granted",
                    "llm_called": False,
                }
            )
            used_authorities.add(authority)
            used_sha256.add(source_sha)
            selection_counts[stratum] += 1
            if selection_counts[stratum] == quota_per_stratum:
                break
        if selection_counts[stratum] != quota_per_stratum:
            available = len(
                {
                    str(row["source_authority_key"])
                    for row in candidates[stratum]
                    if str(row["source_authority_key"]) not in used_authorities
                }
            )
            raise ValueError(
                f"insufficient source-disjoint candidates for {stratum}: "
                f"{selection_counts[stratum]} < {quota_per_stratum}; remaining={available}"
            )

    for stratum in STRATA:
        members = sorted(
            (row for row in selected if row["stratum"] == stratum),
            key=lambda row: _rank(seed, stratum, row),
        )
        midpoint = quota_per_stratum // 2
        for index, row in enumerate(members):
            row["calibration_role"] = "calibration" if index < midpoint else "holdout"

    selected.sort(key=lambda row: (row["stratum"], row["calibration_role"], row["record_id"]))
    calibration = [row for row in selected if row["calibration_role"] == "calibration"]
    holdout = [row for row in selected if row["calibration_role"] == "holdout"]
    if {row["source_authority_key"] for row in calibration} & {
        row["source_authority_key"] for row in holdout
    }:
        raise ValueError("source authority leakage between calibration and holdout")
    if {row["source_sha256"] for row in calibration} & {
        row["source_sha256"] for row in holdout
    }:
        raise ValueError("source SHA leakage between calibration and holdout")

    summary = {
        "schema": f"{SCHEMA}.summary",
        "policy_version": POLICY_VERSION,
        "input_rows": sum(len(rows) for rows in candidates.values()),
        "input_rows_by_stratum": {key: len(candidates[key]) for key in STRATA},
        "quota_per_stratum": quota_per_stratum,
        "selected_rows": len(selected),
        "selected_by_stratum": dict(sorted(selection_counts.items())),
        "calibration_rows": len(calibration),
        "holdout_rows": len(holdout),
        "selected_unique_source_authorities": len(used_authorities),
        "selected_unique_source_sha256": len(used_sha256),
        "source_authority_zero_overlap": True,
        "source_sha256_zero_overlap": True,
        "server_source_reverification": "required_before_rule_evaluation",
        "training_rows_emitted": 0,
        "training_admission": "not_granted_batch3_calibration_only",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "llm_called": False,
        "seed": seed,
    }
    return selected, summary


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)


def write_outputs(
    rows: list[dict[str, Any]], summary: dict[str, Any], *, input_path: Path, output_dir: Path
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = output_dir / "batch3_calibration_manifest_v1.jsonl"
    csv_path = output_dir / "batch3_calibration_manifest_v1.csv"
    summary_path = output_dir / "summary_v1.json"
    report_path = output_dir / "README.md"
    _atomic_write(
        jsonl_path,
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
    )
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8-sig", newline="", dir=output_dir, delete=False
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(
            {
                key: json.dumps(value, ensure_ascii=False)
                if isinstance(value, (dict, list))
                else value
                for key, value in row.items()
            }
            for row in rows
        )
        temporary = Path(handle.name)
    temporary.replace(csv_path)
    _atomic_write(summary_path, json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    _atomic_write(
        report_path,
        "# QGIS Processing Batch-3 calibration manifest\n\n"
        "This 200-authority manifest calibrates reusable Processing recovery rules. "
        "It is source-disjoint by normalized body and SHA, requires server-side source "
        "reverification, and is not training data.\n",
    )
    artifacts = (jsonl_path, csv_path, summary_path, report_path)
    _atomic_write(
        output_dir / "hash_ledger_v1.json",
        json.dumps(
            {
                "schema": "gis_recommend.hash_ledger.v1",
                "input": {"path": str(input_path), "sha256": _sha256(input_path)},
                "artifacts": {
                    path.name: {"sha256": _sha256(path), "bytes": path.stat().st_size}
                    for path in artifacts
                },
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--blockers",
        type=Path,
        default=ROOT
        / "docs/reports/qgis_processing_boundary_families_v2_condition_evidence"
        / "blocker_source_replay_v1.jsonl",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "docs/reports/qgis_processing_batch3_calibration_v1",
    )
    parser.add_argument("--quota-per-stratum", type=int, default=40)
    parser.add_argument("--seed", type=int, default=20260805)
    args = parser.parse_args()
    rows, summary = build_manifest(
        _read_jsonl(args.blockers),
        quota_per_stratum=args.quota_per_stratum,
        seed=args.seed,
    )
    write_outputs(rows, summary, input_path=args.blockers, output_dir=args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


if __name__ == "__main__":
    main()
