import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_qgis_stable101_source_review_pack import build_source_review_pack


def _write_jsonl(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )


class Stable101SourceReviewPackTest(unittest.TestCase):
    def _write_source(self, qgis_root: Path, source_dir: str, file_name: str, text: str) -> None:
        target = qgis_root / source_dir / "downloaded_scripts" / file_name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")

    def test_builds_source_backed_rows_and_cluster_refs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            qgis_root = root / "qgis"
            out_dir = root / "out"

            script_1 = '''"""Buffer clip workflow."""
def run_model():
    buffered = processing.run("native:buffer", {"INPUT": roads, "OUTPUT": "memory:"})["OUTPUT"]
    return processing.run("native:clip", {"INPUT": buffered, "OVERLAY": mask, "OUTPUT": "memory:"})["OUTPUT"]
'''
            script_2 = '''"""Second equivalent workflow."""
def run_model():
    first = processing.run("native:buffer", {"INPUT": roads, "OUTPUT": "memory:"})["OUTPUT"]
    return processing.run("native:clip", {"INPUT": first, "OVERLAY": mask, "OUTPUT": "memory:"})["OUTPUT"]
'''
            self._write_source(
                qgis_root,
                "QGIS_standard_multi_operator_workflows_v2",
                "script_0001.py",
                script_1,
            )
            self._write_source(
                qgis_root,
                "QGIS_standard_multi_operator_workflows_v2",
                "script_0002.py",
                script_2,
            )

            chain_dataset = root / "qgis_chain_dataset.jsonl"
            _write_jsonl(
                chain_dataset,
                [
                    {
                        "task_text": "Buffer clip workflow. run model",
                        "qgis_ops": ["native:buffer", "native:clip"],
                        "operator_names": ["Buffer", "Clip"],
                        "source": "standard_v2",
                        "quality": {"length": 2, "is_pure_vector": True},
                        "training_targets": ["qgis_head"],
                    },
                    {
                        "task_text": "Second equivalent workflow. run model",
                        "qgis_ops": ["native:buffer", "native:clip"],
                        "operator_names": ["Buffer", "Clip"],
                        "source": "standard_v2",
                        "quality": {"length": 2, "is_pure_vector": True},
                        "training_targets": ["qgis_head"],
                    },
                ],
            )
            candidate_path = root / "candidate.jsonl"
            _write_jsonl(
                candidate_path,
                [
                    {
                        "review_index": 1,
                        "selection_stratum": "single_reprojectlayer_representative",
                        "representative_record_index": 1,
                        "representative_record_sha256": "a" * 64,
                        "chain_key": "native:buffer -> native:clip",
                        "chain_frequency": 2,
                        "unique_record_sha_count": 2,
                        "qgis_ops": ["native:buffer", "native:clip"],
                        "proposed_l3_sequence": ["L3_A", "L3_B"],
                        "proposal_ops_present": ["native:reprojectlayer"],
                        "task_text": "Buffer clip workflow. run model",
                        "task_seed_text": "Buffer clip workflow. run model",
                        "task_text_quality": "usable_seed_text",
                        "taxonomy_admission": "granted_for_four_stable101_mappings",
                        "training_admission": "not_granted",
                    }
                ],
            )
            newly_complete_path = root / "newly_complete.jsonl"
            _write_jsonl(
                newly_complete_path,
                [
                    {
                        "record_index": 1,
                        "record_sha256": "a" * 64,
                        "chain_key": "native:buffer -> native:clip",
                        "qgis_ops": ["native:buffer", "native:clip"],
                        "source_repo": "repo/one",
                        "task_seed_text": "Buffer clip workflow",
                    },
                    {
                        "record_index": 2,
                        "record_sha256": "b" * 64,
                        "chain_key": "native:buffer -> native:clip",
                        "qgis_ops": ["native:buffer", "native:clip"],
                        "source_repo": "repo/two",
                        "task_seed_text": "Second equivalent workflow",
                    },
                ],
            )

            catalog = {
                "native:buffer": {"name": "Buffer", "data_type": "vector", "alg_id": "native:buffer"},
                "native:clip": {"name": "Clip", "data_type": "vector", "alg_id": "native:clip"},
            }
            summary = build_source_review_pack(
                candidates_path=candidate_path,
                newly_complete_records_path=newly_complete_path,
                chain_dataset_path=chain_dataset,
                output_dir=out_dir,
                qgis_root=qgis_root,
                catalog=catalog,
                l3_lookup={},
                alg_id_xwalk={},
            )

            self.assertEqual(summary["review_row_count"], 1)
            self.assertEqual(summary["joined_source_count"], 1)
            self.assertEqual(summary["source_snippet_contains_all_ops_count"], 1)

            review_rows = [
                json.loads(line)
                for line in (out_dir / "stable101_source_review_50_v1.jsonl").read_text(
                    encoding="utf-8"
                ).splitlines()
                if line.strip()
            ]
            row = review_rows[0]
            self.assertEqual(row["source_root_id"], "standard_v2")
            self.assertEqual(row["relative_path"], "script_0001.py")
            self.assertEqual(len(row["source_sha256"]), 64)
            self.assertIn('processing.run("native:buffer"', row["source_snippet"])
            self.assertIn('processing.run("native:clip"', row["source_snippet"])
            self.assertEqual(row["cluster_member_count"], 2)
            self.assertEqual(row["cluster_member_record_indices"], [1, 2])
            self.assertEqual(row["cluster_source_refs_sample"][1]["relative_path"], "script_0002.py")
            self.assertNotIn("source_snippet", row["cluster_source_refs_sample"][1])
            self.assertEqual(row["dependency_status"], "not_recovered_source_join_only")
            self.assertEqual(row["human_training_candidate_ready"], "")

    def test_fails_closed_when_replayed_chain_dataset_mismatches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            qgis_root = root / "qgis"
            out_dir = root / "out"
            self._write_source(
                qgis_root,
                "QGIS_standard_multi_operator_workflows_v2",
                "script_0001.py",
                'def run_model():\n    return processing.run("native:buffer", {"INPUT": roads})\n',
            )
            chain_dataset = root / "qgis_chain_dataset.jsonl"
            _write_jsonl(
                chain_dataset,
                [
                    {
                        "task_text": "run model",
                        "qgis_ops": ["native:clip"],
                        "source": "standard_v2",
                        "quality": {},
                    }
                ],
            )
            candidate_path = root / "candidate.jsonl"
            newly_complete_path = root / "newly_complete.jsonl"
            _write_jsonl(candidate_path, [])
            _write_jsonl(newly_complete_path, [])

            catalog = {
                "native:buffer": {
                    "name": "Buffer",
                    "data_type": "vector",
                    "alg_id": "native:buffer",
                }
            }
            with self.assertRaisesRegex(ValueError, "replayed chain dataset mismatch"):
                build_source_review_pack(
                    candidates_path=candidate_path,
                    newly_complete_records_path=newly_complete_path,
                    chain_dataset_path=chain_dataset,
                    output_dir=out_dir,
                    qgis_root=qgis_root,
                    catalog=catalog,
                    l3_lookup={},
                    alg_id_xwalk={},
                    min_length=1,
                )


if __name__ == "__main__":
    unittest.main()
