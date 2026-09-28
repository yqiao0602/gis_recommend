#!/usr/bin/env python3
"""Export the 19 source-reviewed stable101 rows as a train-only pilot JSONL.

The exporter is deterministic and does not call an LLM, update production
vocabularies, merge into outputs_v2, create validation/test rows, or train.
"""

from __future__ import annotations

import argparse
import csv
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
REPORT_ROOT = (
    ROOT
    / "docs/reports/qgis_mapping_high_impact_blockers_2026-07-24"
)
DEFAULT_REVIEW_DIR = REPORT_ROOT / "stable101_source_review_50_v1"
DEFAULT_REVIEW_CSV = DEFAULT_REVIEW_DIR / "stable101_source_review_50_v1.csv"
DEFAULT_ADJUDICATIONS = (
    DEFAULT_REVIEW_DIR / "stable101_source_review_50_adjudications_v1.jsonl"
)
DEFAULT_SALVAGE_LEDGER = DEFAULT_REVIEW_DIR / "stable101_salvage_ledger_v1.jsonl"
DEFAULT_STABLE101_PROPOSAL = REPORT_ROOT / "stable101_conservative_extension_proposal_v1.json"
DEFAULT_AUTHORITY_ADJUDICATIONS = (
    REPORT_ROOT
    / "stable101_authority_review_v1/stable101_authority_adjudications_v1.jsonl"
)
DEFAULT_OUTPUT_DIR = DEFAULT_REVIEW_DIR / "accepted_training_v1"

SPECIAL_TOKENS = {"<PAD>": -1, "<UNK>": -2, "<START>": -3, "<END>": -4}


@dataclass(frozen=True)
class ExportResult:
    rows: list[dict[str, Any]]
    summary: dict[str, Any]


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _load_csv(path: Path) -> list[dict[str, str]]:
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with Path(path).open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"expected JSON object at {path}:{line_number}")
            rows.append(value)
    return rows


def _index_unique(rows: list[dict[str, Any]], field: str) -> dict[int, dict[str, Any]]:
    indexed: dict[int, dict[str, Any]] = {}
    for row in rows:
        key = int(row[field])
        if key in indexed:
            raise ValueError(f"duplicate {field}: {key}")
        indexed[key] = row
    return indexed


def _parse_list(value: Any, field: str, review_index: int) -> list[Any]:
    parsed = json.loads(value) if isinstance(value, str) else value
    if not isinstance(parsed, list):
        raise ValueError(f"{field} must be a list at review_index {review_index}")
    return parsed


def _stable101_code_to_id(proposal: dict[str, Any]) -> dict[str, int]:
    code_to_id = {
        str(code): int(token)
        for code, token in (proposal.get("existing_code_to_id") or {}).items()
    }
    additions = proposal.get("proposed_code_to_id_additions") or {}
    for code, token in additions.items():
        if code in code_to_id and code_to_id[code] != int(token):
            raise ValueError(f"stable101 token conflict for {code}")
        code_to_id[str(code)] = int(token)
    if len(code_to_id) != 101 or set(code_to_id.values()) != set(range(101)):
        raise ValueError("stable101 proposal must define contiguous token IDs 0..100")
    return code_to_id


def _validate_authority(path: Path) -> None:
    accepted = {
        row.get("operator_id"): row.get("candidate_l3_code")
        for row in _load_jsonl(path)
        if row.get("decision") == "accept_taxonomy_mapping"
    }
    required = {
        "gdal:polygonize": "L3_01_09_03",
        "gdal:rasterize": "L3_01_09_03",
        "native:fixgeometries": "L3_01_05_02",
        "native:reprojectlayer": "L3_01_10_01",
    }
    if accepted != required:
        raise ValueError("stable101 authority adjudications do not match the four accepted mappings")


def _source_span(call_sites: list[dict[str, Any]]) -> dict[str, Any]:
    starts = [int(site["line_start"]) for site in call_sites]
    ends = [int(site["line_end"]) for site in call_sites]
    return {
        "line_start": min(starts),
        "line_end": max(ends),
        "call_sites": call_sites,
    }


