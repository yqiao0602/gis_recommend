#!/usr/bin/env python3
"""Build a non-admitted stable-98 draft and measure QGIS mapping impact."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


def _read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{line_number} must contain a JSON object")
            rows.append(row)
    return rows


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _code_rows(rows: Iterable[dict[str, str]], source: str) -> dict[str, dict[str, str]]:
    result: dict[str, dict[str, str]] = {}
    for row in rows:
        code = str(row.get("l3_code", "")).strip()
        if not code:
            raise ValueError(f"{source} contains a row without l3_code")
        if code in result:
            raise ValueError(f"{source} contains duplicate l3_code {code}")
        result[code] = dict(row)
    return result


def build_extension_proposal(
    *,
    stable_rows: list[dict[str, str]],
    legacy_rows: list[dict[str, str]],
    vocab: dict[str, Any],
    restored_codes: list[str],
) -> dict[str, Any]:
    stable_by_code = _code_rows(stable_rows, "stable hierarchy")
    legacy_by_code = _code_rows(legacy_rows, "legacy hierarchy")
    code_to_id = vocab.get("code_to_id")
    if not isinstance(code_to_id, dict) or not code_to_id:
        raise ValueError("vocabulary must contain a non-empty code_to_id mapping")
    normalized_ids = {str(code): int(token_id) for code, token_id in code_to_id.items()}
    if set(normalized_ids) != set(stable_by_code):
        raise ValueError("stable hierarchy and vocabulary code sets differ")
    if sorted(normalized_ids.values()) != list(range(len(normalized_ids))):
        raise ValueError("existing vocabulary token IDs must be contiguous from zero")

    ordered_restored = list(dict.fromkeys(restored_codes))
    if len(ordered_restored) != len(restored_codes):
        raise ValueError("restored L3 codes must be unique")
    for code in ordered_restored:
        if code in stable_by_code:
            raise ValueError(f"restored L3 code already exists in stable hierarchy: {code}")
        if code not in legacy_by_code:
            raise ValueError(f"restored L3 code is absent from legacy hierarchy: {code}")

    start_id = len(normalized_ids)
    additions = {code: start_id + offset for offset, code in enumerate(ordered_restored)}
    restored_l3 = []
    for code in ordered_restored:
        row = dict(legacy_by_code[code])
        row["proposed_token_id"] = additions[code]
        row["source_taxonomy"] = "legacy350"
        row["taxonomy_admission"] = "not_granted"
        restored_l3.append(row)

    return {
        "schema": "gis_recommend.qgis_stable98_extension_proposal.v1",
        "status": "draft_not_granted",
        "base_taxonomy": "stable94",
        "proposed_taxonomy": f"stable{len(normalized_ids) + len(additions)}",
        "base_class_count": len(normalized_ids),
        "proposed_class_count": len(normalized_ids) + len(additions),
        "existing_code_to_id": dict(sorted(normalized_ids.items(), key=lambda item: item[1])),
        "proposed_code_to_id_additions": additions,
        "restored_l3": restored_l3,
        "existing_token_ids_unchanged": True,
        "taxonomy_admission": "not_granted",
        "training_admission": "not_granted",
    }


def build_mapping_delta(
    adjudications: list[dict[str, Any]],
    *,
    stable_codes: set[str],
    restored_codes: set[str],
) -> dict[str, Any]:
    alias_mappings: dict[str, str] = {}
    restored_mappings: dict[str, str] = {}
    entries: list[dict[str, Any]] = []
    for row in adjudications:
        if row.get("review_decision") != "accepted_mapping_proposal":
            continue
        operator_id = str(row.get("operator_id", "")).strip().lower()
        codes = row.get("candidate_l3_codes")
        if not operator_id or not isinstance(codes, list) or len(codes) != 1:
            raise ValueError("each accepted proposal must have one operator and one L3 code")
        if row.get("taxonomy_admission") != "not_granted":
            raise ValueError(f"{operator_id}: taxonomy admission must remain not_granted")
        if row.get("training_admission") != "not_granted":
            raise ValueError(f"{operator_id}: training admission must remain not_granted")
        code = str(codes[0])
        mapping_kind = row.get("mapping_kind")
        if mapping_kind == "alias_existing_stable94":
            if code not in stable_codes:
                raise ValueError(f"{operator_id}: alias target is absent from stable hierarchy")
            alias_mappings[operator_id] = code
            code_admission = "existing_stable94"
        elif mapping_kind == "restore_old350_l3":
            if code not in restored_codes:
                raise ValueError(f"{operator_id}: restoration target is absent from extension")
            restored_mappings[operator_id] = code
            code_admission = "proposed_legacy350_restoration"
        else:
            raise ValueError(f"{operator_id}: unsupported accepted mapping kind {mapping_kind!r}")
        entries.append(
            {
                "operator_id": operator_id,
                "l3_code": code,
                "mapping_kind": mapping_kind,
                "code_admission": code_admission,
                "review_decision": "accepted_mapping_proposal",
                "taxonomy_admission": "not_granted",
                "training_admission": "not_granted",
            }
        )

    entries.sort(key=lambda item: item["operator_id"])
    return {
        "schema": "gis_recommend.qgis_mapping_authority_delta_draft.v1",
        "status": "draft_not_granted",
        "alias_mappings": dict(sorted(alias_mappings.items())),
        "restored_l3_mappings": dict(sorted(restored_mappings.items())),
        "entries": entries,
        "operator_count": len(entries),
        "taxonomy_admission": "not_granted",
        "training_admission": "not_granted",
    }


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


def _chain_state(ops: list[str], mapping: dict[str, str]) -> tuple[list[str], list[str]]:
    unresolved = list(dict.fromkeys(op for op in ops if op not in mapping))
    sequence = [mapping[op] for op in ops] if not unresolved else []
    return unresolved, sequence


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


def compare_embedded_l3_sequences(
    records: list[dict[str, Any]], baseline_mapping: dict[str, str]
) -> dict[str, Any]:
    embedded = {
        index
        for index, record in enumerate(records)
        if isinstance(record.get("optional_l3_sequence"), list)
        and bool(record["optional_l3_sequence"])
    }
    strict = {
        index
        for index, record in enumerate(records)
        if record.get("qgis_ops")
        and all(str(op).lower() in baseline_mapping for op in record["qgis_ops"])
    }
    embedded_only = embedded - strict
    blocker_counts = Counter(
        str(op).lower()
        for index in embedded_only
        for op in records[index].get("qgis_ops", [])
        if str(op).lower() not in baseline_mapping
    )
    return {
        "embedded_optional_l3_records": len(embedded),
        "strict_baseline_complete_records": len(strict),
        "overlap_records": len(embedded & strict),
        "embedded_only_records": len(embedded_only),
        "strict_only_records": len(strict - embedded),
        "embedded_only_unresolved_operator_counts": dict(
            sorted(blocker_counts.items(), key=lambda item: (-item[1], item[0]))
        ),
        "interpretation": (
            "Embedded optional_l3_sequence is legacy data, not the strict audited "
            "crosswalk authority; embedded-only rows remain excluded from strict counts."
        ),
    }


def analyze_mapping_impact(
    records: list[dict[str, Any]],
    *,
    baseline_mapping: dict[str, str],
    alias_mappings: dict[str, str],
    restored_mappings: dict[str, str],
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    alias_mapping = {**baseline_mapping, **alias_mappings}
    stable98_mapping = {**alias_mapping, **restored_mappings}
    proposed_ops = set(alias_mappings) | set(restored_mappings)
    details: list[dict[str, Any]] = []
    alias_new_records = 0
    alias_new_chains: set[tuple[str, ...]] = set()
    restore_new_records = 0
    restore_new_chains: set[tuple[str, ...]] = set()
    affected_chains: set[tuple[str, ...]] = set()
    still_incomplete_chains: set[tuple[str, ...]] = set()

    for record_index, record in enumerate(records, start=1):
        ops = [str(op).lower() for op in record.get("qgis_ops", [])]
        if not ops or not proposed_ops.intersection(ops):
            continue
        chain = tuple(ops)
        affected_chains.add(chain)
        baseline_unresolved, _ = _chain_state(ops, baseline_mapping)
        alias_unresolved, _ = _chain_state(ops, alias_mapping)
        stable98_unresolved, stable98_sequence = _chain_state(ops, stable98_mapping)
        if baseline_unresolved and not alias_unresolved:
            impact_stage = "alias_only"
            alias_new_records += 1
            alias_new_chains.add(chain)
        elif alias_unresolved and not stable98_unresolved:
            impact_stage = "stable98_restoration"
            restore_new_records += 1
            restore_new_chains.add(chain)
        elif stable98_unresolved:
            impact_stage = "still_incomplete"
            still_incomplete_chains.add(chain)
        else:
            impact_stage = "already_complete_baseline"

        record_identity = json.dumps(record, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        details.append(
            {
                "record_index": record_index,
                "record_sha256": hashlib.sha256(record_identity.encode("utf-8")).hexdigest(),
                "task_text": record.get("task_text", ""),
                "qgis_ops": ops,
                "proposal_ops_present": sorted(proposed_ops.intersection(ops)),
                "baseline_unresolved_ops": baseline_unresolved,
                "alias_only_unresolved_ops": alias_unresolved,
                "stable98_unresolved_ops": stable98_unresolved,
                "proposed_l3_sequence": stable98_sequence,
                "impact_stage": impact_stage,
                "taxonomy_admission": "not_granted",
                "training_admission": "not_granted",
            }
        )

    summary = {
        "total_records": len(records),
        "total_unique_chains": len(
            {tuple(str(op).lower() for op in record.get("qgis_ops", [])) for record in records}
        ),
        "baseline": _complete_stats(records, baseline_mapping),
        "alias_only": _complete_stats(records, alias_mapping),
        "stable98_draft": _complete_stats(records, stable98_mapping),
        "newly_complete_by_alias": {
            "records": alias_new_records,
            "unique_chains": len(alias_new_chains),
        },
        "newly_complete_by_restored_l3": {
            "records": restore_new_records,
            "unique_chains": len(restore_new_chains),
        },
        "affected_records": len(details),
        "affected_unique_chains": len(affected_chains),
        "affected_still_incomplete_records": sum(
            row["impact_stage"] == "still_incomplete" for row in details
        ),
        "affected_still_incomplete_unique_chains": len(still_incomplete_chains),
    }
    return summary, details


def _operator_impact(
    details: list[dict[str, Any]], operator_ids: Iterable[str]
) -> dict[str, dict[str, int]]:
    result: dict[str, dict[str, int]] = {}
    for operator_id in sorted(operator_ids):
        matching = [row for row in details if operator_id in row["qgis_ops"]]
        result[operator_id] = {
            "record_count": len(matching),
            "occurrence_count": sum(row["qgis_ops"].count(operator_id) for row in matching),
            "unique_chain_count": len({tuple(row["qgis_ops"]) for row in matching}),
            "newly_complete_record_count": sum(
                row["impact_stage"] in {"alias_only", "stable98_restoration"}
                for row in matching
            ),
        }
    return result


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def _write_json(path: Path, value: Any) -> None:
    _atomic_write_text(path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stable-hierarchy", required=True, type=Path)
    parser.add_argument("--legacy-hierarchy", required=True, type=Path)
    parser.add_argument("--vocab", required=True, type=Path)
    parser.add_argument("--crosswalk", required=True, type=Path)
    parser.add_argument("--adjudications", required=True, type=Path)
    parser.add_argument("--chain-dataset", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()

    stable_rows = _read_csv(args.stable_hierarchy)
    legacy_rows = _read_csv(args.legacy_hierarchy)
    vocab = json.loads(args.vocab.read_text(encoding="utf-8"))
    crosswalk = json.loads(args.crosswalk.read_text(encoding="utf-8"))
    adjudications = _read_jsonl(args.adjudications)
    records = _read_jsonl(args.chain_dataset)

    accepted_restored_codes = {
        str(row["candidate_l3_codes"][0])
        for row in adjudications
        if row.get("review_decision") == "accepted_mapping_proposal"
        and row.get("mapping_kind") == "restore_old350_l3"
    }
    restored_codes = [
        row["l3_code"] for row in legacy_rows if row.get("l3_code") in accepted_restored_codes
    ]
    if set(restored_codes) != accepted_restored_codes:
        raise ValueError("not all accepted legacy restoration codes exist in legacy hierarchy")

    extension = build_extension_proposal(
        stable_rows=stable_rows,
        legacy_rows=legacy_rows,
        vocab=vocab,
        restored_codes=restored_codes,
    )
    stable_codes = {row["l3_code"] for row in stable_rows}
    delta = build_mapping_delta(
        adjudications,
        stable_codes=stable_codes,
        restored_codes=set(restored_codes),
    )
    if extension["base_class_count"] != 94 or extension["proposed_class_count"] != 98:
        raise ValueError("real-data draft must extend exactly stable-94 to stable-98")
    if len(delta["alias_mappings"]) != 4 or len(delta["restored_l3_mappings"]) != 5:
        raise ValueError("real-data draft must contain four aliases and five restored mappings")

    impact, details = analyze_mapping_impact(
        records,
        baseline_mapping=mapping_from_crosswalk(crosswalk),
        alias_mappings=delta["alias_mappings"],
        restored_mappings=delta["restored_l3_mappings"],
    )
    proposal_date = max(str(row.get("reviewed_at", "")) for row in adjudications)
    input_paths = {
        "stable_hierarchy": args.stable_hierarchy,
        "legacy_hierarchy": args.legacy_hierarchy,
        "vocab": args.vocab,
        "crosswalk": args.crosswalk,
        "adjudications": args.adjudications,
        "chain_dataset": args.chain_dataset,
    }
    input_sha256 = {name: _sha256(path) for name, path in input_paths.items()}
    extension["proposal_date"] = proposal_date
    extension["input_sha256"] = input_sha256
    delta["proposal_date"] = proposal_date
    delta["input_sha256"] = input_sha256

    extension_path = args.output_dir / "stable98_extension_proposal_v1.json"
    delta_path = args.output_dir / "qgis_mapping_authority_stable98_delta_draft_v1.json"
    records_path = args.output_dir / "p0_mapping_impact_records_v1.jsonl"
    summary_path = args.output_dir / "p0_mapping_impact_stable98_v1.json"
    _write_json(extension_path, extension)
    _write_json(delta_path, delta)
    _atomic_write_text(
        records_path,
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in details),
    )

    impact.update(
        {
            "schema": "gis_recommend.qgis_stable98_mapping_impact.v1",
            "status": "draft_not_granted",
            "proposal_date": proposal_date,
            "base_class_count": extension["base_class_count"],
            "proposed_class_count": extension["proposed_class_count"],
            "alias_operator_count": len(delta["alias_mappings"]),
            "restored_operator_count": len(delta["restored_l3_mappings"]),
            "restored_l3_count": len(restored_codes),
            "operator_impact": _operator_impact(details, set(delta["alias_mappings"]) | set(delta["restored_l3_mappings"])),
            "remaining_blocker_counts": dict(
                sorted(
                    Counter(
                        operator_id
                        for row in details
                        if row["impact_stage"] == "still_incomplete"
                        for operator_id in row["stable98_unresolved_ops"]
                    ).items(),
                    key=lambda item: (-item[1], item[0]),
                )
            ),
            "embedded_l3_comparison": compare_embedded_l3_sequences(
                records, mapping_from_crosswalk(crosswalk)
            ),
            "input_sha256": input_sha256,
            "artifact_sha256": {
                "extension_proposal": _sha256(extension_path),
                "mapping_delta": _sha256(delta_path),
                "impact_records": _sha256(records_path),
            },
            "taxonomy_admission": "not_granted",
            "training_admission": "not_granted",
        }
    )
    _write_json(summary_path, impact)
    print(
        f"records={impact['total_records']} affected={impact['affected_records']} "
        f"baseline_complete={impact['baseline']['complete_records']} "
        f"alias_complete={impact['alias_only']['complete_records']} "
        f"stable98_complete={impact['stable98_draft']['complete_records']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
