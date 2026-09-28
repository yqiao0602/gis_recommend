# -*- coding: utf-8 -*-
"""Build a quality-gated V4 training-data candidate without touching Step8."""

from __future__ import annotations

from collections import Counter, defaultdict
from copy import deepcopy
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
import re
from typing import Any, Iterable

from gis_recommend.data.training_data_quality import audit_training_data_quality


SPLIT_KEYS = ("train_indices", "val_indices", "test_indices")
SOURCE_IDENTITY_FIELDS = (
    "source_hash",
    "source_sha256",
    "content_sha256",
    "code_sha256",
    "source_group",
    "repository_id",
    "repository",
    "template_group",
)
SOURCE_IDENTITY_NAMESPACES = {
    "source_hash": "content_hash",
    "source_sha256": "content_hash",
    "content_sha256": "content_hash",
    "code_sha256": "content_hash",
    "repository_id": "repository",
    "repository": "repository",
    "source_group": "source_group",
    "template_group": "template_group",
}
DESCRIPTION_CLAIMS = {
    "export": {
        "pattern": re.compile(r"\bexport(?:s|ed|ing)?\b|\bgoogle drive\b", re.IGNORECASE),
        "operator_markers": ("export.",),
        "missing_status": "declared_unlabeled_output",
    },
    "visualization": {
        "pattern": re.compile(
            r"\bvisuali[sz](?:e|es|ed|ing|ation)\b|\bdisplay(?:s|ed|ing)?\b|\bmap layers?\b",
            re.IGNORECASE,
        ),
        "operator_markers": ("map.", "addlayer"),
        "missing_status": "declared_out_of_scope_ui",
    },
    "chart": {
        "pattern": re.compile(r"\bcharts?\b|\bplots?\b", re.IGNORECASE),
        "operator_markers": ("chart", "plot"),
        "missing_status": "declared_out_of_scope_ui",
    },
}


@dataclass(frozen=True)
class QualityGatePolicy:
    """Policy knobs for building a gated V4 training candidate."""

    min_task_count: int = 10
    rare_task_label: str = "Other / Sparse"
    sparse_task_policy: str = "merge"  # merge | filter | keep
    low_confidence_threshold: float = 0.9
    low_confidence_sources: tuple[str, ...] = ("auto_remap",)
    low_confidence_policy: str = "quarantine"  # quarantine | keep
    description_alignment_policy: str = "report"  # report | quarantine
    source_identity_policy: str = "report"  # report | require | ignore
    group_duplicate_l3_sequence: bool = True
    train_ratio: float = 0.8
    val_ratio: float = 0.1
    seed: int = 42


@dataclass
class QualityGateResult:
    candidate_workflows: list[dict[str, Any]]
    quarantined_workflows: list[dict[str, Any]]
    splits: dict[str, list[int]]
    task_vocab: dict[str, Any]
    report: dict[str, Any]
    provenance: dict[str, Any] | None = None
    authority_validation: dict[str, Any] | None = None


