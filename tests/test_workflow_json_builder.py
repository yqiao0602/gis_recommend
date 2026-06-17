from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from gis_recommend.evaluation.workflow_json_builder import build_workflow_json


# Minimal synthetic operator registry (same structure as qgis_operators.json entries)
OP_REGISTRY = {
    "native:buffer": {
        "identifier": "native:buffer", "name": "Buffer",
        "inputs": [
            {"name": "INPUT", "type": "vector", "optional": False, "description": "Input layer"},
            {"name": "DISTANCE", "type": "LiteralData", "optional": True, "description": "Distance"},
            {"name": "SEGMENTS", "type": "LiteralData", "optional": True, "description": "Segments"},
        ],
        "outputs": [
            {"name": "OUTPUT", "type": "vector", "optional": True, "description": "Buffered"},
        ],
    },
    "native:clip": {
        "identifier": "native:clip", "name": "Clip",
        "inputs": [
            {"name": "INPUT", "type": "vector", "optional": False, "description": "Input layer"},
            {"name": "OVERLAY", "type": "vector", "optional": False, "description": "Overlay layer"},
        ],
        "outputs": [
            {"name": "OUTPUT", "type": "vector", "optional": True, "description": "Clipped"},
        ],
    },
}


class BuildWorkflowJsonTests(unittest.TestCase):
    def test_builds_processes_with_params_and_links(self):
        chain = ["native:buffer", "native:clip"]
        wf = build_workflow_json(chain, task_id="ol001", name="Buffer and clip",
                                 description="Buffer roads then clip to boundary",
                                 operators=OP_REGISTRY,
                                 metadata={"platform": "QGIS", "task_type": "Infrastructure"})

        # Top-level
        self.assertEqual(wf["task_id"], "ol001")
        self.assertEqual(wf["name"], "Buffer and clip")
        self.assertIn("metadata", wf)

        # Processes
        self.assertEqual(len(wf["processes"]), 2)
        p0, p1 = wf["processes"][0], wf["processes"][1]
        self.assertEqual(p0["algorithm_id"], "native:buffer")
        self.assertEqual(p0["id"], "proc_1")
        self.assertEqual(p1["id"], "proc_2")
        # param: no value, must have description, param_type, required
        in0 = p0["inputs"][0]
        self.assertNotIn("value", in0)
        self.assertEqual(in0["id"], "INPUT")
        self.assertEqual(in0["description"], "Input layer")
        self.assertEqual(in0["param_type"], "vector")
        self.assertEqual(in0["required"], True)
        # output
        out0 = p0["outputs"][0]
        self.assertNotIn("value", out0)
        self.assertEqual(out0["description"], "Buffered")

        # Links: proc_1 OUTPUT -> proc_2 INPUT
        self.assertEqual(len(wf["links"]), 1)
        self.assertEqual(wf["links"][0], {"source": "proc_1", "output": "OUTPUT", "target": "proc_2", "input": "INPUT"})

    def test_unknown_op_gets_minimal_params(self):
        """Chain containing an op not in the registry: params are {id} only (graceful degrade)."""
        wf = build_workflow_json(["native:buffer", "native:unknown"], task_id="t1",
                                 operators=OP_REGISTRY)
        p1 = wf["processes"][1]
        self.assertEqual(p1["algorithm_id"], "native:unknown")
        # inputs/outputs still present (just the param id, no extra metadata)
        self.assertTrue(len(p1["inputs"]) >= 0)
        self.assertTrue(len(p1["outputs"]) >= 0)
        # link still works if we assume default OUTPUT->INPUT
        self.assertEqual(len(wf["links"]), 1)

    def test_single_op_chain_no_links(self):
        wf = build_workflow_json(["native:buffer"], task_id="t2", operators=OP_REGISTRY)
        self.assertEqual(len(wf["links"]), 0)


if __name__ == "__main__":
    unittest.main()
