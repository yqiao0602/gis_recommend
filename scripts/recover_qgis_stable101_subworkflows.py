#!/usr/bin/env python3
"""Recover bounded QGIS subworkflows from the stable101 50-row review pack.

Each recovery specification is deliberately narrow, then verified against the
current source AST and source SHA256. The output remains review-required and is
not merged into training data automatically.
"""

from __future__ import annotations

import argparse
import ast
from collections import Counter
from dataclasses import dataclass
import csv
import hashlib
import json
from pathlib import Path
import tempfile
from typing import Any
import warnings


ROOT = Path(__file__).resolve().parents[1]
REPORT_ROOT = ROOT / "docs/reports/qgis_mapping_high_impact_blockers_2026-07-24"
DEFAULT_REVIEW_DIR = REPORT_ROOT / "stable101_source_review_50_v1"
DEFAULT_REVIEW_CSV = DEFAULT_REVIEW_DIR / "stable101_source_review_50_v1.csv"
DEFAULT_SALVAGE_LEDGER = DEFAULT_REVIEW_DIR / "stable101_salvage_ledger_v1.jsonl"
DEFAULT_STABLE101_PROPOSAL = REPORT_ROOT / "stable101_conservative_extension_proposal_v1.json"
DEFAULT_OUTPUT_DIR = DEFAULT_REVIEW_DIR / "recovered_subworkflows_v1"


def _edge(producer: int, consumer: int, kind: str = "data") -> dict[str, Any]:
    return {
        "producer_ordinal": producer,
        "consumer_ordinal": consumer,
        "dependency_kind": kind,
    }


def _linear_edges(length: int) -> list[dict[str, Any]]:
    return [_edge(index, index + 1) for index in range(length - 1)]


def _ref(line: int, operator: str, *, expansion_line: int | None = None) -> dict[str, Any]:
    value = {"line": line, "operator_id": operator}
    if expansion_line is not None:
        value["expansion_call_line"] = expansion_line
    return value


