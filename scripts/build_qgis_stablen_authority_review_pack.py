#!/usr/bin/env python3
"""Build a taxonomy-review pack for the stable101 conservative QGIS draft.

This package is review-only. It is meant to be read by taxonomy authority
after the stable101 conservative draft has already been generated from the
source-reviewed conservative mappings.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from pathlib import Path
from typing import Any, Iterable


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def _write_json(path: Path, value: Any) -> None:
    _atomic_write_text(
        path,
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    _atomic_write_text(
        path,
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
    )


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    fieldnames = list(rows[0]) if rows else []
    with temporary.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        if rows:
            writer.writeheader()
            writer.writerows(rows)
    temporary.replace(path)


def _accepted_rows(
    proposal: dict[str, Any],
    delta: dict[str, Any],
    source_review_gate: dict[str, Any],
) -> list[dict[str, Any]]:
    accepted_ops = list(delta.get("restored_l3_mappings", {}))
    reviewed = source_review_gate.get("reviewed_operators", {})
    if not isinstance(reviewed, dict):
        raise ValueError("source_review_gate.reviewed_operators must be an object")
    proposal_by_code = {
        str(row.get("l3_code", "")): dict(row)
        for row in proposal.get("restored_l3", [])
        if isinstance(row, dict)
    }

    rows: list[dict[str, Any]] = []
    for operator_id in sorted(accepted_ops):
        l3_code = str(delta["restored_l3_mappings"][operator_id])
        proposal_row = proposal_by_code.get(l3_code, {})
        review_row = reviewed.get(operator_id, {})
        sample_refs = review_row.get("sample_refs", [])
        rows.append(
            {
                "operator_id": operator_id,
                "candidate_l3_code": l3_code,
                "candidate_l3_name": proposal_row.get("l3_name", ""),
                "candidate_l3_description": proposal_row.get("l3_description", ""),
                "scenario": proposal_row.get("scenario", "conservative"),
                "confidence": proposal_row.get("confidence", "high"),
                "training_role": proposal_row.get(
                    "training_role", "core_candidate_after_authority"
                ),
                "review_reason": proposal_row.get("review_reason", ""),
                "source_samples": int(review_row.get("selected_samples", 0)),
                "unique_layer_hits": int(review_row.get("unique_layer_hits", 0)),
                "sample_refs_json": json.dumps(sample_refs, ensure_ascii=False, sort_keys=True),
                "source_review_verdict": "accept_mapping_after_authority",
                "review_status": "pending_taxonomy_review",
                "human_decision": "",
                "reviewer": "",
                "review_notes": "",
                "taxonomy_admission": "not_granted",
                "training_admission": "not_granted",
            }
        )
    return rows


def _boundary_rows(delta: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in delta.get("excluded_boundary_entries", []):
        if not isinstance(row, dict):
            continue
        rows.append(
            {
                "operator_id": row.get("operator_id", ""),
                "candidate_l3_code": row.get("candidate_l3_code", ""),
                "candidate_l3_name": row.get("candidate_l3_name", ""),
                "scenario": row.get("scenario", ""),
                "training_role": row.get("training_role", ""),
                "exclusion_reason": row.get("exclusion_reason", ""),
                "taxonomy_admission": "not_granted",
                "training_admission": "not_granted",
            }
        )
    return sorted(rows, key=lambda row: row["operator_id"])


def _review_markdown(
    proposal: dict[str, Any],
    review_rows: list[dict[str, Any]],
    boundary_rows: list[dict[str, Any]],
    impact: dict[str, Any],
) -> str:
    lines = [
        "# Stable101 Taxonomy Review Pack",
        "",
        "This package is review-only. It contains only the four source-reviewed conservative mappings from the stable101 draft.",
        "",
        "## Scope",
        "",
        f"- Base taxonomy: {proposal.get('base_taxonomy', '')} ({proposal.get('base_class_count', '')} L3).",
        f"- Draft taxonomy: {proposal.get('proposed_taxonomy', '')} ({proposal.get('proposed_class_count', '')} L3).",
        f"- Coverage gain: +{impact['increment_vs_stable98']['records']} records / +{impact['increment_vs_stable98']['unique_chains']} chains.",
        "",
        "## Review Rows",
        "",
        "| operator | candidate L3 | samples | unique hits | recommendation |",
        "|---|---|---:|---:|---|",
    ]
    for row in review_rows:
        lines.append(
            f"| `{row['operator_id']}` | `{row['candidate_l3_code']}` {row['candidate_l3_name']} | "
            f"{row['source_samples']} | {row['unique_layer_hits']} | {row['source_review_verdict']} |"
        )
    lines.extend(
        [
            "",
            "## Boundary Sidecar",
            "",
            "| operator | candidate L3 | reason |",
            "|---|---|---|",
        ]
    )
    for row in boundary_rows:
        lines.append(
            f"| `{row['operator_id']}` | `{row['candidate_l3_code']}` {row['candidate_l3_name']} | "
            f"{row['exclusion_reason']} |"
        )
    lines.extend(
        [
            "",
            "## Review Contract",
            "",
            "- Accept only if the four conservative mappings are approved as formal taxonomy entries.",
            "- Keep the two boundary operators deferred until a separate support/export strategy exists.",
            "- Do not write review rows into `outputs_v2` or any training export before approval.",
            "",
        ]
    )
    return "\n".join(lines)


def build_review_pack(
    *,
    proposal_path: Path,
    delta_path: Path,
    source_review_gate_path: Path,
    impact_path: Path,
    output_dir: Path,
    date: str,
) -> dict[str, Any]:
    proposal = _read_json(proposal_path)
    delta = _read_json(delta_path)
    source_review_gate = _read_json(source_review_gate_path)
    impact = _read_json(impact_path)

    if proposal.get("proposed_taxonomy") != "stable101":
        raise ValueError("review pack expects the stable101 proposal")
    if int(proposal.get("base_class_count", -1)) != 98:
        raise ValueError("stable101 review pack expects stable98 as the base")
    if int(proposal.get("proposed_class_count", -1)) != 101:
        raise ValueError("stable101 review pack expects 101 total classes")
    if int(delta.get("operator_count", -1)) != 4:
        raise ValueError("stable101 review pack expects four conservative operators")
    if int(delta.get("excluded_boundary_operator_count", -1)) != 2:
        raise ValueError("stable101 review pack expects two boundary exclusions")
    if source_review_gate.get("status") != "passed":
        raise ValueError("source review gate must be passed")
    if int(source_review_gate.get("accepted_operator_count", -1)) != 4:
        raise ValueError("source review gate must cover four accepted operators")

    review_rows = _accepted_rows(proposal, delta, source_review_gate)
    boundary_rows = _boundary_rows(delta)
    summary = {
        "schema": "gis_recommend.qgis_stablen_authority_review_pack.v1",
        "status": "review_ready",
        "date": date,
        "base_taxonomy": proposal.get("base_taxonomy", ""),
        "proposed_taxonomy": proposal.get("proposed_taxonomy", ""),
        "review_row_count": len(review_rows),
        "boundary_row_count": len(boundary_rows),
        "review_operator_count": len(review_rows),
        "taxonomy_admission": "not_granted",
        "training_admission": "not_granted",
        "input_sha256": {
            "proposal": _sha256(proposal_path),
            "delta": _sha256(delta_path),
            "source_review_gate": _sha256(source_review_gate_path),
            "impact": _sha256(impact_path),
        },
    }

    output_dir.mkdir(parents=True, exist_ok=True)
    review_csv = output_dir / "stable101_authority_review.csv"
    review_jsonl = output_dir / "stable101_authority_review.jsonl"
    boundary_json = output_dir / "stable101_boundary_sidecar.json"
    summary_path = output_dir / "stable101_authority_review_summary.json"
    report_path = output_dir / "stable101_authority_review.md"
    instructions_path = output_dir / "REVIEW_INSTRUCTIONS.md"
    ledger_path = output_dir / "hash_ledger.json"

    _write_csv(review_csv, review_rows)
    _write_jsonl(review_jsonl, review_rows)
    _write_json(boundary_json, boundary_rows)
    _atomic_write_text(
        report_path,
        _review_markdown(proposal, review_rows, boundary_rows, impact),
    )
    _atomic_write_text(
        instructions_path,
        "# Stable101 Taxonomy Review\n\n"
        "Review only the four conservative mappings in the CSV/JSONL package.\n"
        "Do not accept the boundary sidecar as training material.\n"
        "Keep all rows out of `outputs_v2` until formal approval.\n",
    )
    _write_json(summary_path, summary)

    output_files = [review_csv, review_jsonl, boundary_json, summary_path, report_path, instructions_path]
    ledger = {
        "schema": "gis_recommend.qgis_stablen_authority_review_pack_hash_ledger.v1",
        "status": "review_ready",
        "inputs": summary["input_sha256"],
        "outputs": {path.name: _sha256(path) for path in output_files if path.exists()},
        "taxonomy_admission": "not_granted",
        "training_admission": "not_granted",
    }
    _write_json(ledger_path, ledger)

    manifest = {
        "summary": summary,
        "artifact_sha256": {
            "review_csv": _sha256(review_csv),
            "review_jsonl": _sha256(review_jsonl),
            "boundary_json": _sha256(boundary_json),
            "summary": _sha256(summary_path),
            "report": _sha256(report_path),
            "instructions": _sha256(instructions_path),
            "hash_ledger": _sha256(ledger_path),
        },
    }
    _write_json(output_dir / "stable101_authority_review_manifest.json", manifest)
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--proposal", required=True, type=Path)
    parser.add_argument("--delta", required=True, type=Path)
    parser.add_argument("--source-review-gate", required=True, type=Path)
    parser.add_argument("--impact", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--date", default="2026-07-24")
    args = parser.parse_args()

    manifest = build_review_pack(
        proposal_path=args.proposal,
        delta_path=args.delta,
        source_review_gate_path=args.source_review_gate,
        impact_path=args.impact,
        output_dir=args.output_dir,
        date=args.date,
    )
    print(json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
