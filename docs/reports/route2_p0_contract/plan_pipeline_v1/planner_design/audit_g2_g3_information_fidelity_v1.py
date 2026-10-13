#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Fail-closed, CPU-only audit of G2 -> G3 information fidelity.

The audit compares rows by ``source_row_id``.  It never constructs a missing
G3 artifact, loads a model, trains, or treats aggregate model metrics as
row-level provenance.  A G3 file without an ID sidecar is deliberately blocked
because the smoke formatter historically omitted source_row_id.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Iterable

AUDIT_VERSION = "g2-g3-information-fidelity-v1"
EXPECTED_G2_KEYS = {"source_row_id", "task", "stages", "repetition_groups"}
EXPECTED_G3_KEYS = {"task", "target"}
HINTS = {"per_band", "per_class", "per_year", "per_feature", "generic_each", "unspecified"}

# These are deliberately conservative lexical diagnostics.  They are not a
# semantic parser and are reported as inventory evidence, not proof of meaning.
CONCEPT_PATTERNS = {
    "index_ndvi": r"\bndvi\b",
    "index_ndwi": r"\bndwi\b",
    "index_ndbi": r"\bndbi\b",
    "index_evi": r"\bevi\b",
    "sensor_sentinel2": r"\bsentinel(?:[- ]?2|[- ]?2a|[- ]?2b)\b",
    "sensor_landsat": r"\blandsat(?:[- ]?[0-9]+)?\b",
    "time_monthly": r"\bmonthly\b|\bmonth(?:ly|s)?\b",
    "time_annual": r"\bannual(?:ly)?\b|\byearly\b|\bper year\b",
    "stat_mean": r"\bmean(?:\s+value)?\b|\baverage\b",
    "stat_median": r"\bmedian\b",
    "task_classification": r"\bclassif(?:y|ication|ied)\b|\bclassifier\b",
    "task_regression": r"\bregression\b|\bregress\b",
    "output_export": r"\bexport\b|\boutput\b|\bsave\b",
    "threshold": r"\bthreshold\b|\bgreater than\b|\bless than\b|\b>=?\b|\b<=?\b",
}
COMPILED_CONCEPTS = {k: re.compile(v, re.I) for k, v in CONCEPT_PATTERNS.items()}


def canonical_json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def iter_jsonl(path: Path, max_rows: int = 0) -> Iterable[tuple[int, dict[str, Any]]]:
    with path.open(encoding="utf-8") as handle:
        for line_no, line in enumerate(handle, 1):
            if max_rows and line_no > max_rows:
                break
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_no}: JSONL row is not an object")
            yield line_no, value


def file_inventory(path: Path, max_rows: int = 0) -> dict[str, Any]:
    result: dict[str, Any] = {
        "path": str(path),
        "exists": path.is_file(),
        "sha256": None,
        "rows": 0,
        "malformed": [],
        "keys": Counter(),
    }
    if not path.is_file():
        return result
    result["sha256"] = sha256_file(path)
    try:
        for line_no, row in iter_jsonl(path, max_rows=max_rows):
            result["rows"] += 1
            for key in row:
                result["keys"][key] += 1
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        result["malformed"].append(str(exc))
    result["keys"] = dict(sorted(result["keys"].items()))
    return result


def source_id(row: dict[str, Any]) -> Any:
    return row.get("source_row_id", row.get("source_id"))


def normalize_stages(value: Any) -> list[dict[str, Any]] | None:
    if not isinstance(value, list):
        return None
    normalized = []
    for stage in value:
        if not isinstance(stage, dict) or "family" not in stage:
            return None
        try:
            repeat = int(stage.get("repeat", 1))
        except (TypeError, ValueError):
            return None
        normalized.append({
            "seq": stage.get("seq"),
            "family": str(stage.get("family")),
            "repeat": repeat,
        })
    return normalized


def normalize_groups(value: Any) -> list[dict[str, Any]] | None:
    if not isinstance(value, list):
        return None
    normalized = []
    for group in value:
        if not isinstance(group, dict):
            return None
        hints = group.get("iteration_hint", [])
        if isinstance(hints, str):
            hints = [hints]
        if not isinstance(hints, list) or any(str(h) not in HINTS for h in hints):
            return None
        try:
            repeat = int(group.get("repeat", 1))
        except (TypeError, ValueError):
            return None
        normalized.append({
            "stage_seq": group.get("stage_seq"),
            "family": str(group.get("family", "")),
            "repeat": repeat,
            "iteration_hint": sorted(str(h) for h in hints),
        })
    return normalized


