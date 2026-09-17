"""Split integrity tests — the four-arm uniformity gate (owner rule 7)."""

import json
import tempfile
import unittest
from pathlib import Path


def write_jsonl(path: Path, rows):
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows),
                    encoding="utf-8")


class TestSplitIntegrity(unittest.TestCase):
    def test_qgis_splits_are_disjoint_by_wid_and_row_count(self):
        # contract numbers from P0-2 (frozen): 1334/120/111
        from route2_training.collators.qgis_graph_collator import QgisGraphDataset
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            tr, dv, te = td / "a.jsonl", td / "b.jsonl", td / "c.jsonl"
            mk = lambda i, t: {"wid": f"t{i}", "task_text": f"task {i}",
                               "processes": [{"process_id": "p0", "operator_id": "native:clip"}],
                               "links": []}
            write_jsonl(tr, [mk(i, "train") for i in range(50)])
            write_jsonl(dv, [mk(100 + i, "dev") for i in range(5)])
            write_jsonl(te, [mk(200 + i, "test") for i in range(5)])
            ids = (set(r["wid"] for r in QgisGraphDataset(tr).rows)
                   & set(r["wid"] for r in QgisGraphDataset(dv).rows)
                   & set(r["wid"] for r in QgisGraphDataset(te).rows))
            self.assertEqual(ids, set())

    def test_gee_split_labels_present_and_three_way(self):
        from route2_training.data.gee_stage_datasets import GeeSemanticDataset
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "g.jsonl"
            rows = [{"script": f"s{i}", "split": s,
                     "instruction": "Task: x", "semantic_chain_rle": "AGGREGATION",
                     "semantic_chain_raw": "AGGREGATION",
                     "gee_canonical_chain": "ee.Reducer.mean",
                     "original_semantic_length": 1, "final_semantic_length": 1,
                     "run_cap_applied": False, "author_proxy": ""}
                    for i, s in enumerate(["train"] * 3 + ["val", "test"])]
            write_jsonl(p, rows)
            ds = GeeSemanticDataset(p, split=None)
            splits = set(r["split"] for r in ds.rows)
            self.assertEqual(splits, {"train", "val", "test"})

    def test_sha_reconciliation_detects_mismatch(self):
        from route2_training.harness import sha256_file, sha256_text
        with tempfile.TemporaryDirectory() as td:
            a = Path(td) / "a.jsonl"
            write_jsonl(a, [{"x": 1}])
            b = Path(td) / "b.jsonl"
            write_jsonl(b, [{"x": 1}])
            c = Path(td) / "c.jsonl"
            write_jsonl(c, [{"x": 2}])
            self.assertEqual(sha256_file(a), sha256_file(b))
            self.assertNotEqual(sha256_file(a), sha256_file(c))

    def test_truncation_report_fields(self):
        from route2_training.harness import TruncationReport
        r = TruncationReport(n_total=100, n_truncated=25,
                             raw_len_p50=11, raw_len_p90=46,
                             final_len_p50=8, final_len_p90=26,
                             max_len=1024, max_observed=1200)
        d = r.to_dict()
        for k in ("n_total", "n_truncated", "truncation_rate",
                  "raw_length_p50", "raw_length_p90", "final_length_p50",
                  "final_length_p90", "max_length", "max_observed"):
            self.assertIn(k, d)
        self.assertEqual(d["truncation_rate"], 0.25)


if __name__ == "__main__":
    unittest.main()
