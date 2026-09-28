from __future__ import annotations

import unittest
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gis_recommend.data.qgis_conversion_features import extract_conversion_features


class QgisConversionFeatureTests(unittest.TestCase):
    def test_extracts_direct_processing_dependency_edges(self) -> None:
        features = extract_conversion_features(
            '''def run(layer):
    fixed = processing.run("native:fixgeometries", {"INPUT": layer})["OUTPUT"]
    merged = processing.run("native:dissolve", {"INPUT": fixed})["OUTPUT"]
    return processing.run("native:reprojectlayer", {"INPUT": merged})["OUTPUT"]
'''
        )
        self.assertEqual(
            features.data["operator_ids"],
            ["native:fixgeometries", "native:dissolve", "native:reprojectlayer"],
        )
        self.assertEqual(features.data["dependency_edges"], [[0, 1], [1, 2]])
        self.assertEqual(
            features.data["workflow_unit_scope"], "whole_processing_scope"
        )

    def test_rejectable_adjacent_examples_have_no_edges(self) -> None:
        features = extract_conversion_features(
            '''
processing.run("native:fixgeometries", {"INPUT": "a.shp", "OUTPUT": "fixed.shp"})
processing.run("native:buffer", {"INPUT": "other.shp", "OUTPUT": "buffer.shp"})
processing.run("native:intersection", {"INPUT": "third.shp", "OVERLAY": "fourth.shp"})
'''
        )
        self.assertEqual(features.data["dependency_edges"], [])
        self.assertEqual(features.data["unbound_output_indices"], [0, 1, 2])

    def test_signature_ignores_variable_names_and_lines(self) -> None:
        left = extract_conversion_features(
            '''def first(a):
    x = processing.run("native:buffer", {"INPUT": a})["OUTPUT"]
    return processing.run("native:fixgeometries", {"INPUT": x})["OUTPUT"]
'''
        )
        right = extract_conversion_features(
            '''

def renamed(source):
    arbitrary = processing.run("native:buffer", {"INPUT": source})["OUTPUT"]
    return processing.run("native:fixgeometries", {"INPUT": arbitrary})["OUTPUT"]
'''
        )
        self.assertEqual(left.signature_hash, right.signature_hash)

    def test_syntax_error_fails_closed(self) -> None:
        features = extract_conversion_features("def broken(:\n")
        self.assertEqual(features.data["parse_status"], "syntax_error")
        self.assertEqual(features.data["operator_ids"], [])

    def test_limits_features_to_candidate_call_sites(self) -> None:
        source = '''def run(layer):
    unrelated = processing.run("native:centroids", {"INPUT": layer})["OUTPUT"]
    fixed = processing.run("native:fixgeometries", {"INPUT": layer})["OUTPUT"]
    return processing.run("native:dissolve", {"INPUT": fixed})["OUTPUT"]
'''
        features = extract_conversion_features(
            source,
            call_sites=[
                {"operator_id": "native:fixgeometries", "line_start": 3, "line_end": 3},
                {"operator_id": "native:dissolve", "line_start": 4, "line_end": 4},
            ],
        )
        self.assertEqual(
            features.data["operator_ids"],
            ["native:fixgeometries", "native:dissolve"],
        )
        self.assertEqual(features.data["dependency_edges"], [[0, 1]])
        self.assertEqual(
            features.data["candidate_alignment_status"],
            "candidate_alignment_matched",
        )
        self.assertEqual(features.data["workflow_unit_scope"], "local_subworkflow")

    def test_rebinding_uses_only_the_latest_processing_definition(self) -> None:
        features = extract_conversion_features(
            '''def run(layer):
    algresult = processing.run("gdal:translate", {"INPUT": layer})
    algresult = processing.run("native:slope", {"INPUT": algresult["OUTPUT"]})
    algresult = processing.run("gdal:warpreproject", {"INPUT": algresult["OUTPUT"]})
    return algresult
'''
        )
        self.assertEqual(features.data["dependency_edges"], [[0, 1], [1, 2]])

    def test_detects_unknown_calls_that_transform_an_intermediate_output(self) -> None:
        features = extract_conversion_features(
            '''def run(layer):
    memory_layer = context.getMapLayer(
        processing.run("native:buffer", {"INPUT": layer})["OUTPUT"]
    )
    cartogram_features = CartogramFeatures.from_polygon_layer(memory_layer)
    cartogram_features.transform()
    cartogram_features.copy_geometries_back_to_layer(memory_layer)
    buffered_layer = context.getMapLayer(
        processing.run("native:buffer", {"INPUT": memory_layer})["OUTPUT"]
    )
    return buffered_layer
'''
        )
        self.assertEqual(features.data["dependency_edges"], [[0, 1]])
        self.assertEqual(
            features.data["intermediate_data_transform_calls"],
            [
                "from_polygon_layer",
                "transform",
                "copy_geometries_back_to_layer",
            ],
        )

    def test_ignores_unrelated_calls_between_processing_steps(self) -> None:
        features = extract_conversion_features(
            '''def run(layer, feedback):
    fixed = processing.run("native:fixgeometries", {"INPUT": layer})["OUTPUT"]
    feedback.pushInfo("fixed")
    return processing.run("native:dissolve", {"INPUT": fixed})["OUTPUT"]
'''
        )
        self.assertEqual(features.data["intermediate_data_transform_calls"], [])

    def test_annotation_without_value_does_not_break_intermediate_analysis(self) -> None:
        features = extract_conversion_features(
            '''def run(layer):
    fixed = processing.run("native:fixgeometries", {"INPUT": layer})["OUTPUT"]
    marker: str
    return processing.run("native:dissolve", {"INPUT": fixed})["OUTPUT"]
'''
        )
        self.assertEqual(features.data["dependency_edges"], [[0, 1]])
        self.assertEqual(features.data["intermediate_data_transform_calls"], [])

    def test_recovers_result_alias_through_parameter_dictionary(self) -> None:
        features = extract_conversion_features(
            '''def run(vector, raster):
    results = processing.run("native:fixgeometries", {"INPUT": vector})
    fixed_vector_layer = results["OUTPUT"]
    params = {"INPUT_VECTOR": fixed_vector_layer, "INPUT_RASTER": raster}
    processing.run("native:zonalstatisticsfb", params)
'''
        )
        self.assertEqual(features.data["dependency_edges"], [[0, 1]])
        self.assertEqual(
            features.data["feature_extractor_version"],
            "qgis-conversion-features-v8",
        )

    def test_parameter_dict_mutations_use_latest_key_values(self) -> None:
        features = extract_conversion_features(
            '''def run(layer):
    clipped = processing.run("native:clip", {"INPUT": layer})
    params = {"INPUT": clipped["OUTPUT"], "EXPRESSION": "selected"}
    selected = processing.run("native:extractbyexpression", params)
    params["EXPRESSION"] = "attached"
    attached = processing.run("native:extractbyexpression", params)
    params["EXPRESSION"] = "detached"
    detached = processing.run("native:extractbyexpression", params)
    params = {"INPUT": attached["OUTPUT"], "DISTANCE": 10}
    attached_buffer = processing.run("native:buffer", params)
    params["INPUT"] = detached["OUTPUT"]
    detached_buffer = processing.run("native:buffer", params)
    params = {"INPUT": selected["OUTPUT"], "OVERLAY": attached_buffer["OUTPUT"]}
    intersection = processing.run("native:intersection", params)
    params["INPUT"] = intersection["OUTPUT"]
    params["OVERLAY"] = detached_buffer["OUTPUT"]
    processing.run("native:difference", params)
'''
        )
        self.assertEqual(
            features.data["dependency_edges"],
            [
                [0, 1],
                [0, 2],
                [0, 3],
                [1, 6],
                [2, 4],
                [3, 5],
                [4, 6],
                [5, 7],
                [6, 7],
            ],
        )

    def test_flags_unresolved_processing_output_reference(self) -> None:
        features = extract_conversion_features(
            '''def run(layer):
    interesection = processing.run("native:intersection", {"INPUT": layer})
    return processing.run("native:difference", {"INPUT": intersection["OUTPUT"]})
'''
        )
        self.assertEqual(features.data["dependency_edges"], [])
        self.assertEqual(
            features.data["unresolved_output_references"],
            [
                {
                    "consumer_index": 1,
                    "reference": "name:intersection.key:OUTPUT",
                }
            ],
        )

    def test_detects_downstream_helper_consuming_final_output(self) -> None:
        features = extract_conversion_features(
            '''def run(layer, output_path):
    processing.run("native:clip", {"INPUT": layer, "OUTPUT": output_path})
    clipped = QgsVectorLayer(output_path, "clipped", "ogr")
    accessibility_analysis(clipped)
'''
        )
        self.assertEqual(
            features.data["downstream_data_transform_calls"],
            ["accessibility_analysis"],
        )

    def test_flags_nonfinal_temporary_terminal_output(self) -> None:
        features = extract_conversion_features(
            '''def run(layer):
    root = processing.run("native:buffer", {"INPUT": layer})["OUTPUT"]
    processing.run("native:centroids", {"INPUT": root, "OUTPUT": "TEMPORARY_OUTPUT"})
    return processing.run("native:fixgeometries", {"INPUT": root})["OUTPUT"]
'''
        )
        self.assertEqual(features.data["dependency_edges"], [[0, 1], [0, 2]])
        self.assertEqual(features.data["unused_temporary_terminal_indices"], [1])

    def test_recovers_static_output_path_consumed_by_next_call(self) -> None:
        features = extract_conversion_features(
            '''def run(layer, mask, folder):
    clipped_path = os.path.join(folder, "clipped.gpkg")
    processing.run("native:clip", {"INPUT": layer, "OVERLAY": mask, "OUTPUT": clipped_path})
    processing.run("native:fixgeometries", {"INPUT": clipped_path, "OUTPUT": "fixed.gpkg"})
'''
        )
        self.assertEqual(features.data["dependency_edges"], [[0, 1]])

    def test_recovers_static_path_with_qgis_provider_uri_suffix(self) -> None:
        features = extract_conversion_features(
            '''def run(vector, raster):
    processing.run("native:dissolve", {"INPUT": vector, "OUTPUT": "dissolved.gpkg"})
    processing.run("gdal:cliprasterbymasklayer", {
        "INPUT": raster,
        "MASK": "dissolved.gpkg|layername=dissolved",
        "OUTPUT": "clipped.tif",
    })
'''
        )
        self.assertEqual(features.data["dependency_edges"], [[0, 1]])
        self.assertEqual(
            features.data["dependency_edge_evidence"],
            [
                {
                    "producer_index": 0,
                    "consumer_index": 1,
                    "kinds": ["static_output_path"],
                }
            ],
        )

    def test_shared_temporary_output_literal_does_not_create_path_edge(self) -> None:
        features = extract_conversion_features(
            '''def run(left, right):
    processing.run("native:buffer", {"INPUT": left, "OUTPUT": "TEMPORARY_OUTPUT"})
    processing.run("native:centroids", {"INPUT": right, "OUTPUT": "TEMPORARY_OUTPUT"})
'''
        )
        self.assertEqual(features.data["dependency_edges"], [])

    def test_flags_provider_input_type_conflict_from_layer_constructor(self) -> None:
        features = extract_conversion_features(
            '''raster_layer = QgsRasterLayer("input.tif", "input")
processing.run("native:buffer", {"INPUT": raster_layer, "OUTPUT": "memory:"})
'''
        )

        self.assertEqual(
            features.data["provider_input_type_conflicts"],
            [
                {
                    "consumer_index": 0,
                    "operator_id": "native:buffer",
                    "parameter": "INPUT",
                    "required_type": "vector",
                    "actual_type": "raster",
                    "evidence": "constructor:QgsRasterLayer",
                }
            ],
        )

    def test_unknown_provider_input_type_does_not_create_conflict(self) -> None:
        features = extract_conversion_features(
            '''def run(layer):
    return processing.run("native:buffer", {"INPUT": layer})
'''
        )

        self.assertEqual(features.data["provider_input_type_conflicts"], [])
        self.assertEqual(features.data["provider_input_type_status"], "unknown")

    def test_flags_provider_conflict_from_processing_output_type(self) -> None:
        features = extract_conversion_features(
            '''def run(vector):
    raster = processing.run("gdal:rasterize", {"INPUT": vector})["OUTPUT"]
    return processing.run("native:buffer", {"INPUT": raster})
'''
        )

        self.assertEqual(
            features.data["provider_input_type_conflicts"],
            [
                {
                    "consumer_index": 1,
                    "operator_id": "native:buffer",
                    "parameter": "INPUT",
                    "required_type": "vector",
                    "actual_type": "raster",
                    "evidence": "processing_output:gdal:rasterize",
                }
            ],
        )

    def test_uses_function_argument_annotation_as_provider_type_evidence(self) -> None:
        features = extract_conversion_features(
            '''def run(layer: QgsRasterLayer):
    return processing.run("native:buffer", {"INPUT": layer})
'''
        )

        self.assertEqual(
            features.data["provider_input_type_conflicts"][0]["evidence"],
            "annotation:QgsRasterLayer",
        )

    def test_flags_mixed_layer_collection_for_vector_only_parameter(self) -> None:
        features = extract_conversion_features(
            '''vector = QgsVectorLayer("input.shp", "vector")
raster = QgsRasterLayer("input.tif", "raster")
processing.run("native:mergevectorlayers", {"LAYERS": [vector, raster]})
'''
        )

        self.assertEqual(features.data["provider_input_type_status"], "conflict")
        self.assertEqual(
            features.data["provider_input_type_conflicts"][0]["actual_type"],
            "mixed",
        )

    def test_propagates_raster_calculator_output_type(self) -> None:
        features = extract_conversion_features(
            '''raster = processing.run("gdal:rastercalculator", {
    "INPUT_A": "input.tif",
    "OUTPUT": "calculated.tif",
})["OUTPUT"]
processing.run("native:buffer", {"INPUT": raster})
'''
        )

        self.assertEqual(
            features.data["provider_input_type_conflicts"][0]["evidence"],
            "processing_output:gdal:rastercalculator",
        )

    def test_flags_processing_temporary_input_literal(self) -> None:
        features = extract_conversion_features(
            '''def run(mask):
    processing.run("native:fillnodata", {"INPUT": "dsm.tif", "OUTPUT": "TEMPORARY_OUTPUT"})
    processing.run("gdal:cliprasterbymasklayer", {
        "INPUT": "C:/Users/susan/AppData/Local/Temp/processing_PmeyZF/abc/OUTPUT.tif",
        "MASK": mask,
        "OUTPUT": "clipped.tif",
    })
'''
        )
        self.assertEqual(
            features.data["processing_temporary_input_references"],
            [
                {
                    "consumer_index": 1,
                    "parameter": "INPUT",
                    "value": "C:/Users/susan/AppData/Local/Temp/processing_PmeyZF/abc/OUTPUT.tif",
                }
            ],
        )


if __name__ == "__main__":
    unittest.main()
