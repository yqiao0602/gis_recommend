import unittest


class BuildGeeSemanticAuthorityReviewPacketTests(unittest.TestCase):
    def test_groups_only_accepted_rows_by_unique_source_authority(self):
        from scripts.build_gee_semantic_authority_review_packet import (
            build_authority_review_packet,
            flatten_representatives,
        )

        rows = [
            {
                "semantic_status": "accepted_proposal",
                "source_sha256": "a" * 64,
                "source_path": "/home/yll/GEE/Data/a.txt",
                "pattern": "annual_mean_clip",
                "definition_id": "mean_a@1",
                "source_snippet": "1: var mean_a = collection.mean().clip(region);",
            },
            {
                "semantic_status": "accepted_proposal",
                "source_sha256": "a" * 64,
                "source_path": "/home/yll/GEE/Data/a.txt",
                "pattern": "annual_mean_clip",
                "definition_id": "mean_b@1",
                "source_snippet": "2: var mean_b = collection.mean().clip(region);",
            },
            {
                "semantic_status": "accepted_proposal",
                "source_sha256": "b" * 64,
                "source_path": "/home/yll/GEE/Data/b.txt",
                "pattern": "year_polarization_preprocess",
                "definition_id": "preprocess@1",
                "source_snippet": "1: var collection = ee.ImageCollection('X');",
            },
            {
                "semantic_status": "fail_closed",
                "source_sha256": "c" * 64,
                "source_path": "/home/yll/GEE/Data/c.txt",
                "pattern": "annual_mean_clip",
                "definition_id": "blocked@1",
                "source_snippet": "1: var blocked = unknown.mean().clip(aoi);",
            },
        ]

        packet, summary = build_authority_review_packet(rows)

        self.assertEqual(len(packet), 2)
        self.assertEqual(summary["counts"]["accepted_proposal_rows"], 3)
        self.assertEqual(summary["counts"]["independent_source_authorities"], 2)
        self.assertEqual(summary["counts"]["authority_pattern_representatives"], 2)
        self.assertEqual(summary["pattern_authority_counts"], {
            "annual_mean_clip": 1,
            "year_polarization_preprocess": 1,
        })
        authority_a = next(row for row in packet if row["source_sha256"] == "a" * 64)
        self.assertEqual(authority_a["proposal_count"], 2)
        self.assertEqual(authority_a["proposal_definition_ids"], ["mean_a@1", "mean_b@1"])
        self.assertEqual(authority_a["representative_definition_ids"], ["mean_a@1"])
        self.assertEqual(authority_a["human_adjudication"], "")
        self.assertEqual(authority_a["training_rows_emitted"], 0)
        representatives = flatten_representatives(packet)
        self.assertEqual(len(representatives), 2)
        self.assertEqual(representatives[0]["human_completeness"], "")
        self.assertTrue(all(row["training_rows_emitted"] == 0 for row in representatives))


if __name__ == "__main__":
    unittest.main()
