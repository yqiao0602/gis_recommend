"""Deterministically review semantic completeness of GEE structure proposals.

This gate checks facts visible in the source-backed proposal snippet.  It does
not execute Earth Engine, infer a task description, or grant training
admission.  A passing row is an ``accepted_proposal`` only: domain meaning and
runtime availability remain explicitly recorded limitations.
"""

from __future__ import annotations

import argparse
from collections import Counter
from pathlib import Path
import re
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.build_gee_strict_candidate_source_audit import (  # noqa: E402
    _atomic_write,
    _json_text,
    _jsonl_text,
    _load_jsonl,
    _sha256,
)


DEFAULT_INPUT = (
    ROOT
    / "docs/reports/gee_raster_core_v1_review_split_2026-07-24"
    / "gee_raster_core_batch_training_package_v1/strict_candidate_v1"
    / "source_audit_60_v1/authority_v2_3_0"
    / "repeated_subworkflow_structure_review_v1"
    / "strict_candidate_repeated_subworkflow_structure_review_rank58_v1.jsonl"
)
DEFAULT_OUTPUT_DIR = DEFAULT_INPUT.parent / "repeated_subworkflow_semantic_review_v1"
OUTPUT_PREFIX = "strict_candidate_repeated_subworkflow_semantic_review_rank58_v1"


def _strings(text: str) -> list[str]:
    return [value for _, value in re.findall(r"(['\"])(.*?)\1", text, flags=re.S)]


def _id_set(row: dict[str, Any], field: str) -> set[str]:
    return {str(value) for value in row.get(field) or []}


def _context(row: dict[str, Any]) -> tuple[str, str | None, str | None, str | None]:
    target = str(row.get("target_variable") or "")
    year = str(row.get("year_literal") or "") or None
    polarization = str(row.get("polarization") or "") or None
    family = str(row.get("target_family") or "") or None
    return target, year, polarization, family


def _source_without_line_prefixes(text: str) -> str:
    return "\n".join(
        re.sub(r"^\s*\d+:\s?", "", line)
        for line in text.splitlines()
    )


