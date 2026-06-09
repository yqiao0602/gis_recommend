#!/usr/bin/env python3
"""Analyze MRV expansion outputs by equivalence family and risk.

This script is read-only with respect to MRV labels: it does not train, mutate
checkpoints, promote candidates into the manual registry, or change validator
decisions. QGIS landing failures are reported only as auxiliary transferability
signals.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable, Sequence


ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from gis_recommend.config.transformer_config import OUTPUT_DIR  # noqa: E402


SCHEMA_VERSION = "gis_recommend.v4_qg.mrv_expansion_analysis.v1"
DEFAULT_INPUT_DIR = OUTPUT_DIR / "v4_qg_multiref_validation_expansion_500"
DEFAULT_INPUT_JSONL = DEFAULT_INPUT_DIR / "generated_variants.jsonl"
DEFAULT_HIERARCHY_PATH = OUTPUT_DIR / "classification_hierarchy_v2.csv"
DEFAULT_L3_VOCAB_PATH = OUTPUT_DIR / "l3_vocab_v2.json"
DEFAULT_TAXONOMY_PATH = ROOT / "configs" / "equivalence_taxonomy.yaml"


DEFAULT_TAXONOMY: dict = {
    "schema_version": "gis_recommend.workflow_equivalence_taxonomy.v1",
    "token_classes": {
        "25": "clip",
        "28": "select_bands",
        "29": "mask",
        "31": "reducer_or_statistics",
        "34": "arithmetic",
        "35": "threshold_or_logic",
        "39": "projection",
        "40": "mosaic_or_merge",
        "50": "temporal_filter",
        "53": "metadata_filter",
        "54": "spatial_filter",
        "56": "temporal_reducer",
        "83": "smoothing_filter",
        "90": "temporal_aggregation",
        "92": "feature_stacking",
    },
    "class_groups": {
        "collection_filters": ["temporal_filter", "metadata_filter", "spatial_filter"],
        "selection": ["select_bands"],
        "spatial_subset": ["clip"],
        "pixelwise_compute": ["arithmetic", "threshold_or_logic"],
        "mask_or_threshold": ["mask", "threshold_or_logic"],
        "reducers_or_aggregation": ["reducer_or_statistics", "temporal_reducer", "temporal_aggregation"],
        "high_risk_sensitive": [
            "projection",
            "mask",
            "threshold_or_logic",
            "reducer_or_statistics",
            "temporal_reducer",
            "temporal_aggregation",
        ],
    },
    "families": {
        "filter_filter": {
            "risk_level": "low",
            "constraints": ["independent_collection_filters", "same_collection_scope"],
            "hidden_dependencies": [],
            "risk_drivers": [],
        },
        "select_filter": {
            "risk_level": "medium",
            "constraints": ["select_does_not_drop_filter_property", "filter_applies_to_same_object_scope"],
            "hidden_dependencies": ["collection_image_boundary", "metadata_property_dependency"],
            "risk_drivers": ["band_or_metadata_scope"],
        },
        "select_clip": {
            "risk_level": "medium",
            "constraints": ["clip_geometry_independent_of_selected_bands", "selection_preserves_bands_used_downstream"],
            "hidden_dependencies": ["downstream_band_dependency"],
            "risk_drivers": ["band_availability"],
        },
        "clip_arithmetic": {
            "risk_level": "medium_high",
            "constraints": ["pixelwise_operation_extent_invariant", "no_region_dependent_reducer_between_steps"],
            "hidden_dependencies": ["spatial_extent_dependency", "raster_alignment_dependency"],
            "risk_drivers": ["extent_sensitive_compute"],
        },
        "mask_threshold_or_logic": {
            "risk_level": "high",
            "constraints": ["manually_verify_mask_threshold_order"],
            "hidden_dependencies": ["mask_semantics_dependency", "threshold_dependency"],
            "risk_drivers": ["mask_or_threshold_semantics"],
        },
        "reducer_or_aggregation": {
            "risk_level": "high",
            "constraints": ["manually_verify_reducer_domain"],
            "hidden_dependencies": ["reducer_domain_dependency", "temporal_window_dependency"],
            "risk_drivers": ["aggregation_semantics"],
        },
        "high_risk_sensitive": {
            "risk_level": "high",
            "constraints": ["manual_source_inspection_required"],
            "hidden_dependencies": [
                "crs_or_projection_dependency",
                "nodata_or_mask_dependency",
                "temporal_or_aggregation_dependency",
            ],
            "risk_drivers": ["sensitive_operation"],
        },
        "other": {
            "risk_level": "unknown",
            "constraints": ["manual_review_required"],
            "hidden_dependencies": ["unclassified_operator_dependency"],
            "risk_drivers": ["taxonomy_gap"],
        },
    },
    "rejection_taxonomy": {
        "sensitive_swap": "high_risk_family",
        "logic_consistency_degraded": "semantic_conflict",
        "harmful_step_rate_increased": "harmful_drift",
        "redundancy_rate_increased": "harmful_drift",
        "missing_critical_step_rate_increased": "hidden_dependency",
        "length_changed": "semantic_conflict",
        "original_semantic_usable_failed": "semantic_conflict",
        "variant_semantic_usable_failed": "semantic_conflict",
        "qgis_chain_unusable": "landing_only_failure",
        "original_qgis_mapping_usable_failed": "landing_only_failure",
        "variant_qgis_mapping_usable_failed": "landing_only_failure",
        "qgis_unknown_count_increased": "landing_only_failure",
    },
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _deep_merge(base: dict, overlay: dict) -> dict:
    merged = dict(base)
    for key, value in overlay.items():
        if isinstance(value, dict) and isinstance(merged.get(key), dict):
            merged[key] = _deep_merge(merged[key], value)
        else:
            merged[key] = value
    return merged


def load_taxonomy(path: str | Path | None) -> dict:
    """Load taxonomy YAML, falling back to embedded defaults."""
    taxonomy = DEFAULT_TAXONOMY
    if path is None:
        return taxonomy
    taxonomy_path = Path(path)
    if not taxonomy_path.exists():
        return taxonomy
    try:
        import yaml
    except ImportError:
        return taxonomy
    loaded = yaml.safe_load(taxonomy_path.read_text(encoding="utf-8")) or {}
    if not isinstance(loaded, dict):
        return taxonomy
    return _deep_merge(taxonomy, loaded)


def _read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def load_jsonl(path: str | Path) -> list[dict]:
    rows = []
    with Path(path).open("r", encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


def _write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


def _write_csv(path: Path, rows: Sequence[dict], fieldnames: Sequence[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fieldnames))
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fieldnames})


def _parse_list(value: object) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, tuple):
        return list(value)
    if isinstance(value, str) and value.strip():
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return [part.strip() for part in value.split(";") if part.strip()]
        if isinstance(parsed, list):
            return parsed
    return []


def _as_tokens(value: object) -> list[int]:
    tokens = []
    for item in _parse_list(value):
        try:
            tokens.append(int(item))
        except (TypeError, ValueError):
            continue
    return tokens


def _as_string_list(value: object) -> list[str]:
    return [str(item) for item in _parse_list(value) if str(item)]


def _rate(count: int, total: int) -> float:
    return round(float(count) / float(total), 8) if total else 0.0


def load_token_metadata(hierarchy_path: str | Path, l3_vocab_path: str | Path) -> dict[int, dict]:
    vocab = _read_json(Path(l3_vocab_path))
    code_to_id = vocab.get("code_to_id", {}) if isinstance(vocab, dict) else {}
    id_to_code = {int(value): str(key) for key, value in code_to_id.items()}

    hierarchy_by_code: dict[str, dict] = {}
    with Path(hierarchy_path).open("r", encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            hierarchy_by_code[str(row.get("l3_code", ""))] = dict(row)

    token_meta: dict[int, dict] = {}
    for token_id, code in id_to_code.items():
        row = dict(hierarchy_by_code.get(code, {}))
        row["l3_code"] = code
        row["token_id"] = token_id
        token_meta[token_id] = row
    return token_meta


def _infer_class_from_name(name: str) -> str:
    text = name.lower()
    normalized = re.sub(r"[_\-]+", " ", text)
    if "filter by date" in normalized or "date range" in normalized:
        return "temporal_filter"
    if "filter by metadata" in normalized or "metadata property" in normalized:
        return "metadata_filter"
    if "filter by spatial" in normalized or "spatial bounds" in normalized:
        return "spatial_filter"
    if "select band" in normalized:
        return "select_bands"
    if "clip" in normalized:
        return "clip"
    if "update mask" in normalized or "mask" in normalized:
        return "mask"
    if "logical" in normalized or "comparison" in normalized or "threshold" in normalized:
        return "threshold_or_logic"
    if "arithmetic" in normalized or "math" in normalized:
        return "arithmetic"
    if "reproject" in normalized or "projection" in normalized or "crs" in normalized:
        return "projection"
    if "temporal reducer" in normalized or "zonal statistic" in normalized or "statistics" in normalized:
        return "reducer_or_statistics"
    if "multi temporal" in normalized or "averaging" in normalized or "aggregation" in normalized:
        return "temporal_aggregation"
    return "other"


def token_class(token_id: int, token_meta: dict[int, dict], taxonomy: dict) -> str:
    configured = taxonomy.get("token_classes", {}).get(str(int(token_id)))
    if configured:
        return str(configured)
    meta = token_meta.get(int(token_id), {})
    name = " ".join(
        str(meta.get(key, ""))
        for key in ("l3_name", "l3_description", "l2_name", "l1_name")
    )
    return _infer_class_from_name(name)


def _classes_in_group(classes: set[str], taxonomy: dict, group_name: str) -> bool:
    group = set(str(item) for item in taxonomy.get("class_groups", {}).get(group_name, []))
    return bool(classes) and classes.issubset(group)


def classify_pair(pair: Sequence[int], token_meta: dict[int, dict], taxonomy: dict) -> dict:
    pair_tokens = [int(item) for item in pair]
    classes = [token_class(token, token_meta, taxonomy) for token in pair_tokens]
    class_set = set(classes)

    if _classes_in_group(class_set, taxonomy, "collection_filters"):
        family = "filter_filter"
    elif "select_bands" in class_set and bool(class_set & set(taxonomy["class_groups"]["collection_filters"])):
        family = "select_filter"
    elif class_set == {"select_bands", "clip"}:
        family = "select_clip"
    elif "clip" in class_set and bool(class_set & set(taxonomy["class_groups"]["pixelwise_compute"])):
        family = "clip_arithmetic"
    elif bool(class_set & set(taxonomy["class_groups"]["mask_or_threshold"])):
        family = "mask_threshold_or_logic"
    elif bool(class_set & set(taxonomy["class_groups"]["reducers_or_aggregation"])):
        family = "reducer_or_aggregation"
    elif bool(class_set & set(taxonomy["class_groups"]["high_risk_sensitive"])):
        family = "high_risk_sensitive"
    else:
        family = "other"

    family_spec = taxonomy.get("families", {}).get(family, taxonomy["families"]["other"])
    names = []
    for token in pair_tokens:
        meta = token_meta.get(token, {})
        names.append(str(meta.get("l3_name") or meta.get("l3_code") or token))
    return {
        "swapped_pair": json.dumps(pair_tokens),
        "swapped_pair_names": " | ".join(names),
        "token_classes": ";".join(classes),
        "equivalence_family": family,
        "risk_level": str(family_spec.get("risk_level", "unknown")),
        "conditional_constraints": ";".join(str(item) for item in family_spec.get("constraints", [])),
        "hidden_dependency": ";".join(str(item) for item in family_spec.get("hidden_dependencies", [])),
        "semantic_risk_drivers": ";".join(str(item) for item in family_spec.get("risk_drivers", [])),
    }


def map_rejection_types(
    *,
    rejection_reasons: Sequence[str],
    landing_rejection_reasons: Sequence[str],
    risk_level: str,
    taxonomy: dict | None = None,
) -> dict:
    taxonomy = taxonomy or DEFAULT_TAXONOMY
    rejection_map = taxonomy.get("rejection_taxonomy", {})
    primary = []
    auxiliary = []
    for reason in rejection_reasons:
        mapped = str(rejection_map.get(str(reason), "semantic_conflict"))
        if mapped == "landing_only_failure":
            auxiliary.append(mapped)
        else:
            primary.append(mapped)
    for reason in landing_rejection_reasons:
        mapped = str(rejection_map.get(str(reason), "landing_only_failure"))
        if mapped == "landing_only_failure":
            auxiliary.append(mapped)
        else:
            auxiliary.append(f"landing_{mapped}")
    if risk_level == "high" and "high_risk_family" not in primary and "sensitive_swap" in set(rejection_reasons):
        primary.append("high_risk_family")
    return {
        "primary_rejection_types": sorted(set(primary)),
        "auxiliary_rejection_types": sorted(set(auxiliary)),
    }


def _counter_rows(counter: Counter, total: int, key_name: str) -> list[dict]:
    return [
        {key_name: key, "count": count, "rate": _rate(count, total)}
        for key, count in counter.most_common()
    ]


def _nested_counter_rows(counter: dict[tuple[str, str], int], total: int, first: str, second: str) -> list[dict]:
    rows = []
    for (a, b), count in sorted(counter.items(), key=lambda item: (-item[1], item[0][0], item[0][1])):
        rows.append({first: a, second: b, "count": count, "rate": _rate(count, total)})
    return rows


def _best_examples(rows: Sequence[dict], n: int = 3) -> str:
    examples = []
    for row in rows[:n]:
        examples.append(str(row.get("variant_id", "")))
    return ";".join(item for item in examples if item)


def analyze_rows(rows: Sequence[dict], token_meta: dict[int, dict], taxonomy: dict) -> dict:
    annotated = []
    total = len(rows)
    family_counter: Counter[str] = Counter()
    risk_counter: Counter[str] = Counter()
    label_counter: Counter[str] = Counter()
    family_label_counter: Counter[tuple[str, str]] = Counter()
    risk_label_counter: Counter[tuple[str, str]] = Counter()
    family_risk_counter: Counter[tuple[str, str]] = Counter()
    rejection_counter: Counter[str] = Counter()
    rejection_label_counter: Counter[tuple[str, str]] = Counter()
    qgis_aux_counter: Counter[str] = Counter()
    registry_eligible_counter: Counter[str] = Counter()
    examples_by_family: defaultdict[str, list[dict]] = defaultdict(list)

    for row in rows:
        pair = _as_tokens(row.get("swapped_pair"))
        pair_info = classify_pair(pair, token_meta, taxonomy)
        label = str(row.get("auto_label", "unknown"))
        rejection_reasons = _as_string_list(row.get("rejection_reasons"))
        landing_rejection_reasons = _as_string_list(row.get("landing_rejection_reasons"))
        mapped = map_rejection_types(
            rejection_reasons=rejection_reasons,
            landing_rejection_reasons=landing_rejection_reasons,
            risk_level=pair_info["risk_level"],
            taxonomy=taxonomy,
        )

        primary_types = mapped["primary_rejection_types"]
        auxiliary_types = mapped["auxiliary_rejection_types"]
        family = pair_info["equivalence_family"]
        risk = pair_info["risk_level"]
        family_counter[family] += 1
        risk_counter[risk] += 1
        label_counter[label] += 1
        family_label_counter[(family, label)] += 1
        risk_label_counter[(risk, label)] += 1
        family_risk_counter[(family, risk)] += 1
        registry_eligible_counter[str(bool(row.get("registry_eligible", False))).lower()] += 1
        for rejection_type in primary_types:
            rejection_counter[rejection_type] += 1
            rejection_label_counter[(rejection_type, label)] += 1
        for rejection_type in auxiliary_types:
            qgis_aux_counter[rejection_type] += 1
            rejection_counter[rejection_type] += 1
            rejection_label_counter[(rejection_type, label)] += 1

        annotated_row = {
            "variant_id": row.get("variant_id", ""),
            "auto_label": label,
            "registry_eligible": str(bool(row.get("registry_eligible", False))).lower(),
            "task_type": row.get("task_type", ""),
            "task_family": row.get("task_family", ""),
            "swap_position": row.get("swap_position", ""),
            **pair_info,
            "primary_rejection_types": ";".join(primary_types),
            "auxiliary_rejection_types": ";".join(auxiliary_types),
            "rejection_reasons": ";".join(rejection_reasons),
            "landing_rejection_reasons": ";".join(landing_rejection_reasons),
            "passed_checks": ";".join(_as_string_list(row.get("passed_checks"))),
        }
        annotated.append(annotated_row)
        if len(examples_by_family[family]) < 5:
            examples_by_family[family].append(annotated_row)

    family_summary = _counter_rows(family_counter, total, "equivalence_family")
    for item in family_summary:
        family = item["equivalence_family"]
        verified_count = family_label_counter.get((family, "verified_equivalent_candidate"), 0)
        invalid_count = family_label_counter.get((family, "invalid_variant"), 0)
        plausible_count = family_label_counter.get((family, "plausible_variant"), 0)
        unknown_count = family_label_counter.get((family, "unknown"), 0)
        item["verified_equivalent_candidate_count"] = verified_count
        item["invalid_variant_count"] = invalid_count
        item["plausible_variant_count"] = plausible_count
        item["unknown_count"] = unknown_count
        item["auto_pass_rate"] = _rate(verified_count, item["count"])
        item["invalid_variant_rate"] = _rate(invalid_count, item["count"])
        item["risk_levels"] = ";".join(
            risk for (family, risk), count in family_risk_counter.items()
            if family == item["equivalence_family"] and count
        )
        item["example_variant_ids"] = _best_examples(examples_by_family[item["equivalence_family"]])
    risk_summary = _counter_rows(risk_counter, total, "risk_level")
    for item in risk_summary:
        risk = item["risk_level"]
        verified_count = risk_label_counter.get((risk, "verified_equivalent_candidate"), 0)
        invalid_count = risk_label_counter.get((risk, "invalid_variant"), 0)
        item["verified_equivalent_candidate_count"] = verified_count
        item["invalid_variant_count"] = invalid_count
        item["auto_pass_rate"] = _rate(verified_count, item["count"])
        item["invalid_variant_rate"] = _rate(invalid_count, item["count"])

    return {
        "summary": {
            "schema_version": SCHEMA_VERSION,
            "created_at": _now(),
            "variant_count": total,
            "auto_label_counts": dict(label_counter),
            "family_count": len(family_counter),
            "risk_level_counts": dict(risk_counter),
            "registry_eligible_counts": dict(registry_eligible_counter),
            "manual_review_required_before_training": True,
            "qgis_landing_auxiliary_only": True,
        },
        "annotated_rows": annotated,
        "family_summary": family_summary,
        "risk_summary": risk_summary,
        "family_by_label_summary": _nested_counter_rows(family_label_counter, total, "equivalence_family", "auto_label"),
        "risk_by_label_summary": _nested_counter_rows(risk_label_counter, total, "risk_level", "auto_label"),
        "family_risk_matrix": _nested_counter_rows(family_risk_counter, total, "equivalence_family", "risk_level"),
        "rejection_summary": _counter_rows(rejection_counter, total, "rejection_type"),
        "rejection_by_label_summary": _nested_counter_rows(rejection_label_counter, total, "rejection_type", "auto_label"),
        "qgis_auxiliary_rejection_summary": _counter_rows(qgis_aux_counter, total, "auxiliary_rejection_type"),
    }


def _write_markdown(path: Path, analysis: dict, input_jsonl: Path, taxonomy_path: Path | None) -> None:
    summary = analysis["summary"]
    lines = [
        "# MRV Expansion Analysis",
        "",
        "This artifact analyzes workflow-level MRV expansion candidates by equivalence family, risk level, and rejection taxonomy.",
        "It does not promote any auto-verified candidate into training labels. QGIS landing failures remain auxiliary.",
        "",
        "## Inputs",
        "",
        f"- Input JSONL: `{input_jsonl}`",
        f"- Taxonomy: `{taxonomy_path}`" if taxonomy_path else "- Taxonomy: embedded default",
        f"- Variant count: {summary['variant_count']}",
        f"- Auto labels: {json.dumps(summary['auto_label_counts'], ensure_ascii=False, sort_keys=True)}",
        "",
        "## Family Summary",
        "",
        "| family | count | rate | auto_pass_rate | risk_levels | examples |",
        "| --- | ---: | ---: | ---: | --- | --- |",
    ]
    for row in analysis["family_summary"]:
        lines.append(
            f"| {row['equivalence_family']} | {row['count']} | {row['rate']:.4f} | "
            f"{row.get('auto_pass_rate', 0.0):.4f} | {row.get('risk_levels', '')} | "
            f"{row.get('example_variant_ids', '')} |"
        )
    lines.extend(["", "## Risk Summary", "", "| risk | count | rate | auto_pass_rate |", "| --- | ---: | ---: | ---: |"])
    for row in analysis["risk_summary"]:
        lines.append(f"| {row['risk_level']} | {row['count']} | {row['rate']:.4f} | {row.get('auto_pass_rate', 0.0):.4f} |")
    lines.extend(["", "## Rejection Taxonomy", "", "| rejection_type | count | rate |", "| --- | ---: | ---: |"])
    for row in analysis["rejection_summary"]:
        lines.append(f"| {row['rejection_type']} | {row['count']} | {row['rate']:.4f} |")
    lines.extend(
        [
            "",
            "## Interpretation Guardrails",
            "",
            "- `verified_equivalent_candidate` is still auto-only in this expansion and is not registry-eligible for training without manual review.",
            "- `landing_only_failure` describes downstream QGIS transferability, not GEE workflow-equivalence failure.",
            "- Medium/high-risk families require source inspection before promotion.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def write_analysis_outputs(output_dir: Path, analysis: dict, input_jsonl: Path, taxonomy_path: Path | None) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    _write_json(output_dir / "mrv_expansion_analysis.json", {key: value for key, value in analysis.items() if key != "annotated_rows"})
    _write_csv(
        output_dir / "mrv_expansion_annotated_variants.csv",
        analysis["annotated_rows"],
        [
            "variant_id",
            "auto_label",
            "registry_eligible",
            "task_type",
            "task_family",
            "swap_position",
            "swapped_pair",
            "swapped_pair_names",
            "token_classes",
            "equivalence_family",
            "risk_level",
            "conditional_constraints",
            "hidden_dependency",
            "semantic_risk_drivers",
            "primary_rejection_types",
            "auxiliary_rejection_types",
            "rejection_reasons",
            "landing_rejection_reasons",
            "passed_checks",
        ],
    )
    _write_csv(
        output_dir / "equivalence_family_summary.csv",
        analysis["family_summary"],
        [
            "equivalence_family",
            "count",
            "rate",
            "verified_equivalent_candidate_count",
            "invalid_variant_count",
            "plausible_variant_count",
            "unknown_count",
            "auto_pass_rate",
            "invalid_variant_rate",
            "risk_levels",
            "example_variant_ids",
        ],
    )
    _write_csv(
        output_dir / "risk_level_summary.csv",
        analysis["risk_summary"],
        [
            "risk_level",
            "count",
            "rate",
            "verified_equivalent_candidate_count",
            "invalid_variant_count",
            "auto_pass_rate",
            "invalid_variant_rate",
        ],
    )
    _write_csv(output_dir / "family_by_label_summary.csv", analysis["family_by_label_summary"], ["equivalence_family", "auto_label", "count", "rate"])
    _write_csv(output_dir / "risk_by_label_summary.csv", analysis["risk_by_label_summary"], ["risk_level", "auto_label", "count", "rate"])
    _write_csv(output_dir / "family_risk_matrix.csv", analysis["family_risk_matrix"], ["equivalence_family", "risk_level", "count", "rate"])
    _write_csv(output_dir / "rejection_taxonomy_summary.csv", analysis["rejection_summary"], ["rejection_type", "count", "rate"])
    _write_csv(output_dir / "rejection_by_label_summary.csv", analysis["rejection_by_label_summary"], ["rejection_type", "auto_label", "count", "rate"])
    _write_csv(output_dir / "qgis_auxiliary_rejection_summary.csv", analysis["qgis_auxiliary_rejection_summary"], ["auxiliary_rejection_type", "count", "rate"])
    _write_markdown(output_dir / "mrv_expansion_analysis.md", analysis, input_jsonl, taxonomy_path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-jsonl", type=Path, default=DEFAULT_INPUT_JSONL)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--hierarchy-path", type=Path, default=DEFAULT_HIERARCHY_PATH)
    parser.add_argument("--l3-vocab-path", type=Path, default=DEFAULT_L3_VOCAB_PATH)
    parser.add_argument("--taxonomy-path", type=Path, default=DEFAULT_TAXONOMY_PATH)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    taxonomy_path = args.taxonomy_path if args.taxonomy_path and args.taxonomy_path.exists() else None
    taxonomy = load_taxonomy(taxonomy_path)
    token_meta = load_token_metadata(args.hierarchy_path, args.l3_vocab_path)
    rows = load_jsonl(args.input_jsonl)
    analysis = analyze_rows(rows, token_meta, taxonomy)
    write_analysis_outputs(args.output_dir, analysis, args.input_jsonl, taxonomy_path)
    print(json.dumps(analysis["summary"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
