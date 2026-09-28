import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from gis_recommend.legacy.gee_pipeline import step4_standardize_chains


class GeeStep4StandardizePolicyTests(unittest.TestCase):
    def setUp(self):
        self.gee_standard_ops = {
            "ee.image.select",
            "ee.image.rename",
            "ee.image.reduceregion",
            "export.image.toasset",
            "export.image.todrive",
        }

    def assert_not_synthesized_as_image(self, operator, expected_ops, expected_status):
        ops, status = step4_standardize_chains.standardize_operation(
            operator,
            self.gee_standard_ops,
        )

        self.assertEqual(ops, expected_ops)
        self.assertEqual(status, expected_status)
        self.assertFalse(
            any(op.startswith("ee.image.") for op in ops),
            f"{operator} was incorrectly normalized to {ops}",
        )

    def test_ui_export_native_and_unknown_dotted_calls_are_not_image_operations(self):
        cases = (
            ("ui.Chart.image.series", ["ui.chart.image.series"], "special"),
            ("Export.image.toAsset", ["export.image.toasset"], "special"),
            ("Date.getFullYear", ["date.getfullyear"], "native_js"),
            ("Number.parseInt", ["number.parseint"], "native_js"),
            ("decisionTree.join", ["decisiontree.join"], "unresolved_dotted"),
        )

        for operator, expected_ops, expected_status in cases:
            with self.subTest(operator=operator):
                self.assert_not_synthesized_as_image(
                    operator,
                    expected_ops,
                    expected_status,
                )

    def test_real_gee_variable_chains_still_use_standard_operator_library(self):
        self.assertEqual(
            step4_standardize_chains.standardize_operation(
                "image.select.rename",
                self.gee_standard_ops,
            ),
            (["ee.image.select", "ee.image.rename"], "standard"),
        )
        self.assertEqual(
            step4_standardize_chains.standardize_operation(
                "image.reduceRegion",
                self.gee_standard_ops,
            ),
            (["ee.image.reduceregion"], "standard"),
        )

    def test_default_operator_library_search_reaches_project_parent_root(self):
        with TemporaryDirectory() as tmp:
            root = Path(tmp)
            expected = root / "gee-operators" / "gee_operators_full_20251108_201454.json"
            expected.parent.mkdir()
            expected.write_text('{"operators": []}', encoding="utf-8")
            nested = root / "Algorithm_classification" / "system_redesign" / "src" / "gis_recommend" / "legacy"
            nested.mkdir(parents=True)

            self.assertEqual(
                step4_standardize_chains._find_gee_ops_file(nested),
                expected,
            )


if __name__ == "__main__":
    unittest.main()
