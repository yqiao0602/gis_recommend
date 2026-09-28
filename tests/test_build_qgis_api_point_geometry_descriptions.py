from __future__ import annotations

import unittest

from scripts.build_qgis_api_point_geometry_descriptions import build_descriptions


class BuildQgisApiPointGeometryDescriptionsTest(unittest.TestCase):
    def test_builds_literal_source_fact_description(self) -> None:
        result = build_descriptions(
            [{"coordinate_origin_kind": "literal_coordinate_pair", "training_row_emitted": False}]
        )
        self.assertEqual(result[0]["description_fidelity"], "passed_source_fact_only")
        self.assertIn("固定坐标", result[0]["task_description_zh"])
        self.assertFalse(result[0]["llm_called"])

    def test_rejects_unsupported_origin(self) -> None:
        with self.assertRaisesRegex(ValueError, "unsupported"):
            build_descriptions(
                [{"coordinate_origin_kind": "unknown", "training_row_emitted": False}]
            )


if __name__ == "__main__":
    unittest.main()
