#!/usr/bin/env python3
"""Build a deterministic P4 operator-to-L3 canonicalization gate.

The gate consumes the 14 accepted P4 rows plus the 10 deterministic P4 rewrites.
It maps source-extracted raw GEE calls to canonical GEE operator IDs and L3
codes only when a deterministic rule and `outputs_v2/id_mappings_v2.json`
support the mapping. It does not emit training rows.
"""

from __future__ import annotations

import argparse
import csv
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import sys
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.audit_gee_training_admission import _atomic_write_text  # noqa: E402


DEFAULT_REPORT_DIR = ROOT / "docs/reports/gee_raster_core_v1_review_split_2026-07-24"
DEFAULT_P4_ADJUDICATION = DEFAULT_REPORT_DIR / "gee_p4_review_adjudication_28_v1.jsonl"
DEFAULT_P4_REWRITES = DEFAULT_REPORT_DIR / "gee_p4_rewrite_10_v1.jsonl"
DEFAULT_ID_MAPPINGS = ROOT / "outputs_v2/id_mappings_v2.json"
OUTPUT_PREFIX = "gee_p4_l3_canonicalization_gate_24_v1"

TRAINING_ADMISSION = "not_granted_pending_export_gate"


@dataclass(frozen=True)
class MappingEntry:
    canonical_operator: str
    primary_l3: str
    mapping_confidence: float | None
    has_ambiguity: bool


@dataclass(frozen=True)
class OperatorCanonicalization:
    canonical_operator_sequence: list[str]
    l3_sequence: list[str]
    skipped_raw_operators: list[str]
    unmapped_raw_operators: list[str]
    canonical_unmapped_l3_operators: list[str]
    used_old_l3_sequence: bool = False


@dataclass(slots=True)
class P4L3GateResult:
    rows: list[dict[str, Any]]
    summary: dict[str, Any]


IMAGE_METHODS = frozenset(
    {
        "abs",
        "add",
        "addbands",
        "and",
        "arrayslice",
        "bitwiseand",
        "classify",
        "clip",
        "copyproperties",
        "divide",
        "eq",
        "expression",
        "glcmtexture",
        "gt",
        "gte",
        "lt",
        "lte",
        "log",
        "mask",
        "max",
        "min",
        "multiply",
        "neq",
        "normalizeddifference",
        "not",
        "or",
        "pixelarea",
        "pow",
        "reduce",
        "reduceregion",
        "reduceregions",
        "rename",
        "reproject",
        "rightshift",
        "sample",
        "sampleregions",
        "select",
        "selfmask",
        "subtract",
        "toarray",
        "tofloat",
        "toint",
        "unmask",
        "updatemask",
        "unitscale",
        "where",
    }
)
IMAGECOLLECTION_METHODS = frozenset(
    {
        "count",
        "filter",
        "filterbounds",
        "filterdate",
        "filtermetadata",
        "first",
        "map",
        "max",
        "mean",
        "median",
        "merge",
        "min",
        "mosaic",
        "qualitymosaic",
        "select",
        "sum",
        "toarray",
        "toarrayperband",
        "tobands",
    }
)
FEATURE_METHODS = frozenset({"centroid", "get", "set"})
FEATURECOLLECTION_METHODS = frozenset(
    {
        "filter",
        "filterbounds",
        "flatten",
        "geometry",
        "merge",
        "randomcolumn",
        "select",
        "set",
        "union",
    }
)
FILTER_METHODS = frozenset(
    {
        "and",
        "calendarrange",
        "date",
        "eq",
        "gt",
        "inlist",
        "listcontains",
        "lt",
        "maxdifference",
        "not",
        "or",
    }
)
REDUCER_METHODS = frozenset({"count", "first", "max", "mean", "median", "min", "sum"})
CLASSIFIER_METHODS = frozenset({"confusionmatrix", "smilerandomforest", "train"})
GEOMETRY_METHODS = frozenset({"coveringgrid"})

