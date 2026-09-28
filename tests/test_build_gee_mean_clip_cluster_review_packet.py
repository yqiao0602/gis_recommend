import unittest


class BuildGeeMeanClipClusterReviewPacketTests(unittest.TestCase):
    def test_collapses_whitespace_near_duplicates_and_keeps_review_closed(self):
        from scripts.build_gee_mean_clip_cluster_review_packet import (
            build_cluster_review_packet,
        )

        rows = [
            {
                "pattern": "annual_mean_clip",
                "source_sha256": "a" * 64,
                "source_path": "/home/yll/GEE/Data/data1/script_1.txt",
                "sample_id": "sample-a",
                "definition_id": "mean_a@1",
                "canonical_operator_sequence": [
                    "ee.imagecollection.mean",
                    "ee.image.clip",
                ],
                "l3_code_sequence": ["L3_10_02_03", "L3_03_01_01"],
                "semantic_facts": {"image_input": "collection_a"},
                "source_snippet": "1: var out = collection_a.mean().clip(region);",
            },
            {
                "pattern": "annual_mean_clip",
                "source_sha256": "b" * 64,
                "source_path": "/home/yll/GEE/Data/data1/script_2.txt",
                "sample_id": "sample-b",
                "definition_id": "mean_b@1",
                "canonical_operator_sequence": [
                    "ee.imagecollection.mean",
                    "ee.image.clip",
                ],
                "l3_code_sequence": ["L3_10_02_03", "L3_03_01_01"],
                "semantic_facts": {"image_input": "collection_b"},
                "source_snippet": "1: var out=collection_b.mean().clip(region);",
            },
            {
                "pattern": "annual_mean_clip",
                "source_sha256": "c" * 64,
                "source_path": "/home/yll/GEE/Data/data1/script_3.txt",
                "sample_id": "sample-c",
                "definition_id": "mean_c@1",
                "canonical_operator_sequence": [
                    "ee.imagecollection.mean",
                    "ee.image.clip",
                ],
                "l3_code_sequence": ["L3_10_02_03", "L3_03_01_01"],
                "semantic_facts": {"image_input": "collection_c"},
                "source_snippet": "1: var out = collection_c.mean().clip(region);",
            },
            {
                "pattern": "year_polarization_preprocess",
                "source_sha256": "d" * 64,
                "source_path": "/home/yll/GEE/Data/data1/script_4.txt",
                "sample_id": "sample-d",
                "definition_id": "preprocess@1",
            },
        ]
        source_texts = {
            "a" * 64: "var x = 1;\nvar out = collection.mean().clip(region);\n",
            "b" * 64: "var   x = 1; var out = collection.mean().clip(region);",
            "c" * 64: "function unrelated() { return ee.Image(1); }",
        }

        packet, summary = build_cluster_review_packet(
            rows,
            source_texts,
            similarity_threshold=0.8,
        )

        self.assertEqual(summary["counts"]["eligible_authorities"], 3)
        self.assertEqual(summary["counts"]["conservative_template_clusters"], 2)
        self.assertEqual(summary["counts"]["collapsed_authorities"], 1)
        self.assertEqual(summary["counts"]["near_duplicate_pairs"], 1)
        duplicate = next(row for row in packet if row["cluster_member_count"] == 2)
        self.assertEqual(
            duplicate["cluster_source_sha256s"],
            ["a" * 64, "b" * 64],
        )
        self.assertEqual(duplicate["human_completeness"], "")
        self.assertEqual(duplicate["human_fidelity"], "")
        self.assertEqual(duplicate["human_adjudication"], "")
        self.assertEqual(duplicate["training_rows_emitted"], 0)
        self.assertTrue(all(row["pattern"] == "annual_mean_clip" for row in packet))
        self.assertTrue(
            all(
                row["training_admission"]
                == "not_granted_gee_mean_clip_cluster_review"
                for row in packet
            )
        )


if __name__ == "__main__":
    unittest.main()
