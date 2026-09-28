import unittest
from pathlib import Path

from scripts.review_gee_repeated_subworkflow_structure import review_structure_rows
from scripts.audit_gee_repeated_subworkflow_semantic_completeness import review_semantic_rows


ROOT = Path(__file__).resolve().parents[1]
AUTHORITY_DIR = (
    ROOT
    / "docs/reports/gee_raster_core_v1_review_split_2026-07-24"
    / "gee_raster_core_batch_training_package_v1/strict_candidate_v1"
    / "source_audit_60_v1/authority_v2_3_0"
)
FIDELITY_JSONL = (
    AUTHORITY_DIR
    / "repeated_subworkflow_fidelity_gate_v1"
    / "strict_candidate_repeated_subworkflow_fidelity_rank58_v1.jsonl"
)
REPLAY_JSONL = AUTHORITY_DIR / "strict_candidate_source_replay_60_v1.jsonl"


class ReviewGeeRepeatedSubworkflowStructureTests(unittest.TestCase):
    @staticmethod
    def _mean_clip_row(snippet, *, dependencies, unresolved=None):
        return {
            "pattern": "annual_mean_clip",
            "target_variable": "out",
            "target_family": None,
            "year_literal": None,
            "polarization": None,
            "dependency_ids": dependencies,
            "selected_dependency_ids": dependencies,
            "unresolved_identifiers": unresolved or [],
            "source_snippet": snippet,
        }

    def test_source_backed_review_classifies_only_verified_patterns(self):
        rows, summary = review_structure_rows(
            fidelity_jsonl=FIDELITY_JSONL,
            replay_jsonl=REPLAY_JSONL,
            audit_rank=58,
        )

        self.assertEqual(len(rows), 38)
        self.assertEqual(
            summary["counts"]["review_proposals"], 38
        )
        self.assertEqual(
            summary["pattern_counts"],
            {
                "annual_mean_clip": 24,
                "polarization_concat_select": 6,
                "year_polarization_preprocess": 8,
            },
        )
        self.assertTrue(all(row["source_snippet"] for row in rows))
        self.assertTrue(all(row["call_site_evidence"] for row in rows))
        self.assertTrue(all(row["review_status"] == "proposal_only" for row in rows))
        self.assertTrue(all(row["training_rows_emitted"] == 0 for row in rows))
        self.assertEqual(summary["counts"]["training_rows_emitted"], 0)
        self.assertFalse(summary["decision"]["training_admission"] == "granted")

    def test_semantic_review_accepts_only_source_visible_complete_facts(self):
        rows, _ = review_structure_rows(
            fidelity_jsonl=FIDELITY_JSONL,
            replay_jsonl=REPLAY_JSONL,
            audit_rank=58,
        )
        reviewed, summary = review_semantic_rows(rows)

        self.assertEqual(len(reviewed), 38)
        self.assertEqual(summary["counts"]["accepted_proposal"], 38)
        self.assertEqual(summary["counts"]["fail_closed"], 0)
        self.assertEqual(summary["counts"]["training_rows_emitted"], 0)
        self.assertTrue(all(row["semantic_status"] == "accepted_proposal" for row in reviewed))
        self.assertTrue(all(row["semantic_limitations"] for row in reviewed))
        self.assertTrue(all(row["training_admission"].startswith("not_granted") for row in reviewed))

    def test_semantic_review_fails_closed_on_polarization_mismatch(self):
        rows, _ = review_structure_rows(
            fidelity_jsonl=FIDELITY_JSONL,
            replay_jsonl=REPLAY_JSONL,
            audit_rank=58,
        )
        candidate = next(row for row in rows if row["pattern"] == "year_polarization_preprocess")
        candidate["source_snippet"] = candidate["source_snippet"].replace("'VV'", "'VH'", 1)

        reviewed, summary = review_semantic_rows([candidate])

        self.assertEqual(summary["counts"]["fail_closed"], 1)
        self.assertEqual(reviewed[0]["semantic_status"], "fail_closed")
        self.assertIn("filter_polarization_mismatch", reviewed[0]["semantic_reasons"])

    def test_semantic_review_parses_source_backed_mean_clip_variants(self):
        rows = [
            self._mean_clip_row(
                "1: var out = collection.mean().clip(region);",
                dependencies=["collection@1", "region@1"],
            ),
            self._mean_clip_row(
                "1: var out = ee.Image(collection.mean()).clip(region);",
                dependencies=["collection@1", "region@1"],
            ),
            self._mean_clip_row(
                "1: out = out.mean().clip(region);",
                dependencies=["out@1", "region@1"],
            ),
            self._mean_clip_row(
                "1: var out = collection.mean()\n2:   .clip(region);",
                dependencies=["collection@1", "region@1"],
            ),
        ]

        reviewed, summary = review_semantic_rows(rows)

        self.assertEqual(summary["counts"]["accepted_proposal"], 4)
        self.assertTrue(all(row["semantic_status"] == "accepted_proposal" for row in reviewed))

    def test_semantic_review_rejects_nested_presentation_mean_clip(self):
        row = self._mean_clip_row(
            "1: var chart = ui.Chart.image.histogram(\n2:   collection.mean().clip(region), region, 200);",
            dependencies=["collection@1", "region@1"],
        )

        reviewed, summary = review_semantic_rows([row])

        self.assertEqual(summary["counts"]["fail_closed"], 1)
        self.assertIn("mean_clip_not_assignment_core", reviewed[0]["semantic_reasons"])

    def test_mean_clip_fails_closed_on_transitive_provenance_errors(self):
        row = self._mean_clip_row(
            "1: var out = collection.mean().clip(region);",
            dependencies=["collection@1", "region@1"],
        )
        row["transitive_unresolved_identifiers"] = ["Area"]
        row["transitive_call_flags"] = [
            "imagecollection_merge_argument_type_mismatch"
        ]

        reviewed, _ = review_semantic_rows([row])

        self.assertEqual(reviewed[0]["semantic_status"], "fail_closed")
        self.assertIn(
            "transitive_unresolved_upstream_identifier",
            reviewed[0]["semantic_reasons"],
        )
        self.assertIn(
            "invalid_upstream_collection_type",
            reviewed[0]["semantic_reasons"],
        )

    def test_semantic_review_rejects_non_calibrated_concat_shape(self):
        row = {
            "pattern": "polarization_concat_select",
            "target_variable": "data",
            "target_family": None,
            "year_literal": None,
            "polarization": None,
            "dependency_ids": ["med@1", "slice@1"],
            "selected_dependency_ids": ["med@1", "slice@1"],
            "unresolved_identifiers": [],
            "source_snippet": (
                '1: var data = ee.Image.cat([med, slice])\n'
                '2:   .select(["blue", "blue_1", "green", "green_1"]);'
            ),
        }

        reviewed, summary = review_semantic_rows([row])

        self.assertEqual(summary["counts"]["fail_closed"], 1)
        self.assertIn("concat_shape_semantic_mismatch", reviewed[0]["semantic_reasons"])
        self.assertNotIn("missing_concat_select_chain", reviewed[0]["semantic_reasons"])

    def test_source_authority_counts_keep_candidate_proposal_and_acceptance_scopes(self):
        from scripts.census_gee_semantic_patterns_3106 import source_authority_counts

        candidates = [
            {"source_sha256": "a"},
            {"source_sha256": "b"},
            {"source_sha256": "c"},
        ]
        proposals = [
            {"source_sha256": "a"},
            {"source_sha256": "a"},
            {"source_sha256": "b"},
        ]
        accepted = [{"source_sha256": "a"}]

        self.assertEqual(
            source_authority_counts(candidates, proposals, accepted),
            {
                "verified_candidate_source_authorities": 3,
                "proposal_source_authorities": 2,
                "accepted_source_authorities": 1,
            },
        )

    def test_semantic_review_propagates_failed_upstream_proposals(self):
        rows = []
        dependency_ids = []
        for year in range(2016, 2020):
            definition_id = f"series{year}@1"
            dependency_ids.append(definition_id)
            rows.append(
                {
                    **self._mean_clip_row(
                        f"1: var series{year} = collection{year}.mean().clip(region);",
                        dependencies=(
                            [f"collection{year}@1"]
                            if year == 2016
                            else [f"collection{year}@1", "region@1"]
                        ),
                        unresolved=["region"] if year == 2016 else [],
                    ),
                    "definition_id": definition_id,
                    "target_variable": f"series{year}",
                    "year_literal": str(year),
                }
            )
        rows.append(
            {
                "pattern": "polarization_concat_select",
                "definition_id": "seriesVV@1",
                "target_variable": "seriesVV",
                "target_family": "series",
                "year_literal": None,
                "polarization": "VV",
                "dependency_ids": dependency_ids,
                "selected_dependency_ids": dependency_ids,
                "unresolved_identifiers": [],
                "source_snippet": (
                    "1: var seriesVV = ee.Image.cat(series2016, series2017, series2018, series2019)\n"
                    '2:   .select(["VV", "VV_1", "VV_2", "VV_3"], '
                    '["2016", "2017", "2018", "2019"]);'
                ),
            }
        )

        reviewed, summary = review_semantic_rows(rows)

        downstream = next(row for row in reviewed if row["definition_id"] == "seriesVV@1")
        self.assertEqual(downstream["semantic_status"], "fail_closed")
        self.assertIn("semantic_dependency_not_accepted", downstream["semantic_reasons"])
        self.assertEqual(summary["counts"]["fail_closed"], 2)


if __name__ == "__main__":
    unittest.main()
