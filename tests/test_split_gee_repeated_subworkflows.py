import unittest
from pathlib import Path
import shutil
import tempfile

from gis_recommend.data.gee_dataflow_slicer import LocalSubworkflowUnit
from scripts.split_gee_repeated_subworkflows import (
    build_repeated_subworkflow_rows,
    propagate_unit_blockers,
    select_repeated_unit_ids,
    write_outputs,
)


ROOT = Path(__file__).resolve().parents[1]
AUTHORITY_DIR = (
    ROOT
    / "docs/reports/gee_raster_core_v1_review_split_2026-07-24"
    / "gee_raster_core_batch_training_package_v1/strict_candidate_v1"
    / "source_audit_60_v1/authority_v2_3_0"
)
REPLAY = AUTHORITY_DIR / "strict_candidate_source_replay_60_v1.jsonl"
ID_MAPPINGS = ROOT / "outputs_v2/id_mappings_v2.json"


def unit(definition_id, dependencies, unresolved=()):
    return LocalSubworkflowUnit(
        definition_id=definition_id,
        target=definition_id.split("@", 1)[0],
        kind="variable",
        start_line=1,
        end_line=1,
        dependency_ids=tuple(dependencies),
        core_call_ordinals=(0,),
        unresolved_identifiers=tuple(unresolved),
    )


class SplitGeeRepeatedSubworkflowsTests(unittest.TestCase):
    def test_selects_cat_select_terminals_and_local_ancestors_only(self):
        units = (
            unit("source@1", ()),
            unit("leaf@1", ("source@1",)),
            unit("concat@1", ("leaf@1", "leaf2@1")),
            unit("leaf2@1", ("source@1",)),
            unit("unrelated@1", ()),
        )
        canonical = {
            "source@1": ("ee.imagecollection.filter",),
            "leaf@1": ("ee.imagecollection.mean", "ee.image.clip"),
            "leaf2@1": ("ee.imagecollection.mean", "ee.image.clip"),
            "concat@1": ("ee.image.cat", "ee.image.select"),
            "unrelated@1": ("ee.image.clip",),
        }

        selected = select_repeated_unit_ids(units, canonical)

        self.assertEqual(selected, ("source@1", "leaf@1", "concat@1", "leaf2@1"))

    def test_blockers_propagate_to_downstream_concat(self):
        units = (
            unit("source@1", ()),
            unit("leaf_ok@1", ("source@1",)),
            unit("leaf_bad@1", ("source@1",), unresolved=("missing_region",)),
            unit("concat@1", ("leaf_ok@1", "leaf_bad@1")),
        )

        blockers = propagate_unit_blockers(units, direct_blockers={})

        self.assertEqual(blockers["source@1"], ())
        self.assertEqual(blockers["leaf_bad@1"], ("unresolved_identifiers",))
        self.assertEqual(blockers["concat@1"], ("upstream_blocked:leaf_bad@1",))

    def test_rank_58_builds_repeated_units_without_granting_training_admission(self):
        rows, summary = build_repeated_subworkflow_rows(
            replay_jsonl=REPLAY,
            id_mappings_json=ID_MAPPINGS,
            audit_rank=58,
        )

        self.assertEqual(len(rows), 48)
        self.assertEqual(summary["counts"]["selected_units"], 48)
        self.assertEqual(summary["counts"]["complete_pending_fidelity_gate"], 38)
        self.assertEqual(summary["counts"]["fail_closed"], 10)
        self.assertEqual(summary["counts"]["training_rows_emitted"], 0)
        self.assertEqual(
            summary["decision"]["training_admission"],
            "not_granted_repeated_subworkflow_split",
        )
        self.assertTrue(all(row["training_rows_emitted"] == 0 for row in rows))
        self.assertTrue(all(not row["validation_eligible"] for row in rows))
        self.assertTrue(all(not row["test_eligible"] for row in rows))

    def test_writes_review_artifacts_without_training_export(self):
        rows, summary = build_repeated_subworkflow_rows(
            replay_jsonl=REPLAY,
            id_mappings_json=ID_MAPPINGS,
            audit_rank=58,
        )
        output_dir = Path(tempfile.mkdtemp(prefix="gee-repeated-split-"))
        try:
            paths = write_outputs(rows, summary, output_dir)
            self.assertEqual(
                set(paths), {"jsonl", "summary", "report", "hash_ledger"}
            )
            self.assertTrue(all(path.exists() for path in paths.values()))
            self.assertFalse(any("train" in path.name for path in paths.values()))
        finally:
            shutil.rmtree(output_dir, ignore_errors=True)


if __name__ == "__main__":
    unittest.main()