SUPPORT_METHODS = frozenset(
    {
        "advance",
        "bandnames",
        "bandtypes",
        "cat",
        "date",
        "difference",
        "evaluate",
        "format",
        "fromimages",
        "getinfo",
        "getrelative",
        "imnormalize",
        "loadgeotiff",
        "int",
        "addall",
        "arraylength",
        "millis",
        "maxdifference",
        "objecttype",
        "palette",
        "parse",
        "propertynames",
        "remove",
        "size",
        "style",
        "toint32",
        "visualize",
        "copyproperties",
        "getvideothumburl",
        "id",
        "keys",
        "setdefaultworkloadtag",
        "setoutputs",
        "sort",
        "toarrayperband",
        "toimage",
        "values",
    }
)
SUPPORT_ROOTS = frozenset(
    {
        "ee.data",
        "ee.date",
        "ee.dictionary",
        "ee.geometry",
        "ee.kernel",
        "ee.list",
        "ee.number",
        "ee.string",
        "ee.algorithms.if",
    }
)


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with Path(path).open(encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            row = json.loads(line)
            if not isinstance(row, dict):
                raise ValueError(f"{path} line {line_number} must be a JSON object")
            rows.append(row)
    if not rows:
        raise ValueError(f"{path} contains no rows")
    return rows


def load_gee_l3_mapping(path: Path) -> dict[str, MappingEntry]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    gee_to_l3 = payload.get("mapping_metadata", {}).get("gee_to_l3", {})
    if not isinstance(gee_to_l3, dict) or not gee_to_l3:
        raise ValueError(f"{path} does not contain mapping_metadata.gee_to_l3")

    entries: dict[str, MappingEntry] = {}
    exact_lower_keys = {
        str(operator).strip().lower()
        for operator in gee_to_l3
        if str(operator).strip() == str(operator).strip().lower()
    }
    for operator, meta in gee_to_l3.items():
        if not isinstance(meta, dict):
            continue
        primary_l3 = str(meta.get("primary_l3") or "").strip()
        if not primary_l3 or not primary_l3.startswith("L3_"):
            continue
        normalized = str(operator).strip().lower()
        if not normalized:
            continue
        if normalized in entries and normalized in exact_lower_keys and str(operator).strip() != normalized:
            continue
        confidence = meta.get("mapping_confidence")
        entries[normalized] = MappingEntry(
            canonical_operator=normalized,
            primary_l3=primary_l3,
            mapping_confidence=float(confidence) if isinstance(confidence, (int, float)) else None,
            has_ambiguity=bool(meta.get("has_ambiguity")),
        )
    if not entries:
        raise ValueError(f"{path} contains no usable GEE->L3 entries")
    return entries


def load_gee_operator_catalog(path: Path) -> frozenset[str]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    raw_catalog = payload.get("gee_op", {})
    if not isinstance(raw_catalog, dict) or not raw_catalog:
        raise ValueError(f"{path} does not contain gee_op")
    catalog = frozenset(
        str(operator).strip().lower()
        for operator in raw_catalog
        if str(operator).strip().lower().startswith(("ee.", "export."))
    )
    if not catalog:
        raise ValueError(f"{path} contains no canonical GEE operators")
    return catalog


def _method(raw_operator: str) -> str:
    return raw_operator.rsplit(".", 1)[-1].lower()


def _has_prefix(raw_operator: str, prefix: str) -> bool:
    return raw_operator == prefix or raw_operator.startswith(prefix + ".")


def _is_support_call(raw_operator: str) -> bool:
    if raw_operator.startswith(("map.", "ui.", "chart.", "export.")):
        return True
    if any(_has_prefix(raw_operator, root) for root in SUPPORT_ROOTS):
        return True
    return _method(raw_operator) in SUPPORT_METHODS


def _candidate_keys(
    raw_operator: str,
    *,
    receiver_type: str | None = None,
    allow_family_heuristics: bool = True,
) -> list[str]:
    method = _method(raw_operator)
    candidates: list[str] = [raw_operator]

    if raw_operator.endswith(".apply") and "join" in raw_operator:
        candidates.append("ee.join.saveall")
    if "errormatrix" in raw_operator:
        candidates.append("ee.featurecollection.errormatrix")
    if method in {"accuracy", "consumersaccuracy", "producersaccuracy"}:
        candidates.append(f"ee.confusionmatrix.{method}")

    if raw_operator.startswith("ee.filter."):
        candidates.append(f"ee.filter.{method}")
    elif raw_operator.startswith("ee.reducer."):
        candidates.append(f"ee.reducer.{method}")
    elif raw_operator.startswith("ee.classifier."):
        candidates.append(f"ee.classifier.{method}")
        if method == "train":
            candidates.append("ee.classifier.train")
    elif raw_operator.startswith("ee.imagecollection."):
        candidates.append(f"ee.imagecollection.{method}")
    elif raw_operator.startswith("ee.image."):
        candidates.append(f"ee.image.{method}")
    elif raw_operator.startswith("ee.featurecollection."):
        candidates.append(f"ee.featurecollection.{method}")
    elif raw_operator.startswith("ee.feature."):
        candidates.append(f"ee.feature.{method}")

    normalized_receiver_type = str(receiver_type or "").strip().lower()
    if normalized_receiver_type.startswith("ee."):
        candidates.append(f"{normalized_receiver_type}.{method}")

    if allow_family_heuristics:
        if method in IMAGECOLLECTION_METHODS:
            candidates.append(f"ee.imagecollection.{method}")
        if method in FEATURECOLLECTION_METHODS:
            candidates.append(f"ee.featurecollection.{method}")
        if method in FEATURE_METHODS:
            candidates.append(f"ee.feature.{method}")
        if method in IMAGE_METHODS:
            candidates.append(f"ee.image.{method}")
        if method in FILTER_METHODS:
            candidates.append(f"ee.filter.{method}")
        if method in REDUCER_METHODS:
            candidates.append(f"ee.reducer.{method}")
        if method in CLASSIFIER_METHODS:
            candidates.append(f"ee.classifier.{method}")
        if method in GEOMETRY_METHODS:
            candidates.append(f"ee.geometry.point.{method}")

    deduped: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        normalized = candidate.strip().lower()
        if normalized and normalized not in seen:
            seen.add(normalized)
            deduped.append(normalized)
    return deduped


def _mapping_for_operator(
    raw_operator: str,
    mapping: dict[str, MappingEntry],
    *,
    receiver_type: str | None = None,
    allow_family_heuristics: bool = True,
) -> MappingEntry | None:
    for candidate in _candidate_keys(
        raw_operator,
        receiver_type=receiver_type,
        allow_family_heuristics=allow_family_heuristics,
    ):
        if candidate in mapping:
            return mapping[candidate]
    return None


def _unique_mapping_for_method(
    raw_operator: str,
    mapping: dict[str, MappingEntry],
    operator_catalog: frozenset[str] | None,
) -> MappingEntry | None:
    suffix = "." + _method(raw_operator)
    matches = {
        entry.canonical_operator: entry
        for key, entry in mapping.items()
        if key.endswith(suffix)
    }
    if len(matches) != 1:
        return None
    entry = next(iter(matches.values()))
    if operator_catalog is not None:
        catalog_matches = {
            operator for operator in operator_catalog if operator.endswith(suffix)
        }
        if catalog_matches != {entry.canonical_operator}:
            return None
    return entry


def _catalog_operator_for_raw(
    raw_operator: str,
    operator_catalog: frozenset[str],
    *,
    receiver_is_proven_ee: bool,
    receiver_type: str | None = None,
) -> str | None:
    if raw_operator in operator_catalog:
        return raw_operator
    if not receiver_is_proven_ee:
        return None
    suffix = "." + _method(raw_operator)
    typed_candidate = f"{str(receiver_type or '').strip().lower()}{suffix}"
    if receiver_type and typed_candidate in operator_catalog:
        return typed_candidate
    matches = [operator for operator in operator_catalog if operator.endswith(suffix)]
    return matches[0] if len(matches) == 1 else None


def canonicalize_operator_sequence(
    raw_operator_sequence: list[str],
    mapping: dict[str, MappingEntry],
    *,
    proven_ee_receivers: list[bool] | None = None,
    receiver_types: list[str | None] | None = None,
    operator_catalog: frozenset[str] | None = None,
) -> OperatorCanonicalization:
    if proven_ee_receivers is not None and len(proven_ee_receivers) != len(raw_operator_sequence):
        raise ValueError("proven_ee_receivers must align with raw_operator_sequence")
    if receiver_types is not None and len(receiver_types) != len(raw_operator_sequence):
        raise ValueError("receiver_types must align with raw_operator_sequence")
    canonical_ops: list[str] = []
    l3_sequence: list[str] = []
    skipped: list[str] = []
    unmapped: list[str] = []
    canonical_unmapped_l3: list[str] = []
    for index, raw_operator in enumerate(raw_operator_sequence):
        if not isinstance(raw_operator, str) or not raw_operator.strip():
            continue
        raw_stripped = raw_operator.strip()
        raw_normalized = raw_stripped.lower()
        receiver_type = receiver_types[index] if receiver_types is not None else None
        mapped = _mapping_for_operator(
            raw_normalized,
            mapping,
            receiver_type=receiver_type,
            allow_family_heuristics=receiver_types is None,
        )
        receiver_is_proven_ee = bool(
            proven_ee_receivers is not None and proven_ee_receivers[index]
        )
        if mapped is None and receiver_is_proven_ee:
            mapped = _unique_mapping_for_method(
                raw_normalized,
                mapping,
                operator_catalog,
            )
        if mapped is not None:
            canonical_ops.append(mapped.canonical_operator)
            l3_sequence.append(mapped.primary_l3)
            continue
        if _is_support_call(raw_normalized):
            skipped.append(raw_stripped)
            continue
        if operator_catalog:
            catalog_operator = _catalog_operator_for_raw(
                raw_normalized,
                operator_catalog,
                receiver_is_proven_ee=receiver_is_proven_ee,
                receiver_type=receiver_type,
            )
            if catalog_operator is not None:
                canonical_unmapped_l3.append(catalog_operator)
                continue
        unmapped.append(raw_stripped)
    return OperatorCanonicalization(
        canonical_operator_sequence=canonical_ops,
        l3_sequence=l3_sequence,
        skipped_raw_operators=skipped,
        unmapped_raw_operators=unmapped,
        canonical_unmapped_l3_operators=canonical_unmapped_l3,
    )


# Compatibility surface: historical callers keep importing this CLI module, while
# production data modules depend only on the stable package-level implementation.
from gis_recommend.data.gee_operator_canonicalization import (  # noqa: E402,F811
    MappingEntry,
    OperatorCanonicalization,
    canonicalize_operator_sequence,
    load_gee_l3_mapping,
    load_gee_operator_catalog,
)


def _accepted_rows(adjudication_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in adjudication_rows:
        if row.get("human_should_enter_train_only") != "yes_train_only":
            continue
        rows.append(
            {
                "review_id": row["review_id"],
                "script_id": row.get("script_id", ""),
                "source_bucket": "p4_accepted",
                "task_name": row.get("task_name", ""),
                "task_description": row.get("task_description", ""),
                "raw_operator_sequence": list(row.get("new_core_operator_sequence") or []),
                "source_sha256": row.get("source_sha256", ""),
                "source_path": row.get("source_path", ""),
                "evidence_snippet": row.get("evidence_snippet", ""),
                "known_omissions": row.get("human_known_omissions", ""),
                "quality_flags": list(row.get("quality_flags") or []),
            }
        )
    return rows


def _rewritten_rows(rewrite_rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    for row in rewrite_rows:
        rows.append(
            {
                "review_id": row["review_id"],
                "script_id": row.get("script_id", ""),
                "source_bucket": "p4_rewritten_needs_edit",
                "task_name": row.get("task_name", ""),
                "task_description": row.get("task_description", ""),
                "raw_operator_sequence": list(row.get("operator_sequence") or []),
                "source_sha256": row.get("source_sha256", ""),
                "source_path": row.get("source_path", ""),
                "evidence_snippet": row.get("evidence_snippet", ""),
                "known_omissions": row.get("known_omissions", []),
                "quality_flags": list(row.get("quality_flags") or []),
            }
        )
    return rows


def build_p4_l3_canonicalization_gate(
    *,
    p4_adjudication_jsonl_path: Path,
    p4_rewrite_jsonl_path: Path,
    id_mappings_json_path: Path,
) -> P4L3GateResult:
    adjudication_rows = _load_jsonl(p4_adjudication_jsonl_path)
    rewrite_rows = _load_jsonl(p4_rewrite_jsonl_path)
    mapping = load_gee_l3_mapping(id_mappings_json_path)

    candidates = _accepted_rows(adjudication_rows) + _rewritten_rows(rewrite_rows)
    if not candidates:
        raise ValueError("no P4 accepted or rewritten rows available for L3 canonicalization")
    if len({row["review_id"] for row in candidates}) != len(candidates):
        raise ValueError("duplicate review_id in P4 L3 canonicalization inputs")

    rows: list[dict[str, Any]] = []
    status_counter: Counter[str] = Counter()
    unmapped_counter: Counter[str] = Counter()
    skipped_counter: Counter[str] = Counter()
    for candidate in sorted(candidates, key=lambda item: item["review_id"]):
        canonicalized = canonicalize_operator_sequence(candidate["raw_operator_sequence"], mapping)
        status = (
            "l3_ready"
            if canonicalized.canonical_operator_sequence and not canonicalized.unmapped_raw_operators
            else "needs_canonicalization_rules"
        )
        status_counter[status] += 1
        unmapped_counter.update(op.lower() for op in canonicalized.unmapped_raw_operators)
        skipped_counter.update(op.lower() for op in canonicalized.skipped_raw_operators)
        rows.append(
            {
                "schema": "gis_recommend.gee_p4_l3_canonicalization_gate_row.v1",
                "review_id": candidate["review_id"],
                "script_id": candidate["script_id"],
                "source_bucket": candidate["source_bucket"],
                "task_name": candidate["task_name"],
                "task_description": candidate["task_description"],
                "raw_operator_count": len(candidate["raw_operator_sequence"]),
                "raw_operator_sequence": candidate["raw_operator_sequence"],
                "canonicalization_status": status,
                "canonical_operator_sequence": canonicalized.canonical_operator_sequence,
                "l3_sequence": canonicalized.l3_sequence,
                "skipped_raw_operators": canonicalized.skipped_raw_operators,
                "unmapped_raw_operators": canonicalized.unmapped_raw_operators,
                "used_old_l3_sequence": False,
                "source_sha256": candidate["source_sha256"],
                "source_path": candidate["source_path"],
                "evidence_snippet": candidate["evidence_snippet"],
                "known_omissions": candidate["known_omissions"],
                "quality_flags": candidate["quality_flags"],
                "training_admission": (
                    "not_granted_pending_export_gate"
                    if status == "l3_ready"
                    else "not_granted_pending_canonicalization_rules"
                ),
                "validation_eligible": False,
                "test_eligible": False,
            }
        )

    summary = {
        "schema": "gis_recommend.gee_p4_l3_canonicalization_gate_summary.v1",
        "inputs": {
            "p4_adjudication": str(Path(p4_adjudication_jsonl_path)),
            "p4_rewrites": str(Path(p4_rewrite_jsonl_path)),
            "id_mappings": str(Path(id_mappings_json_path)),
        },
        "counts": {
            "input_rows": len(rows),
            "accepted_source_rows": sum(1 for row in rows if row["source_bucket"] == "p4_accepted"),
            "rewritten_source_rows": sum(1 for row in rows if row["source_bucket"] == "p4_rewritten_needs_edit"),
            "l3_ready_rows": status_counter["l3_ready"],
            "needs_canonicalization_rules_rows": status_counter["needs_canonicalization_rules"],
            "training_rows_emitted": 0,
            "validation_rows_emitted": 0,
            "test_rows_emitted": 0,
            "unique_unmapped_raw_operators": len(unmapped_counter),
            "unique_skipped_raw_operators": len(skipped_counter),
        },
        "review_ids": [row["review_id"] for row in rows],
        "top_unmapped_raw_operators": unmapped_counter.most_common(50),
        "top_skipped_raw_operators": skipped_counter.most_common(50),
        "decision": {
            "training_admission": TRAINING_ADMISSION,
            "validation_eligible": False,
            "test_eligible": False,
            "next_gate": "export only l3_ready rows after schema and lineage validation; add rules for unmapped operators before admitting other rows",
        },
        "policy": {
            "llm_used": False,
            "old_l3_sequence_reused": False,
            "operator_order_preserved_after_skips": True,
            "support_calls_skipped": True,
            "training_rows_emitted": False,
        },
    }
    return P4L3GateResult(rows=rows, summary=summary)


def _jsonl_text(rows: list[dict[str, Any]]) -> str:
    return "".join(
        json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
        for row in rows
    )


def _csv_value(value: Any) -> Any:
    if isinstance(value, (list, dict)):
        return json.dumps(value, ensure_ascii=False, sort_keys=True)
    return value


CSV_FIELDS = (
    "review_id",
    "source_bucket",
    "canonicalization_status",
    "raw_operator_count",
    "canonical_operator_sequence",
    "l3_sequence",
    "skipped_raw_operators",
    "unmapped_raw_operators",
    "used_old_l3_sequence",
    "task_name",
    "task_description",
    "source_sha256",
    "source_path",
    "training_admission",
    "validation_eligible",
    "test_eligible",
)


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=CSV_FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: _csv_value(row.get(field, "")) for field in CSV_FIELDS})


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _render_report(summary: dict[str, Any], rows: list[dict[str, Any]]) -> str:
    lines = [
        "# GEE P4 L3 Canonicalization Gate",
        "",
        "Deterministic gate for mapping P4 source-extracted GEE calls into canonical GEE operators and L3 codes.",
        "This report emits no training rows and does not reuse old P4 lineage L3 sequences.",
        "",
        "## Summary",
        "",
        f"- Input rows: {summary['counts']['input_rows']}",
        f"- L3-ready rows: {summary['counts']['l3_ready_rows']}",
        f"- Rows needing canonicalization rules: {summary['counts']['needs_canonicalization_rules_rows']}",
        f"- Training rows emitted: {summary['counts']['training_rows_emitted']}",
        f"- Training admission: `{summary['decision']['training_admission']}`",
        "",
        "## Top unmapped raw operators",
        "",
    ]
    for operator, count in summary["top_unmapped_raw_operators"][:20]:
        lines.append(f"- {count}: `{operator}`")
    lines.extend(["", "## Rows", ""])
    for row in rows:
        lines.extend(
            [
                f"### {row['review_id']}",
                "",
                f"- Source bucket: `{row['source_bucket']}`",
                f"- Status: `{row['canonicalization_status']}`",
                f"- Raw operators: {row['raw_operator_count']}",
                f"- Canonical operators: {len(row['canonical_operator_sequence'])}",
                f"- Skipped raw operators: {len(row['skipped_raw_operators'])}",
                f"- Unmapped raw operators: {len(row['unmapped_raw_operators'])}",
                "",
            ]
        )
    return "\n".join(lines)


def write_outputs(
    result: P4L3GateResult,
    output_dir: Path,
    *,
    output_prefix: str = OUTPUT_PREFIX,
) -> dict[str, Path]:
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    csv_path = output_dir / f"{output_prefix}.csv"
    jsonl_path = output_dir / f"{output_prefix}.jsonl"
    summary_path = output_dir / f"{output_prefix}_summary.json"
    report_path = output_dir / f"{output_prefix}_report.md"
    hash_ledger_path = output_dir / f"{output_prefix}_hash_ledger.json"

    _write_csv(csv_path, result.rows)
    _atomic_write_text(jsonl_path, _jsonl_text(result.rows))
    _atomic_write_text(summary_path, json.dumps(result.summary, ensure_ascii=False, indent=2, sort_keys=True))
    _atomic_write_text(report_path, _render_report(result.summary, result.rows))

    ledger = {
        "schema": "gis_recommend.hash_ledger.v1",
        "source_inputs": {
            name: {"path": path, "sha256": _sha256(Path(path))}
            for name, path in result.summary["inputs"].items()
        },
        "artifacts": {
            csv_path.name: {"path": str(csv_path), "sha256": _sha256(csv_path), "bytes": csv_path.stat().st_size},
            jsonl_path.name: {"path": str(jsonl_path), "sha256": _sha256(jsonl_path), "bytes": jsonl_path.stat().st_size},
            summary_path.name: {"path": str(summary_path), "sha256": _sha256(summary_path), "bytes": summary_path.stat().st_size},
            report_path.name: {"path": str(report_path), "sha256": _sha256(report_path), "bytes": report_path.stat().st_size},
        },
    }
    _atomic_write_text(hash_ledger_path, json.dumps(ledger, ensure_ascii=False, indent=2, sort_keys=True))
    return {
        "csv": csv_path,
        "jsonl": jsonl_path,
        "summary": summary_path,
        "report": report_path,
        "hash_ledger": hash_ledger_path,
    }


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--p4-adjudication", type=Path, default=DEFAULT_P4_ADJUDICATION)
    parser.add_argument("--p4-rewrites", type=Path, default=DEFAULT_P4_REWRITES)
    parser.add_argument("--id-mappings", type=Path, default=DEFAULT_ID_MAPPINGS)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--output-prefix", default=OUTPUT_PREFIX)
    args = parser.parse_args(argv)

    result = build_p4_l3_canonicalization_gate(
        p4_adjudication_jsonl_path=args.p4_adjudication,
        p4_rewrite_jsonl_path=args.p4_rewrites,
        id_mappings_json_path=args.id_mappings,
    )
    return write_outputs(result, args.output_dir, output_prefix=args.output_prefix)


if __name__ == "__main__":
    main()
