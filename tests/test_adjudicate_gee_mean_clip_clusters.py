import unittest


class AdjudicateGeeMeanClipClustersTests(unittest.TestCase):
    def test_default_output_reuses_existing_long_path_directory(self):
        from scripts.adjudicate_gee_mean_clip_clusters import BASE_DIR, DEFAULT_OUTPUT_DIR

        self.assertEqual(DEFAULT_OUTPUT_DIR, BASE_DIR)

    def test_validates_identity_and_fails_closed_below_quality_gate(self):
        from scripts.adjudicate_gee_mean_clip_clusters import summarize_adjudications

        review_rows = [
            {
                "review_index": 1,
                "cluster_id": "cluster-a",
                "representative_source_sha256": "a" * 64,
                "human_completeness": "",
                "human_fidelity": "",
                "human_adjudication": "",
                "human_notes": "",
            },
            {
                "review_index": 2,
                "cluster_id": "cluster-b",
                "representative_source_sha256": "b" * 64,
                "human_completeness": "",
                "human_fidelity": "",
                "human_adjudication": "",
                "human_notes": "",
            },
        ]
        adjudications = [
            {
                "review_index": 1,
                "cluster_id": "cluster-a",
                "source_sha256": "a" * 64,
                "human_adjudication": "accept_core",
                "training_rows_emitted": 0,
            },
            {
                "review_index": 2,
                "cluster_id": "cluster-b",
                "source_sha256": "b" * 64,
                "human_adjudication": "defer_unresolved_region",
                "training_rows_emitted": 0,
            },
        ]

        rollup, summary = summarize_adjudications(review_rows, adjudications)

        self.assertEqual([row["review_index"] for row in rollup], [1, 2])
        self.assertEqual(summary["counts"]["accept_core"], 1)
        self.assertEqual(summary["counts"]["defer"], 1)
        self.assertEqual(summary["observed_precision"], 0.5)
        self.assertFalse(summary["gate"]["promotion_eligible"])
        self.assertEqual(summary["training_rows_emitted"], 0)

        adjudications[1]["cluster_id"] = "wrong-cluster"
        with self.assertRaisesRegex(ValueError, "identity mismatch"):
            summarize_adjudications(review_rows, adjudications)

    def test_repaired_rule_passes_only_with_exact_35_cluster_agreement(self):
        from scripts.adjudicate_gee_mean_clip_clusters import calibrate_repaired_rule

        review_rows = []
        adjudications = []
        repaired_rows = []
        for index in range(1, 36):
            source_sha = f"{index:064x}"
            definition_id = f"output{index}@1"
            accepted = index <= 22
            review_rows.append(
                {
                    "review_index": index,
                    "cluster_id": f"cluster-{index}",
                    "representative_source_sha256": source_sha,
                    "representative_definition_id": definition_id,
                }
            )
            adjudications.append(
                {
                    "review_index": index,
                    "human_adjudication": (
                        "accept_core" if accepted else "defer_unresolved_collection"
                    ),
                }
            )
            repaired_rows.append(
                {
                    "source_sha256": source_sha,
                    "definition_id": definition_id,
                    "canonical_operator_sequence": [
                        "ee.imagecollection.mean",
                        "ee.image.clip",
                    ],
                    "l3_code_sequence": ["L3_10_02_03", "L3_03_01_01"],
                    "semantic_status": (
                        "accepted_proposal" if accepted else "fail_closed"
                    ),
                }
            )

        calibration_rows, summary = calibrate_repaired_rule(
            review_rows, adjudications, repaired_rows
        )

        self.assertEqual(len(calibration_rows), 35)
        self.assertEqual(summary["confusion_matrix"], {"tp": 22, "fp": 0, "tn": 13, "fn": 0})
        self.assertEqual(summary["observed_precision"], 1.0)
        self.assertGreater(summary["wilson_lower_95"], 0.80)
        self.assertTrue(summary["gate"]["promotion_eligible"])
        self.assertEqual(summary["exporter_input_candidates"], 22)
        self.assertEqual(
            sum(row["eligible_for_exporter_input"] for row in calibration_rows),
            22,
        )
        self.assertEqual(
            calibration_rows[0]["canonical_operator_sequence"],
            ["ee.imagecollection.mean", "ee.image.clip"],
        )
        self.assertEqual(summary["training_rows_emitted"], 0)


if __name__ == "__main__":
    unittest.main()
