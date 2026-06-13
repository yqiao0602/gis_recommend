from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from gis_recommend.evaluation.qgis_chain_metrics import (
    score_qgis_chain,
    infer_modality,
    aggregate_scores,
    aggregate_by,
    score_chain_records,
)


# Minimal synthetic QGIS I/O metadata (keys = the set of REAL QGIS operators).
IO_TYPES = {
    "native:buffer": {"inputs": ["vector"], "outputs": ["vector"]},
    "native:clip": {"inputs": ["vector"], "outputs": ["vector"]},
    "native:rasterize": {"inputs": ["vector"], "outputs": ["raster"]},
    "gdal:cliprasterbymasklayer": {"inputs": ["raster"], "outputs": ["raster"]},
}


class OperatorValidityTests(unittest.TestCase):
    def test_operator_validity_flags_unknown_and_hallucinated_ops(self):
        """① operator validity: ops not in the known QGIS set (hallucinations,
        UNKNOWN placeholders) are flagged; rate = real / total."""
        chain = ["native:buffer", "native:nonexistent", "UNKNOWN[filter]"]
        r = score_qgis_chain(chain, io_types=IO_TYPES)
        self.assertAlmostEqual(r["operator_validity"], 1 / 3)
        self.assertEqual(set(r["invalid_operators"]), {"native:nonexistent", "UNKNOWN[filter]"})


class IoExecutabilityTests(unittest.TestCase):
    def test_io_executability_checks_adjacent_type_compatibility(self):
        """② adjacent pair compatible iff output types ∩ input types ≠ ∅."""
        # (buffer→clip) vec→vec OK; (clip→rasterize) vec→vec OK; (rasterize→clip) raster→vec BAD
        chain = ["native:buffer", "native:clip", "native:rasterize", "native:clip"]
        r = score_qgis_chain(chain, io_types=IO_TYPES)
        self.assertAlmostEqual(r["io_executability"], 2 / 3)
        self.assertFalse(r["executable"])

    def test_executable_true_when_all_valid_and_compatible(self):
        chain = ["native:buffer", "native:clip"]
        r = score_qgis_chain(chain, io_types=IO_TYPES)
        self.assertEqual(r["operator_validity"], 1.0)
        self.assertAlmostEqual(r["io_executability"], 1.0)
        self.assertTrue(r["executable"])


class OperatorSetF1Tests(unittest.TestCase):
    def test_set_f1_is_order_invariant(self):
        """③ reordered chain with same operator set scores F1=1.0 (multi-solution: reorder免疫)."""
        ref = ["native:buffer", "native:clip"]
        r = score_qgis_chain(["native:clip", "native:buffer"], io_types=IO_TYPES, reference=ref)
        self.assertEqual(r["operator_set_f1"], 1.0)

    def test_set_f1_partial_overlap(self):
        ref = ["native:buffer", "native:clip"]
        r = score_qgis_chain(["native:buffer", "native:rasterize"], io_types=IO_TYPES, reference=ref)
        self.assertAlmostEqual(r["operator_set_f1"], 0.5)

    def test_set_f1_none_without_reference(self):
        r = score_qgis_chain(["native:buffer"], io_types=IO_TYPES)
        self.assertIsNone(r["operator_set_f1"])


class ModalityTests(unittest.TestCase):
    def test_infer_modality_from_io_types(self):
        self.assertEqual(infer_modality(["native:buffer", "native:clip"], IO_TYPES), "vector")
        self.assertEqual(infer_modality(["gdal:cliprasterbymasklayer"], IO_TYPES), "raster")
        # rasterize: vector in -> raster out => touches both
        self.assertEqual(infer_modality(["native:rasterize"], IO_TYPES), "mixed")
        self.assertEqual(infer_modality(["foo:bar"], IO_TYPES), "unknown")


class AggregateTests(unittest.TestCase):
    def test_aggregate_overall_and_by_modality(self):
        records = [
            {"modality": "vector", "operator_validity": 1.0, "io_executability": 1.0, "executable": True, "operator_set_f1": 0.8},
            {"modality": "vector", "operator_validity": 0.5, "io_executability": 0.5, "executable": False, "operator_set_f1": 0.4},
            {"modality": "raster", "operator_validity": 1.0, "io_executability": 1.0, "executable": True, "operator_set_f1": 1.0},
        ]
        agg = aggregate_scores(records)
        self.assertEqual(agg["overall"]["n"], 3)
        self.assertEqual(agg["by_modality"]["vector"]["n"], 2)
        self.assertAlmostEqual(agg["by_modality"]["vector"]["operator_validity"], 0.75)
        self.assertAlmostEqual(agg["by_modality"]["vector"]["executable_rate"], 0.5)
        self.assertAlmostEqual(agg["by_modality"]["raster"]["operator_set_f1"], 1.0)


class AggregateByKeyTests(unittest.TestCase):
    def test_aggregate_by_groups_by_arbitrary_key(self):
        """Generic grouped aggregation: same agg shape, grouped by any record key
        (here human grade A/B) — this is what powers the by-grade view that proves
        ①② don't track correctness."""
        records = [
            {"grade": "A", "operator_validity": 1.0, "io_executability": 1.0, "executable": True, "operator_set_f1": None},
            {"grade": "A", "operator_validity": 0.8, "io_executability": 1.0, "executable": False, "operator_set_f1": None},
            {"grade": "B", "operator_validity": 1.0, "io_executability": 0.5, "executable": False, "operator_set_f1": None},
        ]
        agg = aggregate_by(records, "grade")
        self.assertEqual(agg["overall"]["n"], 3)
        self.assertEqual(agg["groups"]["A"]["n"], 2)
        self.assertEqual(agg["groups"]["B"]["n"], 1)
        self.assertAlmostEqual(agg["groups"]["A"]["operator_validity"], 0.9)
        self.assertAlmostEqual(agg["groups"]["A"]["executable_rate"], 0.5)
        self.assertAlmostEqual(agg["groups"]["B"]["io_executability"], 0.5)


class BatchRecordsTests(unittest.TestCase):
    def test_score_chain_records_attaches_modality_and_metrics(self):
        """Batch driver: ties score_qgis_chain + infer_modality per item, ready for aggregate_scores."""
        items = [
            {"task_id": "t1", "predicted_chain": ["native:buffer", "native:clip"]},
            {"task_id": "t2", "predicted_chain": ["gdal:cliprasterbymasklayer"],
             "reference": ["gdal:cliprasterbymasklayer"]},
        ]
        recs = score_chain_records(items, io_types=IO_TYPES)
        self.assertEqual(recs[0]["task_id"], "t1")
        self.assertEqual(recs[0]["modality"], "vector")
        self.assertEqual(recs[1]["modality"], "raster")
        self.assertEqual(recs[1]["operator_set_f1"], 1.0)

        agg = aggregate_scores(recs)
        self.assertEqual(agg["overall"]["n"], 2)
        self.assertIn("vector", agg["by_modality"])
        self.assertIn("raster", agg["by_modality"])


if __name__ == "__main__":
    unittest.main()
