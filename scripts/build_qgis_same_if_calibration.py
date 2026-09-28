#!/usr/bin/env python3
"""Build a source-disjoint review package for same-if Processing DAGs."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence


SCHEMA = "gis_recommend.qgis_same_if_condition_calibration.v1"
POLICY_VERSION = "same-if-condition-syntax-evidence-v1"
BOUNDARY_RULE_ID = "candidate:same-if-branch-local-dag-v1"


def _json_key(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _sha256_value(value: Any) -> str:
    return hashlib.sha256(_json_key(value).encode("utf-8")).hexdigest()


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSONL at {path}:{line_number}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"JSONL row is not an object at {path}:{line_number}")
            rows.append(row)
    return rows


def _write_jsonl(path: Path, rows: Iterable[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _condition_path(row: Mapping[str, Any]) -> list[dict[str, Any]]:
    risk = row.get("local_risk_evidence") or {}
    if risk.get("control_path_status") != "same_if_branch":
        raise ValueError("same-if candidate is missing exact control-path status")
    path = risk.get("control_path") or []
    if not path:
        raise ValueError("same-if candidate has an empty control path")
    required = {
        "branch",
        "condition_expression",
        "normalized_condition_expression",
        "normalized_condition_key",
        "required_condition_value",
        "condition_syntax_kind",
        "condition_semantic_status",
    }
    normalized: list[dict[str, Any]] = []
    for item in path:
        missing = required - set(item)
        if missing:
            raise ValueError(
                "same-if candidate is missing condition evidence: "
                + ",".join(sorted(missing))
            )
        normalized.append(
            {
                "if_line": int(item.get("if_line") or 0),
                "branch": str(item["branch"]),
                "condition_expression": str(item["condition_expression"]),
                "normalized_condition_expression": str(
                    item["normalized_condition_expression"]
                ),
                "normalized_condition_key": str(item["normalized_condition_key"]),
                "required_condition_value": bool(item["required_condition_value"]),
                "condition_syntax_kind": str(item["condition_syntax_kind"]),
                "condition_semantic_status": str(item["condition_semantic_status"]),
            }
        )
    return normalized


def _condition_family_payload(path: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "normalized_condition_key": item["normalized_condition_key"],
            "branch": item["branch"],
            "required_condition_value": item["required_condition_value"],
        }
        for item in path
    ]


def _is_same_if_candidate(row: Mapping[str, Any]) -> bool:
    return (
        row.get("split_class") == "multi_step_local_dag"
        and BOUNDARY_RULE_ID in (row.get("boundary_rule_ids") or [])
        and (row.get("local_risk_evidence") or {}).get("control_path_status")
        == "same_if_branch"
    )


def build_condition_authorities(
    rows: Sequence[Mapping[str, Any]],
    *,
    minimum_support: int,
) -> list[dict[str, Any]]:
    if minimum_support < 1:
        raise ValueError("minimum_support must be positive")
    selected = [row for row in rows if _is_same_if_candidate(row)]
    grouped: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for row in selected:
        body = str(row.get("normalized_source_body_sha256") or "")
        if not body:
            raise ValueError("same-if candidate is missing normalized source body")
        grouped[body].append(row)

    provisional: list[dict[str, Any]] = []
    for body, members in sorted(grouped.items()):
        path_by_key: dict[str, list[dict[str, Any]]] = {}
        units_by_key: dict[str, dict[str, Any]] = {}
        source_pairs: set[tuple[str, str]] = set()
        for member in members:
            path = _condition_path(member)
            family_id = _sha256_value(_condition_family_payload(path))
            path_by_key.setdefault(family_id, path)
            source_sha = str(member.get("source_sha256") or "")
            if not source_sha:
                raise ValueError("same-if candidate is missing source SHA")
            source_pairs.add((source_sha, str(member.get("source_path") or "")))
            unit_key = str(member.get("unit_id") or "") or _sha256_value(
                {
                    "operator_ids": member.get("operator_ids") or [],
                    "dependency_edges": member.get("dependency_edges") or [],
                    "condition_family_id": family_id,
                }
            )
            units_by_key.setdefault(
                unit_key,
                {
                    "unit_id": unit_key,
                    "operator_ids": list(member.get("operator_ids") or []),
                    "dependency_edges": list(member.get("dependency_edges") or []),
                    "mapped_l3_chain": list(member.get("mapped_l3_chain") or []),
                    "local_structure_reasons": sorted(
                        set(member.get("local_structure_reasons") or [])
                    ),
                    "condition_family_id": family_id,
                },
            )
        family_ids = sorted(path_by_key)
        provisional.append(
            {
                "schema": SCHEMA,
                "policy_version": POLICY_VERSION,
                "normalized_source_body_sha256": body,
                "source_sha256s": sorted(sha for sha, _ in source_pairs),
                "source_paths": sorted(path for _, path in source_pairs),
                "condition_family_ids": family_ids,
                "condition_paths": [path_by_key[key] for key in family_ids],
                "units": [units_by_key[key] for key in sorted(units_by_key)],
                "unit_count": len(units_by_key),
                "condition_semantic_review": "pending",
                "condition_natural_language": "",
                "boundary_complete_review": "pending",
                "chain_truncation_review": "pending",
                "description_fidelity_review": "pending",
                "training_row_emitted": False,
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
            }
        )

    support = Counter(
        family_id
        for authority in provisional
        for family_id in authority["condition_family_ids"]
    )
    for authority in provisional:
        counts = {
            family_id: support[family_id]
            for family_id in authority["condition_family_ids"]
        }
        authority["family_support_authorities_by_id"] = counts
        if len(counts) == 1:
            authority["condition_family_id"] = next(iter(counts))
            authority["family_support_authorities"] = next(iter(counts.values()))
        passed = bool(counts) and all(
            count >= minimum_support for count in counts.values()
        )
        if passed:
            authority["condition_support_status"] = (
                "passed_pending_semantic_calibration"
            )
            authority["training_admission"] = (
                "not_granted_pending_condition_semantic_calibration"
            )
        else:
            authority["condition_support_status"] = (
                "deferred_insufficient_authority_support"
            )
            authority["training_admission"] = (
                "not_granted_insufficient_condition_support"
            )
    return provisional


def _source_components(
    authorities: Sequence[Mapping[str, Any]],
) -> list[list[Mapping[str, Any]]]:
    by_body = {
        str(row["normalized_source_body_sha256"]): row for row in authorities
    }
    parent = {body: body for body in by_body}

    def find(body: str) -> str:
        while parent[body] != body:
            parent[body] = parent[parent[body]]
            body = parent[body]
        return body

    def union(left: str, right: str) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[max(left_root, right_root)] = min(left_root, right_root)

    bodies_by_source: dict[str, list[str]] = defaultdict(list)
    for body, row in by_body.items():
        for source_sha in row.get("source_sha256s") or []:
            bodies_by_source[str(source_sha)].append(body)
    for bodies in bodies_by_source.values():
        for body in bodies[1:]:
            union(bodies[0], body)

    components: dict[str, list[Mapping[str, Any]]] = defaultdict(list)
    for body, row in by_body.items():
        components[find(body)].append(row)
    return [
        sorted(group, key=lambda row: row["normalized_source_body_sha256"])
        for _, group in sorted(components.items())
    ]


def partition_source_disjoint(
    authorities: Sequence[Mapping[str, Any]],
    *,
    seed: int,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    components = _source_components(authorities)
    components.sort(
        key=lambda group: _sha256_value(
            {
                "seed": seed,
                "bodies": [row["normalized_source_body_sha256"] for row in group],
            }
        )
    )
    splits: dict[str, list[dict[str, Any]]] = {
        "calibration": [],
        "holdout": [],
    }
    for component in components:
        target = min(splits, key=lambda name: (len(splits[name]), name))
        for row in component:
            materialized = dict(row)
            materialized["review_split"] = target
            splits[target].append(materialized)
    for rows in splits.values():
        rows.sort(key=lambda row: row["normalized_source_body_sha256"])
    return splits["calibration"], splits["holdout"]


def summarize_package(
    *,
    input_rows: int,
    authorities: Sequence[Mapping[str, Any]],
    calibration: Sequence[Mapping[str, Any]],
    holdout: Sequence[Mapping[str, Any]],
    minimum_support: int,
    seed: int,
) -> dict[str, Any]:
    calibration_bodies = {
        row["normalized_source_body_sha256"] for row in calibration
    }
    holdout_bodies = {row["normalized_source_body_sha256"] for row in holdout}
    calibration_sources = {
        sha for row in calibration for sha in row.get("source_sha256s") or []
    }
    holdout_sources = {
        sha for row in holdout for sha in row.get("source_sha256s") or []
    }
    support_pass = sum(
        row.get("condition_support_status")
        == "passed_pending_semantic_calibration"
        for row in authorities
    )
    return {
        "schema": SCHEMA,
        "policy_version": POLICY_VERSION,
        "input_same_if_units": input_rows,
        "normalized_body_authorities": len(authorities),
        "condition_families": len(
            {
                family_id
                for row in authorities
                for family_id in row.get("condition_family_ids") or []
            }
        ),
        "minimum_authority_support": minimum_support,
        "support_pass_authorities": support_pass,
        "support_deferred_authorities": len(authorities) - support_pass,
        "calibration_authorities": len(calibration),
        "holdout_authorities": len(holdout),
        "calibration_holdout_source_sha_overlap": len(
            calibration_sources & holdout_sources
        ),
        "calibration_holdout_normalized_body_overlap": len(
            calibration_bodies & holdout_bodies
        ),
        "review_seed": seed,
        "training_admission": "not_granted",
        "training_rows_emitted": 0,
        "llm_called": False,
        "next_gate": (
            "condition_semantic_calibration"
            if support_pass
            else "downstream_data_transform_family_census"
        ),
    }


def _write_review_csv(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    fieldnames = [
        "review_split",
        "normalized_source_body_sha256",
        "source_sha256s",
        "source_paths",
        "condition_expressions",
        "condition_branches",
        "condition_syntax_kinds",
        "condition_family_ids",
        "family_support_authorities_by_id",
        "unit_count",
        "operator_sequences",
        "local_structure_reasons",
        "condition_support_status",
        "condition_semantic_review",
        "condition_natural_language",
        "boundary_complete_review",
        "chain_truncation_review",
        "description_fidelity_review",
        "review_notes",
    ]
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            paths = row.get("condition_paths") or []
            flattened = [item for path_items in paths for item in path_items]
            writer.writerow(
                {
                    "review_split": row.get("review_split", ""),
                    "normalized_source_body_sha256": row[
                        "normalized_source_body_sha256"
                    ],
                    "source_sha256s": " | ".join(row.get("source_sha256s") or []),
                    "source_paths": " | ".join(row.get("source_paths") or []),
                    "condition_expressions": " | ".join(
                        str(item["condition_expression"]) for item in flattened
                    ),
                    "condition_branches": " | ".join(
                        str(item["branch"]) for item in flattened
                    ),
                    "condition_syntax_kinds": " | ".join(
                        str(item["condition_syntax_kind"]) for item in flattened
                    ),
                    "condition_family_ids": " | ".join(
                        row.get("condition_family_ids") or []
                    ),
                    "family_support_authorities_by_id": _json_key(
                        row.get("family_support_authorities_by_id") or {}
                    ),
                    "unit_count": row["unit_count"],
                    "operator_sequences": " | ".join(
                        " -> ".join(unit.get("operator_ids") or [])
                        for unit in row.get("units") or []
                    ),
                    "local_structure_reasons": " | ".join(
                        sorted(
                            {
                                reason
                                for unit in row.get("units") or []
                                for reason in unit.get("local_structure_reasons") or []
                            }
                        )
                    ),
                    "condition_support_status": row["condition_support_status"],
                    "condition_semantic_review": "",
                    "condition_natural_language": "",
                    "boundary_complete_review": "",
                    "chain_truncation_review": "",
                    "description_fidelity_review": "",
                    "review_notes": "",
                }
            )


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-jsonl", type=Path, action="append", required=True)
    parser.add_argument("--minimum-authority-support", type=int, default=30)
    parser.add_argument("--seed", type=int, default=20260803)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    for path in args.input_jsonl:
        if not path.is_file():
            raise FileNotFoundError(path)
    all_rows = [row for path in args.input_jsonl for row in _read_jsonl(path)]
    selected_rows = [row for row in all_rows if _is_same_if_candidate(row)]
    authorities = build_condition_authorities(
        selected_rows,
        minimum_support=args.minimum_authority_support,
    )
    calibration, holdout = partition_source_disjoint(authorities, seed=args.seed)
    summary = summarize_package(
        input_rows=len(selected_rows),
        authorities=authorities,
        calibration=calibration,
        holdout=holdout,
        minimum_support=args.minimum_authority_support,
        seed=args.seed,
    )
    if summary["calibration_holdout_source_sha_overlap"]:
        raise ValueError("calibration and holdout share source SHA identities")
    if summary["calibration_holdout_normalized_body_overlap"]:
        raise ValueError("calibration and holdout share normalized bodies")

    args.output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "condition_authority_v1.jsonl": authorities,
        "calibration_v1.jsonl": calibration,
        "holdout_v1.jsonl": holdout,
    }
    for name, rows in outputs.items():
        _write_jsonl(args.output_dir / name, rows)
    _write_review_csv(
        args.output_dir / "condition_review_v1.csv",
        [*calibration, *holdout],
    )
    summary_path = args.output_dir / "summary_v1.json"
    summary_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    report_path = args.output_dir / "report_v1.md"
    report_path.write_text(
        "# QGIS Processing same-if condition calibration\n\n"
        f"- Input same-if units: {summary['input_same_if_units']}\n"
        f"- Normalized-body authorities: {summary['normalized_body_authorities']}\n"
        f"- Condition families: {summary['condition_families']}\n"
        f"- Minimum authority support: {summary['minimum_authority_support']}\n"
        f"- Support-pass authorities: {summary['support_pass_authorities']}\n"
        f"- Calibration/holdout: {summary['calibration_authorities']}/"
        f"{summary['holdout_authorities']}\n"
        "- Source SHA overlap: 0\n"
        "- Normalized-body overlap: 0\n"
        "- Training admission: not granted\n"
        "- Training rows emitted: 0\n"
        f"- Next gate: {summary['next_gate']}\n",
        encoding="utf-8",
        newline="\n",
    )
    artifact_paths = [
        *(args.output_dir / name for name in outputs),
        args.output_dir / "condition_review_v1.csv",
        summary_path,
        report_path,
    ]
    ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "source_inputs": {
            str(path): {"sha256": _file_hash(path), "bytes": path.stat().st_size}
            for path in args.input_jsonl
        },
        "artifacts": {
            path.name: {"sha256": _file_hash(path), "bytes": path.stat().st_size}
            for path in artifact_paths
        },
    }
    (args.output_dir / "hash_ledger_v1.json").write_text(
        json.dumps(ledger, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
