import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_qgis_stable101_candidate_pool import build_candidate_pool


class Stable101CandidatePoolTest(unittest.TestCase):
    def _write_jsonl(self, path: Path, rows: list[dict]) -> None:
        path.write_text(
            "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
            encoding="utf-8",
        )

    def _write_json(self, path: Path, value: dict) -> None:
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    def test_candidate_pool_filters_newly_complete_and_deduplicates_chains(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            impact_records = root / "impact.jsonl"
            chain_dataset = root / "chains.jsonl"
            impact_summary = root / "impact_summary.json"
            out_dir = root / "out"

            self._write_jsonl(
                chain_dataset,
                [
                    {
                        "task_text": "Buffer roads after CRS conversion Source repo: repo/a",
                        "qgis_ops": ["native:reprojectlayer", "native:buffer"],
                        "source": "workflow",
                        "quality": {"is_pure_vector": True},
                        "training_targets": ["qgis_head"],
                    },
                    {
                        "task_text": "initAlgorithm Source repo: repo/b",
                        "qgis_ops": ["native:reprojectlayer", "native:buffer"],
                        "source": "workflow",
                        "quality": {"is_pure_vector": True},
                        "training_targets": ["qgis_head"],
                    },
                    {
                        "task_text": "Rasterize buffered roads Source repo: repo/c",
                        "qgis_ops": ["native:buffer", "gdal:rasterize"],
                        "source": "workflow_A",
                        "quality": {"is_pure_vector": False, "is_pure_raster": False},
                        "training_targets": ["qgis_head"],
                    },
                    {
                        "task_text": "Still blocked Source repo: repo/d",
                        "qgis_ops": ["native:reprojectlayer", "native:package"],
                        "source": "workflow",
                        "quality": {"is_pure_vector": True},
                        "training_targets": ["qgis_head"],
                    },
                ],
            )
            self._write_jsonl(
                impact_records,
                [
                    {
                        "impact_stage": "newly_complete_stablen_conservative",
                        "proposal_ops_present": ["native:reprojectlayer"],
                        "proposed_l3_sequence": ["L3_01_10_01", "L3_02_01_01"],
                        "qgis_ops": ["native:reprojectlayer", "native:buffer"],
                        "record_index": 1,
                        "record_sha256": "sha1",
                        "stable98_unresolved_ops": ["native:reprojectlayer"],
                        "stablen_unresolved_ops": [],
                        "task_text": "Buffer roads after CRS conversion Source repo: repo/a",
                    },
                    {
                        "impact_stage": "newly_complete_stablen_conservative",
                        "proposal_ops_present": ["native:reprojectlayer"],
                        "proposed_l3_sequence": ["L3_01_10_01", "L3_02_01_01"],
                        "qgis_ops": ["native:reprojectlayer", "native:buffer"],
                        "record_index": 2,
                        "record_sha256": "sha2",
                        "stable98_unresolved_ops": ["native:reprojectlayer"],
                        "stablen_unresolved_ops": [],
                        "task_text": "initAlgorithm Source repo: repo/b",
                    },
                    {
                        "impact_stage": "newly_complete_stablen_conservative",
                        "proposal_ops_present": ["gdal:rasterize"],
                        "proposed_l3_sequence": ["L3_02_01_01", "L3_01_09_03"],
                        "qgis_ops": ["native:buffer", "gdal:rasterize"],
                        "record_index": 3,
                        "record_sha256": "sha3",
                        "stable98_unresolved_ops": ["gdal:rasterize"],
                        "stablen_unresolved_ops": [],
                        "task_text": "Rasterize buffered roads Source repo: repo/c",
                    },
                    {
                        "impact_stage": "still_incomplete_after_stablen",
                        "proposal_ops_present": ["native:reprojectlayer"],
                        "proposed_l3_sequence": [],
                        "qgis_ops": ["native:reprojectlayer", "native:package"],
                        "record_index": 4,
                        "record_sha256": "sha4",
                        "stable98_unresolved_ops": ["native:reprojectlayer", "native:package"],
                        "stablen_unresolved_ops": ["native:package"],
                        "task_text": "Still blocked Source repo: repo/d",
                    },
                ],
            )
            self._write_json(
                impact_summary,
                {
                    "stable98_draft": {"complete_records": 1, "complete_unique_chains": 1},
                    "stablen_conservative_draft": {"complete_records": 3, "complete_unique_chains": 2},
                    "increment_vs_stable98": {"records": 2, "unique_chains": 1},
                },
            )

            summary = build_candidate_pool(
                impact_records_path=impact_records,
                chain_dataset_path=chain_dataset,
                impact_summary_path=impact_summary,
                output_dir=out_dir,
                batch_size=2,
            )

            self.assertEqual(summary["newly_complete_record_count"], 3)
            self.assertEqual(summary["newly_complete_unique_chain_count"], 2)
            self.assertEqual(summary["next_review_batch_count"], 2)
            self.assertEqual(summary["training_admission"], "not_granted")
            self.assertTrue(summary["source_join_required_for_full_manual_review_csv"])

            pool_rows = [
                json.loads(line)
                for line in (out_dir / "stable101_unique_chain_pool_v1.jsonl").read_text(
                    encoding="utf-8"
                ).splitlines()
                if line.strip()
            ]
            by_chain = {row["chain_key"]: row for row in pool_rows}
            self.assertEqual(by_chain["native:reprojectlayer -> native:buffer"]["task_text_quality"], "usable_seed_text")
            self.assertEqual(by_chain["native:reprojectlayer -> native:buffer"]["chain_frequency"], 2)
            self.assertTrue((out_dir / "stable101_next_review_candidates_50_v1.csv").is_file())


if __name__ == "__main__":
    unittest.main()