SPECS: tuple[dict[str, Any], ...] = (
    {
        "review_index": 3,
        "suffix": "chip_pair_dag",
        "entrypoint": "run_chipping_pipeline",
        "call_graph_path": [
            "run_chipping_pipeline -> reproject_layer_if_needed",
            "run_chipping_pipeline -> rasterize_building_layer",
            "run_chipping_pipeline -> clip_raster_to_chip (image)",
            "run_chipping_pipeline -> clip_raster_to_chip (mask)",
        ],
        "refs": [
            _ref(256, "native:reprojectlayer", expansion_line=623),
            _ref(316, "gdal:rasterize", expansion_line=629),
            _ref(478, "gdal:cliprasterbyextent", expansion_line=680),
            _ref(478, "gdal:cliprasterbyextent", expansion_line=694),
        ],
        "edges": [_edge(0, 1), _edge(1, 2, "control_order"), _edge(1, 3)],
        "branch_groups": [
            {
                "name": "per_chip_image_and_mask",
                "member_ordinals": [2, 3],
                "semantics": "same chip extent, separate image and rasterized-mask inputs",
            }
        ],
        "control_flow": ["loop: one image clip and one mask clip per chip extent"],
        "scope": "paired_raster_chip_generation",
        "dependency_status": "recovered_dag",
        "known_omissions": ["PNG conversion and building-coverage filtering remain side effects."],
    },
    {
        "review_index": 6,
        "suffix": "processing_csv",
        "entrypoint": "Model.processAlgorithm",
        "call_graph_path": ["Model.processAlgorithm"],
        "refs": [
            _ref(119, "native:fixgeometries"),
            _ref(148, "native:extractbyattribute"),
            _ref(170, "native:reprojectlayer"),
            _ref(205, "native:refactorfields"),
            _ref(255, "native:refactorfields"),
            _ref(275, "native:savefeatures"),
        ],
        "edges": _linear_edges(6),
        "optional": [1, 2],
        "control_flow": [
            "optional ordinal 1 when filter field/value are valid",
            "optional ordinal 2 when target_crs is provided",
        ],
        "scope": "processing_only_csv_subworkflow",
        "dependency_status": "recovered_conditional_dag",
        "known_omissions": [
            "The downstream custom Python AutoCAD SCR generation is outside the Processing chain.",
            "GUI labeling side effects are excluded from the retained subworkflow.",
        ],
    },
    {
        "review_index": 42,
        "suffix": "cn_overlay_preprocess",
        "entrypoint": "CNCalculatorTool.run",
        "call_graph_path": [
            "CNCalculatorTool.run -> reproject_layer (subbasin)",
            "CNCalculatorTool.run -> reproject_layer (landuse)",
            "CNCalculatorTool.run -> reproject_layer (soils)",
            "CNCalculatorTool.run -> intersect_layers (landuse, soils)",
            "CNCalculatorTool.run -> intersect_layers (subbasin, lu_soil)",
        ],
        "refs": [
            _ref(420, "native:reprojectlayer", expansion_line=370),
            _ref(420, "native:reprojectlayer", expansion_line=371),
            _ref(420, "native:reprojectlayer", expansion_line=372),
            _ref(434, "native:intersection", expansion_line=376),
            _ref(434, "native:intersection", expansion_line=380),
        ],
        "edges": [_edge(1, 3), _edge(2, 3), _edge(0, 4), _edge(3, 4)],
        "optional": [0, 1, 2],
        "control_flow": ["each reproject call is conditional on source CRS != target CRS"],
        "scope": "cn_overlay_preprocessing",
        "dependency_status": "recovered_dag",
        "known_omissions": [
            "Low-level composite-CN calculation and CSV output remain outside this Processing subworkflow."
        ],
    },
    {
        "review_index": 9,
        "suffix": "soil_fix_clip",
        "entrypoint": "get_usda_soil_polygons",
        "call_graph_path": ["get_usda_soil_polygons"],
        "refs": [_ref(437, "native:fixgeometries"), _ref(453, "native:clip")],
        "edges": _linear_edges(2),
        "scope": "post_api_soil_cleanup",
        "known_omissions": ["USDA API request, response parsing, and memory-layer construction are prerequisites."],
    },
    {
        "review_index": 10,
        "suffix": "basin_overlay",
        "entrypoint": "SoilDataProcessor.get_soil_for_basin",
        "call_graph_path": ["SoilDataProcessor.run -> get_soil_for_basin"],
        "refs": [_ref(547, "native:reprojectlayer"), _ref(559, "native:intersection")],
        "edges": _linear_edges(2),
        "optional": [0],
        "scope": "per_basin_soil_overlay",
        "known_omissions": ["The soil layer is supplied by an earlier USDA API and feature-construction stage."],
    },
    {
        "review_index": 11,
        "suffix": "soil_postprocess",
        "entrypoint": "get_soil_data",
        "call_graph_path": ["get_soil_data"],
        "refs": [
            _ref(156, "native:fixgeometries"),
            _ref(164, "native:clip"),
            _ref(173, "native:reprojectlayer"),
            _ref(181, "native:fixgeometries"),
        ],
        "edges": _linear_edges(4),
        "scope": "post_api_soil_cleanup",
        "known_omissions": ["USDA API acquisition and in-memory soil feature construction are prerequisites."],
    },
    {
        "review_index": 13,
        "suffix": "classification_polygonize",
        "entrypoint": "UrbanNeedIndexProcessor.run",
        "call_graph_path": [
            "run -> _classify_raster (one of three mutually exclusive tables)",
            "run -> _raster_to_polygons",
        ],
        "refs": [_ref(94, "native:reclassifybytable"), _ref(172, "gdal:polygonize")],
        "edges": _linear_edges(2),
        "scope": "raster_classification_to_polygons",
        "control_flow": ["reclassify line 94 represents one of mutually exclusive lines 94/116/137"],
        "alternative_call_lines": [116, 137],
        "known_omissions": ["Low-level category-field creation after polygonize remains a required sidecar."],
    },
    {
        "review_index": 13,
        "suffix": "zonal_summary",
        "entrypoint": "UrbanNeedIndexProcessor._compute_zonal_summary",
        "call_graph_path": ["run -> _compute_zonal_summary (optional)"],
        "refs": [_ref(225, "native:zonalstatisticsfb")],
        "edges": [],
        "scope": "optional_zonal_summary",
        "control_flow": ["optional when sub_boundaries is supplied"],
        "known_omissions": ["Consumes the classified raster produced by a separate branch-aware unit."],
    },
    {
        "review_index": 23,
        "suffix": "raster_preprocess",
        "entrypoint": "WorkflowBase._subset_raster_layer",
        "call_graph_path": ["WorkflowBase.execute -> _subset_raster_layer"],
        "refs": [_ref(709, "gdal:warpreproject"), _ref(722, "native:fillnodata")],
        "edges": _linear_edges(2),
        "scope": "raster_input_preprocessing",
        "known_omissions": [],
    },
    {
        "review_index": 23,
        "suffix": "vector_mask",
        "entrypoint": "WorkflowBase._process_features_for_area",
        "call_graph_path": ["subclass _process_features_for_area -> _rasterize -> _mask_raster"],
        "refs": [_ref(807, "gdal:rasterize"), _ref(874, "gdal:cliprasterbymasklayer")],
        "edges": _linear_edges(2),
        "scope": "subclass_vector_result_mask",
        "known_omissions": ["Concrete subclass processing before rasterization is not represented by the abstract base."],
    },
    {
        "review_index": 24,
        "suffix": "vector_mask",
        "entrypoint": "OpportunitiesMaskProcessor._process_features_for_area",
        "call_graph_path": [
            "_process_features_for_area -> _buffer_features (point mode only)",
            "_process_features_for_area -> _clip_features -> generate_mask_layer",
        ],
        "refs": [_ref(485, "native:buffer"), _ref(515, "native:clip"), _ref(554, "gdal:rasterize")],
        "edges": _linear_edges(3),
        "optional": [0],
        "scope": "point_or_polygon_vector_mask",
        "control_flow": ["buffer runs only in point mode; polygon/ghsl modes start at clip"],
        "known_omissions": [],
    },
    {
        "review_index": 24,
        "suffix": "raster_mask",
        "entrypoint": "OpportunitiesMaskProcessor._process_raster_for_area",
        "call_graph_path": ["base execute -> _subset_raster_layer -> _process_raster_for_area"],
        "refs": [_ref(590, "gdal:warpreproject"), _ref(638, "gdal:rastercalculator")],
        "edges": _linear_edges(2),
        "scope": "raster_mask",
        "known_omissions": [],
    },
    {
        "review_index": 29,
        "suffix": "dem_baseline",
        "entrypoint": "VolumeCalculation.createNDOMRaster",
        "call_graph_path": ["createNDOMRaster DEM baseline branch"],
        "refs": [
            _ref(930, "gdal:warpreproject"),
            _ref(952, "gdal:rastercalculator"),
            _ref(960, "gdal:cliprasterbymasklayer"),
        ],
        "edges": _linear_edges(3),
        "scope": "dem_baseline_ndom",
        "known_omissions": [],
    },
    {
        "review_index": 29,
        "suffix": "polygon_baseline",
        "entrypoint": "VolumeCalculation.createNDOMRaster",
        "call_graph_path": ["createNDOMRaster -> createBaselineRasterForNDOM polygon branch"],
        "refs": [
            _ref(872, "gdal:rasterize", expansion_line=948),
            _ref(952, "gdal:rastercalculator"),
            _ref(960, "gdal:cliprasterbymasklayer"),
        ],
        "edges": _linear_edges(3),
        "scope": "polygon_baseline_ndom",
        "known_omissions": [],
    },
    {
        "review_index": 34,
        "suffix": "fix_geometries",
        "entrypoint": "fix_geometries",
        "call_graph_path": ["fix_geometries"],
        "refs": [_ref(9, "native:fixgeometries")],
        "edges": [],
        "scope": "single_tool_function",
        "known_omissions": [],
    },
    {
        "review_index": 34,
        "suffix": "singleparts",
        "entrypoint": "multi_to_singlepart",
        "call_graph_path": ["multi_to_singlepart"],
        "refs": [_ref(19, "native:multiparttosingleparts")],
        "edges": [],
        "scope": "single_tool_function",
        "known_omissions": [],
    },
    {
        "review_index": 34,
        "suffix": "clip",
        "entrypoint": "clip",
        "call_graph_path": ["clip"],
        "refs": [_ref(28, "native:clip")],
        "edges": [],
        "scope": "single_tool_function",
        "known_omissions": [],
    },
    {
        "review_index": 34,
        "suffix": "extract_expression",
        "entrypoint": "extract_features_by_expression",
        "call_graph_path": ["extract_features_by_expression"],
        "refs": [_ref(280, "native:extractbyexpression")],
        "edges": [],
        "scope": "single_tool_function",
        "known_omissions": ["Dynamic GDAL helper calls elsewhere in the utility module are excluded."],
    },
    {
        "review_index": 36,
        "suffix": "watershed_outputs",
        "entrypoint": "Model.processAlgorithm",
        "call_graph_path": ["Model.processAlgorithm"],
        "refs": [
            _ref(76, "grass7:r.watershed"),
            _ref(94, "grass7:r.water.outlet"),
            _ref(119, "grass7:r.to.vect"),
            _ref(144, "grass7:r.to.vect"),
            _ref(156, "native:fixgeometries"),
            _ref(181, "grass7:r.to.vect"),
            _ref(193, "native:fixgeometries"),
            _ref(205, "native:fixgeometries"),
            _ref(219, "native:clip"),
            _ref(233, "native:clip"),
        ],
        "edges": [
            _edge(0, 1), _edge(0, 2), _edge(0, 3), _edge(2, 4),
            _edge(1, 5), _edge(3, 6), _edge(5, 7), _edge(4, 8),
            _edge(7, 8), _edge(6, 9), _edge(7, 9),
        ],
        "branch_groups": [
            {"name": "river_and_subbasin_clips", "member_ordinals": [8, 9], "semantics": "parallel outputs"}
        ],
        "scope": "grass_watershed_and_vector_outputs",
        "dependency_status": "recovered_dag_review_required",
        "known_omissions": ["GRASS operator mappings are unresolved in the stable101 review row."],
    },
    {
        "review_index": 37,
        "suffix": "web_vector_fix",
        "entrypoint": "getWebVectorLayer",
        "call_graph_path": ["getWebVectorLayer"],
        "refs": [_ref(139, "native:fixgeometries")],
        "edges": [],
        "scope": "web_vector_geometry_cleanup",
        "known_omissions": ["Web-service fetch and response materialization are prerequisites."],
    },
    {
        "review_index": 37,
        "suffix": "protected_sites_merge",
        "entrypoint": "getProtectedSites",
        "call_graph_path": ["getProtectedSites loop -> fix each service result -> merge"],
        "refs": [_ref(219, "native:fixgeometries"), _ref(226, "native:mergevectorlayers")],
        "edges": _linear_edges(2),
        "scope": "protected_site_aggregation",
        "control_flow": ["fixgeometries repeats once per returned protected-site layer"],
        "known_omissions": ["Commented fix/dissolve calls are intentionally excluded."],
    },
    {
        "review_index": 38,
        "suffix": "complete_measure",
        "entrypoint": "CompletarCampoMedidas",
        "call_graph_path": ["CompletarCampoMedidas"],
        "refs": [_ref(297, "native:fixgeometries")],
        "edges": [],
        "scope": "registered_parcel_geometry_cleanup",
        "known_omissions": [],
    },
    {
        "review_index": 38,
        "suffix": "blocks_selection",
        "entrypoint": "GenerarManzanasDesdeSeleccion",
        "call_graph_path": ["GenerarManzanasDesdeSeleccion"],
        "refs": [_ref(363, "native:fixgeometries")],
        "edges": [],
        "optional": [0],
        "scope": "selected_block_geometry_cleanup",
        "known_omissions": [],
    },
    {
        "review_index": 38,
        "suffix": "registered_selection",
        "entrypoint": "GenerarRegistradosDesdeSeleccion",
        "call_graph_path": ["GenerarRegistradosDesdeSeleccion"],
        "refs": [_ref(380, "native:fixgeometries")],
        "edges": [],
        "optional": [0],
        "scope": "selected_registered_geometry_cleanup",
        "known_omissions": [],
    },
    {
        "review_index": 38,
        "suffix": "owner_layers",
        "entrypoint": "GenerarManzanero",
        "call_graph_path": ["GenerarManzanero parallel owner/occupant cleanup"],
        "refs": [_ref(531, "native:fixgeometries"), _ref(532, "native:fixgeometries")],
        "edges": [],
        "branch_groups": [
            {"name": "owner_and_occupant_layers", "member_ordinals": [0, 1], "semantics": "parallel independent inputs"}
        ],
        "scope": "owner_and_occupant_geometry_cleanup",
        "known_omissions": [],
    },
    {
        "review_index": 40,
        "suffix": "dissolve_overlap",
        "entrypoint": "dissolve_and_resolve_overlaps",
        "call_graph_path": ["dissolve_and_resolve_overlaps"],
        "refs": [_ref(109, "native:dissolve")],
        "edges": [],
        "scope": "attribute_dissolve_helper",
        "known_omissions": [],
    },
    {
        "review_index": 40,
        "suffix": "priority_stack",
        "entrypoint": "LandUseProcessor.stack_layers",
        "call_graph_path": ["LandUseProcessor.stack_layers priority loop"],
        "refs": [
            _ref(640, "native:fixgeometries"),
            _ref(654, "native:difference"),
            _ref(666, "native:removenullgeometries"),
            _ref(685, "native:fixgeometries"),
            _ref(694, "native:fixgeometries"),
            _ref(705, "native:union"),
            _ref(719, "native:fixgeometries"),
            _ref(738, "native:mergevectorlayers"),
        ],
        "edges": [
            _edge(0, 1), _edge(1, 2), _edge(2, 4), _edge(3, 5),
            _edge(4, 5), _edge(5, 6), _edge(2, 7, "collection"),
        ],
        "optional": [1, 3, 4, 5, 6],
        "scope": "priority_layer_stack",
        "control_flow": ["difference is skipped for the first layer; union branch starts after the first accumulated layer"],
        "dependency_status": "recovered_loop_dag_review_required",
        "known_omissions": ["Exception fallback may skip a failed union iteration."],
    },
    {
        "review_index": 48,
        "suffix": "protected_join",
        "entrypoint": "add_protected_buildings",
        "call_graph_path": ["add_protected_buildings"],
        "refs": [_ref(55, "native:reprojectlayer"), _ref(63, "native:joinattributesbylocation")],
        "edges": _linear_edges(2),
        "scope": "protected_area_spatial_join",
        "known_omissions": ["Low-level boolean attribute assignment follows the join."],
    },
    {
        "review_index": 48,
        "suffix": "overlap_groups",
        "entrypoint": "merge_overlapped_buildings",
        "call_graph_path": ["merge_overlapped_buildings"],
        "refs": [_ref(241, "native:multiintersection")],
        "edges": [],
        "scope": "building_overlap_pairs",
        "known_omissions": ["Low-level grouping and geometry merge logic is required after multiintersection."],
    },
)


