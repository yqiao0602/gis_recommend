"""Tests for compute_executable_ratio.

Covers:
  - Level 1 (local io_types, strict) adjacency checks
  - Level 2 (Neo4j KG validator, strict) via mock validator
  - Dual denominators: overall (/total) vs conditional (/counted)
  - Back-fill contract: reads selected_qgis_chain OR qgis_chain
  - Per-task-type breakdown
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from gis_recommend.evaluation.diagnostics import (
    _chain_executable_level1,
    _chain_executable_level2,
    compute_executable_ratio,
)


# ── Fixtures ─────────────────────────────────────────────────────

IO_TYPES = {
    "Slope":          {"inputs": ["raster"], "outputs": ["raster"]},
    "Hillshade":      {"inputs": ["raster"], "outputs": ["raster"]},
    "Buffer vectors": {"inputs": ["vector"], "outputs": ["vector"]},
    "Clip":           {"inputs": ["vector"], "outputs": ["vector"]},
    "Rasterize":      {"inputs": ["vector"], "outputs": ["raster"]},
    "MysteryOp":      {"inputs": [], "outputs": []},
}


# ── Level 1 unit tests ──────────────────────────────────────────

class Level1Tests(unittest.TestCase):
    def test_all_raster_chain_passes(self):
        ok, compat, total = _chain_executable_level1(
            ["Slope", "Hillshade"], IO_TYPES
        )
        self.assertTrue(ok)
        self.assertEqual(compat, 1)
        self.assertEqual(total, 1)

    def test_type_break_in_middle_fails(self):
        ok, _, _ = _chain_executable_level1(
            ["Slope", "Hillshade", "Buffer vectors"], IO_TYPES
        )
        self.assertFalse(ok)

    def test_bridging_operator_rescues_chain(self):
        ok, _, _ = _chain_executable_level1(
            ["Buffer vectors", "Rasterize", "Slope"], IO_TYPES
        )
        self.assertTrue(ok)

    def test_unknown_placeholder_disqualifies(self):
        ok, _, _ = _chain_executable_level1(
            ["Slope", "UNKNOWN[generic]", "Hillshade"], IO_TYPES
        )
        self.assertFalse(ok)

    def test_missing_metadata_fails_strictly(self):
        ok, _, _ = _chain_executable_level1(
            ["Slope", "MysteryOp", "Hillshade"], IO_TYPES
        )
        self.assertFalse(ok)

    def test_empty_chain(self):
        ok, _, _ = _chain_executable_level1([], IO_TYPES)
        self.assertFalse(ok)

    def test_single_known_operator(self):
        ok, _, _ = _chain_executable_level1(["Slope"], IO_TYPES)
        self.assertTrue(ok)

    def test_single_unknown_operator(self):
        ok, _, _ = _chain_executable_level1(["NotInTable"], IO_TYPES)
        self.assertFalse(ok)


# ── Level 2 unit tests (mocked validator) ───────────────────────

class _FakeValidator:
    def __init__(self, verdicts: dict):
        self._verdicts = {tuple(k): v for k, v in verdicts.items()}

    def validate_chain(self, chain):
        is_valid, issues = self._verdicts.get(tuple(chain), (True, []))
        return SimpleNamespace(is_valid=is_valid, issues=issues)


class Level2Tests(unittest.TestCase):
    def test_valid_and_no_issues_passes(self):
        v = _FakeValidator({("Slope", "Hillshade"): (True, [])})
        ok, issues = _chain_executable_level2(["Slope", "Hillshade"], v)
        self.assertTrue(ok)
        self.assertEqual(issues, 0)

    def test_valid_but_has_issues_fails(self):
        v = _FakeValidator({("A", "B"): (True, ["minor io mismatch"])})
        ok, issues = _chain_executable_level2(["A", "B"], v)
        self.assertFalse(ok)
        self.assertEqual(issues, 1)

    def test_invalid_fails(self):
        v = _FakeValidator({("A", "B"): (False, [])})
        ok, _ = _chain_executable_level2(["A", "B"], v)
        self.assertFalse(ok)

    def test_validator_exception_fails_safely(self):
        class Broken:
            def validate_chain(self, chain):
                raise RuntimeError("Neo4j dead")

        ok, issues = _chain_executable_level2(["A", "B"], Broken())
        self.assertFalse(ok)
        self.assertEqual(issues, -1)


# ── Integration: dual-denominator, back-fill contract ──────────

class ComputeExecutableRatioTests(unittest.TestCase):
    def _sample(self, idx, tt="A"):
        return {"index": idx, "task_type": tt, "task_name": f"s{idx}"}

    def test_dual_denominators(self):
        """Overall = exec/total, conditional = exec/counted."""
        test_set = [self._sample(i) for i in range(1, 5)]
        l3_results = [
            {"selected_qgis_chain": ["Slope", "Hillshade"]},            # L1 ✓
            {"selected_qgis_chain": ["Slope", "Buffer vectors"]},        # L1 ✗
            {"selected_qgis_chain": ["Buffer vectors", "Clip"]},         # L1 ✓
            {"selected_qgis_chain": None},                               # missing
        ]
        diag = compute_executable_ratio(test_set, l3_results, io_types=IO_TYPES)
        s = diag["summary"]
        self.assertEqual(s["total_samples"], 4)
        self.assertEqual(s["counted_samples"], 3)
        self.assertEqual(s["missing_chains"], 1)
        self.assertEqual(s["level1_local_executable"], 2)
        # overall = 2/4 = 0.5 (paper metric)
        self.assertAlmostEqual(s["level1_local_ratio_overall"], 0.5, places=3)
        # conditional = 2/3 ≈ 0.667
        self.assertAlmostEqual(s["level1_local_ratio_conditional"], 2 / 3, places=3)

    def test_backfill_contract_reads_qgis_chain_too(self):
        """Baseline path writes qgis_chain not selected_qgis_chain — must still be read."""
        test_set = [self._sample(1), self._sample(2)]
        l3_results = [
            {"qgis_chain": ["Slope", "Hillshade"]},       # back-filled, no selected_qgis_chain
            {"selected_qgis_chain": ["Clip", "Clip"]},    # reranker path
        ]
        diag = compute_executable_ratio(test_set, l3_results, io_types=IO_TYPES)
        s = diag["summary"]
        self.assertEqual(s["counted_samples"], 2)
        self.assertEqual(s["level1_local_executable"], 2)
        self.assertAlmostEqual(s["level1_local_ratio_overall"], 1.0, places=3)

    def test_level2_overall_and_conditional(self):
        test_set = [self._sample(i) for i in range(1, 4)]
        l3_results = [
            {"selected_qgis_chain": ["Slope", "Hillshade"]},
            {"selected_qgis_chain": ["Buffer vectors", "Clip"]},
            {"selected_qgis_chain": None},
        ]
        # Only the second chain passes L2.
        validator = _FakeValidator({
            ("Slope", "Hillshade"): (False, ["KG says nope"]),
            ("Buffer vectors", "Clip"): (True, []),
        })
        diag = compute_executable_ratio(
            test_set, l3_results, io_types=IO_TYPES, validator=validator,
        )
        s = diag["summary"]
        self.assertEqual(s["total_samples"], 3)
        self.assertEqual(s["counted_samples"], 2)
        self.assertEqual(s["level2_kg_executable"], 1)
        # overall = 1/3
        self.assertAlmostEqual(s["level2_kg_ratio_overall"], 1 / 3, places=3)
        # conditional = 1/2
        self.assertAlmostEqual(s["level2_kg_ratio_conditional"], 0.5, places=3)

    def test_overall_gap_is_overall_minus_overall(self):
        """overall_level1_minus_level2 uses OVERALL ratios, not conditional."""
        test_set = [self._sample(i) for i in range(1, 3)]
        l3_results = [
            {"selected_qgis_chain": ["Slope", "Hillshade"]},
            {"selected_qgis_chain": ["Buffer vectors", "Clip"]},
        ]
        validator = _FakeValidator({
            ("Slope", "Hillshade"): (False, ["nope"]),
            ("Buffer vectors", "Clip"): (True, []),
        })
        diag = compute_executable_ratio(
            test_set, l3_results, io_types=IO_TYPES, validator=validator,
        )
        s = diag["summary"]
        # L1 overall = 2/2 = 1.0; L2 overall = 1/2 = 0.5 → gap = 0.5
        self.assertAlmostEqual(s["overall_level1_minus_level2"], 0.5, places=3)

    def test_by_task_type_uses_new_keys(self):
        test_set = [
            self._sample(1, tt="Vegetation"),
            self._sample(2, tt="Vegetation"),
            self._sample(3, tt="Topography"),
        ]
        l3_results = [
            {"selected_qgis_chain": ["Slope", "Hillshade"]},            # ✓
            {"selected_qgis_chain": ["Slope", "Buffer vectors"]},        # ✗
            {"selected_qgis_chain": ["Buffer vectors", "Clip"]},         # ✓
        ]
        diag = compute_executable_ratio(test_set, l3_results, io_types=IO_TYPES)
        bt = diag["by_task_type"]
        self.assertEqual(bt["Vegetation"]["n"], 2)
        self.assertEqual(bt["Vegetation"]["level1_local_exec"], 1)
        self.assertEqual(bt["Topography"]["level1_local_exec"], 1)

    def test_no_io_types_still_runs_level2_if_validator_given(self):
        """If local io_types missing but KG validator provided, L2 still computable."""
        test_set = [self._sample(1)]
        l3_results = [{"selected_qgis_chain": ["Slope", "Hillshade"]}]
        validator = _FakeValidator({("Slope", "Hillshade"): (True, [])})

        diag = compute_executable_ratio(
            test_set, l3_results, io_types={}, validator=validator,
        )
        s = diag["summary"]
        self.assertIsNone(s["level1_local_ratio_overall"])
        self.assertAlmostEqual(s["level2_kg_ratio_overall"], 1.0, places=3)

    def test_zero_counted_samples_returns_none_not_zero(self):
        """Regression: all samples missing chain → ratios must be None, not 0.0.

        The old bug reported 0.00% executable which reads as 'everything failed'.
        None signals 'undefined' so downstream prints N/A.
        """
        test_set = [self._sample(1), self._sample(2), self._sample(3)]
        l3_results = [
            {"selected_qgis_chain": None},
            {"selected_qgis_chain": None},
            {},  # no key at all
        ]
        diag = compute_executable_ratio(test_set, l3_results, io_types=IO_TYPES)
        s = diag["summary"]

        self.assertEqual(s["total_samples"], 3)
        self.assertEqual(s["counted_samples"], 0)
        self.assertEqual(s["missing_chains"], 3)
        self.assertEqual(s["level1_local_executable"], 0)
        # Overall denominator = total > 0, so this is a real 0.0
        self.assertEqual(s["level1_local_ratio_overall"], 0.0)
        # Conditional denominator = counted = 0, must be None (not 0.0)
        self.assertIsNone(s["level1_local_ratio_conditional"])

    def test_zero_total_samples_returns_none_for_both(self):
        """Edge case: empty test_set → both denominators are 0."""
        diag = compute_executable_ratio(
            test_set=[], l3_results=[], io_types=IO_TYPES,
        )
        s = diag["summary"]
        self.assertIsNone(s["level1_local_ratio_overall"])
        self.assertIsNone(s["level1_local_ratio_conditional"])


if __name__ == "__main__":
    unittest.main()
