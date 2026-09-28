#!/usr/bin/env python3
"""Audit independent source-body support for a QGIS Snap taxonomy proposal."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
for import_root in (ROOT, ROOT / "src", ROOT / "scripts"):
    if str(import_root) not in sys.path:
        sys.path.insert(0, str(import_root))

from evaluate_qgis_stable118_structure_increment import (  # noqa: E402
    _fetch_ssh_source,
    materialize_sources,
)
from gate_qgis_recovered_processing_l3 import apply_l3_gate  # noqa: E402
from gis_recommend.data.qgis_source_authority import source_authority  # noqa: E402


OPERATOR_ID = "native:snapgeometries"
CANDIDATE_L3 = "L3_02_07_09"
DEFAULT_REPLAY = (
    ROOT
    / "docs/reports/qgis_processing_mapping_gap_stable110_alias_replay_v2"
    / "replay_v3/l3_gated_manifest_v1.jsonl"
)
DEFAULT_STABLE110 = (
    ROOT
    / "docs/reports/qgis_processing_mapping_gap_stable106_v1"
    / "stable110_authority_v1/stable110_extension_v1.json"
)
DEFAULT_MAPPING = (
    ROOT
    / "docs/reports/qgis_processing_custom_scope_replay_v2_corrected_mapping"
    / "composed_stable110_mapping_v2_corrected.json"
)


def select_snap_rows(rows: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    identities: set[tuple[str, str]] = set()
    for source in rows:
        if OPERATOR_ID not in (source.get("unmapped_operator_ids") or []):
            continue
        key = (str(source.get("record_id") or ""), str(source.get("source_sha256") or ""))
        if not all(key) or key in identities:
            raise ValueError(f"blank or duplicate snap identity: {key!r}")
        identities.add(key)
        selected.append(dict(source))
    return sorted(selected, key=lambda row: str(row["record_id"]))


def build_support_audit(
    rows: Iterable[dict[str, Any]], *, support_gate: int = 30
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    ledger: list[dict[str, Any]] = []
    for source in rows:
        path = Path(str(source.get("source_path") or ""))
        expected = str(source.get("source_sha256") or "")
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"source authority failure: {source.get('record_id')}")
        authority = source_authority(path, source_sha256=expected)
        if authority["source_authority_basis"] != "normalized_source_body_sha256":
            raise ValueError(f"normalized source body unavailable: {source.get('record_id')}")
        ledger.append(
            {
                "schema": "gis_recommend.qgis_snap_taxonomy_support.v1",
                "record_id": str(source["record_id"]),
                "source_sha256": expected,
                "source_path": str(source.get("source_path_original") or path),
                "source_root_id": str(source.get("source_root_id") or ""),
                "normalization_status": str(source.get("normalization_status") or ""),
                "operator_id": OPERATOR_ID,
                "candidate_l3_code": CANDIDATE_L3,
                **authority,
                "mapping_admission": "not_granted_support_audit_only",
                "training_admission": "not_granted",
                "training_row_emitted": False,
                "production_merge": "not_granted",
            }
        )
    support = len({row["normalized_source_body_sha256"] for row in ledger})
    passed = support >= support_gate
    summary = {
        "schema": "gis_recommend.qgis_snap_taxonomy_support.summary.v1",
        "operator_id": OPERATOR_ID,
        "candidate_l3_code": CANDIDATE_L3,
        "source_rows": len(ledger),
        "source_sha_verified_rows": len(ledger),
        "unique_source_sha256": len({row["source_sha256"] for row in ledger}),
        "normalized_source_body_support": support,
        "normalization_status_counts": dict(
            sorted(Counter(row["normalization_status"] for row in ledger).items())
        ),
        "support_gate": support_gate,
        "support_gate_passed": passed,
        "taxonomy_admission": (
            "proposal_only_support_gate_passed"
            if passed
            else "not_granted_support_below_gate"
        ),
        "mapping_admission": "not_granted",
        "training_rows_emitted": 0,
        "llm_called": False,
        "production_merge": "not_granted",
    }
    return ledger, summary


def build_proposal(
    stable110: dict[str, Any],
    hierarchy: dict[str, str],
    support: dict[str, Any],
) -> tuple[dict[str, Any], dict[str, Any]]:
    if not support.get("support_gate_passed"):
        raise ValueError("Snap support gate did not pass")
    tokens = {
        **(stable110.get("existing_code_to_id") or {}),
        **(stable110.get("proposed_code_to_id_additions") or {}),
    }
    token_ids = sorted(int(value) for value in tokens.values())
    if token_ids != list(range(len(token_ids))) or CANDIDATE_L3 in tokens:
        raise ValueError("stable110 token authority is not contiguous or already contains Snap")
    token_id = len(token_ids)
    added = {
        "code": CANDIDATE_L3,
        "name": hierarchy["l3_name"],
        "definition": hierarchy["l3_description"],
        "l2_code": hierarchy["l2_code"],
        "l2_name": hierarchy["l2_name"],
        "l1_code": hierarchy["l1_code"],
        "l1_name": hierarchy["l1_name"],
        "aliases": [OPERATOR_ID],
        "proposed_token_id": token_id,
        "normalized_source_body_support": int(
            support["normalized_source_body_support"]
        ),
        "support_gate": int(support["support_gate"]),
        "taxonomy_admission": "proposal_only_pending_explicit_review",
    }
    extension = {
        "schema": "gis_recommend.qgis_stable111_snap_extension_proposal.v1",
        "base_taxonomy": "stable110",
        "proposed_taxonomy": "stable111",
        "base_class_count": token_id,
        "proposed_class_count": token_id + 1,
        "existing_code_to_id": dict(sorted(tokens.items(), key=lambda item: int(item[1]))),
        "proposed_code_to_id_additions": {CANDIDATE_L3: token_id},
        "added_l3": [added],
        "existing_token_ids_unchanged": True,
        "taxonomy_admission": "proposal_only_pending_explicit_review",
        "mapping_admission": "not_granted",
        "training_admission": "not_granted",
        "production_merge": "not_granted",
    }
    delta = {
        "schema": "gis_recommend.qgis_stable111_snap_mapping_delta_proposal.v1",
        "status": "proposal_only_pending_explicit_review",
        "alias_mappings": {},
        "restored_l3_mappings": {OPERATOR_ID: CANDIDATE_L3},
        "mapping_exclusions": {},
        "parameter_conditioned_deferred": {
            "grass7:v.clean#tool=snap": (
                "requires separate parameter-conditioned replay; not an unconditional operator alias"
            )
        },
        "taxonomy_admission": "proposal_only_pending_explicit_review",
        "mapping_admission": "not_granted",
        "training_admission": "not_granted",
        "production_merge": "not_granted",
    }
    return extension, delta


def measure_dry_run(
    rows: Iterable[dict[str, Any]], base_mapping: dict[str, str]
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_rows = list(rows)
    proposal_mapping = {**base_mapping, OPERATOR_ID: CANDIDATE_L3}
    transitions: list[dict[str, Any]] = []
    baseline_complete = proposal_complete = baseline_direct = proposal_direct = 0
    for source in source_rows:
        baseline = apply_l3_gate(source, base_mapping, mapping_authority="stable110_current")
        proposal = apply_l3_gate(
            source, proposal_mapping, mapping_authority="stable111_snap_proposal_only"
        )
        baseline_complete += int(baseline["mapping_complete"])
        proposal_complete += int(proposal["mapping_complete"])
        baseline_direct += int(
            baseline["mapping_complete"] and baseline["action"] == "auto_accept_candidate"
        )
        proposal_direct += int(
            proposal["mapping_complete"] and proposal["action"] == "auto_accept_candidate"
        )
        if baseline["mapping_complete"] == proposal["mapping_complete"] and baseline["action"] == proposal["action"]:
            continue
        proposal["baseline_mapping_complete"] = baseline["mapping_complete"]
        proposal["baseline_action"] = baseline["action"]
        proposal["proposal_only"] = True
        proposal["training_admission"] = "not_granted_taxonomy_proposal_only"
        proposal["training_row_emitted"] = False
        transitions.append(proposal)
    impact = {
        "schema": "gis_recommend.qgis_stable111_snap_dry_run_impact.v1",
        "input_rows": len(source_rows),
        "baseline_mapping_complete_rows": baseline_complete,
        "proposal_mapping_complete_rows": proposal_complete,
        "new_mapping_complete_rows": proposal_complete - baseline_complete,
        "baseline_direct_rows": baseline_direct,
        "proposal_direct_rows": proposal_direct,
        "new_direct_rows": proposal_direct - baseline_direct,
        "transition_rows": len(transitions),
        "training_rows_emitted": 0,
        "mapping_admission": "not_granted_proposal_only",
    }
    return sorted(transitions, key=lambda row: str(row.get("record_id") or "")), impact


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", newline="", dir=path.parent, delete=False) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def _jsonl(rows: Iterable[dict[str, Any]]) -> str:
    return "".join(json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n" for row in rows)


def _validate_taxonomy(stable110: dict[str, Any], hierarchy_path: Path) -> dict[str, str]:
    active = set(stable110.get("existing_code_to_id") or {}) | set(
        stable110.get("proposed_code_to_id_additions") or {}
    )
    if CANDIDATE_L3 in active:
        raise ValueError(f"{CANDIDATE_L3} is already active in stable110")
    with hierarchy_path.open(encoding="utf-8-sig", newline="") as handle:
        matches = [row for row in csv.DictReader(handle) if row.get("l3_code") == CANDIDATE_L3]
    if len(matches) != 1 or matches[0].get("l3_name") != "Snap":
        raise ValueError("expected one Snap row in classification hierarchy")
    return matches[0]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay", type=Path, default=DEFAULT_REPLAY)
    parser.add_argument("--stable110", type=Path, default=DEFAULT_STABLE110)
    parser.add_argument("--mapping", type=Path, default=DEFAULT_MAPPING)
    parser.add_argument("--hierarchy", type=Path, default=ROOT / "classification_hierarchy.csv")
    parser.add_argument("--ssh-host", default="qy@10.191.2.38")
    parser.add_argument("--remote-prefix-alias", action="append", default=[])
    parser.add_argument("--support-gate", type=int, default=30)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    stable110 = json.loads(args.stable110.read_text(encoding="utf-8"))
    hierarchy = _validate_taxonomy(stable110, args.hierarchy)
    aliases = []
    for value in args.remote_prefix_alias:
        old, separator, new = value.partition("=")
        if not separator or not old or not new:
            raise ValueError(f"invalid remote prefix alias: {value!r}")
        aliases.append((old, new))
    replay_rows = _read_jsonl(args.replay)
    selected = select_snap_rows(replay_rows)
    with tempfile.TemporaryDirectory(prefix="qgis_snap_support_") as temp:
        materialized = materialize_sources(
            selected,
            Path(temp),
            lambda path: _fetch_ssh_source(args.ssh_host, path),
            path_aliases=aliases,
        )
        ledger, summary = build_support_audit(materialized, support_gate=args.support_gate)
    summary["candidate_l3_name"] = hierarchy["l3_name"]
    summary["candidate_l3_description"] = hierarchy["l3_description"]
    extension, delta = build_proposal(stable110, hierarchy, summary)
    transitions, impact = measure_dry_run(
        replay_rows, json.loads(args.mapping.read_text(encoding="utf-8"))
    )
    summary["dry_run_impact"] = impact
    ledger_path = args.output_dir / "source_authority_ledger_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    report_path = args.output_dir / "report_v1.md"
    extension_path = args.output_dir / "stable111_extension_proposal_v1.json"
    delta_path = args.output_dir / "mapping_delta_proposal_v1.json"
    transitions_path = args.output_dir / "dry_run_transitions_v1.jsonl"
    impact_path = args.output_dir / "dry_run_impact_v1.json"
    _write(ledger_path, _jsonl(ledger))
    _write(summary_path, json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    _write(extension_path, json.dumps(extension, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    _write(delta_path, json.dumps(delta, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    _write(transitions_path, _jsonl(transitions))
    _write(impact_path, json.dumps(impact, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    _write(
        report_path,
        "\n".join(
            [
                "# QGIS Snap taxonomy support audit v1",
                "",
                f"- Source rows: {summary['source_rows']}",
                f"- SHA verified: {summary['source_sha_verified_rows']}",
                f"- Independent normalized source bodies: {summary['normalized_source_body_support']}",
                f"- Support gate: {summary['support_gate']}",
                f"- Gate passed: {str(summary['support_gate_passed']).lower()}",
                f"- New mapping-complete rows in dry-run: {impact['new_mapping_complete_rows']}",
                f"- New direct rows in dry-run: {impact['new_direct_rows']}",
                "- Mapping/training admission: not granted",
                "",
                "Passing this audit permits a taxonomy proposal only. It does not modify stable110 or emit training rows.",
                "",
            ]
        ),
    )
    hash_path = args.output_dir / "hash_ledger_v1.json"
    _write(
        hash_path,
        json.dumps(
            {
                "schema": "gis_recommend.hash_ledger.v1",
                "inputs": {
                    str(path): _sha256(path)
                    for path in (args.replay, args.stable110, args.mapping, args.hierarchy)
                },
                "artifacts": {
                    path.name: _sha256(path)
                    for path in (
                        ledger_path,
                        summary_path,
                        report_path,
                        extension_path,
                        delta_path,
                        transitions_path,
                        impact_path,
                    )
                },
                "remote_prefix_aliases": [{"from": old, "to": new} for old, new in aliases],
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