@dataclass(frozen=True)
class RecoveryResult:
    rows: list[dict[str, Any]]
    summary: dict[str, Any]


def _sha256(path: Path) -> str:
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def _load_csv(path: Path) -> list[dict[str, str]]:
    with Path(path).open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    with Path(path).open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def _callable_name(node: ast.AST) -> str:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        prefix = _callable_name(node.value)
        return f"{prefix}.{node.attr}" if prefix else node.attr
    return ""


def _literal_operator(call: ast.Call) -> str | None:
    if _callable_name(call.func) not in {
        "processing.run",
        "processing.runAndLoadResults",
        "processing.runalg",
    }:
        return None
    if not call.args or not isinstance(call.args[0], ast.Constant):
        return None
    value = call.args[0].value
    return value if isinstance(value, str) else None


def _ast_call_index(text: str) -> dict[tuple[int, str], dict[str, Any]]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)
        tree = ast.parse(text)
    parents: dict[ast.AST, ast.AST] = {}
    for parent in ast.walk(tree):
        for child in ast.iter_child_nodes(parent):
            parents[child] = parent
    result: dict[tuple[int, str], dict[str, Any]] = {}
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        operator = _literal_operator(node)
        if operator is None:
            continue
        owners: list[str] = []
        cursor: ast.AST | None = node
        while cursor in parents:
            cursor = parents[cursor]
            if isinstance(cursor, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                owners.append(cursor.name)
        owner = ".".join(reversed(owners)) or "<module>"
        params: list[str] = []
        if len(node.args) > 1 and isinstance(node.args[1], ast.Dict):
            for key in node.args[1].keys:
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    params.append(key.value)
        result[(int(node.lineno), operator)] = {
            "operator_id": operator,
            "line_start": int(node.lineno),
            "line_end": int(getattr(node, "end_lineno", node.lineno)),
            "owner": owner,
            "param_keys": params,
        }
    return result


def _proposal_code_to_id(path: Path) -> dict[str, int]:
    value = json.loads(Path(path).read_text(encoding="utf-8"))
    result = {str(code): int(token) for code, token in value["existing_code_to_id"].items()}
    result.update(
        {str(code): int(token) for code, token in value["proposed_code_to_id_additions"].items()}
    )
    return result


def _mapping_for_review(review: dict[str, Any]) -> dict[str, str]:
    operators = json.loads(review["ordered_operator_ids"])
    codes = json.loads(review["mapped_l3_chain"])
    mapping: dict[str, str] = {}
    for operator, code in zip(operators, codes):
        if operator in mapping and mapping[operator] != code:
            raise ValueError(f"inconsistent L3 mapping for {operator} at review_index {review['review_index']}")
        mapping[operator] = code
    return mapping


def _snippet(lines: list[str], calls: list[dict[str, Any]]) -> str:
    spans: list[tuple[int, int]] = []
    for call in calls:
        start = max(1, int(call["line_start"]) - 1)
        end = min(len(lines), int(call["line_end"]) + 1)
        if (start, end) not in spans:
            spans.append((start, end))
    blocks = []
    for start, end in spans:
        blocks.append("\n".join(f"{line_no:4} | {lines[line_no - 1]}" for line_no in range(start, end + 1)))
    return "\n...\n".join(blocks)


def build_recovery_candidates(
    *,
    review_csv_path: Path,
    salvage_ledger_path: Path,
    stable101_proposal_path: Path,
) -> RecoveryResult:
    reviews = {int(row["review_index"]): row for row in _load_csv(review_csv_path)}
    salvage = {int(row["review_index"]): row for row in _load_jsonl(salvage_ledger_path)}
    code_to_id = _proposal_code_to_id(stable101_proposal_path)
    source_cache: dict[Path, tuple[str, list[str], dict[tuple[int, str], dict[str, Any]]]] = {}
    rows: list[dict[str, Any]] = []

    for spec in SPECS:
        review_index = int(spec["review_index"])
        review = reviews[review_index]
        salvage_row = salvage[review_index]
        source_path = Path(review["source_path"])
        if source_path not in source_cache:
            text = source_path.read_text(encoding="utf-8")
            source_cache[source_path] = (text, text.splitlines(), _ast_call_index(text))
        _, source_lines, call_index = source_cache[source_path]
        actual_sha = _sha256(source_path)
        if actual_sha != review["source_sha256"]:
            raise ValueError(f"source SHA256 mismatch at review_index {review_index}")

        calls: list[dict[str, Any]] = []
        for ordinal, ref in enumerate(spec["refs"]):
            key = (int(ref["line"]), str(ref["operator_id"]))
            if key not in call_index:
                raise ValueError(f"AST call not found for review_index {review_index}: {key}")
            call = dict(call_index[key])
            call["ordinal"] = ordinal
            if "expansion_call_line" in ref:
                call["expansion_call_line"] = int(ref["expansion_call_line"])
            calls.append(call)

        operators = [call["operator_id"] for call in calls]
        operator_to_l3 = _mapping_for_review(review)
        l3_codes = [operator_to_l3.get(operator) for operator in operators]
        l3_token_ids = [code_to_id.get(code) if code else None for code in l3_codes]
        mapping_complete = all(code is not None and token is not None for code, token in zip(l3_codes, l3_token_ids))
        span_segments = [
            {"line_start": call["line_start"], "line_end": call["line_end"]}
            for call in calls
        ]
        expansion_lines = [
            int(call["expansion_call_line"])
            for call in calls
            if "expansion_call_line" in call
        ]
        all_span_lines = [value for segment in span_segments for value in segment.values()] + expansion_lines
        unit_id = f"qgis_stable101_r{review_index}_{spec['suffix']}"
        rows.append(
            {
                "schema_version": "qgis_stable101_recovered_subworkflow_v1",
                "unit_id": unit_id,
                "review_index": review_index,
                "record_id": review["record_id"],
                "source_root_id": review.get("source_root_id", ""),
                "source_path": str(source_path),
                "relative_path": review.get("relative_path", ""),
                "source_sha256": actual_sha,
                "entrypoint": spec["entrypoint"],
                "source_span": {
                    "line_start": min(all_span_lines),
                    "line_end": max(all_span_lines),
                    "segments": span_segments,
                    "expansion_call_lines": expansion_lines,
                },
                "evidence_snippet": _snippet(source_lines, calls),
                "source_calls": calls,
                "operator_sequence": operators,
                "l3_code_sequence": l3_codes,
                "l3_token_ids": l3_token_ids,
                "mapping_status": "complete_stable101_report_only" if mapping_complete else "partial_mapping_gap",
                "dependency_edges": list(spec.get("edges", [])),
                "dependency_status": spec.get("dependency_status", "recovered_local_dataflow"),
                "call_graph_path": list(spec.get("call_graph_path", [])),
                "optional_operator_ordinals": list(spec.get("optional", [])),
                "branch_groups": list(spec.get("branch_groups", [])),
                "control_flow": list(spec.get("control_flow", [])),
                "workflow_scope": spec["scope"],
                "recovery_method": (
                    "curated_ast_call_graph_expansion_v1"
                    if salvage_row["salvage_class"] == "recoverable_call_graph"
                    else "curated_ast_subworkflow_split_v1"
                ),
                "salvage_class": salvage_row["salvage_class"],
                "known_omissions": list(spec.get("known_omissions", [])),
                "alternative_call_lines": list(spec.get("alternative_call_lines", [])),
                "ast_verification": "passed",
                "admission_status": "recovered_review_required",
                "training_admission": "not_granted",
                "validation_eligible": False,
                "test_eligible": False,
            }
        )

    counts = Counter(row["salvage_class"] for row in rows)
    per_review = Counter(row["review_index"] for row in rows)
    summary = {
        "schema": "gis_recommend.qgis_stable101_recovery_summary.v1",
        "counts": {
            "rows": len(rows),
            "deferred_recovered_units": sum(per_review[index] for index in (3, 6, 42)),
            "split_recovered_units": counts["split_subworkflow"],
            "mapping_complete_units": sum(row["mapping_status"].startswith("complete") for row in rows),
            "mapping_gap_units": sum(row["mapping_status"] == "partial_mapping_gap" for row in rows),
        },
        "units_per_review_index": {str(index): per_review[index] for index in sorted(per_review)},
        "decision": {
            "admission_status": "recovered_review_required",
            "training_admission": "not_granted",
            "llm_called": False,
            "next_gate": "human review of recovered boundaries, dependencies, and descriptions",
        },
    }
    if len(rows) != 29 or len({row["unit_id"] for row in rows}) != 29:
        raise ValueError("recovery specification must emit exactly 29 unique units")
    return RecoveryResult(rows=rows, summary=summary)


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", newline="", dir=path.parent, delete=False
    ) as handle:
        handle.write(text)
        temporary = Path(handle.name)
    temporary.replace(path)


