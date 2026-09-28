#!/usr/bin/env python3
"""Build a report-only stable106 draft from the reviewed top-15 QGIS gaps."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


CORE_MAPPINGS = {
    "native:creategrid": "L3_02_03_06",
    "native:joinattributestable": "L3_01_03_05",
    "native:deleteduplicategeometries": "L3_01_05_04",
    "native:polygonstolines": "L3_02_07_03",
    "native:simplifygeometries": "L3_02_05_01",
}

EXISTING_ALIASES = {"native:joinbynearest": "L3_02_04_01"}

DECISIONS = {
    "gdal:importvectorintopostgisdatabaseavailableconnections": (
        "database_sql_excluded",
        "Database import boundary, not a target analysis operation.",
    ),
    "native:creategrid": (
        "core_taxonomy_candidate",
        "Creates a vector grid over an extent; no equivalent stable101 class.",
    ),
    "native:saveselectedfeatures": (
        "support_export_boundary",
        "Materializes a selection as an output layer.",
    ),
    "native:joinattributestable": (
        "core_taxonomy_candidate",
        "Joins table fields by a shared key without a spatial predicate.",
    ),
    "native:postgisexecutesql": (
        "database_sql_excluded",
        "Executes arbitrary PostGIS SQL outside the stable operator target boundary.",
    ),
    "native:createspatialindex": (
        "support_export_boundary",
        "Performance support step; source review already confirmed it as a boundary.",
    ),
    "native:deleteduplicategeometries": (
        "core_taxonomy_candidate",
        "Removes features with duplicate geometries; distinct from validity checking.",
    ),
    "native:polygonstolines": (
        "core_taxonomy_candidate",
        "Converts polygon boundaries to line features.",
    ),
    "native:importintopostgis": (
        "database_sql_excluded",
        "Database import boundary, not a target analysis operation.",
    ),
    "native:filedownloader": (
        "support_export_boundary",
        "External I/O acquisition step, not a GIS analysis target.",
    ),
    "native:pointstopath": (
        "unresolved",
        "Core-looking operation, but taxonomy placement is not yet source-reviewed.",
    ),
    "grass7:r.neighbors": (
        "unresolved",
        "Raster neighborhood operation requires a separate raster taxonomy review.",
    ),
    "native:simplifygeometries": (
        "core_taxonomy_candidate",
        "Reduces geometry complexity using a tolerance; no equivalent stable101 class.",
    ),
    "native:joinbynearest": (
        "existing_stable101_alias",
        "Nearest-feature attribute join is an implementation of stable101 Spatial Join.",
    ),
    "native:rasterize": (
        "unresolved",
        "Provider-migrated QGIS rasterize needs exact algorithm authority before aliasing.",
    ),
}


def _stable_code_to_id(stable101: dict[str, Any]) -> dict[str, int]:
    combined = {
        str(code): int(token_id)
        for code, token_id in (stable101.get("existing_code_to_id") or {}).items()
    }
    for code, token_id in (stable101.get("proposed_code_to_id_additions") or {}).items():
        if code in combined:
            raise ValueError(f"stable101 duplicates code {code}")
        combined[str(code)] = int(token_id)
    if stable101.get("proposed_taxonomy") != "stable101":
        raise ValueError("base proposal must be stable101")
    if sorted(combined.values()) != list(range(101)):
        raise ValueError("stable101 token IDs must be contiguous 0-100")
    return combined


def _verified_samples(row: dict[str, Any]) -> list[dict[str, Any]]:
    samples = list(row.get("samples") or [])
    verified = [
        sample
        for sample in samples
        if sample.get("source_verification") == "verified_sha256"
        and str(sample.get("source_path", "")).startswith("/home/yll/")
        and sample.get("source_sha256")
        and sample.get("source_snippet")
    ]
    return verified


def build_draft(
    queue: list[dict[str, Any]],
    stable101: dict[str, Any],
    experimental114: dict[str, Any],
) -> tuple[list[dict[str, Any]], dict[str, Any], dict[str, Any], dict[str, Any]]:
    by_operator = {str(row.get("operator_id", "")).lower(): row for row in queue}
    if set(by_operator) != set(DECISIONS):
        missing = sorted(set(DECISIONS) - set(by_operator))
        extra = sorted(set(by_operator) - set(DECISIONS))
        raise ValueError(f"top-15 queue mismatch: missing={missing}, extra={extra}")

    base_code_to_id = _stable_code_to_id(stable101)
    classes = {
        str(row.get("code")): row for row in experimental114.get("added_classes") or []
    }
    new_codes = sorted(set(CORE_MAPPINGS.values()))
    if any(code in base_code_to_id for code in new_codes):
        raise ValueError("stable106 code already exists in stable101")
    missing_classes = sorted(set(new_codes) - set(classes))
    if missing_classes:
        raise ValueError(f"experimental taxonomy lacks candidate classes: {missing_classes}")
    if EXISTING_ALIASES["native:joinbynearest"] not in base_code_to_id:
        raise ValueError("Spatial Join must already exist in stable101")

    adjudications: list[dict[str, Any]] = []
    for operator, (decision, reason) in DECISIONS.items():
        source = by_operator[operator]
        verified = _verified_samples(source)
        if decision in {"core_taxonomy_candidate", "existing_stable101_alias"} and len(verified) < 3:
            raise ValueError(f"{operator}: fewer than 3 verified source samples")
        adjudications.append(
            {
                "schema": "gis_recommend.qgis_mapping_gap_adjudication.v1",
                "rank": int(source["rank"]),
                "operator_id": operator,
                "decision": decision,
                "decision_reason": reason,
                "candidate_l3_code": CORE_MAPPINGS.get(operator)
                or EXISTING_ALIASES.get(operator, ""),
                "single_gap_records": int(source.get("single_gap_records", 0)),
                "single_gap_unique_chains": int(
                    source.get("single_gap_unique_chains", 0)
                ),
                "source_samples": verified,
                "mapping_admission": "not_granted_report_only",
                "training_admission": "not_granted_report_only",
                "training_row_emitted": False,
            }
        )
    adjudications.sort(key=lambda row: row["rank"])

    additions = {code: 101 + index for index, code in enumerate(new_codes)}
    restored_l3 = []
    for code in new_codes:
        row = dict(classes[code])
        row.pop("token_id", None)
        row["proposed_token_id"] = additions[code]
        row["evidence_level"] = "three_source_snippets_verified_top15_review"
        row["taxonomy_admission"] = "not_granted"
        restored_l3.append(row)
    extension = {
        "schema": "gis_recommend.qgis_stable106_extension_proposal.v1",
        "status": "formal_draft_not_granted",
        "base_taxonomy": "stable101",
        "proposed_taxonomy": "stable106",
        "base_class_count": 101,
        "proposed_class_count": 106,
        "existing_code_to_id": dict(
            sorted(base_code_to_id.items(), key=lambda item: item[1])
        ),
        "proposed_code_to_id_additions": additions,
        "restored_l3": restored_l3,
        "existing_token_ids_unchanged": True,
        "taxonomy_admission": "not_granted",
        "training_admission": "not_granted",
    }
    delta = {
        "schema": "gis_recommend.qgis_mapping_authority_stable106_delta_draft.v1",
        "status": "formal_draft_not_granted",
        "restored_l3_mappings": CORE_MAPPINGS,
        "alias_mappings": EXISTING_ALIASES,
        "operator_count": len(CORE_MAPPINGS) + len(EXISTING_ALIASES),
        "taxonomy_admission": "not_granted",
        "training_admission": "not_granted",
        "production_merge": "not_granted",
    }
    decision_counts = dict(
        sorted(Counter(row["decision"] for row in adjudications).items())
    )
    admitted = [
        row
        for row in adjudications
        if row["decision"]
        in {"core_taxonomy_candidate", "existing_stable101_alias"}
    ]
    summary = {
        "schema": "gis_recommend.qgis_mapping_gap_stable106_summary.v1",
        "queue_operators": len(adjudications),
        "decision_counts": decision_counts,
        "draft_mapping_operators": len(admitted),
        "single_gap_records_potentially_unlocked": sum(
            row["single_gap_records"] for row in admitted
        ),
        "single_gap_unique_chains_potentially_unlocked": sum(
            row["single_gap_unique_chains"] for row in admitted
        ),
        "taxonomy_admission": "not_granted",
        "training_admission": "not_granted",
        "training_rows_emitted": 0,
        "next_gate": "whole-pool L3 replay, description fidelity, and four-layer dedup",
    }
    return adjudications, extension, delta, summary


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def _write_json(path: Path, value: Any) -> None:
    _atomic_write(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


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
    adjudications: list[dict[str, Any]],
    extension: dict[str, Any],
    delta: dict[str, Any],
    summary: dict[str, Any],
    *,
    inputs: dict[str, Path],
    output_dir: Path,
) -> None:
    adjudication_path = output_dir / "top15_adjudication_v1.jsonl"
    extension_path = output_dir / "stable106_extension_proposal_v1.json"
    delta_path = output_dir / "stable106_mapping_delta_v1.json"
    summary_path = output_dir / "summary_v1.json"
    report_path = output_dir / "report_v1.md"
    hash_path = output_dir / "hash_ledger_v1.json"
    _write_jsonl(adjudication_path, adjudications)
    _write_json(extension_path, extension)
    _write_json(delta_path, delta)
    _write_json(summary_path, summary)
    lines = [
        "# QGIS Processing mapping-gap stable106 draft v1",
        "",
        "Report-only draft. No taxonomy, production mapping, or training admission is granted.",
        "",
        "| Rank | Operator | Decision | Candidate L3 | Single-gap rows | Unique chains |",
        "|---:|---|---|---|---:|---:|",
    ]
    lines.extend(
        f"| {row['rank']} | `{row['operator_id']}` | {row['decision']} | "
        f"`{row['candidate_l3_code']}` | {row['single_gap_records']} | "
        f"{row['single_gap_unique_chains']} |"
        for row in adjudications
    )
    _atomic_write(report_path, "\n".join(lines) + "\n")
    artifacts = [adjudication_path, extension_path, delta_path, summary_path, report_path]
    _write_json(
        hash_path,
        {
            "schema": "gis_recommend.hash_ledger.v1",
            "inputs": {
                name: {"path": str(path), "sha256": _sha256(path)}
                for name, path in inputs.items()
            },
            "artifacts": {path.name: _sha256(path) for path in artifacts},
        },
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--queue", type=Path, required=True)
    parser.add_argument("--stable101", type=Path, required=True)
    parser.add_argument("--experimental114", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    adjudications, extension, delta, summary = build_draft(
        _read_jsonl(args.queue), _read_json(args.stable101), _read_json(args.experimental114)
    )
    write_outputs(
        adjudications,
        extension,
        delta,
        summary,
        inputs={
            "queue": args.queue,
            "stable101": args.stable101,
            "experimental114": args.experimental114,
        },
        output_dir=args.output_dir,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
