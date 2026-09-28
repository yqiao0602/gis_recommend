#!/usr/bin/env python3
"""Build a deterministic source-backed audit for GEE strict candidates.

The audit is calibration-only. It freezes a stratified sample, verifies source
hashes, replays the current deterministic extractor over ESTree ASTs, and
records chain differences without admitting or editing training rows.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import csv
from dataclasses import dataclass
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gis_recommend.data.gee_source_extractor import (  # noqa: E402
    EXTRACTOR_VERSION,
    extract_gee_source_evidence,
)
from scripts.build_gee_p4_l3_canonicalization_gate import (  # noqa: E402
    MappingEntry,
    canonicalize_operator_sequence,
    load_gee_l3_mapping,
    load_gee_operator_catalog,
)


PACKAGE_DIR = (
    ROOT
    / "docs/reports/gee_raster_core_v1_review_split_2026-07-24"
    / "gee_raster_core_batch_training_package_v1"
    / "strict_candidate_v1"
)
DEFAULT_CANDIDATE_JSON = PACKAGE_DIR / "gee_strict_candidate_v1_train3106.json"
DEFAULT_OUTPUT_DIR = PACKAGE_DIR / "source_audit_60_v1"
DEFAULT_SAMPLE_JSONL = DEFAULT_OUTPUT_DIR / "strict_candidate_audit_sample_60_v1.jsonl"
DEFAULT_SOURCE_DIR = ROOT / ".tmp_gee_strict_candidate_audit_sources_20260727"
DEFAULT_AST_DIR = ROOT / ".tmp_gee_strict_candidate_audit_ast_20260727"
DEFAULT_ID_MAPPINGS = ROOT / "outputs_v2/id_mappings_v2.json"
DEFAULT_SAMPLE_SIZE = 60
DEFAULT_SEED = "gee_strict_candidate_source_audit_v1"

AUDIT_ADMISSION = "not_granted_source_audit_calibration"
FATAL_QUALITY_FLAGS = {"dynamic_callee", "external_module_call", "recursive_helper"}
HUMAN_FIELDS = (
    "human_chain_verdict",
    "human_task_text_verdict",
    "human_l3_verdict",
    "human_final_decision",
    "human_notes",
    "adjudicated_by",
    "adjudicated_at",
)


@dataclass(frozen=True)
class StratifiedSampleResult:
    rows: list[dict[str, Any]]
    retrieval_rows: list[dict[str, Any]]
    summary: dict[str, Any]


@dataclass(frozen=True)
class SourceReplayResult:
    rows: list[dict[str, Any]]
    summary: dict[str, Any]


@dataclass(frozen=True)
class FrozenSequenceAlignment:
    status: str
    matched_frozen_indices: list[int]
    matched_replay_indices: list[int]
    window_replay_indices: list[int]
    extra_replay_indices: list[int]
    frozen_coverage: float


def _filesystem_path(path: Path) -> str:
    text = str(path)
    if os.name != "nt" or text.startswith("\\\\?\\"):
        return text
    absolute = path if path.is_absolute() else Path.cwd() / path
    text = str(absolute)
    if text.startswith("\\\\"):
        return "\\\\?\\UNC\\" + text.lstrip("\\")
    return "\\\\?\\" + text


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(_filesystem_path(Path(path)), "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    with open(_filesystem_path(Path(path)), encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return payload


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with open(_filesystem_path(Path(path)), encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{line_number} must contain a JSON object")
            rows.append(row)
    if not rows:
        raise ValueError(f"{path} contains no rows")
    return rows


def _as_string_list(value: Any) -> list[str]:
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _length_band(length: int) -> str:
    if length <= 5:
        return "short_3_5"
    if length <= 8:
        return "medium_6_8"
    return "long_9_plus"


def _operator_family(operator: str) -> str:
    parts = str(operator or "").lower().split(".")
    return ".".join(parts[:2]) if len(parts) >= 2 else str(operator or "unknown").lower()


def _source_group(source_path: str) -> str:
    parent = PurePosixPath(str(source_path or "")).parent.name
    return parent or "unknown"


def _stable_rank(seed: str, sample_id: str) -> int:
    return int(hashlib.sha256(f"{seed}:{sample_id}".encode("utf-8")).hexdigest(), 16)


def _sample_features(row: dict[str, Any], chain_counts: Counter[tuple[str, ...]]) -> dict[str, str]:
    operators = tuple(_as_string_list(row.get("operator_sequence")))
    return {
        "length_band": _length_band(len(operators)),
        "primary_operator_family": _operator_family(operators[0] if operators else "unknown"),
        "source_group": _source_group(str(row.get("source_path") or "")),
        "chain_frequency_class": "unique_chain" if chain_counts[operators] == 1 else "repeated_chain",
    }


def _validate_candidate_rows(rows: list[dict[str, Any]]) -> None:
    sample_ids = [str(row.get("sample_id") or "") for row in rows]
    source_hashes = [str(row.get("source_sha256") or "") for row in rows]
    if not all(sample_ids) or len(set(sample_ids)) != len(rows):
        raise ValueError("candidate sample_id values must be present and unique")
    if not all(source_hashes) or len(set(source_hashes)) != len(rows):
        raise ValueError("candidate source_sha256 values must be present and unique")
    for row in rows:
        if row.get("training_admission") != "not_granted_gee_strict_candidate_v1":
            raise ValueError(f"unexpected candidate admission: {row.get('sample_id')}")
        if row.get("validation_eligible") or row.get("test_eligible"):
            raise ValueError(f"validation/test eligible candidate: {row.get('sample_id')}")


def _audit_sample_row(
    row: dict[str, Any], *, audit_rank: int, selection_stage: str, features: dict[str, str]
) -> dict[str, Any]:
    operators = _as_string_list(row.get("operator_sequence"))
    l3_codes = _as_string_list(row.get("l3_code_sequence"))
    result = {
        "schema": "gis_recommend.gee_strict_candidate_audit_sample.v1",
        "audit_rank": audit_rank,
        "selection_stage": selection_stage,
        "sample_id": row.get("sample_id"),
        "proposal_id": row.get("proposal_id"),
        "script_id": row.get("script_id"),
        "source_sha256": row.get("source_sha256"),
        "source_path": row.get("source_path"),
        "source_group": features["source_group"],
        "task_type": row.get("task_type"),
        "task_name": row.get("task_name"),
        "task_description": row.get("task_description"),
        "operator_sequence": operators,
        "l3_code_sequence": l3_codes,
        "frozen_operator_sequence": operators,
        "frozen_l3_code_sequence": l3_codes,
        "length_band": features["length_band"],
        "primary_operator_family": features["primary_operator_family"],
        "chain_frequency_class": features["chain_frequency_class"],
        "training_admission": AUDIT_ADMISSION,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "training_rows_emitted": 0,
    }
    result.update({field: "" for field in HUMAN_FIELDS})
    return result


def build_stratified_sample(
    *,
    candidate_json: Path = DEFAULT_CANDIDATE_JSON,
    sample_size: int = DEFAULT_SAMPLE_SIZE,
    seed: str = DEFAULT_SEED,
) -> StratifiedSampleResult:
    payload = _load_json(candidate_json)
    candidate_rows = payload.get("labeled_workflows")
    if not isinstance(candidate_rows, list) or not candidate_rows:
        raise ValueError(f"{candidate_json} must contain non-empty labeled_workflows")
    if not all(isinstance(row, dict) for row in candidate_rows):
        raise ValueError("candidate labeled_workflows must contain JSON objects")
    _validate_candidate_rows(candidate_rows)

    task_types = sorted({str(row.get("task_type") or "Unknown") for row in candidate_rows})
    if sample_size < len(task_types):
        raise ValueError(
            f"sample_size={sample_size} cannot cover {len(task_types)} candidate task types"
        )
    if sample_size > len(candidate_rows):
        raise ValueError("sample_size exceeds candidate row count")

    chain_counts = Counter(
        tuple(_as_string_list(row.get("operator_sequence"))) for row in candidate_rows
    )
    features_by_id = {
        row["sample_id"]: _sample_features(row, chain_counts) for row in candidate_rows
    }
    by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in candidate_rows:
        by_task[str(row.get("task_type") or "Unknown")].append(row)

    selected: list[tuple[dict[str, Any], str]] = []
    selected_ids: set[str] = set()
    feature_counts: Counter[tuple[str, str]] = Counter()

    def add(row: dict[str, Any], stage: str) -> None:
        selected.append((row, stage))
        selected_ids.add(row["sample_id"])
        for key, value in features_by_id[row["sample_id"]].items():
            feature_counts[(key, value)] += 1

    for task_type in task_types:
        row = min(
            by_task[task_type],
            key=lambda item: (_stable_rank(seed, item["sample_id"]), item["sample_id"]),
        )
        add(row, "task_type_coverage")

    while len(selected) < sample_size:
        candidates = [row for row in candidate_rows if row["sample_id"] not in selected_ids]

        def diversity_key(row: dict[str, Any]) -> tuple[float, int, str]:
            features = features_by_id[row["sample_id"]]
            score = sum(1.0 / (1 + feature_counts[(key, value)]) for key, value in features.items())
            return (-score, _stable_rank(seed, row["sample_id"]), row["sample_id"])

        add(min(candidates, key=diversity_key), "diversity_fill")

    rows = [
        _audit_sample_row(
            row,
            audit_rank=index,
            selection_stage=stage,
            features=features_by_id[row["sample_id"]],
        )
        for index, (row, stage) in enumerate(selected, start=1)
    ]
    retrieval_rows = [
        {
            "schema": "gis_recommend.gee_strict_candidate_source_retrieval.v1",
            "audit_rank": row["audit_rank"],
            "sample_id": row["sample_id"],
            "remote_source_path": row["source_path"],
            "expected_sha256": row["source_sha256"],
            "local_source_filename": f"{row['source_sha256']}.txt",
            "local_ast_filename": f"{row['source_sha256']}.ast.json",
            "retrieval_status": "pending_read_only_fetch",
        }
        for row in rows
    ]
    coverage_fields = (
        "task_type",
        "length_band",
        "primary_operator_family",
        "source_group",
        "chain_frequency_class",
    )
    coverage = {
        field: dict(sorted(Counter(str(row[field]) for row in rows).items()))
        for field in coverage_fields
    }
    summary = {
        "schema": "gis_recommend.gee_strict_candidate_audit_sample_summary.v1",
        "inputs": {
            "candidate_json": str(candidate_json),
            "candidate_json_sha256": _sha256(candidate_json),
            "sample_size": sample_size,
            "seed": seed,
        },
        "counts": {
            "candidate_rows": len(candidate_rows),
            "sample_rows": len(rows),
            "candidate_task_types": len(task_types),
            "covered_task_types": len({row["task_type"] for row in rows}),
            "unique_sample_ids": len({row["sample_id"] for row in rows}),
            "unique_source_sha256": len({row["source_sha256"] for row in rows}),
            "training_rows_emitted": 0,
        },
        "coverage": coverage,
        "statistical_target": {
            "zero_failure_one_sided_confidence": 0.95,
            "zero_failure_upper_rate": 1 - (0.05 ** (1 / sample_size)),
            "report_only_after_human_adjudication": True,
        },
        "decision": {
            "training_admission": AUDIT_ADMISSION,
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
            "training_rows_emitted": 0,
            "training_run_started": False,
            "llm_used": False,
            "mutated_candidate_package": False,
        },
    }
    return StratifiedSampleResult(rows=rows, retrieval_rows=retrieval_rows, summary=summary)


def _is_subsequence(needle: list[str], haystack: list[str]) -> bool:
    iterator = iter(haystack)
    return all(any(value == candidate for candidate in iterator) for value in needle)


def _lcs_match_indices(
    frozen: list[str], replay: list[str]
) -> tuple[list[int], list[int]]:
    frozen_count = len(frozen)
    replay_count = len(replay)
    lengths = [[0] * (replay_count + 1) for _ in range(frozen_count + 1)]
    for frozen_index in range(frozen_count - 1, -1, -1):
        for replay_index in range(replay_count - 1, -1, -1):
            if frozen[frozen_index] == replay[replay_index]:
                lengths[frozen_index][replay_index] = (
                    1 + lengths[frozen_index + 1][replay_index + 1]
                )
            else:
                lengths[frozen_index][replay_index] = max(
                    lengths[frozen_index + 1][replay_index],
                    lengths[frozen_index][replay_index + 1],
                )
    matched_frozen: list[int] = []
    matched_replay: list[int] = []
    frozen_index = replay_index = 0
    while frozen_index < frozen_count and replay_index < replay_count:
        if frozen[frozen_index] == replay[replay_index]:
            matched_frozen.append(frozen_index)
            matched_replay.append(replay_index)
            frozen_index += 1
            replay_index += 1
        elif lengths[frozen_index + 1][replay_index] >= lengths[frozen_index][replay_index + 1]:
            frozen_index += 1
        else:
            replay_index += 1
    return matched_frozen, matched_replay


def align_frozen_sequence(
    frozen_sequence: list[str], replay_sequence: list[str]
) -> FrozenSequenceAlignment:
    frozen = [value.lower() for value in frozen_sequence]
    replay = [value.lower() for value in replay_sequence]
    if not frozen:
        return FrozenSequenceAlignment("empty_frozen", [], [], [], [], 1.0)

    best_match: list[int] | None = None
    for start, value in enumerate(replay):
        if value != frozen[0]:
            continue
        matched = [start]
        cursor = start + 1
        for target in frozen[1:]:
            while cursor < len(replay) and replay[cursor] != target:
                cursor += 1
            if cursor == len(replay):
                matched = []
                break
            matched.append(cursor)
            cursor += 1
        if not matched:
            continue
        if best_match is None or (matched[-1] - matched[0], matched[0]) < (
            best_match[-1] - best_match[0],
            best_match[0],
        ):
            best_match = matched

    if best_match is not None:
        window = list(range(best_match[0], best_match[-1] + 1))
        matched_set = set(best_match)
        return FrozenSequenceAlignment(
            status="complete_minimal_window",
            matched_frozen_indices=list(range(len(frozen))),
            matched_replay_indices=best_match,
            window_replay_indices=window,
            extra_replay_indices=[index for index in window if index not in matched_set],
            frozen_coverage=1.0,
        )

    matched_frozen, matched_replay = _lcs_match_indices(frozen, replay)
    window = (
        list(range(matched_replay[0], matched_replay[-1] + 1))
        if matched_replay
        else []
    )
    matched_set = set(matched_replay)
    return FrozenSequenceAlignment(
        status="partial_lcs" if matched_replay else "no_ordered_match",
        matched_frozen_indices=matched_frozen,
        matched_replay_indices=matched_replay,
        window_replay_indices=window,
        extra_replay_indices=[index for index in window if index not in matched_set],
        frozen_coverage=len(matched_frozen) / len(frozen),
    )


def classify_replay(
    frozen_sequence: list[str], replay_sequence: list[str], quality_flags: list[str]
) -> tuple[str, str]:
    frozen = [value.lower() for value in frozen_sequence]
    replay = [value.lower() for value in replay_sequence]
    if frozen == replay:
        relationship = "exact"
    elif _is_subsequence(frozen, replay):
        relationship = "frozen_subsequence_of_replay"
    elif _is_subsequence(replay, frozen):
        relationship = "replay_subsequence_of_frozen"
    else:
        relationship = "changed"
    if FATAL_QUALITY_FLAGS.intersection(quality_flags):
        return relationship, "fail_closed_extractor_quality"
    if relationship == "exact":
        return relationship, "exact_replay_pending_human_fidelity_review"
    return relationship, "fail_closed_chain_difference"


def _sequence_difference(left: list[str], right: list[str]) -> list[str]:
    remaining = Counter(value.lower() for value in left)
    difference: list[str] = []
    for value in right:
        lowered = value.lower()
        if remaining[lowered]:
            remaining[lowered] -= 1
        else:
            difference.append(lowered)
    return difference


def _resolve_ast_path(ast_dir: Path, source_sha256: str, source_path: str) -> Path | None:
    basename = PurePosixPath(source_path).name
    candidates = (
        Path(ast_dir) / f"{source_sha256}.ast.json",
        Path(ast_dir) / f"{basename}.ast.json",
        Path(ast_dir) / f"{Path(basename).stem}.ast.json",
    )
    for candidate in candidates:
        if os.path.isfile(_filesystem_path(candidate)):
            return candidate
    return None


def _empty_replay_row(row: dict[str, Any], *, status: str, reason: str) -> dict[str, Any]:
    result = {
        **row,
        "schema": "gis_recommend.gee_strict_candidate_source_replay.v1",
        "reextract_status": status,
        "fail_closed_reason": reason,
        "source_sha256_actual": "",
        "source_sha256_verified": False,
        "local_source_path": "",
        "local_ast_path": "",
        "extractor_version": EXTRACTOR_VERSION,
        "raw_replayed_core_operator_sequence": [],
        "replayed_core_operator_sequence": [],
        "replayed_l3_code_sequence": [],
        "l3_sequence_match": False,
        "skipped_raw_operators": [],
        "unmapped_raw_operators": [],
        "canonical_unmapped_l3_operators": [],
        "added_core_operators": [],
        "removed_frozen_operators": _as_string_list(row.get("frozen_operator_sequence")),
        "sequence_relationship": "not_comparable",
        "frozen_alignment_status": "not_comparable",
        "frozen_alignment_coverage": 0.0,
        "alignment_matched_frozen_indices": [],
        "alignment_matched_replay_indices": [],
        "alignment_window_replay_indices": [],
        "alignment_window_operator_sequence": [],
        "alignment_window_extra_operators": [],
        "alignment_window_call_evidence": [],
        "alignment_review_status": "fail_closed_input_error",
        "quality_flags": [],
        "core_call_evidence": [],
        "replay_disposition": "fail_closed_input_error",
        "training_admission": AUDIT_ADMISSION,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "training_rows_emitted": 0,
    }
    result.update({field: "" for field in HUMAN_FIELDS})
    return result


def _replay_row(
    row: dict[str, Any],
    *,
    source_dir: Path,
    ast_dir: Path,
    mapping: dict[str, MappingEntry],
    operator_catalog: frozenset[str],
) -> dict[str, Any]:
    source_sha256 = str(row.get("source_sha256") or "")
    source_path = Path(source_dir) / f"{source_sha256}.txt"
    if not os.path.isfile(_filesystem_path(source_path)):
        return _empty_replay_row(row, status="source_missing", reason=str(source_path))
    actual_hash = _sha256(source_path)
    if actual_hash != source_sha256:
        result = _empty_replay_row(
            row,
            status="source_hash_mismatch",
            reason=f"expected {source_sha256}, got {actual_hash}",
        )
        result["source_sha256_actual"] = actual_hash
        result["local_source_path"] = str(source_path)
        return result
    ast_path = _resolve_ast_path(ast_dir, source_sha256, str(row.get("source_path") or ""))
    if ast_path is None:
        result = _empty_replay_row(row, status="ast_missing", reason=source_sha256)
        result["source_sha256_actual"] = actual_hash
        result["source_sha256_verified"] = True
        result["local_source_path"] = str(source_path)
        return result
    try:
        with open(_filesystem_path(ast_path), encoding="utf-8") as handle:
            ast = json.load(handle)
    except (json.JSONDecodeError, OSError) as exc:
        result = _empty_replay_row(row, status="ast_invalid", reason=str(exc))
        result["source_sha256_actual"] = actual_hash
        result["source_sha256_verified"] = True
        result["local_source_path"] = str(source_path)
        result["local_ast_path"] = str(ast_path)
        return result
    try:
        evidence = extract_gee_source_evidence(
            ast,
            source_path=str(source_path),
            source_sha256=source_sha256,
        )
    except Exception as exc:  # Diagnostic audit must fail closed on extractor errors.
        result = _empty_replay_row(
            row, status="extractor_error", reason=f"{type(exc).__name__}: {exc}"
        )
        result["source_sha256_actual"] = actual_hash
        result["source_sha256_verified"] = True
        result["local_source_path"] = str(source_path)
        result["local_ast_path"] = str(ast_path)
        return result

    calls_by_ordinal = {call.ordinal: call for call in evidence.ordered_calls}
    raw_calls = [
        calls_by_ordinal[ordinal]
        for ordinal in evidence.core_operator_chain
        if ordinal in calls_by_ordinal
    ]
    raw_replayed = [str(call.raw_callee or "").strip().lower() for call in raw_calls]
    proven_ee_receivers = [
        call.resolution in {"ee_namespace", "receiver_ee_binding"}
        or raw.startswith("ee.")
        for call, raw in zip(raw_calls, raw_replayed)
    ]
    receiver_types = [call.receiver_type for call in raw_calls]
    canonicalized = canonicalize_operator_sequence(
        raw_replayed,
        mapping,
        proven_ee_receivers=proven_ee_receivers,
        receiver_types=receiver_types,
        operator_catalog=operator_catalog,
    )
    replayed = canonicalized.canonical_operator_sequence
    frozen = [value.lower() for value in _as_string_list(row.get("frozen_operator_sequence"))]
    frozen_l3 = _as_string_list(row.get("frozen_l3_code_sequence"))
    alignment = align_frozen_sequence(frozen, replayed)
    quality_flags = list(evidence.quality_flags)
    relationship, disposition = classify_replay(frozen, replayed, quality_flags)
    l3_sequence_match = canonicalized.l3_sequence == frozen_l3
    if not FATAL_QUALITY_FLAGS.intersection(quality_flags):
        if canonicalized.unmapped_raw_operators:
            disposition = "fail_closed_canonicalization_gap"
        elif canonicalized.canonical_unmapped_l3_operators:
            disposition = "fail_closed_l3_mapping_gap"
        elif relationship == "exact" and not l3_sequence_match:
            disposition = "fail_closed_l3_difference"
    if FATAL_QUALITY_FLAGS.intersection(quality_flags):
        alignment_review_status = "blocked_extractor_quality"
    elif canonicalized.unmapped_raw_operators:
        alignment_review_status = "blocked_canonicalization_gap"
    elif canonicalized.canonical_unmapped_l3_operators:
        alignment_review_status = "blocked_l3_mapping_gap"
    elif alignment.frozen_coverage < 1.0:
        alignment_review_status = "partial_source_support"
    elif alignment.extra_replay_indices:
        alignment_review_status = "complete_window_with_extra_core_steps"
    elif not l3_sequence_match:
        alignment_review_status = "exact_window_with_l3_difference"
    else:
        alignment_review_status = "exact_window_pending_human_fidelity_review"
    evidence_dict = evidence.to_dict()
    call_dicts = {
        int(call["ordinal"]): call for call in evidence_dict.get("ordered_calls", [])
    }
    canonical_call_evidence: list[dict[str, Any]] = []
    for raw_index, (call, raw_operator, receiver_is_proven_ee, receiver_type) in enumerate(
        zip(raw_calls, raw_replayed, proven_ee_receivers, receiver_types)
    ):
        single = canonicalize_operator_sequence(
            [raw_operator],
            mapping,
            proven_ee_receivers=[receiver_is_proven_ee],
            receiver_types=[receiver_type],
            operator_catalog=operator_catalog,
        )
        if not single.canonical_operator_sequence:
            continue
        canonical_call_evidence.append(
            {
                "canonical_index": len(canonical_call_evidence),
                "raw_core_index": raw_index,
                "ordered_call_ordinal": call.ordinal,
                "raw_callee": raw_operator,
                "canonical_operator": single.canonical_operator_sequence[0],
                "l3_code": single.l3_sequence[0],
                "resolution": call.resolution,
                "receiver_type": receiver_type,
                "scope": call.scope,
                "context": call.context,
                "source_location": call_dicts.get(call.ordinal, {}).get("source_location"),
            }
        )
    if [item["canonical_operator"] for item in canonical_call_evidence] != replayed:
        raise RuntimeError("call-level canonicalization diverged from replay sequence")
    matched_replay_indices = set(alignment.matched_replay_indices)
    alignment_window_call_evidence = [
        {
            **canonical_call_evidence[index],
            "alignment_role": (
                "frozen_match" if index in matched_replay_indices else "extra_core_step"
            ),
        }
        for index in alignment.window_replay_indices
    ]
    result = {
        **row,
        "schema": "gis_recommend.gee_strict_candidate_source_replay.v1",
        "reextract_status": "ok",
        "fail_closed_reason": "",
        "source_sha256_actual": actual_hash,
        "source_sha256_verified": True,
        "local_source_path": str(source_path),
        "local_ast_path": str(ast_path),
        "extractor_version": EXTRACTOR_VERSION,
        "raw_replayed_core_operator_sequence": raw_replayed,
        "replayed_core_operator_sequence": replayed,
        "replayed_l3_code_sequence": canonicalized.l3_sequence,
        "l3_sequence_match": l3_sequence_match,
        "skipped_raw_operators": canonicalized.skipped_raw_operators,
        "unmapped_raw_operators": canonicalized.unmapped_raw_operators,
        "canonical_unmapped_l3_operators": canonicalized.canonical_unmapped_l3_operators,
        "added_core_operators": _sequence_difference(frozen, replayed),
        "removed_frozen_operators": _sequence_difference(replayed, frozen),
        "sequence_relationship": relationship,
        "frozen_alignment_status": alignment.status,
        "frozen_alignment_coverage": alignment.frozen_coverage,
        "alignment_matched_frozen_indices": alignment.matched_frozen_indices,
        "alignment_matched_replay_indices": alignment.matched_replay_indices,
        "alignment_window_replay_indices": alignment.window_replay_indices,
        "alignment_window_operator_sequence": [
            replayed[index] for index in alignment.window_replay_indices
        ],
        "alignment_window_extra_operators": [
            replayed[index] for index in alignment.extra_replay_indices
        ],
        "alignment_window_call_evidence": alignment_window_call_evidence,
        "alignment_review_status": alignment_review_status,
        "quality_flags": quality_flags,
        "core_call_evidence": [
            call_dicts[ordinal]
            for ordinal in evidence.core_operator_chain
            if ordinal in call_dicts
        ],
        "ordered_call_count": len(evidence.ordered_calls),
        "core_call_count": len(replayed),
        "io_call_count": len(evidence.io_contract),
        "presentation_call_count": len(evidence.presentation_actions),
        "support_call_count": len(evidence.support_calls),
        "unresolved_call_count": len(evidence.unresolved_calls),
        "replay_disposition": disposition,
        "training_admission": AUDIT_ADMISSION,
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "training_rows_emitted": 0,
    }
    result.update({field: "" for field in HUMAN_FIELDS})
    return result


def build_source_replay(
    *,
    sample_jsonl: Path,
    source_dir: Path,
    ast_dir: Path,
    id_mappings_json: Path = DEFAULT_ID_MAPPINGS,
) -> SourceReplayResult:
    sample_rows = _load_jsonl(sample_jsonl)
    if len({row.get("sample_id") for row in sample_rows}) != len(sample_rows):
        raise ValueError("audit sample IDs must be unique")
    mapping = load_gee_l3_mapping(id_mappings_json)
    operator_catalog = load_gee_operator_catalog(id_mappings_json)
    rows = [
        _replay_row(
            row,
            source_dir=Path(source_dir),
            ast_dir=Path(ast_dir),
            mapping=mapping,
            operator_catalog=operator_catalog,
        )
        for row in sample_rows
    ]
    status_counts = Counter(row["reextract_status"] for row in rows)
    relationship_counts = Counter(row["sequence_relationship"] for row in rows)
    disposition_counts = Counter(row["replay_disposition"] for row in rows)
    quality_flag_counts = Counter(flag for row in rows for flag in row["quality_flags"])
    alignment_status_counts = Counter(row["alignment_review_status"] for row in rows)
    summary = {
        "schema": "gis_recommend.gee_strict_candidate_source_replay_summary.v1",
        "extractor_version": EXTRACTOR_VERSION,
        "inputs": {
            "sample_jsonl": str(sample_jsonl),
            "sample_jsonl_sha256": _sha256(sample_jsonl),
            "source_dir": str(source_dir),
            "ast_dir": str(ast_dir),
            "id_mappings_json": str(id_mappings_json),
            "id_mappings_json_sha256": _sha256(id_mappings_json),
        },
        "counts": {
            "sample_rows": len(sample_rows),
            "replay_rows": len(rows),
            "source_hash_verified_rows": sum(
                1 for row in rows if row["source_sha256_verified"]
            ),
            "extraction_ok_rows": status_counts.get("ok", 0),
            "exact_replay_rows": relationship_counts.get("exact", 0),
            "fail_closed_rows": sum(
                1 for row in rows if str(row["replay_disposition"]).startswith("fail_closed")
            ),
            "pending_human_fidelity_rows": disposition_counts.get(
                "exact_replay_pending_human_fidelity_review", 0
            ),
            "l3_sequence_match_rows": sum(1 for row in rows if row["l3_sequence_match"]),
            "canonicalization_gap_rows": sum(
                1 for row in rows if row["unmapped_raw_operators"]
            ),
            "l3_mapping_gap_rows": sum(
                1 for row in rows if row["canonical_unmapped_l3_operators"]
            ),
            "complete_alignment_rows": sum(
                1 for row in rows if row["frozen_alignment_coverage"] == 1.0
            ),
            "exact_alignment_window_rows": sum(
                1
                for row in rows
                if row["frozen_alignment_coverage"] == 1.0
                and not row["alignment_window_extra_operators"]
            ),
            "alignment_review_candidate_rows": sum(
                1
                for row in rows
                if row["alignment_review_status"]
                in {
                    "complete_window_with_extra_core_steps",
                    "exact_window_pending_human_fidelity_review",
                }
            ),
            "training_rows_emitted": 0,
        },
        "reextract_status_counts": dict(sorted(status_counts.items())),
        "sequence_relationship_counts": dict(sorted(relationship_counts.items())),
        "replay_disposition_counts": dict(sorted(disposition_counts.items())),
        "quality_flag_counts": dict(sorted(quality_flag_counts.items())),
        "alignment_review_status_counts": dict(sorted(alignment_status_counts.items())),
        "decision": {
            "training_admission": AUDIT_ADMISSION,
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
            "training_rows_emitted": 0,
            "training_run_started": False,
            "llm_used": False,
            "human_adjudication_complete": False,
        },
    }
    return SourceReplayResult(rows=rows, summary=summary)


def _atomic_write(path: Path, text: str) -> None:
    os.makedirs(_filesystem_path(path.parent), exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        newline="",
        dir=_filesystem_path(path.parent),
        delete=False,
    ) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    os.replace(_filesystem_path(temporary), _filesystem_path(path))


def _json_text(payload: Any) -> str:
    return json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def _jsonl_text(rows: list[dict[str, Any]]) -> str:
    return "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for row in rows
    )


def _csv_text(rows: list[dict[str, Any]]) -> str:
    if not rows:
        raise ValueError("cannot write empty audit CSV")
    fields = list(rows[0])
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow(
            {
                field: json.dumps(value, ensure_ascii=False, sort_keys=True)
                if isinstance(value, (list, dict))
                else value
                for field, value in row.items()
            }
        )
    return output.getvalue()


def _file_record(path: Path) -> dict[str, Any]:
    return {
        "path": str(path),
        "sha256": _sha256(path),
        "bytes": os.path.getsize(_filesystem_path(path)),
    }


def _write_hash_ledger(
    paths: dict[str, Path],
    source_inputs: dict[str, Path],
    *,
    grouped_source_inputs: dict[str, dict[str, Path]] | None = None,
) -> None:
    ledger_path = paths["hash_ledger"]
    source_payload: dict[str, Any] = {
        name: _file_record(path) for name, path in source_inputs.items()
    }
    for group_name, grouped_paths in (grouped_source_inputs or {}).items():
        source_payload[group_name] = {
            name: _file_record(path) for name, path in grouped_paths.items()
        }
    ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "source_inputs": source_payload,
        "artifacts": {
            path.name: {
                "path": str(path),
                "sha256": _sha256(path),
                "bytes": os.path.getsize(_filesystem_path(path)),
            }
            for key, path in paths.items()
            if key != "hash_ledger"
        },
    }
    _atomic_write(ledger_path, _json_text(ledger))


def write_sample_outputs(
    result: StratifiedSampleResult, *, output_dir: Path, candidate_json: Path
) -> dict[str, Path]:
    prefix = f"strict_candidate_audit_sample_{len(result.rows)}_v1"
    output_dir = Path(output_dir)
    paths = {
        "jsonl": output_dir / f"{prefix}.jsonl",
        "csv": output_dir / f"{prefix}.csv",
        "retrieval": output_dir / f"strict_candidate_audit_retrieval_{len(result.rows)}_v1.jsonl",
        "summary": output_dir / f"{prefix}_summary.json",
        "report": output_dir / f"{prefix}_report.md",
        "hash_ledger": output_dir / f"{prefix}_hashes.json",
    }
    _atomic_write(paths["jsonl"], _jsonl_text(result.rows))
    _atomic_write(paths["csv"], _csv_text(result.rows))
    _atomic_write(paths["retrieval"], _jsonl_text(result.retrieval_rows))
    _atomic_write(paths["summary"], _json_text(result.summary))
    counts = result.summary["counts"]
    report = "\n".join(
        [
            "# GEE Strict Candidate Audit Sample v1",
            "",
            f"- Candidate rows: {counts['candidate_rows']:,}",
            f"- Sample rows: {counts['sample_rows']}",
            f"- Covered task types: {counts['covered_task_types']}/{counts['candidate_task_types']}",
            "- Training admission: not granted",
            "- Human adjudication: pending",
            "",
            "This is a deterministic source-audit calibration sample, not a training export.",
            "",
        ]
    )
    _atomic_write(paths["report"], report)
    _write_hash_ledger(paths, {Path(candidate_json).name: Path(candidate_json)})
    return paths


def write_replay_outputs(
    result: SourceReplayResult, *, output_dir: Path, sample_jsonl: Path
) -> dict[str, Path]:
    prefix = f"strict_candidate_source_replay_{len(result.rows)}_v1"
    output_dir = Path(output_dir)
    alignment_rows: list[dict[str, Any]] = []
    for row in result.rows:
        status = row.get("alignment_review_status")
        if status not in {
            "complete_window_with_extra_core_steps",
            "exact_window_pending_human_fidelity_review",
        }:
            continue
        window_evidence = list(row.get("alignment_window_call_evidence") or [])
        frozen = _as_string_list(row.get("frozen_operator_sequence"))
        regenerated = _as_string_list(row.get("alignment_window_operator_sequence"))
        alignment_row = {
            "schema": "gis_recommend.gee_strict_candidate_alignment_review.v1",
            "audit_rank": row.get("audit_rank"),
            "sample_id": row.get("sample_id"),
            "script_id": row.get("script_id"),
            "source_sha256": row.get("source_sha256"),
            "source_path": row.get("source_path"),
            "task_type": row.get("task_type"),
            "task_name": row.get("task_name"),
            "task_description": row.get("task_description"),
            "candidate_kind": (
                "exact_window_fidelity_review"
                if status == "exact_window_pending_human_fidelity_review"
                else "regenerate_with_extra_core_steps"
            ),
            "frozen_operator_sequence": frozen,
            "frozen_l3_code_sequence": _as_string_list(
                row.get("frozen_l3_code_sequence")
            ),
            "regenerated_operator_sequence": regenerated,
            "regenerated_l3_code_sequence": [
                str(item.get("l3_code") or "") for item in window_evidence
            ],
            "extra_core_operators": _as_string_list(
                row.get("alignment_window_extra_operators")
            ),
            "window_operator_count": len(regenerated),
            "frozen_operator_count": len(frozen),
            "window_amplification_ratio": (
                len(regenerated) / len(frozen) if frozen else None
            ),
            "alignment_window_call_evidence": window_evidence,
            "alignment_review_status": status,
            "training_admission": AUDIT_ADMISSION,
            "validation_eligible": False,
            "test_eligible": False,
            "production_merge": "not_granted",
            "training_rows_emitted": 0,
        }
        alignment_row.update({field: "" for field in HUMAN_FIELDS})
        alignment_rows.append(alignment_row)
    paths = {
        "jsonl": output_dir / f"{prefix}.jsonl",
        "csv": output_dir / f"{prefix}.csv",
        "summary": output_dir / f"{prefix}_summary.json",
        "report": output_dir / f"{prefix}_report.md",
        "hash_ledger": output_dir / f"{prefix}_hashes.json",
    }
    if alignment_rows:
        paths.update(
            {
                "alignment_review_jsonl": output_dir
                / f"strict_candidate_alignment_review_{len(alignment_rows)}_v1.jsonl",
                "alignment_review_csv": output_dir
                / f"strict_candidate_alignment_review_{len(alignment_rows)}_v1.csv",
            }
        )
    _atomic_write(paths["jsonl"], _jsonl_text(result.rows))
    _atomic_write(paths["csv"], _csv_text(result.rows))
    if alignment_rows:
        _atomic_write(paths["alignment_review_jsonl"], _jsonl_text(alignment_rows))
        _atomic_write(paths["alignment_review_csv"], _csv_text(alignment_rows))
    _atomic_write(paths["summary"], _json_text(result.summary))
    counts = result.summary["counts"]
    report = "\n".join(
        [
            "# GEE Strict Candidate Source Replay v1",
            "",
            f"- Replay rows: {counts['replay_rows']}",
            f"- Source hash verified: {counts['source_hash_verified_rows']}",
            f"- Exact deterministic replay: {counts['exact_replay_rows']}",
            f"- Complete frozen-chain alignment: {counts['complete_alignment_rows']}",
            f"- Exact minimal alignment window: {counts['exact_alignment_window_rows']}",
            f"- Alignment review candidates: {counts['alignment_review_candidate_rows']}",
            f"- Canonicalization-gap rows: {counts['canonicalization_gap_rows']}",
            f"- L3-mapping-gap rows: {counts['l3_mapping_gap_rows']}",
            f"- Fail-closed rows: {counts['fail_closed_rows']}",
            f"- Pending human fidelity review: {counts['pending_human_fidelity_rows']}",
            "- Training admission: not granted",
            "",
            "Exact replay is extractor-consistency evidence, not final chain/text/L3 admission.",
            "",
        ]
    )
    _atomic_write(paths["report"], report)
    source_files = {
        Path(row["local_source_path"]).name: Path(row["local_source_path"])
        for row in result.rows
        if row.get("source_sha256_verified") and row.get("local_source_path")
    }
    ast_files = {
        Path(row["local_ast_path"]).name: Path(row["local_ast_path"])
        for row in result.rows
        if row.get("reextract_status") == "ok" and row.get("local_ast_path")
    }
    mapping_path = Path(result.summary["inputs"]["id_mappings_json"])
    _write_hash_ledger(
        paths,
        {
            Path(sample_jsonl).name: Path(sample_jsonl),
            mapping_path.name: mapping_path,
        },
        grouped_source_inputs={
            "verified_source_files": source_files,
            "verified_ast_files": ast_files,
        },
    )
    return paths


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--phase", choices=("sample", "replay"), required=True)
    parser.add_argument("--candidate-json", type=Path, default=DEFAULT_CANDIDATE_JSON)
    parser.add_argument("--sample-jsonl", type=Path, default=DEFAULT_SAMPLE_JSONL)
    parser.add_argument("--sample-size", type=int, default=DEFAULT_SAMPLE_SIZE)
    parser.add_argument("--seed", default=DEFAULT_SEED)
    parser.add_argument("--source-dir", type=Path, default=DEFAULT_SOURCE_DIR)
    parser.add_argument("--ast-dir", type=Path, default=DEFAULT_AST_DIR)
    parser.add_argument("--id-mappings-json", type=Path, default=DEFAULT_ID_MAPPINGS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)

    if args.phase == "sample":
        result = build_stratified_sample(
            candidate_json=args.candidate_json,
            sample_size=args.sample_size,
            seed=args.seed,
        )
        return write_sample_outputs(
            result, output_dir=args.output_dir, candidate_json=args.candidate_json
        )
    result = build_source_replay(
        sample_jsonl=args.sample_jsonl,
        source_dir=args.source_dir,
        ast_dir=args.ast_dir,
        id_mappings_json=args.id_mappings_json,
    )
    return write_replay_outputs(
        result, output_dir=args.output_dir, sample_jsonl=args.sample_jsonl
    )


if __name__ == "__main__":
    main()
