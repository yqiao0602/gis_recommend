#!/usr/bin/env python3
"""Freeze hash-only exclusions for every known benchmark exposure surface."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import re
import sys
from typing import Any, Iterable
import unicodedata

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.gis_recommend.data.qgis_source_authority import source_authority


OUTPUT_NAME = "source_exclusion_ledger.jsonl"
OVERLAP_FIELDS = (
    "source_sha256",
    "normalized_source_body_sha256",
    "source_region_key",
    "call_graph_signature",
    "normalized_dag_key",
    "forbidden_near_dag_key",
    "semantic_dag_key",
    "task_text_signature",
    "task_text_token_signature",
)


@dataclass(frozen=True)
class ArtifactSpec:
    artifact_id: str
    path: str
    expected_record_count: int
    platform: str
    exposure_class: str
    data_key: str = ""
    split_path: str = ""
    default_split: str = ""
    fixed_split: bool = False


DEFAULT_ARTIFACTS = (
    ArtifactSpec(
        "gee_quality_gate_v4",
        "outputs_v2/pipeline/step8_quality_gate/labeled_workflows_l3_v4_quality_gate.json",
        76_884,
        "gee",
        "historical_train_val_test",
        data_key="labeled_workflows",
        split_path="outputs_v2/pipeline/step8_quality_gate/dataset_splits_v4_quality_gate.json",
    ),
    ArtifactSpec(
        "qgis_canonical_685",
        "outputs_v2/canonical_vector_clean_sft_seed.jsonl",
        685,
        "qgis",
        "historical_train_val_test",
        split_path="outputs_v2/pipeline/step8_qgis_vector_sft/dataset_splits_qgis_vector.json",
    ),
    ArtifactSpec(
        "qgis_vector_unified_10768",
        "outputs_v2/vector_training_samples_UNIFIED.jsonl",
        10_768,
        "qgis",
        "historical_training",
        default_split="train",
        fixed_split=True,
    ),
    ArtifactSpec(
        "qgis_api_trace_6031",
        "outputs_v2/API_trace_to_L3_TRAINING_FINAL.jsonl",
        6_031,
        "qgis",
        "historical_training",
        default_split="train",
        fixed_split=True,
    ),
    ArtifactSpec(
        "qgis_unified_train_v1_107",
        "docs/reports/qgis_unified_train_v3/qgis_unified_train_v1.jsonl",
        107,
        "qgis",
        "current_training",
        default_split="train",
        fixed_split=True,
    ),
    ArtifactSpec(
        "qgis_stable106_direct_descriptions_125",
        "docs/reports/qgis_processing_mapping_gap_stable106_v1/direct_descriptions_v1/direct_description_candidates_v1.jsonl",
        125,
        "qgis",
        "reviewed_description_exposure",
        default_split="train_or_review",
        fixed_split=True,
    ),
    ArtifactSpec(
        "gee_raster_core_train_11397",
        "docs/reports/gee_raster_core_v1_review_split_2026-07-24/gee_raster_core_batch_training_package_v1/train11397_full.json",
        11_397,
        "gee",
        "current_training",
        data_key="labeled_workflows",
        default_split="train",
        fixed_split=True,
    ),
    ArtifactSpec(
        "qgis_multistep_audit_50",
        "docs/reports/qgis_multistep_processing/pilot_v3_review_50_v2/selection.jsonl",
        50,
        "qgis",
        "human_audit",
        default_split="audit",
        fixed_split=True,
    ),
    ArtifactSpec(
        "qgis_stable101_audit_first_50",
        "docs/reports/qgis_mapping_high_impact_blockers_2026-07-24/stable101_source_review_50_v1/stable101_source_review_50_v1.jsonl",
        50,
        "qgis",
        "human_audit",
        default_split="audit",
        fixed_split=True,
    ),
    ArtifactSpec(
        "qgis_stable101_audit_second_50",
        "docs/reports/qgis_mapping_high_impact_blockers_2026-07-24/stable101_second_source_review_50_v1/stable101_source_review_50_v1.jsonl",
        50,
        "qgis",
        "human_audit",
        default_split="audit",
        fixed_split=True,
    ),
    ArtifactSpec(
        "gee_raster_core_audit_50",
        "docs/reports/gee_raster_core_v1_review_split_2026-07-24/review_50.jsonl",
        50,
        "gee",
        "human_audit",
        default_split="audit",
        fixed_split=True,
    ),
    ArtifactSpec(
        "unseen_vector_prompts_70",
        "configs/unseen_vector_prompts.jsonl",
        70,
        "qgis",
        "prompt_exposure",
        default_split="development",
        fixed_split=True,
    ),
    ArtifactSpec(
        "end_to_end_probes_50",
        "configs/end_to_end_probe_tasks_50.jsonl",
        50,
        "qgis",
        "probe_exposure",
        default_split="probe",
        fixed_split=True,
    ),
    ArtifactSpec(
        "heldout_v46_150",
        "outputs_v2/diagnostics/heldout_v46/heldout_tasks.jsonl",
        150,
        "qgis",
        "prior_evaluation",
        default_split="historical_eval",
        fixed_split=True,
    ),
    ArtifactSpec(
        "open_landing_v46_80",
        "outputs_v2/diagnostics/open_landing_v46/open_landing_tasks.jsonl",
        80,
        "qgis",
        "prior_evaluation",
        default_split="historical_eval",
        fixed_split=True,
    ),
)


def file_sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _hash_json(value: Any) -> str:
    payload = json.dumps(
        value, ensure_ascii=False, sort_keys=True, separators=(",", ":")
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _load_records(path: Path, data_key: str = "") -> list[dict[str, Any]]:
    if path.suffix.lower() == ".jsonl":
        values = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8-sig").splitlines()
            if line.strip()
        ]
    else:
        value = json.loads(path.read_text(encoding="utf-8-sig"))
        values = value[data_key] if data_key else value
    if not isinstance(values, list) or not all(isinstance(row, dict) for row in values):
        raise ValueError(f"{path} must resolve to a list of JSON objects")
    return values


def inspect_inventory(
    root: Path = ROOT, specs: Iterable[ArtifactSpec] = DEFAULT_ARTIFACTS
) -> list[dict[str, Any]]:
    rows = []
    for spec in specs:
        path = root / spec.path
        actual = len(_load_records(path, spec.data_key))
        rows.append(
            {
                "artifact_id": spec.artifact_id,
                "artifact_path": spec.path,
                "artifact_sha256": file_sha256(path),
                "platform": spec.platform,
                "exposure_class": spec.exposure_class,
                "expected_record_count": spec.expected_record_count,
                "actual_record_count": actual,
                "record_count_matches": actual == spec.expected_record_count,
            }
        )
    return rows


def _first(record: dict[str, Any], fields: Iterable[str]) -> Any:
    for field in fields:
        value = record.get(field)
        if value not in (None, "", []):
            return value
    return None


def _parse_sequence(value: Any) -> list[str]:
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return []
        try:
            value = json.loads(stripped)
        except json.JSONDecodeError:
            return [stripped]
    if not isinstance(value, (list, tuple)):
        return []
    return [str(item).strip() for item in value if str(item).strip()]


def _operators(record: dict[str, Any]) -> list[str]:
    values = _parse_sequence(
        _first(
            record,
            (
                "operator_sequence",
                "ordered_operator_ids",
                "qgis_operator_chain",
                "qgis_ops",
                "chain",
                "operator_sequence_json",
            ),
        )
    )
    return [value.lower() for value in values]


def _l3_codes(record: dict[str, Any]) -> list[str]:
    values = _parse_sequence(
        _first(
            record,
            (
                "l3_code_sequence",
                "mapped_l3_chain",
                "proposed_l3_sequence",
                "l3_steps",
                "l3_codes",
                "l3_codes_json",
            ),
        )
    )
    return [value for value in values if value not in {"<START>", "<END>"}]


def _edges(record: dict[str, Any]) -> list[tuple[int, int, str]]:
    result = []
    for edge in record.get("dependency_edges") or []:
        if isinstance(edge, dict):
            producer = edge.get("producer_ordinal", edge.get("source"))
            consumer = edge.get("consumer_ordinal", edge.get("target"))
            kind = str(edge.get("dependency_kind", edge.get("kind", "data")))
        elif isinstance(edge, (list, tuple)) and len(edge) >= 2:
            producer, consumer = edge[:2]
            kind = str(edge[2]) if len(edge) > 2 else "data"
        else:
            continue
        try:
            result.append((int(producer), int(consumer), kind))
        except (TypeError, ValueError):
            continue
    return sorted(set(result))


def _task_text(record: dict[str, Any]) -> str:
    direct = _first(record, ("task_description", "task_text", "task", "prompt"))
    if direct is not None:
        return str(direct)
    metadata = record.get("task_metadata")
    if isinstance(metadata, dict):
        return str(metadata.get("task_description", ""))
    return ""


def _task_tokens(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKC", text).lower()
    return re.findall(r"\w+", normalized, flags=re.UNICODE)


def _source_path(record: dict[str, Any], source_root: Path | None) -> Path | None:
    value = _first(record, ("source_path", "source_file"))
    if value is None:
        return None
    path = Path(str(value))
    if not path.is_absolute() and source_root is not None:
        path = source_root / path
    return path


def _source_sha(record: dict[str, Any]) -> str:
    value = _first(record, ("source_sha256", "content_sha256"))
    if value is None:
        identity = record.get("source_identity")
        if isinstance(identity, dict):
            value = _first(identity, ("source_sha256", "content_sha256", "content_hash"))
    return str(value or "").lower()


_SOURCE_CACHE: dict[tuple[str, str], tuple[str, str]] = {}


def _source_identity(
    record: dict[str, Any], source_root: Path | None
) -> tuple[str, str, str]:
    path = _source_path(record, source_root)
    stated_sha = _source_sha(record)
    if path is None or not path.is_file():
        return stated_sha, "", "sha256_only" if stated_sha else "unavailable"
    actual_sha = file_sha256(path)
    source_sha = stated_sha or actual_sha
    cache_key = (str(path.resolve()), source_sha)
    cached = _SOURCE_CACHE.get(cache_key)
    if cached is None:
        authority = source_authority(path, source_sha256=source_sha)
        cached = (authority["normalized_source_body_sha256"], actual_sha)
        _SOURCE_CACHE[cache_key] = cached
    body_sha, actual_sha = cached
    if stated_sha and stated_sha != actual_sha:
        status = "sha256_body_mismatch"
    else:
        status = "sha256_and_normalized_body"
    return source_sha, body_sha, status


def _source_region_key(record: dict[str, Any], source_sha: str) -> str:
    existing = record.get("source_region_key")
    if existing:
        return str(existing)
    span = record.get("source_span")
    call_sites = record.get("call_sites")
    if not source_sha or (not span and not call_sites):
        return ""
    return _hash_json(
        {"source_sha256": source_sha, "source_span": span, "call_sites": call_sites}
    )


def _call_graph_signature(record: dict[str, Any], source_sha: str) -> str:
    existing = _first(record, ("call_graph_signature", "call_graph_key"))
    if existing:
        return str(existing)
    call_path = record.get("call_graph_path")
    source_calls = _first(record, ("source_calls", "call_sites"))
    entrypoint = record.get("entrypoint")
    if not source_sha or (not call_path and not source_calls and not entrypoint):
        return ""
    return _hash_json(
        {
            "source_sha256": source_sha,
            "entrypoint": entrypoint,
            "call_graph_path": call_path,
            "source_calls": source_calls,
        }
    )


def _dag_keys(record: dict[str, Any]) -> tuple[str, str, str]:
    operators = _operators(record)
    codes = _l3_codes(record)
    edges = _edges(record)
    normalized = _hash_json({"operators": operators, "edges": edges}) if operators else ""
    semantic = _hash_json({"l3_codes": codes, "edges": edges}) if codes else ""
    near = ""
    if operators:
        node_count = max(
            len(operators),
            max((max(producer, consumer) + 1 for producer, consumer, _ in edges), default=0),
        )
        indegree = [0] * node_count
        outdegree = [0] * node_count
        for producer, consumer, _ in edges:
            if 0 <= producer < node_count and 0 <= consumer < node_count:
                outdegree[producer] += 1
                indegree[consumer] += 1
        near = _hash_json(
            {
                "operator_multiset": sorted(Counter(operators).items()),
                "node_count": node_count,
                "degree_shape": sorted(zip(indegree, outdegree)),
            }
        )
    return normalized, near, semantic


def fingerprint_record(
    record: dict[str, Any],
    *,
    artifact_id: str,
    record_index: int,
    platform: str = "",
    exposure_class: str = "",
    split: str = "",
    source_root: Path | None = None,
) -> dict[str, Any]:
    source_sha, body_sha, identity_status = _source_identity(record, source_root)
    normalized_dag, near_dag, semantic_dag = _dag_keys(record)
    task_tokens = _task_tokens(_task_text(record))
    return {
        "schema": "gis_recommend.qgis_benchmark_exclusion.v1",
        "record_type": "exclusion",
        "artifact_id": artifact_id,
        "record_index": int(record_index),
        "record_ref": f"{artifact_id}:{record_index}",
        "platform": platform,
        "exposure_class": exposure_class,
        "split": split,
        "exclusion_decision": "exclude_from_benchmark_candidates",
        "exclusion_reason": f"known_{exposure_class or 'exposure'}",
        "source_sha256": source_sha,
        "normalized_source_body_sha256": body_sha,
        "source_identity_status": identity_status,
        "source_region_key": _source_region_key(record, source_sha),
        "call_graph_signature": _call_graph_signature(record, source_sha),
        "normalized_dag_key": normalized_dag,
        "forbidden_near_dag_key": near_dag,
        "semantic_dag_key": semantic_dag,
        "task_text_signature": _hash_json(task_tokens) if task_tokens else "",
        "task_text_token_signature": (
            _hash_json(sorted(Counter(task_tokens).items())) if task_tokens else ""
        ),
        "record_sha256": _hash_json(record),
    }


def _split_lookup(root: Path, spec: ArtifactSpec) -> dict[int, str]:
    if not spec.split_path:
        return {}
    raw = json.loads((root / spec.split_path).read_text(encoding="utf-8-sig"))
    result: dict[int, str] = {}
    for field, split in (
        ("train_indices", "train"),
        ("val_indices", "validation"),
        ("test_indices", "test"),
    ):
        for index in raw.get(field, []):
            index = int(index)
            if index in result:
                raise ValueError(f"duplicate split index {index} in {spec.split_path}")
            result[index] = split
    return result


def _record_split(
    record: dict[str, Any], index: int, spec: ArtifactSpec, lookup: dict[int, str]
) -> str:
    if index in lookup:
        return lookup[index]
    if spec.fixed_split:
        return spec.default_split
    return str(_first(record, ("split", "source_split")) or spec.default_split)


def build_ledger(
    root: Path = ROOT, specs: Iterable[ArtifactSpec] = DEFAULT_ARTIFACTS
) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for spec in specs:
        path = root / spec.path
        records = _load_records(path, spec.data_key)
        if len(records) != spec.expected_record_count:
            raise ValueError(
                f"{spec.artifact_id} expected {spec.expected_record_count} records, "
                f"found {len(records)}"
            )
        split_lookup = _split_lookup(root, spec)
        if split_lookup and set(split_lookup) != set(range(len(records))):
            raise ValueError(f"split coverage mismatch for {spec.artifact_id}")
        rows.append(
            {
                "schema": "gis_recommend.qgis_benchmark_exclusion_artifact.v1",
                "record_type": "artifact",
                "artifact_id": spec.artifact_id,
                "artifact_path": spec.path,
                "artifact_sha256": file_sha256(path),
                "platform": spec.platform,
                "exposure_class": spec.exposure_class,
                "expected_record_count": spec.expected_record_count,
                "actual_record_count": len(records),
            }
        )
        rows.extend(
            fingerprint_record(
                record,
                artifact_id=spec.artifact_id,
                record_index=index,
                platform=spec.platform,
                exposure_class=spec.exposure_class,
                split=_record_split(record, index, spec, split_lookup),
                source_root=root,
            )
            for index, record in enumerate(records)
        )
    return rows


def build_overlap_indexes(
    rows: Iterable[dict[str, Any]],
) -> dict[str, dict[str, list[str]]]:
    indexes: dict[str, dict[str, list[str]]] = {
        field: defaultdict(list) for field in OVERLAP_FIELDS
    }
    for row in rows:
        if row.get("record_type") != "exclusion":
            continue
        record_ref = str(row.get("record_ref") or f"{row['artifact_id']}:{row['record_index']}")
        for field in OVERLAP_FIELDS:
            value = str(row.get(field, ""))
            if value:
                indexes[field][value].append(record_ref)
    return {field: dict(values) for field, values in indexes.items()}


def check_candidate_overlap(
    candidate: dict[str, Any],
    indexes: dict[str, dict[str, list[str]]],
    *,
    source_root: Path | None = None,
) -> dict[str, list[str]]:
    fingerprint = fingerprint_record(
        candidate,
        artifact_id="candidate",
        record_index=0,
        source_root=source_root,
    )
    return {
        field: indexes[field][str(fingerprint[field])]
        for field in OVERLAP_FIELDS
        if fingerprint.get(field) and str(fingerprint[field]) in indexes.get(field, {})
    }


def write_output(rows: Iterable[dict[str, Any]], output_dir: Path) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    output = output_dir / OUTPUT_NAME
    output.write_text(
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
            + "\n"
            for row in rows
        ),
        encoding="utf-8",
    )
    return output


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=ROOT / "benchmarks/qgis_planner_v1/authority",
    )
    args = parser.parse_args(argv)
    rows = build_ledger(ROOT, DEFAULT_ARTIFACTS)
    output = write_output(rows, args.output_dir)
    exclusions = sum(row["record_type"] == "exclusion" for row in rows)
    print(f"artifacts={len(rows) - exclusions} exclusions={exclusions} output={output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
