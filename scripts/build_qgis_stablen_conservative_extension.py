#!/usr/bin/env python3
"""Build the source-reviewed conservative stable-N QGIS mapping draft.

This is a report-only authority draft. It starts from the non-admitted
stable-98 draft, appends only the four source-reviewed conservative mappings,
and keeps support/export boundary operators out of the training target path.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable


CONSERVATIVE_OPERATORS = [
    "native:reprojectlayer",
    "native:fixgeometries",
    "gdal:polygonize",
    "gdal:rasterize",
]

BOUNDARY_OPERATORS = [
    "native:createspatialindex",
    "native:saveselectedfeatures",
]


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


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


def stable98_code_to_id(stable98_extension: dict[str, Any]) -> dict[str, int]:
    existing = stable98_extension.get("existing_code_to_id")
    additions = stable98_extension.get("proposed_code_to_id_additions")
    if not isinstance(existing, dict) or not isinstance(additions, dict):
        raise ValueError("stable98 extension must contain existing and proposed code_to_id mappings")
    combined = {str(code): int(token_id) for code, token_id in existing.items()}
    for code, token_id in additions.items():
        code = str(code)
        if code in combined:
            raise ValueError(f"stable98 extension duplicates code {code}")
        combined[code] = int(token_id)
    if sorted(combined.values()) != list(range(len(combined))):
        raise ValueError("stable98 token IDs must be contiguous from zero")
    declared_count = int(stable98_extension.get("proposed_class_count", -1))
    if declared_count != len(combined):
        raise ValueError("stable98 proposed_class_count does not match code_to_id size")
    if stable98_extension.get("existing_token_ids_unchanged") is not True:
        raise ValueError("stable98 extension must preserve existing token IDs")
    return combined


def _load_delta_mapping(delta: dict[str, Any]) -> dict[str, str]:
    result: dict[str, str] = {}
    for section in ("alias_mappings", "restored_l3_mappings"):
        values = delta.get(section, {})
        if not isinstance(values, dict):
            raise ValueError(f"{section} must be an object")
        result.update({str(operator).lower(): str(code) for operator, code in values.items()})
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


def conservative_decision_rows(
    decisions: list[dict[str, Any]],
    *,
    base_codes: set[str],
    legacy_by_code: dict[str, dict[str, str]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    by_operator: dict[str, dict[str, Any]] = {}
    for row in decisions:
        operator_id = str(row.get("operator_id", "")).strip().lower()
        if not operator_id:
            raise ValueError("decision row missing operator_id")
        if operator_id in by_operator:
            raise ValueError(f"duplicate decision for {operator_id}")
        by_operator[operator_id] = dict(row, operator_id=operator_id)

    if set(CONSERVATIVE_OPERATORS) - set(by_operator):
        missing = sorted(set(CONSERVATIVE_OPERATORS) - set(by_operator))
        raise ValueError(f"missing conservative decisions: {missing}")

    accepted: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    for operator_id in CONSERVATIVE_OPERATORS:
        row = dict(by_operator[operator_id])
        code = str(row.get("candidate_l3_code", "")).strip()
        if row.get("scenario") != "conservative":
            raise ValueError(f"{operator_id}: expected conservative scenario")
        if row.get("confidence") != "high":
            raise ValueError(f"{operator_id}: expected high confidence")
        if row.get("mapping_kind") != "restore_old350_l3":
            raise ValueError(f"{operator_id}: expected restore_old350_l3 mapping")
        if code in base_codes:
            raise ValueError(f"{operator_id}: {code} already exists in stable98 base")
        if code not in legacy_by_code:
            raise ValueError(f"{operator_id}: {code} missing from legacy hierarchy")
        l3_row = legacy_by_code[code]
        accepted.append(
            {
                "operator_id": operator_id,
                "l3_code": code,
                "l3_name": l3_row.get("l3_name", ""),
                "l3_description": l3_row.get("l3_description", ""),
                "mapping_kind": "restore_old350_l3",
                "review_decision": "accepted_conservative_mapping_proposal",
                "review_reason": row.get("review_reason", ""),
                "source_review_required": True,
                "taxonomy_admission": "not_granted",
                "training_admission": "not_granted",
            }
        )

    for operator_id in BOUNDARY_OPERATORS:
        row = by_operator.get(operator_id)
        if not row:
            continue
        excluded.append(
            {
                "operator_id": operator_id,
                "candidate_l3_code": row.get("candidate_l3_code", ""),
                "candidate_l3_name": row.get("candidate_l3_name", ""),
                "scenario": row.get("scenario", ""),
                "training_role": row.get("training_role", ""),
                "exclusion_reason": (
                    "support/export boundary confirmed by source review; excluded from "
                    "the conservative stable-N training-target draft"
                ),
                "taxonomy_admission": "not_granted",
                "training_admission": "not_granted",
            }
        )
    return sorted(accepted, key=lambda row: row["operator_id"]), sorted(
        excluded, key=lambda row: row["operator_id"]
    )


def validate_source_review(
    source_rows: list[dict[str, Any]],
    source_summary: dict[str, Any],
    accepted_entries: list[dict[str, Any]],
    *,
    required_samples: int = 3,
) -> dict[str, Any]:
    rows_by_operator: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in source_rows:
        operator_id = str(row.get("operator_id", "")).strip().lower()
        if operator_id:
            rows_by_operator[operator_id].append(row)

    selected_per_operator = source_summary.get("selected_per_operator", {})
    unique_layer_hits = source_summary.get("unique_layer_hits", {})
    if not isinstance(selected_per_operator, dict) or not isinstance(unique_layer_hits, dict):
        raise ValueError("source summary must contain selected_per_operator and unique_layer_hits")

    reviewed: dict[str, dict[str, Any]] = {}
    for entry in accepted_entries:
        operator_id = entry["operator_id"]
        rows = rows_by_operator.get(operator_id, [])
        if int(selected_per_operator.get(operator_id, 0)) < required_samples:
            raise ValueError(f"{operator_id}: source summary has fewer than {required_samples} samples")
        if len(rows) < required_samples:
            raise ValueError(f"{operator_id}: source JSONL has fewer than {required_samples} samples")
        for row in rows[:required_samples]:
            if row.get("active_processing_call") is not True:
                raise ValueError(f"{operator_id}: source row is not an active processing call")
            if row.get("candidate_l3_code") != entry["l3_code"]:
                raise ValueError(f"{operator_id}: source row L3 code does not match decision")
            if row.get("source_review_verdict") != "accept_mapping_after_authority":
                raise ValueError(f"{operator_id}: source review verdict is not acceptable")
            if not str(row.get("source_path", "")).startswith("/home/yll/"):
                raise ValueError(f"{operator_id}: source path must be under /home/yll")
        reviewed[operator_id] = {
            "selected_samples": len(rows),
            "required_samples": required_samples,
            "unique_layer_hits": int(unique_layer_hits.get(operator_id, 0)),
            "sample_refs": [
                {
                    "source_path": row.get("source_path", ""),
                    "line_start": row.get("call", {}).get("line_start"),
                    "line_end": row.get("call", {}).get("line_end"),
                    "param_keys": row.get("call", {}).get("param_keys", []),
                    "content_sha256": row.get("content_sha256", ""),
                }
                for row in rows[:required_samples]
            ],
        }

    return {
        "schema": "gis_recommend.qgis_stablen_source_review_gate.v1",
        "status": "passed",
        "review_date": source_summary.get("date"),
        "required_samples_per_operator": required_samples,
        "accepted_operator_count": len(accepted_entries),
        "accepted_total_samples": sum(value["selected_samples"] for value in reviewed.values()),
        "reviewed_operators": reviewed,
        "source_artifact_sha256": source_summary.get("artifact_sha256", {}),
        "taxonomy_admission": "not_granted",
        "training_admission": "not_granted",
    }


def build_extension_proposal(
    *,
    stable98_extension: dict[str, Any],
    accepted_entries: list[dict[str, Any]],
    legacy_by_code: dict[str, dict[str, str]],
    source_review_gate: dict[str, Any],
) -> dict[str, Any]:
    base_code_to_id = stable98_code_to_id(stable98_extension)
    base_count = len(base_code_to_id)
    new_codes = sorted(
        {entry["l3_code"] for entry in accepted_entries},
        key=lambda code: list(legacy_by_code).index(code),
    )
    additions = {code: base_count + offset for offset, code in enumerate(new_codes)}
    restored_l3: list[dict[str, Any]] = []
    for code in new_codes:
        row = dict(legacy_by_code[code])
        row["proposed_token_id"] = additions[code]
        row["source_taxonomy"] = "legacy350"
        row["evidence_level"] = "source_snippet_reviewed_conservative"
        row["taxonomy_admission"] = "not_granted"
        restored_l3.append(row)

    proposed_count = base_count + len(additions)
    return {
        "schema": "gis_recommend.qgis_stablen_conservative_extension_proposal.v1",
        "status": "formal_draft_not_granted",
        "base_taxonomy": stable98_extension.get("proposed_taxonomy", "stable98"),
        "proposed_taxonomy": f"stable{proposed_count}",
        "scope": "source_reviewed_conservative_qgis_mappings_only",
        "base_class_count": base_count,
        "proposed_class_count": proposed_count,
        "existing_code_to_id": dict(sorted(base_code_to_id.items(), key=lambda item: item[1])),
        "proposed_code_to_id_additions": additions,
        "restored_l3": restored_l3,
        "existing_token_ids_unchanged": True,
        "source_review_gate": {
            "status": source_review_gate["status"],
            "review_date": source_review_gate["review_date"],
            "required_samples_per_operator": source_review_gate["required_samples_per_operator"],
            "accepted_operator_count": source_review_gate["accepted_operator_count"],
        },
        "taxonomy_admission": "not_granted",
        "training_admission": "not_granted",
    }


def build_mapping_delta(
    accepted_entries: list[dict[str, Any]],
    excluded_entries: list[dict[str, Any]],
) -> dict[str, Any]:
    restored = {entry["operator_id"]: entry["l3_code"] for entry in accepted_entries}
    return {
        "schema": "gis_recommend.qgis_mapping_authority_stablen_conservative_delta_draft.v1",
        "status": "formal_draft_not_granted",
        "scope": "only_four_source_reviewed_conservative_mappings",
        "restored_l3_mappings": dict(sorted(restored.items())),
        "alias_mappings": {},
        "entries": accepted_entries,
        "excluded_boundary_entries": excluded_entries,
        "operator_count": len(accepted_entries),
        "excluded_boundary_operator_count": len(excluded_entries),
        "taxonomy_admission": "not_granted",
        "training_admission": "not_granted",
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


def _chain_state(ops: list[str], mapping: dict[str, str]) -> tuple[list[str], list[str]]:
    unresolved = list(dict.fromkeys(op for op in ops if op not in mapping))
    sequence = [mapping[op] for op in ops] if not unresolved else []
    return unresolved, sequence


def analyze_conservative_impact(
    records: list[dict[str, Any]],
    *,
    stable98_mapping: dict[str, str],
    conservative_mapping: dict[str, str],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    proposed_mapping = {**stable98_mapping, **conservative_mapping}
    target_ops = set(conservative_mapping)
    details: list[dict[str, Any]] = []
    for record_index, record in enumerate(records, start=1):
        ops = [str(op).lower() for op in record.get("qgis_ops", [])]
        if not ops or not target_ops.intersection(ops):
            continue
        before_unresolved, _ = _chain_state(ops, stable98_mapping)
        after_unresolved, after_sequence = _chain_state(ops, proposed_mapping)
        if not before_unresolved:
            impact_stage = "already_complete_stable98"
        elif not after_unresolved:
            impact_stage = "newly_complete_stablen_conservative"
        else:
            impact_stage = "still_incomplete_after_stablen"
        identity = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        details.append(
            {
                "record_index": record_index,
                "record_sha256": hashlib.sha256(identity.encode("utf-8")).hexdigest(),
                "task_text": record.get("task_text", ""),
                "qgis_ops": ops,
                "proposal_ops_present": sorted(target_ops.intersection(ops)),
                "stable98_unresolved_ops": before_unresolved,
                "stablen_unresolved_ops": after_unresolved,
                "proposed_l3_sequence": after_sequence,
                "impact_stage": impact_stage,
                "taxonomy_admission": "not_granted",
                "training_admission": "not_granted",
            }
        )

    stable98_stats = _complete_stats(records, stable98_mapping)
    stablen_stats = _complete_stats(records, proposed_mapping)
    operator_impact: dict[str, dict[str, int]] = {}
    for operator_id in sorted(target_ops):
        matching = [row for row in details if operator_id in row["qgis_ops"]]
        operator_impact[operator_id] = {
            "record_count": len(matching),
            "occurrence_count": sum(row["qgis_ops"].count(operator_id) for row in matching),
            "unique_chain_count": len({tuple(row["qgis_ops"]) for row in matching}),
            "newly_complete_records": sum(
                row["impact_stage"] == "newly_complete_stablen_conservative"
                for row in matching
            ),
            "newly_complete_unique_chains": len(
                {
                    tuple(row["qgis_ops"])
                    for row in matching
                    if row["impact_stage"] == "newly_complete_stablen_conservative"
                }
            ),
        }

    still_incomplete = [row for row in details if row["impact_stage"] == "still_incomplete_after_stablen"]
    summary = {
        "schema": "gis_recommend.qgis_stablen_conservative_mapping_impact.v1",
        "status": "formal_draft_not_granted",
        "total_records": len(records),
        "total_unique_chains": len(
            {tuple(str(op).lower() for op in record.get("qgis_ops", [])) for record in records}
        ),
        "stable98_draft": stable98_stats,
        "stablen_conservative_draft": stablen_stats,
        "increment_vs_stable98": {
            "records": stablen_stats["complete_records"] - stable98_stats["complete_records"],
            "unique_chains": (
                stablen_stats["complete_unique_chains"]
                - stable98_stats["complete_unique_chains"]
            ),
        },
        "affected_records": len(details),
        "affected_unique_chains": len({tuple(row["qgis_ops"]) for row in details}),
        "newly_complete_records": sum(
            row["impact_stage"] == "newly_complete_stablen_conservative" for row in details
        ),
        "newly_complete_unique_chains": len(
            {
                tuple(row["qgis_ops"])
                for row in details
                if row["impact_stage"] == "newly_complete_stablen_conservative"
            }
        ),
        "still_incomplete_records": len(still_incomplete),
        "still_incomplete_unique_chains": len({tuple(row["qgis_ops"]) for row in still_incomplete}),
        "remaining_blocker_counts": dict(
            sorted(
                Counter(
                    operator_id
                    for row in still_incomplete
                    for operator_id in row["stablen_unresolved_ops"]
                ).items(),
                key=lambda item: (-item[1], item[0]),
            )
        ),
        "operator_impact": operator_impact,
        "taxonomy_admission": "not_granted",
        "training_admission": "not_granted",
    }
    return summary, details


def _markdown(
    proposal: dict[str, Any],
    delta: dict[str, Any],
    impact: dict[str, Any],
    source_review_gate: dict[str, Any],
) -> str:
    lines = [
        "# QGIS stable-N保守扩展正式草案（2026-07-24）",
        "",
        "本草案只纳入服务器源码片段复核通过的4个保守映射，不修改`outputs_v2` authority，不生成训练集，不训练模型。",
        "",
        "## 版本口径",
        "",
        f"- 基线：`{proposal['base_taxonomy']}`，{proposal['base_class_count']}个L3。",
        f"- 草案：`{proposal['proposed_taxonomy']}`，{proposal['proposed_class_count']}个L3。",
        "- 旧token ID保持不变，新L3只追加到末尾。",
        "- `native:createspatialindex`和`native:saveselectedfeatures`不在本草案内。",
        "",
        "## 新增L3",
        "",
        "| L3 | token | 名称 | 说明 |",
        "|---|---:|---|---|",
    ]
    for row in proposal["restored_l3"]:
        description = str(row.get("l3_description", "")).replace("|", "/")
        lines.append(
            f"| `{row['l3_code']}` | {row['proposed_token_id']} | "
            f"{row.get('l3_name', '')} | {description} |"
        )

    lines.extend(
        [
            "",
            "## QGIS算子映射",
            "",
            "| QGIS operator | L3 | 证据 |",
            "|---|---|---|",
        ]
    )
    reviewed = source_review_gate["reviewed_operators"]
    for row in delta["entries"]:
        operator_id = row["operator_id"]
        sample_count = reviewed[operator_id]["selected_samples"]
        unique_hits = reviewed[operator_id]["unique_layer_hits"]
        lines.append(
            f"| `{operator_id}` | `{row['l3_code']}` {row['l3_name']} | "
            f"{sample_count}条源码片段，源码层唯一命中{unique_hits} |"
        )

    lines.extend(
        [
            "",
            "## 覆盖影响",
            "",
            "| 场景 | 完整记录 | 唯一链 |",
            "|---|---:|---:|",
            (
                f"| stable-98草案 | {impact['stable98_draft']['complete_records']} | "
                f"{impact['stable98_draft']['complete_unique_chains']} |"
            ),
            (
                f"| stable-N保守草案 | {impact['stablen_conservative_draft']['complete_records']} | "
                f"{impact['stablen_conservative_draft']['complete_unique_chains']} |"
            ),
            (
                f"| 增量 | {impact['increment_vs_stable98']['records']} | "
                f"{impact['increment_vs_stable98']['unique_chains']} |"
            ),
            "",
            "## 明确排除",
            "",
        ]
    )
    for row in delta["excluded_boundary_entries"]:
        lines.append(
            f"- `{row['operator_id']}`：{row['exclusion_reason']}。"
        )
    lines.extend(
        [
            "",
            "## 准入状态",
            "",
            "- `taxonomy_admission=not_granted`。",
            "- `training_admission=not_granted`。",
            "- 下一步只能进入taxonomy authority人工确认；确认前不得写入生产映射或训练集。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stable98-extension", required=True, type=Path)
    parser.add_argument("--stable98-delta", required=True, type=Path)
    parser.add_argument("--legacy-hierarchy", required=True, type=Path)
    parser.add_argument("--crosswalk", required=True, type=Path)
    parser.add_argument("--decisions", required=True, type=Path)
    parser.add_argument("--source-review", required=True, type=Path)
    parser.add_argument("--source-summary", required=True, type=Path)
    parser.add_argument("--chain-dataset", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--date", default="2026-07-24")
    args = parser.parse_args()

    stable98_extension = _read_json(args.stable98_extension)
    stable98_delta = _read_json(args.stable98_delta)
    legacy_by_code = _l3_rows(_read_csv(args.legacy_hierarchy))
    crosswalk = _read_json(args.crosswalk)
    decisions = _read_jsonl(args.decisions)
    source_rows = _read_jsonl(args.source_review)
    source_summary = _read_json(args.source_summary)
    records = _read_jsonl(args.chain_dataset)

    base_code_to_id = stable98_code_to_id(stable98_extension)
    accepted_entries, excluded_entries = conservative_decision_rows(
        decisions,
        base_codes=set(base_code_to_id),
        legacy_by_code=legacy_by_code,
    )
    source_review_gate = validate_source_review(
        source_rows,
        source_summary,
        accepted_entries,
    )
    proposal = build_extension_proposal(
        stable98_extension=stable98_extension,
        accepted_entries=accepted_entries,
        legacy_by_code=legacy_by_code,
        source_review_gate=source_review_gate,
    )
    proposal["proposal_date"] = args.date

    delta = build_mapping_delta(accepted_entries, excluded_entries)
    delta["proposal_date"] = args.date

    stable98_mapping = {
        **mapping_from_crosswalk(crosswalk),
        **_load_delta_mapping(stable98_delta),
    }
    conservative_mapping = delta["restored_l3_mappings"]
    impact, impact_records = analyze_conservative_impact(
        records,
        stable98_mapping=stable98_mapping,
        conservative_mapping=conservative_mapping,
    )
    impact["proposal_date"] = args.date

    input_paths = {
        "stable98_extension": args.stable98_extension,
        "stable98_delta": args.stable98_delta,
        "legacy_hierarchy": args.legacy_hierarchy,
        "crosswalk": args.crosswalk,
        "decisions": args.decisions,
        "source_review": args.source_review,
        "source_summary": args.source_summary,
        "chain_dataset": args.chain_dataset,
    }
    input_sha256 = {name: _sha256(path) for name, path in input_paths.items()}
    for artifact in (proposal, delta, source_review_gate, impact):
        artifact["input_sha256"] = input_sha256

    output_dir = args.output_dir
    proposal_path = output_dir / "stable101_conservative_extension_proposal_v1.json"
    delta_path = output_dir / "qgis_mapping_authority_stable101_conservative_delta_draft_v1.json"
    source_gate_path = output_dir / "stable101_conservative_source_review_gate_v1.json"
    impact_path = output_dir / "stable101_conservative_impact_v1.json"
    impact_records_path = output_dir / "stable101_conservative_impact_records_v1.jsonl"
    report_path = output_dir / "qgis_stable101_conservative_extension_2026-07-24.md"
    manifest_path = output_dir / "stable101_conservative_artifact_manifest_v1.json"

    _write_json(proposal_path, proposal)
    _write_json(delta_path, delta)
    _write_json(source_gate_path, source_review_gate)
    _write_jsonl(impact_records_path, impact_records)
    _write_json(impact_path, impact)
    _atomic_write_text(report_path, _markdown(proposal, delta, impact, source_review_gate))

    _write_json(
        manifest_path,
        {
            "schema": "gis_recommend.qgis_stablen_conservative_artifact_manifest.v1",
            "status": "formal_draft_not_granted",
            "proposal_date": args.date,
            "artifacts": {
                "extension_proposal": str(proposal_path),
                "mapping_delta": str(delta_path),
                "source_review_gate": str(source_gate_path),
                "impact": str(impact_path),
                "impact_records": str(impact_records_path),
                "report": str(report_path),
            },
            "artifact_sha256": {
                "extension_proposal": _sha256(proposal_path),
                "mapping_delta": _sha256(delta_path),
                "source_review_gate": _sha256(source_gate_path),
                "impact": _sha256(impact_path),
                "impact_records": _sha256(impact_records_path),
                "report": _sha256(report_path),
            },
            "input_sha256": input_sha256,
            "taxonomy_admission": "not_granted",
            "training_admission": "not_granted",
        },
    )

    print(
        "taxonomy={taxonomy} operators={operators} stable98={stable98} "
        "stablen={stablen} increment={inc}".format(
            taxonomy=proposal["proposed_taxonomy"],
            operators=delta["operator_count"],
            stable98=impact["stable98_draft"]["complete_records"],
            stablen=impact["stablen_conservative_draft"]["complete_records"],
            inc=impact["increment_vs_stable98"]["records"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
