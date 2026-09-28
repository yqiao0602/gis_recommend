from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_qgis_v4_128_admission import build_admission


class BuildQgisV4128AdmissionTest(unittest.TestCase):
    def test_binds_passing_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            dataset = root / "dataset.jsonl"
            dataset.write_text(
                json.dumps(
                    {
                        "sample_id": "a",
                        "validation_eligible": False,
                        "test_eligible": False,
                        "production_merge": "not_granted",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            evidence = root / "evidence.json"
            evidence.write_text("{}\n", encoding="utf-8")
            path = str(evidence)
            admission = build_admission(
                dataset_path=dataset,
                text_summary={
                    "input_rows": 1,
                    "eligible_rows": 1,
                    "deferred_rows": 0,
                    "text_truncation_gate": "passed_for_eligible_rows",
                    "bert_model": "bert-base-uncased",
                    "max_text_length": 128,
                    "eligible_max_text_tokens": 12,
                    "_path": path,
                },
                smoke={
                    "rows_loaded": 1,
                    "rows_seen_by_loader": 1,
                    "input_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(),
                    "loss_finite": True,
                    "gradient_finite": True,
                    "checkpoint_written": False,
                    "training_run": False,
                    "batches": 1,
                    "_path": path,
                },
                increment_summary={
                    "input_description_rows": 55,
                    "dedup": {
                        "description_fidelity_passed": 55,
                        "unique_source_authorities": 54,
                        "suppressed_exact_training_pairs": 52,
                    },
                    "export": {"train_only_rows": 3, "cross_pool_suppressed": 0},
                    "_path": path,
                },
                taxonomy_summary={
                    "taxonomy_admission": "granted",
                    "content_token_count": 126,
                    "normalized_source_body_support": 54,
                    "_path": path,
                },
            )

        self.assertEqual(admission["dataset"]["rows"], 1)
        self.assertEqual(admission["point_geometry_increment"]["train_only_rows"], 3)


if __name__ == "__main__":
    unittest.main()
