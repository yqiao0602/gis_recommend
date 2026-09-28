#!/usr/bin/env python3
"""Census Processing DAGs blocked by downstream non-Processing calls."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Mapping, Sequence


PRESENTATION_ROLES = {
    "QColor",
    "QgsColorRampShader",
    "QgsLayerTreeLayer",
    "QgsSingleBandPseudoColorRenderer",
    "format",
    "insertChildNode",
    "loadNamedStyle",
    "renderer",
    "setColor",
    "setRenderer",
    "setStrokeColor",
    "setStrokeWidth",
    "setText",
    "symbol",
    "triggerRepaint",
}
EXPORT_ROLES = {
    "writeAsRasterFormat",
    "writeAsVectorFormat",
    "writeAsVectorFormatV2",
    "writeAsVectorFormatV3",
}
SEMANTIC_CONTINUATION_ROLES = {
    "GetRasterBand",
    "Open",
    "ReadAsArray",
    "addAttributes",
    "addFeature",
    "append",
    "commitChanges",
    "dataProvider",
    "deleteAttributes",
    "edit",
    "featureCount",
    "fields",
    "geometry",
    "getFeatures",
    "parameterAsSink",
    "rasterize",
    "setAttributes",
    "setCrs",
    "setGeometry",
    "startEditing",
    "updateFeature",
}
SAFE_STATUSES = {"presentation_only", "export_only", "presentation_and_export"}


def _sha(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


def _role_status(calls: Sequence[str]) -> str:
    roles = set(calls)
    if not roles:
        return "missing_role_evidence"
    if roles <= PRESENTATION_ROLES:
        return "presentation_only"
    if roles <= EXPORT_ROLES:
        return "export_only"
    if roles <= PRESENTATION_ROLES | EXPORT_ROLES:
        return "presentation_and_export"
    if roles & SEMANTIC_CONTINUATION_ROLES:
        return "semantic_continuation"
    return "unknown_or_custom"


def build_census(
    rows: Sequence[Mapping[str, Any]], *, minimum_support: int
) -> dict[str, Any]:
    selected: dict[tuple[str, str], dict[str, Any]] = {}
    for source in rows:
        reasons = list(source.get("local_structure_reasons") or [])
        if (
            source.get("split_class") != "multi_step_local_dag"
            or "downstream_data_transform" not in reasons
        ):
            continue
        body = str(source.get("normalized_source_body_sha256") or "")
        unit_id = str(source.get("unit_id") or "")
        if not body or not unit_id:
            raise ValueError("downstream candidate lacks body or unit identity")
        calls = sorted(
            set(
                (source.get("local_risk_evidence") or {}).get(
                    "downstream_data_transform_calls"
                )
                or []
            )
        )
        low_level_roles = sorted(
            set(
                (source.get("local_risk_evidence") or {}).get(
                    "downstream_low_level_data_transform_roles"
                )
                or []
            )
        )
        status = _role_status(calls)
        selected.setdefault(
            (body, unit_id),
            {
                "normalized_source_body_sha256": body,
                "unit_id": unit_id,
                "source_sha256": source.get("source_sha256", ""),
                "source_path": source.get("source_path", ""),
                "operator_ids": list(source.get("operator_ids") or []),
                "dependency_edges": list(source.get("dependency_edges") or []),
                "downstream_calls": calls,
                "downstream_low_level_roles": low_level_roles,
                "downstream_role_status": status,
                "local_structure_reasons": reasons,
                "only_downstream_blocker": reasons == ["downstream_data_transform"],
                "training_admission": "not_granted",
                "training_row_emitted": False,
            },
        )

    units = list(selected.values())
    family_bodies: dict[str, set[str]] = defaultdict(set)
    family_meta: dict[str, dict[str, Any]] = {}
    for unit in units:
        family_id = _sha(
            {
                "role_status": unit["downstream_role_status"],
                "calls": unit["downstream_calls"],
                "only_downstream_blocker": unit["only_downstream_blocker"],
            }
        )
        unit["downstream_family_id"] = family_id
        family_bodies[family_id].add(unit["normalized_source_body_sha256"])
        family_meta.setdefault(
            family_id,
            {
                "downstream_family_id": family_id,
                "downstream_role_status": unit["downstream_role_status"],
                "downstream_calls": unit["downstream_calls"],
                "only_downstream_blocker": unit["only_downstream_blocker"],
            },
        )
    families = []
    for family_id, meta in family_meta.items():
        support = len(family_bodies[family_id])
        safe = (
            meta["downstream_role_status"] in SAFE_STATUSES
            and meta["only_downstream_blocker"]
        )
        families.append(
            {
                **meta,
                "normalized_body_support": support,
                "boundary_rule_candidate": safe,
                "support_status": (
                    "passed_pending_source_review"
                    if safe and support >= minimum_support
                    else "deferred_insufficient_support"
                    if safe
                    else "deferred_semantic_continuation_or_unknown"
                ),
                "training_admission": "not_granted",
            }
        )
    families.sort(
        key=lambda row: (-row["normalized_body_support"], row["downstream_family_id"])
    )
    safe_bodies = {
        unit["normalized_source_body_sha256"]
        for unit in units
        if unit["downstream_role_status"] in SAFE_STATUSES
        and unit["only_downstream_blocker"]
    }
    role_body_sets: dict[str, set[str]] = defaultdict(set)
    low_level_units = [unit for unit in units if unit["downstream_low_level_roles"]]
    low_level_bodies = {
        unit["normalized_source_body_sha256"] for unit in low_level_units
    }
    low_level_role_bodies: dict[str, set[str]] = defaultdict(set)
    for unit in units:
        for role in unit["downstream_calls"]:
            role_body_sets[role].add(unit["normalized_source_body_sha256"])
        for role in unit["downstream_low_level_roles"]:
            low_level_role_bodies[role].add(unit["normalized_source_body_sha256"])
    summary = {
        "schema": "gis_recommend.qgis_downstream_transform_census.v1",
        "unique_multi_step_units": len(units),
        "normalized_body_authorities": len(
            {unit["normalized_source_body_sha256"] for unit in units}
        ),
        "only_downstream_blocker_units": sum(
            unit["only_downstream_blocker"] for unit in units
        ),
        "safe_support_authorities": len(safe_bodies),
        "support_pass_safe_families": sum(
            family["support_status"] == "passed_pending_source_review"
            for family in families
        ),
        "low_level_sink_units": len(low_level_units),
        "low_level_sink_authorities": len(low_level_bodies),
        "low_level_sink_role_support": {
            role: len(bodies)
            for role, bodies in sorted(
                low_level_role_bodies.items(),
                key=lambda item: (-len(item[1]), item[0]),
            )
        },
        "low_level_sink_route": "qgis_api_pattern_deferred",
        "role_status_counts": dict(
            Counter(unit["downstream_role_status"] for unit in units)
        ),
        "top_roles_by_normalized_body": [
            {"role": role, "normalized_body_support": len(bodies)}
            for role, bodies in sorted(
                role_body_sets.items(), key=lambda item: (-len(item[1]), item[0])
            )[:50]
        ],
        "minimum_authority_support": minimum_support,
        "training_admission": "not_granted",
        "training_rows_emitted": 0,
        "next_gate": "remaining_processing_unresolved_family_ranking",
    }
    return {"units": units, "families": families, "summary": summary}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _write_jsonl(path: Path, rows: Sequence[Mapping[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def _file_hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-jsonl", action="append", type=Path, required=True)
    parser.add_argument("--minimum-authority-support", type=int, default=30)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    rows = [row for path in args.input_jsonl for row in _read_jsonl(path)]
    census = build_census(rows, minimum_support=args.minimum_authority_support)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    units_path = args.output_dir / "downstream_units_v1.jsonl"
    families_path = args.output_dir / "downstream_families_v1.jsonl"
    summary_path = args.output_dir / "summary_v1.json"
    report_path = args.output_dir / "report_v1.md"
    _write_jsonl(units_path, census["units"])
    _write_jsonl(families_path, census["families"])
    summary_path.write_text(
        json.dumps(census["summary"], ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    summary = census["summary"]
    report_path.write_text(
        "# QGIS Processing downstream-transform census\n\n"
        f"- Multi-step units: {summary['unique_multi_step_units']}\n"
        f"- Normalized-body authorities: {summary['normalized_body_authorities']}\n"
        f"- Only-downstream blocker units: {summary['only_downstream_blocker_units']}\n"
        f"- Safe support authorities: {summary['safe_support_authorities']}\n"
        f"- Support-pass safe families: {summary['support_pass_safe_families']}\n"
        f"- Low-level sink units/authorities: {summary['low_level_sink_units']}/"
        f"{summary['low_level_sink_authorities']}\n"
        f"- Low-level sink route: {summary['low_level_sink_route']}\n"
        "- Training admission: not granted\n"
        "- Training rows emitted: 0\n"
        f"- Next gate: {summary['next_gate']}\n",
        encoding="utf-8",
        newline="\n",
    )
    artifacts = [units_path, families_path, summary_path, report_path]
    ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "source_inputs": {
            str(path): {"sha256": _file_hash(path), "bytes": path.stat().st_size}
            for path in args.input_jsonl
        },
        "artifacts": {
            path.name: {"sha256": _file_hash(path), "bytes": path.stat().st_size}
            for path in artifacts
        },
    }
    (args.output_dir / "hash_ledger_v1.json").write_text(
        json.dumps(ledger, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(census["summary"], ensure_ascii=False, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
