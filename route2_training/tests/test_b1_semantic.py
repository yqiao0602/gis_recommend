"""B1 semantic-target purity tests — GEE chain must never enter the loss."""

import json
import unittest
from pathlib import Path

from route2_training.data.gee_stage_datasets import GeeSemanticDataset


class FakeTokenizer:
    eos_token_id = 2
    bos_token_id = 1
    pad_token_id = 0

    def encode(self, text, add_special_tokens=False):
        return [len(text) % 1000 + 3]

    @property
    def eos_token(self):
        return "</s>"


class TestB1SemanticTarget(unittest.TestCase):
    def _tmp_rows(self, tmpdir: Path):
        rows = [
            {"script": "s1", "split": "train",
             "instruction": "Task: X\nDo X.",
             "semantic_chain_rle": "RASTER_LOAD -> TEMPORAL_FILTER",
             "semantic_chain_raw": "RASTER_LOAD -> TEMPORAL_FILTER",
             "gee_canonical_chain": "ee.ImageCollection -> ee.ImageCollection.filterDate",
             "original_semantic_length": 2, "final_semantic_length": 2,
             "run_cap_applied": False, "author_proxy": "alice"},
            {"script": "s2", "split": "val",
             "instruction": "Task: Y\nDo Y.",
             "semantic_chain_rle": "CLASSIFICATION",
             "semantic_chain_raw": "CLASSIFICATION -> CLASSIFICATION",
             "gee_canonical_chain": "ee.Classifier.smileCart.train",
             "original_semantic_length": 2, "final_semantic_length": 1,
             "run_cap_applied": False, "author_proxy": ""},
        ]
        p = tmpdir / "b1.jsonl"
        p.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                     encoding="utf-8")
        return p, rows

    def test_target_is_semantic_rle_only(self, *_):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            p, rows = self._tmp_rows(Path(td))
            ds = GeeSemanticDataset(p, split="train")
            prompt, target = ds.prompt_target(0)
            self.assertEqual(target, rows[0]["semantic_chain_rle"])
            self.assertIn("ee.", rows[0]["gee_canonical_chain"])
            self.assertNotIn("ee.", target)      # purity: no GEE API in target

    def test_split_filter(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            p, _ = self._tmp_rows(Path(td))
            ds = GeeSemanticDataset(p, split="train")
            self.assertEqual(len(ds), 1)
            self.assertEqual(ds.rows[0]["script"], "s1")
            dsv = GeeSemanticDataset(p, split="val")
            self.assertEqual(len(dsv), 1)

    def test_audit_fields_present_but_separate(self):
        import tempfile
        with tempfile.TemporaryDirectory() as td:
            p, _ = self._tmp_rows(Path(td))
            ds = GeeSemanticDataset(p, split=None)
            a = ds.audit_row(0)
            self.assertIn("gee_canonical_chain", a)   # audit keeps evidence
            self.assertEqual(a["author_proxy"], "alice")


if __name__ == "__main__":
    unittest.main()
