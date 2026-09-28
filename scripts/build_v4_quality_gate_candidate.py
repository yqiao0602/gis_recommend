#!/usr/bin/env python3
"""Build a quality-gated V4 training-data candidate without overwriting Step8."""

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
from gis_recommend.data.quality_gate import (  # noqa: E402
    QualityGatePolicy,
    audit_gee_operator_aliases,
    build_quality_gate_candidate,
    write_quality_gate_outputs,
)


def _load_input(path: Path) -> tuple[list[dict], dict | None, dict | None]:
    with path.open(encoding="utf-8") as f:
        raw = json.load(f)
    if isinstance(raw, dict):
        return (
            raw.get("labeled_workflows", []),
            raw.get("provenance"),
            raw.get("authority_validation"),
        )
    return raw, None, None


def _load_json(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--data",
        default=str(OUTPUT_DIR / "pipeline" / "step8" / "labeled_workflows_l3_v4_cleaned.json"),
        help="Final Step8 labeled workflow file. This file is read-only.",
    )
    parser.add_argument(
        "--id-mappings",
        default=str(OUTPUT_DIR / "id_mappings_v2.json"),
        help="Active v2 id_mappings file.",
    )
    parser.add_argument(
        "--out-dir",
        default=str(OUTPUT_DIR / "pipeline" / "step8_quality_gate"),
        help="Output directory for candidate files.",
    )
    parser.add_argument(
        "--official-gee-operators",
        default=str(ROOT.parent / "operators-json" / "gee_operators.json"),
        help="Optional crawled official GEE operator JSON for alias audit.",
    )
    parser.add_argument("--min-task-count", type=int, default=10)
    parser.add_argument(
        "--sparse-task-policy",
        choices=("merge", "filter", "keep"),
        default="merge",
    )
    parser.add_argument("--rare-task-label", default="Other / Sparse")
    parser.add_argument("--low-confidence-threshold", type=float, default=0.9)
    parser.add_argument(
        "--low-confidence-sources",
        default="auto_remap",
        help="Comma-separated mapping sources to quarantine when confidence is below threshold.",
    )
    parser.add_argument(
        "--low-confidence-policy",
        choices=("quarantine", "keep"),
        default="quarantine",
    )
    parser.add_argument(
        "--description-alignment-policy",
        choices=("report", "quarantine"),
        default="report",
        help="Audit lexical description/chain gaps or quarantine affected workflows.",
    )
    parser.add_argument(
        "--source-identity-policy",
        choices=("report", "require", "ignore"),
        default="report",
        help="Report missing trusted source identity, require it, or use legacy sequence-only grouping.",
    )
    parser.add_argument(
        "--input-authority-policy",
        choices=("require", "report"),
        default="require",
        help="Require Step8 provenance/training admission or retain unvalidated input for diagnostics only.",
    )
    parser.add_argument("--train-ratio", type=float, default=0.8)
    parser.add_argument("--val-ratio", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--no-group-duplicate-l3-sequence",
        action="store_true",
        help="Disable exact L3-sequence grouping during split creation.",
    )
    args = parser.parse_args(argv)

    data_path = Path(args.data)
    mapping_path = Path(args.id_mappings)
    out_dir = Path(args.out_dir)

    workflows, provenance, authority_validation = _load_input(data_path)
    input_authority_valid = bool(
        provenance
        and authority_validation
        and authority_validation.get("training_admission") is True
    )
    if args.input_authority_policy == "require" and not input_authority_valid:
        raise ValueError(
            "Quality-gate input lacks validated Step8 authority; "
            "use --input-authority-policy report for diagnostics only"
        )
    id_mappings = _load_json(mapping_path)
    sources = tuple(
        source.strip()
        for source in args.low_confidence_sources.split(",")
        if source.strip()
    )
    policy = QualityGatePolicy(
        min_task_count=args.min_task_count,
        rare_task_label=args.rare_task_label,
        sparse_task_policy=args.sparse_task_policy,
        low_confidence_threshold=args.low_confidence_threshold,
        low_confidence_sources=sources,
        low_confidence_policy=args.low_confidence_policy,
        description_alignment_policy=args.description_alignment_policy,
        source_identity_policy=args.source_identity_policy,
        group_duplicate_l3_sequence=not args.no_group_duplicate_l3_sequence,
        train_ratio=args.train_ratio,
        val_ratio=args.val_ratio,
        seed=args.seed,
    )

    result = build_quality_gate_candidate(
        workflows,
        id_mappings,
        policy,
        provenance=provenance,
        authority_validation=authority_validation or {
            "training_admission": False,
            "issues": ["missing_or_unvalidated_step8_authority"],
            "policy": args.input_authority_policy,
        },
    )
    paths = write_quality_gate_outputs(result, out_dir)

    official_path = Path(args.official_gee_operators)
    if official_path.exists():
        official = _load_json(official_path)
        alias_report = audit_gee_operator_aliases(
            result.candidate_workflows,
            id_mappings,
            official,
        )
        alias_json = out_dir / "gee_operator_alias_audit.json"
        alias_md = out_dir / "gee_operator_alias_audit.md"
        with alias_json.open("w", encoding="utf-8") as f:
            json.dump(alias_report, f, ensure_ascii=False, indent=2)
        with alias_md.open("w", encoding="utf-8") as f:
            f.write(_render_alias_markdown(alias_report, official_path))
        paths["gee_alias_json"] = alias_json
        paths["gee_alias_md"] = alias_md

    print("Quality gate candidate written:")
    for label, path in paths.items():
        print(f"  {label}: {path}")
    print(
        "Summary: "
        f"input={result.report['counts']['input_workflows']}, "
        f"candidate={result.report['counts']['candidate_workflows']}, "
        f"quarantine={result.report['counts']['quarantined_workflows']}, "
        f"sparse_merged={result.report['counts']['sparse_merged_workflows']}, "
        f"cross_split_duplicates={result.report['splits']['cross_split_sequence_hashes']}, "
        f"missing_source_identity={result.report['source_identity']['missing_workflows']}, "
        f"description_issues={result.report['description_alignment']['workflows_with_issues']}"
    )
    return paths


def _render_alias_markdown(report: dict, official_path: Path) -> str:
    lines = [
        "# GEE Operator Alias Audit",
        "",
        f"Official operator source: `{official_path}`",
        "",
        "## Summary",
        "",
    ]
    counts = report["counts"]
    for key in (
        "operator_tokens",
        "unique_operators",
        "mapping_lower_matches",
        "mapping_exact_matches",
        "official_name_lower_matches",
        "official_name_exact_matches",
        "unresolved_official_name",
        "unresolved_official_tokens",
    ):
        lines.append(f"- {key}: {counts[key]:,}")
    lines.append(
        f"- unresolved_official_token_share: {counts['unresolved_official_token_share']:.2%}"
    )

    lines.extend(["", "## Unresolved Official Names", ""])
    for item in report["unresolved_operators"][:30]:
        lines.append(
            f"- `{item['operator']}`: count={item['count']}, "
            f"mapping_key=`{item.get('mapping_key')}`, source={item.get('source')}, "
            f"conf={item.get('mapping_confidence')}, l3={item.get('primary_l3')}"
        )
    if not report["unresolved_operators"]:
        lines.append("- none")

    lines.extend(["", "## Case Display Mismatches", ""])
    for item in report["case_display_mismatches"][:30]:
        lines.append(
            f"- `{item['operator']}` -> `{item['official_name']}` "
            f"(count={item['count']})"
        )
    if not report["case_display_mismatches"]:
        lines.append("- none")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    main()
