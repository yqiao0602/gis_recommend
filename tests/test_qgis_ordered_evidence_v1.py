import csv
import json
import tempfile
import unittest
from pathlib import Path

from gis_recommend.data.qgis_pilot import (
    build_ordered_evidence,
    map_ordered_evidence_to_taxonomy,
)
from scripts.build_qgis_ordered_evidence_v1 import build_ordered_dataset
from scripts.build_qgis_crosswalk_v1_114 import build_crosswalk


class QgisOrderedEvidenceV1Tests(unittest.TestCase):
    def test_crosswalk_preserves_stable_bridges_and_audits_reviewed_overrides(self):
        taxonomy = {
            "profile": "fixture_114",
            "base_class_count": 1,
            "code_to_token_id": {"L3_BASE": 0, "L3_NEW": 1},
            "alias_to_code": {"native:newop": "L3_NEW"},
        }
        base_crosswalk = {
            "entries": {
                "native:baseop": {
                    "bridge_type": "l3_bridge",
                    "l3_code": "L3_BASE",
                    "status": "accepted",
                },
                "native:newop": {
                    "bridge_type": "rejected",
                    "l3_code": "",
                    "status": "rejected",
                },
            }
        }

        merged = build_crosswalk(taxonomy, base_crosswalk)

        self.assertEqual(merged["alias_to_code"]["native:baseop"], "L3_BASE")
        self.assertEqual(merged["alias_to_code"]["native:newop"], "L3_NEW")
        self.assertEqual(merged["reviewed_overrides"][0]["previous_bridge_type"], "rejected")
        self.assertEqual(merged["entries"]["native:newop"]["source"], "taxonomy_114_reviewed_alias")

    def test_crosswalk_rejects_unreviewed_semantic_reassignment(self):
        taxonomy = {
            "profile": "fixture_114",
            "base_class_count": 1,
            "code_to_token_id": {"L3_BASE": 0, "L3_NEW": 1},
            "alias_to_code": {"native:conflict": "L3_NEW"},
        }
        base_crosswalk = {
            "entries": {
                "native:conflict": {
                    "bridge_type": "l3_bridge",
                    "l3_code": "L3_BASE",
                }
            }
        }

        with self.assertRaisesRegex(ValueError, "conflicts with stable L3 bridge"):
            build_crosswalk(taxonomy, base_crosswalk)

    def test_exact_mapping_preserves_order_duplicates_and_unmapped_steps(self):
        taxonomy = {
            "profile": "fixture_114",
            "code_to_token_id": {"L3_FIX": 94},
            "alias_to_code": {"native:fixgeometries": "L3_FIX"},
        }
        evidence = build_ordered_evidence(
            [
                {
                    "id": "3",
                    "statement_index": "30",
                    "api_source_type": "direct_api",
                    "normalized_api_name": "QgsGeometry.buffer",
                },
                {
                    "id": "1",
                    "statement_index": "10",
                    "api_source_type": "qgis_processing_algorithm",
                    "normalized_api_name": "processing.run:native:fixgeometries",
                },
                {
                    "id": "2",
                    "statement_index": "20",
                    "api_source_type": "qgis_processing_algorithm",
                    "normalized_api_name": "native:fixgeometries",
                },
            ]
        )

        mapped = map_ordered_evidence_to_taxonomy(evidence, taxonomy)

        self.assertEqual(mapped["mapped_l3_chain"], ["L3_FIX", "L3_FIX"])
        self.assertEqual([step["step_id"] for step in mapped["ordered_steps"]], ["1", "2", "3"])
        self.assertEqual(mapped["unmapped_steps"][0]["normalized_operation"], "qgsgeometry.buffer")
        self.assertEqual(mapped["chain_completeness"], "partial_exact")

    def test_builder_keeps_group_identity_and_fails_closed_on_collisions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            extraction = root / "readonly" / "QGIS"
            output = root / "writable" / "ordered"
            taxonomy_path = root / "taxonomy.json"
            facts_path = root / "facts.jsonl"
            taxonomy_path.write_text(
                json.dumps(
                    {
                        "profile": "fixture_114",
                        "code_to_token_id": {"L3_FIX": 94, "L3_GRID": 95},
                        "alias_to_code": {
                            "native:fixgeometries": "L3_FIX",
                            "native:creategrid": "L3_GRID",
                        },
                    }
                ),
                encoding="utf-8",
            )
            groups = ["group_a", "group_b"]
            for group in groups:
                directory = extraction / group
                directory.mkdir(parents=True)
                (directory / "script_1_ast.json").write_text(
                    json.dumps({"group": group}), encoding="utf-8"
                )
                (directory / "script_1_steps.csv").write_text(
                    "id,statement_index,api_source_type,normalized_api_name\n"
                    + (
                        "1,10,qgis_processing_algorithm,native:fixgeometries\n"
                        if group == "group_a"
                        else "1,10,qgis_processing_algorithm,native:creategrid\n"
                    ),
                    encoding="utf-8",
                )
                with (directory / "merged_nodes_process.csv").open(
                    "w", encoding="utf-8", newline=""
                ) as handle:
                    writer = csv.DictWriter(
                        handle,
                        fieldnames=[
                            "id",
                            "source_script",
                            "statement_index",
                            "api_source_type",
                            "normalized_api_name",
                        ],
                    )
                    writer.writeheader()
                    writer.writerow(
                        {
                            "id": "1",
                            "source_script": "script_1.py",
                            "statement_index": "10",
                            "api_source_type": "qgis_processing_algorithm",
                            "normalized_api_name": (
                                "native:fixgeometries"
                                if group == "group_a"
                                else "native:creategrid"
                            ),
                        }
                    )
            candidates = {
                group: {
                    "ast": [str(extraction / group / "script_1_ast.json")],
                    "steps": [str(extraction / group / "script_1_steps.csv")],
                }
                for group in groups
            }
            facts_path.write_text(
                json.dumps(
                    {
                        "facts_row_id": "facts:1",
                        "script_id": "script_1",
                        "source_script": "script_1.py",
                        "task_name": "Repair then grid",
                        "task_description": "Fixture",
                        "candidate_group_count": 2,
                        "collision_state": "requires_path_hash_resolution",
                        "artifact_candidates": candidates,
                    }
                )
                + "\n",
                encoding="utf-8",
            )

            summary = build_ordered_dataset(
                facts_candidates=facts_path,
                extraction_root=extraction,
                taxonomy_path=taxonomy_path,
                output_dir=output,
                allowed_write_roots=[root / "writable"],
            )
            rows = [
                json.loads(line)
                for line in (output / "ordered_evidence.jsonl").read_text(encoding="utf-8").splitlines()
            ]

        self.assertEqual(summary["records"], 2)
        self.assertEqual({row["extraction_group"] for row in rows}, {"group_a", "group_b"})
        self.assertTrue(all(row["collision_state"] == "unresolved_collision" for row in rows))
        self.assertTrue(all(row["evidence_tier"] == "T0" for row in rows))
        self.assertEqual({tuple(row["mapped_l3_chain"]) for row in rows}, {("L3_FIX",), ("L3_GRID",)})
        self.assertTrue(all(row["artifact_hashes"]["ast_sha256"] for row in rows))


if __name__ == "__main__":
    unittest.main()
