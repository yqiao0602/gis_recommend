#!/usr/bin/env python3
"""Export hash-bound, agent-adjudicated QGIS Processing train-only rows."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_qgis_processing_batch import (
    _dedup_keys,
    _l3_sequence,
    _operator_sequence,
)


DEFAULT_REPORT = ROOT / "docs/reports/qgis_processing_second_batch_v5"
DEFAULT_EXISTING = (
    ROOT / "docs/reports/qgis_train_authority_v1/qgis_unified_train_v1.jsonl"
)
DEFAULT_STABLE110 = (
    ROOT
    / "docs/reports/qgis_processing_mapping_gap_stable106_v1"
    / "stable110_authority_v1/stable110_extension_v1.json"
)
DEFAULT_OUTPUT = ROOT / "docs/reports/qgis_processing_second_batch_train_v2"
PASS_FIELDS = (
    "boundary_decision",
    "operator_decision",
    "l3_decision",
    "description_decision",
)
SUPPRESSING_KEYS = ("source_region", "call_graph", "training_pair")
RULE_SIGNATURE_FIELDS = (
    "candidate_lane",
    "policy_version",
    "feature_extractor_version",
    "splitter_version",
    "recovery_rule_id",
    "parent_rule_id",
    "description_policy",
    "description_source",
    "local_structure_status",
    "split_class",
    "parameter_evidence_status",
    "workflow_unit_scope",
)


def _record_sha256(row: dict[str, Any]) -> str:
    payload = json.dumps(
        row, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256((payload + "\n").encode("utf-8")).hexdigest()


def _unit_id(row: dict[str, Any]) -> str:
    return str(row.get("unit_id") or f"record:{row.get('record_id', '')}")


def _index(rows: list[dict[str, Any]], field: str, label: str) -> dict[str, dict[str, Any]]:
    indexed: dict[str, dict[str, Any]] = {}
    for row in rows:
        key = str(row.get(field) or "")
        if not key or key in indexed:
            raise ValueError(f"{label} has blank or duplicate {field}: {key!r}")
        indexed[key] = row
    return indexed


def _validate_decision(row: dict[str, Any], decision: dict[str, Any]) -> None:
    candidate_id = str(row["candidate_id"])
    for field in (
        "candidate_id",
        "record_id",
        "source_sha256",
        "source_authority_key",
    ):
        if str(decision.get(field) or "") != str(row.get(field) or ""):
            raise ValueError(f"adjudication identity mismatch for {candidate_id}: {field}")
    if str(decision.get("unit_id") or "") != _unit_id(row):
        raise ValueError(f"adjudication identity mismatch for {candidate_id}: unit_id")
    if decision.get("candidate_payload_sha256") != _record_sha256(row):
        raise ValueError(f"candidate payload SHA256 mismatch: {candidate_id}")
    failed = [field for field in PASS_FIELDS if decision.get(field) != "pass"]
    if failed:
        raise ValueError(f"canonical candidate did not pass adjudication: {candidate_id} {failed}")


def _rule_signature(row: dict[str, Any]) -> tuple[str, ...]:
    return tuple(str(row.get(field) or "") for field in RULE_SIGNATURE_FIELDS)


def _training_row(
    candidate: dict[str, Any],
    token_ids: list[int],
    keys: dict[str, str],
    admission_basis: str,
    taxonomy_profile: str,
    source_replay_authority: str,
) -> dict[str, Any]:
    operators = _operator_sequence(candidate)
    l3_codes = _l3_sequence(candidate)
    task_name = str(candidate.get("task_name") or "").strip()
    task_description = str(candidate.get("task_description") or "").strip()
    call_sites = candidate.get("call_sites") or []
    if not operators or len(operators) != len(l3_codes) or len(operators) != len(token_ids):
        raise ValueError(f"operator/L3/token alignment failure: {candidate['candidate_id']}")
    if not task_name or not task_description or not call_sites:
        raise ValueError(f"incomplete training evidence: {candidate['candidate_id']}")
    task_type = "QGIS可验证Processing局部工作流"
    return {
        "schema_version": "qgis_processing_reviewed_training_sample_v1",
        "sample_id": f"qgis_processing_{candidate['candidate_id']}_train_v1",
        "record_id": candidate["record_id"],
        "candidate_id": candidate["candidate_id"],
        "unit_id": _unit_id(candidate),
        "source_path": candidate["source_path"],
        "source_sha256": candidate["source_sha256"],
        "source_authority_key": candidate["source_authority_key"],
        "source_verification": "verified_sha256",
        "source_replay_authority": source_replay_authority,
        "source_span": {
            "segments": [
                {
                    "line_start": int(site["line_start"]),
                    "line_end": int(site["line_end"]),
                }
                for site in call_sites
            ]
        },
        "evidence_snippet": candidate["source_snippet"],
        "operator_sequence": operators,
        "qgis_operator_chain": operators,
        "chain": operators,
        "l3_code_sequence": l3_codes,
        "l3_token_ids": token_ids,
        "l3_sequence": [-3, *token_ids, -4],
        "l3_codes": ["<START>", *l3_codes, "<END>"],
        "n": len(operators),
        "task_name": task_name,
        "task_description": task_description,
        "task_type": task_type,
        "task_metadata": {
            "task_type": task_type,
            "task_name": task_name,
            "task_description": task_description,
        },
        "workflow_scope": candidate.get("workflow_unit_scope"),
        "dependency_edges": candidate.get("dependency_edges") or [],
        "parameter_facts": candidate.get("parameter_facts") or [],
        "known_omissions": candidate.get("known_omissions") or [],
        "source_region_key": keys["source_region"],
        "call_graph_key": keys["call_graph"],
        "normalized_dag_key": keys["normalized_dag"],
        "cluster_id": keys["training_pair"],
        "review_split_origin": candidate.get("review_split"),
        "reviewer_kind": "codex_agent",
        "admission_basis": admission_basis,
        "adjudication_payload_sha256": _record_sha256(candidate),
        "source": "qgis_processing_source_replay_agent_adjudicated_v1",
        "_training_quality": {
            "tier": "source_verified_agent_adjudicated_processing",
            "sample_weight": 0.7,
        },
        "taxonomy_profile": taxonomy_profile,
        "training_admission": "granted_train_only_qgis_processing_review_v1",
        "split": "train_only_qgis_processing_review_v1",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
    }


def build_training_package(
    *,
    review_rows: list[dict[str, Any]],
    decisions: list[dict[str, Any]],
    existing_rows: list[dict[str, Any]],
    code_to_id: dict[str, int],
    candidate_rows: list[dict[str, Any]] | None = None,
    rule_authority: dict[str, Any] | None = None,
    taxonomy_profile: str = "stable110_authority_v1",
    source_replay_authority: str = "qgis_processing_second_batch_v5",
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    review = _index(review_rows, "candidate_id", "review packet")
    candidates = _index(candidate_rows or review_rows, "candidate_id", "candidate batch")
    adjudications = _index(decisions, "candidate_id", "adjudication")
    canonical_ids = {
        candidate_id
        for candidate_id, row in review.items()
        if row.get("dedup_status") == "canonical_candidate"
    }
    missing = canonical_ids - set(adjudications)
    extra = set(adjudications) - canonical_ids
    rule_authority_granted = (
        (rule_authority or {}).get("status")
        == "granted_source_disjoint_zero_failure"
    )
    if missing and not rule_authority_granted:
        raise ValueError(f"missing adjudication for canonical candidates: {sorted(missing)}")
    if extra:
        raise ValueError(f"adjudication includes non-canonical candidates: {sorted(extra)}")
    for candidate_id in adjudications:
        _validate_decision(review[candidate_id], adjudications[candidate_id])

    rule_signatures: set[tuple[str, ...]] = set()
    if candidates.keys() != review.keys():
        if not rule_authority_granted:
            raise ValueError("candidate batch expansion requires granted rule authority")
    if rule_authority_granted:
        if (rule_authority or {}).get("signature_fields") != list(RULE_SIGNATURE_FIELDS):
            raise ValueError("rule authority signature fields mismatch")
        split_coverage: dict[tuple[str, ...], set[str]] = {}
        for candidate_id in adjudications:
            signature = _rule_signature(review[candidate_id])
            split_coverage.setdefault(signature, set()).add(
                str(review[candidate_id].get("review_split") or "")
            )
        rule_signatures = {
            signature
            for signature, splits in split_coverage.items()
            if splits == {"calibration", "holdout"}
        }

    indexes = {name: {} for name in _dedup_keys(review_rows[0])} if review_rows else {}
    for row in existing_rows:
        reference = str(row.get("sample_id") or row.get("record_id") or "existing_train")
        for name, value in _dedup_keys(row).items():
            indexes[name].setdefault(value, reference)

    training: list[dict[str, Any]] = []
    ledger: list[dict[str, Any]] = []
    for candidate_id, row in sorted(candidates.items()):
        keys = _dedup_keys(row)
        entry = {
            "candidate_id": candidate_id,
            "record_id": row["record_id"],
            "source_sha256": row["source_sha256"],
            "source_authority_key": row["source_authority_key"],
            "unit_id": _unit_id(row),
            "dedup_status": row.get("dedup_status"),
            **{f"{name}_key": value for name, value in keys.items()},
        }
        if row.get("dedup_status") != "canonical_candidate":
            entry.update(
                {
                    "export_decision": "dedup_exclusion",
                    "duplicate_of": row.get("dedup_duplicate_of"),
                    "training_admission": "not_granted_dedup_exclusion",
                    "source_quality_rejection": False,
                }
            )
            ledger.append(entry)
            continue

        if candidate_id in adjudications:
            admission_basis = "per_row_agent_adjudication"
        elif _rule_signature(row) in rule_signatures:
            admission_basis = "source_disjoint_rule_authority"
        else:
            entry.update(
                {
                    "export_decision": "rule_signature_deferred",
                    "training_admission": "not_granted_unreviewed_rule_signature",
                    "source_quality_rejection": False,
                }
            )
            ledger.append(entry)
            continue

        match = next(
            (
                (name, indexes[name][keys[name]])
                for name in SUPPRESSING_KEYS
                if keys[name] in indexes[name]
            ),
            None,
        )
        if match:
            entry.update(
                {
                    "export_decision": "cross_pool_duplicate",
                    "duplicate_layer": match[0],
                    "duplicate_of": match[1],
                    "training_admission": "not_granted_cross_pool_duplicate",
                    "source_quality_rejection": False,
                }
            )
            ledger.append(entry)
            continue

        l3_codes = _l3_sequence(row)
        try:
            token_ids = [int(code_to_id[code]) for code in l3_codes]
        except KeyError as error:
            raise ValueError(f"L3 code missing from stable110: {error}") from error
        training.append(
            _training_row(
                row,
                token_ids,
                keys,
                admission_basis,
                taxonomy_profile,
                source_replay_authority,
            )
        )
        entry.update(
            {
                "export_decision": "accepted_train_only",
                "admission_basis": admission_basis,
                "training_admission": "granted_train_only_qgis_processing_review_v1",
                "source_quality_rejection": False,
            }
        )
        ledger.append(entry)
        for name, value in keys.items():
            indexes[name].setdefault(value, candidate_id)

    decisions_by_type = Counter(row["export_decision"] for row in ledger)
    summary = {
        "schema": "gis_recommend.qgis_processing_reviewed_export_summary.v1",
        "review_rows": len(review_rows),
        "candidate_rows": len(candidates),
        "reviewed_canonical_rows": len(canonical_ids),
        "dedup_exclusion_rows": decisions_by_type["dedup_exclusion"],
        "cross_pool_suppressed": decisions_by_type["cross_pool_duplicate"],
        "rule_authority_admitted_rows": sum(
            row.get("admission_basis") == "source_disjoint_rule_authority"
            for row in ledger
        ),
        "rule_signature_deferred_rows": decisions_by_type["rule_signature_deferred"],
        "train_only_rows": len(training),
        "unique_source_authorities": len(
            {row["source_authority_key"] for row in training}
        ),
        "reviewer_kind": "codex_agent",
        "taxonomy_profile": taxonomy_profile,
        "training_admission": "granted_train_only_qgis_processing_review_v1",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "llm_called": False,
        "training_run": False,
    }
    return training, ledger, summary


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _validate_bound_package(report_dir: Path, adjudication: dict[str, Any]) -> None:
    ledger_path = report_dir / "hash_ledger_v1.json"
    if adjudication.get("schema") != "gis_recommend.qgis_processing_adjudication.v1":
        raise ValueError("invalid adjudication schema")
    if adjudication.get("reviewer_kind") != "codex_agent":
        raise ValueError("adjudication must identify reviewer_kind=codex_agent")
    if adjudication.get("package_hash_ledger_sha256") != _sha256(ledger_path):
        raise ValueError("package hash ledger SHA256 mismatch")
    package = _read_json(ledger_path)
    for name, evidence in package.get("artifacts", {}).items():
        path = report_dir / name
        if not path.is_file() or _sha256(path) != evidence.get("sha256"):
            raise ValueError(f"package artifact SHA256 mismatch: {name}")
    for field, name in (
        ("candidate_batch_sha256", "candidate_batch_v1.jsonl"),
        ("review_packet_sha256", "source_disjoint_review_v1.jsonl"),
    ):
        if adjudication.get(field) != _sha256(report_dir / name):
            raise ValueError(f"{field} mismatch")


def _validate_candidate_package(report_dir: Path) -> Path:
    candidate_path = report_dir / "candidate_batch_v1.jsonl"
    ledger_path = report_dir / "hash_ledger_v1.json"
    if not candidate_path.is_file() or not ledger_path.is_file():
        raise ValueError("candidate package is incomplete")
    ledger = _read_json(ledger_path)
    expected = (ledger.get("artifacts") or {}).get(candidate_path.name, {}).get(
        "sha256"
    )
    if not expected or _sha256(candidate_path) != expected:
        raise ValueError("candidate package SHA256 mismatch")
    return candidate_path


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def _write_json(path: Path, value: Any) -> None:
    _atomic_write(
        path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    _atomic_write(
        path,
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
            for row in rows
        ),
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--candidate-report-dir", type=Path)
    parser.add_argument("--adjudication", type=Path)
    parser.add_argument("--existing-pool", type=Path, default=DEFAULT_EXISTING)
    parser.add_argument("--stable110-extension", type=Path, default=DEFAULT_STABLE110)
    parser.add_argument("--taxonomy-profile", default="stable110_authority_v1")
    parser.add_argument(
        "--source-replay-authority", default="qgis_processing_second_batch_v5"
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args(argv)
    adjudication_path = args.adjudication or args.report_dir / "adjudication_v1.json"
    adjudication = _read_json(adjudication_path)
    _validate_bound_package(args.report_dir, adjudication)
    candidate_path = _validate_candidate_package(
        args.candidate_report_dir or args.report_dir
    )

    extension = _read_json(args.stable110_extension)
    if extension.get("taxonomy_admission") != "granted":
        raise ValueError("stable110 taxonomy authority is not granted")
    code_to_id = {
        **extension["existing_code_to_id"],
        **extension["proposed_code_to_id_additions"],
    }
    training, ledger, summary = build_training_package(
        review_rows=_read_jsonl(args.report_dir / "source_disjoint_review_v1.jsonl"),
        candidate_rows=_read_jsonl(candidate_path),
        decisions=list(adjudication.get("decisions") or []),
        existing_rows=_read_jsonl(args.existing_pool),
        code_to_id=code_to_id,
        rule_authority=adjudication.get("rule_authority"),
        taxonomy_profile=args.taxonomy_profile,
        source_replay_authority=args.source_replay_authority,
    )

    training_path = args.output_dir / "qgis_processing_train_only_v1.jsonl"
    export_ledger_path = args.output_dir / "adjudication_export_ledger_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    _write_jsonl(training_path, training)
    _write_jsonl(export_ledger_path, ledger)
    _write_json(summary_path, summary)
    inputs = [
        args.report_dir / "hash_ledger_v1.json",
        candidate_path,
        args.report_dir / "source_disjoint_review_v1.jsonl",
        adjudication_path,
        args.existing_pool,
        args.stable110_extension,
    ]
    _write_json(
        args.output_dir / "hash_ledger_v1.json",
        {
            "schema": "gis_recommend.hash_ledger.v1",
            "inputs": {
                path.name: {"path": str(path), "sha256": _sha256(path)}
                for path in inputs
            },
            "artifacts": {
                path.name: {
                    "path": str(path),
                    "sha256": _sha256(path),
                    "bytes": path.stat().st_size,
                }
                for path in (training_path, export_ledger_path, summary_path)
            },
        },
    )
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
