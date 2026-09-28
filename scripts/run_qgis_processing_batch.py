#!/usr/bin/env python3
"""Replay the frozen QGIS Processing policy through one fail-closed entry point."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import tempfile
from collections import Counter, defaultdict, deque
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
POLICY_VERSION = "qgis-processing-unified-replay-v1"
SCHEMA = "gis_recommend.qgis_processing_unified_replay.v1"
TRAIN_ADMISSION = "granted_train_only_qgis_unified_pilot"

DEFAULT_AUTHORITY = (
    ROOT
    / "docs/reports/qgis_full_authority_manifests_v1"
    / "processing_source_manifest_v1.jsonl"
)
DEFAULT_BASE_REPLAY = (
    ROOT
    / "docs/reports/qgis_full_authority_manifests_v1"
    / "processing_full_replay_manifest_v2.jsonl"
)
DEFAULT_LATEST_REPLAY = (
    ROOT
    / "docs/reports/qgis_processing_mapping_gap_stable106_v1"
    / "lineintersections_mapping_correction_v1/replay_v1/l3_gated_manifest_v1.jsonl"
)
DEFAULT_DESCRIPTIONS = (
    ROOT
    / "docs/reports/qgis_processing_mapping_gap_stable106_v1"
    / "lineintersections_mapping_correction_v1/direct_descriptions_v1"
    / "direct_description_candidates_v1.jsonl"
)
DEFAULT_TRAIN_AUTHORITY = (
    ROOT / "docs/reports/qgis_train_authority_v1/qgis_unified_train_v1.jsonl"
)


def _identity(row: dict[str, Any]) -> tuple[str, str]:
    return str(row.get("record_id") or ""), str(row.get("source_sha256") or "")


def _index_unique(
    rows: Iterable[dict[str, Any]], label: str
) -> dict[tuple[str, str], dict[str, Any]]:
    result: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = _identity(row)
        if not all(key):
            raise ValueError(f"{label} contains a blank identity: {key!r}")
        if key in result:
            raise ValueError(f"{label} contains a duplicate identity: {key!r}")
        result[key] = row
    return result


def _json_key(value: Any) -> str:
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _normalize_text(value: Any) -> str:
    return "".join(str(value or "").lower().split())


def _operator_sequence(row: dict[str, Any]) -> list[str]:
    return [
        str(value)
        for value in (
            row.get("operator_sequence")
            or row.get("operator_ids")
            or row.get("ordered_operator_ids")
            or row.get("canonical_operator_ids")
            or []
        )
    ]


def _l3_sequence(row: dict[str, Any]) -> list[str]:
    return [
        str(value)
        for value in (row.get("l3_code_sequence") or row.get("mapped_l3_chain") or [])
    ]


def _training_pair_key(row: dict[str, Any]) -> str:
    return _json_key(
        {
            "task_name": _normalize_text(row.get("task_name")),
            "task_description": _normalize_text(row.get("task_description")),
            "operator_sequence": _operator_sequence(row),
            "l3_code_sequence": _l3_sequence(row),
        }
    )


def _source_region_key(row: dict[str, Any]) -> str:
    if row.get("source_region_key"):
        return str(row["source_region_key"])
    spans = [
        {
            "line_start": int(site["line_start"]),
            "line_end": int(site["line_end"]),
        }
        for site in row.get("call_sites") or []
    ]
    return _json_key({"source_sha256": row["source_sha256"], "call_spans": spans})


def _call_graph_key(row: dict[str, Any]) -> str:
    if row.get("call_graph_key"):
        return str(row["call_graph_key"])
    calls = [
        {
            "ordinal": int(site.get("ordinal") or index + 1),
            "operator_id": str(site.get("operator_id") or ""),
            "line_start": int(site["line_start"]),
            "line_end": int(site["line_end"]),
        }
        for index, site in enumerate(row.get("call_sites") or [])
    ]
    return _json_key(
        {
            "source_sha256": row["source_sha256"],
            "calls": calls,
            "dependency_edges": row.get("dependency_edges") or [],
        }
    )


def _normalized_dag_key(row: dict[str, Any]) -> str:
    if row.get("normalized_dag_key"):
        return str(row["normalized_dag_key"])
    return _json_key(
        {
            "operator_ids": _operator_sequence(row),
            "dependency_edges": row.get("dependency_edges") or [],
            "workflow_unit_scope": row.get("workflow_unit_scope")
            or row.get("workflow_scope"),
        }
    )


def _dedup_keys(row: dict[str, Any]) -> dict[str, str]:
    return {
        "source_region": _source_region_key(row),
        "call_graph": _call_graph_key(row),
        "normalized_dag": _normalized_dag_key(row),
        "training_pair": _training_pair_key(row),
    }


def _validate_training_row(row: dict[str, Any]) -> None:
    sample_id = str(row.get("sample_id") or "")
    operators = _operator_sequence(row)
    l3_codes = _l3_sequence(row)
    token_ids = list(row.get("l3_token_ids") or [])
    if not sample_id:
        raise ValueError("training authority row is missing sample_id")
    if row.get("training_admission") != TRAIN_ADMISSION:
        raise ValueError(f"unapproved training authority row: {sample_id}")
    if not str(row.get("split") or "").startswith("train_only_"):
        raise ValueError(f"non-train split in training authority: {sample_id}")
    if row.get("validation_eligible") or row.get("test_eligible"):
        raise ValueError(f"validation/test leakage in training authority: {sample_id}")
    if row.get("production_merge") != "not_granted":
        raise ValueError(f"production merge is open in training authority: {sample_id}")
    if not operators or len(operators) != len(l3_codes) or len(operators) != len(token_ids):
        raise ValueError(f"operator/L3 alignment failure in training authority: {sample_id}")
    if list(row.get("l3_sequence") or []) != [-3, *token_ids, -4]:
        raise ValueError(f"L3 token framing failure in training authority: {sample_id}")
    if not row.get("source_region_key") or not row.get("call_graph_key"):
        raise ValueError(f"missing source dedup evidence in training authority: {sample_id}")


def _route_status(route: dict[str, Any]) -> tuple[str, str, str]:
    action = str(route.get("action") or "")
    if action == "defer_mapping":
        return "deferred", "deferred_mapping", "operator chain is not fully mapped"
    if action == "defer_operator_resolution":
        return "deferred", "deferred_operator", "operator ID is not fully resolved"
    if action in {"recover_call_graph", "split_subworkflow", "review_api_sidecar"}:
        return "deferred", "deferred_boundary", f"task boundary remains {action}"
    if action == "exclude_candidate_alignment_failure":
        return "excluded", "excluded_boundary", "candidate/source alignment failed"
    if action == "exclude_current_chain":
        rule_id = str(route.get("rule_id") or "")
        if rule_id == "reject-unparseable-v1":
            return "excluded", "excluded_unparseable", "source AST is unparseable"
        return "excluded", "excluded_source", f"source replay rejected by {rule_id}"
    return "deferred", "deferred_boundary", f"unsupported route action: {action or 'blank'}"


def build_replay_ledger(
    authority_rows: list[dict[str, Any]],
    base_replay_rows: list[dict[str, Any]],
    latest_replay_rows: list[dict[str, Any]],
    description_rows: list[dict[str, Any]],
    train_authority_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    authorities = _index_unique(authority_rows, "authority")
    base = _index_unique(base_replay_rows, "base replay")
    latest = _index_unique(latest_replay_rows, "latest replay")
    descriptions = _index_unique(description_rows, "description evidence")

    authority_ids = set(authorities)
    if set(base) != authority_ids:
        raise ValueError(
            "base replay coverage mismatch: "
            f"missing={len(authority_ids - set(base))}, extra={len(set(base) - authority_ids)}"
        )
    if extra := set(latest) - authority_ids:
        raise ValueError(f"latest replay identities outside authority: {len(extra)}")
    if extra := set(descriptions) - authority_ids:
        raise ValueError(f"description identities outside authority: {len(extra)}")

    train = _index_unique(
        (row for row in train_authority_rows if _identity(row) in authority_ids),
        "in-scope training authority",
    )
    for row in train.values():
        _validate_training_row(row)

    accepted_key_indexes: dict[str, dict[str, tuple[str, str]]] = {
        name: {} for name in ("source_region", "call_graph", "training_pair")
    }
    for key, row in train.items():
        for name, value in _dedup_keys(row).items():
            if name in accepted_key_indexes:
                accepted_key_indexes[name].setdefault(value, key)

    prospective_key_indexes = {
        name: dict(values) for name, values in accepted_key_indexes.items()
    }
    ledger: list[dict[str, Any]] = []
    accepted_rows: list[dict[str, Any]] = []
    accepted_chain_checks = 0

    for key in sorted(authorities):
        authority = authorities[key]
        route = latest.get(key, base[key])
        route_source = "latest_stable110_correction" if key in latest else "full_replay_v2"
        action = str(route.get("action") or "")
        description = descriptions.get(key)
        admitted = train.get(key)
        duplicate_reason = ""
        duplicate_of = ""

        if admitted is not None:
            if action == "auto_accept_candidate":
                replay_operators = _operator_sequence(route)
                replay_l3 = _l3_sequence(route)
                if (
                    replay_operators != _operator_sequence(admitted)
                    or replay_l3 != _l3_sequence(admitted)
                ):
                    raise ValueError(f"accepted direct chain mismatch: {key!r}")
                accepted_chain_checks += 1
            outcome = "accepted"
            status = "accepted_train_authority"
            reason = "existing source-reviewed train-only authority passed replay checks"
            accepted_rows.append(dict(admitted))
        elif action == "auto_accept_candidate":
            if description is None:
                outcome = "deferred"
                status = "deferred_description_missing"
                reason = "deterministic description evidence is missing"
            elif description.get("description_fidelity_passed") is not True:
                outcome = "deferred"
                status = "deferred_description_fidelity"
                reason = "deterministic description fidelity gate failed"
            else:
                keys = _dedup_keys(description)
                duplicate_match: tuple[str, tuple[str, str]] | None = None
                for name in ("source_region", "call_graph", "training_pair"):
                    canonical = prospective_key_indexes[name].get(keys[name])
                    if canonical is not None:
                        duplicate_match = (name, canonical)
                        break
                if duplicate_match is not None:
                    name, canonical = duplicate_match
                    outcome = "duplicate"
                    status = "duplicate"
                    duplicate_reason = {
                        "source_region": "duplicate_source_region_suppressed",
                        "call_graph": "duplicate_call_graph_suppressed",
                        "training_pair": "exact_training_pair_suppressed",
                    }[name]
                    duplicate_of = canonical[0]
                    reason = duplicate_reason
                else:
                    for name in prospective_key_indexes:
                        prospective_key_indexes[name][keys[name]] = key
                    outcome = "deferred"
                    if description.get("parameter_evidence_status") == "verified_source_ast":
                        status = "deferred_training_admission"
                        reason = "source and description passed but train-only admission is absent"
                    else:
                        status = "deferred_source_replay"
                        reason = "source-backed parameter replay is unavailable for this description"
        else:
            outcome, status, reason = _route_status(route)

        ledger.append(
            {
                "schema": SCHEMA,
                "policy_version": POLICY_VERSION,
                "record_id": key[0],
                "source_sha256": key[1],
                "source_root_id": authority.get("source_root_id", ""),
                "source_path": authority.get("source_path", ""),
                "parse_status": authority.get("parse_status", ""),
                "route_source": route_source,
                "route_action": action,
                "route_rule_id": route.get("rule_id", ""),
                "route_reason": route.get("reason", {}),
                "mapping_authority": route.get("mapping_authority", ""),
                "operator_sequence": _operator_sequence(route),
                "l3_code_sequence": _l3_sequence(route),
                "call_sites": route.get("call_sites") or [],
                "dependency_edges": route.get("dependency_edges") or [],
                "workflow_unit_scope": route.get("workflow_unit_scope", ""),
                "structure_class": route.get("structure_class", ""),
                "normalization_status": route.get("normalization_status", ""),
                "mapping_complete": bool(route.get("mapping_complete", False)),
                "unmapped_operator_ids": route.get("unmapped_operator_ids") or [],
                "unresolved_operator_ids": route.get("unresolved_operator_ids") or [],
                "signature_hash": route.get("signature_hash")
                or route.get("feature_signature_hash", ""),
                "source_snippet": route.get("source_snippet", ""),
                "task_name": (
                    admitted.get("task_name", "")
                    if admitted
                    else description.get("task_name", "")
                    if description
                    else ""
                ),
                "task_description": (
                    admitted.get("task_description", "")
                    if admitted
                    else description.get("task_description", "")
                    if description
                    else ""
                ),
                "description_evidence_present": description is not None,
                "description_fidelity_passed": (
                    description.get("description_fidelity_passed")
                    if description is not None
                    else None
                ),
                "parameter_evidence_status": (
                    description.get("parameter_evidence_status", "")
                    if description is not None
                    else ""
                ),
                "outcome": outcome,
                "status": status,
                "status_reason": reason,
                "duplicate_reason": duplicate_reason,
                "duplicate_of_record_id": duplicate_of,
                "training_row_emitted": admitted is not None,
                "training_sample_id": admitted.get("sample_id", "") if admitted else "",
                "training_admission": (
                    admitted.get("training_admission") if admitted else "not_granted"
                ),
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
                "llm_called": False,
            }
        )

    outcomes = Counter(row["outcome"] for row in ledger)
    statuses = Counter(row["status"] for row in ledger)
    uncertain_training = sum(
        row["training_row_emitted"] and row["outcome"] != "accepted" for row in ledger
    )
    summary = {
        "schema": "gis_recommend.qgis_processing_unified_replay.summary.v1",
        "policy_version": POLICY_VERSION,
        "authority_rows": len(authorities),
        "base_replay_rows": len(base),
        "latest_overlay_rows": len(latest),
        "description_rows": len(descriptions),
        "matched_train_authority_rows": len(train),
        "outcome_counts": dict(sorted(outcomes.items())),
        "status_counts": dict(sorted(statuses.items())),
        "training_rows_emitted": len(accepted_rows),
        "quality_gate": {
            "authority_identity_unique": True,
            "base_replay_exact_coverage": True,
            "latest_overlay_strict_subset": True,
            "one_state_per_authority": len(ledger) == len(authorities),
            "accepted_chain_checks": accepted_chain_checks,
            "accepted_chain_mismatches": 0,
            "uncertain_training_rows": uncertain_training,
            "validation_test_rows": 0,
        },
        "llm_called": False,
        "training_run": False,
        "production_merge": "not_granted",
    }
    return ledger, accepted_rows, summary


def _diversity_order(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    by_root: dict[str, deque[dict[str, Any]]] = defaultdict(deque)
    for row in sorted(
        rows,
        key=lambda value: (
            str(value.get("source_root_id") or ""),
            str(value["source_sha256"]),
            str(value["record_id"]),
        ),
    ):
        by_root[str(row.get("source_root_id") or "unknown")].append(row)
    ordered: list[dict[str, Any]] = []
    roots = sorted(by_root)
    while any(by_root[root] for root in roots):
        for root in roots:
            if by_root[root]:
                ordered.append(by_root[root].popleft())
    return ordered


def select_calibration_rows(
    rows: list[dict[str, Any]], *, size: int = 200
) -> list[dict[str, Any]]:
    if size < 1 or size > len(rows):
        raise ValueError("calibration size must be within the replay row count")
    priority = [
        row
        for row in rows
        if row.get("route_action") == "auto_accept_candidate"
        or row.get("outcome") == "accepted"
    ]
    selected = _diversity_order(priority)[:size]
    selected_ids = {_identity(row) for row in selected}
    remaining = [row for row in rows if _identity(row) not in selected_ids]

    represented = {str(row["status"]) for row in selected}
    all_statuses = sorted({str(row["status"]) for row in rows})
    for status in all_statuses:
        if len(selected) == size or status in represented:
            continue
        candidate = next(
            row for row in _diversity_order(remaining) if row["status"] == status
        )
        selected.append(candidate)
        selected_ids.add(_identity(candidate))
        represented.add(status)
        remaining = [row for row in remaining if _identity(row) != _identity(candidate)]

    if len(selected) < size:
        by_status: dict[str, deque[dict[str, Any]]] = defaultdict(deque)
        for row in _diversity_order(remaining):
            by_status[str(row["status"])].append(row)
        statuses = sorted(by_status)
        while len(selected) < size:
            progressed = False
            for status in statuses:
                if by_status[status] and len(selected) < size:
                    selected.append(by_status[status].popleft())
                    progressed = True
            if not progressed:
                break
    return selected


def validate_full_gate(
    calibration_summary: dict[str, Any], *, input_hashes: dict[str, str]
) -> None:
    if calibration_summary.get("policy_version") != POLICY_VERSION:
        raise ValueError("calibration policy version does not match")
    if calibration_summary.get("quality_gate", {}).get("calibration_passed") is not True:
        raise ValueError("calibration quality gate did not pass")
    if calibration_summary.get("input_sha256") != input_hashes:
        raise ValueError("calibration input hashes do not match")


def finalize_phase_quality_gate(
    summary: dict[str, Any],
    *,
    phase: str,
    output_rows: list[dict[str, Any]],
    calibration_size: int,
) -> None:
    gate = summary["quality_gate"]
    shared_passed = bool(
        gate["one_state_per_authority"]
        and gate["accepted_chain_mismatches"] == 0
        and gate["uncertain_training_rows"] == 0
        and not any(
            row["validation_eligible"] or row["test_eligible"] for row in output_rows
        )
    )
    gate["calibration_passed"] = bool(
        shared_passed and (phase == "full" or len(output_rows) == calibration_size)
    )
    gate["calibration_gate_verified"] = phase == "full"


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_write(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding=encoding, newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    _atomic_write(
        path,
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
            for row in rows
        ),
    )


def write_outputs(
    rows: list[dict[str, Any]],
    accepted_rows: list[dict[str, Any]],
    summary: dict[str, Any],
    *,
    inputs: dict[str, Path],
    output_dir: Path,
) -> dict[str, Path]:
    if output_dir.exists() and any(output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {output_dir}")
    output_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = output_dir / "processing_replay_ledger_v1.jsonl"
    accepted_path = output_dir / "accepted_train_only_v1.jsonl"
    review_path = output_dir / "calibration_review_v1.csv"
    summary_path = output_dir / "summary_v1.json"
    hash_path = output_dir / "hash_ledger_v1.json"
    _write_jsonl(ledger_path, rows)
    _write_jsonl(accepted_path, accepted_rows)
    _atomic_write(
        summary_path,
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    review_fields = [
        "record_id",
        "source_sha256",
        "source_root_id",
        "source_path",
        "route_action",
        "route_rule_id",
        "status",
        "workflow_unit_scope",
        "structure_class",
        "operator_sequence",
        "l3_code_sequence",
        "unmapped_operator_ids",
        "unresolved_operator_ids",
        "call_sites",
        "dependency_edges",
        "source_snippet",
        "task_name",
        "task_description",
        "description_fidelity_passed",
        "status_reason",
        "boundary_fp_review",
        "chain_truncation_review",
        "description_fidelity_review",
        "review_notes",
    ]
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8-sig", newline="", dir=output_dir, delete=False
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=review_fields)
        writer.writeheader()
        for row in rows:
            writer.writerow(
                {
                    **{field: row.get(field, "") for field in review_fields},
                    "operator_sequence": json.dumps(row["operator_sequence"], ensure_ascii=False),
                    "l3_code_sequence": json.dumps(row["l3_code_sequence"], ensure_ascii=False),
                    "unmapped_operator_ids": json.dumps(
                        row["unmapped_operator_ids"], ensure_ascii=False
                    ),
                    "unresolved_operator_ids": json.dumps(
                        row["unresolved_operator_ids"], ensure_ascii=False
                    ),
                    "call_sites": json.dumps(row["call_sites"], ensure_ascii=False),
                    "dependency_edges": json.dumps(
                        row["dependency_edges"], ensure_ascii=False
                    ),
                    "boundary_fp_review": "",
                    "chain_truncation_review": "",
                    "description_fidelity_review": "",
                    "review_notes": "",
                }
            )
        temporary = Path(handle.name)
    temporary.replace(review_path)
    artifacts = (ledger_path, accepted_path, review_path, summary_path)
    _atomic_write(
        hash_path,
        json.dumps(
            {
                "schema": "gis_recommend.hash_ledger.v1",
                "source_inputs": {
                    name: {"path": str(path), "sha256": _sha256(path)}
                    for name, path in sorted(inputs.items())
                },
                "artifacts": {
                    path.name: {
                        "path": str(path),
                        "sha256": _sha256(path),
                        "bytes": path.stat().st_size,
                    }
                    for path in artifacts
                },
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
    return {
        "ledger": ledger_path,
        "accepted": accepted_path,
        "review": review_path,
        "summary": summary_path,
        "hash_ledger": hash_path,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--authority", type=Path, default=DEFAULT_AUTHORITY)
    parser.add_argument("--base-replay", type=Path, default=DEFAULT_BASE_REPLAY)
    parser.add_argument("--latest-replay", type=Path, default=DEFAULT_LATEST_REPLAY)
    parser.add_argument("--descriptions", type=Path, default=DEFAULT_DESCRIPTIONS)
    parser.add_argument("--train-authority", type=Path, default=DEFAULT_TRAIN_AUTHORITY)
    parser.add_argument("--phase", choices=("calibration", "full"), required=True)
    parser.add_argument("--calibration-size", type=int, default=200)
    parser.add_argument("--calibration-summary", type=Path)
    parser.add_argument("--expected-authority-rows", type=int, default=8466)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    inputs = {
        "authority": args.authority,
        "base_replay": args.base_replay,
        "latest_replay": args.latest_replay,
        "descriptions": args.descriptions,
        "train_authority": args.train_authority,
    }
    input_hashes = {name: _sha256(path) for name, path in sorted(inputs.items())}
    all_rows, all_accepted, summary = build_replay_ledger(
        _read_jsonl(args.authority),
        _read_jsonl(args.base_replay),
        _read_jsonl(args.latest_replay),
        _read_jsonl(args.descriptions),
        _read_jsonl(args.train_authority),
    )
    if len(all_rows) != args.expected_authority_rows:
        raise ValueError(
            f"authority rows {len(all_rows)} != expected {args.expected_authority_rows}"
        )

    if args.phase == "calibration":
        rows = select_calibration_rows(all_rows, size=args.calibration_size)
    else:
        if args.calibration_summary is None:
            raise ValueError("full replay requires --calibration-summary")
        validate_full_gate(
            json.loads(args.calibration_summary.read_text(encoding="utf-8")),
            input_hashes=input_hashes,
        )
        rows = all_rows
    selected_ids = {_identity(row) for row in rows}
    accepted = [row for row in all_accepted if _identity(row) in selected_ids]
    summary.update(
        {
            "phase": args.phase,
            "full_pool_rows_seen": len(all_rows),
            "output_ledger_rows": len(rows),
            "output_status_counts": dict(
                sorted(Counter(row["status"] for row in rows).items())
            ),
            "output_outcome_counts": dict(
                sorted(Counter(row["outcome"] for row in rows).items())
            ),
            "output_training_rows": len(accepted),
            "input_sha256": input_hashes,
        }
    )
    finalize_phase_quality_gate(
        summary,
        phase=args.phase,
        output_rows=rows,
        calibration_size=args.calibration_size,
    )
    write_outputs(accepted_rows=accepted, rows=rows, summary=summary, inputs=inputs, output_dir=args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
