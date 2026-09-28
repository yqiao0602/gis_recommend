import unittest

from gis_recommend.data.gee_dataflow_slicer import DataflowDefinition


class CensusGeeSemanticPatternsTests(unittest.TestCase):
    def test_dependency_closure_collects_unresolved_and_call_flags(self):
        from scripts.census_gee_semantic_patterns_3106 import (
            _dependency_closure_evidence,
        )

        definitions = [
            DataflowDefinition("collection@1", "collection", 1, "variable", 0, 1, 1, (), ("source",)),
            DataflowDefinition("region@1", "region", 1, "variable", 1, 2, 2, (), ("Area",)),
            DataflowDefinition(
                "output@1", "output", 1, "variable", 2, 3, 3,
                ("collection@1", "region@1"), (),
            ),
        ]
        calls = {
            4: {
                "ordinal": 4,
                "source_location": {"start_line": 1, "end_line": 1},
                "flags": ["imagecollection_merge_argument_type_mismatch"],
            },
            5: {
                "ordinal": 5,
                "source_location": {"start_line": 3, "end_line": 3},
                "flags": [],
            },
        }

        evidence = _dependency_closure_evidence(definitions, calls, "output@1")

        self.assertEqual(
            evidence["transitive_dependency_ids"],
            ["collection@1", "region@1"],
        )
        self.assertEqual(
            evidence["transitive_unresolved_identifiers"], ["Area", "source"]
        )
        self.assertEqual(evidence["transitive_core_call_ordinals"], [4, 5])
        self.assertEqual(
            evidence["transitive_call_flags"],
            ["imagecollection_merge_argument_type_mismatch"],
        )


if __name__ == "__main__":
    unittest.main()