def parse_g3_target(value: Any) -> tuple[dict[str, Any] | None, str | None]:
    if isinstance(value, dict):
        return value, None
    if not isinstance(value, str) or not value.strip():
        return None, "target_empty_or_non_string"
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as exc:
        return None, f"target_json_error:{exc.msg}"
    if not isinstance(parsed, dict):
        return None, "target_json_not_object"
    return parsed, None


def semantic_inventory(*parts: Any) -> dict[str, bool]:
    text = "\n".join(str(part) for part in parts if part is not None)
    return {name: bool(pattern.search(text)) for name, pattern in COMPILED_CONCEPTS.items()}


def expanded_families(stages: list[dict[str, Any]] | None) -> list[str] | None:
    if stages is None:
        return None
    result: list[str] = []
    for stage in stages:
        repeat = stage["repeat"]
        if repeat < 1:
            return None
        result.extend([stage["family"]] * repeat)
    return result


def compare_structure(g2: dict[str, Any], g3_target: dict[str, Any] | None) -> dict[str, Any]:
    if g3_target is None:
        return {"status": "unparseable", "reason": "target_unavailable"}
    g2_stages = normalize_stages(g2.get("stages"))
    g2_groups = normalize_groups(g2.get("repetition_groups", []))
    g3_stages = normalize_stages(g3_target.get("stages"))
    g3_groups = normalize_groups(g3_target.get("repetition_groups", []))
    if g2_stages is None or g2_groups is None:
        return {"status": "invalid_g2_schema"}
    if g3_stages is None or g3_groups is None:
        return {"status": "missing_or_invalid_g3_structure"}
    stage_equal = g2_stages == g3_stages
    group_equal = g2_groups == g3_groups
    return {
        "status": "retained" if stage_equal and group_equal else "changed",
        "stages_equal": stage_equal,
        "repetition_groups_equal": group_equal,
        "g2_stage_count": len(g2_stages),
        "g3_stage_count": len(g3_stages),
        "g2_expanded_length": len(expanded_families(g2_stages) or []),
        "g3_expanded_length": len(expanded_families(g3_stages) or []),
        "g2_hint_count": sum(len(g["iteration_hint"]) for g in g2_groups),
        "g3_hint_count": sum(len(g["iteration_hint"]) for g in g3_groups),
        "approved_g2_annotations_omitted": [
            key for key in ("total_iterations", "stage_count", "confirmed_dimensions",
                            "per_band_rule_v3_1", "per_class_rule_v2")
            if key in g2 and key not in g3_target
        ],
    }


def compare_semantics(g2: dict[str, Any], g3_row: dict[str, Any], target: Any) -> dict[str, Any]:
    g2_inv = semantic_inventory(g2.get("task"), g2.get("confirmed_dimensions"),
                                g2.get("repetition_groups"))
    g3_inv = semantic_inventory(g3_row.get("task"), g3_row.get("context"), target,
                                g3_row.get("rendered_plan"))
    fields = {}
    for name in sorted(g2_inv):
        if g2_inv[name] and g3_inv[name]:
            status = "G2_and_G3_retained"
        elif g2_inv[name] and not g3_inv[name]:
            status = "G2_to_G3_lost"
        elif not g2_inv[name]:
            status = "G2_absent"
        else:
            status = "undetermined"
        fields[name] = {"g2": g2_inv[name], "g3": g3_inv[name], "status": status}
    return fields


def load_sidecar(path: Path | None, max_rows: int = 0) -> dict[tuple[str | None, int], dict[str, Any]]:
    if path is None:
        return {}
    result: dict[tuple[str | None, int], dict[str, Any]] = {}
    for line_no, row in iter_jsonl(path, max_rows=max_rows):
        # A sidecar may cover one file (no path field) or several files.  When
        # several files are audited, path-qualified records prevent local line
        # numbers from colliding across train/dev/test files.
        side_path = row.get("g3_path", row.get("path"))
        result[(str(side_path) if side_path is not None else None, line_no)] = row
    return result


