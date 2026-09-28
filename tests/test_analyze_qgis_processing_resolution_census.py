from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "scripts"
    / "analyze_qgis_processing_resolution_census.py"
)
SPEC = importlib.util.spec_from_file_location(
    "analyze_qgis_processing_resolution_census", SCRIPT_PATH
)
assert SPEC and SPEC.loader
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_analyze_source_recovers_bounded_dynamic_ids_and_flow_patterns() -> None:
    source = '''
ALGORITHM = "native:buffer"

def prepare(layer):
    params = {"INPUT": layer, "OUTPUT": "memory:"}
    result = processing.run(ALGORITHM, params)
    output = result["OUTPUT"]
    return output

def execute(layer, use_clip):
    operator_id = "native:clip" if use_clip else "native:intersection"
    return processing.run(operator_id, {"INPUT": prepare(layer)})
'''

    evidence = MODULE.analyze_source(source)

    assert evidence["processing_call_count"] == 2
    assert evidence["dynamic_processing_call_count"] == 2
    assert evidence["resolved_dynamic_call_count"] == 2
    assert evidence["resolved_dynamic_operator_ids"] == [
        "native:buffer",
        "native:clip",
        "native:intersection",
    ]
    assert evidence["parameter_dict_name_call_count"] == 1
    assert evidence["output_alias_call_count"] == 1
    assert evidence["processing_scope_count"] == 2
    assert evidence["helper_edge_count"] == 1
    assert evidence["has_cross_function_processing_flow"] is True


def test_analyze_source_keeps_runtime_operator_ids_unresolved() -> None:
    source = '''
def execute(name, params):
    processing.run(name, params)
    processing.run(sys.argv[1], params)
    processing.run(make_algorithm_name(), params)
'''

    evidence = MODULE.analyze_source(source)

    assert evidence["dynamic_processing_call_count"] == 3
    assert evidence["resolved_dynamic_call_count"] == 0
    assert evidence["unresolved_dynamic_call_count"] == 3


def test_analyze_source_resolves_source_proven_static_conditionals() -> None:
    source = '''
def execute(layer):
    use_buffer = False
    selected = "native:buffer" if use_buffer else "native:centroids"
    return processing.run(selected, {"INPUT": layer})
'''

    evidence = MODULE.analyze_source(source)

    assert evidence["resolved_dynamic_operator_ids"] == ["native:centroids"]
    assert evidence["unresolved_dynamic_call_count"] == 0


def test_analyze_source_keeps_runtime_conditional_and_other_wrappers_unresolved() -> None:
    source = '''
def execute(layer, use_buffer):
    selected = "native:buffer" if use_buffer else "native:centroids"
    processing.run(selected, {"INPUT": layer})
    processing.run(select_algorithm("native:fixgeometries"), {"INPUT": layer})
'''

    evidence = MODULE.analyze_source(source)

    assert evidence["resolved_dynamic_operator_ids"] == [
        "native:buffer",
        "native:centroids",
    ]
    assert evidence["unresolved_dynamic_call_count"] == 1


def test_analyze_source_keeps_literal_bearing_external_wrapper_unresolved() -> None:
    source = '''
def execute(layer):
    return processing.run(select_algorithm("native:fixgeometries"), {"INPUT": layer})
'''

    evidence = MODULE.analyze_source(source)

    assert evidence["resolved_dynamic_operator_ids"] == []
    assert evidence["unresolved_dynamic_call_count"] == 1


def test_analyze_source_keeps_external_match_algo_wrapper_unresolved() -> None:
    source = '''
from ..mappy_utils import matchAlgo

def execute(layer):
    return processing.run(matchAlgo("native:fixgeometries"), {"INPUT": layer})
'''

    evidence = MODULE.analyze_source(source)

    assert evidence["resolved_dynamic_operator_ids"] == []
    assert evidence["unresolved_dynamic_call_count"] == 1


def test_analyze_source_detects_custom_algorithm_embedded_subchain() -> None:
    source = '''
class Example(QgsProcessingAlgorithm):
    def processAlgorithm(self, parameters, context, feedback):
        first = processing.run("native:buffer", {"INPUT": parameters["INPUT"]})
        return processing.run("native:fixgeometries", {"INPUT": first["OUTPUT"]})
'''

    evidence = MODULE.analyze_source(source)

    assert evidence["processing_algorithm_class_count"] == 1
    assert evidence["process_algorithm_method_count"] == 1
    assert evidence["custom_embedded_literal_processing_call_count"] == 2
    assert evidence["custom_embedded_multistep"] is True
    assert evidence["output_alias_call_count"] == 1


def test_analyze_source_excludes_subprocess_run_from_processing_calls() -> None:
    source = '''
class Example(QgsProcessingAlgorithm):
    def processAlgorithm(self, parameters, context, feedback):
        subprocess.run(["gdal_translate", "input.tif", "output.tif"])
        subprocess.run(["gdaladdo", "output.tif", "2", "4"])
        return {}
'''

    evidence = MODULE.analyze_source(source)

    assert evidence["processing_call_count"] == 0
    assert evidence["custom_embedded_processing_call_count"] == 0
    assert evidence["custom_embedded_multistep"] is False


