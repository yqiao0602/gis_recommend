from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from gis_recommend.data.qgis_custom_implementation import (
    build_implementation_index,
    expand_custom_implementation,
    extract_custom_implementations,
)


class QgisCustomImplementationTests(unittest.TestCase):
    def test_extracts_process_algorithm_and_inlines_reachable_helper(self) -> None:
        source = '''
class Example(QgsProcessingAlgorithm):
    def name(self):
        return "outer"

    def initAlgorithm(self, config=None):
        processing.run("native:must_be_ignored", {})

    def processAlgorithm(self, parameters, context, feedback):
        prepared = self.prepare(parameters["INPUT"], context, feedback)
        return processing.run(
            "native:fieldcalculator", {"INPUT": prepared, "OUTPUT": "TEMPORARY_OUTPUT"}
        )

    def prepare(self, layer, context, feedback):
        return processing.run(
            "native:buffer", {"INPUT": layer, "OUTPUT": "TEMPORARY_OUTPUT"}
        )["OUTPUT"]
'''

        implementations = extract_custom_implementations(source)

        self.assertEqual(len(implementations), 1)
        implementation = implementations[0]
        self.assertEqual(implementation["algorithm_id"], "script:outer")
        self.assertEqual(
            implementation["literal_operator_ids"],
            ["native:buffer", "native:fieldcalculator"],
        )
        self.assertEqual(implementation["reachable_helpers"], ["prepare"])
        self.assertEqual(implementation["dynamic_operator_count"], 0)
        self.assertEqual(implementation["extraction_status"], "complete_literal_dag")
        self.assertEqual(len(implementation["implementation_body_sha256"]), 64)

    def test_dynamic_processing_id_fails_closed(self) -> None:
        source = '''
class Dynamic(QgsProcessingAlgorithm):
    def name(self):
        return "dynamic"

    def processAlgorithm(self, parameters, context, feedback):
        algorithm_id = parameters["ALGORITHM"]
        return processing.run(algorithm_id, {"INPUT": parameters["INPUT"]})
'''

        implementation = extract_custom_implementations(source)[0]

        self.assertEqual(implementation["literal_operator_ids"], [])
        self.assertEqual(implementation["dynamic_operator_count"], 1)
        self.assertEqual(implementation["extraction_status"], "deferred_dynamic_operator")

    def test_inlines_reachable_module_level_helpers(self) -> None:
        source = '''
def prepare_layer(layer, context, feedback):
    buffered = processing.run("native:buffer", {"INPUT": layer})
    return processing.run("native:dissolve", {"INPUT": buffered["OUTPUT"]})

class Example(QgsProcessingAlgorithm):
    def name(self): return "outer"
    def processAlgorithm(self, parameters, context, feedback):
        prepared = prepare_layer(parameters["INPUT"], context, feedback)
        return processing.run("native:fieldcalculator", {"INPUT": prepared["OUTPUT"]})
'''

        implementation = extract_custom_implementations(source)[0]

        self.assertEqual(
            implementation["literal_operator_ids"],
            ["native:buffer", "native:dissolve", "native:fieldcalculator"],
        )
        self.assertEqual(implementation["reachable_helpers"], ["module:prepare_layer"])

    def test_expands_nested_custom_algorithm_to_standard_dag(self) -> None:
        inner = extract_custom_implementations(
            '''
class Inner(QgsProcessingAlgorithm):
    def name(self): return "inner"
    def processAlgorithm(self, parameters, context, feedback):
        buffered = processing.run("native:buffer", {"INPUT": parameters["INPUT"]})
        return processing.run("native:dissolve", {"INPUT": buffered["OUTPUT"]})
'''
        )[0]
        outer = extract_custom_implementations(
            '''
class Outer(QgsProcessingAlgorithm):
    def name(self): return "outer"
    def processAlgorithm(self, parameters, context, feedback):
        prepared = processing.run("script:inner", {"INPUT": parameters["INPUT"]})
        return processing.run("qgis:fieldcalculator", {"INPUT": prepared["OUTPUT"]})
'''
        )[0]
        index = build_implementation_index([inner, outer])

        result = expand_custom_implementation(
            "script:outer",
            index,
            catalog_ids={"native:buffer", "native:dissolve", "native:fieldcalculator"},
        )

        self.assertEqual(result["expansion_status"], "expanded_complete")
        self.assertEqual(
            result["expanded_operator_ids"],
            ["native:buffer", "native:dissolve", "native:fieldcalculator"],
        )
        self.assertEqual(result["expanded_custom_ids"], ["script:outer", "script:inner"])
        self.assertEqual(result["unresolved_operator_ids"], [])

    def test_ambiguous_implementation_requires_exact_body_binding(self) -> None:
        first = extract_custom_implementations(
            '''
class Shared(QgsProcessingAlgorithm):
    def name(self): return "shared"
    def processAlgorithm(self, parameters, context, feedback):
        return processing.run("native:buffer", {"INPUT": parameters["INPUT"]})
'''
        )[0]
        second = extract_custom_implementations(
            '''
class Shared(QgsProcessingAlgorithm):
    def name(self): return "shared"
    def processAlgorithm(self, parameters, context, feedback):
        return processing.run("native:centroids", {"INPUT": parameters["INPUT"]})
'''
        )[0]
        index = build_implementation_index([first, second])

        unbound = expand_custom_implementation(
            "script:shared",
            index,
            catalog_ids={"native:buffer", "native:centroids"},
        )
        result = expand_custom_implementation(
            "script:shared",
            index,
            catalog_ids={"native:buffer", "native:centroids"},
            implementation_body_bindings={
                "script:shared": first["implementation_body_sha256"]
            },
        )

        self.assertEqual(
            unbound["expansion_status"], "deferred_ambiguous_implementation"
        )
        self.assertEqual(unbound["expanded_operator_ids"], [])
        self.assertEqual(result["expansion_status"], "expanded_complete")
        self.assertEqual(result["expanded_operator_ids"], ["native:buffer"])

    def test_missing_nested_custom_and_cycle_fail_closed(self) -> None:
        missing = extract_custom_implementations(
            '''
class Missing(QgsProcessingAlgorithm):
    def name(self): return "missing"
    def processAlgorithm(self, parameters, context, feedback):
        return processing.run("script:not_found", {"INPUT": parameters["INPUT"]})
'''
        )[0]
        cyclic = extract_custom_implementations(
            '''
class Cyclic(QgsProcessingAlgorithm):
    def name(self): return "cyclic"
    def processAlgorithm(self, parameters, context, feedback):
        return processing.run("script:cyclic", {"INPUT": parameters["INPUT"]})
'''
        )[0]

        missing_result = expand_custom_implementation(
            "script:missing", build_implementation_index([missing]), catalog_ids=set()
        )
        cyclic_result = expand_custom_implementation(
            "script:cyclic", build_implementation_index([cyclic]), catalog_ids=set()
        )

        self.assertEqual(missing_result["expansion_status"], "deferred_missing_implementation")
        self.assertEqual(missing_result["unresolved_operator_ids"], ["script:not_found"])
        self.assertEqual(cyclic_result["expansion_status"], "deferred_recursive_implementation")
        self.assertEqual(cyclic_result["unresolved_operator_ids"], ["script:cyclic"])


if __name__ == "__main__":
    unittest.main()
