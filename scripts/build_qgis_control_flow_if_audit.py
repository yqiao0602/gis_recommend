#!/usr/bin/env python3
"""Build the source-authority census audit for conditional QGIS recovery."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import tempfile
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CENSUS = (
    ROOT
    / "docs/reports/qgis_recovery_expansion_census_v1"
    / "expansion_census_units_v1.jsonl"
)
DEFAULT_OUTPUT_DIR = (
    ROOT / "docs/reports/qgis_recovery_control_flow_if_audit_census_v1"
)
HUMAN_FIELDS = (
    "human_execution_boundary_correct",
    "human_dependency_correct",
    "human_branch_semantics_recoverable",
    "human_description_scope_correct",
    "human_final_decision",
    "human_notes",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _risk_stratum(reasons: list[str]) -> str:
    reason_set = set(reasons)
    if any(reason.startswith("downstream_low_level_data_transform:") for reason in reasons):
        return "if_with_low_level_transform"
    if "control_flow:for" in reason_set:
        return "if_with_loop"
    if "conditional_early_exit" in reason_set:
        return "if_with_early_exit"
    if "control_flow:try" in reason_set and "downstream_data_transform" in reason_set:
        return "if_with_try_and_downstream_transform"
    if "downstream_data_transform" in reason_set:
        return "if_with_downstream_transform"
    if "control_flow:try" in reason_set:
        return "if_with_try"
    return "if_only"


def _source_snippet(path: Path, call_sites: list[dict[str, Any]]) -> str:
    lines = path.read_text(encoding="utf-8").splitlines()
    start = max(1, min(int(site["line_start"]) for site in call_sites) - 4)
    end = min(
        len(lines),
        max(int(site.get("line_end") or site["line_start"]) for site in call_sites)
        + 4,
    )
    return "\n".join(
        f"{line_number}: {lines[line_number - 1]}"
        for line_number in range(start, end + 1)
    )


def _representative_key(row: dict[str, Any]) -> tuple[int, int, str]:
    return (
        len(row.get("local_structure_reasons") or []),
        len(row.get("operator_ids") or []),
        str(row.get("structure_signature") or ""),
    )


def build_control_flow_if_audit(
    census_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    population = [
        row
        for row in census_rows
        if "control_flow:if" in (row.get("local_structure_reasons") or [])
        and row.get("current_recovery_structure_status") != "eligible"
    ]
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in population:
        grouped[str(row["source_authority_key"])].append(row)
    selected = [
        max(grouped[authority], key=_representative_key)
        for authority in sorted(grouped)
    ]
    packet: list[dict[str, Any]] = []
    for position, source in enumerate(selected, start=1):
        path = Path(str(source["source_path"]))
        if not path.is_file():
            raise ValueError(f"source file missing: {path}")
        if _sha256(path) != str(source["source_sha256"]):
            raise ValueError(f"source sha256 mismatch: {path}")
        row = dict(source)
        reasons = list(source.get("local_structure_reasons") or [])
        row.update(
            {
                "schema": "gis_recommend.qgis_control_flow_if_audit.v1",
                "review_position": position,
                "risk_stratum": _risk_stratum(reasons),
                "reason_set_key": str(source.get("reason_set_key") or "|".join(reasons)),
                "source_snippet": _source_snippet(
                    path, list(source.get("call_sites") or [])
                ),
                "source_verification_status": "verified_current_sha256",
                "review_status": "pending_rule_calibration",
                "training_admission": "not_granted_rule_calibration_only",
                "training_row_emitted": False,
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
            }
        )
        row.update({field: "" for field in HUMAN_FIELDS})
        packet.append(row)
    summary = {
        "schema": "gis_recommend.qgis_control_flow_if_audit_summary.v1",
        "population_raw_units": len(population),
        "population_source_authorities": len(grouped),
        "selected_rows": len(packet),
        "selected_source_authorities": len(
            {row["source_authority_key"] for row in packet}
        ),
        "selected_structure_signatures": len(
            {row["structure_signature"] for row in packet}
        ),
        "selected_risk_strata": dict(
            sorted(Counter(row["risk_stratum"] for row in packet).items())
        ),
        "selected_reason_sets": dict(
            sorted(Counter(row["reason_set_key"] for row in packet).items())
        ),
        "selected_provider_type_status": dict(
            sorted(
                Counter(row["provider_input_type_status"] for row in packet).items()
            )
        ),
        "source_verification_status": dict(
            sorted(
                Counter(row["source_verification_status"] for row in packet).items()
            )
        ),
        "human_fields_blank": all(
            not row[field] for row in packet for field in HUMAN_FIELDS
        ),
        "decision": {
            "training_admission": "not_granted_rule_calibration_only",
            "training_rows_emitted": 0,
            "next_gate": "source-backed proposal calibration and authority-level precision/Wilson evaluation",
        },
    }
    return packet, summary


def _atomic_write(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding=encoding, newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def _csv_value(value: Any) -> Any:
    if isinstance(value, (dict, list)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def _render_report(summary: dict[str, Any]) -> str:
    lines = [
        "# QGIS Conditional Recovery Authority Census v1",
        "",
        "This is a full independent-authority calibration packet, not training data.",
        "",
        f"- Raw conditional units: {summary['population_raw_units']}",
        f"- Independent source authorities: {summary['population_source_authorities']}",
        f"- Selected authority representatives: {summary['selected_rows']}",
        "- Training rows emitted: 0",
        "",
        "## Risk Strata",
        "",
    ]
    lines.extend(
        f"- `{name}`: {count}"
        for name, count in summary["selected_risk_strata"].items()
    )
    return "\n".join(lines) + "\n"


def write_outputs(
    packet: list[dict[str, Any]],
    summary: dict[str, Any],
    *,
    census_path: Path,
    output_dir: Path,
) -> dict[str, Path]:
    jsonl_path = output_dir / "review_packet.jsonl"
    csv_path = output_dir / "review_packet.csv"
    summary_path = output_dir / "summary.json"
    report_path = output_dir / "README.md"
    hash_path = output_dir / "hash_manifest.json"
    _atomic_write(
        jsonl_path,
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
            for row in packet
        ),
    )
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=list(packet[0]))
    writer.writeheader()
    writer.writerows(
        {key: _csv_value(value) for key, value in row.items()} for row in packet
    )
    _atomic_write(csv_path, output.getvalue(), encoding="utf-8-sig")
    _atomic_write(
        summary_path,
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    _atomic_write(report_path, _render_report(summary))
    hashes = {
        "schema": "gis_recommend.qgis_control_flow_if_audit_hashes.v1",
        "inputs": {str(census_path): _sha256(census_path)},
        "outputs": {
            path.name: _sha256(path)
            for path in (jsonl_path, csv_path, summary_path, report_path)
        },
    }
    _atomic_write(
        hash_path,
        json.dumps(hashes, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    return {
        "jsonl": jsonl_path,
        "csv": csv_path,
        "summary": summary_path,
        "report": report_path,
        "hash_manifest": hash_path,
    }


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--census", type=Path, default=DEFAULT_CENSUS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)
    packet, summary = build_control_flow_if_audit(_load_jsonl(args.census))
    return write_outputs(
        packet, summary, census_path=args.census, output_dir=args.output_dir
    )


if __name__ == "__main__":
    main()
