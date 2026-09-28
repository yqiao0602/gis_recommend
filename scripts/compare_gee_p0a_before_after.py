#!/usr/bin/env python3
"""Compare frozen GEE evidence with an isolated extractor rerun."""

from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path
from typing import Any

_NATIVE_JS_NAMESPACES = frozenset({
    "Array", "ArrayBuffer", "BigInt", "Boolean", "console", "DataView", "Date", "Error",
    "Intl", "JSON", "Math", "Number", "Object", "Promise", "Proxy", "Reflect", "RegExp",
    "Set", "String", "Symbol", "WeakMap", "WeakSet",
})


def _load(directory: Path) -> dict[str, dict[str, Any]]:
    result = {}
    for path in sorted(directory.glob("*.json")):
        value = json.loads(path.read_text(encoding="utf-8"))
        result[value["source_path"]] = value
    return result


def _raw_layer(value: dict[str, Any], layer: str) -> list[str | None]:
    return [value["ordered_calls"][index]["raw_callee"] for index in value[layer]]


def build_report(before_dir: Path, after_dir: Path) -> dict[str, Any]:
    before = _load(before_dir)
    after = _load(after_dir)
    if not set(after).issubset(before):
        raise ValueError("after source identities are not contained in before evidence")
    before_versions = {value["extractor_version"] for value in before.values()}
    after_versions = {value["extractor_version"] for value in after.values()}
    if len(before_versions) != 1 or len(after_versions) != 1:
        raise ValueError("before and after must each have one extractor version")
    rows = []
    for source_path in sorted(after):
        old = before[source_path]
        new = after[source_path]
        old_core = _raw_layer(old, "core_operator_chain")
        new_core = _raw_layer(new, "core_operator_chain")
        old_io = _raw_layer(old, "io_contract")
        new_io = _raw_layer(new, "io_contract")
        old_presentation = _raw_layer(old, "presentation_actions")
        new_presentation = _raw_layer(new, "presentation_actions")
        old_native = [
            call["raw_callee"]
            for call in old["ordered_calls"]
            if isinstance(call["raw_callee"], str)
            and call["raw_callee"].split(".", 1)[0] in _NATIVE_JS_NAMESPACES
            and "." in call["raw_callee"]
        ]
        new_native = [
            call["raw_callee"]
            for call in new["ordered_calls"]
            if call["resolution"] == "native_js_namespace"
        ]
        old_native_counter = collections.Counter(old_native)
        new_native_counter = collections.Counter(new_native)
        existing_native_reclassified = sum((new_native_counter & old_native_counter).values())
        newly_recovered_native = sum((new_native_counter - old_native_counter).values())
        rows.append(
            {
                "source_path": source_path,
                "old_extractor_version": old["extractor_version"],
                "new_extractor_version": new["extractor_version"],
                "old_call_count": len(old["ordered_calls"]),
                "new_call_count": len(new["ordered_calls"]),
                "old_core_count": len(old_core),
                "new_core_count": len(new_core),
                "old_io_count": len(old_io),
                "new_io_count": len(new_io),
                "old_presentation_count": len(old_presentation),
                "new_presentation_count": len(new_presentation),
                "recovered_core_calls": list((collections.Counter(new_core) - collections.Counter(old_core)).elements()),
                "recovered_io_calls": list((collections.Counter(new_io) - collections.Counter(old_io)).elements()),
                "recovered_presentation_calls": list(
                    (collections.Counter(new_presentation) - collections.Counter(old_presentation)).elements()
                ),
                "new_quality_flags": new["quality_flags"],
                "new_unresolved_count": len(new["unresolved_calls"]),
                "old_native_namespace_count": len(old_native),
                "new_native_namespace_count": len(new_native),
                "native_namespace_calls": new_native,
                "existing_native_reclassified_count": existing_native_reclassified,
                "newly_recovered_native_count": newly_recovered_native,
            }
        )
    return {
        "schema": "gis_recommend.gee_extractor_p0a_before_after.v1",
        "training_admission": "not_granted",
        "scope": "variable and static object-property function bindings only",
        "before_extractor_version": next(iter(before_versions)),
        "after_extractor_version": next(iter(after_versions)),
    "record_count": len(rows),
    "old_native_namespace_total": sum(row["old_native_namespace_count"] for row in rows),
    "new_native_namespace_total": sum(row["new_native_namespace_count"] for row in rows),
    "existing_native_reclassified_total": sum(row["existing_native_reclassified_count"] for row in rows),
    "newly_recovered_native_total": sum(row["newly_recovered_native_count"] for row in rows),
        "records": rows,
    }


def write_report(report: dict[str, Any], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "before_after.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    lines = [
        "# GEE Extractor v2 Isolated Before/After Diagnostic",
        "",
        "- Scope: variable-bound and static object-property function bindings.",
        f"- Before: {report['before_extractor_version']}.",
        f"- After: {report['after_extractor_version']}.",
        f"- Records: {report['record_count']}.",
        f"- Native namespace calls before/after: {report['old_native_namespace_total']}/{report['new_native_namespace_total']}.",
        f"- Existing native calls reclassified: {report['existing_native_reclassified_total']}; newly recovered native calls are reported separately.",
        "- Training admission: not_granted.",
        "",
        "| Source | Calls before/after | Core before/after | Native before/after | I/O before/after | Recovered core |",
        "| --- | ---: | ---: | ---: | ---: | --- |",
    ]
    for row in report["records"]:
        recovered = ", ".join(row["recovered_core_calls"]) or "-"
        lines.append(
            f"| {Path(row['source_path']).name} | {row['old_call_count']}/{row['new_call_count']} | "
            f"{row['old_core_count']}/{row['new_core_count']} | "
            f"{row['old_native_namespace_count']}/{row['new_native_namespace_count']} | "
            f"{row['old_io_count']}/{row['new_io_count']} | {recovered} |"
        )
    lines.extend(["", "Diagnostic evidence only; this does not populate human review fields or authorize training data."])
    (output_dir / "before_after.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--before-dir", type=Path, required=True)
    parser.add_argument("--after-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    report = build_report(args.before_dir, args.after_dir)
    write_report(report, args.output_dir)
    print(json.dumps({
        "record_count": report["record_count"],
        "recovered_core_total": sum(len(row["recovered_core_calls"]) for row in report["records"]),
        "recovered_io_total": sum(len(row["recovered_io_calls"]) for row in report["records"]),
    }, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
