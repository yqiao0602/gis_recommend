#!/usr/bin/env python3
"""Qualify the unique Processing operator pool against the existing L3 authority.

This is the operator-level semantic/L3 gate. It joins the repaired evidence
sidecar (v7) to the unique operator aggregation, resolves each operator through
the 170-operator composed mapping authority and the 128-token taxonomy, and
emits exactly three verdicts: ``QUALIFIED``, ``DEFERRED``, ``FAIL_CLOSED``.

A ``qgis:<slug>`` operator is only QUALIFIED through the ``native:<slug>``
mapping when every backing row carries an independently verified same-slug alias
proof. ``gdalogr:``/``grass:``/``sagang:`` alias shapes have no precedent
authority and stay deferred. Catalog providers without a mapping stay deferred;
non-catalog (third-party) providers fail closed. Parameter and I/O evidence is
recorded as coverage, not as a gate: this layer decides whether an operator can
be grounded in the taxonomy, not whether a training row exists. No training row
is emitted and no authority is modified.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

SCHEMA = "gis_recommend.qgis_processing_operator_qualification.v1"
CATALOG_PROVIDERS = frozenset({"native", "qgis", "gdal", "gdalogr", "grass", "grass7", "saga", "sagang", "otb"})
ALIAS_TARGET_PROVIDER = {"qgis": "native", "gdalogr": "gdal", "grass": "grass7", "sagang": "saga"}
ALIAS_PRECEDENT_PROVIDERS = frozenset({"qgis"})
EXPECTED_OPERATOR_COUNT = 207
EXPECTED_SUPPORT_ROWS = 591


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _load_taxonomy(path: Path) -> dict[str, dict[str, Any]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return {str(entry["l3_code"]): entry for entry in data["classes"]}


def _load_alias_proofs(path: Path | None) -> dict[tuple[str, str], dict[str, Any]]:
    if path is None or not path.is_file():
        return {}
    proofs: dict[tuple[str, str], dict[str, Any]] = {}
    for row in read_jsonl(path):
        proofs[(str(row.get("record_id") or ""), str(row.get("source_operator") or ""))] = row
    return proofs


def _operator_rows(sidecar_rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in sidecar_rows:
        for call in row.get("calls") or []:
            groups[str(call.get("operator_id") or "")].append(row)
    return groups


def qualify(
    sidecar_rows: list[dict[str, Any]],
    mapping: dict[str, str],
    taxonomy: dict[str, dict[str, Any]],
    alias_proofs: dict[tuple[str, str], dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    ledger: list[dict[str, Any]] = []
    for operator_id, rows in sorted(_operator_rows(sidecar_rows).items()):
        provider = operator_id.partition(":")[0] if ":" in operator_id else None
        slug = operator_id.partition(":")[2] if ":" in operator_id else ""
        calls = [call for row in rows for call in row.get("calls") or [] if str(call.get("operator_id") or "") == operator_id]
        source_verified_rows = sum(row.get("status") == "source_verified_ast" for row in rows)
        entry: dict[str, Any] = {
            "schema": SCHEMA,
            "operator_id": operator_id,
            "provider": provider,
            "support_rows": len(rows),
            "unique_source_sha256": len({str(row.get("source_sha256") or "") for row in rows if row.get("source_sha256")}),
            "operator_identity": {
                "source_verified_rows": source_verified_rows,
                "literal_source_evidence_rows": sum(call.get("resolution_kind") == "literal_source_evidence" for call in calls),
                "status": "verified" if source_verified_rows == len(rows) else "deferred_source_evidence_incomplete",
            },
            "provider_evidence": {
                "prefix_rows": sum(
                    call.get("provider_evidence", {}).get("status") == "operator_id_prefix"
                    and call.get("provider_evidence", {}).get("provider_id") == provider
                    for call in calls
                ),
            },
            "parameter_evidence": {
                "status_counts": dict(sorted(Counter(call["parameter_evidence"]["status"] for call in calls).items())),
                "completeness_counts": dict(sorted(Counter(call["parameter_evidence"]["completeness"] for call in calls).items())),
            },
            "io_evidence": {
                "status_counts": dict(sorted(Counter(call["io_evidence"]["status"] for call in calls).items())),
            },
            "entrypoint_counts": dict(sorted(Counter(call["entrypoint"] for call in calls).items())),
            "l3": {},
            "qualification_status": None,
            "qualification_path": None,
            "training_admission": "not_granted_qualification_only",
            "training_rows_emitted": 0,
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
            "provenance": {
                "sidecar_schema": sorted({str(row.get("schema") or "") for row in rows}),
                "mapping_authority": "composed_stable124_mapping_v1",
                "taxonomy_authority": "taxonomy_128_v1",
                "record_ids": sorted({str(row.get("record_id") or "") for row in rows}),
            },
        }

        proposed_l3: str | None = None
        alias: dict[str, Any] | None = None
        if operator_id in mapping:
            path = "exact_mapping"
            proposed_l3 = mapping[operator_id]
        elif provider in ALIAS_TARGET_PROVIDER:
            canonical = f"{ALIAS_TARGET_PROVIDER[provider]}:{slug}"
            if canonical not in mapping:
                path = "no_mapping_authority"
            else:
                alias = {
                    "rule": "same_slug_provider_alias",
                    "canonical_operator": canonical,
                    "precedent": provider in ALIAS_PRECEDENT_PROVIDERS,
                }
                if provider not in ALIAS_PRECEDENT_PROVIDERS:
                    path = "alias_deferred_no_precedent"
                    alias["verified_rows"] = 0
                else:
                    proofs = [alias_proofs.get((str(row.get("record_id") or ""), operator_id)) for row in rows]
                    verified = sum(proof is not None and proof.get("status") == "verified_exact_same_slug" for proof in proofs)
                    alias["verified_rows"] = verified
                    alias["failed_rows"] = len(rows) - verified
                    if verified == len(rows) and rows:
                        path = "verified_alias_same_slug"
                        proposed_l3 = mapping[canonical]
                    else:
                        path = "alias_proof_incomplete"
        elif provider in CATALOG_PROVIDERS:
            path = "no_mapping_authority"
        else:
            path = "third_party_provider"

        if proposed_l3 is not None and proposed_l3 not in taxonomy:
            path = "l3_target_outside_taxonomy"

        entry["qualification_path"] = path
        if alias is not None:
            entry["alias"] = alias
        if path == "third_party_provider":
            entry["qualification_status"] = "FAIL_CLOSED"
            entry["fail_reason"] = "third_party_or_malformed_provider_outside_catalog"
        elif path in {"exact_mapping", "verified_alias_same_slug"} and entry["operator_identity"]["status"] == "verified":
            entry["qualification_status"] = "QUALIFIED"
            taxonomy_entry = taxonomy[proposed_l3]
            entry["l3"] = {
                "proposed_l3_code": proposed_l3,
                "token_id": taxonomy_entry["token_id"],
                "l3_name": taxonomy_entry["l3_name"],
                "mapping_source": "composed_stable124_mapping_v1" + ("" if path == "exact_mapping" else f" via {entry['alias']['canonical_operator']}"),
                "ambiguity": "unambiguous_single_authority_mapping",
            }
        else:
            entry["qualification_status"] = "DEFERRED"
            entry["defer_reason"] = {
                "alias_deferred_no_precedent": "no_precedent_authority_for_provider_alias",
                "alias_proof_incomplete": "alias_proof_missing_or_failed_for_backing_rows",
                "no_mapping_authority": "no_mapping_in_composed_stable124",
                "l3_target_outside_taxonomy": "mapping_target_not_in_taxonomy_128",
            }.get(path, "operator_identity_evidence_incomplete")
        ledger.append(entry)

    status_counts = Counter(entry["qualification_status"] for entry in ledger)
    path_counts = Counter(entry["qualification_path"] for entry in ledger)
    summary = {
        "schema": f"{SCHEMA}.summary",
        "sidecar_rows": len(sidecar_rows),
        "operator_count": len(ledger),
        "support_rows": sum(entry["support_rows"] for entry in ledger),
        "unique_source_sha256": sum(entry["unique_source_sha256"] for entry in ledger),
        "operator_count_check": "matched" if len(ledger) == EXPECTED_OPERATOR_COUNT else "mismatch",
        "support_rows_check": "matched" if sum(entry["support_rows"] for entry in ledger) == EXPECTED_SUPPORT_ROWS else "mismatch",
        "qualification_status_counts": dict(sorted(status_counts.items())),
        "qualification_path_counts": dict(sorted(path_counts.items())),
        "qualified_support_rows": sum(entry["support_rows"] for entry in ledger if entry["qualification_status"] == "QUALIFIED"),
        "deferred_support_rows": sum(entry["support_rows"] for entry in ledger if entry["qualification_status"] == "DEFERRED"),
        "fail_closed_support_rows": sum(entry["support_rows"] for entry in ledger if entry["qualification_status"] == "FAIL_CLOSED"),
        "qualified_l3_codes": sorted({entry["l3"]["proposed_l3_code"] for entry in ledger if entry["qualification_status"] == "QUALIFIED"}),
        "training_rows_emitted": 0,
        "training_admission": "not_granted_qualification_only",
        "formal_authority_modified": False,
    }
    return ledger, summary


def status_counts_bold(summary: dict[str, Any], status: str) -> str:
    return str(summary["qualification_status_counts"].get(status, 0))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sidecar", type=Path, required=True)
    parser.add_argument("--mapping", type=Path, required=True)
    parser.add_argument("--taxonomy", type=Path, required=True)
    parser.add_argument("--alias-proof", type=Path, default=None)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    mapping = json.loads(args.mapping.read_text(encoding="utf-8"))
    ledger, summary = qualify(
        read_jsonl(args.sidecar),
        mapping,
        _load_taxonomy(args.taxonomy),
        _load_alias_proofs(args.alias_proof),
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    ledger_path = args.output_dir / "qualification_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    report_path = args.output_dir / "qualification_report_v1.md"
    ledger_path.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in ledger), encoding="utf-8")
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    report_path.write_text(
        "# QGIS Processing operator semantic/L3 qualification v1\n\n"
        "Three-state operator-level qualification against the existing authority. "
        "No L3 grant, training row, authority change, or evaluation change is made here.\n\n"
        + "\n".join(
            [
                f"- Operator count: **{summary['operator_count']}** ({summary['operator_count_check']})",
                f"- Support rows: **{summary['support_rows']}** ({summary['support_rows_check']})",
                f"- QUALIFIED operators: **{status_counts_bold(summary, 'QUALIFIED')}** (support {summary['qualified_support_rows']})",
                f"- DEFERRED operators: **{status_counts_bold(summary, 'DEFERRED')}** (support {summary['deferred_support_rows']})",
                f"- FAIL_CLOSED operators: **{status_counts_bold(summary, 'FAIL_CLOSED')}** (support {summary['fail_closed_support_rows']})",
                f"- Path counts: `{json.dumps(summary['qualification_path_counts'], ensure_ascii=False, sort_keys=True)}`",
                f"- Qualified L3 codes: `{json.dumps(summary['qualified_l3_codes'], ensure_ascii=False)}`",
                f"- Training rows emitted: **{summary['training_rows_emitted']}**",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    hashes = {path.name: hashlib.sha256(path.read_bytes()).hexdigest() for path in (ledger_path, summary_path, report_path)}
    hashes["sidecar_input"] = hashlib.sha256(args.sidecar.read_bytes()).hexdigest()
    hashes["mapping_input"] = hashlib.sha256(args.mapping.read_bytes()).hexdigest()
    hashes["taxonomy_input"] = hashlib.sha256(args.taxonomy.read_bytes()).hexdigest()
    if args.alias_proof is not None and args.alias_proof.is_file():
        hashes["alias_proof_input"] = hashlib.sha256(args.alias_proof.read_bytes()).hexdigest()
    (args.output_dir / "hash_ledger_v1.json").write_text(json.dumps(hashes, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
