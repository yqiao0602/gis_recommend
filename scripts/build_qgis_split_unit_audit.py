#!/usr/bin/env python3
"""Build a source-backed census packet for eligible QGIS split units."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import tempfile
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_UNITS = ROOT / "docs/reports/qgis_split_subworkflow_units_v8/split_units_v1.jsonl"
DEFAULT_OUTPUT_DIR = ROOT / "docs/reports/qgis_split_subworkflow_units_v8/audit_census_v1"
HUMAN_FIELDS = (
    "human_dependency_correct",
    "human_operator_order_correct",
    "human_boundary_correct",
    "human_description_faithful",
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


def _source_snippet(source_text: str, call_sites: list[dict[str, Any]]) -> str:
    lines = source_text.splitlines()
    start = max(1, min(int(site["line_start"]) for site in call_sites) - 4)
    end = min(
        len(lines),
        max(int(site.get("line_end") or site["line_start"]) for site in call_sites) + 4,
    )
    return "\n".join(f"{number}: {lines[number - 1]}" for number in range(start, end + 1))


def build_audit_packet(
    unit_rows: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    eligible = [
        row
        for row in unit_rows
        if row.get("split_class") == "multi_step_local_dag"
        and row.get("local_structure_status") == "eligible"
        and row.get("description_fidelity_passed") is True
    ]
    eligible.sort(
        key=lambda row: (
            str(row.get("source_sha256") or ""),
            min(int(site["line_start"]) for site in row.get("call_sites") or []),
            str(row.get("unit_id") or ""),
        )
    )
    identities = [
        (str(row.get("source_sha256") or ""), str(row.get("unit_id") or ""))
        for row in eligible
    ]
    if len(identities) != len(set(identities)):
        raise ValueError("eligible split unit identities must be unique")

    packet: list[dict[str, Any]] = []
    for position, source in enumerate(eligible, start=1):
        path = Path(str(source.get("source_path") or ""))
        if not path.is_file():
            raise ValueError(f"source file missing for {source.get('unit_id')}")
        if _sha256(path) != source.get("source_sha256"):
            raise ValueError(f"source SHA mismatch for {source.get('unit_id')}")
        call_sites = list(source.get("call_sites") or [])
        if not call_sites:
            raise ValueError(f"call sites missing for {source.get('unit_id')}")
        row = dict(source)
        row.update(
            {
                "schema": "gis_recommend.qgis_split_unit_audit.v1",
                "review_position": position,
                "source_hash_verified": True,
                "source_snippet": _source_snippet(
                    path.read_text(encoding="utf-8"), call_sites
                ),
                "review_status": "pending_human_review",
                "training_admission": "not_granted_split_census_audit_only",
                "training_row_emitted": False,
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
                **{field: "" for field in HUMAN_FIELDS},
            }
        )
        packet.append(row)

    unique_sources = len({row["source_sha256"] for row in packet})
    summary = {
        "schema": "gis_recommend.qgis_split_unit_audit_summary.v1",
        "input_units": len(unit_rows),
        "eligible_units": len(packet),
        "unique_sources": unique_sources,
        "unique_parent_records": len({row["parent_record_id"] for row in packet}),
        "unique_normalized_dags": len({row["normalized_dag_key"] for row in packet}),
        "population_census": True,
        "source_disjoint_support": unique_sources,
        "rule_support_requirement": 30,
        "rule_training_eligible": False,
        "review_status": "pending_human_review",
        "training_rows_emitted": 0,
        "training_admission": "not_granted_split_census_audit_only",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "llm_called": False,
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


def write_outputs(
    rows: list[dict[str, Any]],
    summary: dict[str, Any],
    *,
    units_path: Path,
    output_dir: Path,
) -> dict[str, Path]:
    if not rows:
        raise ValueError("no eligible split units found")
    jsonl_path = output_dir / "review_packet.jsonl"
    csv_path = output_dir / "review_packet.csv"
    summary_path = output_dir / "review_summary.json"
    hash_path = output_dir / "hash_manifest.json"
    _atomic_write(
        jsonl_path,
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
            for row in rows
        ),
    )
    buffer = io.StringIO(newline="")
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(
        {key: _csv_value(value) for key, value in row.items()} for row in rows
    )
    _atomic_write(csv_path, buffer.getvalue(), encoding="utf-8-sig")
    _atomic_write(
        summary_path,
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    manifest = {
        "schema": "gis_recommend.qgis_split_unit_audit_hashes.v1",
        "inputs": {str(units_path): _sha256(units_path)},
        "outputs": {
            path.name: _sha256(path)
            for path in (jsonl_path, csv_path, summary_path)
        },
    }
    _atomic_write(
        hash_path,
        json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    return {
        "jsonl": jsonl_path,
        "csv": csv_path,
        "summary": summary_path,
        "hash_manifest": hash_path,
    }


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--units", type=Path, default=DEFAULT_UNITS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)
    rows, summary = build_audit_packet(_load_jsonl(args.units))
    return write_outputs(rows, summary, units_path=args.units, output_dir=args.output_dir)


if __name__ == "__main__":
    main()