def build_accepted_training_rows(
    *,
    review_csv_path: Path,
    adjudications_path: Path,
    salvage_ledger_path: Path,
    stable101_proposal_path: Path,
    authority_adjudications_path: Path = DEFAULT_AUTHORITY_ADJUDICATIONS,
) -> ExportResult:
    review_rows = _index_unique(_load_csv(review_csv_path), "review_index")
    adjudications = _index_unique(_load_jsonl(adjudications_path), "review_index")
    salvage_rows = _index_unique(_load_jsonl(salvage_ledger_path), "review_index")
    proposal = _load_json(stable101_proposal_path)
    code_to_id = _stable101_code_to_id(proposal)
    _validate_authority(authority_adjudications_path)

    ready_indices = sorted(
        index
        for index, row in salvage_rows.items()
        if row.get("salvage_class") == "ready_now"
    )
    if len(ready_indices) != 19:
        raise ValueError(f"expected 19 ready_now rows, got {len(ready_indices)}")

    rows: list[dict[str, Any]] = []
    for index in ready_indices:
        review = review_rows[index]
        adjudication = adjudications[index]
        salvage = salvage_rows[index]
        record_ids = {
            str(review.get("record_id")),
            str(adjudication.get("record_id")),
            str(salvage.get("record_id")),
        }
        if len(record_ids) != 1:
            raise ValueError(f"record_id mismatch at review_index {index}")
        if adjudication.get("final_decision") != "accepted":
            raise ValueError(f"ready_now row is not accepted at review_index {index}")

        source_path = Path(review["source_path"])
        if not source_path.is_file():
            raise FileNotFoundError(source_path)
        source_sha256 = _sha256(source_path)
        if source_sha256 != review.get("source_sha256"):
            raise ValueError(f"source SHA256 mismatch at review_index {index}")

        operators = [str(value) for value in _parse_list(
            review.get("ordered_operator_ids"), "ordered_operator_ids", index
        )]
        l3_codes = [str(value) for value in _parse_list(
            review.get("mapped_l3_chain"), "mapped_l3_chain", index
        )]
        call_sites = _parse_list(review.get("call_sites"), "call_sites", index)
        if not operators or len(operators) != len(l3_codes) or len(call_sites) != len(operators):
            raise ValueError(f"operator/L3/call-site length mismatch at review_index {index}")
        try:
            l3_token_ids = [code_to_id[code] for code in l3_codes]
        except KeyError as exc:
            raise ValueError(f"unmapped stable101 L3 code at review_index {index}: {exc}") from exc

        task_name = str(adjudication.get("task_name") or "").strip()
        task_description = str(adjudication.get("task_description") or "").strip()
        if not task_name or not task_description:
            raise ValueError(f"accepted row lacks reviewed task text at review_index {index}")

        record_id = record_ids.pop()
        sample_id = f"qgis_stable101_{record_id}"
        rows.append(
            {
                "schema_version": "qgis_stable101_training_sample_v1",
                "sample_id": sample_id,
                "record_id": record_id,
                "review_index": index,
                "source_root_id": review.get("source_root_id", ""),
                "source_path": str(source_path),
                "relative_path": review.get("relative_path", ""),
                "source_sha256": source_sha256,
                "source_span": _source_span(call_sites),
                "evidence_snippet": review.get("source_snippet", ""),
                "entrypoint": "source_review_scope",
                "operator_sequence": operators,
                "qgis_operator_chain": operators,
                "chain": operators,
                "l3_code_sequence": l3_codes,
                "l3_token_ids": l3_token_ids,
                "l3_sequence": [SPECIAL_TOKENS["<START>"], *l3_token_ids, SPECIAL_TOKENS["<END>"]],
                "l3_codes": ["<START>", *l3_codes, "<END>"],
                "n": len(operators),
                "task_name": task_name,
                "task_description": task_description,
                "task_type": "QGIS多步处理工作流",
                "task_metadata": {
                    "task_type": "QGIS多步处理工作流",
                    "task_name": task_name,
                    "task_description": task_description,
                },
                "workflow_scope": "human_reviewed_processing_chain",
                "dependency_edges": _parse_list(
                    review.get("dependency_edges") or "[]", "dependency_edges", index
                ),
                "dependency_status": review.get("dependency_status", ""),
                "recovery_method": "human_reviewed_source_chain",
                "known_omissions": [],
                "cluster_id": review.get("chain_key") or record_id,
                "source": "qgis_stable101_source_review",
                "_training_quality": {
                    "tier": "source_reviewed_gold_pilot",
                    "sample_weight": 1.0,
                },
                "taxonomy_profile": "stable101_report_only",
                "training_admission": "granted_train_only_pilot",
                "split": "train_only_pilot",
                "validation_eligible": False,
                "test_eligible": False,
            }
        )

    summary = {
        "schema": "gis_recommend.qgis_stable101_accepted_export_summary.v1",
        "counts": {
            "ready_now_rows": len(ready_indices),
            "exported_rows": len(rows),
            "unique_samples": len({row["sample_id"] for row in rows}),
            "unique_sources": len({row["source_sha256"] for row in rows}),
        },
        "taxonomy": {
            "profile": "stable101_report_only",
            "content_token_count": 101,
            "token_ids": {code: code_to_id[code] for code in sorted(code_to_id)},
        },
        "decision": {
            "row_admission": "granted_train_only_pilot",
            "production_merge": "not_granted",
            "validation_eligible": False,
            "test_eligible": False,
            "llm_called": False,
        },
    }
    return ExportResult(rows=rows, summary=summary)


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def _jsonl_text(rows: list[dict[str, Any]]) -> str:
    return "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for row in rows
    )