def _hash_json(value: Any) -> str:
    return hashlib.md5(
        json.dumps(value, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _task_type(workflow: dict[str, Any]) -> str:
    meta = workflow.get("task_metadata", {}) or {}
    return meta.get("task_type", "Unknown") or "Unknown"


def _sequence_hash(workflow: dict[str, Any]) -> str:
    return _hash_json(workflow.get("l3_sequence", []))


def _description_alignment(workflow: dict[str, Any]) -> dict[str, Any]:
    task_meta = workflow.get("task_metadata", {}) or {}
    text = " ".join(
        str(task_meta.get(key, "") or "")
        for key in ("task_name", "task_description")
    )
    operators = [
        str(operator).lower().strip()
        for operator in workflow.get("operator_sequence", [])
        if isinstance(operator, str)
    ]
    claims: list[dict[str, Any]] = []
    unsupported: list[dict[str, Any]] = []
    for claim_name, rule in DESCRIPTION_CLAIMS.items():
        if not rule["pattern"].search(text):
            continue
        matched_operators = sorted({
            operator
            for operator in operators
            if any(marker in operator for marker in rule["operator_markers"])
        })
        claim = {
            "claim": claim_name,
            "status": "matched" if matched_operators else rule["missing_status"],
            "matched_operators": matched_operators,
        }
        claims.append(claim)
        if not matched_operators:
            unsupported.append(claim)

    metadata = workflow.get("metadata", {}) or {}
    original_count = metadata.get("original_num_operators")
    current_count = len(workflow.get("operator_sequence", []))
    retention_ratio = None
    if isinstance(original_count, int) and original_count > 0:
        retention_ratio = current_count / original_count
    return {
        "claims": claims,
        "unsupported_claims": unsupported,
        "has_issue": bool(unsupported),
        "current_operator_count": current_count,
        "original_operator_count": original_count,
        "operator_retention_ratio": retention_ratio,
        "authority": "lexical_proxy",
    }


def _source_identities(workflow: dict[str, Any]) -> list[str]:
    metadata = workflow.get("metadata", {}) or {}
    identities: set[str] = set()
    for field in SOURCE_IDENTITY_FIELDS:
        value = metadata.get(field)
        if isinstance(value, str) and value.strip():
            identities.add(f"{SOURCE_IDENTITY_NAMESPACES[field]}:{value.strip()}")
    nested = metadata.get("source_identity")
    if isinstance(nested, dict):
        for field in SOURCE_IDENTITY_FIELDS:
            value = nested.get(field)
            if isinstance(value, str) and value.strip():
                identities.add(f"{SOURCE_IDENTITY_NAMESPACES[field]}:{value.strip()}")
    return sorted(identities)


def _authoritative_source_identities(workflow: dict[str, Any]) -> list[str]:
    metadata = workflow.get("metadata", {}) or {}
    authority = metadata.get("source_identity_authority")
    identities = _source_identities(workflow)
    if authority == "source_content_sha256":
        return [
            identity for identity in identities
            if identity.startswith("content_hash:")
            and re.fullmatch(r"[0-9a-fA-F]{64}", identity.split(":", 1)[1])
        ]
    if authority in {"repository_manifest", "reviewed_manifest"}:
        return identities
    return []


def audit_description_alignment(workflow: dict[str, Any]) -> dict[str, Any]:
    """Return the deterministic lexical description/chain proxy for one row."""
    return _description_alignment(workflow)


def extract_source_identities(workflow: dict[str, Any]) -> list[str]:
    """Return trusted, explicitly supplied source identities for one row."""
    return _source_identities(workflow)


def _mapping_metadata_by_operator(id_mappings: dict[str, Any] | None) -> dict[str, dict]:
    if not id_mappings:
        return {}
    gee_to_l3 = id_mappings.get("mapping_metadata", {}).get("gee_to_l3", {})
    return {str(operator).lower().strip(): meta for operator, meta in gee_to_l3.items()}


def _mapping_key_by_operator(id_mappings: dict[str, Any] | None) -> dict[str, str]:
    if not id_mappings:
        return {}
    gee_to_l3 = id_mappings.get("mapping_metadata", {}).get("gee_to_l3", {})
    return {str(operator).lower().strip(): str(operator) for operator in gee_to_l3}


def _official_names_by_operator(official_operators: Any) -> dict[str, dict[str, Any]]:
    names: dict[str, dict[str, Any]] = {}

    def visit_item(item: Any) -> None:
        if not isinstance(item, dict):
            return
        name = item.get("name")
        if not name:
            return
        names[str(name).lower().strip()] = {
            "official_name": str(name),
            "url": item.get("url"),
            "category": item.get("category"),
            "code_examples": item.get("code_examples") or [],
        }

    if isinstance(official_operators, dict):
        for value in official_operators.values():
            if isinstance(value, list):
                for item in value:
                    visit_item(item)
            else:
                visit_item(value)
    elif isinstance(official_operators, list):
        for item in official_operators:
            visit_item(item)
    return names


def audit_gee_operator_aliases(
    workflows: list[dict[str, Any]],
    id_mappings: dict[str, Any] | None,
    official_operators: Any,
) -> dict[str, Any]:
    """Compare candidate operators to v2 mapping keys and crawled official names."""
    op_counts: Counter[str] = Counter()
    for workflow in workflows:
        for operator in workflow.get("operator_sequence", []):
            if isinstance(operator, str) and operator:
                op_counts[operator.lower().strip()] += 1

    mapping_meta = _mapping_metadata_by_operator(id_mappings)
    mapping_keys = _mapping_key_by_operator(id_mappings)
    official_names = _official_names_by_operator(official_operators)

    mapping_lower_matches = 0
    official_lower_matches = 0
    exact_official_matches = 0
    exact_mapping_matches = 0
    case_display_mismatches: list[dict[str, Any]] = []
    unresolved_operators: list[dict[str, Any]] = []

    for operator, count in op_counts.items():
        mapping_key = mapping_keys.get(operator)
        mapping_meta_item = mapping_meta.get(operator, {})
        if mapping_key:
            mapping_lower_matches += 1
            if mapping_key == operator:
                exact_mapping_matches += 1

        official = official_names.get(operator)
        if official:
            official_lower_matches += 1
            if official["official_name"] == operator:
                exact_official_matches += 1
            else:
                case_display_mismatches.append(
                    {
                        "operator": operator,
                        "count": count,
                        "official_name": official["official_name"],
                        "mapping_key": mapping_key,
                        "source": mapping_meta_item.get("source"),
                        "mapping_confidence": mapping_meta_item.get("mapping_confidence"),
                        "primary_l3": mapping_meta_item.get("primary_l3"),
                    }
                )
        else:
            unresolved_operators.append(
                {
                    "operator": operator,
                    "count": count,
                    "mapping_key": mapping_key,
                    "source": mapping_meta_item.get("source"),
                    "mapping_confidence": mapping_meta_item.get("mapping_confidence"),
                    "primary_l3": mapping_meta_item.get("primary_l3"),
                }
            )

    case_display_mismatches.sort(key=lambda item: (-item["count"], item["operator"]))
    unresolved_operators.sort(key=lambda item: (-item["count"], item["operator"]))
    token_total = sum(op_counts.values())
    unresolved_token_count = sum(item["count"] for item in unresolved_operators)

    return {
        "counts": {
            "operator_tokens": token_total,
            "unique_operators": len(op_counts),
            "mapping_lower_matches": mapping_lower_matches,
            "mapping_exact_matches": exact_mapping_matches,
            "official_name_lower_matches": official_lower_matches,
            "official_name_exact_matches": exact_official_matches,
            "unresolved_official_name": len(unresolved_operators),
            "unresolved_official_tokens": unresolved_token_count,
            "unresolved_official_token_share": round(
                unresolved_token_count / max(token_total, 1), 4
            ),
        },
        "case_display_mismatches": case_display_mismatches[:100],
        "unresolved_operators": unresolved_operators[:100],
    }


def _build_task_vocab(task_types: Iterable[str]) -> dict[str, Any]:
    task_types_sorted = sorted(
        {
            task_type
            for task_type in task_types
            if task_type and task_type != "Unknown"
        }
    )
    task_type_to_id = {"Unknown": 0}
    id_to_task_type = {0: "Unknown"}
    for index, task_type in enumerate(task_types_sorted, start=1):
        task_type_to_id[task_type] = index
        id_to_task_type[index] = task_type
    return {
        "task_type_to_id": task_type_to_id,
        "id_to_task_type": {str(key): value for key, value in id_to_task_type.items()},
        "num_types": len(task_type_to_id),
    }


def _group_workflows(
    workflows: list[dict[str, Any]],
    *,
    group_duplicate_l3_sequence: bool,
    group_source_identities: bool,
) -> list[dict[str, Any]]:
    parent = list(range(len(workflows)))

    def find(index: int) -> int:
        while parent[index] != index:
            parent[index] = parent[parent[index]]
            index = parent[index]
        return index

    def union(left: int, right: int) -> None:
        left_root = find(left)
        right_root = find(right)
        if left_root != right_root:
            parent[max(left_root, right_root)] = min(left_root, right_root)

    first_by_evidence: dict[str, int] = {}
    for index, workflow in enumerate(workflows):
        evidence_keys: list[str] = []
        if group_duplicate_l3_sequence:
            evidence_keys.append(f"sequence:{_sequence_hash(workflow)}")
        if group_source_identities:
            evidence_keys.extend(f"source:{identity}" for identity in _source_identities(workflow))
        for evidence_key in evidence_keys:
            previous = first_by_evidence.setdefault(evidence_key, index)
            union(previous, index)

    groups_by_key: dict[int, dict[str, Any]] = {}
    for index, workflow in enumerate(workflows):
        root = find(index)
        group = groups_by_key.setdefault(
            root,
            {
                "group_key": "",
                "indices": [],
                "task_counts": Counter(),
                "task_set": set(),
                "size": 0,
            },
        )
        label = _task_type(workflow)
        group["indices"].append(index)
        group["task_counts"][label] += 1
        group["task_set"].add(label)
        group["size"] += 1

    groups = list(groups_by_key.values())
    for group in groups:
        group["group_key"] = "component:" + _hash_json(sorted(group["indices"]))
        primary_task, _ = group["task_counts"].most_common(1)[0]
        group["primary_task"] = primary_task
        group["task_list"] = sorted(group["task_set"])
    return groups


def _cover_train_tasks(groups: list[dict[str, Any]], task_counts: Counter[str]) -> set[str]:
    """Greedily choose groups for train so every task type is represented."""
    covered: set[str] = set()
    selected: set[str] = set()
    task_order = sorted(task_counts.items(), key=lambda item: (item[1], item[0]))

    groups_by_task: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for group in groups:
        for task_type in group["task_set"]:
            groups_by_task[task_type].append(group)

    for task_type, _ in task_order:
        if task_type in covered:
            continue
        candidates = [group for group in groups_by_task.get(task_type, []) if group["group_key"] not in selected]
        if not candidates:
            continue
        chosen = max(
            candidates,
            key=lambda group: (
                len(group["task_set"] - covered),
                len(group["task_set"]),
                group["size"],
                group["group_key"],
            ),
        )
        selected.add(chosen["group_key"])
        covered |= set(chosen["task_set"])
        if len(covered) == len(task_counts):
            break
    return selected


def _assign_groups_to_splits(
    groups: list[dict[str, Any]],
    *,
    task_counts: Counter[str],
    policy: QualityGatePolicy,
) -> dict[str, list[int]]:
    n_workflows = sum(group["size"] for group in groups)
    train_target = int(n_workflows * policy.train_ratio)
    val_target = int(n_workflows * policy.val_ratio)
    test_target = n_workflows - train_target - val_target
    target_sizes = {
        "train_indices": train_target,
        "val_indices": val_target,
        "test_indices": test_target,
    }
    split_sizes = Counter()
    split_task_counts: dict[str, Counter[str]] = defaultdict(Counter)

    selected_train_groups = _cover_train_tasks(groups, task_counts)
    selected_lookup = set(selected_train_groups)

    assignment = {
        "train_indices": [],
        "val_indices": [],
        "test_indices": [],
    }
    group_order = sorted(
        groups,
        key=lambda group: (
            -group["size"],
            -len(group["task_set"]),
            group["group_key"],
        ),
    )

    for group in group_order:
        if group["group_key"] in selected_lookup:
            split = "train_indices"
        else:
            split_scores: dict[str, float] = {}
            for candidate_split in ("train_indices", "val_indices", "test_indices"):
                target_size = max(target_sizes[candidate_split], 1)
                size_deficit = (target_sizes[candidate_split] - split_sizes[candidate_split]) / target_size
                label_deficit = 0.0
                for task_type in group["task_set"]:
                    desired = task_counts[task_type] * {
                        "train_indices": policy.train_ratio,
                        "val_indices": policy.val_ratio,
                        "test_indices": 1.0 - policy.train_ratio - policy.val_ratio,
                    }[candidate_split]
                    if desired <= 0:
                        desired = 1.0
                    label_deficit += (
                        desired - split_task_counts[candidate_split][task_type]
                    ) / desired
                label_deficit /= max(len(group["task_set"]), 1)
                split_scores[candidate_split] = 0.7 * size_deficit + 0.3 * label_deficit
            split = max(split_scores.items(), key=lambda item: (item[1], -split_sizes[item[0]], item[0]))[0]

        assignment[split].extend(group["indices"])
        split_sizes[split] += group["size"]
        for task_type, count in group["task_counts"].items():
            split_task_counts[split][task_type] += count

    return {key: sorted(indices) for key, indices in assignment.items()}


def _group_quality_annotation(
    *,
    source_index: int,
    sequence_hash: str,
    task_type_original: str,
    task_type_normalized: str,
    flags: list[str] | None = None,
    quarantine_reasons: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    annotation = {
        "source_index": source_index,
        "sequence_hash": sequence_hash,
        "task_type_original": task_type_original,
        "task_type_normalized": task_type_normalized,
    }
    if flags:
        annotation["flags"] = flags
    if quarantine_reasons:
        annotation["quarantine_reasons"] = quarantine_reasons
    return annotation


def build_quality_gate_candidate(
    workflows: list[dict[str, Any]],
    id_mappings: dict[str, Any] | None,
    policy: QualityGatePolicy | None = None,
    provenance: dict[str, Any] | None = None,
    authority_validation: dict[str, Any] | None = None,
) -> QualityGateResult:
    """Build a quality-gated V4 training candidate and grouped split."""
    policy = policy or QualityGatePolicy()
    if policy.description_alignment_policy not in {"report", "quarantine"}:
        raise ValueError(
            "description_alignment_policy must be 'report' or 'quarantine'"
        )
    if policy.source_identity_policy not in {"report", "require", "ignore"}:
        raise ValueError(
            "source_identity_policy must be 'report', 'require', or 'ignore'"
        )
    op_metadata = _mapping_metadata_by_operator(id_mappings)

    retained: list[dict[str, Any]] = []
    quarantined: list[dict[str, Any]] = []
    low_confidence_quarantine_operators: Counter[str] = Counter()
    low_confidence_quarantine_sources: Counter[str] = Counter()
    sparse_filtered: list[dict[str, Any]] = []
    sparse_merged = 0
    alignment_claim_counts: Counter[str] = Counter()
    alignment_status_counts: Counter[str] = Counter()
    alignment_issue_workflows = 0
    schema_issue_workflows = 0

    # First pass: quarantine low-confidence auto-remap workflows.
    for index, workflow in enumerate(workflows):
        wf = deepcopy(workflow)
        seq_hash = _sequence_hash(wf)
        task_type_original = _task_type(wf)
        reasons: list[dict[str, Any]] = []
        flags: list[str] = []
        alignment = _description_alignment(wf)
        for claim in alignment["claims"]:
            alignment_claim_counts[claim["claim"]] += 1
            alignment_status_counts[claim["status"]] += 1
        if alignment["has_issue"]:
            alignment_issue_workflows += 1
            flags.append("description_alignment_issue")
            if policy.description_alignment_policy == "quarantine":
                reasons.extend(
                    {
                        "reason": "description_chain_mismatch",
                        "claim": claim["claim"],
                        "status": claim["status"],
                    }
                    for claim in alignment["unsupported_claims"]
                )
        operators = wf.get("operator_sequence", [])
        confidences = wf.get("confidences", [])
        ambiguity_flags = wf.get("ambiguity_flags", [])
        content_codes = [
            code for code in wf.get("l3_codes", [])
            if not (isinstance(code, str) and code.startswith("<"))
        ]
        content_ids = [token for token in wf.get("l3_sequence", []) if isinstance(token, int) and token >= 0]
        field_lengths = {
            "operators": len(operators),
            "confidences": len(confidences),
            "ambiguity_flags": len(ambiguity_flags),
            "l3_codes": len(content_codes),
            "l3_ids": len(content_ids),
        }
        if len(set(field_lengths.values())) != 1:
            reasons.append({
                "reason": "schema_length_mismatch",
                "field_lengths": field_lengths,
            })
        missing_mapping_operators = sorted({
            operator
            for operator in operators
            if isinstance(operator, str) and operator.lower().strip() not in op_metadata
        })
        for operator in missing_mapping_operators:
            reasons.append({
                "reason": "mapping_metadata_missing",
                "operator": operator,
            })
        if any(reason.get("reason") in {"schema_length_mismatch", "mapping_metadata_missing"} for reason in reasons):
            schema_issue_workflows += 1
        for operator_index, operator in enumerate(operators):
            if not isinstance(operator, str):
                continue
            meta = op_metadata.get(operator.lower().strip())
            if not meta:
                continue
            if operator_index >= len(confidences):
                continue
            confidence = confidences[operator_index]
            source = meta.get("source", "unknown")
            if (
                source in policy.low_confidence_sources
                and isinstance(confidence, (int, float))
                and confidence < policy.low_confidence_threshold
            ):
                reasons.append(
                    {
                        "operator": operator,
                        "source": source,
                        "confidence": float(confidence),
                        "primary_l3": meta.get("primary_l3"),
                    }
                )
                low_confidence_quarantine_operators[operator.lower().strip()] += 1
                low_confidence_quarantine_sources[source] += 1

        has_low_confidence_reasons = any(reason.get("operator") for reason in reasons)
        has_description_reasons = any(
            reason.get("reason") == "description_chain_mismatch" for reason in reasons
        )
        has_schema_reasons = any(
            reason.get("reason") in {"schema_length_mismatch", "mapping_metadata_missing"}
            for reason in reasons
        )
        should_quarantine = (
            has_low_confidence_reasons and policy.low_confidence_policy == "quarantine"
        ) or (
            has_description_reasons
            and policy.description_alignment_policy == "quarantine"
        ) or has_schema_reasons
        if should_quarantine:
            annotation = _group_quality_annotation(
                source_index=index,
                sequence_hash=seq_hash,
                task_type_original=task_type_original,
                task_type_normalized=task_type_original,
                flags=flags,
                quarantine_reasons=reasons,
            )
            annotation["description_alignment"] = alignment
            annotation["source_identities"] = _source_identities(wf)
            wf["quality_gate"] = annotation
            quarantined.append(wf)
            continue

        if has_low_confidence_reasons:
            flags.append("low_confidence_kept")
        annotation = _group_quality_annotation(
            source_index=index,
            sequence_hash=seq_hash,
            task_type_original=task_type_original,
            task_type_normalized=task_type_original,
            flags=flags,
        )
        annotation["description_alignment"] = alignment
        annotation["source_identities"] = _source_identities(wf)
        wf["quality_gate"] = annotation
        retained.append(wf)

    pre_merge_task_counts = Counter(_task_type(workflow) for workflow in retained)

    # Second pass: sparse task handling.
    candidate: list[dict[str, Any]] = []
    for workflow in retained:
        task_type_original = _task_type(workflow)
        normalized_task_type = task_type_original
        flags = list(workflow.get("quality_gate", {}).get("flags", []))
        quality_gate = dict(workflow.get("quality_gate", {}))
        if pre_merge_task_counts[task_type_original] < policy.min_task_count:
            if policy.sparse_task_policy == "filter":
                sparse_filtered.append(workflow)
                continue
            if policy.sparse_task_policy == "merge":
                normalized_task_type = policy.rare_task_label
                sparse_merged += 1
                flags.append("sparse_task_merged")
                task_meta = deepcopy(workflow.get("task_metadata", {}) or {})
                task_meta["quality_gate_original_task_type"] = task_type_original
                task_meta["task_type"] = normalized_task_type
                workflow["task_metadata"] = task_meta

        quality_gate["task_type_normalized"] = normalized_task_type
        if flags:
            quality_gate["flags"] = sorted(set(flags))
        workflow["quality_gate"] = quality_gate
        candidate.append(workflow)

    candidate_task_counts = Counter(_task_type(workflow) for workflow in candidate)
    candidate_task_vocab = _build_task_vocab(candidate_task_counts.keys())
    missing_declared_source_indices = [
        index for index, workflow in enumerate(candidate)
        if not _source_identities(workflow)
    ]
    missing_authoritative_source_indices = [
        index for index, workflow in enumerate(candidate)
        if not _authoritative_source_identities(workflow)
    ]
    if missing_authoritative_source_indices and policy.source_identity_policy == "require":
        first = candidate[missing_authoritative_source_indices[0]]
        script_id = (first.get("metadata", {}) or {}).get("script_id", "unknown")
        raise ValueError(
            "Authoritative source identity is required but missing for "
            f"{len(missing_authoritative_source_indices)} candidate workflows; first={script_id}"
        )
    groups = _group_workflows(
        candidate,
        group_duplicate_l3_sequence=policy.group_duplicate_l3_sequence,
        group_source_identities=policy.source_identity_policy != "ignore",
    )
    splits = _assign_groups_to_splits(
        groups,
        task_counts=candidate_task_counts,
        policy=policy,
    )

    candidate_audit = audit_training_data_quality(candidate, splits, id_mappings=id_mappings)

    split_lookup = {}
    for split_name, key in (("train", "train_indices"), ("val", "val_indices"), ("test", "test_indices")):
        for index in splits[key]:
            split_lookup[index] = split_name

    seq_split_map: dict[str, set[str]] = defaultdict(set)
    for index, workflow in enumerate(candidate):
        seq_split_map[_sequence_hash(workflow)].add(split_lookup.get(index, "unsplit"))
    cross_split_sequence_hashes = sum(
        1 for split_names in seq_split_map.values()
        if len(split_names & {"train", "val", "test"}) > 1
    )

    source_split_map: dict[str, set[str]] = defaultdict(set)
    authoritative_source_split_map: dict[str, set[str]] = defaultdict(set)
    source_field_counts: Counter[str] = Counter()
    for index, workflow in enumerate(candidate):
        for identity in _source_identities(workflow):
            source_split_map[identity].add(split_lookup.get(index, "unsplit"))
            source_field_counts[identity.split(":", 1)[0]] += 1
        for identity in _authoritative_source_identities(workflow):
            authoritative_source_split_map[identity].add(split_lookup.get(index, "unsplit"))
    cross_split_source_identities = sum(
        1 for split_names in source_split_map.values()
        if len(split_names & {"train", "val", "test"}) > 1
    )
    cross_split_authoritative_source_identities = sum(
        1 for split_names in authoritative_source_split_map.values()
        if len(split_names & {"train", "val", "test"}) > 1
    )

    quarantine_task_counts = Counter(_task_type(workflow) for workflow in quarantined)
    quarantine_operator_counts = Counter()
    quarantine_sources = Counter()
    low_confidence_quarantined_workflows = 0
    description_quarantined_workflows = 0
    schema_quarantined_workflows = 0
    for workflow in quarantined:
        has_low_confidence = False
        has_description_issue = False
        has_schema_issue = False
        for reason in workflow.get("quality_gate", {}).get("quarantine_reasons", []):
            if reason.get("operator"):
                has_low_confidence = True
                quarantine_operator_counts[reason["operator"]] += 1
                quarantine_sources[reason.get("source", "unknown")] += 1
            if reason.get("reason") == "description_chain_mismatch":
                has_description_issue = True
            if reason.get("reason") in {"schema_length_mismatch", "mapping_metadata_missing"}:
                has_schema_issue = True
        low_confidence_quarantined_workflows += int(has_low_confidence)
        description_quarantined_workflows += int(has_description_issue)
        schema_quarantined_workflows += int(has_schema_issue)

    split_sizes = {
        key: len(splits[key])
        for key in SPLIT_KEYS
    }
    total_split_rows = max(1, sum(split_sizes.values()))

    report = {
        "policy": asdict(policy),
        "counts": {
            "input_workflows": len(workflows),
            "candidate_workflows": len(candidate),
            "quarantined_workflows": len(quarantined),
            "sparse_filtered_workflows": len(sparse_filtered),
            "sparse_merged_workflows": sparse_merged,
            "task_types_before": len(pre_merge_task_counts),
            "task_types_after": len(candidate_task_counts),
        },
        "task_distribution": {
            "before": dict(pre_merge_task_counts),
            "after": dict(candidate_task_counts),
            "quarantine": dict(quarantine_task_counts),
            "top_after": candidate_task_counts.most_common(20),
        },
        "low_confidence_quarantine": {
            "operators": quarantine_operator_counts.most_common(50),
            "sources": dict(quarantine_sources),
            "threshold": policy.low_confidence_threshold,
            "policy_sources": list(policy.low_confidence_sources),
        },
        "description_alignment": {
            "policy": policy.description_alignment_policy,
            "authority": "lexical_proxy",
            "workflows_with_issues": alignment_issue_workflows,
            "quarantined_workflows": description_quarantined_workflows,
            "claims": dict(alignment_claim_counts),
            "statuses": dict(alignment_status_counts),
        },
        "schema_quarantine": {
            "workflows": schema_quarantined_workflows,
            "detected_workflows": schema_issue_workflows,
        },
        "source_identity": {
            "policy": policy.source_identity_policy,
            "candidate_workflows": len(candidate),
            "declared_workflows": len(candidate) - len(missing_declared_source_indices),
            "declared_missing_workflows": len(missing_declared_source_indices),
            "authoritative_workflows": len(candidate) - len(missing_authoritative_source_indices),
            "missing_workflows": len(missing_authoritative_source_indices),
            "identity_field_occurrences": dict(source_field_counts),
            "unique_identities": len(source_split_map),
            "source_disjoint_verified": (
                policy.source_identity_policy != "ignore"
                and not missing_authoritative_source_indices
                and cross_split_authoritative_source_identities == 0
            ),
        },
        "splits": {
            "train_indices": len(splits["train_indices"]),
            "val_indices": len(splits["val_indices"]),
            "test_indices": len(splits["test_indices"]),
            "cross_split_sequence_hashes": cross_split_sequence_hashes,
            "cross_split_source_identities": cross_split_source_identities,
            "cross_split_authoritative_source_identities": cross_split_authoritative_source_identities,
            "actual_ratios": {
                key: split_sizes[key] / total_split_rows
                for key in SPLIT_KEYS
            },
            "max_group_size": max((group["size"] for group in groups), default=0),
            "val_tasks_not_in_train": candidate_audit["split_quality"]["val_tasks_not_in_train"],
            "test_tasks_not_in_train": candidate_audit["split_quality"]["test_tasks_not_in_train"],
        },
        "candidate_audit": candidate_audit,
        "notes": {
            "group_duplicate_l3_sequence": policy.group_duplicate_l3_sequence,
            "sparse_filtered_workflows": len(sparse_filtered),
            "low_confidence_quarantined_workflows": low_confidence_quarantined_workflows,
            "description_quarantined_workflows": description_quarantined_workflows,
        },
    }

    return QualityGateResult(
        candidate_workflows=candidate,
        quarantined_workflows=quarantined,
        splits=splits,
        task_vocab=candidate_task_vocab,
        report=report,
        provenance=provenance,
        authority_validation=authority_validation,
    )


def _render_markdown_report(
    result: QualityGateResult,
    candidate_path: Path,
    quarantine_path: Path,
    split_path: Path,
    task_vocab_path: Path,
) -> str:
    report = result.report
    audit = report["candidate_audit"]
    lines = [
        "# V4 Quality Gate Candidate",
        "",
        f"Candidate: `{candidate_path}`",
        f"Quarantine: `{quarantine_path}`",
        f"Splits: `{split_path}`",
        f"Task vocab: `{task_vocab_path}`",
        "",
        "## Summary",
        "",
        f"- Input workflows: {report['counts']['input_workflows']:,}",
        f"- Candidate workflows: {report['counts']['candidate_workflows']:,}",
        f"- Quarantined workflows: {report['counts']['quarantined_workflows']:,}",
        f"- Sparse merged workflows: {report['counts']['sparse_merged_workflows']:,}",
        f"- Sparse filtered workflows: {report['counts']['sparse_filtered_workflows']:,}",
        f"- Task types before: {report['counts']['task_types_before']}",
        f"- Task types after: {report['counts']['task_types_after']}",
        f"- Cross-split duplicate sequence hashes: {report['splits']['cross_split_sequence_hashes']}",
        f"- Cross-split source identities: {report['splits']['cross_split_source_identities']}",
        f"- Workflows missing trusted source identity: {report['source_identity']['missing_workflows']:,}",
        f"- Source-disjoint verified: {report['source_identity']['source_disjoint_verified']}",
        f"- Description alignment issues: {report['description_alignment']['workflows_with_issues']:,}",
        "",
        "## Candidate Audit",
        "",
        f"- Warnings: {', '.join(audit['warnings']) if audit['warnings'] else 'none'}",
        f"- Top10 L3 share: {audit['l3_distribution']['top10_share']:.2%}",
        f"- Top20 L3 share: {audit['l3_distribution']['top20_share']:.2%}",
        f"- Task types with <10 samples: {audit['task_distribution']['tasks_lt_10']}",
        f"- Low-confidence tokens (<0.9): {audit['confidence']['low_confidence_tokens']:,}",
        "",
        "## Low-Confidence Quarantine",
        "",
    ]
    for operator, count in report["low_confidence_quarantine"]["operators"][:30]:
        lines.append(f"- `{operator}`: {count}")
    if not report["low_confidence_quarantine"]["operators"]:
        lines.append("- none")

    lines.extend(["", "## Description Alignment Proxy", ""])
    lines.append(f"- Policy: {report['description_alignment']['policy']}")
    lines.append(f"- Authority: {report['description_alignment']['authority']}")
    for claim, count in sorted(report["description_alignment"]["claims"].items()):
        lines.append(f"- `{claim}` claims: {count:,}")

    lines.extend(["", "## Source Identity", ""])
    lines.append(f"- Policy: {report['source_identity']['policy']}")
    lines.append(f"- Unique trusted identities: {report['source_identity']['unique_identities']:,}")
    lines.append(f"- Missing workflows: {report['source_identity']['missing_workflows']:,}")
    lines.append(
        f"- Source-disjoint verified: {report['source_identity']['source_disjoint_verified']}"
    )

    lines.extend(["", "## Split Tasks Not in Train", ""])
    if report["splits"]["val_tasks_not_in_train"]:
        lines.append("Val-only:")
        for task in report["splits"]["val_tasks_not_in_train"]:
            lines.append(f"- {task}")
    if report["splits"]["test_tasks_not_in_train"]:
        lines.append("Test-only:")
        for task in report["splits"]["test_tasks_not_in_train"]:
            lines.append(f"- {task}")
    if not report["splits"]["val_tasks_not_in_train"] and not report["splits"]["test_tasks_not_in_train"]:
        lines.append("- none")
    return "\n".join(lines) + "\n"


def write_quality_gate_outputs(
    result: QualityGateResult,
    out_dir: Path | str,
    *,
    data_filename: str = "labeled_workflows_l3_v4_quality_gate.json",
    quarantine_filename: str = "quarantined_workflows_l3_v4_quality_gate.json",
    split_filename: str = "dataset_splits_v4_quality_gate.json",
    task_vocab_filename: str = "task_type_vocabulary_v4_quality_gate.json",
    report_json_filename: str = "quality_gate_report.json",
    report_md_filename: str = "quality_gate_report.md",
) -> dict[str, Path]:
    """Write the gated candidate outputs and return their paths."""
    out_path = Path(out_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    data_path = out_path / data_filename
    quarantine_path = out_path / quarantine_filename
    split_path = out_path / split_filename
    task_vocab_path = out_path / task_vocab_filename
    report_json_path = out_path / report_json_filename
    report_md_path = out_path / report_md_filename

    data_payload = {
        "num_workflows": len(result.candidate_workflows),
        "labeled_workflows": result.candidate_workflows,
        "statistics": result.report["counts"],
        "quality_gate": result.report,
        "provenance": result.provenance,
        "authority_validation": result.authority_validation,
    }
    quarantine_payload = {
        "num_workflows": len(result.quarantined_workflows),
        "labeled_workflows": result.quarantined_workflows,
        "statistics": {
            "quarantined_workflows": len(result.quarantined_workflows),
            "sources": result.report["low_confidence_quarantine"]["sources"],
        },
        "quality_gate": {
            "policy": result.report["policy"],
            "sources": result.report["low_confidence_quarantine"]["sources"],
        },
        "provenance": result.provenance,
        "authority_validation": result.authority_validation,
    }

    with data_path.open("w", encoding="utf-8") as f:
        json.dump(data_payload, f, ensure_ascii=False, indent=2)
    with quarantine_path.open("w", encoding="utf-8") as f:
        json.dump(quarantine_payload, f, ensure_ascii=False, indent=2)
    with split_path.open("w", encoding="utf-8") as f:
        json.dump(result.splits, f, ensure_ascii=False, indent=2)
    with task_vocab_path.open("w", encoding="utf-8") as f:
        json.dump(result.task_vocab, f, ensure_ascii=False, indent=2)
    with report_json_path.open("w", encoding="utf-8") as f:
        json.dump(result.report, f, ensure_ascii=False, indent=2)
    with report_md_path.open("w", encoding="utf-8") as f:
        f.write(
            _render_markdown_report(
                result,
                data_path,
                quarantine_path,
                split_path,
                task_vocab_path,
            )
        )

    return {
        "data": data_path,
        "quarantine": quarantine_path,
        "splits": split_path,
        "task_vocab": task_vocab_path,
        "report_json": report_json_path,
        "report_md": report_md_path,
    }