def load_split_manifest(path: Path, max_rows: int = 0) -> dict[Any, str]:
    """Load a small JSON/JSONL source_row_id -> split manifest."""
    if path.suffix.lower() == ".jsonl":
        rows = [row for _, row in iter_jsonl(path, max_rows=max_rows)]
    else:
        value = json.loads(path.read_text(encoding="utf-8"))
        rows = value if isinstance(value, list) else value.get("rows", value.get("splits", []))
        if isinstance(rows, dict):
            return rows
    result = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("split manifest row is not an object")
        sid = source_id(row)
        split = row.get("split")
        if sid is None or split not in {"train", "dev", "val", "test"}:
            raise ValueError("split manifest requires source_row_id and valid split")
        if sid in result and result[sid] != split:
            raise ValueError(f"conflicting split manifest entries for {sid}")
        result[sid] = split
    return result


def discover_g3(path: Path) -> list[Path]:
    if path.is_file():
        return [path]
    if not path.is_dir():
        return []
    # Narrow allowlist: never recursively scan a corpus for something named g3.
    names = (
        "planner_v2_train.jsonl", "planner_v2_dev.jsonl", "planner_v2_test.jsonl",
        "planner_v2_test_locked.jsonl", "g3_train.jsonl", "g3_dev.jsonl", "g3_test.jsonl",
    )
    return [path / name for name in names if (path / name).is_file()]


