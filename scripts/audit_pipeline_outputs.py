#!/usr/bin/env python3
"""Audit the 8-step data pipeline outputs under one outputs root.

This is a result-quality audit, not just a code-path check.  It verifies that
the selected baseline directory (for example outputs_v2) contains a coherent
step1-8 chain and that final L3 labels still agree with the current mapping and
skip list.
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gis_recommend.data import (  # noqa: E402
    get_default_gee_skip_list_path,
    get_default_id_mappings_path,
    get_outputs_dir,
)
from gis_recommend.data.pipeline_provenance import provenance_warnings  # noqa: E402


STEP_FILES = {
    1: ("raw_workflows.json", "workflows"),
    2: ("cleaned_workflows.json", "workflows"),
    3: ("final_workflows.json", "workflows"),
    4: ("standardized_workflows.json", "workflows"),
    5: ("workflow_sequences.json", "workflow_dags"),
    6: ("labeled_workflows_l3.json", "labeled_workflows"),
    7: ("labeled_workflows_l3_v4.json", "labeled_workflows"),
    8: ("labeled_workflows_l3_v4_cleaned.json", "labeled_workflows"),
}


def load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def content_codes(workflow: dict) -> list[str]:
    return [c for c in workflow.get("l3_codes", []) if c not in ("<START>", "<END>")]


def length_stats(lengths: list[int]) -> dict:
    if not lengths:
        return {"count": 0, "min": 0, "max": 0, "mean": 0, "median": 0}
    return {
        "count": len(lengths),
        "min": min(lengths),
        "max": max(lengths),
        "mean": round(sum(lengths) / len(lengths), 3),
        "median": statistics.median(lengths),
    }


def count_consecutive_repeats(codes: list[str], threshold: int = 3) -> int:
    if not codes:
        return 0
    run = 1
    for i in range(1, len(codes)):
        if codes[i] == codes[i - 1]:
            run += 1
            if run >= threshold:
                return 1
        else:
            run = 1
    return 0


def load_current_mapping(mapping_file: Path | None) -> dict[str, str]:
    if not mapping_file or not mapping_file.exists():
        return {}
    data = load_json(mapping_file)
    gee = data.get("mapping_metadata", {}).get("gee_to_l3", {})
    return {op.lower().strip(): meta["primary_l3"] for op, meta in gee.items()}


def load_skip_list(skip_file: Path | None) -> set[str]:
    if not skip_file or not skip_file.exists():
        return set()
    data = load_json(skip_file)
    return {op.lower().strip() for op in data.get("skip_operators", [])}


def audit_labeled_workflows(workflows: list[dict], current_mapping: dict[str, str],
                            skip_ops: set[str]) -> dict:
    stats = Counter()
    l3_counter = Counter()
    task_counter = Counter()
    mismatch_patterns = Counter()
    skip_patterns = Counter()
    missing_patterns = Counter()

    for wf in workflows:
        ops = wf.get("operator_sequence", [])
        codes = content_codes(wf)
        stats["tokens"] += len(codes)
        stats["workflows_with_consecutive_3plus"] += count_consecutive_repeats(codes)
        if len(ops) != len(codes):
            stats["length_mismatch_workflows"] += 1
            continue
        if len(wf.get("confidences", [])) != len(codes):
            stats["confidence_mismatch_workflows"] += 1
        if len(wf.get("ambiguity_flags", [])) != len(codes):
            stats["ambiguity_mismatch_workflows"] += 1
        l3_counter.update(codes)
        task_type = wf.get("task_metadata", {}).get("task_type", "Unknown") or "Unknown"
        task_counter[task_type] += 1
        for op, code in zip(ops, codes):
            op_l = op.lower().strip()
            if op_l in skip_ops:
                stats["skip_list_operator_tokens"] += 1
                skip_patterns[(op_l, code)] += 1
            elif current_mapping:
                expected = current_mapping.get(op_l)
                if expected is None:
                    stats["missing_current_mapping_tokens"] += 1
                    missing_patterns[(op_l, code)] += 1
                elif expected != code:
                    stats["current_mapping_mismatch_tokens"] += 1
                    mismatch_patterns[(op_l, code, expected)] += 1

    unknown_tasks = task_counter.get("Unknown", 0)
    return {
        "token_count": stats["tokens"],
        "active_l3_count": len(l3_counter),
        "top_l3": l3_counter.most_common(20),
        "task_type_count": len(task_counter),
        "unknown_task_count": unknown_tasks,
        "unknown_task_rate": round(unknown_tasks / max(len(workflows), 1), 4),
        "top_task_types": task_counter.most_common(20),
        "length_mismatch_workflows": stats["length_mismatch_workflows"],
        "confidence_mismatch_workflows": stats["confidence_mismatch_workflows"],
        "ambiguity_mismatch_workflows": stats["ambiguity_mismatch_workflows"],
        "workflows_with_consecutive_3plus": stats["workflows_with_consecutive_3plus"],
        "skip_list_operator_tokens": stats["skip_list_operator_tokens"],
        "current_mapping_mismatch_tokens": stats["current_mapping_mismatch_tokens"],
        "missing_current_mapping_tokens": stats["missing_current_mapping_tokens"],
        "top_skip_list_patterns": [
            {"operator": op, "l3": code, "count": count}
            for (op, code), count in skip_patterns.most_common(20)
        ],
        "top_mismatch_patterns": [
            {"operator": op, "actual_l3": actual, "expected_l3": expected, "count": count}
            for (op, actual, expected), count in mismatch_patterns.most_common(20)
        ],
        "top_missing_mapping_patterns": [
            {"operator": op, "l3": code, "count": count}
            for (op, code), count in missing_patterns.most_common(20)
        ],
    }


def audit_step(outputs_dir: Path, step: int, previous_count: int | None,
               current_mapping: dict[str, str], skip_ops: set[str],
               mapping_file: Path | None = None, skip_file: Path | None = None,
               require_provenance: bool = False) -> tuple[dict, int | None]:
    filename, list_key = STEP_FILES[step]
    path = outputs_dir / "pipeline" / f"step{step}" / filename
    result = {
        "step": step,
        "path": str(path.relative_to(ROOT)) if path.exists() else str(path),
        "exists": path.exists(),
        "warnings": [],
    }
    if not path.exists():
        result["warnings"].append("missing_step_output")
        return result, previous_count

    data = load_json(path)
    items = data.get(list_key, [])
    result["count"] = len(items)
    result["file_size_mb"] = round(path.stat().st_size / 1024 / 1024, 2)
    if previous_count is not None:
        drop = previous_count - len(items)
        result["delta_from_previous"] = drop
        result["drop_rate_from_previous"] = round(drop / max(previous_count, 1), 4)
        if drop > 0 and drop / max(previous_count, 1) > 0.2:
            result["warnings"].append("large_drop_from_previous")

    if step in (1, 2, 3):
        lengths = [len(w.get("operations", [])) for w in items]
        result["operation_length"] = length_stats(lengths)
        result["empty_sequences"] = sum(1 for n in lengths if n == 0)
    elif step == 4:
        lengths = [len(w.get("operator_sequence", [])) for w in items]
        result["operator_length"] = length_stats(lengths)
        result["empty_sequences"] = sum(1 for n in lengths if n == 0)
        result["unique_operations_declared"] = data.get("unique_operations")
        result["status_distribution"] = data.get("status_distribution")
    elif step == 5:
        lengths = [len(w.get("nodes", [])) for w in items]
        result["node_length"] = length_stats(lengths)
        result["empty_dags"] = sum(1 for n in lengths if n == 0)
    elif step in (6, 7, 8):
        lengths = [len(content_codes(w)) for w in items]
        result["content_l3_length"] = length_stats(lengths)
        result["empty_l3_sequences"] = sum(1 for n in lengths if n == 0)
        result["provenance"] = data.get("provenance")
        provenance_issues = provenance_warnings(
            data.get("provenance"),
            mapping_file,
            skip_file,
            require=require_provenance or step == 8,
        )
        result["provenance_warnings"] = provenance_issues
        result["warnings"].extend(provenance_issues)
        result["labeled_quality"] = audit_labeled_workflows(items, current_mapping, skip_ops)
        lq = result["labeled_quality"]
        if lq["length_mismatch_workflows"]:
            result["warnings"].append("operator_l3_length_mismatch")
        if lq["confidence_mismatch_workflows"]:
            result["warnings"].append("confidence_l3_length_mismatch")
        if lq["ambiguity_mismatch_workflows"]:
            result["warnings"].append("ambiguity_l3_length_mismatch")
        if step == 8 and lq["skip_list_operator_tokens"]:
            result["warnings"].append("final_data_contains_current_skip_list_ops")
        if step == 8 and lq["current_mapping_mismatch_tokens"]:
            result["warnings"].append("final_data_disagrees_with_current_mapping")
        if step == 8 and lq["unknown_task_rate"] > 0.01:
            result["warnings"].append("final_data_has_many_unknown_task_types")

    return result, len(items)


def render_markdown(report: dict) -> str:
    lines = [
        "# Pipeline Quality Audit",
        "",
        f"Outputs dir: `{report['outputs_dir']}`",
        f"Mapping file: `{report.get('mapping_file') or '(none)'}`",
        f"Skip list: `{report.get('skip_list_file') or '(none)'}`",
        "",
        "## Summary",
        "",
    ]
    if report["warnings"]:
        lines.append("Warnings:")
        for warning in report["warnings"]:
            lines.append(f"- {warning}")
    else:
        lines.append("Warnings: none")

    lines.extend(["", "## Step Counts", ""])
    for step in report["steps"]:
        status = "OK" if step.get("exists") else "MISSING"
        count = step.get("count", "-")
        drop = step.get("drop_rate_from_previous")
        drop_text = "" if drop is None else f", drop={drop:.2%}"
        warnings = ", ".join(step.get("warnings", [])) or "none"
        lines.append(f"- Step {step['step']}: {status}, count={count}{drop_text}, warnings={warnings}")

    final = next((s for s in report["steps"] if s["step"] == 8 and s.get("exists")), None)
    if final:
        q = final.get("labeled_quality", {})
        lines.extend([
            "",
            "## Final Step8 Quality",
            "",
            f"- Tokens: {q.get('token_count', 0):,}",
            f"- Active L3: {q.get('active_l3_count', 0)}",
            f"- Operator/L3 length mismatch workflows: {q.get('length_mismatch_workflows', 0)}",
            f"- Confidence/L3 length mismatch workflows: {q.get('confidence_mismatch_workflows', 0)}",
            f"- Ambiguity/L3 length mismatch workflows: {q.get('ambiguity_mismatch_workflows', 0)}",
            f"- Workflows with consecutive 3+ L3 repeats: {q.get('workflows_with_consecutive_3plus', 0)}",
            f"- Current skip-list operator tokens: {q.get('skip_list_operator_tokens', 0)}",
            f"- Current mapping mismatch tokens: {q.get('current_mapping_mismatch_tokens', 0)}",
            f"- Missing current mapping tokens: {q.get('missing_current_mapping_tokens', 0)}",
            f"- Unknown task type rate: {q.get('unknown_task_rate', 0):.2%}",
        ])
        if q.get("top_skip_list_patterns"):
            lines.extend(["", "Top skip-list leaks:"])
            for item in q["top_skip_list_patterns"][:10]:
                lines.append(f"- {item['count']}: `{item['operator']}` -> `{item['l3']}`")
        lines.extend(["", "Top L3:"])
        for code, count in q.get("top_l3", [])[:10]:
            lines.append(f"- {count}: `{code}`")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit step1-8 pipeline outputs under one outputs root.")
    parser.add_argument("--outputs-dir", default=None,
                        help="Outputs root to audit, e.g. outputs_v2. Defaults to GIS_OUTPUTS_DIR or outputs.")
    parser.add_argument("--id-mappings", default=None,
                        help="Current id_mappings file. Defaults to active outputs root.")
    parser.add_argument("--skip-list", default=None,
                        help="Current GEE skip list. Defaults to active outputs root.")
    parser.add_argument("--require-provenance", action="store_true",
                        help="Record warnings when Step6-8 outputs lack valid mapping provenance.")
    parser.add_argument("--fail-on-warning", action="store_true",
                        help="Compatibility flag; warnings remain report-only.")
    args = parser.parse_args()

    outputs_dir = get_outputs_dir(args.outputs_dir)
    mapping_file = Path(args.id_mappings) if args.id_mappings else get_default_id_mappings_path(outputs_dir)
    skip_file = Path(args.skip_list) if args.skip_list else get_default_gee_skip_list_path(outputs_dir)
    if mapping_file and not mapping_file.is_absolute():
        mapping_file = ROOT / mapping_file
    if skip_file and not skip_file.is_absolute():
        skip_file = ROOT / skip_file

    current_mapping = load_current_mapping(mapping_file)
    skip_ops = load_skip_list(skip_file)

    report = {
        "outputs_dir": str(outputs_dir.relative_to(ROOT) if outputs_dir.is_relative_to(ROOT) else outputs_dir),
        "mapping_file": str(mapping_file.relative_to(ROOT) if mapping_file and mapping_file.exists() and mapping_file.is_relative_to(ROOT) else mapping_file),
        "skip_list_file": str(skip_file.relative_to(ROOT) if skip_file and skip_file.exists() and skip_file.is_relative_to(ROOT) else skip_file),
        "steps": [],
        "warnings": [],
    }

    previous_count = None
    for step in range(1, 9):
        step_report, previous_count = audit_step(
            outputs_dir,
            step,
            previous_count,
            current_mapping,
            skip_ops,
            mapping_file=mapping_file,
            skip_file=skip_file,
            require_provenance=args.require_provenance,
        )
        report["steps"].append(step_report)
        for warning in step_report.get("warnings", []):
            report["warnings"].append(f"step{step}:{warning}")

    audit_dir = outputs_dir / "pipeline" / "audit"
    audit_dir.mkdir(parents=True, exist_ok=True)
    json_path = audit_dir / "pipeline_quality_audit.json"
    md_path = audit_dir / "pipeline_quality_audit.md"
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    with md_path.open("w", encoding="utf-8") as f:
        f.write(render_markdown(report))

    print(f"Wrote {json_path}")
    print(f"Wrote {md_path}")
    if report["warnings"]:
        print("Warnings:")
        for warning in report["warnings"]:
            print(f"  - {warning}")
    else:
        print("Warnings: none")
    if args.fail_on_warning and report["warnings"]:
        print("  [INFO] --fail-on-warning is report-only under the Phase 15C execution contract")


if __name__ == "__main__":
    main()