def write_outputs(result: RecoveryResult, output_dir: Path, input_paths: dict[str, Path]) -> dict[str, Path]:
    output_dir = Path(output_dir)
    candidates = output_dir / "recovered_29_v1.jsonl"
    summary_path = output_dir / "recovered_29_summary_v1.json"
    hash_ledger = output_dir / "recovered_29_hashes_v1.json"
    _atomic_write(
        candidates,
        "".join(
            json.dumps(row, ensure_ascii=False, sort_keys=True, separators=(",", ":")) + "\n"
            for row in result.rows
        ),
    )
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
        "source_files": {
            row["source_sha256"]: {"path": row["source_path"]}
            for row in result.rows
        },
        "artifacts": {
            path.name: {"path": str(path), "sha256": _sha256(path), "bytes": path.stat().st_size}
            for path in (candidates, summary_path)
        },
    }
    _atomic_write(
        hash_ledger,
        json.dumps(ledger, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
    )
    return {"candidates": candidates, "summary": summary_path, "hash_ledger": hash_ledger}


def main(argv: list[str] | None = None) -> dict[str, Path]:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--review-csv", type=Path, default=DEFAULT_REVIEW_CSV)
    parser.add_argument("--salvage-ledger", type=Path, default=DEFAULT_SALVAGE_LEDGER)
    parser.add_argument("--stable101-proposal", type=Path, default=DEFAULT_STABLE101_PROPOSAL)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)
    result = build_recovery_candidates(
        review_csv_path=args.review_csv,
        salvage_ledger_path=args.salvage_ledger,
        stable101_proposal_path=args.stable101_proposal,
    )
    return write_outputs(
        result,
        args.output_dir,
        {
            "review_csv": args.review_csv,
            "salvage_ledger": args.salvage_ledger,
            "stable101_proposal": args.stable101_proposal,
        },
    )


if __name__ == "__main__":
    main()