def _review_preprocess(row: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    text = str(row.get("source_snippet") or "")
    target, year, polarization, _ = _context(row)
    reasons: list[str] = []
    facts: dict[str, Any] = {}
    declaration = re.search(
        r"var\s+(\w+)\s*=\s*ee\.ImageCollection\(\s*(['\"])(.*?)\2\s*\)",
        text,
        flags=re.S,
    )
    if declaration:
        facts["collection_id"] = declaration.group(3)
        if declaration.group(1) != target:
            reasons.append("target_declaration_mismatch")
    else:
        reasons.append("missing_imagecollection_literal")
    bounds = re.search(r"\.filterBounds\(\s*([A-Za-z_]\w*)\s*\)", text)
    if bounds:
        facts["bounds_variable"] = bounds.group(1)
    else:
        reasons.append("missing_spatial_filter")
    instrument = re.search(
        r"Filter\.eq\(\s*['\"]instrumentMode['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\)",
        text,
    )
    if instrument:
        facts["instrument_mode"] = instrument.group(1)
    else:
        reasons.append("missing_instrument_filter")
    polar = re.search(
        r"Filter\.listContains\(\s*['\"]transmitterReceiverPolarisation['\"]\s*,\s*['\"](VV|VH)['\"]\s*\)",
        text,
        flags=re.I,
    )
    if polar:
        facts["filter_polarization"] = polar.group(1).upper()
        if polarization and facts["filter_polarization"] != polarization:
            reasons.append("filter_polarization_mismatch")
    else:
        reasons.append("missing_polarization_filter")
    orbit = re.search(
        r"Filter\.eq\(\s*['\"]orbitProperties_pass['\"]\s*,\s*['\"]([^'\"]+)['\"]\s*\)",
        text,
    )
    if orbit:
        facts["orbit"] = orbit.group(1)
    else:
        reasons.append("missing_orbit_filter")
    year_filter = re.search(
        r"Filter\.calendarRange\(\s*(\d{4})\s*,\s*(\d{4})\s*,\s*['\"]year['\"]\s*\)",
        text,
        flags=re.I,
    )
    if year_filter:
        facts["year_range"] = [year_filter.group(1), year_filter.group(2)]
        if year and (year_filter.group(1) != year or year_filter.group(2) != year):
            reasons.append("year_filter_mismatch")
    else:
        reasons.append("missing_year_filter")
    month_filter = re.search(
        r"Filter\.calendarRange\(\s*(\d{1,2})\s*,\s*(\d{1,2})\s*,\s*['\"]month['\"]\s*\)",
        text,
        flags=re.I,
    )
    if month_filter:
        facts["month_range"] = [int(month_filter.group(1)), int(month_filter.group(2))]
    else:
        reasons.append("missing_month_filter")
    selected = re.search(r"\.select\(\s*\[\s*(['\"])(VV|VH)\1\s*\]\s*\)", text, flags=re.I)
    if selected:
        facts["selected_band"] = selected.group(2).upper()
        if polarization and facts["selected_band"] != polarization:
            reasons.append("selected_band_mismatch")
    else:
        reasons.append("missing_final_band_select")
    if not _id_set(row, "dependency_ids"):
        reasons.append("missing_upstream_dependency_evidence")
    if row.get("unresolved_identifiers"):
        reasons.append("unresolved_upstream_identifier")
    return reasons, facts


def _review_mean_clip(row: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    text = _source_without_line_prefixes(str(row.get("source_snippet") or ""))
    target, year, polarization, family = _context(row)
    reasons: list[str] = []
    facts: dict[str, Any] = {}
    assignment = re.match(
        r"(?s)^\s*(?:(?:var|let|const)\s+)?([A-Za-z_]\w*)\s*=\s*(.*?)\s*;?\s*$",
        text,
    )
    if not assignment:
        return ["missing_mean_clip_chain"], facts
    output, rhs = assignment.groups()
    match = re.fullmatch(
        r"(?:(?:([A-Za-z_]\w*)\.mean\(\))|(?:ee\.Image\(\s*([A-Za-z_]\w*)\.mean\(\)\s*\)))"
        r"\s*\.clip\(\s*([A-Za-z_]\w*)\s*\)",
        rhs.strip(),
        flags=re.S,
    )
    if not match:
        if re.search(r"\.mean\(\)\s*\.clip\(", rhs, flags=re.S):
            return ["mean_clip_not_assignment_core"], facts
        return ["missing_mean_clip_chain"], facts
    image_input = match.group(1) or match.group(2)
    region = match.group(3)
    facts.update({"output_variable": output, "image_input": image_input, "clip_region": region})
    if output != target:
        reasons.append("target_declaration_mismatch")
    input_year_match = re.search(r"20\d{2}", image_input)
    input_year = input_year_match.group(0) if input_year_match else None
    input_polarization_match = re.search(r"(?:^|_)(VV|VH)(?:_|$)|(?:VV|VH)$", image_input, flags=re.I)
    input_polarization = None
    if input_polarization_match:
        input_polarization = next(
            (value.upper() for value in input_polarization_match.groups() if value),
            input_polarization_match.group(0).strip("_").upper(),
        )
    target_polarization_match = re.search(r"(?:^|_)(VV|VH)(?:_|$)|(?:VV|VH)$", target, flags=re.I)
    target_polarization = polarization
    if target_polarization is None and target_polarization_match:
        target_polarization = next(
            (value.upper() for value in target_polarization_match.groups() if value),
            target_polarization_match.group(0).strip("_").upper(),
        )
    facts.update(
        {
            "target_year": year,
            "input_year": input_year,
            "target_polarization": target_polarization,
            "input_polarization": input_polarization,
            "target_family_hint": family,
        }
    )
    if year and input_year != year:
        reasons.append("mean_input_year_mismatch")
    if target_polarization and input_polarization != target_polarization:
        reasons.append("mean_input_polarization_mismatch")
    dependencies = _id_set(row, "dependency_ids")
    if not any(value.startswith(f"{image_input}@") for value in dependencies):
        reasons.append("mean_input_dependency_missing")
    if not any(value.startswith(f"{region}@") for value in dependencies):
        reasons.append("clip_region_dependency_missing")
    if row.get("unresolved_identifiers"):
        reasons.append("unresolved_upstream_identifier")
    if row.get("transitive_unresolved_identifiers"):
        reasons.append("transitive_unresolved_upstream_identifier")
    if "imagecollection_merge_argument_type_mismatch" in set(
        row.get("transitive_call_flags") or []
    ):
        reasons.append("invalid_upstream_collection_type")
    return reasons, facts


def _review_concat(row: dict[str, Any]) -> tuple[list[str], dict[str, Any]]:
    text = _source_without_line_prefixes(str(row.get("source_snippet") or ""))
    target, _, polarization, family = _context(row)
    reasons: list[str] = []
    facts: dict[str, Any] = {}
    match = re.search(
        r"(?ms)^\s*(?:(?:var|let|const)\s+)?([A-Za-z_]\w*)\s*=\s*"
        r"ee\.Image\.cat\((.*?)\)\s*\.select\(\s*\[(.*?)\]\s*,\s*\[(.*?)\]\s*\)\s*;?\s*$",
        text,
    )
    if not match:
        if re.search(r"ee\.Image\.cat\s*\(.*?\)\s*\.select\s*\(", text, flags=re.S):
            output_match = re.match(
                r"(?ms)^\s*(?:(?:var|let|const)\s+)?([A-Za-z_]\w*)\s*=", text
            )
            if output_match:
                facts["output_variable"] = output_match.group(1)
            return ["concat_shape_semantic_mismatch"], facts
        return ["missing_concat_select_chain"], facts
    output, args, input_band_text, output_band_text = match.groups()
    input_variables = re.findall(r"\b[A-Za-z_]\w*\b", args)
    input_bands = _strings(input_band_text)
    output_bands = _strings(output_band_text)
    facts.update(
        {
            "output_variable": output,
            "input_variables": input_variables,
            "input_bands": input_bands,
            "output_bands": output_bands,
        }
    )
    if output != target:
        reasons.append("target_declaration_mismatch")
    if len(input_variables) != 4:
        reasons.append("concat_input_count_not_four")
    parsed_inputs = [
        re.fullmatch(r"(.+?)(20\d{2})(vh)?", value, flags=re.I)
        for value in input_variables
    ]
    if len(parsed_inputs) != 4 or any(match is None for match in parsed_inputs):
        reasons.append("concat_input_year_literals_incomplete")
    input_families = {
        match.group(1).lower() for match in parsed_inputs if match is not None
    }
    input_suffixes = {
        (match.group(3) or "").lower() for match in parsed_inputs if match is not None
    }
    if len(input_families) != 1 or len(input_suffixes) != 1:
        reasons.append("concat_input_family_or_polarization_mismatch")
    inferred_polarization = "VH" if input_suffixes == {"vh"} else "VV" if input_suffixes == {""} else None
    expected_pol = (polarization or inferred_polarization or "").upper()
    facts["input_family"] = next(iter(input_families), None)
    facts["inferred_polarization"] = inferred_polarization
    if polarization and inferred_polarization != polarization:
        reasons.append("concat_target_polarization_mismatch")
    expected_input_bands = [expected_pol, f"{expected_pol}_1", f"{expected_pol}_2", f"{expected_pol}_3"]
    if input_bands != expected_input_bands:
        reasons.append("concat_input_band_mapping_mismatch")
    input_years = [
        match.group(0)
        for value in input_variables
        if (match := re.search(r"20\d{2}", value))
    ]
    facts["input_years"] = input_years
    if output_bands != input_years:
        reasons.append("concat_output_year_mapping_mismatch")
    dependencies = _id_set(row, "dependency_ids")
    selected = _id_set(row, "selected_dependency_ids")
    if len(selected) != 4 or not all(any(value.startswith(f"{name}@") for value in selected) for name in input_variables):
        reasons.append("concat_dependency_set_incomplete")
    if dependencies != selected:
        reasons.append("concat_selected_dependency_mismatch")
    if row.get("unresolved_identifiers"):
        reasons.append("unresolved_upstream_identifier")
    return reasons, facts


def review_semantic_rows(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for row in rows:
        pattern = str(row.get("pattern") or "")
        if pattern == "year_polarization_preprocess":
            reasons, facts = _review_preprocess(row)
        elif pattern == "annual_mean_clip":
            reasons, facts = _review_mean_clip(row)
        elif pattern == "polarization_concat_select":
            reasons, facts = _review_concat(row)
        else:
            reasons, facts = ["unknown_semantic_pattern"], {}
        reasons = sorted(set(reasons))
        status = "fail_closed" if reasons else "accepted_proposal"
        output.append(
            {
                **row,
                "schema": "gis_recommend.gee_repeated_subworkflow_semantic_review.v1",
                "semantic_facts": facts,
                "semantic_status": status,
                "semantic_reasons": reasons,
                "semantic_limitations": [
                    "region_domain_meaning_not_catalog_validated",
                    "earth_engine_runtime_not_executed",
                    "proposal_is_core_subworkflow_not_full_script_intent",
                ],
                "review_status": "semantic_review_proposal",
                "training_admission": "not_granted_repeated_subworkflow_semantic_review",
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
                "training_rows_emitted": 0,
            }
        )

    status_by_definition = {
        str(row.get("definition_id")): str(row["semantic_status"])
        for row in output
        if str(row.get("definition_id") or "")
    }
    changed = True
    while changed:
        changed = False
        for row in output:
            if row["semantic_status"] != "accepted_proposal":
                continue
            blocked = sorted(
                dependency
                for dependency in _id_set(row, "selected_dependency_ids")
                if status_by_definition.get(dependency) == "fail_closed"
            )
            if not blocked:
                continue
            row["semantic_status"] = "fail_closed"
            row["semantic_reasons"] = sorted(
                {*row["semantic_reasons"], "semantic_dependency_not_accepted"}
            )
            row["semantic_facts"] = {
                **row["semantic_facts"],
                "blocked_semantic_dependency_ids": blocked,
            }
            definition_id = str(row.get("definition_id") or "")
            if definition_id:
                status_by_definition[definition_id] = "fail_closed"
            changed = True

    statuses = Counter(str(row["semantic_status"]) for row in output)
    reasons_counter = Counter(
        reason for row in output for reason in row.get("semantic_reasons", [])
    )
    summary = {
        "schema": "gis_recommend.gee_repeated_subworkflow_semantic_review_summary.v1",
        "counts": {
            "input_rows": len(rows),
            "accepted_proposal": statuses["accepted_proposal"],
            "fail_closed": statuses["fail_closed"],
            "training_rows_emitted": 0,
        },
        "pattern_counts": dict(sorted(Counter(str(row.get("pattern") or "") for row in rows).items())),
        "reason_counts": dict(sorted(reasons_counter.items())),
        "decision": {
            "training_admission": "not_granted_repeated_subworkflow_semantic_review",
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
            "next_gate": "rule-owner or human review of accepted proposals before chain-faithful text",
        },
    }
    return output, summary


def _render_report(summary: dict[str, Any]) -> str:
    counts = summary["counts"]
    lines = [
        "# GEE Repeated Subworkflow Semantic Completeness Review v1",
        "",
        f"- Input proposals: {counts['input_rows']}",
        f"- Accepted proposals (deterministic semantic facts complete): {counts['accepted_proposal']}",
        f"- Fail-closed proposals: {counts['fail_closed']}",
        "- Training rows emitted: 0",
        "- Training/validation/test/production admission: not granted",
        "",
        "A passing proposal has complete source-visible core-subworkflow facts; it is not a human approval, runtime execution result, or full-script task label.",
        "",
        "## Pattern counts",
        "",
        *[f"- `{key}`: {value}" for key, value in summary["pattern_counts"].items()],
        "",
        "## Semantic limitations retained on every row",
        "",
        "- Region domain meaning is not catalog-validated.",
        "- Earth Engine runtime/data availability is not executed.",
        "- The proposal represents a retained core subworkflow, not full script intent.",
    ]
    return "\n".join(lines) + "\n"


def write_outputs(rows: list[dict[str, Any]], summary: dict[str, Any], output_dir: Path) -> dict[str, Path]:
    output_dir = Path(output_dir)
    paths = {
        "jsonl": output_dir / f"{OUTPUT_PREFIX}.jsonl",
        "summary": output_dir / f"{OUTPUT_PREFIX}_summary.json",
        "report": output_dir / f"{OUTPUT_PREFIX}_report.md",
        "hash_ledger": output_dir / f"{OUTPUT_PREFIX}_hash_ledger.json",
    }
    _atomic_write(paths["jsonl"], _jsonl_text(rows))
    _atomic_write(paths["summary"], _json_text(summary))
    _atomic_write(paths["report"], _render_report(summary))
    ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "source_input_sha256": summary.get("source_input_sha256"),
        "artifacts": {
            path.name: {"path": str(path), "sha256": _sha256(path)}
            for key, path in paths.items()
            if key != "hash_ledger"
        },
    }
    _atomic_write(paths["hash_ledger"], _json_text(ledger))
    return paths


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-jsonl", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)
    input_path = Path(args.input_jsonl)
    rows, summary = review_semantic_rows(_load_jsonl(input_path))
    summary["source_input"] = str(input_path)
    summary["source_input_sha256"] = _sha256(input_path)
    return write_outputs(rows, summary, Path(args.output_dir))


if __name__ == "__main__":
    main()
