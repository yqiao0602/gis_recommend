#!/usr/bin/env python3
"""Build the chain-level review candidate pool unlocked by stable101.

This is a report-only triage step. It consumes the stable101 impact records and
the immutable QGIS chain dataset, keeps only records newly completed by the four
adjudicated stable101 mappings, deduplicates to chain representatives, and
exports a balanced next-review batch.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable, Iterable


SCHEMA_VERSION = "gis_recommend.qgis_stable101_candidate_pool.v1"
NEWLY_COMPLETE_STAGE = "newly_complete_stablen_conservative"
TRAINING_ADMISSION = "not_granted"
TAXONOMY_ADMISSION = "granted_for_four_stable101_mappings"
STABLE101_OPERATORS = [
    "gdal:polygonize",
    "gdal:rasterize",
    "native:fixgeometries",
    "native:reprojectlayer",
]


def _read_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            value = json.loads(line)
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{line_number} must contain a JSON object")
            rows.append(value)
    return rows


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(text, encoding="utf-8")
    temporary.replace(path)


def _write_json(path: Path, value: Any) -> None:
    _atomic_write_text(
        path,
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    _atomic_write_text(
        path,
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
    )


def _csv_value(value: Any) -> Any:
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


def _write_csv(path: Path, rows: list[dict[str, Any]], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    with temporary.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field, "")) for field in fieldnames})
    temporary.replace(path)


def _normalize_ops(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    return [str(item).strip().lower() for item in value if str(item).strip()]


def source_repo(task_text: str) -> str:
    match = re.search(r"\bSource repo:\s*(.+?)\s*$", task_text or "")
    if not match:
        return ""
    return re.sub(r"\s+", " ", match.group(1)).strip()


def task_seed_text(task_text: str) -> str:
    text = str(task_text or "").strip()
    match = re.search(r"\bSource repo:\s*.+?\s*$", text)
    if match:
        text = text[: match.start()]
    text = re.sub(r"^[/*\s#-]+", "", text).strip()
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def task_text_quality(task_text: str) -> str:
    seed = task_seed_text(task_text)
    if len(seed) < 18:
        return "weak_short_or_empty"
    if "processing.run" in seed or "Traceback" in seed:
        return "weak_code_fragment"
    if re.match(r"^(author|copyright|license|created by)\b", seed, re.IGNORECASE):
        return "weak_metadata"
    if re.search(r"\b(import|from)\s+(qgis|processing|os|sys)\b", seed, re.IGNORECASE):
        return "weak_code_import"
    if re.match(
        r"^(init|initalgorithm|name|fetchmessage|addadvancedparameter|norm|get layer|"
        r"add layer to project|class |def )\b",
        seed,
        re.IGNORECASE,
    ):
        return "weak_symbol_or_method"
    if len(seed.split()) < 3:
        return "weak_too_few_words"
    return "usable_seed_text"


def modality(quality: dict[str, Any]) -> str:
    if quality.get("is_pure_vector"):
        return "pure_vector"
    if quality.get("is_pure_raster"):
        return "pure_raster"
    return "mixed"


def repeated_operator_ids(ops: list[str]) -> list[str]:
    return sorted(operator_id for operator_id, count in Counter(ops).items() if count > 1)


def _risk_flags(row: dict[str, Any]) -> list[str]:
    flags: list[str] = []
    if row["task_text_quality"] != "usable_seed_text":
        flags.append(row["task_text_quality"])
    if row["chain_frequency"] >= 10:
        flags.append("high_duplicate_chain_frequency")
    if row["record_sha_duplicate_count"] > 1:
        flags.append("duplicate_record_hash")
    if row["repeated_operator_ids"]:
        flags.append("repeated_operator_ids")
    if row["chain_length"] > 8:
        flags.append("long_chain_gt8")
    if row["modality"] == "pure_raster":
        flags.append("pure_raster_low_count")
    return flags


def _priority_score(row: dict[str, Any]) -> float:
    score = 0.0
    if row["task_text_quality"] == "usable_seed_text":
        score += 30.0
    else:
        score -= 8.0
    score += min(14.0, math.log2(float(row["chain_frequency"]) + 1.0) * 4.0)
    if 3 <= row["chain_length"] <= 8:
        score += 6.0
    elif row["chain_length"] == 2:
        score += 3.0
    else:
        score -= 3.0
    if len(row["proposal_ops_present"]) > 1:
        score += 6.0
    if any(op in row["proposal_ops_present"] for op in ("gdal:polygonize", "gdal:rasterize")):
        score += 4.0
    if row["modality"] == "pure_vector":
        score += 4.0
    elif row["modality"] == "mixed":
        score += 3.0
    if not row["repeated_operator_ids"]:
        score += 2.0
    return round(score, 6)


def _quality_rank(row: dict[str, Any]) -> tuple[int, int, int, int]:
    text_rank = {
        "usable_seed_text": 4,
        "weak_too_few_words": 2,
        "weak_symbol_or_method": 1,
        "weak_code_fragment": 0,
        "weak_short_or_empty": 0,
        "weak_code_import": 0,
        "weak_metadata": 0,
    }.get(row["task_text_quality"], 0)
    no_duplicate_rank = 1 if row["record_sha_duplicate_count"] == 1 else 0
    no_repeated_rank = 1 if not row["repeated_operator_ids"] else 0
    return (text_rank, no_duplicate_rank, no_repeated_rank, -int(row["record_index"]))


def enrich_newly_complete_records(
    impact_rows: list[dict[str, Any]],
    chain_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    new_rows = [
        dict(row)
        for row in impact_rows
        if row.get("impact_stage") == NEWLY_COMPLETE_STAGE
    ]
    sha_counts = Counter(str(row.get("record_sha256", "")) for row in new_rows)
    chain_counts = Counter(tuple(_normalize_ops(row.get("qgis_ops", []))) for row in new_rows)

    enriched: list[dict[str, Any]] = []
    for row in new_rows:
        record_index = int(row["record_index"])
        if record_index < 1 or record_index > len(chain_rows):
            raise ValueError(f"record_index out of range: {record_index}")
        chain_row = chain_rows[record_index - 1]
        ops = _normalize_ops(row.get("qgis_ops", []))
        if ops != _normalize_ops(chain_row.get("qgis_ops", [])):
            raise ValueError(f"qgis_ops mismatch at record_index {record_index}")
        quality = chain_row.get("quality", {})
        if not isinstance(quality, dict):
            quality = {}
        enriched_row = {
            **row,
            "chain_key": " -> ".join(ops),
            "chain_frequency": chain_counts[tuple(ops)],
            "chain_length": len(ops),
            "modality": modality(quality),
            "record_sha_duplicate_count": sha_counts[str(row.get("record_sha256", ""))],
            "repeated_operator_ids": repeated_operator_ids(ops),
            "source": chain_row.get("source", ""),
            "source_repo": source_repo(str(row.get("task_text", ""))),
            "task_seed_text": task_seed_text(str(row.get("task_text", ""))),
            "task_text_quality": task_text_quality(str(row.get("task_text", ""))),
            "training_targets": chain_row.get("training_targets", []),
            "quality": quality,
            "review_pool_status": "chain_level_candidate_after_stable101",
            "taxonomy_admission": TAXONOMY_ADMISSION,
            "training_admission": TRAINING_ADMISSION,
        }
        enriched_row["risk_flags"] = _risk_flags(enriched_row)
        enriched_row["review_priority_score"] = _priority_score(enriched_row)
        enriched.append(enriched_row)
    return enriched


def build_unique_chain_pool(enriched_records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in enriched_records:
        grouped[row["chain_key"]].append(row)

    representatives: list[dict[str, Any]] = []
    for chain_key, rows in grouped.items():
        chosen = sorted(rows, key=lambda row: _quality_rank(row), reverse=True)[0]
        representative = {
            "chain_key": chain_key,
            "representative_record_index": chosen["record_index"],
            "representative_record_sha256": chosen["record_sha256"],
            "representative_source": chosen["source"],
            "source_repo": chosen["source_repo"],
            "task_seed_text": chosen["task_seed_text"],
            "task_text": chosen.get("task_text", ""),
            "task_text_quality": chosen["task_text_quality"],
            "qgis_ops": chosen["qgis_ops"],
            "operator_names": chosen.get("operator_names", []),
            "proposal_ops_present": chosen["proposal_ops_present"],
            "proposed_l3_sequence": chosen["proposed_l3_sequence"],
            "stable98_unresolved_ops": chosen["stable98_unresolved_ops"],
            "chain_frequency": len(rows),
            "unique_record_sha_count": len({row["record_sha256"] for row in rows}),
            "chain_length": chosen["chain_length"],
            "modality": chosen["modality"],
            "repeated_operator_ids": chosen["repeated_operator_ids"],
            "risk_flags": chosen["risk_flags"],
            "review_priority_score": chosen["review_priority_score"],
            "taxonomy_admission": TAXONOMY_ADMISSION,
            "training_admission": TRAINING_ADMISSION,
            "review_pool_status": "unique_chain_candidate_after_stable101",
        }
        representatives.append(representative)
    return sorted(
        representatives,
        key=lambda row: (-float(row["review_priority_score"]), row["chain_key"]),
    )


def _repo_cap(repo: str, default_cap: int) -> int:
    return max(default_cap, 5) if not repo else default_cap


def select_next_review_batch(
    chain_pool: list[dict[str, Any]],
    *,
    batch_size: int,
    max_per_source_repo: int,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    selected_keys: set[str] = set()
    source_counts: Counter[str] = Counter()

    strata: list[tuple[str, Callable[[dict[str, Any]], bool], int]] = [
        (
            "multi_stable101_operator_combo",
            lambda row: len(row["proposal_ops_present"]) > 1,
            12,
        ),
        (
            "single_polygonize_representative",
            lambda row: row["proposal_ops_present"] == ["gdal:polygonize"],
            10,
        ),
        (
            "single_rasterize_representative",
            lambda row: row["proposal_ops_present"] == ["gdal:rasterize"],
            8,
        ),
        (
            "single_fixgeometries_representative",
            lambda row: row["proposal_ops_present"] == ["native:fixgeometries"],
            10,
        ),
        (
            "single_reprojectlayer_representative",
            lambda row: row["proposal_ops_present"] == ["native:reprojectlayer"],
            10,
        ),
    ]

    def pick(
        stratum: str,
        predicate: Callable[[dict[str, Any]], bool],
        quota: int,
        *,
        enforce_source_cap: bool,
    ) -> None:
        nonlocal selected
        candidates = [row for row in chain_pool if predicate(row)]
        for row in candidates:
            if len([item for item in selected if item["selection_stratum"] == stratum]) >= quota:
                return
            if len(selected) >= batch_size:
                return
            chain_key = str(row["chain_key"])
            if chain_key in selected_keys:
                continue
            repo = str(row.get("source_repo") or "")
            if enforce_source_cap and source_counts[repo] >= _repo_cap(repo, max_per_source_repo):
                continue
            selected_row = dict(row)
            selected_row["selection_stratum"] = stratum
            selected_row["selection_rationale"] = [
                "newly_complete_after_stable101",
                "unique_chain_representative",
                "balanced_operator_quota",
            ]
            selected.append(selected_row)
            selected_keys.add(chain_key)
            source_counts[repo] += 1

    for stratum, predicate, quota in strata:
        pick(stratum, predicate, quota, enforce_source_cap=True)
        pick(stratum, predicate, quota, enforce_source_cap=False)

    if len(selected) < batch_size:
        for row in chain_pool:
            if len(selected) >= batch_size:
                break
            chain_key = str(row["chain_key"])
            if chain_key in selected_keys:
                continue
            selected_row = dict(row)
            selected_row["selection_stratum"] = "diversity_fill"
            selected_row["selection_rationale"] = [
                "newly_complete_after_stable101",
                "unique_chain_representative",
                "fill_to_batch_size",
            ]
            selected.append(selected_row)
            selected_keys.add(chain_key)

    for index, row in enumerate(selected, start=1):
        row["review_index"] = index
        row["human_source_retrieval_ready"] = ""
        row["human_workflow_boundary_decision"] = ""
        row["human_operator_identity_order_decision"] = ""
        row["human_dependency_decision"] = ""
        row["human_task_text_usable"] = ""
        row["human_description_generation_ready"] = ""
        row["human_training_candidate_ready"] = ""
        row["human_notes"] = ""
        row["reviewer"] = ""
        row["reviewed_at"] = ""
    return selected


def _count_values(rows: list[dict[str, Any]], field: str) -> dict[str, int]:
    return dict(sorted(Counter(str(row.get(field, "")) for row in rows).items()))


def summarize(
    *,
    impact_rows: list[dict[str, Any]],
    enriched_records: list[dict[str, Any]],
    chain_pool: list[dict[str, Any]],
    next_batch: list[dict[str, Any]],
    impact_summary: dict[str, Any] | None,
    input_sha256: dict[str, str],
) -> dict[str, Any]:
    chain_frequency = Counter(row["chain_key"] for row in enriched_records)
    top_duplicate_chains = [
        {"chain_key": chain_key, "record_count": count}
        for chain_key, count in chain_frequency.most_common(15)
    ]
    summary = {
        "schema": SCHEMA_VERSION,
        "status": "candidate_pool_built",
        "input_sha256": input_sha256,
        "impact_row_count": len(impact_rows),
        "newly_complete_record_count": len(enriched_records),
        "newly_complete_unique_record_sha256_count": len(
            {row["record_sha256"] for row in enriched_records}
        ),
        "newly_complete_unique_chain_count": len(chain_pool),
        "next_review_batch_count": len(next_batch),
        "source_join_required_for_full_manual_review_csv": True,
        "record_text_quality_counts": _count_values(enriched_records, "task_text_quality"),
        "chain_text_quality_counts": _count_values(chain_pool, "task_text_quality"),
        "record_modality_counts": _count_values(enriched_records, "modality"),
        "chain_modality_counts": _count_values(chain_pool, "modality"),
        "next_batch_modality_counts": _count_values(next_batch, "modality"),
        "next_batch_text_quality_counts": _count_values(next_batch, "task_text_quality"),
        "record_proposal_combo_counts": dict(
            sorted(
                Counter(",".join(row["proposal_ops_present"]) for row in enriched_records).items()
            )
        ),
        "chain_proposal_combo_counts": dict(
            sorted(Counter(",".join(row["proposal_ops_present"]) for row in chain_pool).items())
        ),
        "next_batch_proposal_combo_counts": dict(
            sorted(Counter(",".join(row["proposal_ops_present"]) for row in next_batch).items())
        ),
        "next_batch_selection_stratum_counts": _count_values(next_batch, "selection_stratum"),
        "top_duplicate_chains": top_duplicate_chains,
        "taxonomy_admission": TAXONOMY_ADMISSION,
        "training_admission": TRAINING_ADMISSION,
        "notes": [
            "All newly complete records are chain-level review candidates only.",
            "The next-review batch is deduplicated by ordered QGIS operator chain.",
            "Source snippets are not present in qgis_chain_dataset.jsonl; a server provenance join is required before final human CSV review.",
            "No production mapping or training export is emitted.",
        ],
    }
    if impact_summary:
        summary["stable101_impact_context"] = {
            "stable98_complete_records": impact_summary.get("stable98_draft", {}).get("complete_records"),
            "stable98_complete_unique_chains": impact_summary.get("stable98_draft", {}).get("complete_unique_chains"),
            "stable101_complete_records": impact_summary.get("stablen_conservative_draft", {}).get("complete_records"),
            "stable101_complete_unique_chains": impact_summary.get("stablen_conservative_draft", {}).get("complete_unique_chains"),
            "increment_records": impact_summary.get("increment_vs_stable98", {}).get("records"),
            "increment_unique_chains": impact_summary.get("increment_vs_stable98", {}).get("unique_chains"),
        }
    return summary


def _markdown(summary: dict[str, Any], next_batch: list[dict[str, Any]]) -> str:
    lines = [
        "# QGIS stable101 Newly Complete Candidate Pool",
        "",
        "This report re-evaluates the multi-step Processing candidate pool after the four stable101 mappings were adjudicated. It is chain-level triage only: no `outputs_v2` production mapping, training export, LLM description generation, or model training is performed.",
        "",
        "## Summary",
        "",
        f"- Newly complete records: {summary['newly_complete_record_count']}",
        f"- Unique record hashes: {summary['newly_complete_unique_record_sha256_count']}",
        f"- Unique ordered chains: {summary['newly_complete_unique_chain_count']}",
        f"- Recommended next-review batch: {summary['next_review_batch_count']} unique chain representatives",
        f"- Source snippet join required before full manual review CSV: {summary['source_join_required_for_full_manual_review_csv']}",
        f"- Taxonomy admission: `{summary['taxonomy_admission']}`",
        f"- Training admission: `{summary['training_admission']}`",
        "",
        "## Chain Pool Shape",
        "",
        "| dimension | counts |",
        "|---|---|",
        f"| record modality | `{json.dumps(summary['record_modality_counts'], ensure_ascii=False, sort_keys=True)}` |",
        f"| unique-chain modality | `{json.dumps(summary['chain_modality_counts'], ensure_ascii=False, sort_keys=True)}` |",
        f"| next-batch modality | `{json.dumps(summary['next_batch_modality_counts'], ensure_ascii=False, sort_keys=True)}` |",
        f"| record task-text quality | `{json.dumps(summary['record_text_quality_counts'], ensure_ascii=False, sort_keys=True)}` |",
        f"| unique-chain task-text quality | `{json.dumps(summary['chain_text_quality_counts'], ensure_ascii=False, sort_keys=True)}` |",
        f"| next-batch task-text quality | `{json.dumps(summary['next_batch_text_quality_counts'], ensure_ascii=False, sort_keys=True)}` |",
        f"| next batch strata | `{json.dumps(summary['next_batch_selection_stratum_counts'], ensure_ascii=False, sort_keys=True)}` |",
        "",
        "## Recommended Next Review Batch",
        "",
        "| # | stratum | chain frequency | modality | stable101 ops | ordered QGIS chain | task seed |",
        "|---:|---|---:|---|---|---|---|",
    ]
    for row in next_batch:
        task = str(row.get("task_seed_text", "")).replace("|", "/")[:90]
        lines.append(
            f"| {row['review_index']} | {row['selection_stratum']} | {row['chain_frequency']} | "
            f"{row['modality']} | `{', '.join(row['proposal_ops_present'])}` | "
            f"`{row['chain_key']}` | {task} |"
        )
    lines.extend(
        [
            "",
            "## Admission Boundary",
            "",
            "- The 179 unique chains can enter chain-level human review.",
            "- The 50-row batch is a balanced first slice, not a training set.",
            "- Before actual manual source review, join each representative back to `/home/yll` provenance and embed source snippets.",
            "- Before training export, require chain-level human approval plus faithful task-description generation.",
            "",
        ]
    )
    return "\n".join(lines)


def build_candidate_pool(
    *,
    impact_records_path: Path,
    chain_dataset_path: Path,
    output_dir: Path,
    impact_summary_path: Path | None = None,
    batch_size: int = 50,
    max_per_source_repo: int = 3,
) -> dict[str, Any]:
    impact_rows = _read_jsonl(impact_records_path)
    chain_rows = _read_jsonl(chain_dataset_path)
    impact_summary = _read_json(impact_summary_path) if impact_summary_path else None

    enriched_records = enrich_newly_complete_records(impact_rows, chain_rows)
    chain_pool = build_unique_chain_pool(enriched_records)
    next_batch = select_next_review_batch(
        chain_pool,
        batch_size=batch_size,
        max_per_source_repo=max_per_source_repo,
    )
    input_sha256 = {
        "impact_records": _sha256(impact_records_path),
        "chain_dataset": _sha256(chain_dataset_path),
    }
    if impact_summary_path:
        input_sha256["impact_summary"] = _sha256(impact_summary_path)
    summary = summarize(
        impact_rows=impact_rows,
        enriched_records=enriched_records,
        chain_pool=chain_pool,
        next_batch=next_batch,
        impact_summary=impact_summary,
        input_sha256=input_sha256,
    )

    output_dir.mkdir(parents=True, exist_ok=True)
    records_path = output_dir / "stable101_newly_complete_records_v1.jsonl"
    chain_pool_jsonl = output_dir / "stable101_unique_chain_pool_v1.jsonl"
    chain_pool_csv = output_dir / "stable101_unique_chain_pool_v1.csv"
    batch_jsonl = output_dir / "stable101_next_review_candidates_50_v1.jsonl"
    batch_csv = output_dir / "stable101_next_review_candidates_50_v1.csv"
    summary_path = output_dir / "stable101_candidate_pool_summary_v1.json"
    report_path = output_dir / "stable101_candidate_pool_report_v1.md"
    manifest_path = output_dir / "stable101_candidate_pool_manifest_v1.json"

    _write_jsonl(records_path, enriched_records)
    _write_jsonl(chain_pool_jsonl, chain_pool)
    pool_fields = [
        "chain_key",
        "representative_record_index",
        "chain_frequency",
        "unique_record_sha_count",
        "chain_length",
        "modality",
        "task_text_quality",
        "source_repo",
        "proposal_ops_present",
        "qgis_ops",
        "proposed_l3_sequence",
        "risk_flags",
        "review_priority_score",
        "task_seed_text",
    ]
    _write_csv(chain_pool_csv, chain_pool, pool_fields)
    batch_fields = [
        "review_index",
        "selection_stratum",
        "selection_rationale",
        "representative_record_index",
        "representative_record_sha256",
        "chain_frequency",
        "unique_record_sha_count",
        "chain_length",
        "modality",
        "source_repo",
        "task_text_quality",
        "proposal_ops_present",
        "qgis_ops",
        "proposed_l3_sequence",
        "stable98_unresolved_ops",
        "repeated_operator_ids",
        "risk_flags",
        "review_priority_score",
        "task_seed_text",
        "task_text",
        "taxonomy_admission",
        "training_admission",
        "human_source_retrieval_ready",
        "human_workflow_boundary_decision",
        "human_operator_identity_order_decision",
        "human_dependency_decision",
        "human_task_text_usable",
        "human_description_generation_ready",
        "human_training_candidate_ready",
        "human_notes",
        "reviewer",
        "reviewed_at",
    ]
    _write_jsonl(batch_jsonl, next_batch)
    _write_csv(batch_csv, next_batch, batch_fields)
    _write_json(summary_path, summary)
    _atomic_write_text(report_path, _markdown(summary, next_batch))

    artifact_paths = {
        "newly_complete_records": records_path,
        "unique_chain_pool_jsonl": chain_pool_jsonl,
        "unique_chain_pool_csv": chain_pool_csv,
        "next_review_batch_jsonl": batch_jsonl,
        "next_review_batch_csv": batch_csv,
        "summary": summary_path,
        "report": report_path,
    }
    manifest = {
        "schema": f"{SCHEMA_VERSION}.manifest",
        "status": "candidate_pool_built",
        "input_sha256": input_sha256,
        "artifacts": {name: str(path) for name, path in artifact_paths.items()},
        "artifact_sha256": {name: _sha256(path) for name, path in artifact_paths.items()},
        "taxonomy_admission": TAXONOMY_ADMISSION,
        "training_admission": TRAINING_ADMISSION,
    }
    _write_json(manifest_path, manifest)
    summary["manifest_sha256"] = _sha256(manifest_path)
    return summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--impact-records", required=True, type=Path)
    parser.add_argument("--chain-dataset", required=True, type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--impact-summary", type=Path)
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--max-per-source-repo", type=int, default=3)
    args = parser.parse_args()
    summary = build_candidate_pool(
        impact_records_path=args.impact_records,
        chain_dataset_path=args.chain_dataset,
        impact_summary_path=args.impact_summary,
        output_dir=args.output_dir,
        batch_size=args.batch_size,
        max_per_source_repo=args.max_per_source_repo,
    )
    print(
        "stable101_candidate_pool records={records} unique_chains={chains} next_batch={batch}".format(
            records=summary["newly_complete_record_count"],
            chains=summary["newly_complete_unique_chain_count"],
            batch=summary["next_review_batch_count"],
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
