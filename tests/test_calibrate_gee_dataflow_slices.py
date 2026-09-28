import unittest

from gis_recommend.data.gee_dataflow_slicer import BackwardSlice, DataflowSliceResult
from scripts.calibrate_gee_dataflow_slices import select_candidate_slice


def slice_(root_id, kind, line, definitions, ordinals):
    return BackwardSlice(
        root_id=root_id,
        root_kind=kind,
        root_line=line,
        definition_ids=tuple(definitions),
        dependency_edges=(),
        core_call_ordinals=tuple(ordinals),
        unresolved_identifiers=(),
    )


class CalibrateGeeDataflowSlicesTests(unittest.TestCase):
    def test_leaf_component_merges_connected_fanout_slices(self):
        result = DataflowSliceResult(
            definitions=(),
            slices=(
                slice_("leaf-a", "unconsumed_core_leaf", 10, ["source@1", "a@1"], [0, 1]),
                slice_("leaf-b", "unconsumed_core_leaf", 11, ["source@1", "b@1"], [0, 2]),
                slice_("sink", "presentation_sink", 12, ["source@1", "shown@1"], [0, 3]),
                slice_("other", "presentation_sink", 20, ["other@1"], [9]),
            ),
            quality_flags=(),
        )

        selected = select_candidate_slice(result)

        self.assertEqual(selected.strategy, "connected_component_with_core_leaves")
        self.assertEqual(selected.root_ids, ("leaf-a", "leaf-b", "sink"))
        self.assertEqual(selected.definition_ids, ("source@1", "a@1", "b@1", "shown@1"))
        self.assertEqual(selected.core_call_ordinals, (0, 1, 2, 3))

    def test_without_leaves_selects_maximal_latest_sink(self):
        result = DataflowSliceResult(
            definitions=(),
            slices=(
                slice_("early", "presentation_sink", 5, ["source@1"], [0]),
                slice_("wide", "presentation_sink", 10, ["source@1", "qa@1"], [0, 1]),
                slice_("latest", "presentation_sink", 20, ["source@1", "qa@1"], [0, 1, 2]),
            ),
            quality_flags=(),
        )

        selected = select_candidate_slice(result)

        self.assertEqual(selected.strategy, "maximal_latest_sink")
        self.assertEqual(selected.root_ids, ("latest",))
        self.assertEqual(selected.core_call_ordinals, (0, 1, 2))


if __name__ == "__main__":
    unittest.main()