def write_outputs(result: ExportResult, output_dir: Path, input_paths: dict[str, Path]) -> dict[str, Path]:
    output_dir = Path(output_dir)
    training_jsonl = output_dir / "stable101_accepted_training_19_v1.jsonl"
    summary_path = output_dir / "stable101_accepted_training_19_summary_v1.json"
    hash_ledger_path = output_dir / "stable101_accepted_training_19_hash_ledger_v1.json"
    _atomic_write(training_jsonl, _jsonl_text(result.rows))
    _atomic_write(
        summary_path,
        json.dumps(result.summary, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "source_inputs": {
            name: {"path": str(path), "sha256": _sha256(path)}
            for name, path in sorted(input_paths.items())
        },
        "artifacts": {
            path.name: {
                "path": str(path),
                "sha256": _sha256(path),
                "bytes": path.stat().st_size,
            }
            for path in (training_jsonl, summary_path)
        },
    }
    _atomic_write(
        hash_ledger_path,
        json.dumps(ledger, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    return {
        "training_jsonl": training_jsonl,
        "summary": summary_path,
        "hash_ledger": hash_ledger_path,
    }


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-csv", type=Path, default=DEFAULT_REVIEW_CSV)
    parser.add_argument("--adjudications", type=Path, default=DEFAULT_ADJUDICATIONS)
    parser.add_argument("--salvage-ledger", type=Path, default=DEFAULT_SALVAGE_LEDGER)
    parser.add_argument("--stable101-proposal", type=Path, default=DEFAULT_STABLE101_PROPOSAL)
    parser.add_argument(
        "--authority-adjudications", type=Path, default=DEFAULT_AUTHORITY_ADJUDICATIONS
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)
    result = build_accepted_training_rows(
        review_csv_path=args.review_csv,
        adjudications_path=args.adjudications,
        salvage_ledger_path=args.salvage_ledger,
        stable101_proposal_path=args.stable101_proposal,
        authority_adjudications_path=args.authority_adjudications,
    )
    return write_outputs(
        result,
        args.output_dir,
        {
            "review_csv": args.review_csv,
            "adjudications": args.adjudications,
            "salvage_ledger": args.salvage_ledger,
            "stable101_proposal": args.stable101_proposal,
            "authority_adjudications": args.authority_adjudications,
        },
    )


if __name__ == "__main__":
    main()
