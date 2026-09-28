#!/usr/bin/env python3
"""Re-rollup terminal-macro discovery units into composite macro families.

v3 differs from census_v2 in three ways:
  1. Multi-producer units are kept (census_v2 dropped any unit whose producers
     rolled up to more than one semantic family -> 1,286/5,580 units were
     invisible).
  2. Chained calls (e.g. ``qgsgeometry.frompointxy.buffer(...)``) are split
     into head producer + chain-tail; read-only accessor tails (aspoint,
     wkbtype, length, ...) are dropped, mutation tails move to the mutation
     set.
  3. Families are keyed on the composite (semantic producer set x mutation
     set x sink) instead of a single semantic producer.

Families that touch any already-exploited semantic (completed construction /
transform / union families and COMPLETED_SEMANTICS producers) are deferred
with evidence; the remainder forms the new family candidate list.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from collections import Counter, defaultdict
from collections.abc import Iterable
from pathlib import Path
from typing import Any

RULE_ID = "qgis-api-composite-producer-mutation-sink-rollup-v1"

SPECIFIC_PRODUCERS = {
    "buffer",
    "centroid",
    "combine",
    "convexhull",
    "difference",
    "intersection",
    "interpolate",
    "makevalid",
    "offsetcurve",
    "qgscoordinatetransform",
    "qgsgeometry.frompoint",
    "qgsgeometry.frompointxy",
    "qgsgeometry.frompolygon",
    "qgsgeometry.frompolyline",
    "qgsrastercalculator",
    "simplify",
    "smooth",
    "symdifference",
    "transform",
    "unaryunion",
}
MUTATIONS = {
    "addattribute",
    "addattributes",
    "changeattributevalue",
    "changeattributevalues",
    "setattribute",
    "setattributes",
    "setcrs",
    "setgeometry",
    "updatefeature",
    "updatefields",
}
SINKS = {
    "addfeature",
    "addfeatures",
    "writeraster",
    "writeasvectorformat",
    "writeasvectorformatv2",
    "writeasvectorformatv3",
}
# Chain-tail methods that are read-only accessors: they do not change the
# macro's semantic signature (fromWkt(...).asPoint() is still wkt construction).
ACCESSOR_TAILS = {
    "asgeometrycollection",
    "aspoint",
    "aspolygon",
    "aspolyline",
    "aswkb",
    "aswkt",
    "boundingbox",
    "centroid",  # keep centroid as producer; see _chain_tail split order
    "densifybycount",
    "distance",
    "extent",
    "isvalid",
    "length",
    "wkbtype",
}
EXPLOITED_SEMANTICS = frozenset(
    {
        # Completed construction / transform / union families (08-05 .. 08-10)
        "point_geometry_construction",
        "polyline_geometry_construction",
        "wkt_geometry_construction",
        "polygon_geometry_construction",
        "rectangle_geometry_construction",
        "coordinate_transform",
        "unary_union",
        # COMPLETED_SEMANTICS from census_v2
        "buffer",
        "centroid",
        "convexhull",
        "difference",
        "intersection",
        "qgsrastercalculator",
        "simplify",
    }
)


def _producer_rollup(producer: str) -> str:
    if producer in {"qgsgeometry.frompoint", "qgsgeometry.frompointxy"}:
        return "point_geometry_construction"
    if producer in {"qgsgeometry.frompolyline", "qgsgeometry.frompolylinexy"}:
        return "polyline_geometry_construction"
    if producer in {"qgsgeometry.frompolygon", "qgsgeometry.frompolygonxy"}:
        return "polygon_geometry_construction"
    if producer == "qgsgeometry.fromwkt":
        return "wkt_geometry_construction"
    if producer == "qgsgeometry.fromrect":
        return "rectangle_geometry_construction"
    if producer == "qgscoordinatetransform":
        return "coordinate_transform"
    if producer == "unaryunion":
        return "unary_union"
    return producer


def _method(name: str) -> str:
    return name.strip().lower().rsplit(".", 1)[-1]


def _producer(name: str) -> str:
    normalized = name.strip().lower()
    method = _method(normalized)
    if normalized.startswith("qgsgeometry.from"):
        return normalized
    if "qgscoordinatetransform" in normalized:
        return "qgscoordinatetransform"
    if "qgsrastercalculator" in normalized:
        return "qgsrastercalculator"
    return method if method in SPECIFIC_PRODUCERS else ""


def _sink(name: str) -> str:
    method = _method(name)
    if method in SINKS:
        return method
    normalized = name.strip().lower()
    if method == "write" and "writer" in normalized:
        return "write"
    return ""


def _chain_tail(name: str) -> str | None:
    """Split a chained producer name into head producer + chain-tail method.

    ``qgsgeometry.frompointxy.buffer`` -> (head, tail) where head feeds
    ``_producer_rollup`` and tail either feeds ``_producer_rollup`` (semantic
    producer), ``MUTATIONS`` (mutation) or is dropped (accessor).
    """
    parts = name.strip().lower().split(".")
    if len(parts) < 3 or parts[0] != "qgsgeometry" or not parts[1].startswith("from"):
        return None
    return parts[2]


def _composite_signature(row: dict[str, Any]) -> tuple[list[str], list[str], str]:
    """Derive (semantic producers, mutations, sink) for one discovery unit."""
    rollups: set[str] = set()
    mutations: set[str] = set()
    for producer in row.get("producer_signature") or []:
        tail = _chain_tail(producer)
        if tail is None:
            rollups.add(_producer_rollup(producer))
            continue
        head = producer.rsplit(".", 1)[0]
        rollups.add(_producer_rollup(head))
        if tail in MUTATIONS:
            mutations.add(tail)
        elif tail in SPECIFIC_PRODUCERS or tail == "unaryunion":
            rollups.add(_producer_rollup(tail))
        # accessor tails (length, wkbtype, aspoint, ...) carry no semantics
    for mutation in row.get("mutation_signature") or []:
        mutations.add(_method(mutation))
    return sorted(rollups), sorted(mutations), str(row.get("sink_signature") or "")


def build_terminal_units_loose(
    row: dict[str, Any], *, maximum_lines: int, maximum_steps: int
) -> list[dict[str, Any]]:
    """Build discovery units without the producer-mutation conjunction filter.

    census_v2 dropped any sink window that lacked a producer or a mutation
    (``if not producers or not mutations: continue``).  v3 keeps every window
    that has at least one of the two, so mutation-only attribute-editing macros
    (``feature.setAttributes(...) -> addFeature``) become visible.
    """
    if row.get("status") != "pattern_candidate":
        return []
    steps = sorted(
        row.get("steps") or [],
        key=lambda item: (int(item.get("line_start") or 0), str(item.get("name") or "")),
    )
    units: list[dict[str, Any]] = []
    for sink_step in steps:
        sink_name = _sink(str(sink_step.get("name") or ""))
        if not sink_name:
            continue
        sink_line = int(sink_step.get("line_start") or 0)
        window = [
            step
            for step in steps
            if 0 <= sink_line - int(step.get("line_start") or 0) <= maximum_lines
        ][-maximum_steps:]
        producers = sorted(
            {value for step in window if (value := _producer(str(step.get("name") or "")))}
        )
        mutations = sorted(
            {method for step in window if (method := _method(str(step.get("name") or ""))) in MUTATIONS}
        )
        if not producers and not mutations:
            continue
        signature = {"producers": producers, "mutations": mutations, "sink": sink_name}
        unit_id = hashlib.sha256(
            json.dumps(
                {
                    "source_sha256": row.get("source_sha256"),
                    "sink_line": sink_line,
                    "signature": signature,
                },
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
        units.append(
            {
                "schema": "gis_recommend.qgis_api_composite_macro_discovery_unit.v1",
                "composite_macro_rule_id": RULE_ID,
                "unit_id": unit_id,
                "record_id": row.get("record_id"),
                "source_path": row.get("source_path"),
                "source_sha256": row.get("source_sha256"),
                "source_root_id": row.get("source_root_id"),
                "sink_line": sink_line,
                "window_line_start": min(
                    int(step.get("line_start") or sink_line) for step in window
                ),
                "window_line_end": int(sink_step.get("line_end") or sink_line),
                "producer_signature": producers,
                "mutation_signature": mutations,
                "sink_signature": sink_name,
                "window_call_names": [str(step.get("name") or "") for step in window],
                "source_verification": row.get("source_verification"),
                "candidate_l3_sequence": [],
                "mapping_status": "not_started_discovery_only",
                "description_fidelity": "not_started",
                "training_admission": "not_granted_composite_macro_census_only",
                "training_row_emitted": False,
                "validation_eligible": False,
                "test_eligible": False,
                "production_merge": "not_granted",
                "llm_called": False,
            }
        )
    return units


def _signature_key(producers: list[str], mutations: list[str], sink: str) -> str:
    return json.dumps(
        {"producers": producers, "mutations": mutations, "sink": sink},
        sort_keys=True,
        separators=(",", ":"),
    )


def build_composite_family_census(
    units: list[dict[str, Any]], *, minimum_support: int
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for unit in units:
        producers, mutations, sink = _composite_signature(unit)
        grouped[_signature_key(producers, mutations, sink)].append(unit)
    families: list[dict[str, Any]] = []
    priority_units: list[dict[str, Any]] = []
    defer_reasons: Counter = Counter()
    for key, members in grouped.items():
        signature = json.loads(key)
        producers = signature["producers"]
        source_shas = sorted({str(row["source_sha256"]) for row in members})
        overlap = sorted(set(producers).intersection(EXPLOITED_SEMANTICS))
        if overlap:
            review_priority = "defer_completed_semantic_overlap"
            defer_reasons["defer_completed_semantic_overlap"] += 1
        elif len(source_shas) < minimum_support:
            review_priority = "defer_source_sha_support_below_threshold"
            defer_reasons["defer_source_sha_support_below_threshold"] += 1
        else:
            review_priority = "source_replay_required"
            defer_reasons["source_replay_required"] += 1
        family_id = hashlib.sha256(key.encode("utf-8")).hexdigest()
        families.append(
            {
                "schema": "gis_recommend.qgis_api_composite_macro_family_census.v1",
                "composite_macro_rule_id": RULE_ID,
                "family_id": family_id,
                "producer_rollups": producers,
                "mutation_rollups": signature["mutations"],
                "sink_signature": signature["sink"],
                "unit_count": len(members),
                "source_sha_support": len(source_shas),
                "exact_signature_count": len(
                    {
                        json.dumps(
                            {
                                "producers": row["producer_signature"],
                                "mutations": row["mutation_signature"],
                                "sink": row["sink_signature"],
                            },
                            sort_keys=True,
                            separators=(",", ":"),
                        )
                        for row in members
                    }
                ),
                "producer_variants": sorted(
                    {value for row in members for value in row["producer_signature"]}
                ),
                "mutation_variants": sorted(
                    {value for row in members for value in row["mutation_signature"]}
                ),
                "sink_variants": sorted({str(row["sink_signature"]) for row in members}),
                "completed_semantic_overlap": overlap,
                "review_priority": review_priority,
                "support_basis": "source_sha_discovery_only_not_normalized_body_authority",
                "example_unit_ids": sorted(row["unit_id"] for row in members)[:10],
                "training_admission": "not_granted_composite_macro_census_only",
                "mapping_rows_emitted": 0,
                "description_fidelity_rows": 0,
                "training_rows_emitted": 0,
            }
        )
        if review_priority == "source_replay_required":
            priority_units.extend({**row, "family_id": family_id} for row in members)
    families.sort(
        key=lambda row: (
            row["review_priority"] != "source_replay_required",
            -int(row["source_sha_support"]),
            str(row["family_id"]),
        )
    )
    priority_units.sort(key=lambda row: (str(row["family_id"]), str(row["unit_id"])))
    summary = {
        "schema": "gis_recommend.qgis_api_composite_macro_census_summary.v1",
        "composite_macro_rule_id": RULE_ID,
        "terminal_macro_units_input": len(units),
        "composite_family_count": len(families),
        "priority_family_count": defer_reasons["source_replay_required"],
        "priority_units": len(priority_units),
        "defer_reason_counts": dict(sorted(defer_reasons.items())),
        "minimum_source_sha_support": minimum_support,
        "support_limitation": "normalized_body_authority_requires_server_source_replay",
        "mapping_rows_emitted": 0,
        "description_fidelity_rows": 0,
        "training_rows_emitted": 0,
        "training_admission": "not_granted_composite_macro_census_only",
        "validation_eligible": False,
        "test_eligible": False,
        "production_merge": "not_granted",
        "llm_called": False,
    }
    return families, priority_units, summary


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    temporary.replace(path)


def _write_json(path: Path, value: Any) -> None:
    _atomic_write(
        path, json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    )


def _write_jsonl(path: Path, rows: Iterable[dict[str, Any]]) -> None:
    _atomic_write(
        path,
        "".join(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n" for row in rows),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--api-steps", type=Path, required=True)
    parser.add_argument("--exclude-jsonl", type=Path, action="append", default=[])
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--expected-source-rows", type=int, default=39386)
    parser.add_argument("--expected-pattern-candidates", type=int, default=13554)
    parser.add_argument("--maximum-lines", type=int, default=80)
    parser.add_argument("--maximum-steps", type=int, default=16)
    parser.add_argument("--minimum-support", type=int, default=30)
    args = parser.parse_args()
    if args.output_dir.exists() and any(args.output_dir.iterdir()):
        raise ValueError(f"output directory is not empty: {args.output_dir}")
    rows = _read_jsonl(args.api_steps)
    if len(rows) != args.expected_source_rows:
        raise ValueError("API step source row count mismatch")
    pattern_candidates = [row for row in rows if row.get("status") == "pattern_candidate"]
    if len(pattern_candidates) != args.expected_pattern_candidates:
        raise ValueError("pattern candidate count mismatch")
    excluded_source_shas = {
        str(row.get("source_sha256") or "")
        for path in args.exclude_jsonl
        for row in _read_jsonl(path)
        if row.get("source_sha256")
    }
    remaining = [
        row
        for row in pattern_candidates
        if str(row.get("source_sha256") or "") not in excluded_source_shas
    ]
    units = [
        unit
        for row in remaining
        for unit in build_terminal_units_loose(
            row, maximum_lines=args.maximum_lines, maximum_steps=args.maximum_steps
        )
    ]
    families, priority_units, summary = build_composite_family_census(
        units, minimum_support=args.minimum_support
    )
    summary.update(
        {
            "input_source_rows": len(rows),
            "input_pattern_candidates": len(pattern_candidates),
            "excluded_source_sha_count": len(excluded_source_shas),
            "remaining_pattern_candidates": len(remaining),
            "discovery_units": len(units),
            "maximum_lines": args.maximum_lines,
            "maximum_steps": args.maximum_steps,
        }
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    outputs = {
        "discovery_units_v1.jsonl": units,
        "composite_family_census_v1.jsonl": families,
        "priority_units_v1.jsonl": priority_units,
    }
    paths: list[Path] = []
    for name, output_rows in outputs.items():
        path = args.output_dir / name
        _write_jsonl(path, output_rows)
        paths.append(path)
    summary_path = args.output_dir / "summary_v1.json"
    _write_json(summary_path, summary)
    paths.append(summary_path)
    inputs = [args.api_steps, *args.exclude_jsonl]
    _write_json(
        args.output_dir / "hash_ledger_v1.json",
        {
            "schema": "gis_recommend.hash_ledger.v1",
            "inputs": {
                str(index): {"path": str(path), "sha256": _sha256(path)}
                for index, path in enumerate(inputs)
            },
            "artifacts": {
                path.name: {"bytes": path.stat().st_size, "sha256": _sha256(path)}
                for path in paths
            },
        },
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))
    for family in families:
        if family["review_priority"] != "source_replay_required":
            continue
        print(
            f"  PRIORITY {family['source_sha_support']:>4} src "
            f"{family['unit_count']:>4} units {family['exact_signature_count']:>3} sigs "
            f"producers={family['producer_rollups']} mutations={family['mutation_rollups']} "
            f"sink={family['sink_signature']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
