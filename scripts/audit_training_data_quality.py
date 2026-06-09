#!/usr/bin/env python3
"""Audit final Step8 training data for model-facing quality risks."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gis_recommend.config.transformer_config import OUTPUT_DIR  # noqa: E402
from gis_recommend.data.training_data_quality import (  # noqa: E402
    audit_training_data_quality,
    load_l3_names,
)


def _load_workflows(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        raw = json.load(f)
    if isinstance(raw, dict):
        return raw.get("labeled_workflows", [])
    return raw


def _load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def _render_markdown(report: dict, data_path: Path, split_path: Path,
                     l3_names: dict[str, str] | None = None) -> str:
    l3_names = l3_names or {}
    counts = report["counts"]
    lines = [
        "# Training Data Quality Audit",
        "",
        f"Data: `{data_path}`",
        f"Splits: `{split_path}`",
        "",
        "## Summary",
        "",
        f"- Workflows: {counts['workflows']:,}",
        f"- L3 tokens: {counts['tokens']:,}",
        f"- Active L3: {counts['active_l3']} / {counts.get('expected_l3_vocab')}",
        f"- Task types: {counts['task_types']}",
        f"- Warnings: {', '.join(report['warnings']) if report['warnings'] else 'none'}",
        "",
        "## Model-Facing Risks",
        "",
        f"- Top10 L3 token share: {report['l3_distribution']['top10_share']:.2%}",
        f"- Top20 L3 token share: {report['l3_distribution']['top20_share']:.2%}",
        f"- Task types with <10 samples: {report['task_distribution']['tasks_lt_10']}",
        f"- Val-only task types: {len(report['split_quality']['val_tasks_not_in_train'])}",
        f"- Test-only task types: {len(report['split_quality']['test_tasks_not_in_train'])}",
        f"- Low-confidence tokens (<0.9): {report['confidence']['low_confidence_tokens']:,}",
        f"- Cross-split duplicate L3 sequences: {report['duplicates']['cross_split_sequence_hashes']:,}",
        "",
        "## Mapping Sources",
        "",
    ]
    for source, summary in sorted(
        report["mapping_source"]["source_summary"].items(),
        key=lambda item: item[1]["tokens"],
        reverse=True,
    ):
        lines.append(
            f"- `{source}`: {summary['tokens']:,} tokens "
            f"({summary['token_share']:.2%}), mean_conf={summary['mean_confidence']}, "
            f"low_conf={summary['low_confidence_tokens']:,}"
        )

    lines.extend(["", "## Top L3", ""])
    for item in report["l3_distribution"]["top_l3"][:20]:
        code = item.get("l3_code") or item["token_id"]
        name = l3_names.get(code)
        label = f"`{code}` ({name})" if name else f"`{code}`"
        lines.append(f"- {item['count']:,}: {label}")

    lines.extend(["", "## Sparse Split Tasks", ""])
    if report["split_quality"]["val_tasks_not_in_train"]:
        lines.append("Val-only:")
        for task in report["split_quality"]["val_tasks_not_in_train"]:
            lines.append(f"- {task}")
    if report["split_quality"]["test_tasks_not_in_train"]:
        lines.append("Test-only:")
        for task in report["split_quality"]["test_tasks_not_in_train"]:
            lines.append(f"- {task}")

    lines.extend(["", "## Low-Confidence Operator Hotlist", ""])
    for item in report["confidence"]["low_confidence_operators"][:30]:
        top_l3 = ", ".join(
            (
                f"{entry.get('l3_code') or entry['token_id']}"
                f"{'/' + l3_names[entry['l3_code']] if entry.get('l3_code') in l3_names else ''}"
                f":{entry['count']}"
            )
            for entry in item["top_l3"]
        )
        lines.append(
            f"- `{item['operator']}`: count={item['count']}, "
            f"low={item['low_confidence_ratio']:.2%}, "
            f"mean={item['mean_confidence']}, top_l3=[{top_l3}]"
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data",
        default=str(OUTPUT_DIR / "pipeline" / "step8" / "labeled_workflows_l3_v4_cleaned.json"),
        help="Final Step8 labeled workflow file.",
    )
    parser.add_argument(
        "--splits",
        default=str(OUTPUT_DIR / "dataset_splits_v4.json"),
        help="Dataset split file used by training/evaluation.",
    )
    parser.add_argument(
        "--id-mappings",
        default=str(OUTPUT_DIR / "id_mappings_v2.json"),
        help="Active id_mappings file for L3 names and mapping provenance.",
    )
    parser.add_argument(
        "--out-dir",
        default=str(OUTPUT_DIR / "pipeline" / "audit"),
        help="Directory for JSON/Markdown audit output.",
    )
    parser.add_argument(
        "--hierarchy",
        default=str(OUTPUT_DIR / "classification_hierarchy_v2.csv"),
        help="Optional hierarchy CSV used to render human-readable L3 names.",
    )
    parser.add_argument("--fail-on-warning", action="store_true",
                        help="Compatibility flag; warnings remain report-only.")
    args = parser.parse_args()

    data_path = Path(args.data)
    split_path = Path(args.splits)
    mapping_path = Path(args.id_mappings)
    out_dir = Path(args.out_dir)

    workflows = _load_workflows(data_path)
    splits = _load_json(split_path)
    id_mappings = _load_json(mapping_path)
    report = audit_training_data_quality(workflows, splits, id_mappings=id_mappings)
    l3_names = load_l3_names(args.hierarchy)

    out_dir.mkdir(parents=True, exist_ok=True)
    json_path = out_dir / "training_data_quality_audit.json"
    md_path = out_dir / "training_data_quality_audit.md"
    with json_path.open("w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)
    with md_path.open("w", encoding="utf-8") as f:
        f.write(_render_markdown(report, data_path, split_path, l3_names))

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
