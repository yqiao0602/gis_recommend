import tempfile
import unittest
from pathlib import Path

from gis_recommend.data.qgis_pilot import (
    EvidenceTier,
    assert_write_allowed,
    build_authority_diff,
    build_ordered_evidence,
    build_sampling_proposal,
    resolve_provenance_clusters,
)
from scripts.build_qgis_pilot_phase0 import build_report


class QgisPilotTests(unittest.TestCase):
    def test_phase0_report_surfaces_missing_run_contract_authority(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "outputs_v2").mkdir()
            report = build_report(root)

        self.assertEqual(report["status"], "authority_decision_required")
        self.assertFalse(report["default_changed"])
        run_contract = report["surfaces"]["step8_v4_6_run_contract"]
        self.assertFalse(run_contract["transformer_checkpoint"]["exists"])
        self.assertIn("quality_gate_v4_6_entrypoints", report["surfaces"])
        self.assertIn("phase11_vector_sft_94", report["surfaces"])
        self.assertIn("best_gen_composite_model.pth", report["surfaces"]["phase11_vector_sft_94"]["transformer_checkpoint"]["path"])

    def test_authority_diff_keeps_each_divergent_role_explicit(self):
        profile = {
            "id_mappings": "/repo/outputs_v2/id_mappings_v2.json",
            "workflow": "/repo/outputs_v2/pipeline/vec11277/workflows.json",
            "set_predictor": "/repo/outputs_v2/set_predictor_vec11277/best_model.pth",
        }
        mainline = {
            "id_mappings": "/repo/outputs_v2/id_mappings_v2.json",
            "workflow": "/repo/outputs_v2/pipeline/step8/workflows.json",
            "set_predictor": "/repo/outputs_v2/set_predictor_v3/best_model.pth",
        }

        rows = build_authority_diff(profile, mainline)

        self.assertEqual([row["role"] for row in rows], sorted(profile))
        self.assertFalse(next(row for row in rows if row["role"] == "workflow")["matches"])
        self.assertTrue(next(row for row in rows if row["role"] == "id_mappings")["matches"])

    def test_write_allowlist_rejects_source_root_and_path_escape(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            writable = root / "home" / "qy"
            readonly = root / "home" / "yll"
            writable.mkdir(parents=True)
            readonly.mkdir(parents=True)

            self.assertEqual(
                assert_write_allowed(writable / "pilot" / "manifest.json", [writable]),
                (writable / "pilot" / "manifest.json").resolve(),
            )
            with self.assertRaises(ValueError):
                assert_write_allowed(readonly / "forbidden.json", [writable])
            with self.assertRaises(ValueError):
                assert_write_allowed(writable / ".." / "yll" / "escape.json", [writable])

    def test_provenance_collapses_identical_mirrors_and_rejects_collision(self):
        facts = [
            {"facts_row_id": "f1", "source_script": "script_1.py", "task_text": "Buffer roads"},
            {"facts_row_id": "f2", "source_script": "script_2.py", "task_text": "Clip roads"},
        ]
        artifacts = [
            {
                "source_path": "/a/script_1.py",
                "source_script": "script_1.py",
                "raw_sha256": "a" * 64,
                "normalized_steps_sha256": "n" * 64,
            },
            {
                "source_path": "/mirror/script_1.py",
                "source_script": "script_1.py",
                "raw_sha256": "a" * 64,
                "normalized_steps_sha256": "n" * 64,
            },
            {
                "source_path": "/a/script_2.py",
                "source_script": "script_2.py",
                "raw_sha256": "b" * 64,
                "normalized_steps_sha256": "x" * 64,
            },
            {
                "source_path": "/b/script_2.py",
                "source_script": "script_2.py",
                "raw_sha256": "c" * 64,
                "normalized_steps_sha256": "y" * 64,
            },
        ]

        rows = resolve_provenance_clusters(facts, artifacts)

        f1 = next(row for row in rows if row["facts_row_id"] == "f1")
        f2 = next(row for row in rows if row["facts_row_id"] == "f2")
        self.assertEqual(f1["collision_state"], "equivalent_mirrors")
        self.assertEqual(len(f1["source_aliases"]), 2)
        self.assertEqual(f1["evidence_tier"], EvidenceTier.T2.value)
        self.assertEqual(f2["collision_state"], "unresolved_collision")
        self.assertEqual(f2["evidence_tier"], EvidenceTier.T0.value)
        self.assertIsNone(f2["canonical_source"])

    def test_ordered_evidence_preserves_order_channels_and_unresolved_fragments(self):
        rows = [
            {
                "id": "s3",
                "statement_index": "20",
                "api_source_type": "qgis_api",
                "normalized_api_name": "QgsGeometry.buffer",
                "scope": "run",
                "nesting_depth": "1",
            },
            {
                "id": "s1",
                "statement_index": "10",
                "api_source_type": "qgis_processing_algorithm",
                "normalized_api_name": "native:fixgeometries",
                "scope": "run",
                "nesting_depth": "0",
            },
            {
                "id": "s2",
                "statement_index": "15",
                "api_source_type": "custom_processing_algorithm",
                "normalized_api_name": "acme:cleanup",
                "scope": "run",
                "nesting_depth": "0",
            },
            {
                "id": "s4",
                "statement_index": "bad",
                "api_source_type": "unknown",
                "normalized_api_name": "mystery.call",
            },
        ]

        evidence = build_ordered_evidence(rows)

        self.assertEqual(
            [step["step_id"] for step in evidence["ordered_steps"]],
            ["s1", "s2", "s3", "s4"],
        )
        self.assertEqual(evidence["processing_algorithms"][0]["operation"], "native:fixgeometries")
        self.assertEqual(evidence["custom_algorithms"][0]["operation"], "acme:cleanup")
        self.assertEqual(evidence["direct_api"][0]["operation"], "QgsGeometry.buffer")
        self.assertEqual(evidence["unresolved_fragments"][0]["operation"], "mystery.call")
        self.assertEqual(evidence["ordering_confidence"], "degraded")

    def test_sampling_is_reproducible_disjoint_and_never_backfills_reference_with_t3(self):
        records = []
        for index in range(18):
            tier = "T4" if index < 8 else ("T3" if index < 14 else "T2")
            records.append(
                {
                    "provenance_cluster_id": f"p{index:02d}",
                    "evidence_tier": tier,
                    "evidence_source": ["processing_run", "direct_api", "custom_algorithm"][index % 3],
                    "modality": ["vector", "raster", "mixed"][index % 3],
                    "operation_family": ["overlay", "crs", "geometry_repair"][index % 3],
                    "collision_state": "resolved",
                }
            )
        records.append(
            {
                "provenance_cluster_id": "collision",
                "evidence_tier": "T0",
                "evidence_source": "direct_api",
                "modality": "vector",
                "operation_family": "overlay",
                "collision_state": "unresolved_collision",
            }
        )

        first = build_sampling_proposal(records, reference_size=10, diagnostic_size=6, seed=42)
        second = build_sampling_proposal(records, reference_size=10, diagnostic_size=6, seed=42)

        self.assertEqual(first, second)
        reference = first["estimation_reference_subset"]
        diagnostic = first["coverage_diagnostic_subset"]
        self.assertEqual(len(reference), 8)
        self.assertEqual(first["shortfalls"]["estimation_reference_subset"], 2)
        self.assertTrue(all(row["evidence_tier"] == "T4" for row in reference))
        self.assertFalse({row["provenance_cluster_id"] for row in reference} &
                         {row["provenance_cluster_id"] for row in diagnostic})
        self.assertEqual(first["collision_diagnostic_subset"][0]["provenance_cluster_id"], "collision")
        self.assertEqual(first["metric_policy"], "subsets_must_not_be_merged")


if __name__ == "__main__":
    unittest.main()
