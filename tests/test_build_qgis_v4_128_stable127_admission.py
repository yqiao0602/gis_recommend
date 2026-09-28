from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.build_qgis_v4_128_stable127_admission import build_admission


class BuildQgisV4128Stable127AdmissionTest(unittest.TestCase):
    def test_binds_all_required_gates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            dataset = root / "dataset.jsonl"
            dataset.write_text(json.dumps({"sample_id": "a", "validation_eligible": False, "test_eligible": False, "production_merge": "not_granted"}) + "\n", encoding="utf-8")
            paths = {name: root / f"{name}.json" for name in ("text", "smoke", "increment", "taxonomy")}
            paths["text"].write_text(json.dumps({"input_rows": 1, "eligible_rows": 1, "deferred_rows": 0, "text_truncation_gate": "passed_for_eligible_rows", "max_text_length": 128, "eligible_max_text_tokens": 12, "bert_model": "bert-base-uncased"}), encoding="utf-8")
            paths["smoke"].write_text(json.dumps({"rows_loaded": 1, "rows_seen_by_loader": 1, "input_sha256": hashlib.sha256(dataset.read_bytes()).hexdigest(), "loss_finite": True, "gradient_finite": True, "checkpoint_written": False, "training_run": False, "batches": 1}), encoding="utf-8")
            paths["increment"].write_text(json.dumps({"input_candidate_rows": 54, "dedup": {"description_fidelity_passed": 54, "unique_source_authorities": 34, "suppressed_exact_training_pairs": 51}, "export": {"train_only_rows": 3, "cross_pool_suppressed": 0}}), encoding="utf-8")
            paths["taxonomy"].write_text(json.dumps({"taxonomy_admission": "granted", "content_token_count": 127, "normalized_source_body_support": 34}), encoding="utf-8")
            def loaded(name: str) -> dict:
                value = json.loads(paths[name].read_text(encoding="utf-8"))
                value["_path"] = str(paths[name])
                return value

            result = build_admission(dataset_path=dataset, text_summary=loaded("text"), smoke=loaded("smoke"), increment_summary=loaded("increment"), taxonomy_summary=loaded("taxonomy"))

            self.assertEqual(result["dataset"]["rows"], 1)
            self.assertEqual(result["polyline_geometry_increment"]["train_only_rows"], 3)
            self.assertEqual(result["stable127_taxonomy"]["content_token_count"], 127)


if __name__ == "__main__":
    unittest.main()
