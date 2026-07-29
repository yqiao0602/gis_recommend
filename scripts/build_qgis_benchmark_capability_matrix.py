#!/usr/bin/env python3
"""Build the stable101 paper-v1 QGIS benchmark capability authority."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROUTES = ("m1", "m2", "m3", "retrieval", "general_llm")
ROLE_OVERRIDES = {
    "native:createspatialindex": "support_only",
    "native:saveselectedfeatures": "output_only",
}


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _evidence_ref(path: Path, *, version: str = "") -> dict[str, str]:
    value = {"path": str(path), "sha256": _sha256(path)}
    if version:
        value["version"] = version
    return value


def _stable101_families(
    hierarchy_path: Path, stable98: dict[str, Any], stable101: dict[str, Any]
) -> list[dict[str, Any]]:
    hierarchy = {
        row["l3_code"]: row
        for row in csv.DictReader(
            hierarchy_path.read_text(encoding="utf-8-sig").splitlines()
        )
    }
    additions = {
        row["l3_code"]: row
        for row in [
            *(stable98.get("restored_l3") or []),
            *(stable101.get("restored_l3") or []),
        ]
    }
    code_to_id = {
        **{
            str(code): int(token_id)
            for code, token_id in (stable101.get("existing_code_to_id") or {}).items()
        },
        **{
            str(code): int(token_id)
            for code, token_id in (
                stable101.get("proposed_code_to_id_additions") or {}
            ).items()
        },
    }
    if len(code_to_id) != 101 or sorted(code_to_id.values()) != list(range(101)):
        raise ValueError("stable101 must contain exactly contiguous token IDs 0-100")
    rows = []
    for code, token_id in sorted(code_to_id.items(), key=lambda item: item[1]):
        source = hierarchy.get(code) or additions.get(code)
        if source is None:
            raise ValueError(f"missing hierarchy metadata for {code}")
        rows.append(
            {
                "token_id": token_id,
                "l1_code": str(source.get("l1_code", "")),
                "l1_name": str(source.get("l1_name", "")),
                "l2_code": str(source.get("l2_code", "")),
                "l2_name": str(source.get("l2_name", "")),
                "l3_code": code,
                "l3_name": str(source.get("l3_name", "")),
                "l3_description": str(source.get("l3_description", "")),
            }
        )
    return rows


def _catalog(catalog_path: Path) -> tuple[dict[str, Any], dict[str, dict[str, Any]]]:
    raw = json.loads(catalog_path.read_text(encoding="utf-8"))
    if not isinstance(raw, list):
        raise ValueError("QGIS catalog must contain a JSON array")
    by_id: dict[str, dict[str, Any]] = {}
    for item in raw:
        operator_id = str(item.get("identifier", "")).strip().lower()
        if not operator_id or ":" not in operator_id:
            raise ValueError("catalog operator missing provider-qualified identifier")
        if operator_id in by_id:
            raise ValueError(f"duplicate catalog operator {operator_id}")
        by_id[operator_id] = {
            "operator_id": operator_id,
            "provider": operator_id.split(":", 1)[0],
            "official_name": str(item.get("name", "")),
            "input_types": sorted(
                {
                    str(value.get("type", ""))
                    for value in item.get("inputs", [])
                    if value.get("type")
                }
            ),
            "output_types": sorted(
                {
                    str(value.get("type", ""))
                    for value in item.get("outputs", [])
                    if value.get("type")
                }
            ),
        }
    catalog_sha = _sha256(catalog_path)
    artifact = {
        "schema": "gis_recommend.qgis_benchmark_catalog.v1",
        "catalog_version": f"sha256:{catalog_sha}",
        "source_path": str(catalog_path),
        "source_sha256": catalog_sha,
        "operator_count": len(by_id),
        "operators": [by_id[key] for key in sorted(by_id)],
    }
    return artifact, by_id


def _replay_pairs(path: Path) -> dict[str, set[str]]:
    pairs: dict[str, set[str]] = defaultdict(set)
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        row = json.loads(line)
        operators = [str(value).strip().lower() for value in row.get("qgis_ops", [])]
        codes = [str(value).strip() for value in row.get("proposed_l3_sequence", [])]
        if len(operators) != len(codes):
            raise ValueError(f"{path}:{line_number} operator/L3 length mismatch")
        for operator_id, code in zip(operators, codes):
            pairs[operator_id].add(code)
    return pairs


def _delta_mapping(delta: dict[str, Any]) -> dict[str, str]:
    return {
        str(operator_id).lower(): str(code)
        for section in ("alias_mappings", "restored_l3_mappings")
        for operator_id, code in (delta.get(section) or {}).items()
    }


def _mapping_entries(
    *,
    crosswalk: dict[str, Any],
    restored: dict[str, str],
    catalog_by_id: dict[str, dict[str, Any]],
    stable101_codes: set[str],
    replay_pairs: dict[str, set[str]],
    evidence: dict[str, dict[str, str]],
) -> list[dict[str, Any]]:
    rows = []
    for operator_id, raw in sorted((crosswalk.get("entries") or {}).items()):
        operator_id = str(operator_id).lower()
        bridge_type = str(raw.get("bridge_type", ""))
        crosswalk_code = str(raw.get("l3_code", ""))
        if operator_id in restored:
            code = restored[operator_id]
            status = "stable101_direct"
        elif (
            raw.get("status") == "accepted"
            and bridge_type == "l3_bridge"
            and crosswalk_code in stable101_codes
        ):
            code = crosswalk_code
            status = "stable101_direct"
        elif raw.get("status") == "accepted" and bridge_type == "native_bridge":
            code = ""
            status = "qgis_native_bridge"
        elif raw.get("status") == "rejected" or bridge_type == "rejected":
            code = ""
            status = "rejected"
        else:
            code = ""
            status = "pending"

        observed = sorted(replay_pairs.get(operator_id, set()))
        replay_status = "not_observed"
        if observed:
            replay_status = (
                "consistent" if code and observed == [code] else "conflict"
            )
        catalog_row = catalog_by_id.get(operator_id)
        task_role = ROLE_OVERRIDES.get(
            operator_id,
            "output_only"
            if status == "stable101_direct" and code.startswith("L3_07_")
            else "preparation"
            if status == "stable101_direct" and code.startswith("L3_01_")
            else "analytical"
            if status == "stable101_direct"
            else "unresolved",
        )
        headline_eligible = bool(
            status == "stable101_direct"
            and catalog_row
            and task_role in {"analytical", "preparation"}
            and replay_status != "conflict"
        )
        rows.append(
            {
                "operator_id": operator_id,
                "provider": operator_id.split(":", 1)[0],
                "official_name": str(raw.get("official_name", "")),
                "strict_catalog_present": catalog_row is not None,
                "catalog_version": evidence["qgis_catalog"]["version"],
                "stable101_l3": code,
                "mapping_status": status,
                "mapping_source": str(raw.get("source", "")),
                "task_role": task_role,
                "frequency": int(raw.get("frequency", 0)),
                "replay_observed_l3": observed,
                "replay_mapping_status": replay_status,
                "headline_eligible": headline_eligible,
                "operator_admission_tier": (
                    "headline_core" if headline_eligible else "capability_gap_diagnostic"
                ),
                "evidence_refs": evidence,
            }
        )
    return rows


def _route_support(design_spec_path: Path) -> dict[str, dict[str, Any]]:
    evidence = f"{design_spec_path}#model-and-system-alignment"
    return {
        route: {
            "supported": True,
            "output_contract": "parameter_free_qgis_processes_links_v1",
            "evidence_ref": evidence,
        }
        for route in ROUTES
    }


def build(
    *,
    hierarchy_path: Path,
    stable98_path: Path,
    stable101_path: Path,
    crosswalk_path: Path,
    stable98_delta_path: Path,
    stable101_delta_path: Path,
    catalog_path: Path,
    replay_path: Path,
    design_spec_path: Path,
) -> dict[str, Any]:
    stable98 = _read_json(stable98_path)
    stable101 = _read_json(stable101_path)
    crosswalk = _read_json(crosswalk_path)
    stable98_delta = _read_json(stable98_delta_path)
    stable101_delta = _read_json(stable101_delta_path)
    families = _stable101_families(hierarchy_path, stable98, stable101)
    stable101_codes = {row["l3_code"] for row in families}
    catalog, catalog_by_id = _catalog(catalog_path)
    evidence = {
        "hierarchy": _evidence_ref(hierarchy_path),
        "stable98_extension": _evidence_ref(stable98_path),
        "stable101_extension": _evidence_ref(stable101_path),
        "qgis_catalog": _evidence_ref(
            catalog_path, version=catalog["catalog_version"]
        ),
        "crosswalk": _evidence_ref(crosswalk_path),
        "stable98_delta": _evidence_ref(stable98_delta_path),
        "stable101_delta": _evidence_ref(stable101_delta_path),
        "source_replay": _evidence_ref(replay_path),
        "design_spec": _evidence_ref(design_spec_path),
    }
    entries = _mapping_entries(
        crosswalk=crosswalk,
        restored={
            **_delta_mapping(stable98_delta),
            **_delta_mapping(stable101_delta),
        },
        catalog_by_id=catalog_by_id,
        stable101_codes=stable101_codes,
        replay_pairs=_replay_pairs(replay_path),
        evidence=evidence,
    )
    by_l3: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in entries:
        if row["stable101_l3"]:
            by_l3[row["stable101_l3"]].append(row)
    route_support = _route_support(design_spec_path)
    matrix = []
    for family in families:
        operators = by_l3.get(family["l3_code"], [])
        admitted = [row for row in operators if row["headline_eligible"]]
        if admitted:
            tier = "headline_core"
            admission_reason = "eligible_strict_operator"
        elif operators:
            tier = "capability_gap_diagnostic"
            admission_reason = "mapped_operator_not_headline_eligible"
        else:
            tier = "refusal"
            admission_reason = "no_frozen_qgis_implementation"
        matrix.append(
            {
                **family,
                "mapping_status": (
                    "stable101_direct" if operators else "pending"
                ),
                "task_roles": sorted({row["task_role"] for row in operators}),
                "admitted_operator_ids": [
                    row["operator_id"] for row in admitted
                ],
                "operator_evidence": [
                    {
                        "operator_id": row["operator_id"],
                        "provider": row["provider"],
                        "catalog_version": row["catalog_version"],
                        "mapping_status": row["mapping_status"],
                        "task_role": row["task_role"],
                    }
                    for row in operators
                ],
                "route_output_support": route_support,
                "evaluation_taxonomy_admission": "granted",
                "evaluation_target_support": (
                    "granted" if tier == "headline_core" else "not_granted"
                ),
                "training_target_support": "not_granted",
                "admission_tier": tier,
                "admission_reason": admission_reason,
                "supply_status": "not_measured_gate3",
                "source_backed_supply": {
                    "status": "not_measured_gate3",
                    "distinct_source_authorities": None,
                    "distinct_normalized_chains": None,
                    "modality_counts": None,
                    "topology_counts": None,
                    "graph_size_counts": None,
                },
                "provisional_roster_candidate": False,
                "evidence_refs": evidence,
            }
        )
    ranked = sorted(
        (row for row in matrix if row["admission_tier"] == "headline_core"),
        key=lambda row: (
            -sum(
                entry["frequency"]
                for entry in by_l3.get(row["l3_code"], [])
                if entry["headline_eligible"]
            ),
            row["token_id"],
        ),
    )
    for row in ranked[:20]:
        row["provisional_roster_candidate"] = True

    status_counts = dict(sorted(Counter(row["mapping_status"] for row in entries).items()))
    mapping = {
        "schema": "gis_recommend.qgis_operator_l3_mapping.paper_v1.v1",
        "taxonomy_id": "stable101-paper-v1",
        "operator_count": len(entries),
        "status_counts": status_counts,
        "replay_conflict_count": sum(
            row["replay_mapping_status"] == "conflict" for row in entries
        ),
        "evaluation_taxonomy_admission": "granted",
        "training_admission": "not_granted",
        "production_merge": "not_granted",
        "evidence_refs": evidence,
        "entries": entries,
    }
    taxonomy = {
        "schema": "gis_recommend.qgis_benchmark_taxonomy.paper_v1.v1",
        "taxonomy_id": "stable101-paper-v1",
        "class_count": 101,
        "evaluation_taxonomy_admission": "granted",
        "training_admission": "not_granted",
        "production_merge": "not_granted",
        "experimental_114_l3_included": False,
        "evidence_refs": evidence,
        "l3_families": families,
    }
    return {
        "stable101_taxonomy": taxonomy,
        "qgis_catalog": catalog,
        "qgis_operator_l3_mapping": mapping,
        "capability_matrix": matrix,
    }


def _write_json(path: Path, value: Any) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def write_outputs(artifacts: dict[str, Any], output_dir: Path) -> dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "stable101_taxonomy": output_dir / "stable101_taxonomy.json",
        "qgis_catalog": output_dir / "qgis_catalog.json",
        "qgis_operator_l3_mapping": output_dir / "qgis_operator_l3_mapping.json",
        "capability_matrix": output_dir / "capability_matrix.jsonl",
    }
    for key in ("stable101_taxonomy", "qgis_catalog", "qgis_operator_l3_mapping"):
        _write_json(paths[key], artifacts[key])
    paths["capability_matrix"].write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
            for row in artifacts["capability_matrix"]
        ),
        encoding="utf-8",
    )
    return paths


def main(argv: list[str] | None = None) -> int:
    root = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hierarchy", type=Path, default=root / "outputs_v2/classification_hierarchy_v2.csv")
    parser.add_argument("--stable98", type=Path, default=root / "docs/reports/qgis_mapping_coverage_audit_2026-07-23/stable98_extension_proposal_v1.json")
    parser.add_argument("--stable101", type=Path, default=root / "docs/reports/qgis_mapping_high_impact_blockers_2026-07-24/stable101_conservative_extension_proposal_v1.json")
    parser.add_argument("--crosswalk", type=Path, default=root / "docs/reports/qgis_mapping_coverage_audit_2026-07-23/qgis_alg_id_crosswalk_v1.json")
    parser.add_argument("--stable98-delta", type=Path, default=root / "docs/reports/qgis_mapping_coverage_audit_2026-07-23/qgis_mapping_authority_stable98_delta_draft_v1.json")
    parser.add_argument("--stable101-delta", type=Path, default=root / "docs/reports/qgis_mapping_high_impact_blockers_2026-07-24/qgis_mapping_authority_stable101_conservative_delta_draft_v1.json")
    parser.add_argument("--catalog", type=Path, default=root.parent / "operators-json/qgis_operators.json")
    parser.add_argument("--replay", type=Path, default=root / "docs/reports/qgis_mapping_high_impact_blockers_2026-07-24/stable101_all1442_source_replay_v1/complete_records.jsonl")
    parser.add_argument("--design-spec", type=Path, default=root / ".omx/specs/deep-interview-qgis-evaluation-set.md")
    parser.add_argument("--output-dir", type=Path, default=root / "benchmarks/qgis_planner_v1/authority")
    args = parser.parse_args(argv)
    artifacts = build(
        hierarchy_path=args.hierarchy,
        stable98_path=args.stable98,
        stable101_path=args.stable101,
        crosswalk_path=args.crosswalk,
        stable98_delta_path=args.stable98_delta,
        stable101_delta_path=args.stable101_delta,
        catalog_path=args.catalog,
        replay_path=args.replay,
        design_spec_path=args.design_spec,
    )
    write_outputs(artifacts, args.output_dir)
    print(
        "stable101=101 catalog={catalog} operators={operators} conflicts={conflicts} headline_l3={headline}".format(
            catalog=artifacts["qgis_catalog"]["operator_count"],
            operators=artifacts["qgis_operator_l3_mapping"]["operator_count"],
            conflicts=artifacts["qgis_operator_l3_mapping"]["replay_conflict_count"],
            headline=sum(row["admission_tier"] == "headline_core" for row in artifacts["capability_matrix"]),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
