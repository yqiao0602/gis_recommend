from __future__ import annotations

import sys
import unittest
from pathlib import Path
from types import SimpleNamespace


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from gis_recommend.knowledge_graph.chain_repair import ChainRepairer
from gis_recommend.operators.qgis_candidate_generator import QGISCandidate, StepInfo


def _make_candidate(step_operator: str, *, is_unknown: bool, confidence: float) -> QGISCandidate:
    step = StepInfo(
        position=0,
        l3_code="L3_0",
        operator=step_operator,
        is_unknown=is_unknown,
        confidence=confidence,
    )
    return QGISCandidate(
        qgis_sequence=[step_operator],
        l3_sequence=["L3_0"],
        steps=[step],
        score=confidence,
        confidence=confidence,
        unknown_count=int(is_unknown),
        unknown_ratio=1.0 if is_unknown else 0.0,
        has_critical_unknown=is_unknown,
    )


class ChainRepairTests(unittest.TestCase):
    def test_apply_repair_syncs_step_metadata_for_replaced_unknown(self):
        repairer = ChainRepairer(retriever=None, validator=None, llm_scorer=None, io_types={})
        candidate = _make_candidate("slope", is_unknown=False, confidence=0.4)

        repaired = repairer._apply_repair(
            candidate,
            0,
            {"operator_name": "buffer", "confidence": 0.8},
        )

        self.assertEqual(repaired.qgis_sequence, ["buffer"])
        self.assertEqual(repaired.steps[0].operator, "buffer")
        self.assertFalse(repaired.steps[0].is_unknown)
        self.assertIsNone(repaired.steps[0].unknown_info)
        self.assertEqual(repaired.steps[0].confidence, 0.8)

        self.assertEqual(candidate.qgis_sequence, ["slope"])
        self.assertEqual(candidate.steps[0].operator, "slope")
        self.assertFalse(candidate.steps[0].is_unknown)

    def test_repair_returns_report_only_suggestion_without_mutating_candidate(self):
        class Retriever:
            def get_operators_for_l3(self, *args, **kwargs):
                return [{"name": "buffer", "confidence": 0.8}]

            def get_related_operators(self, *args, **kwargs):
                return []

        class Validator:
            def validate_chain(self, chain):
                return SimpleNamespace(issues=[] if chain == ["buffer"] else ["io"], step_details=[])

        repairer = ChainRepairer(
            retriever=Retriever(),
            validator=Validator(),
            llm_scorer=None,
            io_types={},
        )
        candidate = _make_candidate("slope", is_unknown=False, confidence=0.4)
        validation = SimpleNamespace(
            issues=["io"],
            step_details=[{"index": 0, "io_check": {"compatible": False}}],
        )

        repaired, final_validation, log = repairer.repair(candidate, validation, "query")

        self.assertIs(repaired, candidate)
        self.assertIs(final_validation, validation)
        self.assertEqual(candidate.qgis_sequence, ["slope"])
        self.assertEqual(log[0]["action"], "suggestion")
        self.assertFalse(log[0]["applied"])
        self.assertEqual(log[0]["suggested_chain"], ["buffer"])


if __name__ == "__main__":
    unittest.main()
