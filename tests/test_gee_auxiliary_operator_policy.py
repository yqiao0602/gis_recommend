import unittest

from gis_recommend.data import step2_clean_workflows
from gis_recommend.data.enhanced_sequence_cleaner_final import EnhancedSequenceCleanerFinal


class GeeAuxiliaryOperatorPolicyTests(unittest.TestCase):
    def setUp(self):
        self.step8_cleaner = EnhancedSequenceCleanerFinal()

    def assert_stage_decisions(self, operator, expected):
        self.assertEqual(
            step2_clean_workflows.is_auxiliary_op(operator),
            expected,
            f"Step2 decision differs for {operator}",
        )
        self.assertEqual(
            self.step8_cleaner.is_auxiliary_operator(operator),
            expected,
            f"Step8 decision differs for {operator}",
        )

    def test_earth_engine_value_methods_are_not_auxiliary_constructors(self):
        for operator in (
            "ee.Number.add",
            "ee.Number.parse",
            "ee.Date.advance",
            "ee.Date.fromYMD",
            "ee.List.sequence",
            "ee.List.map",
        ):
            with self.subTest(operator=operator):
                self.assert_stage_decisions(operator, False)

    def test_exact_auxiliary_constructors_remain_filtered(self):
        for operator in (
            "ee.Number",
            "ee.Date",
            "ee.List",
        ):
            with self.subTest(operator=operator):
                self.assert_stage_decisions(operator, True)

    def test_native_unknown_and_special_operators_are_not_claimed(self):
        for operator in (
            "Number.parseInt",
            "Date.getFullYear",
            "decisionTree.join",
            "<START>",
            None,
        ):
            with self.subTest(operator=operator):
                self.assert_stage_decisions(operator, False)

    def test_cleaning_stages_drop_exact_constructors_but_keep_methods(self):
        operators = [
            "ee.Number",
            "ee.Number.add",
            "ee.Date",
            "ee.Date.advance",
            "ee.List",
            "ee.List.sequence",
        ]
        expected = [
            "ee.Number.add",
            "ee.Date.advance",
            "ee.List.sequence",
        ]

        step2_config = {
            "filter_auxiliary": True,
            "aggressive": True,
            "max_cycle_len": 15,
            "spaced_min_repeats": 4,
            "spaced_min_gap": 2,
            "spaced_max_gap": 10,
            "min_length": 1,
            "max_length": 20,
            "min_uniqueness": 0.1,
        }
        self.assertEqual(
            step2_clean_workflows.clean_workflow(list(operators), step2_config),
            expected,
        )

        step8_workflow = {
            "l3_codes": ["<START>", "100", "101", "102", "103", "104", "105", "<END>"],
            "operator_sequence": list(operators),
            "confidences": [1.0] * len(operators),
            "ambiguity_flags": [False] * len(operators),
        }
        step8_config = {
            "filter_auxiliary": True,
            "aggressive": True,
            "min_length": 1,
            "min_uniqueness": 0.1,
        }

        cleaned_workflow, should_keep, metadata = self.step8_cleaner.clean_workflow(
            step8_workflow,
            step8_config,
        )

        self.assertTrue(should_keep, metadata)
        self.assertEqual(cleaned_workflow["operator_sequence"], expected)
        self.assertEqual(cleaned_workflow["l3_codes"], ["<START>", "101", "103", "105", "<END>"])
        self.assertEqual(metadata["tokens_from_auxiliary"], 3)


if __name__ == "__main__":
    unittest.main()
