#!/usr/bin/env python3
"""Draft and measure high-impact QGIS blocker mappings without granting admission."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


DEFAULT_HIGH_IMPACT_DECISIONS: list[dict[str, str]] = [
    {
        "operator_id": "native:reprojectlayer",
        "candidate_l3_code": "L3_01_10_01",
        "mapping_kind": "restore_old350_l3",
        "scenario": "conservative",
        "confidence": "high",
        "training_role": "core_candidate_after_authority",
        "review_reason": "QGIS catalog says vector CRS reprojection; legacy-350 has Project/Reproject, absent from stable-94.",
    },
    {
        "operator_id": "native:fixgeometries",
        "candidate_l3_code": "L3_01_05_02",
        "mapping_kind": "restore_old350_l3",
        "scenario": "conservative",
        "confidence": "high",
        "training_role": "core_candidate_after_authority",
        "review_reason": "QGIS catalog says invalid geometry repair; legacy-350 has Repair Geometry, absent from stable-94.",
    },
    {
        "operator_id": "gdal:polygonize",
        "candidate_l3_code": "L3_01_09_03",
        "mapping_kind": "restore_old350_l3",
        "scenario": "conservative",
        "confidence": "high",
        "training_role": "core_candidate_after_authority",
        "review_reason": "GDAL polygonize converts raster regions to vector polygons; legacy-350 has Raster-Vector Conversion.",
    },
    {
        "operator_id": "gdal:rasterize",
        "candidate_l3_code": "L3_01_09_03",
        "mapping_kind": "restore_old350_l3",
        "scenario": "conservative",
        "confidence": "high",
        "training_role": "core_candidate_after_authority",
        "review_reason": "GDAL rasterize converts vector geometries to raster; same legacy Raster-Vector Conversion class as polygonize.",
    },
    {
        "operator_id": "native:createspatialindex",
        "candidate_l3_code": "L3_01_07_01",
        "mapping_kind": "restore_old350_l3",
        "scenario": "support_boundary",
        "confidence": "medium",
        "training_role": "support_step_deferred",
        "review_reason": "QGIS catalog describes spatial-index creation for query performance; legacy-350 has Add Spatial Index, but it is support/performance rather than analytical output.",
    },
    {
        "operator_id": "native:saveselectedfeatures",
        "candidate_l3_code": "L3_07_04_01",
        "mapping_kind": "alias_existing_stable94",
        "scenario": "support_boundary",
        "confidence": "medium",
        "training_role": "export_step_deferred",
        "review_reason": "QGIS catalog creates an output layer from selected features; current stable-94 has export-to-shapefile but this operator may be temporary-layer copy/export, so it remains a boundary alias.",
    },
]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number} must contain a JSON object")
            rows.append(value)
    return rows


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _l3_rows(rows: Iterable[dict[str, str]]) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        code = str(row.get("l3_code", "")).strip()
        if not code:
            raise ValueError("hierarchy row missing l3_code")
        if code in result:
            raise ValueError(f"duplicate l3_code {code}")
        result[code] = dict(row)
    return result


def mapping_from_crosswalk(crosswalk: dict[str, Any]) -> dict[str, str]:
    entries = crosswalk.get("entries", {})
    if not isinstance(entries, dict):
        raise ValueError("crosswalk entries must be an object")
    return {
        str(operator_id).lower(): str(entry["l3_code"])
        for operator_id, entry in entries.items()
        if isinstance(entry, dict)
        and entry.get("bridge_type") == "l3_bridge"
        and entry.get("status") == "accepted"
        and str(entry.get("l3_code", "")).startswith("L3_")
    }


def _complete_stats(records: list[dict[str, Any]], mapping: dict[str, str]) -> dict[str, int]:
    complete_records = 0
    complete_chains: set[tuple[str, ...]] = set()
    for record in records:
        ops = [str(op).lower() for op in record.get("qgis_ops", [])]
        if ops and all(op in mapping for op in ops):
            complete_records += 1
            complete_chains.add(tuple(ops))
    return {
        "complete_records": complete_records,
        "complete_unique_chains": len(complete_chains),
    }


def _increment(left: dict[str, int], right: dict[str, int]) -> dict[str, int]:
    return {
        "records": right["complete_records"] - left["complete_records"],
        "unique_chains": right["complete_unique_chains"] - left["complete_unique_chains"],
    }


def _load_stable98_mapping(delta: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for section in ("alias_mappings", "restored_l3_mappings"):
        values = delta.get(section, {})
        if not isinstance(values, dict):
            raise ValueError(f"{section} must be an object")
        result.update({str(operator_id).lower(): str(code) for operator_id, code in values.items()})
    return result


def build_high_impact_mappings(
    decisions: list[dict[str, str]],
    *,
    stable_codes: set[str],
    legacy_codes: set[str],
) -> dict[str, Any]:
    conservative: dict[str, str] = {}
    extended: dict[str, str] = {}
    entries: list[dict[str, str]] = []
    seen: set[str] = set()
    for decision in decisions:
        operator_id = str(decision.get("operator_id", "")).strip().lower()
        code = str(decision.get("candidate_l3_code", "")).strip()
        mapping_kind = str(decision.get("mapping_kind", "")).strip()
        scenario = str(decision.get("scenario", "")).strip()
        if not operator_id or not code:
            raise ValueError("each decision must include operator_id and candidate_l3_code")
        if operator_id in seen:
            raise ValueError(f"duplicate operator decision {operator_id}")
        seen.add(operator_id)
        if mapping_kind == "alias_existing_stable94":
            if code not in stable_codes:
                raise ValueError(f"{operator_id}: alias target {code} is absent from stable hierarchy")
        elif mapping_kind == "restore_old350_l3":
            if code not in legacy_codes:
                raise ValueError(f"{operator_id}: restored target {code} is absent from legacy hierarchy")
            if code in stable_codes:
                raise ValueError(f"{operator_id}: restored target {code} already exists in stable hierarchy")
        else:
            raise ValueError(f"{operator_id}: unsupported mapping kind {mapping_kind!r}")
        if scenario not in {"conservative", "support_boundary"}:
            raise ValueError(f"{operator_id}: unsupported scenario {scenario!r}")

        row = dict(decision)
        row["operator_id"] = operator_id
        row["candidate_l3_code"] = code
        row["taxonomy_admission"] = "not_granted"
        row["training_admission"] = "not_granted"
        entries.append(row)
        if scenario == "conservative":
            conservative[operator_id] = code
        extended[operator_id] = code

    return {
        "entries": sorted(entries, key=lambda row: row["operator_id"]),
        "conservative_mapping": dict(sorted(conservative.items())),
        "extended_mapping": dict(sorted(extended.items())),
        "new_legacy_codes_conservative": sorted(
            {code for code in conservative.values() if code not in stable_codes}
        ),
        "new_legacy_codes_extended": sorted(
            {code for code in extended.values() if code not in stable_codes}
        ),
        "taxonomy_admission": "not_granted",
        "training_admission": "not_granted",
    }


def analyze_scenarios(
    records: list[dict[str, Any]],
    *,
    baseline_mapping: dict[str, str],
    stable98_mapping: dict[str, str],
    conservative_mapping: dict[str, str],
    extended_mapping: dict[str, str],
) -> dict[str, Any]:
    baseline_full = dict(baseline_mapping)
    stable98_full = {**baseline_full, **stable98_mapping}
    conservative_full = {**stable98_full, **conservative_mapping}
    extended_full = {**stable98_full, **extended_mapping}
    baseline_stats = _complete_stats(records, baseline_full)
    stable98_stats = _complete_stats(records, stable98_full)
    conservative_stats = _complete_stats(records, conservative_full)
    extended_stats = _complete_stats(records, extended_full)
    return {
        "total_records": len(records),
        "total_unique_chains": len(
            {tuple(str(op).lower() for op in record.get("qgis_ops", [])) for record in records}
        ),
        "baseline": baseline_stats,
        "stable98_draft": stable98_stats,
        "high_impact_conservative": conservative_stats,
        "high_impact_extended": extended_stats,
        "increment_vs_stable98_conservative": _increment(stable98_stats, conservative_stats),
        "increment_vs_stable98_extended": _increment(stable98_stats, extended_stats),
        "support_boundary_increment": _increment(conservative_stats, extended_stats),
    }


def _operator_stats(
    records: list[dict[str, Any]],
    *,
    operator_ids: Iterable[str],
    stable98_mapping: dict[str, str],
    additions: dict[str, str],
) -> dict[str, dict[str, Any]]:
    stable98_full = dict(stable98_mapping)
    result: dict[str, dict[str, Any]] = {}
    for operator_id in sorted(operator_ids):
        with_single = {**stable98_full, operator_id: additions[operator_id]}
        rows = [
            record
            for record in records
            if operator_id in [str(op).lower() for op in record.get("qgis_ops", [])]
        ]
        newly_complete = [
            record
            for record in rows
            if not _is_complete(record, stable98_full) and _is_complete(record, with_single)
        ]
        unresolved = Counter(
            str(op).lower()
            for record in rows
            for op in record.get("qgis_ops", [])
            if str(op).lower() not in with_single
        )
        result[operator_id] = {
            "record_count": len(rows),
            "occurrence_count": sum(
                [str(op).lower() for op in record.get("qgis_ops", [])].count(operator_id)
                for record in rows
            ),
            "unique_chain_count": len(
                {tuple(str(op).lower() for op in record.get("qgis_ops", [])) for record in rows}
            ),
            "newly_complete_if_added_alone_records": len(newly_complete),
            "newly_complete_if_added_alone_unique_chains": len(
                {tuple(str(op).lower() for op in record.get("qgis_ops", [])) for record in newly_complete}
            ),
            "top_remaining_blockers_if_added_alone": dict(
                sorted(unresolved.items(), key=lambda item: (-item[1], item[0]))[:12]
            ),
        }
    return result


def _is_complete(record: dict[str, Any], mapping: dict[str, str]) -> bool:
    ops = [str(op).lower() for op in record.get("qgis_ops", [])]
    return bool(ops) and all(op in mapping for op in ops)


def _sample_examples(
    records: list[dict[str, Any]], operator_ids: Iterable[str], *, per_operator: int
) -> list[dict[str, Any]]:
    examples: list[dict[str, Any]] = []
    for operator_id in sorted(operator_ids):
        rank = 0
        seen_chains: set[tuple[str, ...]] = set()
        for index, record in enumerate(records, start=1):
            ops = tuple(str(op).lower() for op in record.get("qgis_ops", []))
            if operator_id not in ops or ops in seen_chains:
                continue
            seen_chains.add(ops)
            rank += 1
            examples.append(
                {
                    "operator_id": operator_id,
                    "sample_rank": rank,
                    "record_index": index,
                    "source": record.get("source", ""),
                    "task_text": record.get("task_text", ""),
                    "qgis_ops": list(ops),
                    "optional_l3_sequence": record.get("optional_l3_sequence"),
                }
            )
            if rank >= per_operator:
                break
    return examples


def _decision_rows(
    decisions: list[dict[str, str]],
    *,
    catalog: dict[str, Any],
    stable_by_code: dict[str, dict[str, str]],
    legacy_by_code: dict[str, dict[str, str]],
    crosswalk_entries: dict[str, Any],
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for decision in decisions:
        operator_id = decision["operator_id"].lower()
        code = decision["candidate_l3_code"]
        l3_row = stable_by_code.get(code) or legacy_by_code.get(code, {})
        crosswalk = crosswalk_entries.get(operator_id, {})
        rows.append(
            {
                **decision,
                "operator_id": operator_id,
                "candidate_l3_name": l3_row.get("l3_name", ""),
                "candidate_l3_description": l3_row.get("l3_description", ""),
                "catalog_display_name": catalog.get(operator_id, {}).get("display_name", ""),
                "catalog_description": catalog.get(operator_id, {}).get("description", ""),
                "previous_crosswalk_status": crosswalk.get("status", ""),
                "previous_crosswalk_bridge_type": crosswalk.get("bridge_type", ""),
                "previous_crosswalk_l3_code": crosswalk.get("l3_code", ""),
                "taxonomy_admission": "not_granted",
                "training_admission": "not_granted",
            }
        )
    return sorted(rows, key=lambda row: row["operator_id"])


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def _write_json(path: Path, value: Any) -> None:
    _atomic_write_text(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    _atomic_write_text(
        path,
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
    )


def _markdown(summary: dict[str, Any], decision_rows: list[dict[str, Any]]) -> str:
    lines = [
        "# QGIS高影响阻塞算子映射草案（2026-07-24）",
        "",
        "本报告只做影响测算，不修改stable-94/stable-98 authority，不授予训练准入。",
        "证据范围为本机已同步的QGIS catalog与当前chain dataset记录；正式准入前仍需在服务器原始源码上补源码片段复核。",
        "",
        "## 影响统计",
        "",
        "| 场景 | 完整记录 | 唯一链 | 相对stable-98新增记录 | 相对stable-98新增唯一链 |",
        "|---|---:|---:|---:|---:|",
    ]
    stable98 = summary["stable98_draft"]
    for key, label in [
        ("baseline", "严格stable-94"),
        ("stable98_draft", "stable-98草案"),
        ("high_impact_conservative", "高影响保守档"),
        ("high_impact_extended", "高影响扩展档"),
    ]:
        stats = summary[key]
        lines.append(
            f"| {label} | {stats['complete_records']} | {stats['complete_unique_chains']} | "
            f"{stats['complete_records'] - stable98['complete_records']} | "
            f"{stats['complete_unique_chains'] - stable98['complete_unique_chains']} |"
        )
    lines.extend(
        [
            "",
            "## 裁判草案",
            "",
            "| 算子 | 场景 | 候选L3 | 置信度 | 训练角色 | 说明 |",
            "|---|---|---|---|---|---|",
        ]
    )
    for row in decision_rows:
        reason = str(row.get("review_reason", "")).replace("|", "/")
        lines.append(
            f"| `{row['operator_id']}` | {row['scenario']} | `{row['candidate_l3_code']}` "
            f"{row.get('candidate_l3_name', '')} | {row['confidence']} | "
            f"{row['training_role']} | {reason} |"
        )
    lines.extend(
        [
            "",
            "## 逐算子影响",
            "",
            "| 算子 | 记录 | 唯一链 | 单独加入可解锁记录 | 单独加入可解锁唯一链 | 主要共现阻塞 |",
            "|---|---:|---:|---:|---:|---|",
        ]
    )
    for operator_id, impact in sorted(summary.get("operator_impact", {}).items()):
        blockers = ", ".join(
            f"`{key}`:{value}"
            for key, value in list(impact.get("top_remaining_blockers_if_added_alone", {}).items())[:5]
        )
        lines.append(
            f"| `{operator_id}` | {impact['record_count']} | {impact['unique_chain_count']} | "
            f"{impact['newly_complete_if_added_alone_records']} | "
            f"{impact['newly_complete_if_added_alone_unique_chains']} | {blockers} |"
        )
    lines.extend(
        [
            "",
            "## 结论",
            "",
            "- 保守档只包含高置信能力映射，仍需正式taxonomy authority批准后才能进训练。",
            "- `createspatialindex`和`saveselectedfeatures`属于support/export边界；可用于测算潜在覆盖，但不能直接当作训练准入。",
            "- 后续若要进一步扩量，应优先补正式L3 authority和源码片段复核，而不是把历史`optional_l3_sequence`直接当真值。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stable-hierarchy", required=True, type=Path)
    parser.add_argument("--legacy-hierarchy", required=True, type=Path)
    parser.add_argument("--crosswalk", required=True, type=Path)
    parser.add_argument("--stable98-delta", required=True, type=Path)
    parser.add_argument("--chain-dataset", required=True, type=Path)
    parser.add_argument("--catalog", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--examples-per-operator", default=5, type=int)
    args = parser.parse_args()

    stable_rows = _read_csv(args.stable_hierarchy)
    legacy_rows = _read_csv(args.legacy_hierarchy)
    stable_by_code = _l3_rows(stable_rows)
    legacy_by_code = _l3_rows(legacy_rows)
    crosswalk = json.loads(args.crosswalk.read_text(encoding="utf-8"))
    stable98_delta = json.loads(args.stable98_delta.read_text(encoding="utf-8"))
    records = _read_jsonl(args.chain_dataset)
    catalog = json.loads(args.catalog.read_text(encoding="utf-8"))
    if not isinstance(catalog, dict):
        raise ValueError("catalog must be an object keyed by operator id")

    mapping_bundle = build_high_impact_mappings(
        DEFAULT_HIGH_IMPACT_DECISIONS,
        stable_codes=set(stable_by_code),
        legacy_codes=set(legacy_by_code),
    )
    baseline_mapping = mapping_from_crosswalk(crosswalk)
    stable98_mapping = _load_stable98_mapping(stable98_delta)
    summary = analyze_scenarios(
        records,
        baseline_mapping=baseline_mapping,
        stable98_mapping=stable98_mapping,
        conservative_mapping=mapping_bundle["conservative_mapping"],
        extended_mapping=mapping_bundle["extended_mapping"],
    )
    decision_rows = _decision_rows(
        mapping_bundle["entries"],
        catalog=catalog,
        stable_by_code=stable_by_code,
        legacy_by_code=legacy_by_code,
        crosswalk_entries=crosswalk.get("entries", {}),
    )
    all_additions = mapping_bundle["extended_mapping"]
    stable98_full = {**baseline_mapping, **stable98_mapping}
    summary.update(
        {
            "schema": "gis_recommend.qgis_high_impact_blocker_mapping_draft.v1",
            "status": "draft_not_granted",
            "operator_count": len(mapping_bundle["entries"]),
            "conservative_operator_count": len(mapping_bundle["conservative_mapping"]),
            "support_boundary_operator_count": len(mapping_bundle["extended_mapping"]) - len(mapping_bundle["conservative_mapping"]),
            "new_legacy_codes_conservative": mapping_bundle["new_legacy_codes_conservative"],
            "new_legacy_codes_extended": mapping_bundle["new_legacy_codes_extended"],
            "operator_impact": _operator_stats(
                records,
                operator_ids=all_additions,
                stable98_mapping=stable98_full,
                additions=all_additions,
            ),
            "taxonomy_admission": "not_granted",
            "training_admission": "not_granted",
            "evidence_scope": (
                "local_qgis_catalog_and_current_chain_dataset_only; "
                "raw_server_source_snippet_review_required_before_admission"
            ),
            "input_sha256": {
                "stable_hierarchy": _sha256(args.stable_hierarchy),
                "legacy_hierarchy": _sha256(args.legacy_hierarchy),
                "crosswalk": _sha256(args.crosswalk),
                "stable98_delta": _sha256(args.stable98_delta),
                "chain_dataset": _sha256(args.chain_dataset),
                "catalog": _sha256(args.catalog),
            },
        }
    )

    examples = _sample_examples(
        records,
        [row["operator_id"] for row in mapping_bundle["entries"]],
        per_operator=args.examples_per_operator,
    )
    output_dir = args.output_dir
    decisions_path = output_dir / "high_impact_blocker_decisions_v1.jsonl"
    examples_path = output_dir / "high_impact_blocker_examples_v1.jsonl"
    summary_path = output_dir / "high_impact_blocker_impact_v1.json"
    report_path = output_dir / "qgis_high_impact_blockers_2026-07-24.md"
    _write_jsonl(decisions_path, decision_rows)
    _write_jsonl(examples_path, examples)
    _write_json(summary_path, summary)
    _atomic_write_text(report_path, _markdown(summary, decision_rows))
    summary["artifact_sha256"] = {
        "decisions": _sha256(decisions_path),
        "examples": _sha256(examples_path),
        "report": _sha256(report_path),
    }
    _write_json(summary_path, summary)

    print(
        "records={records} stable98={stable98} conservative={conservative} extended={extended}".format(
            records=summary["total_records"],
            stable98=summary["stable98_draft"]["complete_records"],
            conservative=summary["high_impact_conservative"]["complete_records"],
            extended=summary["high_impact_extended"]["complete_records"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
