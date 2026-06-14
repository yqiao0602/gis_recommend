from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from gis_recommend.data.vector_training_builder import to_training_sample


SPECIAL = {"<PAD>": -1, "<UNK>": -2, "<START>": -3, "<END>": -4}
CODE_TO_ID = {"L3_02_01_01": 10, "L3_02_06_02": 11, "L3_01_02_03": 3}
TT_TO_ID = {"Unknown": 0, "Other / Sparse": 28}


class ToTrainingSampleTests(unittest.TestCase):
    def _described(self, **over):
        d = {
            "qgis_ops": ["native:buffer", "native:extractbyexpression"],
            "operator_names": ["Buffer", "Extract by expression"],
            "task_description_en": "Buffer features then filter by an attribute expression",
            "optional_l3_sequence": ["L3_02_01_01", "L3_02_06_02"],
            "modality": "pure_vector",
            "source": "standard_v2",
        }
        d.update(over)
        return d

    def test_builds_labeled_workflow_schema_sample(self):
        s = to_training_sample(self._described(), code_to_id=CODE_TO_ID,
                               special_tokens=SPECIAL, task_type="Other / Sparse",
                               task_type_to_id=TT_TO_ID)
        # l3_sequence wraps content ids with START/END
        self.assertEqual(s["l3_sequence"], [-3, 10, 11, -4])
        self.assertEqual(s["l3_codes"], ["<START>", "L3_02_01_01", "L3_02_06_02", "<END>"])
        # operator_sequence = the QGIS alg-ids
        self.assertEqual(s["operator_sequence"], ["native:buffer", "native:extractbyexpression"])
        # task_metadata carries the assigned task_type + description
        self.assertEqual(s["task_metadata"]["task_type"], "Other / Sparse")
        self.assertEqual(s["task_metadata"]["task_description"],
                         "Buffer features then filter by an attribute expression")
        self.assertTrue(s["task_metadata"]["task_name"])  # non-empty derived name

    def test_drops_sample_with_out_of_vocab_l3_code(self):
        # a code not in the 94-vocab -> not clean training data -> None
        s = to_training_sample(self._described(optional_l3_sequence=["L3_02_01_01", "L3_99_99_99"]),
                               code_to_id=CODE_TO_ID, special_tokens=SPECIAL,
                               task_type="Other / Sparse", task_type_to_id=TT_TO_ID)
        self.assertIsNone(s)

    def test_drops_sample_with_no_l3(self):
        s = to_training_sample(self._described(optional_l3_sequence=[]),
                               code_to_id=CODE_TO_ID, special_tokens=SPECIAL,
                               task_type="Other / Sparse", task_type_to_id=TT_TO_ID)
        self.assertIsNone(s)


if __name__ == "__main__":
    unittest.main()