def make_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--g2", type=Path, required=True)
    parser.add_argument("--g3", type=Path, action="append", required=True,
                        help="G3 JSONL or an allowlisted directory; repeatable")
    parser.add_argument("--g3-sidecar", type=Path,
                        help="JSONL sidecar aligned by non-empty G3 row number")
    parser.add_argument("--split-manifest", type=Path)
    parser.add_argument("--formatter-manifest", type=Path)
    parser.add_argument("--tokenizer", type=Path,
                        help="Optional local tokenizer path; no download is attempted")
    parser.add_argument("--max-len", type=int, default=1024)
    parser.add_argument("--out-dir", type=Path, required=True)
    parser.add_argument("--max-rows", type=int, default=0)
    return parser


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
                    encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    args = make_parser().parse_args(argv)
    if not isinstance(args.g3, list):
        raise ValueError("at least one --g3 path is required")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    g3_paths = []
    for supplied in args.g3:
        g3_paths.extend(discover_g3(supplied))
    # De-duplicate while retaining CLI order.
    g3_paths = list(dict.fromkeys(g3_paths))
    inventory = {
        "audit_version": AUDIT_VERSION,
        "inputs": {
            "g2": file_inventory(args.g2, args.max_rows),
            "g3": [file_inventory(path, args.max_rows) for path in g3_paths],
            "g3_sidecar": file_inventory(args.g3_sidecar, args.max_rows) if args.g3_sidecar else None,
            "split_manifest": file_inventory(args.split_manifest, args.max_rows) if args.split_manifest else None,
            "formatter_manifest": file_inventory(args.formatter_manifest, args.max_rows) if args.formatter_manifest else None,
        },
        "policy": {
            "training_rows_emitted": 0,
            "training_admission": "not_granted",
            "model_loaded": False,
            "large_data_loaded": False,
            "locked_test_modified": False,
        },
    }
    write_json(args.out_dir / "artifact_manifest.json", inventory)

    blockers = []
    if not args.g2.is_file():
        blockers.append("g2_artifact_absent")
    if not g3_paths:
        blockers.append("g3_artifacts_absent")
    direct_g3_ids = False
    if not args.g3_sidecar:
        try:
            direct_g3_ids = all(
                source_id(row) is not None
                for path in g3_paths
                for _, row in iter_jsonl(path, args.max_rows)
            )
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError):
            direct_g3_ids = False
    if g3_paths and args.g3_sidecar is None and not direct_g3_ids:
        blockers.append("g3_source_row_sidecar_absent")
    if args.g3_sidecar is not None and not args.g3_sidecar.is_file():
        blockers.append("g3_source_row_sidecar_absent")
    if args.split_manifest is None or not args.split_manifest.is_file():
        blockers.append("split_manifest_absent")
    if args.formatter_manifest is None or not args.formatter_manifest.is_file():
        blockers.append("formatter_manifest_absent")
    if args.max_len <= 0:
        blockers.append("invalid_max_len")

    if blockers:
        summary = {
            "audit_version": AUDIT_VERSION,
            "status": "blocked",
            "admission": "not_granted",
            "blockers": sorted(set(blockers)),
            "scored_rows": 0,
            "gates": {name: "blocked" for name in ("L1_provenance", "L2_structural",
                                                       "L3_semantic", "L4_serialization")},
            "policy": inventory["policy"],
        }
        write_json(args.out_dir / "summary.json", summary)
        (args.out_dir / "row_ledger.jsonl").write_text("", encoding="utf-8")
        (args.out_dir / "counterexamples.jsonl").write_text("", encoding="utf-8")
        (args.out_dir / "report.md").write_text(
            "# G2→G3 Information Fidelity Audit\n\n"
            "**Status: BLOCKED**\n\n"
            "No fidelity score is valid until all required artifacts and manifests "
            "are supplied.\n\n"
            + "\n".join(f"- `{item}`" for item in sorted(set(blockers))) + "\n",
            encoding="utf-8",
        )
        return 2

    g2_rows = {}
    g2_errors = []
    for line_no, row in iter_jsonl(args.g2, args.max_rows):
        sid = source_id(row)
        if sid is None:
            g2_errors.append({"line": line_no, "reason": "missing_source_row_id"})
        elif sid in g2_rows:
            g2_errors.append({"line": line_no, "source_row_id": sid, "reason": "duplicate_g2_id"})
        else:
            g2_rows[sid] = {"line": line_no, "row": row}

    sidecar = load_sidecar(args.g3_sidecar, args.max_rows)
    split_manifest = {}
    try:
        split_manifest = load_split_manifest(args.split_manifest, args.max_rows)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        blockers.append(f"split_manifest_invalid:{exc}")
    if blockers:
        summary = {
            "audit_version": AUDIT_VERSION,
            "status": "blocked",
            "admission": "not_granted",
            "blockers": sorted(set(blockers)),
            "scored_rows": 0,
            "gates": {name: "blocked" for name in ("L1_provenance", "L2_structural",
                                                       "L3_semantic", "L4_serialization")},
            "policy": inventory["policy"],
        }
        write_json(args.out_dir / "summary.json", summary)
        (args.out_dir / "row_ledger.jsonl").write_text("", encoding="utf-8")
        (args.out_dir / "counterexamples.jsonl").write_text("", encoding="utf-8")
        (args.out_dir / "report.md").write_text(
            "# G2→G3 Information Fidelity Audit\n\n"
            "**Status: BLOCKED**\n\n"
            "No fidelity score is valid until all required artifacts and manifests "
            "are supplied.\n\n"
            + "\n".join(f"- `{item}`" for item in sorted(set(blockers))) + "\n",
            encoding="utf-8",
        )
        return 2
    ledger = []
    counters = Counter()
    target_collision = Counter()
    task_target_collision = Counter()
    g3_seen = set()
    for g3_path in g3_paths:
        for local_no, g3 in iter_jsonl(g3_path, args.max_rows):
            global_key = (str(g3_path), local_no)
            side = sidecar.get((str(g3_path), local_no)) or sidecar.get((None, local_no), {})
            sid = source_id(g3)
            if sid is None:
                sid = source_id(side)
            split_value = side.get("split", g3.get("split"))
            entry = {
                "g3_path": str(g3_path),
                "g3_line": local_no,
                "source_row_id": sid,
                "split": split_value,
                "task_sha256": hashlib.sha256(str(g3.get("task", "")).encode("utf-8")).hexdigest(),
                "reasons": [],
            }
            if sid is None:
                entry["reasons"].append("missing_source_row_id")
                counters["missing_g3_id"] += 1
                ledger.append(entry)
                continue
            if sid in g3_seen:
                entry["reasons"].append("duplicate_g3_id")
                counters["duplicate_g3_id"] += 1
            g3_seen.add(sid)
            g2_info = g2_rows.get(sid)
            if g2_info is None:
                entry["reasons"].append("unknown_source_row_id")
                counters["unknown_g3_id"] += 1
                ledger.append(entry)
                continue
            g2 = g2_info["row"]
            target, target_error = parse_g3_target(g3.get("target"))
            if sid in split_manifest and split_value and split_manifest[sid] != split_value:
                entry["reasons"].append("split_manifest_mismatch")
                counters["split_manifest_mismatch"] += 1
            if sid not in split_manifest:
                entry["reasons"].append("source_id_missing_from_split_manifest")
                counters["source_id_missing_from_split_manifest"] += 1
            structural = compare_structure(g2, target)
            semantic = compare_semantics(g2, g3, target if target is not None else g3.get("target"))
            task_equal = g2.get("task") == g3.get("task")
            if not task_equal:
                entry["reasons"].append("task_mismatch")
                counters["task_mismatch"] += 1
            if target_error:
                entry["reasons"].append(target_error)
                counters["target_parse_error"] += 1
            if structural.get("status") != "retained":
                counters[f"structural_{structural.get('status', 'unknown')}"] += 1
                entry["reasons"].append("structural_not_retained")
            for field in semantic.values():
                counters[field["status"]] += 1
            target_key = canonical_json(target) if target is not None else "<unparseable>"
            target_collision[target_key] += 1
            task_target_collision[canonical_json([g3.get("task"), target_key])] += 1
            entry.update({
                "g2_line": g2_info["line"],
                "task_equal": task_equal,
                "target_sha256": hashlib.sha256(target_key.encode("utf-8")).hexdigest(),
                "target_error": target_error,
                "structural": structural,
                "semantic": semantic,
                "g2_task_sha256": hashlib.sha256(str(g2.get("task", "")).encode("utf-8")).hexdigest(),
            })
            ledger.append(entry)

    for count in target_collision.values():
        if count > 1:
            counters["target_collision_rows"] += count
    for count in task_target_collision.values():
        if count > 1:
            counters["task_target_collision_rows"] += count

    counters["g2_rows"] = len(g2_rows)
    counters["g3_rows"] = len(ledger)
    counters["g2_ids_not_seen_in_g3"] = len(set(g2_rows) - g3_seen)
    counters["g3_ids_not_in_g2"] = sum(1 for row in ledger if "unknown_source_row_id" in row["reasons"])
    l1_ok = not g2_errors and not counters["missing_g3_id"] and not counters["duplicate_g3_id"] \
        and not counters["unknown_g3_id"] and not counters["task_mismatch"] \
        and not counters["split_manifest_mismatch"] \
        and not counters["source_id_missing_from_split_manifest"] \
        and counters["g2_ids_not_seen_in_g3"] == 0
    l2_ok = l1_ok and counters["structural_changed"] == 0 and counters["structural_unparseable"] == 0 \
        and counters["structural_missing_or_invalid_g3_structure"] == 0
    l3_status = "not_evaluable" if not l1_ok else "diagnostic"
    l4_status = "not_evaluable" if not args.tokenizer else "diagnostic"
    summary = {
        "audit_version": AUDIT_VERSION,
        "status": "pass" if l1_ok and l2_ok else "fail",
        "admission": "not_granted",
        "blockers": ["g2_schema_errors"] if g2_errors else [],
        "counts": dict(counters),
        "gates": {
            "L1_provenance": "pass" if l1_ok else "fail",
            "L2_structural": "pass" if l2_ok else "fail",
            "L3_semantic": l3_status,
            "L4_serialization": l4_status,
        },
        "g2_schema_errors": g2_errors[:20],
        "policy": inventory["policy"],
    }
    write_json(args.out_dir / "summary.json", summary)
    with (args.out_dir / "row_ledger.jsonl").open("w", encoding="utf-8") as handle:
        for row in ledger:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    with (args.out_dir / "counterexamples.jsonl").open("w", encoding="utf-8") as handle:
        for row in ledger:
            if row.get("reasons"):
                handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")
    write_json(args.out_dir / "collision_summary.json", {
        "target_collision_classes": sum(1 for n in target_collision.values() if n > 1),
        "task_target_collision_classes": sum(1 for n in task_target_collision.values() if n > 1),
        "target_collision_top": target_collision.most_common(20),
        "task_target_collision_top": task_target_collision.most_common(20),
    })
    (args.out_dir / "report.md").write_text(
        "# G2→G3 Information Fidelity Audit\n\n"
        f"**Status: {summary['status'].upper()}**\n\n"
        "L1 provenance is the hard gate; L3/L4 are diagnostic/not-evaluable "
        "until their declared artifacts are supplied.\n\n"
        f"- G2 rows: {len(g2_rows)}\n"
        f"- G3 rows: {len(ledger)}\n"
        f"- L1: {summary['gates']['L1_provenance']}\n"
        f"- L2: {summary['gates']['L2_structural']}\n"
        f"- L3: {summary['gates']['L3_semantic']}\n"
        f"- L4: {summary['gates']['L4_serialization']}\n",
        encoding="utf-8",
    )
    return 0 if l1_ok and l2_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