def test_analyze_source_recovers_registry_algorithm_run_ids() -> None:
    source = '''
class Example(QgsProcessingAlgorithm):
    def processAlgorithm(self, parameters, context, feedback):
        translate = QgsApplication.processingRegistry().algorithmById("gdal:translate")
        translate.run({"INPUT": parameters["INPUT"]}, context, feedback)
        rasterize = QgsApplication.processingRegistry().algorithmById(
            "gdal:rasterize_over"
        )
        rasterize.run({"INPUT": parameters["INPUT"]}, context, feedback)
        return {}
'''

    evidence = MODULE.analyze_source(source)

    assert evidence["processing_call_count"] == 2
    assert evidence["literal_operator_ids"] == [
        "gdal:translate",
        "gdal:rasterize_over",
    ]
    assert evidence["dynamic_processing_call_count"] == 0
    assert evidence["custom_embedded_literal_processing_call_count"] == 2
    assert evidence["custom_embedded_multistep"] is True


def test_build_census_joins_authority_and_emits_mutually_exclusive_counts(
    tmp_path: Path,
) -> None:
    source_rows = [
        (
            "explicit_processing_catalog_miss",
            'processing.run("legacy:buffer", {"INPUT": layer})\n',
            ["legacy:buffer"],
            0,
            False,
        ),
        (
            "dynamic_or_blank_processing_id",
            'ALG = "native:buffer"\nprocessing.run(ALG, {"INPUT": layer})\n',
            [],
            1,
            False,
        ),
        (
            "processing_algorithm_implementation_or_custom",
            "class A(QgsProcessingAlgorithm):\n    def processAlgorithm(self, parameters, context, feedback):\n        return {}\n",
            [],
            0,
            True,
        ),
    ]
    layered_path = tmp_path / "layered.jsonl"
    manifest_path = tmp_path / "manifest.jsonl"
    layered_lines = []
    manifest_lines = []
    for index, (layer, text, misses, dynamic_count, is_algorithm) in enumerate(
        source_rows
    ):
        source_path = tmp_path / f"source_{index}.py"
        source_path.write_text(text, encoding="utf-8")
        digest = _sha256(source_path)
        relative_path = source_path.name
        layered_lines.append(
            json.dumps(
                {
                    "content_sha256": digest,
                    "canonical_source": {
                        "source_root_id": "fixture",
                        "relative_path": relative_path,
                    },
                    "broad_bucket": "processing_needs_resolution",
                    "primary_layer": layer,
                    "catalog_miss_ids": misses,
                    "dynamic_processing_call_count": dynamic_count,
                    "is_processing_algorithm": is_algorithm,
                    "literal_operator_ids": misses,
                }
            )
        )
        manifest_lines.append(
            json.dumps(
                {
                    "content_sha256": digest,
                    "source_root_id": "fixture",
                    "relative_path": relative_path,
                    "source_path": str(source_path),
                }
            )
        )
    layered_path.write_text("\n".join(layered_lines) + "\n", encoding="utf-8")
    manifest_path.write_text("\n".join(manifest_lines) + "\n", encoding="utf-8")

    rows, summary = MODULE.build_census(layered_path, manifest_path)

    assert len(rows) == 3
    assert summary["input_processing_resolution_records"] == 3
    assert summary["verified_source_records"] == 3
    assert summary["source_failures"] == []
    assert summary["primary_layer_counts"] == {
        "dynamic_or_blank_processing_id": 1,
        "explicit_processing_catalog_miss": 1,
        "processing_algorithm_implementation_or_custom": 1,
    }
    assert summary["dynamic_resolution"]["fully_resolved_records"] == 1
    assert summary["catalog_miss"]["records"] == 1
    assert summary["custom_algorithm"]["records"] == 1


def test_write_outputs_versions_recomputed_census_as_v2(tmp_path: Path) -> None:
    layered_path = tmp_path / "layered.jsonl"
    manifest_path = tmp_path / "manifest.jsonl"
    output_dir = tmp_path / "out"
    layered_path.write_text("{}\n", encoding="utf-8")
    manifest_path.write_text("{}\n", encoding="utf-8")

    MODULE.write_outputs(
        [],
        {
            "input_processing_resolution_records": 0,
            "verified_source_records": 0,
            "source_failures": [],
            "recovery_opportunity_records": {},
        },
        layered_path=layered_path,
        manifest_path=manifest_path,
        output_dir=output_dir,
    )

    assert (output_dir / "resolution_census_v2.jsonl").is_file()
    assert (output_dir / "summary_v2.json").is_file()
    assert (output_dir / "report_v2.md").is_file()
    ledger = json.loads(
        (output_dir / "hash_ledger_v2.json").read_text(encoding="utf-8")
    )
    assert ledger["schema"] == "gis_recommend.hash_ledger.v2"
