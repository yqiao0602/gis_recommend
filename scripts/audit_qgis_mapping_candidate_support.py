#!/usr/bin/env python3
"""Audit normalized-body support and dry-run impact for QGIS mapping candidates."""

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


DEFAULT_REPLAY = (
    ROOT
    / "docs/reports/qgis_processing_stable120_replay_v1"
    / "l3_gated_manifest_v1.jsonl"
)
DEFAULT_MAPPING = (
    ROOT
    / "docs/reports/qgis_processing_stable120_authority_v1"
    / "composed_stable120_mapping_v1.json"
)


def select_candidate_rows(
    rows: Iterable[dict[str, Any]], candidates: dict[str, str]
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    identities: set[tuple[str, str]] = set()
    candidate_ids = set(candidates)
    for source in rows:
        gaps = {str(value).lower() for value in source.get("unmapped_operator_ids") or []}
        if not gaps & candidate_ids:
            continue
        key = (str(source.get("record_id") or ""), str(source.get("source_sha256") or ""))
        if not all(key) or key in identities:
            raise ValueError(f"blank or duplicate candidate identity: {key!r}")
        identities.add(key)
        selected.append(dict(source))
    return sorted(selected, key=lambda row: str(row["record_id"]))


def build_support_audit(
    rows: Iterable[dict[str, Any]],
    candidates: dict[str, str],
    *,
    support_gate: int = 30,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    ledger: list[dict[str, Any]] = []
    candidate_ids = set(candidates)
    for source in rows:
        path = Path(str(source.get("source_path") or ""))
        expected = str(source.get("source_sha256") or "")
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"source authority failure: {source.get('record_id')}")
        authority = source_authority(path, source_sha256=expected)
        if authority["source_authority_basis"] != "normalized_source_body_sha256":
            raise ValueError(f"normalized source body unavailable: {source.get('record_id')}")
        gaps = {
            str(value).lower() for value in source.get("unmapped_operator_ids") or []
        }
        for operator_id in sorted(gaps & candidate_ids):
            ledger.append(
                {
                    "schema": "gis_recommend.qgis_mapping_candidate_support.v1",
                    "record_id": str(source["record_id"]),
                    "source_sha256": expected,
                    "source_path": str(source.get("source_path_original") or path),
                    "source_root_id": str(source.get("source_root_id") or ""),
                    "normalization_status": str(
                        source.get("normalization_status") or ""
                    ),
                    "operator_id": operator_id,
                    "candidate_l3_code": candidates[operator_id],
                    **authority,
                    "mapping_admission": "not_granted_support_audit_only",
                    "training_admission": "not_granted",
                    "training_row_emitted": False,
                    "production_merge": "not_granted",
                }
            )

    candidate_support: dict[str, dict[str, Any]] = {}
    for operator_id, l3_code in sorted(candidates.items()):
        matched = [row for row in ledger if row["operator_id"] == operator_id]
        support = len(
            {row["normalized_source_body_sha256"] for row in matched}
        )
        candidate_support[operator_id] = {
            "candidate_l3_code": l3_code,
            "source_rows": len(matched),
            "unique_source_sha256": len({row["source_sha256"] for row in matched}),
            "normalized_source_body_support": support,
            "largest_body_cluster": max(
                Counter(
                    row["normalized_source_body_sha256"] for row in matched
                ).values(),
                default=0,
            ),
            "normalization_status_counts": dict(
                sorted(Counter(row["normalization_status"] for row in matched).items())
            ),
            "support_gate": support_gate,
            "support_gate_passed": support >= support_gate,
        }
    summary = {
        "schema": "gis_recommend.qgis_mapping_candidate_support.summary.v1",
        "candidate_support": candidate_support,
        "selected_source_rows": len(
            {(row["record_id"], row["source_sha256"]) for row in ledger}
        ),
        "ledger_rows": len(ledger),
        "source_authority_failures": 0,
        "mapping_admission": "not_granted_support_audit_only",
        "training_admission": "not_granted",
        "training_rows_emitted": 0,
        "llm_called": False,
        "production_merge": "not_granted",
    }
    return ledger, summary


def _impact(rows: list[dict[str, Any]], mapping: dict[str, str]) -> dict[str, int]:
    replayed = [
        apply_l3_gate(row, mapping, mapping_authority="candidate_support_dry_run")
        for row in rows
    ]
    return {
        "mapping_complete_rows": sum(bool(row["mapping_complete"]) for row in replayed),
        "direct_rows": sum(
            bool(row["mapping_complete"])
            and row["action"] == "auto_accept_candidate"
            for row in replayed
        ),
    }


def measure_dry_run(
    rows: Iterable[dict[str, Any]],
    base_mapping: dict[str, str],
    candidates: dict[str, str],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    source_rows = list(rows)
    normalized_base = {str(key).lower(): str(value) for key, value in base_mapping.items()}
    baseline = _impact(source_rows, normalized_base)
    by_operator: dict[str, dict[str, int]] = {}
    for operator_id, l3_code in sorted(candidates.items()):
        proposal = _impact(source_rows, {**normalized_base, operator_id: l3_code})
        by_operator[operator_id] = {
            "new_mapping_complete_rows": (
                proposal["mapping_complete_rows"] - baseline["mapping_complete_rows"]
            ),
            "new_direct_rows": proposal["direct_rows"] - baseline["direct_rows"],
        }

    combined_mapping = {**normalized_base, **candidates}
    combined = _impact(source_rows, combined_mapping)
    transitions: list[dict[str, Any]] = []
    for source in source_rows:
        before = apply_l3_gate(
            source, normalized_base, mapping_authority="stable_mapping_baseline"
        )
        after = apply_l3_gate(
            source, combined_mapping, mapping_authority="mapping_candidate_dry_run"
        )
        if (
            before["mapping_complete"] == after["mapping_complete"]
            and before["action"] == after["action"]
        ):
            continue
        after["baseline_mapping_complete"] = before["mapping_complete"]
        after["baseline_action"] = before["action"]
        after["proposal_only"] = True
        after["training_admission"] = "not_granted_mapping_candidate_dry_run"
        after["training_row_emitted"] = False
        transitions.append(after)
    impact = {
        "schema": "gis_recommend.qgis_mapping_candidate_dry_run_impact.v1",
        "input_rows": len(source_rows),
        "baseline": baseline,
        "by_operator": by_operator,
        "combined": {
            "new_mapping_complete_rows": (
                combined["mapping_complete_rows"] - baseline["mapping_complete_rows"]
            ),
            "new_direct_rows": combined["direct_rows"] - baseline["direct_rows"],
            "transition_rows": len(transitions),
        },
        "mapping_admission": "not_granted_support_audit_only",
        "training_rows_emitted": 0,
    }
    return sorted(transitions, key=lambda row: str(row.get("record_id") or "")), impact


def _parse_candidates(values: Iterable[str]) -> dict[str, str]:
    candidates: dict[str, str] = {}
    for value in values:
        operator_id, separator, l3_code = value.partition("=")
        operator_id = operator_id.strip().lower()
        l3_code = l3_code.strip()
        if not separator or not operator_id or not l3_code:
            raise ValueError(f"invalid candidate mapping: {value!r}")
        if operator_id in candidates:
            raise ValueError(f"duplicate candidate operator: {operator_id}")
        candidates[operator_id] = l3_code
    if not candidates:
        raise ValueError("at least one candidate mapping is required")
    return candidates


def _validate_hierarchy(candidates: dict[str, str], hierarchy_path: Path) -> None:
    with hierarchy_path.open(encoding="utf-8-sig", newline="") as handle:
        hierarchy_codes = {str(row.get("l3_code") or "") for row in csv.DictReader(handle)}
    missing = sorted(set(candidates.values()) - hierarchy_codes)
    if missing:
        raise ValueError("candidate L3 missing from hierarchy: " + ", ".join(missing))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _jsonl(rows: Iterable[dict[str, Any]]) -> str:
    return "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        + "\n"
        for row in rows
    )


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--replay", type=Path, default=DEFAULT_REPLAY)
    parser.add_argument("--mapping", type=Path, default=DEFAULT_MAPPING)
    parser.add_argument(
        "--hierarchy", type=Path, default=ROOT / "classification_hierarchy.csv"
    )
    parser.add_argument("--candidate", action="append", default=[])
    parser.add_argument("--ssh-host", default="qy@10.191.2.38")
    parser.add_argument("--remote-prefix-alias", action="append", default=[])
    parser.add_argument("--support-gate", type=int, default=30)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")

    candidates = _parse_candidates(args.candidate)
    _validate_hierarchy(candidates, args.hierarchy)
    aliases: list[tuple[str, str]] = []
    for value in args.remote_prefix_alias:
        old, separator, new = value.partition("=")
        if not separator or not old or not new:
            raise ValueError(f"invalid remote prefix alias: {value!r}")
        aliases.append((old, new))

    replay_rows = _read_jsonl(args.replay)
    selected = select_candidate_rows(replay_rows, candidates)
    with tempfile.TemporaryDirectory(prefix="qgis_mapping_candidate_support_") as temp:
        materialized = materialize_sources(
            selected,
            Path(temp),
            lambda path: _fetch_ssh_source(args.ssh_host, path),
            path_aliases=aliases,
        )
        ledger, summary = build_support_audit(
            materialized, candidates, support_gate=args.support_gate
        )
    transitions, impact = measure_dry_run(
        replay_rows,
        json.loads(args.mapping.read_text(encoding="utf-8")),
        candidates,
    )
    summary["dry_run_impact"] = impact

    ledger_path = args.output_dir / "source_authority_ledger_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    transitions_path = args.output_dir / "dry_run_transitions_v1.jsonl"
    report_path = args.output_dir / "report_v1.md"
    _write(ledger_path, _jsonl(ledger))
    _write(summary_path, json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    _write(transitions_path, _jsonl(transitions))
    report_lines = [
        "# QGIS mapping candidate support audit v1",
        "",
        "| operator | candidate L3 | source rows | normalized bodies | gate |",
        "|---|---|---:|---:|---|",
    ]
    for operator_id, row in summary["candidate_support"].items():
        report_lines.append(
            f"| `{operator_id}` | `{row['candidate_l3_code']}` | {row['source_rows']} | "
            f"{row['normalized_source_body_support']} | "
            f"{'pass' if row['support_gate_passed'] else 'defer'} |"
        )
    report_lines.extend(
        [
            "",
            f"- Combined new mapping-complete rows: {impact['combined']['new_mapping_complete_rows']}",
            f"- Combined new direct rows: {impact['combined']['new_direct_rows']}",
            "- Mapping/training admission: not granted",
            "",
        ]
    )
    _write(report_path, "\n".join(report_lines))
    hash_path = args.output_dir / "hash_ledger_v1.json"
    _write(
        hash_path,
        json.dumps(
            {
                "schema": "gis_recommend.hash_ledger.v1",
                "inputs": {
                    str(path): _sha256(path)
                    for path in (args.replay, args.mapping, args.hierarchy)
                },
                "artifacts": {
                    path.name: _sha256(path)
                    for path in (ledger_path, summary_path, transitions_path, report_path)
                },
                "remote_prefix_aliases": [
                    {"from": old, "to": new} for old, new in aliases
                ],
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
