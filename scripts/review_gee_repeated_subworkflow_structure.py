"""Build source-backed structural/semantic review proposals for GEE local units."""

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
    _filesystem_path,
    _json_text,
    _jsonl_text,
    _load_jsonl,
    _sha256,
)


DEFAULT_AUTHORITY_DIR = (
    ROOT
    / "docs/reports/gee_raster_core_v1_review_split_2026-07-24"
    / "gee_raster_core_batch_training_package_v1/strict_candidate_v1"
    / "source_audit_60_v1/authority_v2_3_0"
)
DEFAULT_FIDELITY = (
    DEFAULT_AUTHORITY_DIR
    / "repeated_subworkflow_fidelity_gate_v1"
    / "strict_candidate_repeated_subworkflow_fidelity_rank58_v1.jsonl"
)
DEFAULT_REPLAY = DEFAULT_AUTHORITY_DIR / "strict_candidate_source_replay_60_v1.jsonl"
DEFAULT_OUTPUT_DIR = DEFAULT_AUTHORITY_DIR / "repeated_subworkflow_structure_review_v1"
OUTPUT_PREFIX = "strict_candidate_repeated_subworkflow_structure_review_rank58_v1"


def _pattern_for(sequence: list[str]) -> str:
    signature = tuple(sequence)
    if signature == ("ee.imagecollection.mean", "ee.image.clip"):
        return "annual_mean_clip"
    if signature == ("ee.image.cat", "ee.image.select"):
        return "polarization_concat_select"
    if (
        len(signature) == 12
        and signature[0] == "ee.imagecollection.filterbounds"
        and signature[-1] == "ee.imagecollection.select"
        and signature.count("ee.imagecollection.filter") == 5
    ):
        return "year_polarization_preprocess"
    raise ValueError(f"unrecognized verified repeated-unit signature: {signature}")


def _source_snippet(source_text: str, start_line: int, end_line: int) -> str:
    lines = source_text.splitlines()
    if start_line < 1 or end_line < start_line or end_line > len(lines):
        raise ValueError("invalid source span")
    return "\n".join(
        f"{line_number}: {lines[line_number - 1]}"
        for line_number in range(start_line, end_line + 1)
    )


def _semantic_context(target: str, pattern: str) -> dict[str, Any]:
    normalized = str(target or "")
    year_match = re.search(r"20\d{2}", normalized)
    polarization = "VV" if normalized.upper().endswith("VV") else "VH" if normalized.upper().endswith("VH") else None
    family = re.sub(r"20\d{2}", "", normalized, flags=re.IGNORECASE)
    family = re.sub(r"(?:vv|vh)$", "", family, flags=re.IGNORECASE).strip("_")
    return {
        "target_variable": normalized,
        "year_literal": year_match.group(0) if year_match else None,
        "polarization": polarization,
        "target_family": family or None,
        "semantic_pattern": pattern,
    }


