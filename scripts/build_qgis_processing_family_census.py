#!/usr/bin/env python3
"""Census exact workflows, local subworkflows, and transitions.

This is a scheduling inventory over normalized Asset Miner discoveries.  It
does not slice sources, invent tasks, or emit training rows.  L3 and I/O
figures are read-only preflight signals; they are not admission decisions.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any


SCHEMA = "gis_recommend.qgis_processing_family_census.v1"
KNOWN_IO = {
    "native:buffer": ("vector", "vector"),
    "native:clip": ("vector+vector", "vector"),
    "qgis:multiparttosingleparts": ("vector", "vector"),
    "native:multiparttosingleparts": ("vector", "vector"),
    "native:intersection": ("vector+vector", "vector"),
    "native:difference": ("vector+vector", "vector"),
    "native:dissolve": ("vector", "vector"),
    "native:reprojectlayer": ("vector", "vector"),
    "native:fixgeometries": ("vector", "vector"),
    "native:fieldcalculator": ("vector", "vector"),
    "native:extractbyexpression": ("vector", "vector"),
    "native:extractbylocation": ("vector+vector", "vector"),
    "native:mergevectorlayers": ("vector+vector", "vector"),
    "native:savefeatures": ("vector", "vector"),
}


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def _load_l3(path: Path | None, catalog_path: Path | None) -> dict[str, str]:
    if path is None or not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    by_name = {
        str(name).strip().lower(): str(value.get("primary_l3"))
        for name, value in (data.get("mapping_metadata", {}).get("qgis_to_l3", {}) or {}).items()
        if isinstance(value, dict) and value.get("primary_l3")
    }
    catalog: dict[str, str] = {}
    if catalog_path and catalog_path.is_file():
        for item in json.loads(catalog_path.read_text(encoding="utf-8")):
            ident = str(item.get("identifier") or "").strip().lower()
            name = str(item.get("name") or "").strip().lower()
            if ident and name:
                catalog[ident] = by_name.get(name, "")
    aliases = {
        "native:multiparttosingleparts": "multipart to singleparts",
        "qgis:multiparttosingleparts": "multipart to singleparts",
        "native:clip": "clip",
    }
    for operator, name in aliases.items():
        catalog.setdefault(operator, by_name.get(name, ""))
    return catalog


def _sequence(row: dict[str, Any]) -> list[str]:
    return [str(value).strip().lower() for value in row.get("processing_operator_ids") or [] if str(value).strip()]


def _family_id(level: str, values: tuple[str, ...]) -> str:
    return hashlib.sha256(f"{level}\0{'|'.join(values)}".encode("utf-8")).hexdigest()[:16]


def census(rows: list[dict[str, Any]], *, l3_lookup: dict[str, str] | None = None, min_support: int = 1) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    workflows = [row for row in rows if row.get("asset_type") == "processing_workflow"]
    groups: dict[tuple[str, tuple[str, ...]], list[dict[str, Any]]] = defaultdict(list)
    for row in workflows:
        sequence = _sequence(row)
        if sequence:
            groups[("exact_workflow", tuple(sequence))].append(row)
            for width, level in ((2, "subworkflow_2"), (3, "subworkflow_3")):
                for start in range(max(0, len(sequence) - width + 1)):
                    if len(sequence[start:start + width]) == width:
                        groups[(level, tuple(sequence[start:start + width]))].append(row)
            for start in range(len(sequence) - 1):
                groups[("transition", tuple(sequence[start:start + 2]))].append(row)
    families: list[dict[str, Any]] = []
    for (level, values), members in groups.items():
        if len(members) < min_support:
            continue
        sources = {str(row.get("source_sha256") or "") for row in members if row.get("source_sha256")}
        parents = {str(row.get("parent_source_sha256") or row.get("source_sha256") or "") for row in members if row.get("parent_source_sha256") or row.get("source_sha256")}
        full_sequences = {tuple(_sequence(row)) for row in members}
        providers = {value.split(":", 1)[0] for value in values if ":" in value}
        l3_status = "not_available"
        l3_count = 0
        if l3_lookup is not None:
            l3_count = sum(bool(l3_lookup.get(operator)) for operator in values)
            l3_status = "fully_resolvable" if l3_count == len(values) else "partially_resolvable"
        io_status = "valid_known_contract" if all(operator in KNOWN_IO for operator in values) else "unknown_operator_contract"
        repeated_operator = len(set(values)) == 1
        quality_factor = (1.0 if l3_status == "fully_resolvable" else 0.5 if l3_status == "partially_resolvable" else 0.75) * (1.0 if io_status == "valid_known_contract" else 0.5) * (0.35 if repeated_operator else 1.0)
        priority_score = round(len(members) * (1.0 + min(len(sources), 50) / 100.0) * (1.0 + min(len(full_sequences), 25) / 100.0) * quality_factor, 6)
        families.append({
            "schema": SCHEMA,
            "family_id": _family_id(level, values),
            "family_level": level,
            "family_sequence": list(values),
            "family_sequence_key": "|".join(values),
            "support_count": len(members),
            "unique_source_count": len(sources),
            "unique_parent_count": len(parents),
            "unique_full_workflow_count": len(full_sequences),
            "provider_count": len(providers),
            "providers": sorted(providers),
            "l3_resolvable_operator_count": l3_count,
            "l3_status": l3_status,
            "io_status": io_status,
            "repeated_operator": repeated_operator,
            "quality_factor": quality_factor,
            "priority_score": priority_score,
            "dynamic_count": sum(int(row.get("dynamic_processing_call_count") or 0) > 0 for row in members),
            "task_metric_status": "not_available_from_normalized_ledger",
            "unique_task_count": None,
            "unique_template_count": None,
            "production_potential": {"support": len(members), "source_diversity": len(sources), "structure_diversity": len(full_sequences), "quality_signals_complete": False},
            "candidate_only": True,
            "l3_mapping": "preflight_only_not_admitted",
            "training_rows_emitted": 0,
        })
    families.sort(key=lambda row: (-row["priority_score"], -row["support_count"], -row["unique_source_count"], row["family_level"], row["family_id"]))
    summary = {
        "schema": f"{SCHEMA}.summary",
        "input_rows": len(rows),
        "processing_workflow_rows": len(workflows),
        "family_rows": len(families),
        "family_level_counts": {},
        "top_families": families[:50],
        "min_support": min_support,
        "l3_preflight": "read_only",
        "training_rows_emitted": 0,
        "training_admission": "not_granted_processing_family_census_v1",
    }
    for row in families:
        level = row["family_level"]
        summary["family_level_counts"][level] = summary["family_level_counts"].get(level, 0) + 1
    summary["family_level_counts"] = dict(sorted(summary["family_level_counts"].items()))
    return families, summary


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--normalized-ledger", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--id-mappings", type=Path)
    parser.add_argument("--operator-catalog", type=Path)
    parser.add_argument("--min-support", type=int, default=1)
    args = parser.parse_args()
    families, summary = census(read_jsonl(args.normalized_ledger), l3_lookup=_load_l3(args.id_mappings, args.operator_catalog) if args.id_mappings else None, min_support=args.min_support)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    ledger = args.output_dir / "family_census_v1.jsonl"
    ledger.write_text("".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in families), encoding="utf-8")
    summary_path = args.output_dir / "summary_v1.json"
    summary_path.write_text(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    hashes = {ledger.name: hashlib.sha256(ledger.read_bytes()).hexdigest(), summary_path.name: hashlib.sha256(summary_path.read_bytes()).hexdigest()}
    (args.output_dir / "hash_ledger_v1.json").write_text(json.dumps(hashes, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in summary.items() if key != "top_families"}, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
