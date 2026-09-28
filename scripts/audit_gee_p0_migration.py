#!/usr/bin/env python3
"""Audit current GEE artifacts against the P0 authority contracts without mutation."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gis_recommend.data.quality_gate import (  # noqa: E402
    audit_description_alignment,
    extract_source_identities,
)


def _load_workflows(path: Path) -> list[dict[str, Any]]:
    with Path(path).open(encoding="utf-8") as handle:
        payload = json.load(handle)
    if isinstance(payload, dict):
        workflows = payload.get("labeled_workflows", [])
    else:
        workflows = payload
    if not isinstance(workflows, list):
        raise ValueError(f"{path} does not contain a workflow list")
    return workflows


def _content_codes(workflows: list[dict[str, Any]]) -> set[str]:
    return {
        code
        for workflow in workflows
        for code in workflow.get("l3_codes", [])
        if isinstance(code, str) and not code.startswith("<")
    }


def build_migration_audit(
    *,
    step7_path: Path,
    step8_path: Path,
    quality_gate_path: Path,
    id_mappings_path: Path,
    legacy_sample_limit: int = 1000,
) -> dict[str, Any]:
    step7 = _load_workflows(step7_path)
    step8 = _load_workflows(step8_path)
    quality_gate = _load_workflows(quality_gate_path)
    with Path(id_mappings_path).open(encoding="utf-8") as handle:
        id_mappings = json.load(handle)
    authority = id_mappings.get("l3") if isinstance(id_mappings, dict) else None
    if not isinstance(authority, dict) or not authority:
        raise ValueError(f"{id_mappings_path} must contain a non-empty 'l3' mapping")

    step7_codes = _content_codes(step7)
    legacy_codes = _content_codes(step7[:legacy_sample_limit])
    step8_codes = _content_codes(step8)
    quality_gate_codes = _content_codes(quality_gate)
    legacy_missing = step7_codes - legacy_codes
    legacy_affected = sum(
        any(code in legacy_missing for code in workflow.get("l3_codes", []))
        for workflow in step7
    )
    legacy_missing_tokens = sum(
        code in legacy_missing
        for workflow in step7
        for code in workflow.get("l3_codes", [])
    )

    claim_counts: Counter[str] = Counter()
    status_counts: Counter[str] = Counter()
    alignment_issues = 0
    retention_below_half = 0
    for workflow in quality_gate:
        alignment = audit_description_alignment(workflow)
        alignment_issues += int(alignment["has_issue"])
        ratio = alignment["operator_retention_ratio"]
        retention_below_half += int(ratio is not None and ratio < 0.5)
        for claim in alignment["claims"]:
            claim_counts[claim["claim"]] += 1
            status_counts[claim["status"]] += 1

    identity_field_counts: Counter[str] = Counter()
    workflows_with_identity = 0
    for workflow in quality_gate:
        identities = extract_source_identities(workflow)
        workflows_with_identity += int(bool(identities))
        for identity in identities:
            identity_field_counts[identity.split(":", 1)[0]] += 1

    return {
        "schema": "gis_recommend.gee_p0_migration_audit.v1",
        "inputs": {
            "step7": str(Path(step7_path)),
            "step8": str(Path(step8_path)),
            "quality_gate": str(Path(quality_gate_path)),
            "id_mappings": str(Path(id_mappings_path)),
            "legacy_sample_limit": legacy_sample_limit,
        },
        "counts": {
            "step7_workflows": len(step7),
            "step8_workflows": len(step8),
            "quality_gate_workflows": len(quality_gate),
        },
        "vocabulary": {
            "authority_codes": len(authority),
            "step7_codes": len(step7_codes),
            "legacy_sample_codes": len(legacy_codes),
            "step8_codes": len(step8_codes),
            "quality_gate_codes": len(quality_gate_codes),
            "legacy_missing_codes": sorted(legacy_missing),
            "legacy_affected_workflows": legacy_affected,
            "legacy_missing_tokens": legacy_missing_tokens,
            "lost_step7_to_step8": sorted(step7_codes - step8_codes),
            "lost_step8_to_quality_gate": sorted(step8_codes - quality_gate_codes),
            "step7_codes_missing_from_authority": sorted(step7_codes - set(authority)),
        },
        "description_alignment": {
            "authority": "lexical_proxy",
            "workflows_with_issues": alignment_issues,
            "claims": dict(claim_counts),
            "statuses": dict(status_counts),
            "operator_retention_below_50_percent": retention_below_half,
        },
        "source_identity": {
            "workflows_with_identity": workflows_with_identity,
            "missing_workflows": len(quality_gate) - workflows_with_identity,
            "identity_field_occurrences": dict(identity_field_counts),
            "source_disjoint_verified": False,
        },
        "decision": {
            "training_regeneration_authorized": False,
            "large_dataset_overwrite_authorized": False,
            "next_gate": "review audit before any GEE regeneration",
        },
    }


def _render_markdown(report: dict[str, Any]) -> str:
    vocab = report["vocabulary"]
    alignment = report["description_alignment"]
    source = report["source_identity"]
    return "\n".join([
        "# GEE P0 Migration Audit",
        "",
        f"- Step7 workflows: {report['counts']['step7_workflows']:,}",
        f"- Step8 workflows: {report['counts']['step8_workflows']:,}",
        f"- Quality-gate workflows: {report['counts']['quality_gate_workflows']:,}",
        f"- Authority L3 codes: {vocab['authority_codes']}",
        f"- Step7 L3 codes: {vocab['step7_codes']}",
        f"- Legacy first-sample missing L3 codes: {len(vocab['legacy_missing_codes'])}",
        f"- Legacy affected workflows: {vocab['legacy_affected_workflows']:,}",
        f"- Description alignment issues: {alignment['workflows_with_issues']:,}",
        f"- Missing trusted source identity: {source['missing_workflows']:,}",
        "- Training regeneration authorized: false",
        "",
    ])


def main(argv: list[str] | None = None) -> dict[str, Any]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--step7", type=Path, default=ROOT / "outputs_v2/pipeline/step7/labeled_workflows_l3_v4.json")
    parser.add_argument("--step8", type=Path, default=ROOT / "outputs_v2/pipeline/step8/labeled_workflows_l3_v4_cleaned.json")
    parser.add_argument("--quality-gate", type=Path, default=ROOT / "outputs_v2/pipeline/step8_quality_gate/labeled_workflows_l3_v4_quality_gate.json")
    parser.add_argument("--id-mappings", type=Path, default=ROOT / "outputs_v2/id_mappings_v2.json")
    parser.add_argument("--legacy-sample-limit", type=int, default=1000)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument("--markdown-output", type=Path, default=None)
    args = parser.parse_args(argv)

    report = build_migration_audit(
        step7_path=args.step7,
        step8_path=args.step8,
        quality_gate_path=args.quality_gate,
        id_mappings_path=args.id_mappings,
        legacy_sample_limit=args.legacy_sample_limit,
    )
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    if args.markdown_output:
        args.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        args.markdown_output.write_text(_render_markdown(report), encoding="utf-8")
    if not args.output and not args.markdown_output:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    return report


if __name__ == "__main__":
    main()