def review_structure_rows(
    *,
    fidelity_jsonl: Path,
    replay_jsonl: Path,
    audit_rank: int = 58,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    fidelity_rows = [
        row
        for row in _load_jsonl(Path(fidelity_jsonl))
        if row.get("audit_rank") == audit_rank and row.get("fidelity_status") == "passed"
    ]
    replay_rows = [row for row in _load_jsonl(Path(replay_jsonl)) if row.get("audit_rank") == audit_rank]
    if len(replay_rows) != 1:
        raise ValueError(f"expected one replay row for rank {audit_rank}")
    replay = replay_rows[0]
    calls_by_ordinal = {
        int(call["ordinal"]): call
        for call in replay.get("core_call_evidence", [])
        if isinstance(call, dict) and isinstance(call.get("ordinal"), int)
    }
    source_path = Path(str(replay["local_source_path"]))
    source_sha = _sha256(source_path)
    if source_sha != replay.get("source_sha256"):
        raise ValueError("replay source hash no longer matches local source")
    with open(_filesystem_path(source_path), encoding="utf-8") as handle:
        source_text = handle.read()

    rows: list[dict[str, Any]] = []
    patterns: Counter[str] = Counter()
    for candidate in fidelity_rows:
        pattern = _pattern_for(list(candidate.get("canonical_operator_sequence") or []))
        patterns[pattern] += 1
        ordinals = [int(item) for item in candidate.get("core_call_ordinals") or []]
        call_sites: list[dict[str, Any]] = []
        for index, ordinal in enumerate(ordinals):
            call = calls_by_ordinal.get(ordinal)
            if call is None:
                raise ValueError(f"missing replay call ordinal {ordinal}")
            call_sites.append(
                {
                    "ordinal": ordinal,
                    "source_location": call.get("source_location"),
                    "raw_callee": call.get("raw_callee"),
                    "canonical_operator": candidate["canonical_operator_sequence"][index],
                    "l3_code": candidate["l3_code_sequence"][index],
                }
            )
        start_line = int(candidate["start_line"])
        end_line = int(candidate["end_line"])
        rows.append(
            {
                "schema": "gis_recommend.gee_repeated_subworkflow_structure_review.v1",
                "audit_rank": audit_rank,
                "sample_id": candidate.get("sample_id"),
                "script_id": candidate.get("script_id"),
                "source_path": candidate.get("source_path"),
                "source_sha256": candidate.get("source_sha256"),
                "definition_id": candidate.get("definition_id"),
                "definition_kind": candidate.get("definition_kind"),
                "start_line": start_line,
                "end_line": end_line,
                "dependency_ids": candidate.get("dependency_ids", []),
                "selected_dependency_ids": candidate.get("selected_dependency_ids", []),
                "core_call_ordinals": ordinals,
                "raw_operator_sequence": candidate.get("raw_operator_sequence", []),
                "canonical_operator_sequence": candidate.get("canonical_operator_sequence", []),
                "l3_code_sequence": candidate.get("l3_code_sequence", []),
                "pattern": pattern,
                **_semantic_context(str(candidate.get("target") or ""), pattern),
                "source_snippet": _source_snippet(source_text, start_line, end_line),
                "call_site_evidence": call_sites,
                "review_status": "proposal_only",
                "review_reasons": [
                    "source_hash_verified_by_prior_gate",
                    "canonical_l3_replay_verified_by_prior_gate",
                    "pattern_signature_exact_match",
                ],
                "training_admission": "not_granted_repeated_subworkflow_structure_review",
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
                "training_rows_emitted": 0,
            }
        )

    summary = {
        "schema": "gis_recommend.gee_repeated_subworkflow_structure_review_summary.v1",
        "inputs": {
            "fidelity_jsonl": str(fidelity_jsonl),
            "fidelity_jsonl_sha256": _sha256(Path(fidelity_jsonl)),
            "replay_jsonl": str(replay_jsonl),
            "replay_jsonl_sha256": _sha256(Path(replay_jsonl)),
            "audit_rank": audit_rank,
            "sample_id": replay.get("sample_id"),
            "source_sha256": replay.get("source_sha256"),
        },
        "counts": {
            "fidelity_passed_input_rows": len(fidelity_rows),
            "review_proposals": len(rows),
            "training_rows_emitted": 0,
        },
        "pattern_counts": dict(sorted(patterns.items())),
        "decision": {
            "training_admission": "not_granted_repeated_subworkflow_structure_review",
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
            "training_rows_emitted": 0,
            "next_gate": "manual or rule-owner semantic completeness review before any task text",
        },
    }
    return rows, summary


def _render_report(summary: dict[str, Any]) -> str:
    counts = summary["counts"]
    lines = [
        "# GEE Repeated Subworkflow Structure Review v1",
        "",
        f"- Fidelity-passed input rows: {counts['fidelity_passed_input_rows']}",
        f"- Source-backed review proposals: {counts['review_proposals']}",
        f"- Pattern counts: {summary['pattern_counts']}",
        "- Training rows emitted: 0",
        "- Training/validation/test/production admission: not granted",
        "",
    ]
    return "\n".join(lines)


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
        "source_inputs": summary["inputs"],
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
    parser.add_argument("--fidelity-jsonl", type=Path, default=DEFAULT_FIDELITY)
    parser.add_argument("--replay-jsonl", type=Path, default=DEFAULT_REPLAY)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--audit-rank", type=int, default=58)
    args = parser.parse_args(argv)
    rows, summary = review_structure_rows(
        fidelity_jsonl=args.fidelity_jsonl,
        replay_jsonl=args.replay_jsonl,
        audit_rank=args.audit_rank,
    )
    return write_outputs(rows, summary, args.output_dir)


if __name__ == "__main__":
    main()
