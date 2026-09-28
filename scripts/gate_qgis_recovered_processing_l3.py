#!/usr/bin/env python3
"""Apply the composed stable101 mapping to recovered QGIS Processing rows."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections import Counter
from pathlib import Path
from typing import Any, Iterable


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def _read_jsonl(path: Path) -> Iterable[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            if line.strip():
                yield json.loads(line)


def _crosswalk_mapping(value: dict[str, Any]) -> dict[str, str]:
    return {
        str(operator).lower(): str(entry["l3_code"])
        for operator, entry in (value.get("entries") or {}).items()
        if isinstance(entry, dict)
        and entry.get("bridge_type") == "l3_bridge"
        and entry.get("status") == "accepted"
        and str(entry.get("l3_code", "")).startswith("L3_")
    }


def _delta_mapping(value: dict[str, Any]) -> dict[str, str]:
    mapping: dict[str, str] = {}
    for field in ("alias_mappings", "restored_l3_mappings"):
        mapping.update(
            {
                str(operator).lower(): str(code)
                for operator, code in (value.get(field) or {}).items()
            }
        )
    return mapping


def _apply_authority_delta(
    mapping: dict[str, str], value: dict[str, Any]
) -> None:
    additions = _delta_mapping(value)
    corrections = value.get("correction_mappings") or {}
    exclusions = value.get("mapping_exclusions") or {}
    fields = [set(additions), set(corrections), set(exclusions)]
    if any(fields[index].intersection(fields[other]) for index in range(3) for other in range(index + 1, 3)):
        raise ValueError("operator appears in multiple mapping delta actions")

    for operator, code in additions.items():
        if operator in mapping and mapping[operator] != code:
            raise ValueError(
                f"mapping conflict for {operator}: {mapping[operator]} != {code}"
            )
        mapping[operator] = code

    for raw_operator, entry in corrections.items():
        operator = str(raw_operator).lower()
        if not isinstance(entry, dict) or "from_l3" not in entry:
            raise ValueError(f"invalid correction mapping for {operator}")
        expected_value = entry["from_l3"]
        expected = None if expected_value is None else str(expected_value)
        replacement = str(entry.get("to_l3") or "")
        if mapping.get(operator) != expected:
            raise ValueError(
                f"correction precondition failed for {operator}: "
                f"{mapping.get(operator)!r} != {expected!r}"
            )
        if not replacement.startswith("L3_"):
            raise ValueError(f"invalid correction target for {operator}")
        mapping[operator] = replacement

    for raw_operator, entry in exclusions.items():
        operator = str(raw_operator).lower()
        if not isinstance(entry, dict):
            raise ValueError(f"invalid mapping exclusion for {operator}")
        expected = str(entry.get("excluded_l3_code") or "")
        if mapping.get(operator) != expected:
            raise ValueError(
                f"exclusion precondition failed for {operator}: "
                f"{mapping.get(operator)!r} != {expected!r}"
            )
        del mapping[operator]


def load_composed_mapping(
    crosswalk_path: Path,
    stable98_delta_path: Path,
    stable101_delta_path: Path,
    *,
    additional_delta_paths: Iterable[Path] = (),
) -> dict[str, str]:
    mapping = {
        **_crosswalk_mapping(_read_json(crosswalk_path)),
        **_delta_mapping(_read_json(stable98_delta_path)),
        **_delta_mapping(_read_json(stable101_delta_path)),
    }
    for path in additional_delta_paths:
        _apply_authority_delta(mapping, _read_json(path))
    return mapping


def load_explicit_mapping_authority(path: Path) -> dict[str, str]:
    value = _read_json(path)
    mapping: dict[str, str] = {}
    for raw_operator, raw_code in value.items():
        operator = str(raw_operator).strip().lower()
        code = str(raw_code).strip()
        if not operator or not code.startswith("L3_") or operator in mapping:
            raise ValueError(f"invalid explicit mapping: {raw_operator!r} -> {raw_code!r}")
        mapping[operator] = code
    if not mapping:
        raise ValueError("invalid explicit mapping: empty authority")
    return mapping


def build_source_snippet(
    source_path: Path,
    call_sites: list[dict[str, Any]],
    *,
    context_lines: int = 2,
) -> str:
    if not source_path.is_file() or not call_sites:
        return ""
    lines = source_path.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    intervals = sorted(
        (
            max(1, int(site["line_start"]) - context_lines),
            min(len(lines), int(site["line_end"]) + context_lines),
        )
        for site in call_sites
    )
    merged: list[list[int]] = []
    for start, end in intervals:
        if merged and start <= merged[-1][1] + 1:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    segments = [
        "\n".join(f"{line_number} | {lines[line_number - 1]}" for line_number in range(start, end + 1))
        for start, end in merged
    ]
    return "\n...\n".join(segments)


def apply_l3_gate(
    row: dict[str, Any],
    mapping: dict[str, str],
    *,
    mapping_authority: str = "stable101_composed_draft_v1",
) -> dict[str, Any]:
    result = dict(row)
    operators = [
        str(value).strip().lower()
        for value in row.get("canonical_operator_ids") or []
        if str(value).strip()
    ]
    unmapped = list(dict.fromkeys(value for value in operators if value not in mapping))
    complete = bool(operators) and not unmapped
    source_snippet = row.get("source_snippet") or build_source_snippet(
        Path(str(row.get("source_path") or "")), row.get("call_sites") or []
    )
    result.update(
        {
            "schema": "gis_recommend.qgis_recovered_processing_l3_gate.v1",
            "operator_ids": operators,
            "ordered_operator_ids": operators,
            "signature_hash": row.get("feature_signature_hash", ""),
            "source_snippet": source_snippet,
            "source_snippet_contains_all_ops": bool(source_snippet) and bool(operators),
            "mapping_complete": complete,
            "unmapped_operator_ids": unmapped,
            "mapped_l3_chain": [mapping[value] for value in operators] if complete else [],
            "action": row.get("structure_action") if complete else "defer_mapping",
            "rule_id": row.get("structure_rule_id") if complete else "defer-mapping-gap-v1",
            "mapping_authority": mapping_authority,
            "training_admission": "not_granted_pending_description_and_dedup",
            "training_row_emitted": False,
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
        }
    )
    return result


def build_gate(
    recovery_path: Path,
    mapping: dict[str, str],
    *,
    mapping_authority: str = "stable101_composed_draft_v1",
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    inputs = list(_read_jsonl(recovery_path))
    rows = [
        apply_l3_gate(row, mapping, mapping_authority=mapping_authority)
        for row in inputs
    ]
    fully_normalized = [
        row for row in rows if row.get("normalization_status") == "fully_normalized"
    ]
    complete = [row for row in fully_normalized if row["mapping_complete"]]
    direct = [row for row in complete if row["action"] == "auto_accept_candidate"]
    summary = {
        "schema": "gis_recommend.qgis_recovered_processing_l3_gate.summary.v1",
        "input_rows": len(rows),
        "fully_normalized_rows": len(fully_normalized),
        "mapping_complete_rows": len(complete),
        "mapping_complete_unique_chains": len(
            {tuple(row["operator_ids"]) for row in complete}
        ),
        "direct_description_ready_rows": len(direct),
        "direct_description_ready_unique_chains": len(
            {tuple(row["operator_ids"]) for row in direct}
        ),
        "action_counts": dict(sorted(Counter(row["action"] for row in rows).items())),
        "top_mapping_gaps": dict(
            Counter(
                operator
                for row in fully_normalized
                for operator in row["unmapped_operator_ids"]
            ).most_common(100)
        ),
        "training_rows_emitted": 0,
        "next_gate": "deterministic description fidelity and four-layer dedup",
    }
    return rows, summary


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def write_outputs(
    rows: list[dict[str, Any]],
    summary: dict[str, Any],
    *,
    inputs: dict[str, Path],
    output_dir: Path,
) -> None:
    manifest_path = output_dir / "l3_gated_manifest_v1.jsonl"
    summary_path = output_dir / "summary_v1.json"
    hash_path = output_dir / "hash_ledger_v1.json"
    _atomic_write(
        manifest_path,
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
            for row in rows
        ),
    )
    _atomic_write(
        summary_path,
        json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    _atomic_write(
        hash_path,
        json.dumps(
            {
                "schema": "gis_recommend.hash_ledger.v1",
                "source_inputs": {
                    name: {"path": str(path), "sha256": _sha256(path)}
                    for name, path in inputs.items()
                },
                "artifacts": {
                    path.name: _sha256(path) for path in (manifest_path, summary_path)
                },
            },
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recovery", type=Path, required=True)
    parser.add_argument("--composed-mapping", type=Path)
    parser.add_argument("--crosswalk", type=Path)
    parser.add_argument("--stable98-delta", type=Path)
    parser.add_argument("--stable101-delta", type=Path)
    parser.add_argument("--additional-delta", type=Path, action="append", default=[])
    parser.add_argument(
        "--mapping-authority", default="stable101_composed_draft_v1"
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    legacy_inputs = (args.crosswalk, args.stable98_delta, args.stable101_delta)
    if args.composed_mapping:
        if any(legacy_inputs) or args.additional_delta:
            parser.error("--composed-mapping cannot be combined with mapping deltas")
        mapping = load_explicit_mapping_authority(args.composed_mapping)
    else:
        if not all(legacy_inputs):
            parser.error(
                "provide --composed-mapping or all of --crosswalk, "
                "--stable98-delta, and --stable101-delta"
            )
        mapping = load_composed_mapping(
            args.crosswalk,
            args.stable98_delta,
            args.stable101_delta,
            additional_delta_paths=args.additional_delta,
        )
    rows, summary = build_gate(
        args.recovery, mapping, mapping_authority=args.mapping_authority
    )
    additional_inputs = {
        f"additional_delta_{index}": path
        for index, path in enumerate(args.additional_delta, start=1)
    }
    mapping_inputs = (
        {"composed_mapping": args.composed_mapping}
        if args.composed_mapping
        else {
            "crosswalk": args.crosswalk,
            "stable98_delta": args.stable98_delta,
            "stable101_delta": args.stable101_delta,
            **additional_inputs,
        }
    )
    write_outputs(
        rows,
        summary,
        inputs={
            "recovery": args.recovery,
            **mapping_inputs,
        },
        output_dir=args.output_dir,
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
